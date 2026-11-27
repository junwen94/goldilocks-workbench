"""S1b, the routing of qwen3.8 27B on Ollama (workbench plan, "S1"; changes/2026-11-25-workbench/spikes/).

Three experiments, each case run --runs times, every call through the capture proxy, which now passes streamed
replies on as they arrive (S1a's proxy read them whole):
  predecessor  the predecessor's 36 tool-choice cases (stfc/goldilocks-agent#68 and after; carried in
               s1_predecessor_cases.py) with its prompt and 8 web tools, by three paths:
               litellm         ChatLiteLLM, our layer, without streaming
               litellm-stream  ChatLiteLLM, streaming
               litellm-raw     #68's own path: litellm.completion, streaming, its options (no num_ctx), and tool-call
                               pieces joined by index unless a new id starts a new call
  catalogue    D27 step-1 picks on 30 labelled goals, with the short (51-line) and the long (81-line) catalogue
  genius       D27 step-1 picks on GENIUS's requests that s1_genius's rule labels, with the short catalogue

Step-1 picks use ChatLiteLLM's schema-constrained output (S1a's forced-choice route).
Usage: uv run python spikes/S1/s1_routing.py --out spikes/S1/runs/<name> [--runs 3] [--only catalogue,genius]
"""

import argparse
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import s1_catalogue as cat
import s1_common as c
import s1_genius as g
import s1_mechanics as m

MODEL_RAW = f"ollama_chat/{c.MODEL}"
PREDECESSOR_PATHS = ("litellm", "litellm-stream", "litellm-raw")


def join_tool_call_pieces(pieces: Iterable[Any], split_on_new_id: bool = True) -> list[dict[str, Any]]:
    """Joins streamed tool-call pieces into calls: a piece with another index starts a new call, and so, with
    `split_on_new_id`, does a piece with another id at the same index (litellm streams Ollama's parallel calls whole,
    each with its own id, all at index 0). Written for S1 from the predecessor's description of its fix (6473803)."""
    calls: list[dict[str, Any]] = []
    for piece in pieces:
        function = getattr(piece, "function", None)
        name = getattr(function, "name", None) or ""
        arguments = getattr(function, "arguments", None) or ""
        index, call_id = getattr(piece, "index", None), getattr(piece, "id", None)
        last = calls[-1] if calls else None
        new = (
            last is None
            or index != last["index"]
            or (split_on_new_id and call_id is not None and last["id"] is not None and call_id != last["id"])
        )
        if new:
            calls.append({"index": index, "id": call_id, "name": name, "arguments": arguments})
        else:
            assert last is not None
            last["name"] = last["name"] or name
            last["arguments"] += arguments
    return calls


