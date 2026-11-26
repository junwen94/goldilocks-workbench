"""Shared parts of S1 (workbench plan, "S1 qwen3.8 27B on Ollama"): the three clients, a capture proxy, the call
recorder, the environment record, bootstrap intervals and the argument classifier.

Calls no model on import. The clients are configured as goldilocks-agent will run qwen3.8: thinking off, the model
card's non-thinking sampling (temperature 0.7, top_p 0.8, as the predecessor sets them in `graph.py`), and an
explicit context length.
"""

import json
import platform
import random
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MODEL = "qwen3.8:latest"
OLLAMA = "http://127.0.0.1:11434"
TEMPERATURE = 0.7
TOP_P = 0.8
NUM_CTX = 32_768
CLIENTS = ("litellm", "ollama", "raw")


# --- clients ---------------------------------------------------------------------------------------------------


def litellm_chat(base_url: str, num_ctx: int = NUM_CTX, streaming: bool = False, top_p_field_only: bool = False) -> Any:
    """ChatLiteLLM as D11's model layer would build it; litellm turns reasoning_effort "none" into think: false.

    ChatLiteLLM's own `top_p` field does not reach Ollama (S1a found it missing from the request), so top_p also goes
    in `model_kwargs`; `top_p_field_only=True` builds it without that, to show the difference.
    """
    from langchain_litellm import ChatLiteLLM

    kwargs: dict[str, Any] = {"num_ctx": num_ctx, "reasoning_effort": "none"}
    if not top_p_field_only:
        kwargs["top_p"] = TOP_P
    return ChatLiteLLM(
        model=f"ollama_chat/{MODEL}",
        api_base=base_url,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        streaming=streaming,
        model_kwargs=kwargs,
    )


def ollama_chat(base_url: str, num_ctx: int = NUM_CTX) -> Any:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=MODEL, base_url=base_url, temperature=TEMPERATURE, top_p=TOP_P, num_ctx=num_ctx, reasoning=False
    )


def raw_chat(
    base_url: str,
    messages: Sequence[Mapping[str, Any]],
    *,
    fmt: Mapping[str, Any] | str | None = None,
    tools: Sequence[Mapping[str, Any]] | None = None,
    num_ctx: int | None = NUM_CTX,
    think: bool | None = False,
    timeout: float = 900,
) -> dict[str, Any]:
    """One non-streaming POST /api/chat. `num_ctx=None` or `think=None` leaves the field out, to see the defaults."""
    options: dict[str, Any] = {"temperature": TEMPERATURE, "top_p": TOP_P}
    if num_ctx is not None:
        options["num_ctx"] = num_ctx
    body: dict[str, Any] = {"model": MODEL, "messages": list(messages), "stream": False, "options": options}
    if think is not None:
        body["think"] = think
    if fmt is not None:
        body["format"] = fmt
    if tools is not None:
        body["tools"] = list(tools)
    return post_json(f"{base_url}/api/chat", body, timeout)


def post_json(url: str, body: Mapping[str, Any], timeout: float = 60) -> dict[str, Any]:
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result: dict[str, Any] = json.load(response)
    return result


def get_json(url: str, timeout: float = 30) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        result: dict[str, Any] = json.load(response)
    return result


def usage(message: Any) -> tuple[int | None, int | None]:
    """Prompt and output tokens of a LangChain AIMessage, as Ollama counted them."""
    meta = getattr(message, "usage_metadata", None) or {}
    return meta.get("input_tokens"), meta.get("output_tokens")


# --- capture proxy ---------------------------------------------------------------------------------------------


class CaptureProxy:
    """A localhost proxy that records every request body sent to Ollama and passes the response back unchanged.

    Responses are read whole and sent with a Content-Length, so streamed answers arrive as one block of NDJSON
    lines; clients parse them line by line either way.
    """

    def __init__(self, upstream: str, log: Path) -> None:
        self.upstream = upstream.rstrip("/")
        self.log = log
        self.lock = threading.Lock()
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

            def do_GET(self) -> None:
                self.forward(None)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                self.forward(self.rfile.read(length))

            def forward(self, body: bytes | None) -> None:
                proxy.record(self.command, self.path, body)
                request = urllib.request.Request(proxy.upstream + self.path, data=body, method=self.command)
                request.add_header("Content-Type", self.headers.get("Content-Type") or "application/json")
                try:
                    with urllib.request.urlopen(request, timeout=900) as upstream:
                        status, payload = upstream.status, upstream.read()
                        content_type = upstream.headers.get("Content-Type") or "application/json"
                except urllib.error.HTTPError as error:
                    status, payload = error.code, error.read()
                    content_type = error.headers.get("Content-Type") or "application/json"
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.tag: dict[str, Any] = {}
        self.last: dict[str, Any] = {}  # the last /api/chat body, whole, for the experiment that sent it

    def record(self, method: str, path: str, body: bytes | None) -> None:
        try:
            parsed: Any = json.loads(body) if body else None
        except ValueError:
            parsed = {"unparsed": len(body or b"")}
        entry = {"method": method, "path": path, "tag": self.tag, "summary": summarise(parsed)}
        with self.lock:
            if path.startswith("/api/chat") and isinstance(parsed, dict):
                self.last = parsed
            with self.log.open("a") as out:
                out.write(json.dumps(entry) + "\n")

    def __enter__(self) -> "CaptureProxy":
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.shutdown()
        self.server.server_close()


