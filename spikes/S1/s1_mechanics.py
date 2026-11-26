"""S1a, the mechanics of qwen3.8 27B on Ollama (workbench plan, "S1"; changes/2026-11-25-workbench/spikes/).

Nine experiments, each case run --runs times, every call through a capture proxy:
  options      temperature, top_p, num_ctx and thinking-off reach Ollama; the defaults when they are left out
  choice       a schema-constrained choice among goldilocks-dft's tasks: ChatLiteLLM, ChatOllama, raw `format`
  tool_choice  a named tool, required and none, and auto as the baseline, through both LangChain clients
  tools_format tools and `format` in one request: what comes back
  parallel     two independent tool calls in one answer, streamed and not, through both LangChain clients
  schemas      DFT settings extracted into a flat and a nested schema
  schemas_plain  the same, without the prompt's hint that names a smearing
  rewrite      one rewrite of a broken tool call from a typed error list
  degradation  choice and extraction with the history padded towards 2K, 8K, 16K and 24K tokens (3 characters
               a token; Ollama counted 2.9K, 10.5K, 20.7K and 30.7K in S1a's run)

The cases and their labels are written for S1; the tools are stand-ins, not the Workbench's.
Usage: uv run python spikes/S1/s1_mechanics.py --out spikes/S1/runs/<name> [--runs 3] [--only choice,schemas]
"""

import argparse
import json
import random
import sys
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import s1_common as c

# goldilocks-core's tasks (junwen94/goldilocks-core a6d4c19, src/goldilocks_core/plan.py:77-112).
TASKS = ["scf_single_point", "relax", "vc-relax", "band", "dos", "phonon", "relax-phonon", "vc-relax-phonon"]
CHOICE_SCHEMA: dict[str, Any] = {
    "title": "TaskChoice",
    "description": "The goldilocks-dft calculation task the request needs.",
    "type": "object",
    "properties": {"task": {"type": "string", "enum": TASKS}},
    "required": ["task"],
    "additionalProperties": False,
}
CHOICE_SYSTEM = (
    "You choose the goldilocks-dft calculation task that a user's request needs. The tasks: scf_single_point (one "
    "self-consistent calculation at fixed geometry), relax (atoms move, cell fixed), vc-relax (atoms and cell "
    "move), band (band structure), dos (density of states), phonon (phonons at the given geometry), relax-phonon "
    "and vc-relax-phonon (a relaxation, then phonons). Answer in JSON."
)
CHOICE_CASES = [
    ("c01", "What is the total energy of bulk silicon at its experimental lattice constant?", "scf_single_point"),
    ("c02", "Find the equilibrium atomic positions of this slab, keeping the cell fixed.", "relax"),
    ("c03", "Optimise both the lattice parameters and the atomic positions of GaAs.", "vc-relax"),
    ("c04", "Plot the electronic band structure of graphene along the high-symmetry lines.", "band"),
    ("c05", "I need the density of states of copper.", "dos"),
    ("c06", "Compute the phonon dispersion of NaCl at its current geometry.", "phonon"),
    ("c07", "Relax the atoms of the MoS2 monolayer first, then calculate its phonons.", "relax-phonon"),
    ("c08", "Fully relax the cell of MgO, then give me its phonon density of states.", "vc-relax-phonon"),
    ("c09", "Just a single-point SCF for this structure, please.", "scf_single_point"),
    ("c10", "How do the bands of TiO2 look near the Fermi level?", "band"),
    ("c11", "Get me the projected density of states of iron.", "dos"),
    ("c12", "The forces on the atoms are large; minimise them without changing the cell.", "relax"),
    ("c13", "Find the zero-pressure volume of aluminium together with its atomic positions.", "vc-relax"),
    ("c14", "Is this structure dynamically stable as it is? Check for imaginary modes.", "phonon"),
    ("c15", "Compute the ground-state energy of an isolated water molecule in a box.", "scf_single_point"),
    ("c16", "Relax the internal coordinates of BaTiO3, then compute its vibrational spectrum.", "relax-phonon"),
    ("c17", "I want the electronic band dispersion of hexagonal boron nitride.", "band"),
    ("c18", "What does the electronic density of states of nickel oxide look like?", "dos"),
    ("c19", "Optimise the unit cell of diamond at zero pressure, then compute its phonons.", "vc-relax-phonon"),
    ("c20", "Compute the vibrational frequencies of silicon across the Brillouin zone.", "phonon"),
]

