"""Offline tests of S2's harness: the summaries and job records (AGENTS.md rule 10), the isolated environment, the
monitor entry point, the broker-queue and leftover checks, and that no script touches the user's ~/.aiida.
No AiiDA profile, daemon or network."""

import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import s2_env as e
import s2_report as r
from s2_experiments import job_records

HERE = Path(__file__).resolve().parent


def job(wake: float | None, mtime: float, broadcast: float | None, state: str = "finished") -> dict[str, Any]:
    return {"state": state, "exit_status": 0, "mtime": mtime, "wake": wake, "broadcast": broadcast}


def test_job_records_measure_wakes_from_the_change_and_the_broadcast() -> None:
    status = {
        "jobs": {"1": job(105.0, 100.0, None), "2": job(100.05, 100.0, 100.0), "3": job(None, 100.0, None, "created")}
    }
    records = job_records(status, [1, 2, 3], experiment="wakes", mode="plain")
    assert [x["wake_after_change"] for x in records] == [5.0, 0.05, None]
    assert [x["broadcast_seen"] for x in records] == [False, True, False]
    assert records[1]["wake_after_broadcast"] == 0.05
    assert records[2]["woken"] is False and records[2]["state"] == "created"
    assert all(x["mode"] == "plain" and x["experiment"] == "wakes" for x in records)


def wake_row(delay: float | None, broadcast: bool, mode: str = "rpc", woken: bool = True) -> dict[str, Any]:
    return {
        "experiment": "wakes",
        "origin": "run",
        "mode": mode,
        "pk": 1,
        "state": "finished",
        "woken": woken,
        "wake_after_change": delay,
        "broadcast_seen": broadcast,
    }


def test_wake_summary_counts_by_group() -> None:
    rows = [
        wake_row(0.1, True),
        wake_row(4.9, True),
        wake_row(6.0, False),
        wake_row(None, False, woken=False),
        wake_row(23.0, False, mode="plain"),
    ]
    summary = {x["mode"]: x for x in r.wake_summary(rows)}
    assert summary["rpc"]["jobs"] == 4
    assert summary["rpc"]["woken"] == 3
    assert summary["rpc"]["broadcast_seen"] == 2
    assert summary["rpc"]["within_5s"] == 2
    assert summary["rpc"]["max_s"] == 6.0
    assert summary["plain"]["within_5s"] == 0 and summary["plain"]["median_s"] == 23.0
    assert summary["rpc"]["exit_statuses"] == {"None": 4}


def test_wake_summary_ignores_rows_without_a_job() -> None:
    assert r.wake_summary([{"experiment": "sleep", "origin": "x", "phase": "summary"}]) == []


def test_caching_summary_names_the_case_a_job_came_from() -> None:
    rows: list[dict[str, Any]] = [
        {
            "experiment": "caching",
            "origin": "a",
            "case": "first",
            "uuid": "u1",
            "exit_status": 0,
            "from_cache": False,
            "source": None,
        },
        {
            "experiment": "caching",
            "origin": "a",
            "case": "second",
            "uuid": "u2",
            "exit_status": 0,
            "from_cache": True,
            "source": "u1",
        },
        {"experiment": "caching", "origin": "a", "case": "reference", "first_uuid": "u1"},
    ]
    summary = r.caching_summary(rows)
    assert [(x["case"], x["from_cache"], x["cache_source"]) for x in summary] == [
        ("first", False, None),
        ("second", True, "first"),
    ]


def test_qe_summary_checks_the_below_400_rule() -> None:
    good = {
        "experiment": "qe_exit_codes",
        "origin": "a",
        "calculation": "quantumespresso.pw",
        "codes": [
            {"status": 305, "label": "A", "invalidates_cache": True},
            {"status": 410, "label": "B", "invalidates_cache": False},
        ],
    }
    bad = {
        **good,
        "calculation": "quantumespresso.ph",
        "codes": [{"status": 500, "label": "C", "invalidates_cache": True}],
    }
    summary = r.qe_summary([good, bad])
    assert summary[0]["invalidating"] == [305] and summary[0]["below_400_rule_holds"] is True
    assert summary[1]["below_400_rule_holds"] is False


def test_report_renders_every_section(tmp_path: Path) -> None:
    results = tmp_path / "macos.jsonl"
    results.write_text(
        "\n".join(
            json.dumps(x)
            for x in [
                {"experiment": "environment", "platform": "test"},
                wake_row(0.1, True),
                {"experiment": "isolation", "home_aiida_unchanged": True},
            ]
        )
    )
    text = r.report([results])
    for title in ("## Environment", "## Wakes", "## Caching", "## Sleep", "## Cleanup and isolation", "## Errors"):
        assert title in text
    assert "| macos | wakes | rpc |" in text


def test_the_environment_isolates_aiida_in_the_run(tmp_path: Path) -> None:
    env = e.environment(tmp_path)
    assert env["AIIDA_PATH"] == str(tmp_path)
    assert env["PYTHONPATH"].split(os.pathsep)[:2] == [str(HERE), str(tmp_path / "entry_points")]
    assert "AIIDA_PROFILE" not in env
    assert e.config_dir(tmp_path) == tmp_path / ".aiida"


def test_the_monitor_entry_point_is_found_without_installing(tmp_path: Path) -> None:
    dist = e.write_monitor_entry_point(tmp_path)
    found = {
        point.name: point.value
        for d in importlib.metadata.distributions(path=[str(dist.parent)])
        for point in d.entry_points
        if point.group == "aiida.calculations.monitors"
    }
    assert found == {"s2.observe": "s2_processes:observe", "s2.observe_unversioned": "s2_unversioned:observe"}


def test_broker_queue_and_leftovers_read_the_run_folder(tmp_path: Path) -> None:
    broker = tmp_path / ".aiida" / "broker" / f"abc-{e.PROFILE}"
    (broker / "storage" / "tasks" / "pending").mkdir(parents=True)
    (broker / "storage" / "tasks" / "pending" / "1_x.json").write_text("{}")
    assert e.broker_queue(tmp_path) == {"pending": 1, "processing": 0}
    (broker / "broker.pid").write_text("aiida-zeromq-broker 999999999")
    assert e.broker_pid(tmp_path) == 999999999
    assert e.leftovers(tmp_path) == []
    (broker / "broker.pid").write_text(f"aiida-zeromq-broker {os.getpid()}")
    assert e.leftovers(tmp_path) == [f"broker.pid: {os.getpid()}"]


def test_home_snapshot_reads_names_and_times_only(tmp_path: Path) -> None:
    home = tmp_path / ".aiida"
    (home / "profiles").mkdir(parents=True)
    (home / "config.json").write_text("secret contents")
    snapshot = e.home_snapshot(home)
    assert any(line.endswith("config.json") for line in snapshot)
    assert not any("secret" in line for line in snapshot)
    assert e.home_snapshot(tmp_path / "missing") == []


@pytest.mark.parametrize("path", sorted(HERE.glob("*.py")), ids=lambda p: p.name)
def test_no_script_names_the_users_aiida_folder_except_the_snapshot(path: Path) -> None:
    text = path.read_text()
    if path.name in ("s2_env.py", "test_s2.py"):
        return
    assert '".aiida"' not in text and "~/.aiida" not in text.replace("~/.aiida set-up", "")
