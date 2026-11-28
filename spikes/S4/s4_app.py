"""S4's server: the conversation agent and the executor behind FastAPI, with pause cards on server-sent events.

- A turn (`POST /conversations/{id}/turn`) streams the agent's frames; when the agent pauses, the stream ends with a
  `card` frame (pause ID, kind, payload, the answer's JSON Schema) and `end` with status "paused".
- An answer (`POST /conversations/{id}/answer`) resumes the conversation with `Command(resume={pause ID: value})`
  and streams the rest of the turn. An answer whose pause ID is not pending is refused before anything runs; an
  answer that fails the pause's schema gets an `invalid_answer` frame and the pause stays.
- `start_run` starts the executor on a run thread derived from the conversation and the tool call, driven from an
  OS thread of its own, and returns at once (D34). The run's cards and its end go to the conversation's outbox,
  which `GET /conversations/{id}/events` streams. `POST /runs/{run}/answer` resumes a run with answers for any of its
  pending pauses.
- At start-up the server reads every thread in the checkpointer and puts a `card` frame (source "catch-up") in the
  outbox of each conversation with a pending pause, its own or one of its runs'.

One AsyncSqliteSaver on the server's event loop. The executor's OS threads drive the run with the graph's
synchronous API, whose checkpointer calls the saver hands to that loop (`run_coroutine_threadsafe`).

Run as `python s4_app.py --port N --db FILE --root DIR --effects FILE --model-log FILE`.
"""

import argparse
import asyncio
import json
import os
import sys
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command, Interrupt
from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from s4_graphs import Effects, Plan, build_agent, build_executor
from s4_model import ScriptedModel


def config_for(thread: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread}}


def card(thread: str, interrupts: tuple[Interrupt, ...], source: str) -> dict[str, Any]:
    return {
        "event": "card",
        "thread": thread,
        "source": source,
        "pauses": [
            {"id": i.id, "kind": i.value.get("kind"), "payload": i.value, "response_schema": i.response_schema}
            for i in interrupts
        ],
        "pid": os.getpid(),
        "os_thread": threading.current_thread().name,
        "on_loop_thread": threading.current_thread() is threading.main_thread(),
    }


class Server:
    def __init__(self, db: Path, root: Path, effects: Path, model_log: Path) -> None:
        self.db, self.root = db, root
        self.effects = Effects(effects)
        self.model = ScriptedModel(log=str(model_log))
        self.loop: asyncio.AbstractEventLoop | None = None
        self.saver: AsyncSqliteSaver | None = None
        self.agent: Any = None
        self.executor: Any = None
        self.outboxes: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self.turn_locks: dict[str, asyncio.Lock] = {}
        self.run_locks: dict[str, threading.Lock] = {}
        self.started_runs: set[str] = set()

    def attach(self, saver: AsyncSqliteSaver) -> None:
        self.loop = asyncio.get_running_loop()
        self.saver = saver
        self.agent = build_agent(self.model, self.root, saver, self.effects, self.start_run)
        self.executor = build_executor(saver, self.effects)

    def outbox(self, conversation: str) -> asyncio.Queue[dict[str, Any]]:
        return self.outboxes.setdefault(conversation, asyncio.Queue())

    def emit(self, conversation: str, frame: dict[str, Any]) -> None:
        """Put a frame in a conversation's outbox; callable from any thread."""
        assert self.loop is not None
        self.loop.call_soon_threadsafe(lambda: self.outbox(conversation).put_nowait(frame))

    # The executor, on OS threads of its own.

    def start_run(self, parent: str, run: str, plan: Plan) -> str:
        """Called by the start_run tool. A run already started or already checkpointed is not started again."""
        if run in self.started_runs or self.executor.get_state(config_for(run)).values:
            return run
        self.started_runs.add(run)
        self.launch(run, parent, {"parent": parent, "plan": plan.model_dump()})
        return run

    def launch(self, run: str, parent: str, given: Any) -> None:
        name = f"executor-{run[4:12]}"
        threading.Thread(target=self.drive, args=(run, parent, given), name=name, daemon=True).start()

    def drive(self, run: str, parent: str, given: Any) -> None:
        lock = self.run_locks.setdefault(run, threading.Lock())
        with lock:
            config = config_for(run)
            try:
                for _ in self.executor.stream(given, config, stream_mode="updates"):
                    pass
                state = self.executor.get_state(config)
            except Exception as error:
                self.emit(parent, {"event": "run_error", "run": run, "error": repr(error)})
                return
            if state.interrupts:
                self.emit(parent, card(run, state.interrupts, "executor"))
            else:
                results = sorted(state.values.get("results", []))
                self.emit(parent, {"event": "run_finished", "run": run, "results": results, "pid": os.getpid()})

    # The conversation, on the event loop.

    async def stream_turn(self, conversation: str, given: Any) -> AsyncIterator[dict[str, Any]]:
        config = config_for(conversation)
        try:
            async for chunk in self.agent.astream(given, config, stream_mode="updates"):
                for node, update in chunk.items():
                    messages = update.get("messages") if isinstance(update, dict) else None
                    for message in messages if isinstance(messages, list) else []:
                        if isinstance(message, AIMessage):
                            calls = [c["name"] for c in message.tool_calls]
                            yield {"event": "message", "node": node, "text": str(message.content), "tool_calls": calls}
                        elif isinstance(message, ToolMessage):
                            yield {"event": "tool_result", "name": message.name, "text": str(message.content)[:300]}
        except ValidationError as error:
            yield {"event": "invalid_answer", "errors": json.loads(error.json(include_url=False))}
        state = await self.agent.aget_state(config)
        if state.interrupts:
            yield card(conversation, state.interrupts, "turn")
            yield {"event": "end", "status": "paused"}
        else:
            replies = [m for m in state.values.get("messages", []) if isinstance(m, AIMessage)]
            yield {"event": "end", "status": "finished", "reply": str(replies[-1].content) if replies else ""}

    async def pending(self, graph: Any, thread: str) -> list[str]:
        state = await graph.aget_state(config_for(thread))
        return [i.id for i in state.interrupts]

    async def catch_up(self) -> None:
        """Re-raise the card of every pending pause in the checkpointer (the start-up half of D17 part 3)."""
        assert self.saver is not None
        threads: set[str] = set()
        async for item in self.saver.alist(None):
            threads.add(str(item.config["configurable"]["thread_id"]))
        for thread in sorted(threads):
            if thread.startswith("run-"):
                state = await self.executor.aget_state(config_for(thread))
                parent = str(state.values.get("parent", ""))
                self.started_runs.add(thread)
            else:
                state = await self.agent.aget_state(config_for(thread))
                parent = thread
            if state.interrupts:
                self.outbox(parent).put_nowait(card(thread, state.interrupts, "catch-up"))
            elif state.next:
                self.outbox(parent).put_nowait({"event": "stopped", "thread": thread, "next": list(state.next)})