SMEARING = ["gaussian", "methfessel-paxton", "marzari-vanderbilt", "fermi-dirac"]
NUMBER_OR_NULL = {"type": ["number", "null"]}
GRID_OR_NULL = {"type": ["array", "null"], "items": {"type": "integer"}, "minItems": 3, "maxItems": 3}
KIND_OR_NULL = {"type": ["string", "null"], "enum": [*SMEARING, None]}
FLAT_SCHEMA: dict[str, Any] = {
    "title": "Settings",
    "description": "The DFT settings the user states; null for any the user does not state.",
    "type": "object",
    "properties": {
        "ecutwfc_ry": NUMBER_OR_NULL,
        "k_grid": GRID_OR_NULL,
        "smearing": KIND_OR_NULL,
        "degauss_ry": NUMBER_OR_NULL,
    },
    "required": ["ecutwfc_ry", "k_grid", "smearing", "degauss_ry"],
    "additionalProperties": False,
}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


NESTED_SCHEMA: dict[str, Any] = {
    "title": "Settings",
    "description": "The DFT settings the user states; null for any the user does not state.",
    **_object(
        {
            "basis": _object({"ecutwfc_ry": NUMBER_OR_NULL}),
            "kpoints": _object({"grid": GRID_OR_NULL}),
            "smearing": _object({"kind": KIND_OR_NULL, "degauss_ry": NUMBER_OR_NULL}),
        }
    ),
}
SETTINGS_SYSTEM = (
    "Extract the DFT settings the user states. Use null for any setting the user does not state, and never add a "
    "value of your own. Cold smearing is marzari-vanderbilt. Answer in JSON."
)
# The same without the hint that names a smearing: in the first full run, every invented value was the one the hint
# names, so `schemas_plain` measures how much of that came from the prompt.
SETTINGS_SYSTEM_PLAIN = SETTINGS_SYSTEM.replace(" Cold smearing is marzari-vanderbilt.", "")
Flat = tuple[float | None, list[int] | None, str | None, float | None]
SETTINGS_CASES: list[tuple[str, str, Flat]] = [
    ("s01", "Use a plane-wave cutoff of 60 Ry and a 6x6x6 k-point grid.", (60, [6, 6, 6], None, None)),
    ("s02", "Set Marzari-Vanderbilt smearing with a width of 0.02 Ry.", (None, None, "marzari-vanderbilt", 0.02)),
    ("s03", "Cutoff 45 Ry, please.", (45, None, None, None)),
    ("s04", "k-mesh 4x4x1 and Gaussian smearing of 0.01 Ry.", (None, [4, 4, 1], "gaussian", 0.01)),
    (
        "s05",
        "I want 80 Ry for the wavefunctions, a 12 by 12 by 12 grid, and Fermi-Dirac smearing at 0.005 Ry.",
        (80, [12, 12, 12], "fermi-dirac", 0.005),
    ),
    ("s06", "Use Methfessel-Paxton smearing.", (None, None, "methfessel-paxton", None)),
    ("s07", "Make the k-point grid 3x3x3.", (None, [3, 3, 3], None, None)),
    ("s08", "Cold smearing, 0.015 Ry, with a 50 Ry cutoff.", (50, None, "marzari-vanderbilt", 0.015)),
    ("s09", "A grid of 8 x 8 x 4 k-points and ecutwfc 70 Ry.", (70, [8, 8, 4], None, None)),
    ("s10", "Smearing width 0.03 Ry, Gaussian.", (None, None, "gaussian", 0.03)),
    ("s11", "Please set the wavefunction cutoff to 35 Ry and degauss to 0.01 Ry.", (35, None, None, 0.01)),
    ("s12", "Use a 10x10x1 mesh for this slab.", (None, [10, 10, 1], None, None)),
    (
        "s13",
        "Wavefunction cutoff of 55 Ry, 5x5x5 k-points, Methfessel-Paxton smearing with 0.02 Ry.",
        (55, [5, 5, 5], "methfessel-paxton", 0.02),
    ),
    ("s14", "Fermi-Dirac occupations with a smearing of 0.001 Ry.", (None, None, "fermi-dirac", 0.001)),
    ("s15", "Raise the cutoff to 90 Ry.", (90, None, None, None)),
]


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


SEARCH = _tool(
    "search_structures",
    "Search databases for computed structures of one chemical formula.",
    {"formula": {"type": "string", "description": "A chemical formula, such as GaAs."}},
)
EXPLAIN = _tool(
    "explain_setting",
    "Explain what one DFT setting does.",
    {"name": {"type": "string", "description": "The setting's name, such as smearing."}},
)
KPOINTS = _tool(
    "set_kpoints",
    "Set the k-point grid of the calculation.",
    {"grid": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3}},
)
CUTOFF = _tool("set_cutoff", "Set the wavefunction cutoff in Ry.", {"ecutwfc_ry": {"type": "number"}})
SMEAR = _tool(
    "set_smearing",
    "Set the smearing and its width in Ry.",
    {"kind": {"type": "string", "enum": SMEARING}, "degauss_ry": {"type": "number"}},
)
TOOLS = [SEARCH, EXPLAIN, KPOINTS]
REWRITE_TOOLS = [SEARCH, KPOINTS, CUTOFF, SMEAR]
SCHEMAS = {t["function"]["name"]: t["function"]["parameters"] for t in [*TOOLS, *REWRITE_TOOLS]}
TOOL_SYSTEM = "You help set up DFT calculations. Use a tool when one fits the request; otherwise answer briefly."

