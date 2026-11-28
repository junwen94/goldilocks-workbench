"""Compares two pw.x input files value by value, for S3's round trip (workbench plan, "S3"; the plan's "Round trip"
test, D22 and D37).

Both files are read with qe-tools' PwInputFile, the parser that aiida-quantumespresso's own PwInputFile extends, so a
value counts as kept when it parses to the same value. Cards that qe-tools does not read (HUBBARD, for one) are found by
name, so a card that one file has and the other lacks is reported even when its content cannot be compared.
Imports no AiiDA.
"""

import math
import re
from collections.abc import Mapping
from typing import Any

from qe_tools.parsers import PwInputFile  # type: ignore[import-untyped]

# pw.x's input cards (Quantum ESPRESSO's INPUT_PW); a line starting with one of these names opens the card.
CARDS = (
    "ATOMIC_SPECIES",
    "ATOMIC_POSITIONS",
    "K_POINTS",
    "ADDITIONAL_K_POINTS",
    "CELL_PARAMETERS",
    "CONSTRAINTS",
    "OCCUPATIONS",
    "ATOMIC_VELOCITIES",
    "ATOMIC_FORCES",
    "SOLVENTS",
    "HUBBARD",
)
CARD_LINE = re.compile(r"^[ \t]*(" + "|".join(CARDS) + r")\b", re.M)
# Lengths in Angstrom: both files give the cell and qe-tools gives positions in Angstrom, Cartesian. A value written
# with fewer digits than it parses to differs by less than this.
LENGTH_TOLERANCE = 1e-6


def cards(text: str) -> list[str]:
    return sorted(set(CARD_LINE.findall(text)))


def same_value(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=0.0)
    return bool(a == b)


def flat_namelists(namelists: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {f"{name}.{key}": value for name, entries in namelists.items() for key, value in entries.items()}


def max_difference(a: list[list[float]], b: list[list[float]]) -> float | None:
    if len(a) != len(b) or any(len(x) != len(y) for x, y in zip(a, b, strict=True)):
        return None
    return max(
        (abs(x - y) for row_a, row_b in zip(a, b, strict=True) for x, y in zip(row_a, row_b, strict=True)), default=0.0
    )


def compare(original: str, generated: str) -> dict[str, Any]:
    """What `generated` kept, changed, dropped and added of `original`'s values."""
    a, b = PwInputFile(original), PwInputFile(generated)
    left, right = flat_namelists(a.namelists), flat_namelists(b.namelists)
    same, changed = [], []
    for key in sorted(left.keys() & right.keys()):
        if same_value(left[key], right[key]):
            same.append(key)
        else:
            changed.append({"key": key, "original": left[key], "generated": right[key]})
    cell = max_difference(a.structure["cell"], b.structure["cell"])
    positions = max_difference(a.structure["positions"], b.structure["positions"])
    return {
        "same": same,
        "changed": changed,
        "only_original": {key: left[key] for key in sorted(left.keys() - right.keys())},
        "only_generated": {key: right[key] for key in sorted(right.keys() - left.keys())},
        "cards_lost": sorted(set(cards(original)) - set(cards(generated))),
        "cards_added": sorted(set(cards(generated)) - set(cards(original))),
        "species_equal": a.atomic_species == b.atomic_species,
        "species": {"original": a.atomic_species, "generated": b.atomic_species},
        "atom_names_equal": a.structure["atom_names"] == b.structure["atom_names"],
        "cell_max_difference_angstrom": cell,
        "positions_max_difference_angstrom": positions,
        "structure_kept": cell is not None
        and positions is not None
        and cell <= LENGTH_TOLERANCE
        and positions <= LENGTH_TOLERANCE,
        "k_points_equal": a.k_points == b.k_points,
        "k_points": {"original": a.k_points, "generated": b.k_points},
    }


def verdict(result: Mapping[str, Any], plumbing: Mapping[str, Any]) -> list[str]:
    """Every way in which `generated` did not keep `original`, beyond the plumbing: the namelist keys whose value the
    plugin sets itself, each mapped to the value the plugin writes."""
    problems = []
    for entry in result["changed"]:
        if entry["key"] not in plumbing or plumbing[entry["key"]] != entry["generated"]:
            problems.append(f"changed {entry['key']}: {entry['original']!r} -> {entry['generated']!r}")
    problems += [f"dropped {key}" for key in result["only_original"] if key not in plumbing]
    problems += [f"added {key}" for key in result["only_generated"] if key not in plumbing]
    problems += [f"card lost: {name}" for name in result["cards_lost"]]
    problems += [f"card added: {name}" for name in result["cards_added"]]
    if not result["species_equal"]:
        problems.append("species differ")
    if not result["atom_names_equal"]:
        problems.append("atom names or their order differ")
    if not result["structure_kept"]:
        problems.append("structure differs")
    if not result["k_points_equal"]:
        problems.append("k-points differ")
    return problems


STEP_LINE = re.compile(r"\b([A-Za-z0-9_.]+\.x)\b[^\n]*?-in\s+(\S+)")


def executables(submit_script: str) -> dict[str, str]:
    """Each input file of a goldilocks-core bundle mapped to the executable its submit.sh runs it with."""
    return {name: executable for executable, name in STEP_LINE.findall(submit_script)}
