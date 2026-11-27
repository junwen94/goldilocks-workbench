"""Offline tests of S1b: the GENIUS rule and checksum, the draft catalogue and its scoring, the joining of streamed
tool-call pieces, the proxy's pass-through, and the carried predecessor cases' shape. No model or network."""

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
# Made-up sentences in GENIUS's style, not GENIUS's own text.


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("Perform a geometry optimization of NaCl bulk with PBE and a 6x6x6 k-mesh.", "relaxation"),
        (
            "Relax the structure of a MoS2 monolayer using a smearing method and a mixing parameter for the SCF cycle.",
            "relaxation",
        ),
        ("Carry out a geometry refinement for ZnO in the P6_3mc space group.", "relaxation"),
        ("Optimize the GaN wurtzite structure with LDA.", "relaxation"),
        ("Relax the atomic positions of Si, without changing the lattice vectors, using PBE.", "relax"),
        ("Obtain the lattice constants of MgO through a structural optimization with PBEsol.", "vc-relax"),
        ("Do a geometry relaxation of TiO2 with the 'ibrav' 'cell_dofree' constrain.", "vc-relax"),
        ("Perform a single shot calculation for GaAs using all default parameters.", "scf_single_point"),
        ("Calculate the total magnetization of Fe with spin polarization and PBE0.", "scf_single_point"),
        ("Do the structural optimization of graphene varying the cutoff from 30 to 60 Ry, in steps of 10 Ry.", None),
        ("Compute the total magnetization of CrI3 using the following XC functionals: PBE, PBE0.", None),
        ("We want to compare the role of vdW corrections in the lattice parameters of BN.", None),
        ("Plot the phonon dispersion of diamond.", None),
    ],
)
def test_the_rule(request_text: str, expected: str | None) -> None:
    assert g.label(request_text) == expected


def test_studies_and_unplaced_requests_are_told_apart() -> None:
    assert g.rule_of("Optimize X varying the cutoff from 30 to 60 Ry.") == g.STUDY
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