# (id, prompt, the tool it naturally calls or None, the tool forced in "named" mode)
TOOL_CHOICE_CASES = [
    ("t01", "Hello! What can you help me with?", None, "search_structures"),
    ("t02", "Thanks, that is all for today.", None, "explain_setting"),
    ("t03", "In one sentence, what is a pseudopotential?", None, "search_structures"),
    ("t04", "Which DFT codes do you support?", None, "set_kpoints"),
    ("t05", "Good morning.", None, "explain_setting"),
    ("t06", "Search the databases for structures of GaAs.", "search_structures", "explain_setting"),
    ("t07", "What does the smearing setting do?", "explain_setting", "search_structures"),
    ("t08", "Set the k-point grid to 8x8x8.", "set_kpoints", "explain_setting"),
    ("t09", "Find computed structures of ZnO for me.", "search_structures", "set_kpoints"),
    ("t10", "Use a 4 by 4 by 1 k-mesh.", "set_kpoints", "search_structures"),
]
PARALLEL_CASES = [
    ("p01", "Search the databases for GaAs and for TiO2.", {"GaAs", "TiO2"}),
    ("p02", "Look up computed structures of both ZnO and MgO.", {"ZnO", "MgO"}),
    ("p03", "I need database entries for NaCl and KCl; please search both.", {"NaCl", "KCl"}),
    ("p04", "Find structures for Si and for Ge.", {"Si", "Ge"}),
    ("p05", "Search for Fe2O3 and also for Fe3O4.", {"Fe2O3", "Fe3O4"}),
    ("p06", "Can you check the databases for MoS2 and WS2?", {"MoS2", "WS2"}),
    ("p07", "Get me candidate structures of BaTiO3 and SrTiO3.", {"BaTiO3", "SrTiO3"}),
    ("p08", "Search two formulas: CsPbI3 and CsPbBr3.", {"CsPbI3", "CsPbBr3"}),
]
# (id, request, tool, broken arguments, problems, the arguments a correct rewrite sends)
REWRITE_CASES: list[tuple[str, str, str, dict[str, Any], list[dict[str, str]], dict[str, Any]]] = [
    (
        "r01",
        "Set the k-point grid to 6x6x6.",
        "set_kpoints",
        {"grid": "6x6x6"},
        [{"field": "grid", "problem": "expected an array of 3 integers, got a string"}],
        {"grid": [6, 6, 6]},
    ),
    (
        "r02",
        "Use a 6 by 6 by 6 k-mesh.",
        "set_kpoints",
        {"kgrid": [6, 6, 6]},
        [
            {"field": "kgrid", "problem": "unknown argument; did you mean grid?"},
            {"field": "grid", "problem": "required argument missing"},
        ],
        {"grid": [6, 6, 6]},
    ),
    (
        "r03",
        "Set the cutoff to 60 Ry.",
        "set_cutoff",
        {"ecutwfc": 60},
        [
            {"field": "ecutwfc", "problem": "unknown argument; did you mean ecutwfc_ry?"},
            {"field": "ecutwfc_ry", "problem": "required argument missing"},
        ],
        {"ecutwfc_ry": 60},
    ),
    (
        "r04",
        "Cutoff of 60 Ry.",
        "set_cutoff",
        {"ecutwfc_ry": "60 Ry"},
        [{"field": "ecutwfc_ry", "problem": "expected a number in Ry, got a string"}],
        {"ecutwfc_ry": 60},
    ),
    (
        "r05",
        "Use cold smearing with 0.02 Ry.",
        "set_smearing",
        {"kind": "cold", "degauss_ry": 0.02},
        [
            {
                "field": "kind",
                "problem": "'cold' is not one of gaussian, methfessel-paxton, marzari-vanderbilt, "
                "fermi-dirac; did you mean marzari-vanderbilt?",
            }
        ],
        {"kind": "marzari-vanderbilt", "degauss_ry": 0.02},
    ),
    (
        "r06",
        "Gaussian smearing of 0.01 Ry.",
        "set_smearing",
        {"kind": "gaussian"},
        [{"field": "degauss_ry", "problem": "required argument missing"}],
        {"kind": "gaussian", "degauss_ry": 0.01},
    ),
    (
        "r07",
        "Search for GaAs.",
        "search_structures",
        {"formula": ["GaAs"]},
        [{"field": "formula", "problem": "expected a string, got an array"}],
        {"formula": "GaAs"},
    ),
    (
        "r08",
        "Look up GaAs structures.",
        "search_structures",
        {"query": "GaAs"},
        [
            {"field": "query", "problem": "unknown argument; did you mean formula?"},
            {"field": "formula", "problem": "required argument missing"},
        ],
        {"formula": "GaAs"},
    ),
    (
        "r09",
        "k-points 4x4x1.",
        "set_kpoints",
        {"grid": [4, 4]},
        [{"field": "grid", "problem": "expected 3 integers, got 2"}],
        {"grid": [4, 4, 1]},
    ),
    (
        "r10",
        "Cutoff 45 Ry.",
        "set_cutoff",
        {"ecutwfc_ry": 45, "units": "Ry"},
        [{"field": "units", "problem": "unknown argument"}],
        {"ecutwfc_ry": 45},
    ),
]
DEGRADATION_TOKENS = [2_000, 8_000, 16_000, 24_000]


