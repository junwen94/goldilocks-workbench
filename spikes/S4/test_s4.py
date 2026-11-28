"""Tests of S4's harness, and S4 kept as regression tests (plan, "Risks", row 5: "S4 tests kept as regression tests").

- Offline, on hand-written data: the SSE parser, the scripted model, every judge's pass and each kind of failure it
  reports, the skills tally and the report's counting (AGENTS.md rule 10).
- On the pinned Deep Agents and LangGraph, in this process: the library facts (s4_facts), a tool's pause and a run's
  staggered pauses resumed on a second saver opened on the same file, and skills kept in the checkpoint.
- One trial of tool-restart and of executor-restart through the real server, with SIGKILL.
No network and no LLM.
"""

import asyncio
import copy
import json
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import s4_experiments as x
import s4_facts as f
import s4_judge as j
import s4_report as r
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from s4_graphs import Effects, build_agent, build_executor, run_thread_id
from s4_model import ScriptedModel, decide, listed_skills

Obs = dict[str, Any]


# The SSE parser and the scripted model.


def test_parse_sse_reads_frames_and_ignores_other_fields() -> None:
    lines = ["event: card", 'data: {"event": "card", "n": 1}', "", ": a comment", "id: 7", 'data: {"n": 2}', ""]
    lines += ['data: {"n": 3}']
    assert [frame["n"] for frame in x.parse_sse(lines)] == [1, 2, 3]


def test_listed_skills_reads_only_the_available_skills_section() -> None:
    system = "- **early**: not a skill\n**Available Skills:**\n\n- **alpha**: alpha skill, version 1\n  -> Read `x`\n"
    system += "- **beta**: beta skill, version 2\n"
    assert listed_skills(system) == [["alpha", "alpha skill, version 1"], ["beta", "beta skill, version 2"]]
    assert listed_skills("no skills here") == []


def tool_result(name: str, content: str, call: str = "c") -> ToolMessage:
    return ToolMessage(content=content, name=name, tool_call_id=call)


def test_the_scripted_model_follows_each_scenario() -> None:
    system = SystemMessage("s")
    choose = decide([system, HumanMessage("choose t")])
    assert choose.tool_calls[0]["name"] == "choose_structure"
    assert choose.tool_calls[0]["id"] == "call-t-0"
    assert decide([system, HumanMessage("choose t"), choose, tool_result("choose_structure", "mp-2")]).content == (
        "chose mp-2"
    )
    plan = decide([system, HumanMessage("plan t")])
    assert plan.tool_calls[0]["args"] == {"plan": {"recipe": "screen", "candidates": ["x", "y", "z"]}}
    skills = [system, HumanMessage("skills t"), AIMessage(""), tool_result("choose_structure", "mp-1")]
    assert decide(skills).tool_calls[0]["args"]["file_path"] == "/skills/alpha/SKILL.md"
    skills += [AIMessage(""), tool_result("read_file", "a")]
    assert decide(skills).tool_calls[0]["args"]["file_path"] == "/skills/beta/SKILL.md"
    skills += [AIMessage(""), tool_result("read_file", "b")]
    assert decide(skills).content == "read skills after choosing mp-1"
    # Only the current turn counts: an earlier turn's tool results do not move the script on.
    later = [system, HumanMessage("choose a"), choose, tool_result("choose_structure", "mp-2"), AIMessage("chose")]
    assert decide([*later, HumanMessage("hello b")]).content == "hello b"


def test_the_scripted_model_logs_what_it_was_shown(tmp_path: Path) -> None:
    log = tmp_path / "model.jsonl"
    system = SystemMessage(content=[{"type": "text", "text": "**Available Skills:**\n- **alpha**: alpha skill, v 1"}])
    ScriptedModel(log=str(log)).invoke([system, HumanMessage("choose t")])
    record = json.loads(log.read_text())
    assert record["skills"] == [["alpha", "alpha skill, v 1"]]
    assert record["reply_tool"] == "choose_structure"


# The judges: a pass, and each kind of failure.


