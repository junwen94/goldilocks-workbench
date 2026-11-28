"""S2's experiments that run inside a run's profile, as `python s2_inside.py <experiment> --out <file>`.

Imports AiiDA: s2_experiments runs this only as a subprocess with the run's AIIDA_PATH (s2_env.python). Each
experiment writes one JSON line per measurement to --out.
"""

import argparse
import json
import os
import random
import sys
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import s2_env as e


def write(out: Path, entry: dict[str, Any]) -> None:
    with out.open("a") as stream:
        stream.write(json.dumps(entry, default=str) + "\n")


def error_text(error: BaseException) -> str:
    return "".join(traceback.format_exception_only(error)).strip()[:300]


def run_folder() -> Path:
    return Path(os.environ["AIIDA_PATH"])


def daemon_control(out: Path) -> None:
    """Start, inspect, grow, shrink, restart and stop the daemon from Python, timing each step."""
    from aiida import load_profile
    from aiida.engine.daemon.client import get_daemon_client

    load_profile()
    client = get_daemon_client()
    run = run_folder()

    def step(name: str, action: Callable[[], Any]) -> None:
        start = time.monotonic()
        try:
            value, error = action(), None
        except Exception as caught:  # a spike records every failure and goes on
            value, error = None, error_text(caught)
        write(
            out,
            {
                "experiment": "daemon",
                "step": name,
                "seconds": round(time.monotonic() - start, 2),
                "value": value,
                "error": error,
                "broker_alive": e.alive(e.broker_pid(run)),
            },
        )

    def start() -> None:
        client.start_daemon(number_workers=1)

    step("start", start)
    step("broker ready after start (s)", lambda: e.wait_broker(run))
    step("running", lambda: client.is_daemon_running)
    step("workers", client.get_number_of_workers)
    step("increase", lambda: client.increase_workers(1, wait=True) and None)
    step("workers after increase", client.get_number_of_workers)
    step("decrease", lambda: client.decrease_workers(1, wait=True) and None)
    step("workers after decrease", client.get_number_of_workers)
    broker_before = e.broker_pid(run)
    step("restart", lambda: client.restart_daemon(wait=True) and None)
    step("broker kept its pid over the restart", lambda: e.broker_pid(run) == broker_before)
    step("workers after restart", client.get_number_of_workers)
    step("stop", lambda: client.stop_daemon(wait=True) and None)
    time.sleep(2)
    step("running after stop", lambda: client.is_daemon_running)


def caching(out: Path) -> None:
    """Which jobs come from the cache, with caching enabled for core.arithmetic.add (s2_env.setup)."""
    from aiida import load_profile
    from aiida.engine import run_get_node

    load_profile()
    from s2_processes import add_builder

    def job(case: str, x: int, y: int, **options: Any) -> dict[str, Any]:
        _, created = run_get_node(add_builder(x, y, **options))
        node: Any = created
        entry = {
            "experiment": "caching",
            "case": case,
            "pk": node.pk,
            "uuid": node.uuid,
            "exit_status": node.exit_status,
            "state": node.process_state.value,
            "from_cache": node.base.caching.is_created_from_cache,
            "source": node.base.caching.get_cache_source(),
            "hash": node.base.caching.get_hash(),
        }
        write(out, entry)
        return entry

    first = job("identical, first", 1, 2)
    job("identical, second", 1, 2)
    job("same inputs, code version 1", 3, 4, code="bash-v1")
    job("same inputs, code version 2", 3, 4, code="bash-v2")
    job("same inputs, code version 1 again", 3, 4, code="bash-v1")
    job("identical, with disable_cache", 1, 2, disable_cache=True)
    job("exit 410 (negative sum), first", -5, 2)
    job("exit 410 (negative sum), second", -5, 2)
    job("no output (silent code), first", 1, 2, code="silent")
    job("no output (silent code), second", 1, 2, code="silent")
    write(out, {"experiment": "caching", "case": "reference", "first_uuid": first["uuid"]})


def qe_exit_codes(out: Path) -> None:
    """Every exit code of aiida-quantumespresso's calculations, with invalidates_cache, read from their specs."""
    from importlib.metadata import entry_points, version

    from aiida import load_profile
    from aiida.plugins import CalculationFactory

    load_profile()
    for point in sorted(entry_points(group="aiida.calculations"), key=lambda p: p.name):
        if not point.name.startswith("quantumespresso."):
            continue
        factory: Any = CalculationFactory(point.name)
        spec = factory.spec()
        codes = sorted((code.status, label, bool(code.invalidates_cache)) for label, code in spec.exit_codes.items())
        write(
            out,
            {
                "experiment": "qe_exit_codes",
                "calculation": point.name,
                "plugin_version": version("aiida-quantumespresso"),
                "codes": [{"status": s, "label": label, "invalidates_cache": inv} for s, label, inv in codes],
            },
        )


def wait_terminated(pks: Sequence[int], timeout: float) -> list[Any]:
    from aiida.orm import load_node
    from s2_processes import fresh_reads

    deadline = time.monotonic() + timeout
    while True:
        fresh_reads()
        nodes = [load_node(pk) for pk in pks]
        if all(node.is_terminated for node in nodes) or time.monotonic() > deadline:
            return nodes
        time.sleep(1)


