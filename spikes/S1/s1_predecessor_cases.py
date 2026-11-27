# Carried from stfc/goldilocks-agent tests/eval/tool_choice.py@ea757c7, with changes:
# - Re-targeted at S1's harness: kept are the fixture trimming, the chat-history builders, the judges and the 36
#   cases, in the source's order. Dropped: the litellm runner, the report, the command line and `Case.tags`. `Step`
#   holds only `tool_calls` and `content`. `Case.check` is renamed `Case.judge`. `Case` gains `in_68` (groups R, N,
#   D and M, the 19 cases of stfc/goldilocks-agent#68).
# - Translated to English: the user messages of R3, N3, D3, G2, G7 and S4, and the history that M7 and S4 share
#   (`review_turn_zh`, renamed `review_turn_job`). N3, M7 and G2 asked for an answer in Chinese; they now use the
#   `en` check, and `expect_answer` keeps only that check. G2's message is now the same as G1's.
# - The `en` check's Han-character test is written as code-point escapes (U+4E00 to U+9FFF, the source's range).
#   The hours pattern keeps only its English units (h, hrs, hours); the Chinese word for hours is dropped.
# - Tool arguments are checked with `s1_common.classify` instead of `jsonschema.validate`. classify checks the
#   top level: required, extra (unknown) and mistyped properties, enums, and array items and lengths. It does not
#   check other nested constraints. The eight WEB schemas have none besides find_in_databases' item enum, which
#   classify checks, so the verdicts agree. A failure now names classify's problems, not jsonschema's message.
#   Arguments may arrive as a dict as well as a JSON string.
# - Tool schemas come from predecessor/tools_*.json, not from the goldilocks_agent package. They were extracted
#   from the TOOL_SCHEMA literals of src/goldilocks_agent/tools/structure_search/tool.py and
#   src/goldilocks_agent/tools/dft_workbench/tool.py at ea757c7. In the second, the one non-literal node, the
#   module-level name `_FILE_NAME_PARAM`, was replaced by its literal value from the same file before evaluation.
#   SCHEMAS covers only the eight WEB tools.
# - Fixtures come from predecessor/fixtures. capabilities.json is not carried; its task ids are TASKS_AVAILABLE.
# - V1's PNG is drawn by a small pure-Python writer (zlib and struct) instead of Pillow: the same canvas, colours,
#   endpoints and width, with square line ends. Its pixels may differ from Pillow's.
# - S8's comment pointed to a section of the predecessor's design document, which is in Chinese; it now says what
#   that section says.
# - Typed for strict mypy and formatted by ruff.
"""The predecessor's tool-choice cases for S1b (workbench plan, "S1 qwen3.8 27B on Ollama").

Calls no model. Each case is a chat history, without the system message (`s1_predecessor_prompt.SYSTEM`), and a
judge of the next assistant step. The step is the expected one when it calls the expected tool with valid
arguments, or calls no tool. Free-form answers are not judged, except that:
- an answer comes in English, the language of every (translated) question;
- the image case names a number;
- a summary of tool results states no parameter values or walltime of its own and doesn't repeat the review card;
- the open-goal cases (G) switch the task the user asked for with dft_set;
- the setting cases (S) set exactly the values the user gave, and none of the model's own.

Tool results in the multi-step cases are built from goldilocks-core 0.3.0's recorded responses (the predecessor's
app/src/__fixtures__/core), trimmed the way the predecessor's app/src/dftWorkbench.ts trims them for the model.
"""

from __future__ import annotations

import base64
import json
import math
import re
import struct
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import s1_common as c

DATA = Path(__file__).resolve().parent / "predecessor"
FIXTURES = DATA / "fixtures"

# The task ids of app/src/__fixtures__/core/capabilities.json@ea757c7, in its order: the only part of that fixture
# the eval read (dft_open_structure's `tasks_available`).
TASKS_AVAILABLE = ("scf_single_point", "dos", "band", "relax", "vc-relax", "phonon", "relax-phonon", "vc-relax-phonon")


def _tools(name: str) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = json.loads((DATA / name).read_text())
    return tools


# The WEB profile's tools, in its order: (*STRUCTURE_SEARCH_TOOLS, *DFT_WORKBENCH_TOOLS).
TOOLS: list[dict[str, Any]] = [*_tools("tools_structure_search.json"), *_tools("tools_dft_workbench.json")]
SCHEMAS: dict[str, dict[str, Any]] = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}


def _fixture(name: str) -> dict[str, Any]:
    fixture: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())
    return fixture


SI_CIF: str = _fixture("structure")["structure_content"]