def choice_card(source: str = "turn", pause: str = "p1") -> dict[str, Any]:
    payload = {"kind": "choice", "options": ["mp-1", "mp-2", "mp-3"]}
    schema = {"type": "object"}
    return {
        "event": "card",
        "thread": "c",
        "source": source,
        "pauses": [{"id": pause, "kind": "choice", "payload": payload, "response_schema": schema}],
        "on_loop_thread": True,
    }


def tool_obs(restart: bool) -> Obs:
    obs: Obs = {
        "restart": restart,
        "turn": [{"event": "message"}, choice_card(), {"event": "end", "status": "paused"}],
        "answer": [{"event": "end", "status": "finished", "reply": "chose mp-2"}],
        "state": {"pending": [], "tool_messages": ["choose_structure"]},
    }
    if restart:
        obs["pids"] = [10, 11]
        obs["catch_up"] = choice_card("catch-up")
    return obs


def set_path(obs: Obs, path: tuple[Any, ...], value: Any) -> Obs:
    changed = copy.deepcopy(obs)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return changed


def test_judge_tool_passes_a_good_trial() -> None:
    assert j.judge_tool(tool_obs(False)) == []
    assert j.judge_tool(tool_obs(True)) == []


TOOL_FAILURES: list[tuple[str, bool, tuple[Any, ...], Any]] = [
    ("no card on the stream", False, ("turn",), [{"event": "end", "status": "finished"}]),
    ("the card has 2 pauses, expected 1", False, ("turn", 1, "pauses"), choice_card()["pauses"] * 2),
    ("the card's kinds are ['job'], expected ['choice']", False, ("turn", 1, "pauses", 0, "kind"), "job"),
    ("the card carries no answer schema", False, ("turn", 1, "pauses", 0, "response_schema"), None),
    ("the turn did not end paused", False, ("turn", 2, "status"), "finished"),
    ("the server was not restarted", True, ("pids",), [10, 10]),
    ("no catch-up card after the restart", True, ("catch_up",), None),
    (
        "the catch-up card's pause IDs differ from the pending ones before the restart",
        True,
        ("catch_up", "pauses", 0, "id"),
        "p2",
    ),
    ("the answer did not finish the turn", False, ("answer", 0, "status"), "paused"),
    ("the reply was 'chose mp-1', expected 'chose mp-2'", False, ("answer", 0, "reply"), "chose mp-1"),
    ("a pause is still pending after the answer", False, ("state", "pending"), ["p1"]),
    (
        "2 results of choose_structure in the conversation, expected 1",
        False,
        ("state", "tool_messages"),
        ["choose_structure", "choose_structure"],
    ),
]


@pytest.mark.parametrize(("failure", "restart", "path", "value"), TOOL_FAILURES)
def test_judge_tool_reports_each_failure(failure: str, restart: bool, path: tuple[Any, ...], value: Any) -> None:
    assert failure in j.judge_tool(set_path(tool_obs(restart), path, value))


def answers_obs() -> Obs:
    return {
        "turn": [choice_card(), {"event": "end", "status": "paused"}],
        "invalid": [{"event": "invalid_answer", "errors": []}, choice_card(), {"event": "end", "status": "paused"}],
        "stale": [{"event": "refused", "pending": ["p1"]}],
        "answer": [{"event": "end", "status": "finished", "reply": "chose mp-2"}],
        "again": [{"event": "refused", "pending": []}],
        "state": {"pending": [], "tool_messages": ["choose_structure"]},
    }


ANSWERS_FAILURES: list[tuple[str, tuple[Any, ...], Any]] = [
    ("no card on the stream", ("turn",), []),
    ("an answer that fails the schema was not reported", ("invalid", 0, "event"), "message"),
    ("the pause was not pending after an invalid answer", ("invalid", 1, "pauses", 0, "id"), "p9"),
    ("a pause ID that is not pending was not refused", ("stale",), [{"event": "end", "status": "finished"}]),
    ("the valid answer did not finish the turn", ("answer",), [{"event": "end", "status": "paused"}]),
    ("an answered pause ID was not refused", ("again",), [{"event": "end", "status": "finished"}]),
    ("0 results of choose_structure in the conversation, expected 1", ("state", "tool_messages"), []),
]


