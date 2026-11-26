"""Offline tests of S1's harness: statistics, argument checks, scoring, the capture proxy, and one experiment run
against a stand-in Ollama. No model is called."""

import json
import math
import sys
import threading
import urllib.error
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import s1_common as c
import s1_mechanics as m
import s1_report as r


def test_bootstrap_of_a_constant_is_that_constant() -> None:
    assert c.bootstrap([1.0] * 10) == (1.0, 1.0, 1.0)


def test_bootstrap_interval_holds_the_mean() -> None:
    mean, low, high = c.bootstrap([1.0, 0.0, 1.0, 1.0, 0.5])
    assert low <= mean <= high
    assert mean == pytest.approx(0.7)


def test_bootstrap_of_nothing_is_not_a_number() -> None:
    assert all(math.isnan(x) for x in c.bootstrap([]))


GRID = m.SCHEMAS["set_kpoints"]
SMEAR = m.SCHEMAS["set_smearing"]


@pytest.mark.parametrize(
    ("arguments", "schema", "expected"),
    [
        ({"grid": [6, 6, 6]}, GRID, []),
        ({}, GRID, ["missing:grid"]),
        ({"grid": [6, 6, 6], "units": "Ry"}, GRID, ["extra:units"]),
        ({"grid": "6x6x6"}, GRID, ["mistyped:grid"]),
        ({"grid": [6, 6]}, GRID, ["mistyped:grid"]),
        ({"grid": [6, 6, 6.5]}, GRID, ["mistyped:grid"]),
        ({"grid": [True, 6, 6]}, GRID, ["mistyped:grid"]),
        ({"kind": "cold", "degauss_ry": 0.02}, SMEAR, ["mistyped:kind"]),
        ({"kind": "gaussian", "degauss_ry": 1}, SMEAR, []),
        ("grid", GRID, ["not-an-object"]),
    ],
)
def test_classify(arguments: Any, schema: dict[str, Any], expected: list[str]) -> None:
    assert c.classify(arguments, schema) == expected


def test_same_compares_numbers_as_numbers_but_not_booleans() -> None:
    assert m.same({"a": 60, "b": [1, 2]}, {"a": 60.0, "b": [1, 2]})
    assert not m.same(True, 1)
    assert not m.same([1, 2], [1, 2, 3])
    assert not m.same({"a": None}, {"a": 0})


def call(experiment: str = "x") -> c.Call:
    return c.Call(experiment, "case", "raw", 0, None, "")


@pytest.mark.parametrize(
    ("parsed", "passed", "outcome"),
    [
        ({"task": "relax"}, True, "correct"),
        ({"task": "band"}, False, "wrong:band"),
        ({"task": "relax", "why": "x"}, False, "invalid"),
        ({"task": "magic"}, False, "invalid"),
        (None, False, "invalid"),
    ],
)
def test_score_choice(parsed: Any, passed: bool, outcome: str) -> None:
    result = call()
    m.score_choice(result, parsed, "relax")
    assert (result.passed, result.outcome) == (passed, outcome)


def test_score_settings_flat_and_nested() -> None:
    flat: m.Flat = (60, [6, 6, 6], None, None)
    good = call()
    m.score_settings(
        good,
        {"ecutwfc_ry": 60.0, "k_grid": [6, 6, 6], "smearing": None, "degauss_ry": None},
        m.FLAT_SCHEMA,
        m.flat_dict(flat),
    )
    assert (good.passed, good.outcome) == (True, "exact")
    invented = call()
    m.score_settings(
        invented,
        {"ecutwfc_ry": 60, "k_grid": [6, 6, 6], "smearing": "gaussian", "degauss_ry": 0.01},
        m.FLAT_SCHEMA,
        m.flat_dict(flat),
    )
    assert (invented.passed, invented.outcome) == (False, "wrong-values")
    nested_good = call()
    m.score_settings(nested_good, m.nested(flat), m.NESTED_SCHEMA, m.nested(flat))
    assert nested_good.passed
    nested_bad = call()
    m.score_settings(
        nested_bad, {"basis": {"ecutwfc_ry": 60}, "kpoints": {"grid": [6, 6, 6]}}, m.NESTED_SCHEMA, m.nested(flat)
    )
    assert nested_bad.outcome == "invalid"