NACL_POSCAR = """NaCl
1.0
5.64 0.00 0.00
0.00 5.64 0.00
0.00 0.00 5.64
Na Cl
4 4
Direct
0.0 0.0 0.0
0.5 0.5 0.0
0.5 0.0 0.5
0.0 0.5 0.5
0.5 0.0 0.0
0.0 0.5 0.0
0.0 0.0 0.5
0.5 0.5 0.5
"""

GAAS_CIF = """# generated using pymatgen
data_GaAs
_symmetry_space_group_name_H-M   'P 1'
_cell_length_a   4.06599954
_cell_length_b   4.06599954
_cell_length_c   4.06599954
_cell_angle_alpha   60.00000000
_cell_angle_beta   60.00000000
_cell_angle_gamma   60.00000000
_symmetry_Int_Tables_number   1
_chemical_formula_structural   GaAs
_chemical_formula_sum   'Ga1 As1'
_cell_volume   47.53175000
_cell_formula_units_Z   1
loop_
 _symmetry_equiv_pos_site_id
 _symmetry_equiv_pos_as_xyz
  1  'x, y, z'
loop_
 _atom_site_type_symbol
 _atom_site_label
 _atom_site_symmetry_multiplicity
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 _atom_site_occupancy
  Ga  Ga0  1  0.00000000  0.00000000  0.00000000  1
  As  As1  1  0.25000000  0.25000000  0.25000000  1
"""


def _bcc_fe_cif(n: int) -> str:
    """A P1 CIF of an n x n x n bcc Fe supercell (2 n^3 sites), the size of a
    typical database entry for a supercell or a defect cell."""
    a = 2.87 * n
    lines = [
        "data_Fe",
        "_symmetry_space_group_name_H-M   'P 1'",
        *(f"_cell_length_{x}   {a:.8f}" for x in "abc"),
        *(f"_cell_angle_{x}   90.00000000" for x in ("alpha", "beta", "gamma")),
        "_symmetry_Int_Tables_number   1",
        "loop_",
        " _atom_site_type_symbol",
        " _atom_site_label",
        " _atom_site_fract_x",
        " _atom_site_fract_y",
        " _atom_site_fract_z",
        " _atom_site_occupancy",
    ]
    sites = [
        ((i + d) / n, (j + d) / n, (k + d) / n)
        for i in range(n)
        for j in range(n)
        for k in range(n)
        for d in (0.0, 0.5)
    ]
    lines += [f"  Fe  Fe{m}  {x:.8f}  {y:.8f}  {z:.8f}  1" for m, (x, y, z) in enumerate(sites)]
    return "\n".join(lines) + "\n"


FE128_CIF = _bcc_fe_cif(4)


def _attached(name: str, lang: str, content: str, text: str) -> str:
    """A user message as App.tsx's send() builds it with one attached file."""
    return f"{text}\n\n[Attached file: {name}]\n```{lang}\n{content}```"


def _calculation(task: str = "scf_single_point") -> dict[str, Any]:
    return {
        "code": "quantum_espresso",
        "task": task,
        "hpc": None,
        "overrides": {},
    }


def _set_result(changed: dict[str, Any]) -> dict[str, Any]:
    """dftWorkbench.ts's dft_set result: what it changed and the new review
    (the recorded one, with the task it set)."""
    review = _review_result("explain")
    review["calculation"] = _calculation(changed.get("task", "scf_single_point"))
    return {"changed": changed, **review}


def _open_result() -> dict[str, Any]:
    """dftWorkbench.ts's dft_open_structure result for the Si fixture."""
    s = _fixture("inspect")["structure"]
    lat = s["lattice"]
    return {
        "structure": {
            "formula": s["formula"],
            "reduced_formula": s["reduced_formula"],
            "site_count": s["site_count"],
            "periodicity": s["periodicity"],
            "lattice": {k: lat[k] for k in ("lengths_angstrom", "angles_degrees", "volume_angstrom3")},
            "partially_occupied_sites": 0,
        },
        "calculation": _calculation(),
        "cleared_overrides": [],
        "tasks_available": list(TASKS_AVAILABLE),
    }


def _review_result(name: str) -> dict[str, Any]:
    """dftWorkbench.ts's reviewForModel for a recorded /explain response."""
    explain = _fixture(name)
    records: dict[str, Any] = {}
    for key, r in explain["records"].items():
        if r["status"] == "resolved":
            records[key] = {"value": r["value"], "source": r["source"]} | (
                {"source_note": r["source_note"]} if r.get("source_note") else {}
            )
        else:
            records[key] = {"status": r["status"]} | {k: r[k] for k in ("reason", "blocked_by") if r.get(k)}
    return {
        "calculation": _calculation(),
        "records": records,
        "warnings": [{k: w[k] for k in ("record", "level", "message")} for w in explain["warnings"]],
        "blocking": [{k: b[k] for k in ("summary", "fields", "remedies")} for b in explain["blocking"]],
    }


