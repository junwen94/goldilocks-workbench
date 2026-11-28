"""S2, AiiDA on the desktop (workbench plan, Phase 1): the experiments, each in its own isolated profile.

Imports no AiiDA (see s2_env). Experiments:
  profile          verdi presto --use-zeromq in a fresh AIIDA_PATH; verdi status
  daemon           start, grow, shrink, restart and stop the daemon from Python (s2_inside daemon)
  wakes            the FastAPI app (s2_app) submits 20 jobs per round and is woken as each ends, in mode plain
                   and in mode rpc, 3 rounds each; poll interval 30 s, so a broadcast wake is told from a poll wake
  states           the app is woken for finished, excepted and killed processes, 3 of each, in both modes
  freeze           polling fail-safe: the broker is frozen (SIGSTOP) while 10 jobs end; poll interval 10 s
  restart          the broker is killed and respawned: what is stranded, and what recovers it
  caching          which jobs come from the cache (s2_inside caching), and aiida-quantumespresso's exit codes
  monitors         an observe-only monitor (s2_inside monitors)
  threads          nodes across threads, a LangGraph ToolNode, and writes under contention (s2_inside threads)
The laptop-sleep test is s2_sleep.py, which the owner runs.

Every experiment writes JSON lines to --out, stops its daemon and app even when it fails, and records any process of
its run still alive afterwards.
Usage: uv run python spikes/S2/s2_experiments.py [--only wakes,states] [--out FILE] [--keep]
"""

import argparse
import json
import platform
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

import s2_env as e

Writer = Callable[[dict[str, Any]], None]


class App:
    """s2_app.py as its own process, under the run's AIIDA_PATH."""

    def __init__(self, run: Path, mode: str) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.log = (run / f"app-{mode}-{self.port}.log").open("w")
        self.process = subprocess.Popen(
            [sys.executable, "s2_app.py", "--port", str(self.port), "--mode", mode],
            env=e.environment(run),
            cwd=e.HERE,
            stdout=self.log,
            stderr=self.log,
        )
        deadline = time.monotonic() + 90
        while True:
            try:
                self.get("/health")
                return
            except OSError:
                if self.process.poll() is not None or time.monotonic() > deadline:
                    self.stop()
                    raise RuntimeError(f"the app did not start; see {self.log.name}") from None
                time.sleep(0.5)

    def request(self, path: str, body: dict[str, Any] | None = None, timeout: float = 120) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def get(self, path: str) -> Any:
        return self.request(path)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self.request(path, body)

    def wait(self, pks: Sequence[int], timeout: float) -> dict[str, Any]:
        """Polls the app's status until every job has woken it, or `timeout` seconds pass."""
        deadline = time.monotonic() + timeout
        while True:
            status: dict[str, Any] = self.get("/status")
            jobs = [status["jobs"].get(str(pk), {}) for pk in pks]
            if all(job.get("wake") for job in jobs) or time.monotonic() > deadline:
                return status
            time.sleep(1)

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(15)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.log.close()


def job_records(status: dict[str, Any], pks: Sequence[int], **labels: Any) -> list[dict[str, Any]]:
    """One record per job: its state, and the wake's delay after the node's last change and after the broadcast."""
    records = []
    for pk in pks:
        job = status["jobs"].get(str(pk), {})
        wake, mtime, broadcast = job.get("wake"), job.get("mtime"), job.get("broadcast")
        records.append(
            {
                **labels,
                "pk": pk,
                "state": job.get("state"),
                "exit_status": job.get("exit_status"),
                "woken": wake is not None,
                "wake_after_change": round(wake - mtime, 2) if wake and mtime else None,
                "broadcast_seen": broadcast is not None,
                "wake_after_broadcast": round(wake - broadcast, 2) if wake and broadcast else None,
            }
        )
    return records


def experiment_profile(run: Path, write: Writer) -> None:
    setup = e.setup(run, poll_interval=30)
    status = e.verdi(run, "status", check=False)
    write(
        {
            "experiment": "profile",
            **setup,
            "verdi_status": status.stdout.strip().splitlines(),
            "broker_dir_exists_before_daemon": e.broker_dir(run) is not None,
        }
    )


