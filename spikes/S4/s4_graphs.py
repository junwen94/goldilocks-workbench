"""The two graphs S4 pauses and resumes, shared by the server (s4_app), the in-process facts (s4_facts) and the tests.

- The conversation agent: Deep Agents' `create_deep_agent` with the scripted model (s4_model), a FilesystemBackend
  rooted at the run's folder, skills from its `/skills/`, and two tools. `choose_structure` pauses with
  `interrupt()` and a typed answer (`Choice`, through `response_schema`); `start_run` takes a typed plan and hands it
  to a callback that starts the executor on a thread of its own (D34).
- The executor: one LangGraph graph per run. It fans out one task per candidate (`Send`); each task runs the step
  subgraph, which submits in one node, pauses in the next and checks in a third (D17 part 1's shape). The step
  subgraph is invoked from inside the task's node, as a tool built as a subgraph would be (D9.1), and inherits the
  run's checkpointer.

Every node and tool body appends one line to the effects file when it runs, with the process and the OS thread, so
the driver counts how often each ran across restarts.
"""

import json
import operator
import os
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, TypedDict

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt
from pydantic import BaseModel, ConfigDict

RUN_NAMESPACE = uuid.UUID("0b6f5f3e-6c1e-4d55-9a4b-6a1c1b4a3d54")


class Choice(BaseModel):
    """The answer to a choice card."""

    model_config = ConfigDict(extra="forbid")
    structure: str


class Plan(BaseModel):
    """The approved plan the agent hands to the executor (D34.1: the document itself, never retold as text)."""

    model_config = ConfigDict(extra="forbid")
    recipe: str
    candidates: list[str]


class Effects:
    """Appends one JSON line per node or tool run. Thread-safe within a process; one server writes at a time."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()

    def write(self, node: str, **fields: Any) -> None:
        record = {"node": node, "pid": os.getpid(), "os_thread": threading.current_thread().name, **fields}
        with self.lock, self.path.open("a") as handle:
            handle.write(json.dumps(record) + "\n")


def run_thread_id(parent: str, tool_call_id: str) -> str:
    """The run's thread ID, derived from the parent conversation and the tool call (D34.2)."""
    return "run-" + str(uuid.uuid5(RUN_NAMESPACE, f"{parent}:{tool_call_id}"))


def thread_of(config: RunnableConfig | None = None) -> str:
    configurable = (config or get_config()).get("configurable", {})
    return str(configurable.get("thread_id", ""))


StartRun = Callable[[str, str, Plan], str]


def agent_tools(effects: Effects, start: StartRun | None) -> list[BaseTool]:
    @tool
    def choose_structure(candidates: list[str]) -> str:
        """Ask the user to choose one structure from the candidates; returns the chosen one."""
        effects.write("choose_structure", thread=thread_of())
        answer = interrupt({"kind": "choice", "options": candidates}, response_schema=Choice)
        return answer.structure

    @tool
    def start_run(plan: Plan, tool_call_id: Annotated[str, InjectedToolCallId], config: RunnableConfig) -> str:
        """Start an approved plan in the background; returns the run's thread ID at once."""
        parent = thread_of(config)
        run = run_thread_id(parent, tool_call_id)
        effects.write("start_run", thread=parent, run=run)
        if start is None:
            return run
        return start(parent, run, plan)

    return [choose_structure, start_run]


def build_agent(
    model: BaseChatModel, root: Path, saver: BaseCheckpointSaver[Any], effects: Effects, start: StartRun | None
) -> Any:
    backend = FilesystemBackend(root_dir=root, virtual_mode=True)
    return create_deep_agent(
        model=model,
        tools=agent_tools(effects, start),
        skills=["/skills/"],
        backend=backend,
        checkpointer=saver,
    )


class StepState(TypedDict, total=False):
    candidate: str
    job: str
    outcome: str
    verdict: str


class RunState(TypedDict, total=False):
    parent: str
    plan: dict[str, Any]
    results: Annotated[list[str], operator.add]


def build_step(effects: Effects) -> Any:
    """The long step: submit, then pause until the job's outcome comes back, then check (D17 part 1)."""

    def submit(state: StepState) -> StepState:
        effects.write("submit", thread=thread_of(), candidate=state["candidate"])
        return {"job": f"job-{state['candidate']}"}

    def wait(state: StepState) -> StepState:
        effects.write("wait", thread=thread_of(), candidate=state["candidate"])
        outcome = interrupt({"kind": "job", "candidate": state["candidate"], "job": state["job"]})
        return {"outcome": str(outcome)}

    def check(state: StepState) -> StepState:
        effects.write("check", thread=thread_of(), candidate=state["candidate"])
        return {"verdict": "passed" if state["outcome"] == "finished" else "failed"}

    graph = StateGraph(StepState)
    graph.add_node("submit", submit)
    graph.add_node("wait", wait)
    graph.add_node("check", check)
    graph.add_edge(START, "submit")
    graph.add_edge("submit", "wait")
    graph.add_edge("wait", "check")
    graph.add_edge("check", END)
    return graph.compile()


def build_executor(saver: BaseCheckpointSaver[Any], effects: Effects) -> Any:
    step_graph = build_step(effects)

    def fan_out(state: RunState) -> list[Send]:
        return [Send("step", {"candidate": c}) for c in state["plan"]["candidates"]]

    def step(state: StepState) -> RunState:
        result = step_graph.invoke(state)
        return {"results": [f"{state['candidate']}:{result['verdict']}"]}

    def finish(state: RunState) -> RunState:
        effects.write("finish", thread=thread_of(), results=sorted(state.get("results", [])))
        return {}

    graph = StateGraph(RunState)
    graph.add_node("step", step)
    graph.add_node("finish", finish)
    graph.add_conditional_edges(START, fan_out, ["step"])
    graph.add_edge("step", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=saver)
