"""S4, interrupts and resume through our server (workbench plan, Phase 1): the experiments.

Each server experiment runs its own server (s4_app.py) as a subprocess on 127.0.0.1, with its own SQLite checkpoint
file, skills folder and effects file in a fresh folder under ~/.cache/goldilocks-spikes/s4/. "Restart" means SIGKILL
to the server's process, then a new process on the same files. Experiments:
  tool              a tool of the Deep Agents loop pauses; the card comes on the turn's stream; the answer resumes it
  tool-restart      the same, with the server SIGKILLed while paused and a new one started before the answer
  answers           an answer that fails the card's schema, a pause ID that is not pending, the valid answer, then the
                    answered ID again
  executor          start_run; the run's three pauses come as one card on the conversation's events stream; a second
                    turn while the run is paused; one answer for all three pauses
  staggered         the same, answered one pause at a time, as the watcher would when jobs end apart
  executor-restart  answer x's pause, SIGKILL, start again, answer y's and z's
  skills-restart    pause in a turn, change the skills on disk, SIGKILL, start again, answer; then a later turn, a
                    later turn that resets the skills, and a new conversation
  facts             the library facts of s4_facts, in this process
Every trial writes one JSON line with its observations and its verdict (s4_judge).
Usage: uv run python spikes/S4/s4_experiments.py [--only tool,executor] [--trials N] [--out FILE] [--keep]
"""

import argparse
import json
import os
import platform
import queue
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from importlib.metadata import version
from pathlib import Path
from typing import Any

import httpx
import s4_judge as j
from s4_facts import all_facts

HERE = Path(__file__).resolve().parent
CACHE = Path.home() / ".cache" / "goldilocks-spikes" / "s4"
TRIALS = 20
TIMEOUT = 30.0
PACKAGES = (
    "deepagents",
    "langgraph",
    "langgraph-checkpoint",
    "langgraph-checkpoint-sqlite",
    "langchain",
    "langchain-core",
    "fastapi",
    "uvicorn",
    "aiosqlite",
    "httpx",
)
Writer = Callable[[dict[str, Any]], None]