def monitors(out: Path) -> None:
    """An observe-only monitor (s2_processes.observe, entry point s2.observe) on a 20 s job. The daemon runs."""
    from aiida import load_profile
    from aiida.engine import submit

    load_profile()
    from s2_processes import add_builder

    try:
        submit(add_builder(5, 6, monitors={"observe": {"entry_point": "s2.observe_unversioned"}}))
        unversioned = "accepted"
    except Exception as caught:
        unversioned = error_text(caught)
    write(out, {"experiment": "monitors", "case": "monitor in a module without __version__", "result": unversioned})

    log = run_folder() / "monitor.log"
    monitor = {"entry_point": "s2.observe", "kwargs": {"log": str(log)}, "minimum_poll_interval": 1}
    with_monitor: Any = submit(add_builder(5, 6, sleep=20, monitors={"observe": monitor}))
    without: Any = submit(add_builder(5, 6, sleep=20, disable_cache=True))
    node, plain = wait_terminated([with_monitor.pk, without.pk], timeout=180)
    calls = log.read_text().splitlines() if log.exists() else []
    write(
        out,
        {
            "experiment": "monitors",
            "case": "observe-only monitor on a 20 s job",
            "state": node.process_state.value,
            "exit_status": node.exit_status,
            "calls": len(calls),
            "hash_with_monitor": node.base.caching.get_hash(),
            "hash_without": plain.base.caching.get_hash(),
            "plain_exit_status": plain.exit_status,
        },
    )


def threads(out: Path) -> None:
    """AiiDA nodes across threads: passed whole, passed as a PK, in a LangGraph ToolNode, and under contention."""
    import aiida.orm
    from aiida import load_profile
    from aiida.engine import submit

    load_profile()
    from s2_processes import add_builder

    orm: Any = aiida.orm
    values = [orm.Int(i).store() for i in range(5)]
    pks = [node.pk for node in values]

    def attempt(case: str, action: Callable[[], Any]) -> None:
        try:
            result, error = action(), None
        except Exception as caught:
            result, error = None, error_text(caught)
        write(out, {"experiment": "threads", "case": case, "ok": error is None, "result": result, "error": error})

    shared = orm.load_node(pks[0])
    with ThreadPoolExecutor(max_workers=1) as pool:
        attempt(
            "node loaded in the main thread: read in a worker thread",
            lambda: pool.submit(lambda: shared.value).result(),
        )
        attempt(
            "node loaded in the main thread: extra set in a worker thread",
            lambda: pool.submit(lambda: shared.base.extras.set("from_worker", 1)).result(),
        )
        attempt(
            "PK passed: loaded and extra set in a worker thread",
            lambda: pool.submit(lambda: orm.load_node(pks[1]).base.extras.set("from_worker", 1)).result(),
        )

    def toolnode() -> list[str]:
        from langchain_core.messages import AIMessage
        from langchain_core.tools import tool
        from langgraph.prebuilt import ToolNode

        @tool
        def read_node(pk: int) -> str:
            """Read an integer node by its PK and mark it."""
            node = orm.load_node(pk)
            node.base.extras.set("from_toolnode", threading.get_ident())
            return f"{node.value} in thread {threading.get_ident()}"

        from langgraph.graph import END, START, MessagesState, StateGraph

        graph = StateGraph(MessagesState)
        graph.add_node("tools", ToolNode([read_node]))
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        calls = [{"name": "read_node", "args": {"pk": pk}, "id": f"call-{pk}"} for pk in pks[2:]]
        reply = graph.compile().invoke({"messages": [AIMessage("", tool_calls=calls)]})
        return [str(message.content) for message in reply["messages"][1:]]

    attempt("LangGraph ToolNode with a sync tool that loads by PK", toolnode)
    attempt("main thread: main-thread id", lambda: threading.get_ident())

    submitted: list[Any] = [submit(add_builder(i, 1, sleep=2, disable_cache=True)) for i in range(20)]
    jobs = [int(node.pk) for node in submitted]
    errors: list[str] = []
    writes = [0]
    lock = threading.Lock()

    def writer(index: int) -> None:
        deadline = time.monotonic() + 30
        rng = random.Random(index)
        while time.monotonic() < deadline:
            try:
                orm.load_node(rng.choice(pks)).base.extras.set(f"writer_{index}", time.time())
                with lock:
                    writes[0] += 1
            except Exception as caught:
                with lock:
                    errors.append(error_text(caught))
            time.sleep(0.01)

    workers = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    finished = wait_terminated(jobs, timeout=180)
    write(
        out,
        {
            "experiment": "threads",
            "case": "4 writers for 30 s while the daemon runs 20 jobs",
            "writes": writes[0],
            "errors": len(errors),
            "error_kinds": sorted({x.split(":")[0] for x in errors}),
            "first_error": errors[0] if errors else None,
            "jobs": {n.pk: [n.process_state.value if n.process_state else None, n.exit_status] for n in finished},
        },
    )


EXPERIMENTS: dict[str, Callable[[Path], None]] = {
    "daemon": daemon_control,
    "caching": caching,
    "qe_exit_codes": qe_exit_codes,
    "monitors": monitors,
    "threads": threads,
}


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", choices=sorted(EXPERIMENTS))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if "AIIDA_PATH" not in os.environ:
        parser.error("run under a run's AIIDA_PATH (s2_env.python)")
    EXPERIMENTS[args.experiment](args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