def experiment_inside(
    name: str, daemon: bool, caching: bool = False, poll: float = 10
) -> Callable[[Path, Writer], None]:
    def run_it(run: Path, write: Writer) -> None:
        e.setup(run, poll_interval=poll, caching=caching)
        out = run / f"{name}.jsonl"
        try:
            if daemon:
                e.daemon_start(run)
            result = e.python(run, "s2_inside.py", name, "--out", str(out), check=False)
            if result.returncode:
                write({"experiment": name, "error": result.stderr[-1500:]})
        finally:
            e.daemon_stop(run)
        for line in out.read_text().splitlines() if out.exists() else []:
            write(json.loads(line))

    return run_it


def experiment_wakes(run: Path, write: Writer, rounds: int = 3) -> None:
    e.setup(run, poll_interval=30)
    e.daemon_start(run)
    try:
        for mode in ("plain", "rpc"):
            app = App(run, mode)
            try:
                for index in range(rounds):
                    pks = app.post("/submit", {"kind": "add", "count": 20, "sleep": 3})["pks"]
                    status = app.wait(pks, timeout=120)
                    for record in job_records(status, pks, experiment="wakes", mode=mode, round=index):
                        write(record)
            finally:
                app.stop()
    finally:
        e.daemon_stop(run)


def experiment_states(run: Path, write: Writer) -> None:
    e.setup(run, poll_interval=30)
    e.daemon_start(run)
    try:
        for mode in ("plain", "rpc"):
            app = App(run, mode)
            try:
                finished = app.post("/submit", {"kind": "add", "count": 3, "sleep": 2})["pks"]
                excepted = app.post("/submit", {"kind": "boom", "count": 3})["pks"]
                killed = app.post("/submit", {"kind": "add", "count": 3, "sleep": 60})["pks"]
                time.sleep(8)
                app.post("/kill", {"pks": killed})
                status = app.wait([*finished, *excepted, *killed], timeout=120)
                for kind, pks in (("finished", finished), ("excepted", excepted), ("killed", killed)):
                    for record in job_records(status, pks, experiment="states", mode=mode, expected=kind):
                        write(record)
            finally:
                app.stop()
    finally:
        e.daemon_stop(run)


def experiment_freeze(run: Path, write: Writer) -> None:
    """Jobs end while the broker is frozen: only backup polling (every 10 s) can wake the app."""
    e.setup(run, poll_interval=10)
    e.daemon_start(run)
    app = App(run, "rpc")
    frozen = None
    try:
        pks = app.post("/submit", {"kind": "add", "count": 10, "sleep": 12})["pks"]
        time.sleep(4)
        frozen = e.signal_broker(run, signal.SIGSTOP)
        status = app.wait(pks, timeout=90)
        for record in job_records(status, pks, experiment="freeze", phase="broker frozen"):
            write(record)
        e.signal_broker(run, signal.SIGCONT)
        frozen = None
        time.sleep(5)
        after = app.post("/submit", {"kind": "add", "count": 5, "sleep": 2})["pks"]
        status = app.wait(after, timeout=90)
        for record in job_records(status, after, experiment="freeze", phase="broker resumed"):
            write(record)
    finally:
        if frozen:
            e.signal_broker(run, signal.SIGCONT)
        app.stop()
        e.daemon_stop(run)