def parse_sse(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Frames from server-sent event lines: each frame's `data:` is one JSON object, ended by a blank line."""
    data: list[str] = []
    for line in lines:
        if line == "":
            if data:
                yield json.loads("\n".join(data))
            data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield json.loads("\n".join(data))


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class Server:
    """One run folder and the server process that serves it; `restart` kills it with SIGKILL and starts another."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.root = folder / "root"
        (self.root / "skills").mkdir(parents=True, exist_ok=True)
        self.effects = folder / "effects.jsonl"
        self.model_log = folder / "model.jsonl"
        self.process: subprocess.Popen[bytes] | None = None
        self.base = ""
        self.pids: list[int] = []

    def start(self) -> float:
        started = time.monotonic()
        port = free_port()
        self.base = f"http://127.0.0.1:{port}"
        args = [sys.executable, str(HERE / "s4_app.py"), "--port", str(port), "--db", str(self.folder / "db.sqlite")]
        args += ["--root", str(self.root), "--effects", str(self.effects), "--model-log", str(self.model_log)]
        with (self.folder / "server.log").open("ab") as log:
            self.process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = started + TIMEOUT
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"server exited with {self.process.returncode}; see {self.folder / 'server.log'}")
            try:
                health = httpx.get(f"{self.base}/health", timeout=1).json()
                if health["ready"]:
                    self.pids.append(int(health["pid"]))
                    return time.monotonic() - started
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        raise RuntimeError("server did not become ready")

    def kill(self) -> None:
        if self.process is not None and self.process.poll() is None:
            os.kill(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=TIMEOUT)

    def restart(self) -> float:
        self.kill()
        return self.start()

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.kill()

    def post_sse(self, path: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        with httpx.stream("POST", f"{self.base}{path}", json=body, timeout=TIMEOUT) as response:
            return list(parse_sse(response.iter_lines()))

    def turn(self, conversation: str, text: str, refresh: bool = False) -> list[dict[str, Any]]:
        return self.post_sse(f"/conversations/{conversation}/turn", {"text": text, "refresh_skills": refresh})

    def answer(self, conversation: str, pause: str, value: Any) -> list[dict[str, Any]]:
        return self.post_sse(f"/conversations/{conversation}/answer", {"pause_id": pause, "value": value})

    def run_answer(self, run: str, answers: dict[str, str]) -> int:
        return httpx.post(f"{self.base}/runs/{run}/answer", json={"answers": answers}, timeout=TIMEOUT).status_code

    def state(self, thread: str) -> dict[str, Any]:
        result: dict[str, Any] = httpx.get(f"{self.base}/threads/{thread}", timeout=TIMEOUT).json()
        return result

    def effects_of(self, thread: str) -> list[dict[str, Any]]:
        if not self.effects.exists():
            return []
        records = [json.loads(line) for line in self.effects.read_text().splitlines()]
        return [r for r in records if r.get("thread") == thread]


class Events:
    """Reads a conversation's events stream on a thread of its own until the server goes away."""

    def __init__(self, server: Server, conversation: str) -> None:
        self.frames: queue.Queue[dict[str, Any]] = queue.Queue()
        self.url = f"{server.base}/conversations/{conversation}/events"
        threading.Thread(target=self.read, daemon=True).start()

    def read(self) -> None:
        try:
            with httpx.stream("GET", self.url, timeout=httpx.Timeout(TIMEOUT, read=None)) as response:
                for frame in parse_sse(response.iter_lines()):
                    self.frames.put(frame)
        except httpx.HTTPError:
            return

    def wait(self, wanted: Callable[[dict[str, Any]], bool]) -> dict[str, Any] | None:
        deadline = time.monotonic() + TIMEOUT
        while (left := deadline - time.monotonic()) > 0:
            try:
                frame = self.frames.get(timeout=left)
            except queue.Empty:
                return None
            if wanted(frame):
                return frame
        return None


def is_card(thread: str, source: str | None = None) -> Callable[[dict[str, Any]], bool]:
    return lambda f: f.get("event") == "card" and f.get("thread") == thread and source in (None, f.get("source"))


def trial_tool(server: Server, tag: str, restart: bool) -> dict[str, Any]:
    conversation = f"conv-{uuid.uuid4()}"
    started = time.monotonic()
    obs: dict[str, Any] = {"restart": restart, "turn": server.turn(conversation, f"choose {tag}")}
    obs["seconds_to_card"] = time.monotonic() - started
    card = j.last(obs["turn"], "card")
    pause = card["pauses"][0]["id"] if card else "none"
    if restart:
        obs["seconds_to_ready"] = server.restart()
        obs["pids"] = server.pids[-2:]
        obs["catch_up"] = Events(server, conversation).wait(is_card(conversation, "catch-up"))
    started = time.monotonic()
    obs["answer"] = server.answer(conversation, pause, {"structure": j.CHOSEN})
    obs["seconds_to_end"] = time.monotonic() - started
    obs["state"] = server.state(conversation)
    return obs


def trial_answers(server: Server, tag: str) -> dict[str, Any]:
    conversation = f"conv-{uuid.uuid4()}"
    obs: dict[str, Any] = {"turn": server.turn(conversation, f"choose {tag}")}
    card = j.last(obs["turn"], "card")
    pause = card["pauses"][0]["id"] if card else "none"
    obs["invalid"] = server.answer(conversation, pause, {"structure": 2})
    obs["stale"] = server.answer(conversation, uuid.uuid4().hex, {"structure": j.CHOSEN})
    obs["answer"] = server.answer(conversation, pause, {"structure": j.CHOSEN})
    obs["again"] = server.answer(conversation, pause, {"structure": j.CHOSEN})
    obs["state"] = server.state(conversation)
    return obs


def trial_executor(server: Server, tag: str, mode: str) -> dict[str, Any]:
    conversation = f"conv-{uuid.uuid4()}"
    events = Events(server, conversation)
    started = time.monotonic()
    obs: dict[str, Any] = {"mode": mode, "turn": server.turn(conversation, f"plan {tag}"), "cards": []}
    end = j.last(obs["turn"], "end")
    run = str(end.get("reply", "")).removeprefix("started ") if end else ""
    obs["run"] = run
    first = events.wait(is_card(run))
    obs["seconds_to_card"] = time.monotonic() - started
    obs["free"] = server.turn(conversation, f"hello {tag}")
    obs["bogus"] = server.run_answer(run, {uuid.uuid4().hex: "finished"})
    if first is not None:
        obs["cards"].append(first)
        pause = {p["payload"]["candidate"]: p["id"] for p in first["pauses"]}
        if mode == "together":
            server.run_answer(run, {pause[c]: j.RUN_ANSWERS[c] for c in j.CANDIDATES})
        else:
            server.run_answer(run, {pause["x"]: j.RUN_ANSWERS["x"]})
            obs["cards"].append(events.wait(is_card(run)))
            if mode == "staggered":
                server.run_answer(run, {pause["y"]: j.RUN_ANSWERS["y"]})
                obs["cards"].append(events.wait(is_card(run)))
                server.run_answer(run, {pause["z"]: j.RUN_ANSWERS["z"]})
            else:
                obs["seconds_to_ready"] = server.restart()
                obs["pids"] = server.pids[-2:]
                events = Events(server, conversation)
                obs["catch_up"] = events.wait(is_card(run, "catch-up"))
                server.run_answer(run, {pause[c]: j.RUN_ANSWERS[c] for c in ("y", "z")})
        obs["finished"] = events.wait(lambda f: f.get("event") == "run_finished" and f.get("run") == run)
    counts: dict[str, Counter[str]] = {"submit": Counter(), "wait": Counter(), "check": Counter()}
    finish = 0
    for record in server.effects_of(run):
        if record["node"] in counts:
            counts[record["node"]][record["candidate"]] += 1
        finish += record["node"] == "finish"
    obs["effects"] = {**{k: dict(v) for k, v in counts.items()}, "finish": finish}
    obs["processes"] = sorted({r["pid"] for r in server.effects_of(run)})
    return obs


def write_skills(root: Path, skills: dict[str, int]) -> None:
    folder = root / "skills"
    shutil.rmtree(folder, ignore_errors=True)
    for name, revision in skills.items():
        (folder / name).mkdir(parents=True)
        front = f"---\nname: {name}\ndescription: {name} skill, version {revision}\n---\n"
        text = f"{front}\n{name} body, version {revision}\n"
        (folder / name / "SKILL.md").write_text(text)


def trial_skills(server: Server, tag: str) -> dict[str, Any]:
    conversation = f"conv-{uuid.uuid4()}"
    write_skills(server.root, {"alpha": 1, "beta": 1})
    obs: dict[str, Any] = {"turn": server.turn(conversation, f"skills {tag}")}
    card = j.last(obs["turn"], "card")
    pause = card["pauses"][0]["id"] if card else "none"
    write_skills(server.root, {"alpha": 2, "gamma": 1})
    obs["seconds_to_ready"] = server.restart()
    obs["pids"] = server.pids[-2:]
    obs["catch_up"] = Events(server, conversation).wait(is_card(conversation, "catch-up"))
    obs["answer"] = server.answer(conversation, pause, {"structure": j.CHOSEN})
    obs["hello_same"] = server.turn(conversation, f"hello {tag}")
    obs["hello_refresh"] = server.turn(conversation, f"hello {tag}-refresh", refresh=True)
    obs["hello_new"] = server.turn(f"conv-{uuid.uuid4()}", f"hello {tag}-new")
    obs["state_skills"] = server.state(conversation)["skills"]
    model = [json.loads(line) for line in server.model_log.read_text().splitlines()]
    obs["seen"] = j.skills_seen(model, tag)
    return obs


Trial = Callable[[Server, str], dict[str, Any]]
Judge = Callable[[dict[str, Any]], list[str]]
TRIALS_BY_EXPERIMENT: dict[str, tuple[Trial, Judge]] = {
    "tool": (lambda s, t: trial_tool(s, t, False), j.judge_tool),
    "tool-restart": (lambda s, t: trial_tool(s, t, True), j.judge_tool),
    "answers": (trial_answers, j.judge_answers),
    "executor": (lambda s, t: trial_executor(s, t, "together"), j.judge_executor),
    "staggered": (lambda s, t: trial_executor(s, t, "staggered"), j.judge_executor),
    "executor-restart": (lambda s, t: trial_executor(s, t, "restart"), j.judge_executor),
    "skills-restart": (trial_skills, j.judge_skills),
}
EXPERIMENTS = [*TRIALS_BY_EXPERIMENT, "facts"]


def run_experiment(name: str, trials: int, base: Path, write: Writer) -> None:
    if name == "facts":
        for record in all_facts():
            write({"experiment": "facts", **record})
        return
    trial, judge = TRIALS_BY_EXPERIMENT[name]
    server = Server(base / name)
    try:
        server.start()
        for index in range(trials):
            tag = f"{name}-{index:02d}"
            try:
                obs = trial(server, tag)
                failures = judge(obs)
            except Exception as error:
                obs, failures = {}, [f"the trial raised {type(error).__name__}: {error}"]
            write({"experiment": name, "trial": index, "ok": not failures, "failures": failures, **obs})
    finally:
        server.stop()
        leftover = server.process is not None and server.process.poll() is None
        write({"experiment": name, "server_left_running": leftover, "processes": server.pids})


def environment() -> dict[str, Any]:
    return {
        "experiment": "environment",
        "python": platform.python_version(),
        "system": platform.platform(),
        "machine": platform.machine(),
        "sqlite": sqlite3.sqlite_version,
        "packages": {name: version(name) for name in PACKAGES},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=",".join(EXPERIMENTS))
    parser.add_argument("--trials", type=int, default=TRIALS)
    parser.add_argument("--out", type=Path, default=CACHE / "results" / f"{platform.system().lower()}.jsonl")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    chosen = args.only.split(",")
    unknown = sorted(set(chosen) - set(EXPERIMENTS))
    if unknown:
        parser.error(f"unknown experiments: {unknown}")
    if args.out.exists():
        parser.error(f"{args.out} exists; results of two runs are never mixed in one file")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    base = CACHE / time.strftime("%Y%m%d-%H%M%S")
    base.mkdir(parents=True)

    def write(record: dict[str, Any]) -> None:
        with args.out.open("a") as handle:
            handle.write(json.dumps(record) + "\n")
        if "ok" in record:
            print(record["experiment"], record["trial"], "ok" if record["ok"] else record["failures"], flush=True)

    write(environment())
    try:
        for name in chosen:
            run_experiment(name, args.trials, base, write)
    finally:
        if not args.keep:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