def test_judge_answers_passes_a_good_trial() -> None:
    assert j.judge_answers(answers_obs()) == []


@pytest.mark.parametrize(("failure", "path", "value"), ANSWERS_FAILURES)
def test_judge_answers_reports_each_failure(failure: str, path: tuple[Any, ...], value: Any) -> None:
    assert failure in j.judge_answers(set_path(answers_obs(), path, value))


def run_card(candidates: tuple[str, ...], source: str = "executor") -> dict[str, Any]:
    pauses = [
        {
            "id": f"id-{c}",
            "kind": "job",
            "payload": {"kind": "job", "candidate": c, "job": f"job-{c}"},
            "response_schema": None,
        }
        for c in candidates
    ]
    return {"event": "card", "thread": "run-1", "source": source, "pauses": pauses, "on_loop_thread": False}


def executor_obs(mode: str) -> Obs:
    cards = [run_card(("x", "y", "z"))]
    if mode in ("staggered", "restart"):
        cards.append(run_card(("y", "z")))
    if mode == "staggered":
        cards.append(run_card(("z",)))
    obs: Obs = {
        "mode": mode,
        "turn": [{"event": "end", "status": "finished", "reply": "started run-1"}],
        "free": [{"event": "end", "status": "finished", "reply": "hello"}],
        "cards": cards,
        "bogus": 409,
        "finished": {"event": "run_finished", "results": list(j.RUN_RESULTS)},
        "effects": {
            "submit": {"x": 1, "y": 1, "z": 1},
            "wait": {"x": 2, "y": 3, "z": 4},
            "check": {"x": 1, "y": 1, "z": 1},
            "finish": 1,
        },
    }
    if mode == "restart":
        obs["pids"] = [10, 11]
        obs["catch_up"] = run_card(("y", "z"), "catch-up")
    return obs


@pytest.mark.parametrize("mode", ["together", "staggered", "restart"])
def test_judge_executor_passes_a_good_trial(mode: str) -> None:
    assert j.judge_executor(executor_obs(mode)) == []


EXECUTOR_FAILURES: list[tuple[str, str, tuple[Any, ...], Any]] = [
    ("the plan's turn did not end at once with the run's ID", "together", ("turn", 0, "status"), "paused"),
    ("a second turn while the run was paused did not finish", "together", ("free", 0, "status"), "paused"),
    ("no card on the stream", "together", ("cards",), []),
    ("the card has 2 pauses, expected 3", "together", ("cards", 0), run_card(("x", "y"))),
    (
        "the card's kinds are ['choice', 'job'], expected ['job']",
        "together",
        ("cards", 0, "pauses", 1, "kind"),
        "choice",
    ),
    ("the run's card came from the event loop's thread", "together", ("cards", 0, "on_loop_thread"), True),
    ("the run's card does not have one pause per candidate", "together", ("cards", 0), run_card(("x", "x", "z"))),
    ("an unknown pause ID was not refused (status 202)", "together", ("bogus",), 202),
    ("after x's answer the card did not list y's and z's pauses", "staggered", ("cards", 1), run_card(("z",))),
    ("after y's answer the card did not list z's pause", "staggered", ("cards", 2), run_card(("y",))),
    ("no catch-up card after the restart", "restart", ("catch_up",), None),
    (
        "the catch-up card's pause IDs differ from the pending ones before the restart",
        "restart",
        ("catch_up",),
        run_card(("x", "y", "z"), "catch-up"),
    ),
    ("the server was not restarted", "restart", ("pids",), [10]),
    ("the run did not finish", "together", ("finished",), None),
    (
        "the run's results were ['x:passed'], expected ['x:passed', 'y:passed', 'z:failed']",
        "together",
        ("finished", "results"),
        ["x:passed"],
    ),
    ("submit ran 2 times for y, expected 1", "restart", ("effects", "submit", "y"), 2),
    ("check ran 0 times for z, expected 1", "together", ("effects", "check", "z"), 0),
    ("finish ran 2 times, expected 1", "together", ("effects", "finish"), 2),
]