@dataclass
class Context:
    proxy: c.CaptureProxy
    rec: c.Recorder
    runs: int

    @property
    def base(self) -> str:
        return self.proxy.url


# --- helpers ---------------------------------------------------------------------------------------------------


def lc(system: str, user: str, history: Sequence[Any] = ()) -> list[Any]:
    from langchain_core.messages import HumanMessage, SystemMessage

    return [SystemMessage(system), *history, HumanMessage(user)]


def raw_messages(system: str, user: str, history: Sequence[Mapping[str, str]] = ()) -> list[dict[str, str]]:
    return [{"role": "system", "content": system}, *[dict(m) for m in history], {"role": "user", "content": user}]


def same(a: Any, b: Any) -> bool:
    """Equal, with numbers compared as numbers (60 == 60.0) and lists item by item."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(a - b) <= 1e-9 * max(1.0, abs(b))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return bool(a == b)


def parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def structured(llm: Any, schema: Mapping[str, Any], messages: list[Any]) -> tuple[Any, Any]:
    """A LangChain structured-output call: (parsed result or None, the raw message)."""
    out = llm.with_structured_output(dict(schema), method="json_schema", include_raw=True).invoke(messages)
    return out.get("parsed"), out.get("raw")


def tool_calls_of(message: Any) -> list[dict[str, Any]]:
    calls = [{"name": t["name"], "args": t["args"]} for t in getattr(message, "tool_calls", None) or []]
    calls += [
        {"name": t.get("name"), "args": t.get("args"), "invalid": True}
        for t in getattr(message, "invalid_tool_calls", None) or []
    ]
    return calls


def problems_of(calls: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    return [
        ["invalid-json"] if call.get("invalid") else c.classify(call.get("args"), SCHEMAS.get(str(call["name"]), {}))
        for call in calls
    ]


def sent(ctx: Context) -> dict[str, Any]:
    """What the last request carried, from the proxy."""
    summary = c.summarise(ctx.proxy.last)
    return summary if isinstance(summary, dict) else {}


def attempt(ctx: Context, call: c.Call, body: Callable[[c.Call], None]) -> None:
    """Runs one call; an exception becomes the call's outcome, and the call is always recorded."""
    ctx.proxy.tag = {
        "experiment": call.experiment,
        "case": call.case,
        "client": call.client,
        "variant": call.variant,
        "run": call.run,
    }
    ctx.proxy.last = {}
    with c.timed() as seconds:
        try:
            body(call)
        except Exception as error:  # a spike records every failure and goes on
            call.passed, call.outcome = False, f"error:{type(error).__name__}"
            call.detail["error"] = "".join(traceback.format_exception_only(error)).strip()[:300]
    call.seconds = seconds[0]
    call.detail.setdefault("sent", sent(ctx))
    ctx.rec.write(call)
    print(
        f"{call.experiment:12} {call.client:8} {call.variant:14} {call.case:5} run {call.run}: {call.outcome}",
        flush=True,
    )


# --- experiments -----------------------------------------------------------------------------------------------


