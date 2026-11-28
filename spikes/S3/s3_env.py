"""S3's isolated AiiDA environments (workbench plan, "S3 submission key through aiida-quantumespresso").

Imports no AiiDA: AiiDA fixes its configuration folder when it is first imported, so everything that imports it runs
as a subprocess with AIIDA_PATH set to a fresh run folder under ~/.cache/goldilocks-spikes/s3/, as S2 does. That keeps
S3's profile, daemon and ZeroMQ broker apart from any AiiDA set-up the user already has, and outside cloud-synced
folders, which SQLite does not cope with. Each run's profile is called "s3".
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("GOLDILOCKS_SPIKES_CACHE", Path.home() / ".cache" / "goldilocks-spikes")) / "s3"
PROFILE = "s3"
# The stand-in for pw.x on presto's localhost: it writes no output, so aiida-quantumespresso's parser fails the
# PwCalculation with an exit code below 400, and PwBaseWorkChain, which has no handler for those, ends at once. The
# kill trials need jobs that run and end, not physics.
STANDIN = """#!/bin/bash
# S3's stand-in for pw.x (spikes/S3/s3_env.py): sleeps, writes nothing.
sleep {sleep}
"""


def new_run(name: str, root: Path = ROOT) -> Path:
    folder = root / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
    folder.mkdir(parents=True)
    return folder


def config_dir(run: Path) -> Path:
    return run / ".aiida"


def environment(run: Path) -> dict[str, str]:
    """The environment of every AiiDA subprocess of a run: its own AIIDA_PATH and S3's modules on PYTHONPATH (daemon
    workers inherit the starting process's path)."""
    env = dict(os.environ)
    env["AIIDA_PATH"] = str(run)
    env["PYTHONPATH"] = os.pathsep.join([str(HERE), *filter(None, [env.get("PYTHONPATH", "")])])
    env.pop("AIIDA_PROFILE", None)
    return env


def verdi(run: Path, *args: str, check: bool = True, timeout: float = 300) -> subprocess.CompletedProcess[str]:
    command = ["verdi", *args] if args[:1] == ("presto",) else ["verdi", "-p", PROFILE, *args]
    return subprocess.run(command, env=environment(run), capture_output=True, text=True, check=check, timeout=timeout)


def python(run: Path, *args: str, check: bool = True, timeout: float = 1800) -> subprocess.CompletedProcess[str]:
    """Runs a Python script of this folder under the run's AIIDA_PATH, in the run folder (dry runs write there)."""
    return subprocess.run(
        [sys.executable, str(HERE / args[0]), *args[1:]],
        env=environment(run),
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
        cwd=run,
    )


def write_standin(run: Path, sleep: float = 1) -> Path:
    path = run / "standin" / "pw.x"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(STANDIN.format(sleep=sleep))
    path.chmod(0o755)
    return path


def create_code(run: Path, label: str, executable: str | Path) -> None:
    verdi(
        run,
        "code",
        "create",
        "core.code.installed",
        "--non-interactive",
        "--label",
        label,
        "--computer",
        "localhost",
        "--filepath-executable",
        str(executable),
        "--default-calc-job-plugin",
        "quantumespresso.pw",
    )


def setup(
    run: Path,
    poll_interval: float = 10,
    caching: bool = False,
    standin_sleep: float = 1,
    real_pw: str | None = None,
    slots: int | None = None,
) -> dict[str, Any]:
    """A profile like goldilocks-agent's: SQLite storage, the ZeroMQ broker, presto's localhost, a stand-in pw.x code
    ("pw-standin") and, where pw.x is installed, a real one ("pw-real"). With `caching`, caching is on for every
    process (D39: on by default in goldilocks-agent's profiles)."""
    presto = verdi(run, "presto", "--use-zeromq", "--profile-name", PROFILE, "--non-interactive")
    verdi(run, "config", "set", "runner.poll.interval", str(poll_interval))
    if caching:
        verdi(run, "config", "set", "caching.default_enabled", "True")
    if slots is not None:
        verdi(run, "config", "set", "daemon.worker_process_slots", str(slots))
    create_code(run, "pw-standin", write_standin(run, standin_sleep))
    if real_pw:
        create_code(run, "pw-real", real_pw)
    return {
        "presto": presto.stdout.strip().splitlines()[-3:],
        "poll_interval": poll_interval,
        "caching": caching,
        "real_pw": real_pw,
        "slots": slots,
    }


def daemon_start(run: Path, workers: int = 1) -> None:
    verdi(run, "daemon", "start", str(workers))
    wait_broker(run)


def daemon_stop(run: Path) -> None:
    verdi(run, "daemon", "stop", check=False, timeout=120)


def wait_broker(run: Path, timeout: float = 20) -> float:
    """Seconds until the broker's pid file names a live process: circus starts it a moment after the daemon."""
    start = time.monotonic()
    while not alive(broker_pid(run)):
        if time.monotonic() - start > timeout:
            raise TimeoutError(f"the broker of {run} did not start within {timeout} s")
        time.sleep(0.2)
    return round(time.monotonic() - start, 2)


def broker_dir(run: Path) -> Path | None:
    found = sorted((config_dir(run) / "broker").glob(f"*-{PROFILE}"))
    return found[0] if found else None


def broker_pid(run: Path) -> int | None:
    folder = broker_dir(run)
    pid_file = folder / "broker.pid" if folder else None
    if not pid_file or not pid_file.exists():
        return None
    return int(pid_file.read_text().split()[-1])


def broker_tasks(run: Path) -> dict[str, list[int]]:
    """The process PKs of the tasks the ZeroMQ broker holds on disk, pending and processing, read without changing
    anything. aiida-core's own get_process_tasks() builds a PersistentQueue on the same folder, and that moves every
    processing task back to pending (aiida/brokers/zeromq/queue.py, `_load`), so S3 reads the files instead."""
    folder = broker_dir(run)
    found: dict[str, list[int]] = {"pending": [], "processing": []}
    for kind in found:
        path = folder / "storage" / "tasks" / kind if folder else None
        for task_file in sorted(path.glob("*.json")) if path and path.exists() else []:
            try:
                body = json.loads(task_file.read_text()).get("body") or {}
                found[kind].append(int(body["args"]["pid"]))
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return found


def daemon_log_lines(run: Path, needles: list[str], limit: int = 40) -> list[str]:
    """Lines of the daemon's logs that mention one of `needles` or report an error or a warning."""
    lines = []
    for log in sorted((config_dir(run) / "daemon" / "log").glob("*.log")):
        for line in log.read_text(errors="replace").splitlines():
            if any(needle in line for needle in needles) or any(m in line for m in ("ERROR", "WARNING", "Traceback")):
                lines.append(f"{log.name}: {line.strip()[:300]}")
    return lines[-limit:]


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
