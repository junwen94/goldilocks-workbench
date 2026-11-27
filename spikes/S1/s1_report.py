"""Tables for S1's written result, from a run folder made by s1_mechanics.py.

Each rate is the share of calls that passed. Its 95% interval comes from resampling cases (each case's runs
averaged first), so it reflects how many different cases were tried, not only how many calls.
Usage: uv run python spikes/S1/s1_report.py spikes/S1/runs/<name>
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import s1_common as c

DESCRIPTIVE = {"options", "tools_format"}  # no pass or fail: outcomes are counted instead


def load(folder: Path) -> list[dict[str, Any]]:
    with (folder / "calls.jsonl").open() as lines:
        return [json.loads(line) for line in lines if line.strip()]


def rate_rows(calls: Iterable[Mapping[str, Any]]) -> list[list[str]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for call in calls:
        if call["experiment"] not in DESCRIPTIVE and call["passed"] is not None:
            groups[(call["experiment"], call["variant"], call["client"])].append(call)
    rows = []
    for (experiment, variant, client), group in sorted(groups.items()):
        by_case: dict[str, list[bool]] = defaultdict(list)
        for call in group:
            by_case[call["case"]].append(bool(call["passed"]))
        mean, low, high = c.bootstrap([sum(v) / len(v) for v in by_case.values()])
        valid = [call["detail"]["valid"] for call in group if "valid" in call["detail"]]
        tokens = [call["prompt_tokens"] for call in group if call.get("prompt_tokens")]
        rows.append(
            [
                experiment,
                variant or "-",
                client,
                str(len(group)),
                str(len(by_case)),
                f"{mean:.0%}",
                f"{low:.0%} to {high:.0%}",
                f"{sum(valid) / len(valid):.0%}" if valid else "-",
                f"{statistics.median(call['seconds'] for call in group):.1f}",
                f"{statistics.median(tokens):.0f}" if tokens else "-",
            ]
        )
    return rows


def outcome_rows(calls: Iterable[Mapping[str, Any]]) -> list[list[str]]:
    groups: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for call in calls:
        groups[
            (
                call["experiment"],
                call["case"] if call["experiment"] == "options" else call["variant"],
                call["client"],
                "",
            )
        ][call["outcome"]] += 1
    return [
        [e, v, cl, ", ".join(f"{k} {n}" for k, n in counts.most_common())]
        for (e, v, cl, _), counts in sorted(groups.items())
    ]


def problem_rows(calls: Iterable[Mapping[str, Any]]) -> list[list[str]]:
    """Missing, extra and mistyped arguments over every tool call the model made, by experiment and client."""
    totals: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for call in calls:
        for problems in call["detail"].get("problems", []):
            counter = totals[(call["experiment"], call["client"])]
            counter["tool calls"] += 1
            counter["clean" if not problems else "with problems"] += 1
            for problem in problems:
                counter[problem.split(":")[0]] += 1
    return [[e, cl, ", ".join(f"{k} {n}" for k, n in counts.items())] for (e, cl), counts in sorted(totals.items())]


def table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(row) + " |" for row in rows])


def report(folder: Path) -> str:
    calls = load(folder)
    env = json.loads((folder / "environment.json").read_text())
    parts = [
        "## Environment",
        "```",
        json.dumps(env, indent=2),
        "```",
        "## Rates",
        table(
            [
                "experiment",
                "variant",
                "client",
                "calls",
                "cases",
                "pass",
                "95% interval",
                "valid",
                "median s",
                "median prompt tokens",
            ],
            rate_rows(calls),
        ),
        "## Outcomes",
        table(
            ["experiment", "case or variant", "client", "outcomes"],
            outcome_rows(x for x in calls if x["experiment"] in DESCRIPTIVE | {"parallel"}),
        ),
        "## Tool-call arguments",
        table(["experiment", "client", "counts"], problem_rows(calls)),
    ]
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    sys.stdout.write(report(Path(sys.argv[1])))
