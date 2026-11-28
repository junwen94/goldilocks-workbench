"""S4's verdicts: each judge turns one trial's observations (the frames the driver read, the effects the server
wrote) into the list of what went wrong; an empty list is a pass. `skills_seen` turns a skills trial's model log into
which skills the model was shown at each point. Pure functions, tested offline on hand-written observations
(AGENTS.md rule 10).
"""

from typing import Any

Frames = list[dict[str, Any]]
CANDIDATES = ("x", "y", "z")
RUN_ANSWERS = {"x": "finished", "y": "finished", "z": "failed"}
RUN_RESULTS = ["x:passed", "y:passed", "z:failed"]
CHOSEN = "mp-2"


def last(frames: Frames, event: str) -> dict[str, Any] | None:
    found = [f for f in frames if f.get("event") == event]
    return found[-1] if found else None


def ended(frames: Frames) -> str:
    end = last(frames, "end")
    return str(end["status"]) if end else "no end frame"


def ids(card: dict[str, Any] | None) -> list[str]:
    return [p["id"] for p in card["pauses"]] if card else []


def pause_of(card: dict[str, Any], candidate: str) -> str:
    return str(next(p["id"] for p in card["pauses"] if p["payload"].get("candidate") == candidate))


def judge_card(card: dict[str, Any] | None, pauses: int, kind: str) -> list[str]:
    if card is None:
        return ["no card on the stream"]
    wrong = []
    if len(card["pauses"]) != pauses:
        wrong.append(f"the card has {len(card['pauses'])} pauses, expected {pauses}")
    kinds = sorted({str(p["kind"]) for p in card["pauses"]})
    if kinds != [kind]:
        wrong.append(f"the card's kinds are {kinds}, expected ['{kind}']")
    return wrong


def judge_restart(obs: dict[str, Any], expected: list[str]) -> list[str]:
    wrong = []
    if len(set(obs.get("pids", []))) < 2:
        wrong.append("the server was not restarted")
    catch_up = obs.get("catch_up")
    if catch_up is None:
        wrong.append("no catch-up card after the restart")
    elif sorted(ids(catch_up)) != sorted(expected):
        wrong.append("the catch-up card's pause IDs differ from the pending ones before the restart")
    return wrong


def judge_tool(obs: dict[str, Any]) -> list[str]:
    """A tool's pause in the conversation, answered in the same process or after a restart."""
    card = last(obs["turn"], "card")
    wrong = judge_card(card, 1, "choice")
    if card is not None and card["pauses"] and card["pauses"][0].get("response_schema") is None:
        wrong.append("the card carries no answer schema")
    if ended(obs["turn"]) != "paused":
        wrong.append("the turn did not end paused")
    if obs.get("restart"):
        wrong += judge_restart(obs, ids(card))
    end = last(obs["answer"], "end")
    if end is None or end["status"] != "finished":
        wrong.append("the answer did not finish the turn")
    elif end.get("reply") != f"chose {CHOSEN}":
        wrong.append(f"the reply was {end.get('reply')!r}, expected 'chose {CHOSEN}'")
    if obs["state"]["pending"]:
        wrong.append("a pause is still pending after the answer")
    results = obs["state"]["tool_messages"].count("choose_structure")
    if results != 1:
        wrong.append(f"{results} results of choose_structure in the conversation, expected 1")
    return wrong


def judge_answers(obs: dict[str, Any]) -> list[str]:
    """An invalid answer, a pause ID that is not pending, the valid answer, then the answered ID again."""
    card = last(obs["turn"], "card")
    wrong = judge_card(card, 1, "choice")
    if last(obs["invalid"], "invalid_answer") is None:
        wrong.append("an answer that fails the schema was not reported")
    if card is not None and ids(last(obs["invalid"], "card")) != ids(card):
        wrong.append("the pause was not pending after an invalid answer")
    if last(obs["stale"], "refused") is None:
        wrong.append("a pause ID that is not pending was not refused")
    end = last(obs["answer"], "end")
    if end is None or end.get("reply") != f"chose {CHOSEN}":
        wrong.append("the valid answer did not finish the turn")
    if last(obs["again"], "refused") is None:
        wrong.append("an answered pause ID was not refused")
    results = obs["state"]["tool_messages"].count("choose_structure")
    if results != 1:
        wrong.append(f"{results} results of choose_structure in the conversation, expected 1")
    return wrong