@pytest.mark.parametrize(("failure", "mode", "path", "value"), EXECUTOR_FAILURES)
def test_judge_executor_reports_each_failure(failure: str, mode: str, path: tuple[Any, ...], value: Any) -> None:
    assert failure in j.judge_executor(set_path(executor_obs(mode), path, value))


def skills_obs() -> Obs:
    finished = [{"event": "end", "status": "finished", "reply": "r"}]
    return {
        "turn": [choice_card(), {"event": "end", "status": "paused"}],
        "pids": [10, 11],
        "catch_up": choice_card("catch-up"),
        "answer": finished,
        "hello_same": finished,
        "hello_refresh": finished,
        "hello_new": finished,
    }


SKILLS_FAILURES: list[tuple[str, tuple[Any, ...], Any]] = [
    ("no card on the stream", ("turn",), []),
    ("no catch-up card after the restart", ("catch_up",), None),
    ("the server was not restarted", ("pids",), [11, 11]),
    ("the answer did not finish the turn", ("answer",), []),
    ("the turn hello_refresh did not finish", ("hello_refresh", 0, "status"), "paused"),
]


def test_judge_skills_passes_a_good_trial() -> None:
    assert j.judge_skills(skills_obs()) == []


@pytest.mark.parametrize(("failure", "path", "value"), SKILLS_FAILURES)
def test_judge_skills_reports_each_failure(failure: str, path: tuple[Any, ...], value: Any) -> None:
    assert failure in j.judge_skills(set_path(skills_obs(), path, value))


def model_record(user: str, skills: list[list[str]], tool: str | None, result: str | None, reply: str | None) -> Obs:
    return {"user": user, "skills": skills, "tool": tool, "tool_result": result, "reply_tool": reply}


def test_skills_seen_names_what_the_model_was_shown_at_each_point() -> None:
    old = [["alpha", "alpha skill, version 1"], ["beta", "beta skill, version 1"]]
    new = [["alpha", "alpha skill, version 2"], ["gamma", "gamma skill, version 1"]]
    model = [
        model_record("skills t", old, None, None, "choose_structure"),
        model_record("skills t", old, "choose_structure", "mp-2", "read_file"),
        model_record("skills t", old, "read_file", "alpha body, version 2", "read_file"),
        model_record("skills t", old, "read_file", "Error: File '/skills/beta/SKILL.md' not found", None),
        model_record("hello t", old, None, None, None),
        model_record("hello t-refresh", new, None, None, None),
    ]
    assert j.skills_seen(model, "t") == {
        "before_pause": "alpha v1, beta v1",
        "after_resume": "alpha v1, beta v1",
        "alpha_read": "v2",
        "beta_read": "error",
        "same_thread_later": "alpha v1, beta v1",
        "refreshed": "alpha v2, gamma v1",
        "new_thread": "no call",
    }
    assert j.read_result(None) == "not read"
    assert j.read_result("alpha body, version 1") == "v1"
    assert j.read_result("something else") == "other"
    assert j.label([]) == "none"


# The report's counting.


