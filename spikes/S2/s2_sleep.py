"""S2's laptop-sleep test, which the owner runs (workbench plan, "S2 AiiDA on the desktop"; owner, 2026-11-27).

It starts an isolated profile, its daemon and the FastAPI app (mode rpc), submits 5 jobs of 4 minutes, and asks you to
put the Mac to sleep for about 5 minutes. After you wake it, it waits for the jobs and records:
  - whether the Mac really slept: macOS's monotonic clock does not advance during sleep, so the gap between it and
    the wall clock is the time asleep;
  - each job's state and how the app was woken (by broadcast or by polling, every 10 s);
  - whether the broker kept its process and resumed rewriting its status file, and whether the daemon's workers live;
  - whether 3 jobs submitted after waking run and wake the app.
It then stops everything and prints a summary to paste back. Do not run it under `caffeinate`.
Usage: uv run python spikes/S2/s2_sleep.py
"""

import sys
import time
from pathlib import Path
from typing import Any

import s2_env as e
from s2_experiments import App, job_records

SLEEP_JOB_SECONDS = 240


def main() -> int:
    out = e.ROOT / "results" / f"sleep-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    home_before = e.home_snapshot()
    run = e.new_run("sleep")
    e.setup(run, poll_interval=10)
    e.daemon_start(run)
    app = None
    try:
        app = App(run, "rpc")
        broker_before = e.broker_pid(run)
        pks = app.post("/submit", {"kind": "add", "count": 5, "sleep": SLEEP_JOB_SECONDS})["pks"]
        print("\n=== S2 laptop-sleep test ===")
        print(f"5 jobs of {SLEEP_JOB_SECONDS // 60} minutes are running.")
        print("Now put the Mac to sleep for about 5 minutes: close the lid (with no external display attached),")
        print("or choose Apple menu > Sleep. Then wake it and log in. This script carries on by itself.\n", flush=True)
        offset = time.time() - time.monotonic()
        slept = 0.0
        deadline = time.monotonic() + 20 * 60
        while time.monotonic() < deadline:
            time.sleep(2)
            slept = max(slept, (time.time() - time.monotonic()) - offset)
            if slept > 60:
                print(f"Woke after about {slept / 60:.1f} minutes asleep. Waiting for the jobs...", flush=True)
                break
        woke_at = time.time()
        status = app.wait(pks, timeout=10 * 60)
        records = job_records(status, pks, experiment="sleep", phase="jobs running across the sleep")
        broker_dir = e.broker_dir(run)
        status_file = broker_dir / "broker.status" if broker_dir else None
        time.sleep(7)
        after = app.post("/submit", {"kind": "add", "count": 3, "sleep": 2})["pks"]
        after_status = app.wait(after, timeout=120)
        records += job_records(after_status, after, experiment="sleep", phase="jobs submitted after waking")
        daemon = e.verdi(run, "daemon", "status", check=False).stdout
        summary: dict[str, Any] = {
            "experiment": "sleep",
            "phase": "summary",
            "slept_minutes": round(slept / 60, 1),
            "broker_same_process": e.broker_pid(run) == broker_before,
            "broker_alive": e.alive(e.broker_pid(run)),
            "broker_status_rewritten_after_wake": bool(
                status_file and status_file.exists() and status_file.stat().st_mtime > woke_at
            ),
            "daemon_workers_listed": "Active workers" in daemon,
        }
        for entry in [*records, summary]:
            e.record(out, entry)
    finally:
        if app:
            app.stop()
        e.daemon_stop(run)
    time.sleep(1)
    e.record(out, {"experiment": "cleanup", "of": "sleep", "leftovers": e.leftovers(run)})
    e.record(out, {"experiment": "isolation", "home_aiida_unchanged": e.home_snapshot() == home_before})
    if not e.leftovers(run):
        e.remove_run(run)
    print("\n=== Paste everything below this line back to Claude ===")
    print(Path(out).read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
