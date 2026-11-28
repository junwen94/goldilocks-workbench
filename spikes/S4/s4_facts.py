"""S4's library facts, in one process with no server: what LangGraph and Deep Agents do on their own, before any check
of ours. Each fact is a function that returns a record; the driver writes them and the tests assert them, so a
Deep Agents or LangGraph upgrade that changes one fails the check (plan, "Risks", row 5).

  stale         resume a paused tool with a pause ID that is not pending
  plain-one     resume the only pending pause with a plain value (no ID)
  plain-many    resume a run with three pending pauses with a plain value
  invalid       answer a pause whose `response_schema` is a Pydantic model with a value that fails it
  loop          the AsyncSqliteSaver bound to one event loop, used synchronously from that loop's thread, from
                another OS thread, and from a second event loop in another thread
  harness       whether HarnessProfile is public API, and how Deep Agents marks it
  skills-docs   what Deep Agents' SkillsMiddleware states about loading skills
"""

import asyncio
import inspect
import tempfile
import threading
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

CONTENDED_READS = 200


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

    async def paused_run(self, thread: str) -> list[str]:
        given = {"parent": "c", "plan": {"recipe": "screen", "candidates": ["x", "y", "z"]}}
        await asyncio.to_thread(self.executor.invoke, given, config_for(thread))
        state = await self.executor.aget_state(config_for(thread))
        return [str(i.id) for i in state.interrupts]


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

    errors: list[BaseException] = []

    async def reads() -> None:
        results = await asyncio.gather(
            *(bench.executor.aget_state(config) for _ in range(CONTENDED_READS)), return_exceptions=True
        )
        errors.extend(r for r in results if isinstance(r, BaseException))

    def second_loop() -> None:
        try:
            asyncio.run(reads())
        except Exception as error:
            errors.append(error)

    other = threading.Thread(target=second_loop)
    other.start()
    await reads()
    await asyncio.to_thread(other.join)
    record["two_loops_reads"] = CONTENDED_READS * 2
    record["two_loops_errors"] = sorted({type(e).__name__ for e in errors})
    record["two_loops_error_count"] = len(errors)
    record["two_loops_first_message"] = str(errors[0])[:200] if errors else ""
    return record


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
    "plain-one": fact_plain_one,
    "plain-many": fact_plain_many,
    "invalid": fact_invalid,
    "loop": fact_loop,
}
SYNC_FACTS: dict[str, Callable[[], dict[str, Any]]] = {"harness": fact_harness, "skills-docs": fact_skills_docs}


def run_fact(name: str) -> dict[str, Any]:
    if name in SYNC_FACTS:
        return SYNC_FACTS[name]()
    return asyncio.run(with_bench(ASYNC_FACTS[name]))


def all_facts() -> list[dict[str, Any]]:
    return [{"fact": name, **run_fact(name)} for name in [*ASYNC_FACTS, *SYNC_FACTS]]