def summarise(body: Any) -> Any:
    """What a request asked Ollama for, without the messages themselves (the degradation prompts are long)."""
    if not isinstance(body, dict):
        return body
    fmt = body.get("format")
    return {
        "keys": sorted(body),
        "options": body.get("options"),
        "think": body.get("think", "absent"),
        "format": None if fmt is None else (fmt if isinstance(fmt, str) else {"schema_keys": sorted(fmt)}),
        "tools": [t.get("function", {}).get("name") for t in body.get("tools") or []],
        "tool_choice": body.get("tool_choice", "absent"),
        "stream": body.get("stream"),
        "messages": len(body.get("messages") or []),
        "message_chars": len(json.dumps(body.get("messages") or [])),
    }


# --- recording -------------------------------------------------------------------------------------------------


@dataclass
class Call:
    experiment: str
    case: str
    client: str
    run: int
    passed: bool | None
    outcome: str
    variant: str = ""
    seconds: float = 0.0
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class Recorder:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, call: Call) -> None:
        with self.path.open("a") as out:
            out.write(json.dumps(asdict(call), default=str) + "\n")


@contextmanager
def timed() -> Iterator[list[float]]:
    """Yields a one-item list that holds the elapsed seconds once the block ends."""
    box = [0.0]
    start = time.monotonic()
    try:
        yield box
    finally:
        box[0] = round(time.monotonic() - start, 2)


def environment(base_url: str = OLLAMA) -> dict[str, Any]:
    """Ollama's version, the model's digest and details, and the machine."""
    show = post_json(f"{base_url}/api/show", {"model": MODEL})
    tags = get_json(f"{base_url}/api/tags")
    digest = next((m.get("digest") for m in tags.get("models", []) if m.get("name") == MODEL), None)
    info = show.get("model_info", {})
    context = next((v for k, v in info.items() if k.endswith(".context_length")), None)

    def sysctl(name: str) -> str:
        try:
            return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, check=False).stdout.strip()
        except OSError:
            return ""

    return {
        "ollama_version": get_json(f"{base_url}/api/version").get("version"),
        "model": MODEL,
        "digest": digest,
        "details": show.get("details", {}),
        "model_context_length": context,
        "machine": platform.machine(),
        "chip": sysctl("machdep.cpu.brand_string"),
        "memory_bytes": sysctl("hw.memsize"),
        "python": platform.python_version(),
    }


# --- statistics ------------------------------------------------------------------------------------------------


def bootstrap(per_case: Sequence[float], resamples: int = 2000, seed: int = 1) -> tuple[float, float, float]:
    """Mean of per-case scores and a 95% percentile interval from resampling cases with replacement."""
    if not per_case:
        return (float("nan"), float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(per_case)
    means = sorted(sum(rng.choice(per_case) for _ in range(n)) / n for _ in range(resamples))
    return (sum(per_case) / n, means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1])


# --- argument checks -------------------------------------------------------------------------------------------

JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


def type_ok(value: Any, schema: Mapping[str, Any]) -> bool:
    kinds = schema.get("type")
    if kinds is None:
        return True
    names = [kinds] if isinstance(kinds, str) else list(kinds)
    for name in names:
        if isinstance(value, bool) and name in ("integer", "number"):
            continue
        if isinstance(value, JSON_TYPES[name]):
            if name == "string" and "enum" in schema and value not in schema["enum"]:
                continue
            if name == "array" and isinstance(value, list):
                if "items" in schema and not all(type_ok(item, schema["items"]) for item in value):
                    continue
                if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
                    continue
            return True
    return False


def classify(arguments: Any, schema: Mapping[str, Any]) -> list[str]:
    """Problems of a tool call's arguments against an object schema: missing:<f>, extra:<f>, mistyped:<f>."""
    if not isinstance(arguments, dict):
        return ["not-an-object"]
    properties: Mapping[str, Any] = schema.get("properties", {})
    problems = [f"missing:{name}" for name in schema.get("required", []) if name not in arguments]
    for name, value in arguments.items():
        if name not in properties:
            problems.append(f"extra:{name}")
        elif not type_ok(value, properties[name]):
            problems.append(f"mistyped:{name}")
    return problems