def test_summarise_counts_passes_failures_effects_skills_and_facts() -> None:
    effects = {
        "submit": {"x": 1, "y": 1, "z": 1},
        "wait": {"x": 2, "y": 2, "z": 2},
        "check": {"x": 1, "y": 1, "z": 1},
        "finish": 1,
    }
    seen = {point: "v" for point in r.SKILL_POINTS}
    records: list[dict[str, Any]] = [
        {"experiment": "environment", "python": "3.12", "system": "s", "sqlite": "3", "packages": {"a": "1"}},
        {
            "experiment": "tool-restart",
            "trial": 0,
            "ok": True,
            "failures": [],
            "seconds_to_card": 0.1,
            "seconds_to_end": 0.2,
            "seconds_to_ready": 0.5,
            "catch_up": {"event": "card"},
            "pids": [1, 2],
        },
        {
            "experiment": "tool-restart",
            "trial": 1,
            "ok": False,
            "failures": ["no catch-up card after the restart"],
            "seconds_to_card": 0.3,
            "seconds_to_end": 0.4,
            "seconds_to_ready": 0.7,
            "catch_up": None,
            "pids": [2, 3],
        },
        {"experiment": "executor", "trial": 0, "ok": True, "failures": [], "effects": effects},
        {"experiment": "executor", "trial": 1, "ok": True, "failures": [], "effects": effects},
        {"experiment": "skills-restart", "trial": 0, "ok": True, "failures": [], "seen": seen},
        {"experiment": "facts", "fact": "stale", "raised": None},
        {"experiment": "executor", "server_left_running": True, "processes": [4]},
    ]
    summary = r.summarise(records)
    tool = summary["paths"]["tool-restart"]
    assert (tool["passed"], tool["trials"], tool["restarts"], tool["catch_up_cards"], tool["two_processes"]) == (
        1,
        2,
        2,
        1,
        2,
    )
    assert tool["failures"] == {"no catch-up card after the restart": 1}
    assert tool["to_ready"] == [0.5, 0.7]
    pattern = "submit x 1, y 1, z 1; wait x 2, y 2, z 2; check x 1, y 1, z 1; finish 1"
    assert summary["effects"]["executor"] == {pattern: 2}
    assert summary["skills"]["alpha_read"] == {"v": 1}
    assert summary["facts"] == {"stale": {"raised": None}}
    assert summary["left"] == ["executor"]
    assert "| tool-restart | 1 of 2 | 0.20 s, 0.30 s | 0.30 s, 0.40 s | 0.60 s, 0.70 s | 1 of 2 |" in r.render(summary)


def test_the_driver_refuses_to_mix_two_runs_in_one_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "results.jsonl"
    out.write_text("{}\n")
    monkeypatch.setattr(sys, "argv", ["s4_experiments.py", "--out", str(out)])
    with pytest.raises(SystemExit):
        x.main()
    monkeypatch.setattr(sys, "argv", ["s4_experiments.py", "--only", "nonsense", "--out", str(tmp_path / "n.jsonl")])
    with pytest.raises(SystemExit):
        x.main()


# Regression tests on the pinned libraries.


def test_library_facts_hold() -> None:
    facts = {record["fact"]: record for record in f.all_facts()}
    # LangGraph itself does not refuse a pause ID that is not pending: it runs the tool again and pauses again.
    assert facts["stale"]["raised"] is None
    assert facts["stale"]["same_pause_pending"] is True
    assert facts["stale"]["tool_ran_again"] == 1
    assert facts["plain-one"]["reply"] == "chose mp-3"
    assert facts["plain-many"]["raised"] == "RuntimeError"
    assert facts["plain-many"]["still_pending"] == 3
    # A typed answer that fails the schema raises before anything is saved; the pause stays.
    assert facts["invalid"]["raised"] == "ValidationError"
    assert facts["invalid"]["same_pause_pending"] is True
    assert facts["invalid"]["reply_after_valid"] == "chose mp-2"
    assert facts["loop"]["sync_on_loop_thread"] == "InvalidStateError"
    assert facts["loop"]["sync_from_other_thread"] == "ok (3 pauses)"
    assert facts["harness"]["in_top_level_all"] is True
    assert facts["harness"]["module_marked_beta"] is True
    assert all(facts["skills-docs"].values())


def opened(folder: Path, body: Callable[[AsyncSqliteSaver], Any]) -> Any:
    async def run() -> Any:
        async with AsyncSqliteSaver.from_conn_string(str(folder / "db.sqlite")) as saver:
            return await body(saver)

    return asyncio.run(run())