def _blocked_bundle_error() -> str:
    findings = " ".join(
        f"{b['summary']} (resolved by setting {' or '.join(json.dumps(r) for r in b['remedies'])})"
        for b in _fixture("explain-blocked")["blocking"]
    )
    return (
        f"Input files can't be generated for the current settings: {findings} Ask the user before changing any setting."
    )


GAAS_SEARCH = {
    "query_formula": "GaAs",
    "groups": [
        {
            "formula": "GaAs",
            "spacegroup": "F-43m",
            "sources": ["Materials Project", "JARVIS"],
            "entries": [
                {
                    "formula": "GaAs",
                    "spacegroup": "F-43m",
                    "entry_id": "mp-2534",
                    "source": "Materials Project",
                    "url": "https://next-gen.materialsproject.org/materials/mp-2534",
                    "matched": True,
                    "score": None,
                    "band_gap": 0.19,
                    "band_gap_method": "PBE",
                    "energy_above_hull": 0.0,
                },
                {
                    "formula": "GaAs",
                    "spacegroup": "F-43m",
                    "entry_id": "JVASP-1174",
                    "source": "JARVIS",
                    "url": "https://www.ctcms.nist.gov/~knc6/jsmol/JVASP-1174.html",
                    "matched": True,
                    "score": None,
                    "band_gap": 0.75,
                    "band_gap_method": "OptB88vdW",
                },
            ],
            "band_gap": 0.19,
            "band_gap_method": "PBE",
            "energy_above_hull": 0.0,
            "property_sources": {
                "band_gap": "Materials Project",
                "energy_above_hull": "Materials Project",
            },
        },
        {
            "formula": "GaAs",
            "spacegroup": "P6_3mc",
            "sources": ["Materials Project"],
            "entries": [
                {
                    "formula": "GaAs",
                    "spacegroup": "P6_3mc",
                    "entry_id": "mp-8883",
                    "source": "Materials Project",
                    "url": "https://next-gen.materialsproject.org/materials/mp-8883",
                    "matched": True,
                    "score": None,
                    "energy_above_hull": 0.017,
                },
            ],
            "energy_above_hull": 0.017,
            "property_sources": {"energy_above_hull": "Materials Project"},
        },
    ],
    "ungrouped": [],
    "truncated_group_count": 0,
    "unavailable_properties": [],
    "errors": {},
}


def _png(width: int, height: int, pixels: bytes | bytearray) -> bytes:
    """An 8-bit RGB PNG of `pixels`: rows top to bottom, 3 bytes a pixel, no filtering."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    stride = 3 * width
    raw = b"".join(b"\x00" + bytes(pixels[y * stride : (y + 1) * stride]) for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # bit depth 8, colour type 2 (RGB)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _line(
    pixels: bytearray,
    size: int,
    start: tuple[int, int],
    end: tuple[int, int],
    colour: tuple[int, int, int],
    width: int,
) -> None:
    """A straight line `width` pixels wide with square ends, drawn into `pixels` (a square RGB image of `size`)."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    for y in range(max(0, min(y0, y1) - width), min(size, max(y0, y1) + width + 1)):
        for x in range(max(0, min(x0, x1) - width), min(size, max(x0, x1) + width + 1)):
            along = ((x - x0) * dx + (y - y0) * dy) / length
            across = abs((x - x0) * dy - (y - y0) * dx) / length
            if 0 <= along <= length and across <= width / 2:
                offset = 3 * (y * size + x)
                pixels[offset : offset + 3] = bytes(colour)


def _three_lines_png() -> str:
    """A 1:1 PNG with three coloured lines, as a data URL."""
    size = 512
    pixels = bytearray(b"\xff" * (3 * size * size))
    # Pillow's "red", "green" and "blue", as the source drew them.
    for i, colour in enumerate(((255, 0, 0), (0, 128, 0), (0, 0, 255))):
        y = 140 + i * 120
        _line(pixels, size, (60, y), (452, y - 80), colour, 8)
    return "data:image/png;base64," + base64.b64encode(_png(size, size, pixels)).decode()


# --- chat-history builders -------------------------------------------------


def user(content: Any) -> dict[str, Any]:
    return {"role": "user", "content": content}


def call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


def result(call_id: str, output: Any) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(output)}


