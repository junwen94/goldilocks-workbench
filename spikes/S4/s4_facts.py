"""S4's library facts, in one process with no server: what LangGraph and Deep Agents do on their own, before any check
of ours. Each fact is a function that returns a record. The driver writes them all; the tests assert every fact in
REGRESSION, so a Deep Agents or LangGraph upgrade that changes one fails the check (plan, "Risks", row 5).

  stale         resume a paused tool with a pause ID that was never issued
  answered      resume with a pause ID already answered: in a finished conversation, and in a run whose other
                pauses are still pending
  plain-one     resume the only pending pause with a plain value (no ID)
  plain-many    resume a run with three pending pauses with a plain value
  invalid       answer a pause whose `response_schema` is a Pydantic model with a value that fails it
  loop          the AsyncSqliteSaver bound to one event loop, used synchronously from that loop's thread and from
                another OS thread
  serde         the saver's default serializer, and whether it falls back to pickle
  harness       whether HarnessProfile is public API, and how Deep Agents marks it
  skills-docs   what Deep Agents' SkillsMiddleware states about loading skills
  two-loops     driver only: a second event loop, in another thread, holds the saver's lock while the first loop
                reads; each trial waits a bounded time. Using one saver from two loops is undefined behaviour (its
                lock is an asyncio.Lock), and an unbounded version of this probe hung the check on a macOS runner,
                so the check never runs it.
"""

import asyncio
import contextlib
import inspect
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import deepagents
import deepagents.profiles
from deepagents.middleware.skills import SkillsMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import ValidationError
from s4_graphs import Effects, build_agent, build_executor
from s4_model import ScriptedModel

TWO_LOOP_TRIALS = 10
LOCK_HELD = 0.2
READ_WAIT = 2.0


def config_for(thread: str) -> Any:
    return {"configurable": {"thread_id": thread}}


def count(effects: Path, node: str) -> int:
    if not effects.exists():
        return 0
    return sum(1 for line in effects.read_text().splitlines() if f'"node": "{node}"' in line)


class Bench:
    """A temporary folder, one saver, the agent and the executor."""

    def __init__(self, folder: Path, saver: AsyncSqliteSaver) -> None:
        self.folder = folder
        (folder / "root" / "skills").mkdir(parents=True, exist_ok=True)
        self.effects_path = folder / "effects.jsonl"
        effects = Effects(self.effects_path)
        self.saver = saver
        self.agent = build_agent(ScriptedModel(), folder / "root", saver, effects, None)
        self.executor = build_executor(saver, effects)

    async def paused_choice(self, thread: str) -> str:
        await self.agent.ainvoke({"messages": [{"role": "user", "content": f"choose {thread}"}]}, config_for(thread))
        state = await self.agent.aget_state(config_for(thread))
        return str(state.interrupts[0].id)

    async def paused_run(self, thread: str) -> dict[str, str]:
        """Start a run of three candidates; its pause IDs by candidate."""
        given = {"parent": "c", "plan": {"recipe": "screen", "candidates": ["x", "y", "z"]}}
        await asyncio.to_thread(self.executor.invoke, given, config_for(thread))
        state = await self.executor.aget_state(config_for(thread))
        return {str(i.value["candidate"]): str(i.id) for i in state.interrupts}