def as_arguments(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    parsed = m.parse_json(raw) if isinstance(raw, str) else None
    return parsed if isinstance(parsed, dict) else raw


def step_of(message: Any) -> Any:
    import s1_predecessor_cases as p

    calls = [{"name": t["name"], "arguments": t["args"]} for t in getattr(message, "tool_calls", None) or []]
    calls += [
        {"name": t.get("name") or "", "arguments": t.get("args") or ""}
        for t in getattr(message, "invalid_tool_calls", None) or []
    ]
    return p.Step(tool_calls=calls, content=str(message.content or ""))


def predecessor(ctx: m.Context) -> None:
    import litellm
    import s1_predecessor_cases as p
    import s1_predecessor_prompt as prompt
    from langchain_core.messages import convert_to_messages

    for run in range(ctx.runs):
        for case in p.CASES:
            messages = [{"role": "system", "content": prompt.SYSTEM}, *case.messages]
            for path in PREDECESSOR_PATHS:

                def body(call: c.Call, path: str = path, case: Any = case, messages: list[Any] = messages) -> None:
                    if path == "litellm-raw":
                        stream = litellm.completion(
                            model=MODEL_RAW,
                            api_base=ctx.base,
                            messages=messages,
                            tools=p.TOOLS,
                            stream=True,
                            reasoning_effort="none",
                            temperature=c.TEMPERATURE,
                            top_p=c.TOP_P,
                        )
                        content, pieces = "", []
                        for chunk in stream:
                            delta = chunk.choices[0].delta
                            content += delta.content or ""
                            pieces += list(delta.tool_calls or [])
                        joined = join_tool_call_pieces(pieces)
                        call.detail["calls_without_split"] = len(join_tool_call_pieces(pieces, split_on_new_id=False))
                        step = p.Step(
                            tool_calls=[{"name": x["name"], "arguments": as_arguments(x["arguments"])} for x in joined],
                            content=content,
                        )
                    else:
                        llm = c.litellm_chat(ctx.base, streaming=path == "litellm-stream").bind_tools(p.TOOLS)
                        lc_messages = convert_to_messages(messages)
                        if path == "litellm-stream":
                            chunks = list(llm.stream(lc_messages))
                            message = chunks[0]
                            for chunk in chunks[1:]:
                                message = message + chunk
                        else:
                            message = llm.invoke(lc_messages)
                        call.prompt_tokens, call.output_tokens = c.usage(message)
                        step = step_of(message)
                    failure = case.judge(step)
                    call.passed, call.outcome = failure is None, "pass" if failure is None else f"fail:{failure}"[:120]
                    call.detail.update(
                        tool_calls=step.tool_calls,
                        content=step.content[:300],
                        pieces=ctx.proxy.chunks,
                        in_68=case.in_68,
                        category=case.category,
                    )

                attempt(
                    ctx, c.Call("predecessor", case.id, path, run, None, "", "in68" if case.in_68 else "later"), body
                )


def pick(
    ctx: m.Context,
    call: c.Call,
    request: str,
    size: str,
    recipes: frozenset[str],
    groups: Sequence[frozenset[str]],
    no_tools: bool = False,
    template: str = cat.SYSTEM,
) -> cat.Pick:
    system = template.format(catalogue=cat.catalogue(size))
    parsed, raw = m.structured(c.litellm_chat(ctx.base), cat.schema(size), m.lc(system, request))
    call.prompt_tokens, call.output_tokens = c.usage(raw)
    result = cat.score_pick(parsed, recipes, groups, size, no_tools)
    call.passed, call.outcome = result.passed, result.outcome[:120]
    call.detail.update(result.detail)
    return result


def catalogue(ctx: m.Context) -> None:
    for variant, (size, template) in cat.VARIANTS.items():
        for run in range(ctx.runs):
            for item in cat.GOALS:

                def body(call: c.Call, item: cat.Goal = item, size: str = size, template: str = template) -> None:
                    pick(ctx, call, item.request, size, item.recipes, item.groups, item.no_tools, template)

                attempt(ctx, c.Call("catalogue", item.id, "litellm", run, None, "", variant), body)


def genius(ctx: m.Context, requests: Sequence[g.Request] | None = None) -> None:
    labelled = [(r, g.label(r.request)) for r in (requests if requests is not None else g.load())]
    allowed = frozenset({"none", "recipe.one_material"})
    for run in range(ctx.runs):
        for request, label in labelled:
            if label is None:
                continue

            def body(call: c.Call, request: g.Request = request, label: str = label) -> None:
                calculation = frozenset(g.CALCULATION[label])
                result = pick(ctx, call, request.request, "short", allowed, [frozenset(cat.DB), calculation])
                call.detail.update(
                    label=label, calculation_picked=bool(calculation & set(result.detail.get("tools", [])))
                )

            attempt(ctx, c.Call("genius", f"r{request.record}", "litellm", run, None, "", "short"), body)


def attempt(ctx: m.Context, call: c.Call, body: Callable[[c.Call], None]) -> None:
    ctx.proxy.chunks = 0
    m.attempt(ctx, call, body)


EXPERIMENTS: dict[str, Callable[[m.Context], None]] = {
    "predecessor": predecessor,
    "catalogue": catalogue,
    "genius": genius,
}


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="a new folder for calls.jsonl, requests.jsonl")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", default=",".join(EXPERIMENTS), help="comma-separated experiments")
    parser.add_argument("--ollama", default=c.OLLAMA)
    args = parser.parse_args(argv)
    chosen = [name.strip() for name in args.only.split(",") if name.strip()]
    unknown = [name for name in chosen if name not in EXPERIMENTS]
    if unknown:
        parser.error(f"unknown experiments: {', '.join(unknown)}")
    if (args.out / "calls.jsonl").exists():
        parser.error(f"{args.out} already has calls.jsonl; use a new folder")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "environment.json").write_text(json.dumps(c.environment(args.ollama), indent=2) + "\n")
    with c.CaptureProxy(args.ollama, args.out / "requests.jsonl", stream_through=True) as proxy:
        ctx = m.Context(proxy, c.Recorder(args.out / "calls.jsonl"), args.runs)
        for name in chosen:
            EXPERIMENTS[name](ctx)
    return 0


def summary(calls: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Figures the result needs beyond s1_report's tables: GENIUS by label and with the calculation tool alone,
    and catalogue goals' extra and distractor picks."""
    by_label: dict[str, list[bool]] = {}
    calculation: list[bool] = []
    extras: dict[str, list[int]] = {}
    parts: dict[str, list[tuple[bool, bool]]] = {}
    distractors = 0
    for call in calls:
        detail = call["detail"]
        if "recipe_ok" in detail:
            parts.setdefault(f"{call['experiment']}-{call['variant']}", []).append(
                (bool(detail["recipe_ok"]), bool(detail["tools_ok"]))
            )
        if call["experiment"] == "genius" and "label" in detail:
            by_label.setdefault(detail["label"], []).append(bool(call["passed"]))
            calculation.append(bool(detail.get("calculation_picked")))
        if call["experiment"] in ("catalogue", "genius") and "extra" in detail:
            extras.setdefault(f"{call['experiment']}-{call['variant']}", []).append(detail["extra"])
            distractors += bool(detail.get("distractors"))
    return {
        "genius_by_label": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by_label.items())},
        "genius_calculation_tool_picked": f"{sum(calculation)}/{len(calculation)}",
        "mean_extra_tools": {k: round(sum(v) / len(v), 2) for k, v in sorted(extras.items())},
        "recipe_ok_and_tools_ok": {
            k: f"recipe {sum(r for r, _ in v)}/{len(v)}, tools {sum(t for _, t in v)}/{len(v)}"
            for k, v in sorted(parts.items())
        },
        "picks_with_a_distractor": distractors,
    }


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