def test_a_tool_pause_resumes_on_a_second_saver(tmp_path: Path) -> None:
    (tmp_path / "root" / "skills" / "alpha").mkdir(parents=True)
    skill = "---\nname: alpha\ndescription: alpha skill, version 1\n---\nbody\n"
    (tmp_path / "root" / "skills" / "alpha" / "SKILL.md").write_text(skill)
    config: Any = {"configurable": {"thread_id": "conv-1"}}
    effects = Effects(tmp_path / "effects.jsonl")

    async def pause(saver: AsyncSqliteSaver) -> str:
        agent = build_agent(ScriptedModel(), tmp_path / "root", saver, effects, None)
        await agent.ainvoke({"messages": [{"role": "user", "content": "choose t"}]}, config)
        return str((await agent.aget_state(config)).interrupts[0].id)

    pause_id = opened(tmp_path, pause)
    (tmp_path / "root" / "skills" / "alpha" / "SKILL.md").write_text(skill.replace("version 1", "version 2"))

    async def resume(saver: AsyncSqliteSaver) -> tuple[list[str], str, list[str]]:
        agent = build_agent(ScriptedModel(), tmp_path / "root", saver, effects, None)
        pending = [i.id for i in (await agent.aget_state(config)).interrupts]
        result = await agent.ainvoke(Command(resume={pause_id: {"structure": "mp-2"}}), config)
        skills = [s["description"] for s in (await agent.aget_state(config)).values["skills_metadata"]]
        return pending, str(result["messages"][-1].content), skills

    pending, reply, skills = opened(tmp_path, resume)
    assert pending == [pause_id]
    assert reply == "chose mp-2"
    # The skills list is the one loaded at the thread's first turn, kept in the checkpoint.
    assert skills == ["alpha skill, version 1"]


def test_a_runs_pauses_resume_one_at_a_time_on_a_second_saver(tmp_path: Path) -> None:
    run = run_thread_id("conv-1", "call-1")
    config: Any = {"configurable": {"thread_id": run}}
    effects = Effects(tmp_path / "effects.jsonl")

    async def first(saver: AsyncSqliteSaver) -> dict[str, str]:
        executor = build_executor(saver, effects)
        given = {"parent": "conv-1", "plan": {"recipe": "screen", "candidates": ["x", "y", "z"]}}
        worker = threading.Thread(target=executor.invoke, args=(given, config))
        worker.start()
        await asyncio.to_thread(worker.join)
        state = await executor.aget_state(config)
        pauses = {i.value["candidate"]: i.id for i in state.interrupts}
        await asyncio.to_thread(executor.invoke, Command(resume={pauses["x"]: "finished"}), config)
        return pauses

    pauses = opened(tmp_path, first)

    async def second(saver: AsyncSqliteSaver) -> tuple[list[str], list[str]]:
        executor = build_executor(saver, effects)
        pending = sorted(i.id for i in (await executor.aget_state(config)).interrupts)
        answers = {pauses["y"]: "finished", pauses["z"]: "failed"}
        await asyncio.to_thread(executor.invoke, Command(resume=answers), config)
        return pending, sorted((await executor.aget_state(config)).values["results"])

    pending, results = opened(tmp_path, second)
    assert pending == sorted([pauses["y"], pauses["z"]])
    assert results == ["x:passed", "y:passed", "z:failed"]
    runs = [json.loads(line) for line in (tmp_path / "effects.jsonl").read_text().splitlines()]
    for node in ("submit", "check"):
        assert sorted(rec["candidate"] for rec in runs if rec["node"] == node) == ["x", "y", "z"]
    # Every resume runs the paused siblings' wait node again up to interrupt().
    assert sorted(rec["candidate"] for rec in runs if rec["node"] == "wait") == ["x", "x", "y", "y", "y", "z", "z", "z"]
    assert {rec["thread"] for rec in runs} == {run}


def test_one_restart_trial_of_each_kind_through_the_server(tmp_path: Path) -> None:
    for name, mode in (("tool", None), ("run", "restart")):
        server = x.Server(tmp_path / name)
        try:
            server.start()
            obs = x.trial_tool(server, "t", True) if mode is None else x.trial_executor(server, "t", mode)
            failures = j.judge_tool(obs) if mode is None else j.judge_executor(obs)
        finally:
            server.stop()
        assert failures == []