def experiment_restart(run: Path, write: Writer) -> None:
    """The broker is killed; circus starts a new one on a new socket. Which parts are stranded, and what helps."""
    e.setup(run, poll_interval=10)
    e.daemon_start(run)
    apps: list[App] = []
    try:
        apps.append(App(run, "rpc"))
        before = e.broker_pid(run)
        e.signal_broker(run, signal.SIGKILL)
        start = time.monotonic()
        while e.broker_pid(run) in (None, before) or not e.alive(e.broker_pid(run)):
            if time.monotonic() - start > 30:
                break
            time.sleep(0.5)
        write(
            {
                "experiment": "restart",
                "step": "broker killed",
                "old_pid": before,
                "new_pid": e.broker_pid(run),
                "respawn_seconds": round(time.monotonic() - start, 1),
            }
        )
        all_pks: list[int] = []

        def submit_and_wait(step: str, app: App) -> None:
            pks = app.post("/submit", {"kind": "add", "count": 5, "sleep": 2})["pks"]
            all_pks.extend(pks)
            status = app.wait(all_pks, timeout=40)
            states = [status["jobs"][str(pk)]["state"] for pk in all_pks]
            write(
                {
                    "experiment": "restart",
                    "step": step,
                    "submitted": pks,
                    "finished_of_all_so_far": f"{states.count('finished')}/{len(all_pks)}",
                    "states": states,
                    "woken": sum(bool(status["jobs"][str(p)]["wake"]) for p in all_pks),
                    "broker_pid": e.broker_pid(run),
                    "broker_queue": e.broker_queue(run),
                }
            )

        submit_and_wait("submitted from the same app", apps[-1])
        apps[-1].stop()
        apps.append(App(run, "rpc"))
        apps[-1].post("/adopt", {"pks": all_pks})
        submit_and_wait("submitted from a restarted app", apps[-1])
        write(
            {
                "experiment": "restart",
                "step": "before verdi daemon restart",
                "broker_pid": e.broker_pid(run),
                "broker_queue": e.broker_queue(run),
            }
        )
        e.verdi(run, "daemon", "restart", check=False)
        time.sleep(5)
        write(
            {
                "experiment": "restart",
                "step": "after verdi daemon restart",
                "broker_pid": e.broker_pid(run),
                "broker_queue": e.broker_queue(run),
            }
        )
        submit_and_wait("after verdi daemon restart (the whole daemon, broker included)", apps[-1])
        e.daemon_stop(run)
        e.daemon_start(run)
        apps[-1].stop()
        apps.append(App(run, "rpc"))
        apps[-1].post("/adopt", {"pks": all_pks})
        submit_and_wait("after daemon stop and start, and a restarted app", apps[-1])
    finally:
        for app in apps:
            app.stop()
        e.daemon_stop(run)


EXPERIMENTS: dict[str, Callable[[Path, Writer], None]] = {
    "profile": experiment_profile,
    "daemon": experiment_inside("daemon", daemon=False),
    "wakes": experiment_wakes,
    "states": experiment_states,
    "freeze": experiment_freeze,
    "restart": experiment_restart,
    "caching": experiment_inside("caching", daemon=False, caching=True),
    "qe_exit_codes": experiment_inside("qe_exit_codes", daemon=False),
    "monitors": experiment_inside("monitors", daemon=True),
    "threads": experiment_inside("threads", daemon=True),
}


def environment_record() -> dict[str, Any]:
    docker = (
        subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True, check=False
        )
        if sys.platform == "darwin"
        else None
    )
    return {
        "experiment": "environment",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "macos": platform.mac_ver()[0] or None,
        "python": platform.python_version(),
        "aiida_core": version("aiida-core"),
        "aiida_quantumespresso": version("aiida-quantumespresso"),
        "plumpy": version("plumpy"),
        "kiwipy": version("kiwipy"),
        "docker": docker.stdout.strip() if docker and docker.returncode == 0 else None,
    }


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", default=",".join(EXPERIMENTS))
    parser.add_argument("--out", type=Path, default=e.ROOT / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    parser.add_argument("--keep", action="store_true", help="keep each run folder after its experiment")
    args = parser.parse_args(argv)
    chosen = [name.strip() for name in args.only.split(",") if name.strip()]
    unknown = [name for name in chosen if name not in EXPERIMENTS]
    if unknown:
        parser.error(f"unknown experiments: {', '.join(unknown)}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def write(entry: dict[str, Any]) -> None:
        e.record(args.out, entry)

    home_before = e.home_snapshot()
    write(environment_record())
    for name in chosen:
        run = e.new_run(name)
        print(f"{name}: {run}", flush=True)
        start = time.monotonic()
        try:
            EXPERIMENTS[name](run, write)
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
