"""S2's isolated AiiDA environments (workbench plan, "S2 AiiDA on the desktop").

Imports no AiiDA: AiiDA fixes its configuration folder when it is first imported, so everything that imports it runs
as a subprocess with AIIDA_PATH set to a fresh run folder under ~/.cache/goldilocks-spikes/s2/. That keeps S2's
profile, daemon and ZeroMQ broker apart from any AiiDA set-up the user already has, and outside cloud-synced folders,
which SQLite does not cope with. Each run's profile is called "s2".
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("GOLDILOCKS_SPIKES_CACHE", Path.home() / ".cache" / "goldilocks-spikes")) / "s2"
PROFILE = "s2"
# Codes on presto's localhost: bash runs core.arithmetic.add's script; the versioned ones differ only in
# prepend_text, as one Code per code version would (workbench plan, D39); "silent" writes no output.
CODES = {
    "bash": ("/bin/bash", ""),
    "bash-v1": ("/bin/bash", "# code version 1"),
    "bash-v2": ("/bin/bash", "# code version 2"),
    "silent": ("/usr/bin/true", ""),
}
MONITOR_DIST = "s2_monitors-0.0.0.dist-info"


def new_run(name: str, root: Path = ROOT) -> Path:
    folder = root / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
    folder.mkdir(parents=True)
    return folder


def config_dir(run: Path) -> Path:
    return run / ".aiida"


def environment(run: Path) -> dict[str, str]:
    """The environment of every AiiDA subprocess of a run: its own AIIDA_PATH, and S2's modules and the run's monitor
    entry point on PYTHONPATH (daemon workers inherit the starting process's path)."""
    env = dict(os.environ)
    env["AIIDA_PATH"] = str(run)
    paths = [str(HERE), str(run / "entry_points")]
    env["PYTHONPATH"] = os.pathsep.join([*paths, *filter(None, [env.get("PYTHONPATH", "")])])
    env.pop("AIIDA_PROFILE", None)
    return env


def verdi(run: Path, *args: str, check: bool = True, timeout: float = 300) -> subprocess.CompletedProcess[str]:
    command = ["verdi", *args] if args[:1] == ("presto",) else ["verdi", "-p", PROFILE, *args]
    return subprocess.run(command, env=environment(run), capture_output=True, text=True, check=check, timeout=timeout)


def python(run: Path, *args: str, check: bool = True, timeout: float = 900) -> subprocess.CompletedProcess[str]:
    """Runs a Python script of this folder under the run's AIIDA_PATH."""
    return subprocess.run(
        [sys.executable, *args],
        env=environment(run),
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
        cwd=HERE,
    )


def write_monitor_entry_point(run: Path) -> Path:
    """Registers s2_processes.observe as the monitor `s2.observe` without installing anything: a dist-info folder on
    the run's PYTHONPATH is enough for importlib.metadata to find the entry point."""
    dist = run / "entry_points" / MONITOR_DIST
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: s2-monitors\nVersion: 0.0.0\n")
    (dist / "entry_points.txt").write_text(
        "[aiida.calculations.monitors]\ns2.observe = s2_processes:observe\n"
        "s2.observe_unversioned = s2_unversioned:observe\n"
    )
    return dist


def setup(run: Path, poll_interval: float = 30, caching: bool = False) -> dict[str, Any]:
    """A profile like goldilocks-agent's: SQLite storage, the ZeroMQ broker, presto's localhost, and the codes."""
    write_monitor_entry_point(run)
    presto = verdi(run, "presto", "--use-zeromq", "--profile-name", PROFILE, "--non-interactive")
    verdi(run, "config", "set", "runner.poll.interval", str(poll_interval))
    if caching:
        verdi(run, "config", "set", "caching.enabled_for", "aiida.calculations:core.arithmetic.add")
    for label, (executable, prepend) in CODES.items():
        args = [
            "code",
            "create",
            "core.code.installed",
            "--non-interactive",
            "--label",
            label,
            "--computer",
            "localhost",
            "--filepath-executable",
            executable,
            "--default-calc-job-plugin",
            "core.arithmetic.add",
        ]
        if prepend:
            args += ["--prepend-text", prepend]
        verdi(run, *args)
    return {"presto": presto.stdout.strip().splitlines()[-3:], "poll_interval": poll_interval, "caching": caching}


def daemon_start(run: Path, workers: int = 1) -> None:
    verdi(run, "daemon", "start", str(workers))
    wait_broker(run)


def wait_broker(run: Path, timeout: float = 20) -> float:
    """Seconds until the broker's pid file names a live process: circus starts it a moment after the daemon."""
    start = time.monotonic()
    while not alive(broker_pid(run)):
        if time.monotonic() - start > timeout:
            raise TimeoutError(f"the broker of {run} did not start within {timeout} s")
        time.sleep(0.2)
    return round(time.monotonic() - start, 2)


def daemon_stop(run: Path) -> None:
    verdi(run, "daemon", "stop", check=False, timeout=120)


def broker_dir(run: Path) -> Path | None:
    found = sorted((config_dir(run) / "broker").glob(f"*-{PROFILE}"))
    return found[0] if found else None


def broker_pid(run: Path) -> int | None:
    folder = broker_dir(run)
    pid_file = folder / "broker.pid" if folder else None
    if not pid_file or not pid_file.exists():
        return None
    return int(pid_file.read_text().split()[-1])


def broker_queue(run: Path) -> dict[str, int]:
    """How many tasks the broker holds on disk, pending and processing."""
    folder = broker_dir(run)
    tasks = folder / "storage" / "tasks" if folder else None
    return {
        kind: len(list((tasks / kind).glob("*.json"))) if tasks and (tasks / kind).exists() else 0
        for kind in ("pending", "processing")
    }


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def leftovers(run: Path) -> list[str]:
    """Processes of this run still alive: the circus daemon and the broker, from their pid files."""
    found = []
    for pid_file in [
        *(config_dir(run) / "daemon").glob("circus-*.pid"),
        *(config_dir(run) / "broker").glob("*/broker.pid"),
    ]:
        try:
            pid = int(pid_file.read_text().split()[-1])
        except (OSError, ValueError):
            continue
        if alive(pid):
            found.append(f"{pid_file.name}: {pid}")
    return found


def signal_broker(run: Path, sig: signal.Signals) -> int | None:
    pid = broker_pid(run)
    if pid:
        os.kill(pid, sig)
    return pid


def home_snapshot(home_aiida: Path | None = None) -> list[str]:
    """Names and modification times under the user's ~/.aiida, two levels deep; never the files' contents."""
    home_aiida = home_aiida or Path.home() / ".aiida"
    if not home_aiida.exists():
        return []
    entries = [home_aiida, *home_aiida.iterdir()]
    entries += [child for entry in list(home_aiida.iterdir()) if entry.is_dir() for child in entry.iterdir()]
    return sorted(f"{int(entry.stat().st_mtime)} {entry}" for entry in entries)


def remove_run(run: Path) -> None:
    if leftovers(run):
        raise RuntimeError(f"processes of {run} are still alive: {leftovers(run)}")
    shutil.rmtree(run)


def record(out: Path, entry: dict[str, Any]) -> None:
    with out.open("a") as stream:
        stream.write(json.dumps(entry, default=str) + "\n")


def main(argv: Sequence[str]) -> int:
    if argv[:1] == ["snapshot"]:
        print("\n".join(home_snapshot()))
        return 0
    print("usage: s2_env.py snapshot", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