def options(ctx: Context) -> None:
    probe_ctx = 12_345  # an unusual value, so the capture shows it was sent
    for run in range(ctx.runs):
        for client in ("litellm-field-only", *c.CLIENTS):

            def body(call: c.Call, client: str = client) -> None:
                if client == "raw":
                    reply = c.raw_chat(
                        ctx.base, raw_messages("Answer briefly.", "Reply with the word ready."), num_ctx=probe_ctx
                    )
                    thinking = reply.get("message", {}).get("thinking") or ""
                    call.prompt_tokens, call.output_tokens = reply.get("prompt_eval_count"), reply.get("eval_count")
                else:
                    if client == "ollama":
                        llm = c.ollama_chat(ctx.base, probe_ctx)
                    else:
                        llm = c.litellm_chat(ctx.base, probe_ctx, top_p_field_only=client == "litellm-field-only")
                    message = llm.invoke(lc("Answer briefly.", "Reply with the word ready."))
                    thinking = str(message.additional_kwargs.get("reasoning_content") or "")
                    call.prompt_tokens, call.output_tokens = c.usage(message)
                body_sent = ctx.proxy.last
                opts = body_sent.get("options") or {}
                checks = {
                    "temperature": opts.get("temperature") == c.TEMPERATURE,
                    "top_p": opts.get("top_p") == c.TOP_P,
                    "num_ctx": opts.get("num_ctx") == probe_ctx,
                    "think_false": body_sent.get("think") is False,
                    "no_thinking_back": thinking == "",
                }
                call.passed = all(checks.values())
                call.outcome = (
                    "all-reached" if call.passed else "missing:" + ",".join(k for k, v in checks.items() if not v)
                )
                call.detail.update(checks=checks, options_sent=opts, think_sent=body_sent.get("think", "absent"))

            attempt(ctx, c.Call("options", "probe", client, run, None, ""), body)

        def think_default(call: c.Call) -> None:
            reply = c.raw_chat(ctx.base, raw_messages("Answer briefly.", "What is 17 times 23?"), think=None)
            thinking = reply.get("message", {}).get("thinking") or ""
            call.prompt_tokens, call.output_tokens = reply.get("prompt_eval_count"), reply.get("eval_count")
            call.outcome = "thinks-by-default" if thinking else "no-thinking-by-default"
            call.detail["thinking_chars"] = len(thinking)

        attempt(ctx, c.Call("options", "think-omitted", "raw", run, None, ""), think_default)

        def context_default(call: c.Call) -> None:
            filler = filler_text(10_000)
            reply = c.raw_chat(
                ctx.base, raw_messages("Answer briefly.", filler + "\nHow many lines were above?"), num_ctx=None
            )
            call.prompt_tokens, call.output_tokens = reply.get("prompt_eval_count"), reply.get("eval_count")
            call.outcome = f"prompt_tokens={call.prompt_tokens}"

        attempt(ctx, c.Call("options", "num_ctx-omitted-10k", "raw", run, None, ""), context_default)


def score_choice(call: c.Call, parsed: Any, label: str) -> None:
    valid = isinstance(parsed, dict) and not c.classify(parsed, CHOICE_SCHEMA) and set(parsed) == {"task"}
    call.detail["valid"] = valid
    if not valid:
        call.passed, call.outcome = False, "invalid"
        call.detail["parsed"] = parsed
    else:
        call.passed = parsed["task"] == label
        call.outcome = "correct" if call.passed else f"wrong:{parsed['task']}"


def choice(
    ctx: Context,
    cases: Sequence[tuple[str, str, str]] = CHOICE_CASES,
    history: Sequence[Any] = (),
    raw_history: Sequence[Mapping[str, str]] = (),
    experiment: str = "choice",
    variant: str = "",
    clients: Sequence[str] = c.CLIENTS,
) -> None:
    for run in range(ctx.runs):
        for case, request, label in cases:
            for client in clients:

                def body(call: c.Call, client: str = client, request: str = request, label: str = label) -> None:
                    if client == "raw":
                        reply = c.raw_chat(
                            ctx.base, raw_messages(CHOICE_SYSTEM, request, raw_history), fmt=CHOICE_SCHEMA
                        )
                        parsed = parse_json(reply.get("message", {}).get("content", ""))
                        call.prompt_tokens = reply.get("prompt_eval_count")
                        call.output_tokens = reply.get("eval_count")
                    else:
                        llm = c.litellm_chat(ctx.base) if client == "litellm" else c.ollama_chat(ctx.base)
                        parsed, raw = structured(llm, CHOICE_SCHEMA, lc(CHOICE_SYSTEM, request, history))
                        call.prompt_tokens, call.output_tokens = c.usage(raw)
                    score_choice(call, parsed, label)
                    call.detail["format_sent"] = sent(ctx).get("format") is not None

                attempt(ctx, c.Call(experiment, case, client, run, None, "", variant), body)