def test_every_case_label_is_valid() -> None:
    assert all(label in m.TASKS for _, _, label in m.CHOICE_CASES)
    for _, _, flat in m.SETTINGS_CASES:
        assert m.valid_settings(m.flat_dict(flat), m.FLAT_SCHEMA)
        assert m.valid_settings(m.nested(flat), m.NESTED_SCHEMA)
    for _, _, tool, broken, _, expected in m.REWRITE_CASES:
        assert c.classify(broken, m.SCHEMAS[tool]), "a broken call must be broken"
        assert c.classify(expected, m.SCHEMAS[tool]) == [], "the expected rewrite must be valid"


def test_filler_is_repeatable_and_grows() -> None:
    assert m.filler_turns(2_000) == m.filler_turns(2_000)
    assert len(m.filler_text(8_000)) > 3 * len(m.filler_text(2_000))


class FakeOllama:
    """Answers /api/chat with one fixed message and /api/show, /api/tags, /api/version with small documents."""

    def __init__(self, content: str) -> None:
        reply = {"message": {"role": "assistant", "content": content}, "prompt_eval_count": 50, "eval_count": 5}
        documents = {
            "/api/chat": reply,
            "/api/version": {"version": "0.0-test"},
            "/api/show": {"details": {"quantization_level": "Q4_K_M"}, "model_info": {}},
            "/api/tags": {"models": [{"name": c.MODEL, "digest": "abc"}]},
        }

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

            def answer(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if self.path == "/api/missing":
                    self.send_response(404)
                    payload = b'{"error": "not found"}'
                else:
                    self.send_response(200)
                    payload = json.dumps(documents[self.path]).encode()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = answer

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def fake() -> Iterator[FakeOllama]:
    server = FakeOllama('{"task": "relax"}')
    yield server
    server.server.shutdown()


def test_the_proxy_records_a_summary_and_passes_answers_through(fake: FakeOllama, tmp_path: Path) -> None:
    log = tmp_path / "requests.jsonl"
    with c.CaptureProxy(fake.url, log) as proxy:
        proxy.tag = {"experiment": "t"}
        reply = c.raw_chat(proxy.url, [{"role": "user", "content": "hi"}], fmt={"type": "object"}, num_ctx=1234)
        assert reply["message"]["content"] == '{"task": "relax"}'
        assert proxy.last["options"]["num_ctx"] == 1234
        with pytest.raises(urllib.error.HTTPError) as error:
            c.get_json(proxy.url + "/api/missing")
        assert error.value.code == 404
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["tag"] == {"experiment": "t"}
    assert entry["summary"]["options"] == {"temperature": 0.7, "top_p": 0.8, "num_ctx": 1234}
    assert entry["summary"]["think"] is False
    assert entry["summary"]["format"] == {"schema_keys": ["type"]}
    assert "messages" not in json.dumps(entry["summary"]["keys"]) or entry["summary"]["messages"] == 1


def test_a_raw_choice_run_is_recorded_and_reported(fake: FakeOllama, tmp_path: Path) -> None:
    (tmp_path / "environment.json").write_text(json.dumps(c.environment(fake.url)))
    with c.CaptureProxy(fake.url, tmp_path / "requests.jsonl") as proxy:
        ctx = m.Context(proxy, c.Recorder(tmp_path / "calls.jsonl"), runs=2)
        m.choice(ctx, m.CHOICE_CASES[:3], clients=("raw",))
    calls = r.load(tmp_path)
    assert len(calls) == 6
    assert [x["outcome"] for x in calls[:3]] == ["wrong:relax", "correct", "wrong:relax"]
    assert all(x["detail"]["format_sent"] for x in calls)
    text = r.report(tmp_path)
    assert "| choice | - | raw | 6 | 3 | 33% |" in text
    assert '"ollama_version": "0.0-test"' in text


def test_an_exception_becomes_the_outcome(tmp_path: Path) -> None:
    with c.CaptureProxy("http://127.0.0.1:9", tmp_path / "requests.jsonl") as proxy:
        ctx = m.Context(proxy, c.Recorder(tmp_path / "calls.jsonl"), runs=1)
        m.choice(ctx, m.CHOICE_CASES[:1], clients=("raw",))
    recorded = json.loads((tmp_path / "calls.jsonl").read_text())
    assert recorded["passed"] is False
    assert recorded["outcome"].startswith("error:")
