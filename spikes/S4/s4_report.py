"""S4's tables for the result, from the driver's JSON lines.

  uv run python spikes/S4/s4_report.py ~/.cache/goldilocks-spikes/s4/results/darwin.jsonl

`summarise` does the counting and is tested offline (AGENTS.md rule 10); `render` only formats.
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PATHS = ("tool", "tool-restart", "answers", "executor", "staggered", "executor-restart", "skills-restart")
SKILL_POINTS = (
    "before_pause",
    "after_resume",
    "alpha_read",
    "beta_read",
    "same_thread_later",
    "refreshed",
    "new_thread",
)


def spread(values: list[float]) -> str:
    if not values:
        return "n/a"
    return f"{statistics.median(values):.2f} s, {max(values):.2f} s"


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    trials: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if "trial" in record:
            trials[record["experiment"]].append(record)
    paths = {}
    for name in PATHS:
        rows = trials.get(name, [])
        failures = Counter(f for r in rows for f in r["failures"])
        restarted = [r for r in rows if "catch_up" in r]
        paths[name] = {
            "passed": sum(1 for r in rows if r["ok"]),
            "trials": len(rows),
            "failures": dict(failures),
            "to_card": [r["seconds_to_card"] for r in rows if "seconds_to_card" in r],
            "to_end": [r["seconds_to_end"] for r in rows if "seconds_to_end" in r],
            "to_ready": [r["seconds_to_ready"] for r in rows if "seconds_to_ready" in r],
            "restarts": len(restarted),
            "catch_up_cards": sum(1 for r in restarted if r["catch_up"] is not None),
            "two_processes": sum(1 for r in restarted if len(set(r.get("pids", []))) == 2),
        }
    effects = {}
    for name in ("executor", "staggered", "executor-restart"):
        patterns: Counter[str] = Counter()
        for r in trials.get(name, []):
            if "effects" not in r:
                continue
            e = r["effects"]
            pattern = "; ".join(
                f"{node} " + ", ".join(f"{c} {e.get(node, {}).get(c, 0)}" for c in ("x", "y", "z"))
                for node in ("submit", "wait", "check")
            )
            patterns[f"{pattern}; finish {e.get('finish', 0)}"] += 1
        effects[name] = dict(patterns)
    skills: dict[str, dict[str, int]] = {}
    for point in SKILL_POINTS:
        skills[point] = dict(Counter(r["seen"][point] for r in trials.get("skills-restart", []) if "seen" in r))
    facts = {r["fact"]: {k: v for k, v in r.items() if k not in ("experiment", "fact")} for r in records if "fact" in r}
    environment = next((r for r in records if r.get("experiment") == "environment"), {})
    left = [r["experiment"] for r in records if r.get("server_left_running")]
    return {
        "environment": environment,
        "paths": paths,
        "effects": effects,
        "skills": skills,
        "facts": facts,
        "left": left,
    }


def render(summary: dict[str, Any]) -> str:
    out = []
    env = summary["environment"]
    if env:
        out.append(f"Environment: Python {env['python']}, {env['system']}, SQLite {env['sqlite']}")
        out.append(", ".join(f"{k} {v}" for k, v in env["packages"].items()))
        out.append("")
    out.append("| experiment | passed | to the card, median and max | to the end | restart to ready | catch-up cards |")
    out.append("|---|---|---|---|---|---|")
    for name, p in summary["paths"].items():
        if not p["trials"]:
            continue
        catch = f"{p['catch_up_cards']} of {p['restarts']}" if p["restarts"] else "n/a"
        out.append(
            f"| {name} | {p['passed']} of {p['trials']} | {spread(p['to_card'])} | {spread(p['to_end'])} "
            f"| {spread(p['to_ready'])} | {catch} |"
        )
    for name, p in summary["paths"].items():
        for failure, n in p["failures"].items():
            out.append(f"- {name}: {failure} ({n})")
    out.append("")
    out.append("| run | effects per candidate | trials |")
    out.append("|---|---|---|")
    for name, patterns in summary["effects"].items():
        for pattern, n in patterns.items():
            out.append(f"| {name} | {pattern} | {n} |")
    out.append("")
    out.append("| point in the skills trial | what the model was shown or read | trials |")
    out.append("|---|---|---|")
    for point, seen in summary["skills"].items():
        for value, n in seen.items():
            out.append(f"| {point} | {value} | {n} |")
    out.append("")
    for name, fact in summary["facts"].items():
        out.append(f"- {name}: {json.dumps(fact)}")
    if summary["left"]:
        out.append(f"Servers left running after: {summary['left']}")
    return "\n".join(out)


def main() -> None:
    records = [json.loads(line) for path in sys.argv[1:] for line in Path(path).read_text().splitlines()]
    print(render(summarise(records)))


if __name__ == "__main__":
    main()
