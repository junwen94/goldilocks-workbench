"""S3, the submission key through aiida-quantumespresso (workbench plan, Phase 1): the experiments, each in its own
isolated profile.

Imports no AiiDA (see s3_env). Experiments:
  key        where a key can be stored at node creation (label; extras), what a lookup by label finds, and whether
             the work chain's children carry the label
  kills      the submit node (s3_inside.submit_node) is SIGKILLed inside aiida-core's submit(): 5 trials at each of
             4 points, 20 at random times, and 5 with a confirmed submission; after each, the submit node runs again
             in a new process and takes the job over or submits. Then every key is counted, and processes left in
             `created` without a task are revived by hand
  tasks      with one process slot, how a running, a queued and a finished job look; what aiida-core's
             get_process_tasks() does to the broker's files while the daemon runs; then a daemon restart
  roundtrip  goldilocks-core's bundles (s3_core.py) through the plugin's parser, a dry run and a PwBaseWorkChain on
             the stand-in, compared value by value with core's inputs
  handlers   PwBaseWorkChain's process handlers and the inputs that govern them
  caching    with caching on (D39) and a real pw.x, which failed or finished jobs are reused; skipped without pw.x
Every experiment writes JSON lines to --out, stops its daemon even when it fails, and records any process of its run
still alive afterwards.
Usage: uv run python spikes/S3/s3_experiments.py [--only kills,roundtrip] [--bundles DIR] [--out FILE] [--keep]
"""

import argparse
import json
import platform
import random
import shutil
import signal
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

import s3_env as e
from s3_inside import key_for

Writer = Callable[[dict[str, Any]], None]
DETERMINISTIC = ("before-submit", "node-stored", "checkpoint-saved", "task-sent")
TRIALS_PER_POINT = 5
RANDOM_TRIALS = 20
CONFIRMED_TRIALS = 5


class Context:
    def __init__(self, run: Path, out: Path, bundles: Path, write: Writer) -> None:
        self.run, self.out, self.bundles, self.write = run, out, bundles, write

    def inside(self, *args: str, check: bool = False, timeout: float = 1800) -> subprocess.CompletedProcess[str]:
        result = e.python(self.run, "s3_inside.py", *args, "--out", str(self.out), check=False, timeout=timeout)
        if check and result.returncode:
            self.write({"experiment": args[0], "error": result.stderr[-2000:], "returncode": result.returncode})
        return result


def experiment_key(c: Context) -> None:
    e.setup(c.run)
    e.daemon_start(c.run)
    try:
        c.inside("key", "--bundle", str(c.bundles / "si_scf"), check=True)
    finally:
        e.daemon_stop(c.run)


def submit_args(c: Context, key: str, phase: str, step: str, confirmed: bool = False) -> list[str]:
    args = ["submit", "--key", key, "--phase", phase, "--step", step, "--bundle", str(c.bundles / "si_scf")]
    return [*args, "--confirmed"] if confirmed else args


def rerun(c: Context, key: str) -> None:
    c.inside(*submit_args(c, key, "none", "rerun"), check=True)


def experiment_kills(c: Context, seed: int = 3) -> None:
    e.setup(c.run, poll_interval=10)
    e.daemon_start(c.run)
    keys: list[str] = []
    rng = random.Random(seed)
    try:
        for index in range(3):
            key = key_for(f"calibrate-{index}")
            keys.append(key)
            c.inside(*submit_args(c, key, "none", "calibrate"), check=True)
        rows = [json.loads(line) for line in c.out.read_text().splitlines()]
        seconds = [row["submit_seconds"] for row in rows if row.get("key") in keys and "submit_seconds" in row]
        typical = statistics.median(seconds)
        c.write({"experiment": "kills", "step": "calibration", "submit_seconds": seconds, "median": typical})

        def trial(key: str, phase: str, confirmed: bool = False) -> None:
            keys.append(key)
            result = c.inside(*submit_args(c, key, phase, "trial", confirmed))
            c.write(
                {
                    "experiment": "kills",
                    "step": "trial",
                    "key": key,
                    "phase": phase,
                    "confirmed": confirmed,
                    "killed": result.returncode == -signal.SIGKILL,
                    "returncode": result.returncode,
                    "stderr": result.stderr[-600:] if result.returncode not in (0, -signal.SIGKILL) else None,
                }
            )
            rerun(c, key)

        for phase in DETERMINISTIC:
            for index in range(TRIALS_PER_POINT):
                trial(key_for(f"{phase}-{index}"), phase)
        for index in range(CONFIRMED_TRIALS):
            trial(key_for(f"confirmed-task-sent-{index}"), "task-sent", confirmed=True)
        for index in range(RANDOM_TRIALS):
            key = key_for(f"random-{index}")
            keys.append(key)
            delay = rng.uniform(0, 1.5 * typical)
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(e.HERE / "s3_inside.py"),
                    *submit_args(c, key, "none", "trial"),
                    "--out",
                    str(c.out),
                ],
                env=e.environment(c.run),
                cwd=c.run,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            assert process.stdout is not None
            line = process.stdout.readline()
            time.sleep(delay)
            alive = process.poll() is None
            if alive:
                process.send_signal(signal.SIGKILL)
            process.wait(60)
            c.write(
                {
                    "experiment": "kills",
                    "step": "trial",
                    "key": key,
                    "phase": "random",
                    "delay": round(delay, 3),
                    "reached_submit": line.strip() == "SUBMITTING",
                    "killed": alive,
                }
            )
            rerun(c, key)
        keys_file = c.run / "keys.json"
        keys_file.write_text(json.dumps(keys))
        c.inside("audit", "--keys", str(keys_file), check=True)
    finally:
        e.daemon_stop(c.run)