def assistant(text: str) -> dict[str, Any]:
    return {"role": "assistant", "content": text}


# --- expectations ------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """One model reply. Each tool call is {"name": str, "arguments": dict | str}, a str if not valid JSON."""

    tool_calls: list[dict[str, Any]]
    content: str


Check = Callable[[Step], str | None]  # None = pass, else why it failed
ArgsOk = Callable[[dict[str, Any]], bool]

_NOT_JSON = object()


def _arguments(raw: Any) -> Any:
    """A tool call's arguments as a value: parsed if a string, `_NOT_JSON` if that fails."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw or "{}")
        except json.JSONDecodeError:
            return _NOT_JSON
    return raw


def expect_tool(name: str, args_ok: ArgsOk = lambda a: True, why: str = "") -> Check:
    def check(step: Step) -> str | None:
        if not step.tool_calls:
            return "no tool call"
        first = step.tool_calls[0]
        if first["name"] != name:
            return f"called {first['name']}"
        args = _arguments(first.get("arguments"))
        if args is _NOT_JSON:
            return "arguments are not JSON"
        problems = c.classify(args, SCHEMAS[name])
        if problems or not isinstance(args, dict):
            return f"arguments fail the schema: {', '.join(problems)[:80]}"
        return None if args_ok(args) else f"wrong arguments{': ' + why if why else ''}"

    return check


# A few common German words: a 2026-11-09 run answered an English question in
# German.
_GERMAN = re.compile(r"\b(ich|und|die|der|nicht|ist|Sie|für|nach)\b")
# Han ideographs, U+4E00 to U+9FFF, written as escapes: this repository is English only (AGENTS.md).
_HAN = re.compile(r"[\u4e00-\u9fff]")


def expect_answer(
    lang: Literal["en"] | None = None, contains: str | None = None, mentions: tuple[str, ...] = ()
) -> Check:
    """No tool call, a non-empty answer in ``lang`` that contains ``contains``
    and mentions every word in ``mentions`` (case-insensitive)."""

    def check(step: Step) -> str | None:
        if step.tool_calls:
            return f"called {step.tool_calls[0]['name']}"
        if not step.content.strip():
            return "empty answer"
        if lang == "en" and (_HAN.search(step.content) or len(_GERMAN.findall(step.content)) >= 3):
            return "answer is not in English"
        if contains is not None and contains not in step.content:
            return f"answer lacks {contains!r}"
        missing = [w for w in mentions if w.lower() not in step.content.lower()]
        return f"answer doesn't mention {', '.join(missing)}" if missing else None

    return check


def expect_one_of(*checks: Check) -> Check:
    """Passes if any of ``checks`` does."""

    def check(step: Step) -> str | None:
        failures = [c(step) for c in checks]
        return None if None in failures else " / ".join(f for f in failures if f is not None)

    return check


# Parameter values an answer states: a number with an energy or length unit,
# and a k-mesh written as 6x6x6 or (6, 6, 6).
_NUMBER = r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_STANDALONE_NUMBER = re.compile(rf"(?<![\w.]){_NUMBER}(?!\w)")  # not in a hash
_UNIT_VALUE = re.compile(rf"(?<![\w.])({_NUMBER})\s*(?:Ry|Rydberg|eV|meV|Å|Angstrom)\b")
_MESH = re.compile(
    r"(?<![\w.])(\d+)\s*[x\u00d7]\s*(\d+)\s*[x\u00d7]\s*(\d+)(?![\w.])"
    r"|[\[(]\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*[\])]"
)


def _numbers(value: Any) -> list[float]:
    """Every number in a JSON value, strings included."""
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return [n for item in value for n in _numbers(item)]
    return [float(n) for n in _STANDALONE_NUMBER.findall(str(value))]


def _meshes(value: Any) -> set[tuple[int, ...]]:
    """Every list of three integers in a JSON value."""
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        return set()
    own = (
        {tuple(value)}
        if len(value) == 3 and all(isinstance(i, int) and not isinstance(i, bool) for i in value)
        else set()
    )
    return own.union(*(_meshes(item) for item in value))


def _shown_as(text: str, known: float) -> bool:
    """Whether ``text`` is ``known`` written to the precision ``text`` shows."""
    mantissa, _, exponent = text.lower().partition("e")
    step = 10.0 ** (int(exponent or 0) - len(mantissa.partition(".")[2]))
    return abs(float(text) - known) <= step / 2 + 1e-12 * abs(known)


def expect_values_from(messages: list[dict[str, Any]]) -> Check:
    """#72: every parameter value the answer states comes from the tool
    results or the user's messages in ``messages``: none of the model's own."""
    tool_outputs = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
    user_text = [m["content"] for m in messages if m["role"] == "user"]
    # Unsigned: the patterns above keep only the digits of "-2.10 eV".
    known = [abs(n) for n in _numbers(tool_outputs) + _numbers(user_text)]
    meshes = _meshes(tool_outputs)

    def check(step: Step) -> str | None:
        own: list[str] = [v for v in _UNIT_VALUE.findall(step.content) if not any(_shown_as(v, k) for k in known)]
        for match in _MESH.finditer(step.content):
            mesh = tuple(int(g) for g in match.groups() if g is not None)
            if mesh not in meshes:
                own.append("x".join(map(str, mesh)))
        return f"values of its own: {', '.join(own)}" if own else None

    return check


# A Markdown table's header separator row, e.g. "|---|:---:|".
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", re.M)


def expect_no_card_repeat(max_values: int = 3) -> Check:
    """The answer to a review doesn't repeat the review card above it (#74):
    no Markdown table, and at most ``max_values`` parameter values, enough to
    explain core's warnings, which name values themselves. On 2026-11-10
    qwen restated the card as a table on the web, and as a list naming 4-5
    values in this eval; asked not to, it named 2-3, in its warnings."""

    def check(step: Step) -> str | None:
        if _TABLE_RULE.search(step.content):
            return "repeats the card as a table"
        named = values_mentioned(step.content)
        return f"repeats the card ({named} values)" if named > max_values else None

    return check


# Hours, single or a range ("168h", "1-2 hours", en dash too).
_HOURS = re.compile(rf"(?<![\w.])({_NUMBER})(?:\s*[-\u2013~]\s*({_NUMBER}))?\s*(?:h|hrs?|hours?)(?![a-zA-Z])")


def expect_no_hours_of_its_own(messages: list[dict[str, Any]]) -> Check:
    """No walltime of the model's own: every number of hours the answer
    states appears as hours in the tool results (core's 168h ceiling), the
    usual slip being "set it to 1-2 h" (2026-11-11)."""
    tool_text = " ".join(m["content"] for m in messages if m["role"] == "tool")
    known = {float(n) for match in _HOURS.finditer(tool_text) for n in match.groups() if n}
    known |= {float(n) for n in re.findall(r'"walltime_h":\s*(\d+(?:\.\d+)?)', tool_text)}

    def check(step: Step) -> str | None:
        own = sorted(
            {n for match in _HOURS.finditer(step.content) for n in match.groups() if n and float(n) not in known}
        )
        return f"hours of its own: {', '.join(own)}" if own else None

    return check


def values_mentioned(content: str) -> int:
    """How many parameter values (numbers with units, k-meshes) an answer
    names. #74 shows a review's values in a card; the report prints this for
    M2 to show how much of the card the answer repeats;
    ``expect_no_card_repeat`` fails an answer that names more than three."""
    return len(set(_UNIT_VALUE.findall(content)) | {m.group(0) for m in _MESH.finditer(content)})


def expect_all(*checks: Check) -> Check:
    def check(step: Step) -> str | None:
        return next((f for c in checks if (f := c(step)) is not None), None)

    return check


def _names(expected: str) -> ArgsOk:
    """Whether dft_open_structure names the chat's file ``expected`` (#73:
    it takes the file's name; the browser reads the file)."""
    return lambda a: bool(a.get("file_name") == expected)


def _formula(expected: str) -> ArgsOk:
    return lambda a: bool(a.get("formula", "").replace(" ", "") == expected)


PHONON_TASKS = ("phonon", "relax-phonon", "vc-relax-phonon")


def _values(expected: dict[str, Any], optional: dict[str, Any] | None = None) -> ArgsOk:
    """Whether dft_set sets exactly ``expected`` (each a value, or a check
    of one), plus any of ``optional``, and nothing the user didn't ask for."""
    extra = optional or {}

    def ok(check: Any, value: Any) -> bool:
        return bool(check(value)) if callable(check) else bool(value == check)

    def args_ok(a: dict[str, Any]) -> bool:
        values = a.get("values")
        if not isinstance(values, dict) or not set(expected) <= set(values):
            return False
        return all(ok(expected[k] if k in expected else extra.get(k, object()), v) for k, v in values.items())

    return args_ok


def _task(*expected: str) -> ArgsOk:
    """Whether dft_set switches the task to one of ``expected`` and sets
    nothing else."""
    return _values({"task": lambda t: t in expected})


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    in_68: bool  # one of the 19 cases of stfc/goldilocks-agent#68: groups R, N, D and M
    messages: list[dict[str, Any]]
    judge: Check


def _case(id: str, category: str, messages: list[dict[str, Any]], judge: Check) -> Case:
    return Case(id, category, id[0] in "RNDM", messages, judge)


def cases() -> list[Case]:
    si_review = "What parameters would Goldilocks recommend for an SCF calculation on this structure?"
    si_open_args = {"file_name": "Si.cif"}
    open_turn = [
        user(_attached("Si.cif", "cif", SI_CIF, si_review)),
        call("dft_open_structure", si_open_args, "c1"),
        result("c1", _open_result()),
    ]
    review_turn = [
        *open_turn,
        call("dft_review", {}, "c2"),
        result("c2", _review_result("explain")),
    ]
    # M2 asking about the job too (in Chinese at ea757c7, translated here): on the web (2026-11-11) a Chinese review
    # answer told the user to set walltime to "1-2h".
    review_turn_job = [
        user(
            _attached(
                "Si.cif",
                "cif",
                SI_CIF,
                "This is silicon. I want to run an SCF calculation. Please look at the recommended parameters for me. "
                "Especially how the job should be set up.",
            )
        ),
        call("dft_open_structure", si_open_args, "c1"),
        result("c1", _open_result()),
        call("dft_review", {}, "c2"),
        result("c2", _review_result("explain")),
    ]
    band_open = [
        user(
            _attached(
                "Si.cif",
                "cif",
                SI_CIF,
                "I want to calculate the band structure of this.",
            )
        ),
        call("dft_open_structure", si_open_args, "c1"),
        result("c1", _open_result()),
    ]
    blocked_turn = [
        *open_turn,
        call("dft_review", {}, "c2"),
        result("c2", _review_result("explain-blocked")),
        assistant(
            "One setting needs a decision before input files can be generated: isolation=slab doesn't suit this cell."
        ),
        user("Just generate the input files."),
        call("dft_download_bundle", {}, "c3"),
        result("c3", {"error": _blocked_bundle_error()}),
    ]
    gaas_search = [
        user("Find me a starting structure for GaAs in the databases, then set up an SCF calculation with it."),
        call("find_in_databases", {"formula": "GaAs"}, "s1"),
        result("s1", GAAS_SEARCH),
        assistant(
            "I found two GaAs structures: zinc blende (F-43m, Materials Project "
            "mp-2534 and JARVIS JVASP-1174, on the convex hull) and wurtzite "
            "(P6_3mc, mp-8883, 17 meV/atom above the hull). "
            "Which one should I use?"
        ),
        user("Use the Materials Project zinc blende one, mp-2534."),
    ]
    return [
        # routing: database search
        _case(
            "R1",
            "search",
            [user("Is there already computed data for GaAs in the materials databases?")],
            expect_tool("find_in_databases", _formula("GaAs")),
        ),
        _case(
            "R2",
            "search",
            [user("Look up the band gap of TiO2 in the databases.")],
            expect_tool(
                "find_in_databases",
                lambda a: _formula("TiO2")(a) and "electronic" in a.get("properties", ["electronic"]),
            ),
        ),
        _case(
            "R3",
            "search",
            [user("Help me check the materials databases for any computed magnetic data on Fe2O3.")],
            expect_tool("find_in_databases", _formula("Fe2O3")),
        ),
        _case(
            "R4",
            "search",
            [user("I need a starting structure for wurtzite ZnO to run a calculation on.")],
            expect_tool("find_in_databases", _formula("ZnO")),
        ),
        # no tool
        _case(
            "N1",
            "answer",
            [user("What does smearing do in a DFT calculation of a metal?")],
            expect_answer(),
        ),
        _case(
            "N2",
            "answer",
            [
                user(
                    "I'm writing a paper about NaCl. Can you explain in two "
                    "sentences what a plane-wave cutoff energy is?"
                )
            ],
            expect_answer(),
        ),
        _case(
            "N3",
            "answer",
            [user("Hello, what can you help me with?")],
            expect_answer(lang="en"),
        ),
        _case("N4", "answer", [user("Thanks, that's all for now!")], expect_answer()),
        # opening an attached structure
        _case(
            "D1",
            "dft",
            [
                user(
                    _attached(
                        "Si.cif",
                        "cif",
                        SI_CIF,
                        "Set up an SCF calculation for this structure.",
                    )
                )
            ],
            expect_tool(
                "dft_open_structure",
                _names("Si.cif"),
                "not the attached file's name",
            ),
        ),
        _case(
            "D2",
            "dft",
            [user(_attached("POSCAR", "text", NACL_POSCAR, "Open this in the DFT workbench."))],
            expect_tool(
                "dft_open_structure",
                _names("POSCAR"),
                "not the attached file's name",
            ),
        ),
        _case(
            "D3",
            "dft",
            [
                user(
                    _attached(
                        "Si.cif",
                        "cif",
                        SI_CIF,
                        "Generate the Quantum ESPRESSO input files for this structure for me.",
                    )
                )
            ],
            expect_tool(
                "dft_open_structure",
                _names("Si.cif"),
                "not the attached file's name",
            ),
        ),
        _case(
            "D4",
            "dft",
            [
                user(
                    _attached(
                        "Fe_supercell.cif",
                        "cif",
                        FE128_CIF,
                        "Set up an SCF calculation for this supercell.",
                    )
                )
            ],
            expect_tool(
                "dft_open_structure",
                _names("Fe_supercell.cif"),
                "not the attached file's name",
            ),
        ),
        # multi-step
        _case("M1", "multi", open_turn, expect_tool("dft_review")),
        _case(
            "M2",
            "multi",
            review_turn,
            expect_all(
                expect_answer(),
                expect_values_from(review_turn),
                expect_no_card_repeat(),
                expect_no_hours_of_its_own(review_turn),
            ),
        ),
        _case(
            "M3",
            "multi",
            [
                *review_turn,
                assistant(
                    "Goldilocks recommends a 48 Ry wavefunction cutoff, 192 Ry for "
                    "the density, and a Monkhorst-Pack k-point grid from its "
                    "k-distance model, with PseudoDojo PBEsol pseudopotentials."
                ),
                user("Great, generate the input files."),
            ],
            expect_tool("dft_download_bundle"),
        ),
        _case(
            "M4",
            "multi",
            blocked_turn,
            expect_all(
                expect_answer(),
                expect_values_from(blocked_turn),
                expect_no_card_repeat(),
                expect_no_hours_of_its_own(blocked_turn),
            ),
        ),
        _case(
            "M5",
            "multi",
            gaas_search,
            expect_tool(
                "get_structure",
                lambda a: a["source"] == "Materials Project" and a["entry_id"] == "mp-2534",
            ),
        ),
        _case(
            "M6",
            "multi",
            [
                *gaas_search,
                call(
                    "get_structure",
                    {"source": "Materials Project", "entry_id": "mp-2534"},
                    "s2",
                ),
                result(
                    "s2",
                    {
                        "filename": "GaAs_mp-2534.cif",
                        "content": GAAS_CIF,
                        "format": "cif",
                    },
                ),
            ],
            expect_tool(
                "dft_open_structure",
                _names("GaAs_mp-2534.cif"),
                "not the fetched file's name",
            ),
        ),
        _case(
            "M7",
            "multi",
            review_turn_job,
            expect_all(
                expect_answer(lang="en"),
                expect_values_from(review_turn_job),
                expect_no_card_repeat(),
                expect_no_hours_of_its_own(review_turn_job),
            ),
        ),
        # open-ended goals (2026-11-09 browser runs: "I want to study NaCl")
        _case(
            "G1",
            "goal",
            [user("I want to study NaCl")],
            expect_one_of(
                expect_tool("find_in_databases", _formula("NaCl")),
                expect_answer(lang="en"),
            ),
        ),
        _case(
            "G2",
            "goal",
            [user("I want to study NaCl")],
            expect_one_of(
                expect_tool("find_in_databases", _formula("NaCl")),
                expect_answer(lang="en"),
            ),
        ),
        # dft_set switches the task the user names. Switching straight away
        # is best; reviewing the open SCF first is fine if the step after it
        # switches (G5).
        _case(
            "G3",
            "goal",
            band_open,
            expect_one_of(
                expect_tool("dft_set", _task("band")),
                expect_tool("dft_review"),
            ),
        ),
        _case(
            "G5",
            "goal",
            [
                *band_open,
                call("dft_review", {}, "c2"),
                result("c2", _review_result("explain")),
            ],
            expect_tool("dft_set", _task("band")),
        ),
        # Switched: dft_set returned the new review. Say what needs
        # attention; don't generate files unasked (#81).
        _case(
            "G4",
            "goal",
            [
                *band_open,
                call("dft_set", {"values": {"task": "band"}}, "c2"),
                result("c2", _set_result({"task": "band"})),
            ],
            expect_one_of(expect_answer(lang="en"), expect_tool("dft_review")),
        ),
        # 2026-11-12 on the web: after an SCF review the user typed "PHONON",
        # and the model told them to switch the task in the panel themselves.
        _case(
            "G6",
            "goal",
            [
                *review_turn,
                assistant(
                    "Nothing blocks generation; the k-point mesh comes from an ML "
                    "model that hasn't been externally validated. The task is a "
                    "single-point SCF. Should I generate the input files, or "
                    "switch to another calculation (band structure, DOS, relax)?"
                ),
                user("PHONON"),
            ],
            expect_tool("dft_set", _task(*PHONON_TASKS)),
        ),
        _case(
            "G7",
            "goal",
            [
                user(_attached("Si.cif", "cif", SI_CIF, "I want to calculate the phonon spectrum of this structure.")),
                call("dft_open_structure", si_open_args, "c1"),
                result("c1", _open_result()),
            ],
            expect_tool("dft_set", _task(*PHONON_TASKS)),
        ),
        # settings the user gives (dft_set) -- or looks up first
        # (dft_settings), since the key isn't always guessable
        _case(
            "S1",
            "set",
            [*review_turn, user("Change the k-point mesh to 10x10x10.")],
            expect_one_of(
                expect_tool("dft_set", _values({"k_grid": [10, 10, 10]})),
                expect_tool("dft_settings"),
            ),
        ),
        _case(
            "S2",
            "set",
            [*review_turn, user("Set the walltime to 24 hours.")],
            expect_one_of(
                expect_tool("dft_set", _values({"walltime_h": 24})),
                expect_tool("dft_settings"),
            ),
        ),
        _case(
            "S3",
            "set",
            [*review_turn, user("Use cold smearing.")],
            expect_one_of(
                expect_tool(
                    "dft_set",
                    _values({"smearing_type": "cold"}, {"occupations": "smearing"}),
                ),
                expect_tool("dft_settings"),
            ),
        ),
        _case(
            "S4",
            "set",
            [*review_turn_job, user("Set the wavefunction cutoff energy to 80 Ry.")],
            expect_one_of(
                expect_tool("dft_set", _values({"ecutwfc_ry": 80})),
                expect_tool("dft_settings"),
            ),
        ),
        _case(
            "S5",
            "set",
            [
                *review_turn,
                user("Change the k-point mesh to 10x10x10."),
                call("dft_set", {"values": {"k_grid": [10, 10, 10]}}, "c3"),
                result("c3", _set_result({"k_grid": [10, 10, 10]})),
                assistant("The k-point mesh is now 10x10x10 (your setting)."),
                user("Actually, put the k-points back to automatic."),
            ],
            expect_tool("dft_set", _values({"k_grid": None})),
        ),
        _case(
            "S6",
            "set",
            [*review_turn, user("Use PBE instead.")],
            expect_tool("dft_set", _values({"functional": "PBE"})),
        ),
        # A task and a setting in one call, the setting checked against it.
        _case(
            "S7",
            "set",
            [
                user(
                    _attached(
                        "Si.cif",
                        "cif",
                        SI_CIF,
                        "Set up phonons for this with a 4x4x4 q-point mesh.",
                    )
                ),
                call("dft_open_structure", si_open_args, "c1"),
                result("c1", _open_result()),
            ],
            expect_tool(
                "dft_set",
                _values({"task": lambda t: t in PHONON_TASKS, "q_grid": [4, 4, 4]}),
            ),
        ),
        # ...or the task first: then the setting, now that it applies.
        _case(
            "S7b",
            "set",
            [
                user(
                    _attached(
                        "Si.cif",
                        "cif",
                        SI_CIF,
                        "Set up phonons for this with a 4x4x4 q-point mesh.",
                    )
                ),
                call("dft_open_structure", si_open_args, "c1"),
                result("c1", _open_result()),
                call("dft_set", {"values": {"task": "phonon"}}, "c2"),
                result("c2", _set_result({"task": "phonon"})),
            ],
            expect_one_of(
                expect_tool("dft_set", _values({"q_grid": [4, 4, 4]})),
                expect_tool("dft_settings"),
            ),
        ),
        # No value given: the model mustn't choose one. Turning "more accurate" into a value would be the model's
        # choice, not the user's (a "suggest", not a "relay", in the predecessor's design).
        _case(
            "S8",
            "set",
            [*review_turn, user("Make the calculation more accurate.")],
            expect_one_of(expect_answer(lang="en"), expect_tool("dft_settings")),
        ),
        # image attached in the composer (App.tsx sends it as an image_url part)
        _case(
            "V1",
            "vision",
            [
                user(
                    [
                        {
                            "type": "text",
                            "text": "How many lines are drawn in this image? Reply with only the number.",
                        },
                        {"type": "image_url", "image_url": {"url": _three_lines_png()}},
                    ]
                )
            ],
            expect_answer(contains="3"),
        ),
    ]


CASES: list[Case] = cases()
