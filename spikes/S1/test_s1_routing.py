"""Offline tests of S1b: the GENIUS rule and checksum, the draft catalogue and its scoring, the joining of streamed
tool-call pieces, the proxy's pass-through, the carried predecessor cases' shape and judges, `step_of` and `summary`.
No model or network."""

import json
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import s1_catalogue as cat
import s1_common as c
import s1_genius as g
import s1_routing as r

# --- GENIUS ----------------------------------------------------------------------------------------------------
# Written for this test around the phrases the rule matches; not taken from GENIUS's requests. Against the cached
# requests (2026-11-27), none shares more than four words in a row with any of them, and those four are a phrase of
# the rule ("without changing the lattice").


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("NaCl rock salt: I need a geometry optimisation at the PBE level on a 6x6x6 k-point grid.", "relaxation"),
        ("MoS2 monolayer: relax it, with Marzari-Vanderbilt smearing and a mixing beta of 0.3.", "relaxation"),
        ("Could you run a geometry refinement on wurtzite ZnO (space group 186)?", "relaxation"),
        ("Please optimise the wurtzite GaN structure; LDA is fine.", "relaxation"),
        ("Let the atoms of Si find their minimum with PBE, without changing the lattice.", "relax"),
        ("What lattice constant does PBEsol give for MgO once the cell is fully optimised?", "vc-relax"),
        ("TiO2: let both the cell and the ions move (cell_dofree = 'all') while it relaxes.", "vc-relax"),
        ("Just a single shot SCF on GaAs, please; keep every setting at its default.", "scf_single_point"),
        ("For bcc Fe with PBE0 and spin polarisation, what is the total magnetization?", "scf_single_point"),
        ("Relax graphene several times, stepping ecutwfc from 40 to 70 Ry.", None),
        (
            "For CrI3, report the total magnetization with each of the following exchange-correlation functionals: "
            "PBE and PBE0.",
            None,
        ),
        ("Compare hexagonal BN's lattice parameters with and without a dispersion correction.", None),
        ("Plot the phonon dispersion of diamond.", None),
    ],
)
def test_the_rule(request_text: str, expected: str | None) -> None:
    assert g.label(request_text) == expected


def test_studies_and_unplaced_requests_are_told_apart() -> None:
    assert g.rule_of("Relax X once for each cutoff from 35 to 55 Ry.") == g.STUDY
    assert g.rule_of("Plot the phonon dispersion of diamond.") == "unlabelled"


def test_every_label_has_a_calculation_group_in_the_catalogue() -> None:
    labels = {task for _, task in g.RULES if task != g.STUDY}
    assert labels == set(g.CALCULATION)
    assert all(tool in cat.TOOLS for tools in g.CALCULATION.values() for tool in tools)


def test_digest_ignores_order_and_sees_any_change() -> None:
    a = [g.Request(2, "b", "X", "mc3d"), g.Request(1, "a", "Y", "mc2d")]
    assert g.digest(a) == g.digest(list(reversed(a)))
    assert g.digest(a) != g.digest([g.Request(2, "b!", "X", "mc3d"), g.Request(1, "a", "Y", "mc2d")])


def test_extract_reads_the_record_layout() -> None:
    document = [{"calculation_description": "Relax NaCl.", "analysis_dict": {"formula": "NaCl", "database": "mc3d"}}]
    assert g.extract(7, document) == g.Request(7, "Relax NaCl.", "NaCl", "mc3d")
    with pytest.raises(ValueError):
        g.extract(7, ["not a record"])


