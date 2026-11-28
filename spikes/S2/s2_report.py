"""Tables for S2's written result, from the JSON lines of s2_experiments.py, s2_sleep.py and the container run.

Imports no AiiDA. A wake counts as "within 5 s" when it came no more than 5 s after the node's last change; a
broadcast wake is one where the app's own broadcast subscriber saw the terminal-state broadcast.
Usage: uv run python spikes/S2/s2_report.py RESULTS.jsonl [MORE.jsonl ...]
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

WAKE_EXPERIMENTS = ("wakes", "states", "freeze", "sleep")
WITHIN = 5.0


def load(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        rows += [{**json.loads(line), "origin": path.stem} for line in path.read_text().splitlines() if line.strip()]
    return rows


def wake_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per source, experiment, mode, expected state and phase: how many jobs woke the app, how, and how fast."""
    groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("experiment") in WAKE_EXPERIMENTS and "pk" in row:
            key = (row["origin"], row["experiment"], row.get("mode", ""), row.get("expected", ""), row.get("phase", ""))
            groups[key].append(row)
    summary = []
    for (origin, experiment, mode, expected, phase), group in sorted(groups.items()):
        delays = [row["wake_after_change"] for row in group if row.get("wake_after_change") is not None]
        summary.append(
            {
                "origin": origin,
                "experiment": experiment,
                "mode": mode,
                "expected": expected,
                "phase": phase,
                "jobs": len(group),
                "woken": sum(bool(row.get("woken")) for row in group),
                "broadcast_seen": sum(bool(row.get("broadcast_seen")) for row in group),
                "within_5s": sum(delay <= WITHIN for delay in delays),
                "median_s": round(statistics.median(delays), 2) if delays else None,
                "max_s": round(max(delays), 2) if delays else None,
                "states": dict(Counter(str(row.get("state")) for row in group)),
                "exit_statuses": dict(Counter(str(row.get("exit_status")) for row in group)),
            }
        )
    return summary


def caching_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per run and case: the exit status, whether the job came from the cache, and from which earlier case."""
    by_origin: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("experiment") == "caching" and row.get("case") != "reference" and "uuid" in row:
            by_origin[row["origin"]].append(row)
    summary = []
    for origin, cases in sorted(by_origin.items()):
        names = {row["uuid"]: row["case"] for row in cases}
        for row in cases:
            summary.append(
                {
                    "origin": origin,
                    "case": row["case"],
                    "exit_status": row["exit_status"],
                    "from_cache": row["from_cache"],
                    "cache_source": names.get(row.get("source") or ""),
                }
            )
    return summary


def qe_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per calculation: its exit codes that invalidate the cache, and whether "status < 400" predicts every one."""
    summary = []
    for row in rows:
        if row.get("experiment") == "qe_exit_codes":
            codes = row["codes"]
            summary.append(
                {
                    "origin": row["origin"],
                    "calculation": row["calculation"],
                    "codes": len(codes),
                    "invalidating": sorted({code["status"] for code in codes if code["invalidates_cache"]}),
                    "below_400_rule_holds": all(code["invalidates_cache"] == (code["status"] < 400) for code in codes),
                }
            )
    return summary


def picked(rows: Iterable[Mapping[str, Any]], experiment: str, drop: Sequence[str] = ()) -> list[dict[str, Any]]:
    return [{k: v for k, v in row.items() if k not in drop} for row in rows if row.get("experiment") == experiment]


def table(entries: Sequence[Mapping[str, Any]]) -> str:
    if not entries:
        return "(none)"
    header = list(dict.fromkeys(name for entry in entries for name in entry))
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(entry.get(name, "")) for name in header) + " |" for entry in entries]
    return "\n".join(lines)


def report(paths: Sequence[Path]) -> str:
    rows = load(paths)
    sections = [
        ("Environment", picked(rows, "environment")),
        ("Wakes", wake_summary(rows)),
        ("Daemon control", picked(rows, "daemon")),
        ("Broker restart", picked(rows, "restart", drop=("submitted", "states"))),
        ("Caching", caching_summary(rows)),
        ("aiida-quantumespresso exit codes", qe_summary(rows)),
        ("Monitors", picked(rows, "monitors", drop=("hash_with_monitor", "hash_without"))),
        ("Threads", picked(rows, "threads", drop=("jobs",))),
        ("Sleep", [row for row in picked(rows, "sleep") if row.get("phase") == "summary"]),
        ("Cleanup and isolation", picked(rows, "cleanup") + picked(rows, "isolation")),
        ("Errors", [row for row in rows if "error" in row and row.get("experiment") not in ("threads", "daemon")]),
    ]
    return "\n\n".join(f"## {title}\n\n{table(entries)}" for title, entries in sections) + "\n"


if __name__ == "__main__":
    sys.stdout.write(report([Path(arg) for arg in sys.argv[1:]]))