def experiment_tasks(c: Context) -> None:
    e.setup(c.run, poll_interval=10, standin_sleep=20, slots=1)
    e.daemon_start(c.run)
    try:
        c.inside("tasks", "--bundle", str(c.bundles / "si_scf"), check=True)
        rows = [json.loads(line) for line in c.out.read_text().splitlines()]
        pks = next(row["pks"] for row in reversed(rows) if row.get("step") == "all ended")
        pks_file = c.run / "pks.json"
        pks_file.write_text(json.dumps(pks))
        e.daemon_stop(c.run)
        e.daemon_start(c.run)
        c.inside("tasks-after", "--keys", str(pks_file), check=True)
    finally:
        e.daemon_stop(c.run)


def experiment_roundtrip(c: Context) -> None:
    e.setup(c.run, poll_interval=5)
    e.daemon_start(c.run)
    try:
        c.inside("roundtrip", "--bundles", str(c.bundles), check=True)
    finally:
        e.daemon_stop(c.run)


def experiment_handlers(c: Context) -> None:
    e.setup(c.run)
    c.inside("handlers", check=True)


def experiment_caching(c: Context) -> None:
    pw = shutil.which("pw.x")
    if not pw:
        c.write({"experiment": "caching", "skipped": "no pw.x on PATH"})
        return
    e.setup(c.run, caching=True, real_pw=pw)
    c.inside("caching", "--bundles", str(c.bundles), check=True, timeout=3600)


EXPERIMENTS: dict[str, Callable[[Context], None]] = {
    "key": experiment_key,
    "kills": experiment_kills,
    "tasks": experiment_tasks,
    "roundtrip": experiment_roundtrip,
    "handlers": experiment_handlers,
    "caching": experiment_caching,
}


def environment_record(bundles: Path) -> dict[str, Any]:
    docker = (
        subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True, check=False
        )
        if sys.platform == "darwin" and shutil.which("docker")
        else None
    )
    cases = json.loads((bundles / "cases.json").read_text()) if (bundles / "cases.json").exists() else []
    return {
        "experiment": "environment",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "macos": platform.mac_ver()[0] or None,
        "python": platform.python_version(),
        **{
            name: version(name)
            for name in ("aiida-core", "aiida-quantumespresso", "aiida-pseudo", "qe-tools", "plumpy")
        },
        "pw.x": shutil.which("pw.x"),
        "docker": docker.stdout.strip() if docker and docker.returncode == 0 else None,
        "core_versions": sorted({case.get("core_version") for case in cases if case.get("core_version")}),
    }


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", default=",".join(EXPERIMENTS))
    parser.add_argument("--bundles", type=Path, default=e.ROOT / "bundles")
    parser.add_argument("--out", type=Path, default=e.ROOT / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    parser.add_argument("--keep", action="store_true", help="keep each run folder after its experiment")
    args = parser.parse_args(argv)
    chosen = [name.strip() for name in args.only.split(",") if name.strip()]
    unknown = [name for name in chosen if name not in EXPERIMENTS]
    if unknown:
        parser.error(f"unknown experiments: {', '.join(unknown)}")
    if not (args.bundles / "cases.json").exists():
        parser.error(f"no bundles in {args.bundles}; run s3_core.py first")
    args.out = args.out.resolve()
    # Every row is appended, and the kill trials' keys are the same every run, so a second run in one file would mix
    # with the first: the report would count its trials twice and the calibration would take both runs' median.
    if args.out.exists():
        parser.error(f"{args.out} exists; give each run its own --out")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def write(entry: dict[str, Any]) -> None:
        e.record(args.out, entry)

    home_before = e.home_snapshot()
    write(environment_record(args.bundles))
    for name in chosen:
        run = e.new_run(name)
        print(f"{name}: {run}", flush=True)
        start = time.monotonic()
        try:
            EXPERIMENTS[name](Context(run, args.out, args.bundles.resolve(), write))
        except Exception as caught:  # one experiment's failure must not stop the others
            write({"experiment": name, "error": f"{type(caught).__name__}: {caught}"})
        finally:
            e.daemon_stop(run)
            time.sleep(1)
            left = e.leftovers(run)
            write(
                {"experiment": "cleanup", "of": name, "seconds": round(time.monotonic() - start, 1), "leftovers": left}
            )
            if not args.keep and not left:
                e.remove_run(run)
    write({"experiment": "isolation", "home_aiida_unchanged": e.home_snapshot() == home_before})
    print(f"results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
