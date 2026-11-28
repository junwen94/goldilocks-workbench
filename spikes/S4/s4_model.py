"""A scripted chat model for S4 (the plan's "scripted fake model"). It decides each reply from the conversation it
is given, never from a counter of its own, so a turn resumed in a new process gets the reply it would have had in
the old one. No network and no LLM.

The first word of the turn's user message picks the scenario; the rest is a tag the driver makes unique per trial:
  choose   call choose_structure; after its result, answer with it
  plan     call start_run with a plan of three candidates; after its result, answer that the run started
  skills   call choose_structure; after its result, read the alpha skill's SKILL.md, then the beta skill's; then
           answer
  hello    answer at once (a later turn, to see which skills the system prompt lists)

Every call appends one JSON line to `log` if one is given: the process, the turn's user message, the kind of the last
message, the skills the system prompt lists (name and description), and the last tool result.
"""

import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolCall, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable

CANDIDATES = ["mp-1", "mp-2", "mp-3"]
PLAN_CANDIDATES = ["x", "y", "z"]
SKILL_LINE = re.compile(r"^- \*\*(?P<name>[^*]+)\*\*: (?P<description>.*)$")


def listed_skills(system: str) -> list[list[str]]:
    """The skills a system prompt lists, as [name, description] pairs, in order. Reads Deep Agents' list format
    (`- **name**: description`) only after its "Available Skills" heading."""
    if "**Available Skills:**" not in system:
        return []
    section = system.split("**Available Skills:**", 1)[1]
    pairs = []
    for line in section.splitlines():
        match = SKILL_LINE.match(line)
        if match:
            pairs.append([match["name"], match["description"]])
    return pairs


def turn_of(messages: Sequence[BaseMessage]) -> tuple[str, list[BaseMessage]]:
    """The current turn's user message and the messages after it."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return str(messages[index].content), list(messages[index + 1 :])
    return "", list(messages)


def call(name: str, args: dict[str, Any], tag: str, step: int) -> AIMessage:
    tool_call: ToolCall = {"name": name, "args": args, "id": f"call-{tag}-{step}", "type": "tool_call"}
    return AIMessage(content="", tool_calls=[tool_call])


def decide(messages: Sequence[BaseMessage]) -> AIMessage:
    """The reply to a conversation: a tool call or a final answer."""
    user, after = turn_of(messages)
    scenario, _, tag = user.partition(" ")
    results = [m for m in after if isinstance(m, ToolMessage)]
    last = str(results[-1].content) if results else ""
    step = len(results)
    if scenario == "choose":
        return call("choose_structure", {"candidates": CANDIDATES}, tag, 0) if step == 0 else AIMessage(f"chose {last}")
    if scenario == "plan":
        if step == 0:
            plan = {"recipe": "screen", "candidates": PLAN_CANDIDATES}
            return call("start_run", {"plan": plan}, tag, 0)
        return AIMessage(f"started {last}")
    if scenario == "skills":
        if step == 0:
            return call("choose_structure", {"candidates": CANDIDATES}, tag, 0)
        if step in (1, 2):
            path = "/skills/alpha/SKILL.md" if step == 1 else "/skills/beta/SKILL.md"
            return call("read_file", {"file_path": path, "limit": 1000}, tag, step)
        return AIMessage(f"read skills after choosing {results[0].content}")
    return AIMessage(f"hello {tag}")


class ScriptedModel(BaseChatModel):
    """`decide` as a chat model. `bind_tools` returns the model itself: the script names its tools."""

    log: str | None = None

    @property
    def _llm_type(self) -> str:
        return "s4-scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable[LanguageModelInput, AIMessage]:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        reply = decide(messages)
        if self.log:
            system = next((m.text for m in messages if isinstance(m, SystemMessage)), "")
            user, after = turn_of(messages)
            results = [m for m in after if isinstance(m, ToolMessage)]
            record = {
                "pid": os.getpid(),
                "user": user,
                "last": type(messages[-1]).__name__,
                "skills": listed_skills(system),
                "tool": results[-1].name if results else None,
                "tool_result": str(results[-1].content) if results else None,
                "reply_tool": reply.tool_calls[0]["name"] if reply.tool_calls else None,
            }
            with Path(self.log).open("a") as handle:
                handle.write(json.dumps(record) + "\n")
        return ChatResult(generations=[ChatGeneration(message=reply)])
