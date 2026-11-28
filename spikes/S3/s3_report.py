"""Tables for S3's written result, from the JSON lines of s3_experiments.py (macOS and the container).

Imports no AiiDA. A kill trial is the driver's row (it has `killed`); the submit node that ran after it is the `rerun`
row with the same key.
Usage: uv run python spikes/S3/s3_report.py RESULTS.jsonl [MORE.jsonl ...]
"""

import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def load(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        rows += [{**json.loads(line), "origin": path.stem} for line in path.read_text().splitlines() if line.strip()]
    return rows


def kill_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per source and kill point: the trials, how many were killed, and what the submit node did when it ran again."""
    rows = list(rows)
    reruns = {(row["origin"], row["key"]): row for row in rows if row.get("step") == "rerun"}
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("experiment") == "kills" and row.get("step") == "trial" and "killed" in row:
            point = row["phase"] + (" (confirmed)" if row.get("confirmed") else "")
            groups[(row["origin"], point)].append(row)
    summary = []
    for (origin, point), trials in groups.items():
        after = [reruns.get((origin, trial["key"]), {}) for trial in trials]
        not_started = [row for row in after if str(row.get("action", "")).startswith("needs check")]
        summary.append(
            {
                "origin": origin,
                "kill point": point,
                "trials": len(trials),
                "killed": sum(bool(trial["killed"]) for trial in trials),
                "rerun actions": dict(Counter(str(row.get("action")) for row in after)),
                "states found": dict(Counter(str(row.get("state")) for row in after if row.get("found"))),
                "not started, with checkpoint": sum(bool(row.get("checkpoint")) for row in not_started),
                "not started, task in broker": sum(
                    bool(row.get("in_broker_pending") or row.get("in_broker_processing")) for row in not_started
                ),
            }
        )
    return summary


def revive_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per source, state and checkpoint before the revive: how the revived processes ended."""
    groups: dict[tuple[str, str, bool], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("experiment") == "kills" and row.get("step") == "revive":
            groups[(row["origin"], str(row["state_before"]), bool(row["checkpoint_before"]))].append(row)
    return [
        {
            "origin": origin,
            "state before": state,
            "checkpoint before": checkpoint,
            "revived": len(group),
            "ended": dict(Counter(f"{row['state']} {row['exit_status']}" for row in group)),
            "errors": sum(row.get("error") is not None for row in group),
        }
        for (origin, state, checkpoint), group in sorted(groups.items())
    ]


def roundtrip_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for row in rows:
        if row.get("experiment") != "roundtrip" or "file" not in row:
            continue
        chain = row.get("work_chain") or {}
        differences = chain.get("differences") or {}
        summary.append(
            {
                "origin": row["origin"],
                "case": row["case"],
                "file": row["file"],
                "executable": row.get("executable"),
                "route": row.get("route"),
                "problems beyond the plumbing": "; ".join(row.get("problems") or [])
                or ("none" if "problems" in row else ""),
                "pseudopotentials identical": all((row.get("pseudos_identical") or {"": False}).values())
                if "pseudos_identical" in row
                else "",
                "work chain's input = dry run's": chain.get("first_input_identical_to_dry_run", ""),
                "work chain added": ", ".join(
                    f"{k} = {v}" for k, v in (differences.get("only_generated") or {}).items()
                ),
                "error": (row.get("error") or "").splitlines()[0][:120] if row.get("error") else "",
            }
        )
    return summary


def caching_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per case: the exit status, whether it came from the cache and from which earlier case; a work chain's
    calculations one per line."""
    rows = [row for row in rows if row.get("experiment") == "caching"]
    names: dict[str, str] = {}
    for row in rows:
        for entry in [row, *row.get("children", [])]:
            if entry.get("uuid"):
                names.setdefault(entry["uuid"], entry["case"] if entry is row else f"{row['case']}, its calculation")
    summary = []
    for row in rows:
        if "skipped" in row:
            summary.append({"origin": row["origin"], "case": f"skipped: {row['skipped']}"})
            continue
        if not row.get("work_chain"):
            summary.append(
                {
                    "origin": row["origin"],
                    "case": row["case"],
                    "exit": row["exit_status"],
                    "from cache": row["from_cache"],
                    "source": names.get(row.get("source") or "", ""),
                    "pw.x": row.get("creator", ""),
                }
            )
            continue
        summary.append({"origin": row["origin"], "case": row["case"], "exit": row["exit_status"]})
        for index, child in enumerate(row.get("children", []), start=1):
            summary.append(
                {
                    "origin": row["origin"],
                    "case": f"  calculation {index}",
                    "exit": child["exit_status"],
                    "from cache": child["from_cache"],
                    "source": names.get(child.get("source") or "", ""),
                    "mixing_beta": child.get("mixing_beta"),
                    "restart_mode": child.get("restart_mode"),
                    "disable_cache": child.get("disable_cache"),
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
    kills = [row for row in rows if row.get("experiment") == "kills"]
    sections = [
        ("Environment", picked(rows, "environment")),
        ("Key", picked(rows, "key")),
        ("Kill trials", kill_summary(rows)),
        ("Kill trials: audit", [row for row in kills if row.get("step") in ("calibration", "audit totals")]),
        ("Kill trials: revived", revive_summary(rows)),
        ("Tasks", picked(rows, "tasks", drop=("daemon_log",))),
        ("Round trip", roundtrip_summary(rows)),
        ("Handlers", picked(rows, "handlers", drop=("doc",))),
        ("Caching", caching_summary(rows)),
        ("Cleanup and isolation", picked(rows, "cleanup") + picked(rows, "isolation")),
        ("Errors", [row for row in rows if row.get("error") and row.get("experiment") not in ("key", "roundtrip")]),
    ]
    return "\n\n".join(f"## {title}\n\n{table(entries)}" for title, entries in sections) + "\n"


if __name__ == "__main__":
    sys.stdout.write(report([Path(arg) for arg in sys.argv[1:]]))
