"""A FastAPI app that submits AiiDA jobs and records when it is woken as they end (S2, experiments 3 to 6).

One owner thread loads the profile, owns AiiDA's runner loop, and runs every AiiDA call; the web handlers hand it
work and wait for the answer. That is the design the workbench plan gives M5 ("one owner thread holding the profile
and running every AiiDA call through a queue").

For each job it registers `Runner.call_on_process_finish` (the wake) and, beside it, its own subscriber to state-change
broadcasts (to tell a broadcast wake from one by backup polling). In mode "rpc" the communicator also registers an RPC
subscriber, because the ZeroMQ broker forwards broadcasts only to identities it knows as task or RPC subscribers.

Imports AiiDA: run under a run's AIIDA_PATH, as `python s2_app.py --port N --mode plain|rpc`.
"""

import argparse
import asyncio
import concurrent.futures
import functools
import sys
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

TERMINAL = ("finished", "excepted", "killed")


class Owner:
    """The thread that holds the profile and the runner loop; `call` runs a function on it and returns its result."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.wakes: dict[int, float] = {}
        self.broadcasts: dict[int, tuple[float, str]] = {}
        self.tracked: list[int] = []
        self.started = time.time()
        self.ready = threading.Event()
        self.failure: BaseException | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.runner: Any = None
        self.thread = threading.Thread(target=self.main, name="aiida-owner", daemon=True)
        self.thread.start()
        if not self.ready.wait(60) or self.failure:
            raise RuntimeError(f"the AiiDA owner thread did not start: {self.failure}")

    def main(self) -> None:
        try:
            from aiida import load_profile
            from aiida.manage import get_manager

            load_profile()
            manager = get_manager()
            self.runner = manager.get_runner()
            self.loop = self.runner.loop
            asyncio.set_event_loop(self.loop)
            communicator = manager.get_communicator()
            if self.mode == "rpc":
                communicator.add_rpc_subscriber(lambda _c, _m: None, identifier=f"s2-listener-{uuid.uuid4().hex}")
            communicator.add_broadcast_subscriber(self.on_broadcast, identifier=f"s2-log-{uuid.uuid4().hex}")
        except BaseException as caught:
            self.failure = caught
            self.ready.set()
            return
        self.ready.set()
        assert self.loop is not None
        self.loop.run_forever()

    def on_broadcast(self, _communicator: Any, _body: Any, sender: Any, subject: Any, _correlation: Any) -> None:
        """Runs on the communicator's own thread; it only records the time (a dict write)."""
        if str(subject).rsplit(".", 1)[-1] in TERMINAL and sender is not None:
            self.broadcasts.setdefault(int(sender), (time.time(), str(subject)))

    def call(self, function: Callable[[], Any], timeout: float = 120) -> Any:
        assert self.loop is not None
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()

        def job() -> None:
            try:
                future.set_result(function())
            except BaseException as caught:
                future.set_exception(caught)

        self.loop.call_soon_threadsafe(job)
        return future.result(timeout)

    # The functions below run on the owner thread, through `call`.

    def woke(self, pk: int) -> None:
        self.wakes.setdefault(pk, time.time())

    def submit(self, kind: str, count: int, sleep: int) -> list[int]:
        from aiida.engine import submit
        from s2_processes import Boom, add_builder

        pks = []
        for index in range(count):
            node: Any = (
                submit(Boom)
                if kind == "boom"
                else submit(add_builder(index + 1, len(self.tracked) + 1, sleep=sleep, disable_cache=True))
            )
            pks.append(node.pk)
            self.tracked.append(node.pk)
            self.runner.call_on_process_finish(node.pk, functools.partial(self.woke, node.pk))
        return pks

    def adopt(self, pks: list[int]) -> None:
        """Tracks jobs another app submitted and registers their wakes, as a restarted server must at start-up."""
        for pk in pks:
            if pk not in self.tracked:
                self.tracked.append(pk)
                self.runner.call_on_process_finish(pk, functools.partial(self.woke, pk))

    def kill(self, pks: list[int]) -> None:
        from aiida.engine.processes.control import kill_processes
        from aiida.orm import load_node

        nodes: list[Any] = [load_node(pk) for pk in pks]
        kill_processes(nodes, timeout=10)

    def status(self) -> dict[str, Any]:
        from aiida.orm import load_node
        from s2_processes import fresh_reads

        fresh_reads()
        jobs = {}
        for pk in self.tracked:
            node = load_node(pk)
            broadcast = self.broadcasts.get(pk)
            jobs[str(pk)] = {
                "state": node.process_state.value if node.process_state else None,
                "exit_status": node.exit_status,
                "mtime": node.mtime.timestamp(),
                "wake": self.wakes.get(pk),
                "broadcast": broadcast[0] if broadcast else None,
            }
        return {"mode": self.mode, "poll_interval": self.runner._poll_interval, "jobs": jobs}


def make_app(owner: Owner) -> Any:
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "mode": owner.mode, "pid_started": owner.started}

    @app.post("/submit")
    def submit(request: dict[str, Any]) -> dict[str, Any]:
        kind, count, sleep = str(request.get("kind", "add")), int(request.get("count", 1)), int(request.get("sleep", 0))
        return {"pks": owner.call(lambda: owner.submit(kind, count, sleep))}

    @app.post("/adopt")
    def adopt(request: dict[str, Any]) -> dict[str, Any]:
        pks = [int(pk) for pk in request.get("pks", [])]
        owner.call(lambda: owner.adopt(pks))
        return {"adopted": pks}

    @app.post("/kill")
    def kill(request: dict[str, Any]) -> dict[str, Any]:
        pks = [int(pk) for pk in request.get("pks", [])]
        owner.call(lambda: owner.kill(pks))
        return {"killed": pks}

    @app.get("/status")
    def status() -> dict[str, Any]:
        result: dict[str, Any] = owner.call(owner.status)
        return result

    return app


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--mode", choices=["plain", "rpc"], default="plain")
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run(make_app(Owner(args.mode)), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