def judge_executor(obs: dict[str, Any]) -> list[str]:
    """A run started by start_run, its three pauses answered together, one at a time, or across a restart."""
    wrong = []
    end = last(obs["turn"], "end")
    if end is None or end["status"] != "finished" or not str(end.get("reply", "")).startswith("started run-"):
        wrong.append("the plan's turn did not end at once with the run's ID")
    if ended(obs["free"]) != "finished":
        wrong.append("a second turn while the run was paused did not finish")
    cards = obs["cards"]
    first = cards[0] if cards else None
    wrong += judge_card(first, 3, "job")
    if first is None:
        return wrong
    if first.get("on_loop_thread"):
        wrong.append("the run's card came from the event loop's thread")
    if sorted(p["payload"].get("candidate") for p in first["pauses"]) != list(CANDIDATES):
        wrong.append("the run's card does not have one pause per candidate")
        return wrong
    if obs["bogus"] != 409:
        wrong.append(f"an unknown pause ID was not refused (status {obs['bogus']})")
    if obs["mode"] in ("staggered", "restart"):
        second = cards[1] if len(cards) > 1 else None
        if sorted(ids(second)) != sorted([pause_of(first, "y"), pause_of(first, "z")]):
            wrong.append("after x's answer the card did not list y's and z's pauses")
    if obs["mode"] == "staggered":
        third = cards[2] if len(cards) > 2 else None
        if ids(third) != [pause_of(first, "z")]:
            wrong.append("after y's answer the card did not list z's pause")
    if obs["mode"] == "restart":
        wrong += judge_restart(obs, [pause_of(first, "y"), pause_of(first, "z")])
    finished = obs.get("finished")
    if finished is None:
        wrong.append("the run did not finish")
    elif finished["results"] != RUN_RESULTS:
        wrong.append(f"the run's results were {finished['results']}, expected {RUN_RESULTS}")
    effects = obs["effects"]
    for node in ("submit", "check"):
        for candidate in CANDIDATES:
            runs = effects.get(node, {}).get(candidate, 0)
            if runs != 1:
                wrong.append(f"{node} ran {runs} times for {candidate}, expected 1")
    if effects.get("finish", 0) != 1:
        wrong.append(f"finish ran {effects.get('finish', 0)} times, expected 1")
    return wrong


def judge_skills(obs: dict[str, Any]) -> list[str]:
    """The resume itself in a skills trial: what the model was shown is `skills_seen`'s, not a verdict."""
    card = last(obs["turn"], "card")
    wrong = judge_card(card, 1, "choice")
    wrong += judge_restart(obs, ids(card))
    if ended(obs["answer"]) != "finished":
        wrong.append("the answer did not finish the turn")
    for key in ("hello_same", "hello_refresh", "hello_new"):
        if ended(obs[key]) != "finished":
            wrong.append(f"the turn {key} did not finish")
    return wrong


def label(skills: list[list[str]]) -> str:
    """[["alpha", "alpha skill, version 1"], ...] as "alpha v1, beta v1"."""
    return ", ".join(f"{name} v{description.split()[-1]}" for name, description in skills) or "none"


def read_result(text: str | None) -> str:
    if text is None:
        return "not read"
    if "version 2" in text:
        return "v2"
    if "version 1" in text:
        return "v1"
    if "not found" in text.lower() or "error" in text.lower():
        return "error"
    return "other"


def skills_seen(model: list[dict[str, Any]], tag: str) -> dict[str, str]:
    """Which skills the system prompt listed at each point of a skills trial, and what the two reads returned."""

    def first(user: str, tool: str | None, reply_tool: str | None = "any") -> dict[str, Any] | None:
        for record in model:
            if record["user"] == user and record["tool"] == tool and reply_tool in ("any", record["reply_tool"]):
                return record
        return None

    def listed(record: dict[str, Any] | None) -> str:
        return label(record["skills"]) if record else "no call"

    alpha = first(f"skills {tag}", "read_file", "read_file")
    beta = first(f"skills {tag}", "read_file", None)
    return {
        "before_pause": listed(first(f"skills {tag}", None)),
        "after_resume": listed(first(f"skills {tag}", "choose_structure")),
        "alpha_read": read_result(alpha["tool_result"] if alpha else None),
        "beta_read": read_result(beta["tool_result"] if beta else None),
        "same_thread_later": listed(first(f"hello {tag}", None)),
        "refreshed": listed(first(f"hello {tag}-refresh", None)),
        "new_thread": listed(first(f"hello {tag}-new", None)),
    }