def tool_choice(ctx: Context) -> None:
    for run in range(ctx.runs):
        for case, prompt, natural, forced in TOOL_CHOICE_CASES:
            modes: list[tuple[str, Any]] = [
                ("auto", None),
                ("named", {"type": "function", "function": {"name": forced}}),
            ]
            modes.append(("required", "required") if natural is None else ("none", "none"))
            for client in ("litellm", "ollama"):
                for mode, choice_value in modes:

                    def body(
                        call: c.Call,
                        client: str = client,
                        mode: str = mode,
                        choice_value: Any = choice_value,
                        prompt: str = prompt,
                        natural: str | None = natural,
                        forced: str = forced,
                    ) -> None:
                        llm = c.litellm_chat(ctx.base) if client == "litellm" else c.ollama_chat(ctx.base)
                        bound = (
                            llm.bind_tools(TOOLS, tool_choice=choice_value) if choice_value else llm.bind_tools(TOOLS)
                        )
                        message = bound.invoke(lc(TOOL_SYSTEM, prompt))
                        call.prompt_tokens, call.output_tokens = c.usage(message)
                        calls = tool_calls_of(message)
                        first = calls[0]["name"] if calls else None
                        call.passed = {
                            "auto": first == natural,
                            "named": first == forced,
                            "required": bool(calls),
                            "none": not calls,
                        }[mode]
                        call.outcome = f"first={first}"
                        call.detail.update(
                            tool_calls=calls, problems=problems_of(calls), tool_choice_sent=sent(ctx).get("tool_choice")
                        )

                    attempt(ctx, c.Call("tool_choice", case, client, run, None, "", mode), body)