def test_load_refuses_requests_that_changed(tmp_path: Path) -> None:
    lines = [json.dumps({"record": n, "request": f"r{n}", "formula": "X", "database": "mc3d"}) for n in range(g.COUNT)]
    (tmp_path / "requests.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="GENIUS requests changed"):
        g.load(tmp_path)


# --- catalogue -------------------------------------------------------------------------------------------------


def test_the_catalogue_sizes() -> None:
    assert len(cat.catalogue("short").splitlines()) == len(cat.RECIPES) + len(cat.TOOLS) == 51
    assert len(cat.catalogue("long").splitlines()) == 81
    assert set(cat.DISTRACTORS).isdisjoint(cat.TOOLS)


def test_every_goal_names_catalogue_entries() -> None:
    assert len(cat.GOALS) == 30
    assert len({x.id for x in cat.GOALS}) == 30
    for item in cat.GOALS:
        assert item.recipes <= {*cat.RECIPES, "none"}, item.id
        assert all(group <= set(cat.TOOLS) for group in item.groups), item.id
        assert item.no_tools == (not item.groups), item.id


def test_the_schema_offers_what_the_size_offers() -> None:
    short, long = cat.schema("short"), cat.schema("long")
    assert short["properties"]["recipe"]["enum"][-1] == "none"
    assert len(long["properties"]["tools"]["items"]["enum"]) == len(cat.TOOLS) + len(cat.DISTRACTORS)
    assert "md.classical" not in short["properties"]["tools"]["items"]["enum"]


def test_the_guided_prompt_differs_by_one_sentence() -> None:
    assert cat.SYSTEM_GUIDED != cat.SYSTEM
    assert cat.SYSTEM_GUIDED.replace("A recipe is a whole multi-step task; most requests need none. ", "") == cat.SYSTEM


DB, CALC = frozenset(cat.DB), frozenset({"aiida.relax", "aiida.vc_relax"})
NONE_OR_ONE = frozenset({"none", "recipe.one_material"})


@pytest.mark.parametrize(
    ("parsed", "outcome", "recipe_ok", "tools_ok"),
    [
        ({"recipe": "none", "tools": ["databases.search", "aiida.relax"]}, "pass", True, True),
        (
            {"recipe": "recipe.one_material", "tools": ["databases.get_structure", "aiida.vc_relax", "dft.review"]},
            "pass",
            True,
            True,
        ),
        (
            {"recipe": "recipe.screening_funnel", "tools": ["databases.search", "aiida.relax"]},
            "recipe:recipe.screening_funnel",
            False,
            True,
        ),
        ({"recipe": "none", "tools": ["aiida.relax"]}, "missing:databases.get_structure|databases.search", True, False),
        ({"recipe": "none", "tools": ["databases.search", "md.classical"]}, "invalid", None, None),
        ({"recipe": "none"}, "invalid", None, None),
        ("none", "invalid", None, None),
    ],
)
def test_score_pick(parsed: Any, outcome: str, recipe_ok: bool | None, tools_ok: bool | None) -> None:
    result = cat.score_pick(parsed, NONE_OR_ONE, [DB, CALC], "short")
    assert result.outcome == outcome
    assert result.passed == (outcome == "pass")
    assert result.detail.get("recipe_ok") == recipe_ok
    assert result.detail.get("tools_ok") == tools_ok


def test_score_pick_counts_extras_and_distractors_and_refuses_tools_on_chat() -> None:
    picked = {"recipe": "none", "tools": ["databases.search", "aiida.relax", "dft.review", "md.classical"]}
    result = cat.score_pick(picked, NONE_OR_ONE, [DB, CALC], "long")
    assert result.passed
    assert result.detail["extra"] == 2
    assert result.detail["distractors"] == ["md.classical"]
    chat = cat.score_pick({"recipe": "none", "tools": ["dft.review"]}, frozenset({"none"}), [], "short", True)
    assert (chat.passed, chat.outcome) == (False, "tools-on-chat")
    assert cat.score_pick({"recipe": "none", "tools": []}, frozenset({"none"}), [], "short", True).passed


# --- streamed tool-call pieces ---------------------------------------------------------------------------------


def piece(index: int, call_id: str | None, name: str | None, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(index=index, id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def test_pieces_of_one_call_join() -> None:
    joined = r.join_tool_call_pieces([piece(0, "a", "search", '{"formula": '), piece(0, None, None, '"GaAs"}')])
    assert [(x["name"], x["arguments"]) for x in joined] == [("search", '{"formula": "GaAs"}')]


def test_whole_calls_at_one_index_split_on_a_new_id_only_with_the_split() -> None:
    pieces = [piece(0, "a", "search", '{"formula": "GaAs"}'), piece(0, "b", "search", '{"formula": "TiO2"}')]
    assert len(r.join_tool_call_pieces(pieces)) == 2
    merged = r.join_tool_call_pieces(pieces, split_on_new_id=False)
    assert len(merged) == 1
    assert merged[0]["arguments"] == '{"formula": "GaAs"}{"formula": "TiO2"}'


def test_calls_at_different_indexes_split_either_way() -> None:
    pieces = [piece(0, "a", "search", "{}"), piece(1, "b", "review", "{}")]
    assert len(r.join_tool_call_pieces(pieces, split_on_new_id=False)) == 2


def test_as_arguments() -> None:
    assert r.as_arguments('{"a": 1}') == {"a": 1}
    assert r.as_arguments("{broken") == "{broken"
    assert r.as_arguments({"a": 1}) == {"a": 1}


# --- the proxy passes streamed replies on as they arrive ------------------------------------------------------


@pytest.fixture
def slow_streamer() -> Iterator[str]:
    lines = [b'{"message": {"content": "a"}, "done": false}\n', b'{"message": {"content": "b"}, "done": true}\n']

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for line in lines:
                self.wfile.write(line)
                self.wfile.flush()
                time.sleep(0.2)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_stream_through_passes_pieces_on_as_they_come(slow_streamer: str, tmp_path: Path) -> None:
    with c.CaptureProxy(slow_streamer, tmp_path / "requests.jsonl", stream_through=True) as proxy:
        request = urllib.request.Request(proxy.url + "/api/chat", b'{"stream": true}', method="POST")
        start = time.monotonic()
        with urllib.request.urlopen(request, timeout=10) as response:
            first = response.readline()
            first_after = time.monotonic() - start
            rest = response.read()
    assert json.loads(first)["message"]["content"] == "a"
    assert json.loads(rest)["done"] is True
    assert first_after < 0.2, "the first line must arrive before the upstream has sent the second"
    assert proxy.chunks == 2


@pytest.fixture
def stalling_streamer() -> Iterator[str]:
    """Sends the headers and one line, then nothing for longer than the proxy waits."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            self.wfile.write(b'{"message": {"content": "a"}, "done": false}\n')
            self.wfile.flush()
            time.sleep(2)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_a_stream_that_stalls_part_way_ends_with_an_error_line(stalling_streamer: str, tmp_path: Path) -> None:
    with c.CaptureProxy(stalling_streamer, tmp_path / "requests.jsonl", timeout=0.5, stream_through=True) as proxy:
        request = urllib.request.Request(proxy.url + "/api/chat", b'{"stream": true}', method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            status, lines = response.status, response.read().splitlines()
    assert status == 200
    assert len(lines) == 2, "no second status line or headers in the body"
    assert json.loads(lines[0])["message"]["content"] == "a"
    assert json.loads(lines[1])["error"].startswith("capture proxy: TimeoutError")


# --- the carried predecessor cases ----------------------------------------------------------------------------


def test_the_carried_cases_have_their_shape() -> None:
    import s1_predecessor_cases as p
    import s1_predecessor_prompt as prompt

    assert len(p.CASES) == 36
    assert sum(x.in_68 for x in p.CASES) == 19
    assert len({x.id for x in p.CASES}) == 36
    assert [t["function"]["name"] for t in p.TOOLS] == [
        "find_in_databases",
        "get_structure",
        "dft_open_structure",
        "dft_settings",
        "dft_set",
        "dft_review",
        "dft_download_bundle",
        "dft_magnetic_orderings",
    ]
    assert set(p.SCHEMAS) == {t["function"]["name"] for t in p.TOOLS}
    assert prompt.SYSTEM.endswith("\n\nAnswer briefly.")
    for case in p.CASES:
        assert case.messages and case.messages[0]["role"] != "system", case.id
        assert p.Step([], "").__class__ is p.Step


# --- the carried judges, on hand-written steps -------------------------------------------------------------------
# Carrying changed them (`classify` instead of jsonschema, the English check, the hours pattern), so each kind of
# judge is run here on steps that pass and steps that fail for each reason. The answers' values come from the
# recorded review in the cases' history: a 48 Ry cutoff, a 6x6x6 mesh, the 168 h walltime ceiling.


def judged(case_id: str, content: str = "", *calls: tuple[str, Any]) -> str | None:
    import s1_predecessor_cases as p

    case = next(x for x in p.CASES if x.id == case_id)
    return case.judge(p.Step([{"name": name, "arguments": args} for name, args in calls], content))


@pytest.mark.parametrize(
    ("calls", "content", "verdict"),
    [
        ([("find_in_databases", {"formula": "GaAs"})], "", None),
        ([("find_in_databases", '{"formula": "Ga As"}')], "", None),
        ([("find_in_databases", {"formula": "TiO2"})], "", "wrong arguments"),
        ([("find_in_databases", {"formula": "GaAs", "colour": "red"})], "", "arguments fail the schema: extra:colour"),
        ([("find_in_databases", {})], "", "arguments fail the schema: missing:formula"),
        ([("find_in_databases", '{"formula": "GaAs"')], "", "arguments are not JSON"),
        ([("dft_review", {})], "", "called dft_review"),
        ([], "GaAs has been computed many times.", "no tool call"),
    ],
)
def test_a_tool_judge(calls: list[tuple[str, Any]], content: str, verdict: str | None) -> None:
    assert judged("R1", content, *calls) == verdict


@pytest.mark.parametrize(
    ("content", "verdict"),
    [
        ("I can help you set up DFT calculations with goldilocks-core.", None),
        ("\u4f60\u597d. I can help.", "answer is not in English"),
        ("Ich kann Ihnen helfen, und die Rechnung ist nicht schwer.", "answer is not in English"),
        ("   ", "empty answer"),
    ],
)
def test_an_answer_judge(content: str, verdict: str | None) -> None:
    assert judged("N3", content) == verdict


def test_an_answer_judge_refuses_a_tool_call_and_wants_its_number() -> None:
    assert judged("N3", "", ("find_in_databases", {"formula": "NaCl"})) == "called find_in_databases"
    assert judged("V1", "3") is None
    assert judged("V1", "three") == "answer lacks '3'"


def test_one_of_passes_on_either_and_names_both_failures() -> None:
    assert judged("G1", "", ("find_in_databases", {"formula": "NaCl"})) is None
    assert judged("G1", "Do you want a structure from the databases?") is None
    assert judged("G1", "", ("find_in_databases", {"formula": "KCl"})) == "wrong arguments / called find_in_databases"


@pytest.mark.parametrize(
    ("content", "verdict"),
    [
        ("Goldilocks recommends a 48 Ry cutoff and a 6x6x6 mesh; nothing blocks generation.", None),
        ("The walltime is the partition's 168h ceiling unless you set one.", None),
        ("I would raise the cutoff to 60 Ry.", "values of its own: 60"),
        ("An 8x8x8 mesh would be safer.", "values of its own: 8x8x8"),
        ("| setting | value |\n|---|---|\n| ecutwfc | 48 Ry |", "repeats the card as a table"),
        ("Cutoffs 48 Ry and 192 Ry, a 6x6x6 mesh, 1.36 Angstrom of vacuum.", "repeats the card (4 values)"),
        ("Set the walltime to 1-2 h to queue faster.", "hours of its own: 1, 2"),
        ("Goldilocks recommends \u4e00 48 Ry cutoff.", None),
    ],
)
def test_the_judge_of_an_answer_to_a_review(content: str, verdict: str | None) -> None:
    # M2 has no language check; M7, the same judge with one, refuses the Han character (U+4E00) in the last answer.
    assert judged("M2", content) == verdict


def test_the_language_check_of_an_answer_to_a_review() -> None:
    assert judged("M7", "Goldilocks recommends a 48 Ry cutoff.") is None
    assert judged("M7", "Goldilocks recommends \u4e00 48 Ry cutoff.") == "answer is not in English"


def test_a_setting_judge_takes_only_the_users_values() -> None:
    assert judged("S1", "", ("dft_set", {"values": {"k_grid": [10, 10, 10]}})) is None
    assert judged("S1", "", ("dft_settings", {})) is None
    own = judged("S1", "", ("dft_set", {"values": {"k_grid": [10, 10, 10], "ecutwfc_ry": 60}}))
    assert own == "wrong arguments / called dft_set"
    assert judged("S8", "", ("dft_set", {"values": {"k_index": 8}})) == "called dft_set / called dft_set"
    assert judged("S8", "Which do you mean: a denser k-mesh or higher cutoffs?") is None


def test_step_of_keeps_broken_calls_for_the_judge() -> None:
    import s1_predecessor_cases as p
    from langchain_core.messages import AIMessage

    whole = AIMessage(content="", tool_calls=[{"name": "dft_review", "args": {}, "id": "a"}])
    broken = AIMessage(
        content="", invalid_tool_calls=[{"name": "dft_review", "args": "{oops", "id": "b", "error": None}]
    )
    assert r.step_of(whole).tool_calls == [{"name": "dft_review", "arguments": {}}]
    assert r.step_of(broken).tool_calls == [{"name": "dft_review", "arguments": "{oops"}]
    assert r.step_of(AIMessage(content="Hello.")).content == "Hello."
    judge = next(x for x in p.CASES if x.id == "M1").judge
    assert judge(r.step_of(whole)) is None
    assert judge(r.step_of(broken)) == "arguments are not JSON"


def test_summary() -> None:
    def call(experiment: str, variant: str, passed: bool, **detail: Any) -> dict[str, Any]:
        return {"experiment": experiment, "variant": variant, "passed": passed, "detail": detail}

    calls = [
        call("predecessor", "in68", True, in_68=True),
        call("catalogue", "short", True, recipe_ok=True, tools_ok=True, extra=1, distractors=[]),
        call("catalogue", "long", False, recipe_ok=False, tools_ok=True, extra=2, distractors=["md.classical"]),
        call("genius", "short", True, recipe_ok=True, tools_ok=True, extra=4, label="relax", calculation_picked=True),
        call("genius", "short", False, recipe_ok=True, tools_ok=False, extra=5, label="relax", calculation_picked=True),
        call("genius", "short", False, recipe_ok=True, tools_ok=False, extra=0, label="vc-relax"),
    ]
    assert r.summary(calls) == {
        "genius_by_label": {"relax": "1/2", "vc-relax": "0/1"},
        "genius_calculation_tool_picked": "2/3",
        "mean_extra_tools": {"catalogue-long": 2.0, "catalogue-short": 1.0, "genius-short": 3.0},
        "recipe_ok_and_tools_ok": {
            "catalogue-long": "recipe 0/1, tools 1/1",
            "catalogue-short": "recipe 1/1, tools 1/1",
            "genius-short": "recipe 3/3, tools 1/3",
        },
        "picks_with_a_distractor": 1,
    }