async def with_bench(body: Callable[[Bench], Coroutine[Any, Any, dict[str, Any]]]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as folder:
        async with AsyncSqliteSaver.from_conn_string(str(Path(folder) / "db.sqlite")) as saver:
            return await body(Bench(Path(folder), saver))


async def fact_stale(bench: Bench) -> dict[str, Any]:
    pause = await bench.paused_choice("stale")
    runs_before = count(bench.effects_path, "choose_structure")
    raised = None
    try:
        await bench.agent.ainvoke(Command(resume={"0" * 32: {"structure": "mp-1"}}), config_for("stale"))
    except Exception as error:
        raised = type(error).__name__
    state = await bench.agent.aget_state(config_for("stale"))
    return {
        "raised": raised,
        "pending_after": [i.id for i in state.interrupts],
        "same_pause_pending": [i.id for i in state.interrupts] == [pause],
        "tool_ran_again": count(bench.effects_path, "choose_structure") - runs_before,
    }


async def fact_answered(bench: Bench) -> dict[str, Any]:
    conversation = config_for("answered")
    pause = await bench.paused_choice("answered")
    await bench.agent.ainvoke(Command(resume={pause: {"structure": "mp-2"}}), conversation)
    messages_before = len((await bench.agent.aget_state(conversation)).values["messages"])
    tool_runs_before = count(bench.effects_path, "choose_structure")
    raised = None
    try:
        await bench.agent.ainvoke(Command(resume={pause: {"structure": "mp-1"}}), conversation)
    except Exception as error:
        raised = type(error).__name__
    after = await bench.agent.aget_state(conversation)

    run = config_for("run-answered")
    pauses = await bench.paused_run("run-answered")
    await asyncio.to_thread(bench.executor.invoke, Command(resume={pauses["x"]: "finished"}), run)
    waits_before = count(bench.effects_path, "wait")
    run_raised = None
    try:
        await asyncio.to_thread(bench.executor.invoke, Command(resume={pauses["x"]: "failed"}), run)
    except Exception as error:
        run_raised = type(error).__name__
    run_after = await bench.executor.aget_state(run)
    return {
        "conversation_raised": raised,
        "conversation_new_messages": len(after.values["messages"]) - messages_before,
        "conversation_tool_ran_again": count(bench.effects_path, "choose_structure") - tool_runs_before,
        "conversation_pending": len(after.interrupts),
        "run_raised": run_raised,
        "run_wait_nodes_ran_again": count(bench.effects_path, "wait") - waits_before,
        "run_others_still_pending": sorted(i.id for i in run_after.interrupts) == sorted([pauses["y"], pauses["z"]]),
        "run_results": sorted(run_after.values.get("results", [])),
    }


async def fact_plain_one(bench: Bench) -> dict[str, Any]:
    await bench.paused_choice("plain-one")
    result = await bench.agent.ainvoke(Command(resume={"structure": "mp-3"}), config_for("plain-one"))
    return {"reply": str(result["messages"][-1].content)}


async def fact_plain_many(bench: Bench) -> dict[str, Any]:
    pauses = await bench.paused_run("run-plain-many")
    raised, message = None, ""
    try:
        await asyncio.to_thread(bench.executor.invoke, Command(resume="finished"), config_for("run-plain-many"))
    except Exception as error:
        raised, message = type(error).__name__, str(error).split(" Docs:")[0]
    state = await bench.executor.aget_state(config_for("run-plain-many"))
    return {
        "pending_before": len(pauses),
        "raised": raised,
        "message": message,
        "still_pending": len(state.interrupts),
    }


async def fact_invalid(bench: Bench) -> dict[str, Any]:
    pause = await bench.paused_choice("invalid")
    raised, errors = None, []
    try:
        await bench.agent.ainvoke(Command(resume={pause: {"structure": 2}}), config_for("invalid"))
    except ValidationError as error:
        raised, errors = type(error).__name__, [e["type"] for e in error.errors()]
    state = await bench.agent.aget_state(config_for("invalid"))
    result = await bench.agent.ainvoke(Command(resume={pause: {"structure": "mp-2"}}), config_for("invalid"))
    return {
        "raised": raised,
        "error_types": errors,
        "same_pause_pending": [i.id for i in state.interrupts] == [pause],
        "schema_sent": state.interrupts[0].response_schema is not None,
        "reply_after_valid": str(result["messages"][-1].content),
    }


async def fact_loop(bench: Bench) -> dict[str, Any]:
    await bench.paused_run("run-loop")
    config = config_for("run-loop")
    record: dict[str, Any] = {}
    try:
        bench.executor.get_state(config)
        record["sync_on_loop_thread"] = "ok"
    except Exception as error:
        record["sync_on_loop_thread"] = type(error).__name__
    try:
        state = await asyncio.to_thread(bench.executor.get_state, config)
        record["sync_from_other_thread"] = f"ok ({len(state.interrupts)} pauses)"
    except Exception as error:
        record["sync_from_other_thread"] = type(error).__name__
    return record


async def fact_serde(bench: Bench) -> dict[str, Any]:
    serde = bench.saver.serde
    return {"serializer": type(serde).__name__, "pickle_fallback": getattr(serde, "pickle_fallback", None)}


async def two_loop_trial(bench: Bench) -> dict[str, Any]:
    """Loop B, in another thread, holds the saver's lock for LOCK_HELD seconds; meanwhile this loop reads, waiting at
    most READ_WAIT seconds. The read is cancelled if it has not finished by then."""
    await bench.paused_run("run-two-loops")
    held = threading.Event()
    errors: list[str] = []

    async def hold() -> None:
        async with bench.saver.lock:
            held.set()
            await asyncio.sleep(LOCK_HELD)

    def other() -> None:
        try:
            asyncio.run(hold())
        except Exception as error:
            errors.append(type(error).__name__)

    holder = threading.Thread(target=other, daemon=True)
    holder.start()
    await asyncio.to_thread(held.wait, READ_WAIT)
    started = time.monotonic()
    read = asyncio.ensure_future(bench.executor.aget_state(config_for("run-two-loops")))
    done, _ = await asyncio.wait([read], timeout=READ_WAIT)
    seconds = time.monotonic() - started
    if not done:
        read.cancel()
        with contextlib.suppress(BaseException):
            await read
    await asyncio.to_thread(holder.join, READ_WAIT)
    return {"finished": bool(done), "seconds": round(seconds, 2), "holder_errors": errors}


def fact_two_loops() -> dict[str, Any]:
    trials = [asyncio.run(with_bench(two_loop_trial)) for _ in range(TWO_LOOP_TRIALS)]
    finished = [t["seconds"] for t in trials if t["finished"]]
    return {
        "trials": TWO_LOOP_TRIALS,
        "lock_held_seconds": LOCK_HELD,
        "read_wait_seconds": READ_WAIT,
        "reads_finished": len(finished),
        "finished_seconds": finished,
        "holder_errors": dict(Counter(e for t in trials for e in t["holder_errors"])),
    }


def fact_harness() -> dict[str, Any]:
    module_doc = deepagents.profiles.__doc__ or ""
    class_doc = inspect.getdoc(deepagents.HarnessProfile) or ""
    return {
        "in_top_level_all": "HarnessProfile" in deepagents.__all__,
        "module": deepagents.HarnessProfile.__module__,
        "module_marked_beta": "!!! beta" in module_doc,
        "class_marked_beta": "!!! beta" in class_doc,
        "beta_note": "may receive minor changes" in module_doc,
    }


def fact_skills_docs() -> dict[str, Any]:
    doc = inspect.getdoc(SkillsMiddleware) or ""
    return {
        "loaded_once_per_thread": "Skills are loaded once per thread and cached in state" in doc,
        "reload_by_none": "set `skills_metadata` to `None`" in doc,
        "later_sources_override": "later sources overriding" in doc,
    }


ASYNC_FACTS: dict[str, Callable[[Bench], Coroutine[Any, Any, dict[str, Any]]]] = {
    "stale": fact_stale,
    "answered": fact_answered,
    "plain-one": fact_plain_one,
    "plain-many": fact_plain_many,
    "invalid": fact_invalid,
    "loop": fact_loop,
    "serde": fact_serde,
}
SYNC_FACTS: dict[str, Callable[[], dict[str, Any]]] = {
    "harness": fact_harness,
    "skills-docs": fact_skills_docs,
    "two-loops": fact_two_loops,
}
REGRESSION = [name for name in [*ASYNC_FACTS, *SYNC_FACTS] if name != "two-loops"]


def run_fact(name: str) -> dict[str, Any]:
    if name in SYNC_FACTS:
        return SYNC_FACTS[name]()
    return asyncio.run(with_bench(ASYNC_FACTS[name]))


def all_facts(names: list[str] | None = None) -> list[dict[str, Any]]:
    return [{"fact": name, **run_fact(name)} for name in (names or [*ASYNC_FACTS, *SYNC_FACTS])]