def tools_format(ctx: Context) -> None:
    answer_schema = {
        "title": "Answer",
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    cases = [case for case in TOOL_CHOICE_CASES if case[0] in ("t01", "t03", "t05", "t06", "t08", "t09")]
    for run in range(ctx.runs):
        for case, prompt, natural, _ in cases:
            for client in ("raw", "ollama", "litellm"):

                def body(call: c.Call, client: str = client, prompt: str = prompt) -> None:
                    if client == "raw":
                        reply = c.raw_chat(ctx.base, raw_messages(TOOL_SYSTEM, prompt), fmt=answer_schema, tools=TOOLS)
                        message = reply.get("message", {})
                        calls = [
                            {"name": t["function"]["name"], "args": t["function"].get("arguments")}
                            for t in message.get("tool_calls") or []
                        ]
                        content = message.get("content") or ""
                    elif client == "ollama":
                        from langchain_ollama import ChatOllama

                        llm = ChatOllama(
                            model=c.MODEL,
                            base_url=ctx.base,
                            temperature=c.TEMPERATURE,
                            top_p=c.TOP_P,
                            num_ctx=c.NUM_CTX,
                            reasoning=False,
                            format=answer_schema,
                        )
                        reply_message = llm.bind_tools(TOOLS).invoke(lc(TOOL_SYSTEM, prompt))
                        calls, content = tool_calls_of(reply_message), str(reply_message.content)
                    else:
                        response_format = {
                            "type": "json_schema",
                            "json_schema": {"name": "Answer", "schema": answer_schema},
                        }
                        reply_message = (
                            c.litellm_chat(ctx.base)
                            .bind_tools(TOOLS, response_format=response_format)
                            .invoke(lc(TOOL_SYSTEM, prompt))
                        )
                        calls, content = tool_calls_of(reply_message), str(reply_message.content)
                    parsed = parse_json(content)
                    call.outcome = (
                        "tool_calls" if calls else "json" if isinstance(parsed, dict) and "answer" in parsed else "text"
                    )
                    summary = sent(ctx)
                    call.detail.update(
                        tool_calls=calls,
                        content=content[:300],
                        sent_tools=bool(summary.get("tools")),
                        sent_format=summary.get("format") is not None,
                    )

                variant = "natural-tool" if natural else "natural-answer"
                attempt(ctx, c.Call("tools_format", case, client, run, None, "", variant), body)


def parallel(ctx: Context) -> None:
    for run in range(ctx.runs):
        for case, prompt, expected in PARALLEL_CASES:
            for client in ("litellm", "ollama"):
                for streaming in (False, True):

                    def body(
                        call: c.Call,
                        client: str = client,
                        streaming: bool = streaming,
                        prompt: str = prompt,
                        expected: set[str] = expected,
                    ) -> None:
                        llm = (
                            c.litellm_chat(ctx.base, streaming=streaming)
                            if client == "litellm"
                            else c.ollama_chat(ctx.base)
                        )
                        bound = llm.bind_tools([SEARCH])
                        messages = lc(TOOL_SYSTEM, prompt)
                        if streaming:
                            chunks = list(bound.stream(messages))
                            message = chunks[0]
                            for chunk in chunks[1:]:
                                message = message + chunk
                        else:
                            message = bound.invoke(messages)
                        call.prompt_tokens, call.output_tokens = c.usage(message)
                        calls = tool_calls_of(message)
                        good = [
                            x for x in calls if not x.get("invalid") and not c.classify(x["args"], SCHEMAS[x["name"]])
                        ]
                        formulas = {x["args"]["formula"] for x in good}
                        call.passed = len(calls) == 2 and formulas == expected
                        call.outcome = (
                            "two-calls"
                            if call.passed
                            else "merged"
                            if any(x.get("invalid") for x in calls)
                            else "no-call"
                            if not calls
                            else f"{len(calls)}-calls"
                        )
                        call.detail.update(tool_calls=calls, problems=problems_of(calls))

                    variant = "stream" if streaming else "invoke"
                    attempt(ctx, c.Call("parallel", case, client, run, None, "", variant), body)


def nested(flat: Flat) -> dict[str, Any]:
    return {
        "basis": {"ecutwfc_ry": flat[0]},
        "kpoints": {"grid": flat[1]},
        "smearing": {"kind": flat[2], "degauss_ry": flat[3]},
    }


def flat_dict(flat: Flat) -> dict[str, Any]:
    return {"ecutwfc_ry": flat[0], "k_grid": flat[1], "smearing": flat[2], "degauss_ry": flat[3]}


def valid_settings(parsed: Any, schema: Mapping[str, Any]) -> bool:
    if not isinstance(parsed, dict) or c.classify(parsed, schema) or set(parsed) != set(schema["properties"]):
        return False
    return all(valid_settings(parsed[k], sub) for k, sub in schema["properties"].items() if sub.get("type") == "object")


def score_settings(call: c.Call, parsed: Any, schema: Mapping[str, Any], expected: dict[str, Any]) -> None:
    valid = valid_settings(parsed, schema)
    call.detail["valid"] = valid
    call.passed = valid and same(parsed, expected)
    call.outcome = "exact" if call.passed else ("invalid" if not valid else "wrong-values")
    if not call.passed:
        call.detail["parsed"] = parsed


def schemas(
    ctx: Context,
    cases: Sequence[tuple[str, str, Flat]] = SETTINGS_CASES,
    history: Sequence[Any] = (),
    raw_history: Sequence[Mapping[str, str]] = (),
    experiment: str = "schemas",
    variant: str = "",
    shapes: Sequence[str] = ("flat", "nested"),
    clients: Sequence[str] = ("litellm", "raw"),
    system: str = SETTINGS_SYSTEM,
) -> None:
    for run in range(ctx.runs):
        for case, request, flat in cases:
            for shape in shapes:
                schema = FLAT_SCHEMA if shape == "flat" else NESTED_SCHEMA
                expected = flat_dict(flat) if shape == "flat" else nested(flat)
                for client in clients:

                    def body(
                        call: c.Call,
                        client: str = client,
                        schema: dict[str, Any] = schema,
                        expected: dict[str, Any] = expected,
                        request: str = request,
                    ) -> None:
                        if client == "raw":
                            reply = c.raw_chat(ctx.base, raw_messages(system, request, raw_history), fmt=schema)
                            parsed = parse_json(reply.get("message", {}).get("content", ""))
                            call.prompt_tokens = reply.get("prompt_eval_count")
                            call.output_tokens = reply.get("eval_count")
                        else:
                            parsed, raw = structured(c.litellm_chat(ctx.base), schema, lc(system, request, history))
                            call.prompt_tokens, call.output_tokens = c.usage(raw)
                        score_settings(call, parsed, schema, expected)

                    attempt(ctx, c.Call(experiment, case, client, run, None, "", variant or shape), body)


def rewrite(ctx: Context) -> None:
    from langchain_core.messages import AIMessage, ToolMessage

    for run in range(ctx.runs):
        for case, request, tool, broken, problems, expected in REWRITE_CASES:
            envelope = {
                "error": {
                    "kind": "invalid_arguments",
                    "retriable": True,
                    "problems": problems,
                    "next_steps": f"Call {tool} again with corrected arguments.",
                }
            }
            history = [
                AIMessage("", tool_calls=[{"name": tool, "args": broken, "id": "call_1"}]),
                ToolMessage(json.dumps(envelope), tool_call_id="call_1"),
            ]
            for client in ("litellm", "ollama"):

                def body(
                    call: c.Call,
                    client: str = client,
                    request: str = request,
                    tool: str = tool,
                    expected: dict[str, Any] = expected,
                    history: list[Any] = history,
                ) -> None:
                    llm = c.litellm_chat(ctx.base) if client == "litellm" else c.ollama_chat(ctx.base)
                    messages = [*lc(TOOL_SYSTEM, request), *history]
                    message = llm.bind_tools(REWRITE_TOOLS).invoke(messages)
                    call.prompt_tokens, call.output_tokens = c.usage(message)
                    calls = tool_calls_of(message)
                    first = calls[0] if calls else None
                    call.passed = bool(
                        first and first["name"] == tool and not first.get("invalid") and same(first["args"], expected)
                    )
                    call.outcome = (
                        "fixed"
                        if call.passed
                        else "no-call"
                        if not first
                        else "other-tool"
                        if first["name"] != tool
                        else "still-wrong"
                    )
                    call.detail.update(tool_calls=calls, problems=problems_of(calls))

                attempt(ctx, c.Call("rewrite", case, client, run, None, ""), body)


FORMULAS = [
    "GaAs",
    "TiO2",
    "ZnO",
    "MgO",
    "NaCl",
    "KCl",
    "Si",
    "Ge",
    "Fe2O3",
    "MoS2",
    "WS2",
    "BaTiO3",
    "SrTiO3",
    "CsPbI3",
    "Al2O3",
    "CuO",
    "NiO",
    "LiFePO4",
    "GaN",
    "InP",
    "CdTe",
    "SiC",
    "BN",
    "AlN",
    "ZrO2",
    "HfO2",
]
DATABASES = ["Materials Project", "Materials Cloud", "NOMAD", "JARVIS"]
SPACE_GROUPS = ["Fm-3m", "F-43m", "P6_3mc", "P4_2/mnm", "R-3c", "Pnma", "I4/mmm", "P-3m1", "Pm-3m", "C2/m"]


def filler_turns(tokens: int) -> list[tuple[str, str]]:
    """Earlier turns of a session, searches and their results, about `tokens` long (3 characters a token)."""
    rng = random.Random(7)
    turns: list[tuple[str, str]] = []
    chars = 0
    while chars < tokens * 3:
        formula = rng.choice(FORMULAS)
        rows = [
            {
                "database": rng.choice(DATABASES),
                "entry_id": f"id-{rng.randrange(10**5, 10**6)}",
                "formula": formula,
                "space_group": rng.choice(SPACE_GROUPS),
                "natoms": rng.choice([2, 4, 6, 8, 12]),
                "energy_above_hull_ev_per_atom": round(rng.uniform(0, 0.3), 3),
            }
            for _ in range(5)
        ]
        user = f"Search the databases for {formula}."
        assistant = f"I found {len(rows)} structures of {formula}: {json.dumps(rows)}"
        turns.append((user, assistant))
        chars += len(user) + len(assistant)
    return turns


def filler_text(tokens: int) -> str:
    return "\n".join(f"{u} {a}" for u, a in filler_turns(tokens))


def degradation(ctx: Context) -> None:
    from langchain_core.messages import AIMessage, HumanMessage

    for tokens in DEGRADATION_TOKENS:
        turns = filler_turns(tokens)
        history = [m for u, a in turns for m in (HumanMessage(u), AIMessage(a))]
        variant = f"{tokens // 1000}k"
        choice(
            ctx,
            CHOICE_CASES[:10],
            history=history,
            experiment="degradation",
            variant=f"choice-{variant}",
            clients=("litellm",),
        )
        schemas(
            ctx,
            SETTINGS_CASES[:10],
            history=history,
            experiment="degradation",
            variant=f"settings-{variant}",
            shapes=("flat",),
            clients=("litellm",),
        )


def schemas_plain(ctx: Context) -> None:
    schemas(ctx, experiment="schemas_plain", system=SETTINGS_SYSTEM_PLAIN)


EXPERIMENTS: dict[str, Callable[[Context], None]] = {
    "options": options,
    "choice": choice,
    "tool_choice": tool_choice,
    "tools_format": tools_format,
    "parallel": parallel,
    "schemas": schemas,
    "rewrite": rewrite,
    "degradation": degradation,
    "schemas_plain": schemas_plain,
}


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="folder for calls.jsonl, requests.jsonl, environment")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", default=",".join(EXPERIMENTS), help="comma-separated experiments")
    parser.add_argument("--ollama", default=c.OLLAMA)
    args = parser.parse_args(argv)
    chosen = [name.strip() for name in args.only.split(",") if name.strip()]
    unknown = [name for name in chosen if name not in EXPERIMENTS]
    if unknown:
        parser.error(f"unknown experiments: {', '.join(unknown)}")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "environment.json").write_text(json.dumps(c.environment(args.ollama), indent=2) + "\n")
    with c.CaptureProxy(args.ollama, args.out / "requests.jsonl") as proxy:
        ctx = Context(proxy, c.Recorder(args.out / "calls.jsonl"), args.runs)
        for name in chosen:
            EXPERIMENTS[name](ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