class TurnIn(BaseModel):
    text: str
    refresh_skills: bool = False


class AnswerIn(BaseModel):
    pause_id: str
    value: Any


class RunAnswerIn(BaseModel):
    answers: dict[str, Any]


def make_app(server: Server) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with AsyncSqliteSaver.from_conn_string(str(server.db)) as saver:
            server.attach(saver)
            await server.catch_up()
            yield

    app = FastAPI(lifespan=lifespan)

    def sse(frame: dict[str, Any]) -> ServerSentEvent:
        return ServerSentEvent(event=frame["event"], data=frame)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"pid": os.getpid(), "ready": server.agent is not None}

    @app.post("/conversations/{conversation}/turn", response_class=EventSourceResponse)
    async def turn(conversation: str, body: TurnIn) -> AsyncIterator[ServerSentEvent]:
        lock = server.turn_locks.setdefault(conversation, asyncio.Lock())
        async with lock:
            given: dict[str, Any] = {"messages": [{"role": "user", "content": body.text}]}
            if body.refresh_skills:
                given["skills_metadata"] = None
            async for frame in server.stream_turn(conversation, given):
                yield sse(frame)

    @app.post("/conversations/{conversation}/answer", response_class=EventSourceResponse)
    async def answer(conversation: str, body: AnswerIn) -> AsyncIterator[ServerSentEvent]:
        lock = server.turn_locks.setdefault(conversation, asyncio.Lock())
        async with lock:
            pending = await server.pending(server.agent, conversation)
            if body.pause_id not in pending:
                yield sse({"event": "refused", "reason": "pause ID not pending", "pending": pending})
                return
            async for frame in server.stream_turn(conversation, Command(resume={body.pause_id: body.value})):
                yield sse(frame)

    @app.get("/conversations/{conversation}/events", response_class=EventSourceResponse)
    async def events(conversation: str) -> AsyncIterator[ServerSentEvent]:
        queue = server.outbox(conversation)
        while True:
            yield sse(await queue.get())

    @app.post("/runs/{run}/answer")
    async def run_answer(run: str, body: RunAnswerIn) -> JSONResponse:
        state = await server.executor.aget_state(config_for(run))
        pending = sorted(i.id for i in state.interrupts)
        unknown = sorted(set(body.answers) - set(pending))
        if unknown or not body.answers:
            return JSONResponse({"refused": unknown, "pending": pending}, status_code=409)
        server.launch(run, str(state.values["parent"]), Command(resume=body.answers))
        return JSONResponse({"accepted": sorted(body.answers)}, status_code=202)

    @app.get("/threads/{thread}")
    async def thread_state(thread: str) -> dict[str, Any]:
        graph = server.executor if thread.startswith("run-") else server.agent
        state = await graph.aget_state(config_for(thread))
        values = state.values
        messages = values.get("messages", [])
        return {
            "pending": [i.id for i in state.interrupts],
            "next": list(state.next),
            "results": sorted(values.get("results", [])),
            "tool_messages": [m.name for m in messages if isinstance(m, ToolMessage)],
            "skills": [[s["name"], s["description"]] for s in values.get("skills_metadata") or []],
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--effects", type=Path, required=True)
    parser.add_argument("--model-log", type=Path, required=True)
    args = parser.parse_args()
    server = Server(args.db, args.root, args.effects, args.model_log)
    uvicorn.run(make_app(server), host="127.0.0.1", port=args.port, log_level="warning", timeout_graceful_shutdown=1)


if __name__ == "__main__":
    main()
