"""A draft D27 catalogue and labelled goals for S1b's step-1 picks (workbench plan, S1; spec D27).

D27's step 1: from a short catalogue, one line per recipe and per tool, the model picks a recipe or none and the tools
it needs. The catalogue below is a draft for S1 only: its recipes are D8's five tasks and its tools follow the
workbench plan's module table ("Tool modules in the first version"). It is not the Workbench's registry, which M1
builds. DISTRACTORS are plausible tools outside the first version, added to measure a longer catalogue.

A goal's label: the recipes allowed, and groups of tools of which the pick must include at least one each. Picking
more tools than needed does not fail a pick (the schema allows at most MAX_TOOLS); the extra count is recorded.
The labels are Claude's, written for S1 (2026-11-27).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

RECIPES = {
    "recipe.one_material": "Task 1: one material start to finish: convergence, relaxation, bands, DOS and phonons "
    "on HPC, checked and reported.",
    "recipe.screening_funnel": "Task 2: screen database candidates: MLIP pre-screen, DFT on the top few, rank and "
    "report.",
    "recipe.mlip_validation": "Task 3: compare an MLIP with DFT over a set of structures and find where it errs.",
    "recipe.method_study": "Task 4: compare parameter rules (cutoff, k-points, smearing) for accuracy and compute "
    "cost over many materials.",
    "recipe.magnetic_screening": "Task 5: find the magnetic ground state of candidate materials over their magnetic "
    "orderings.",
}
TOOLS = {
    "databases.search": "Search Materials Project, OPTIMADE and JARVIS for computed structures of a formula.",
    "databases.get_structure": "Fetch one structure from a database by its ID.",
    "dft.open_structure": "Open a structure file the user gave, for DFT parameters.",
    "dft.review": "Show goldilocks-dft's recommended DFT parameters for the open structure, with sources.",
    "dft.settings": "List the DFT settings a user may change.",
    "dft.set": "Set DFT settings to values the user gave.",
    "dft.capabilities": "List the codes, tasks and settings goldilocks-dft supports.",
    "builder.supercell": "Build a supercell of a structure.",
    "builder.substitute": "Substitute elements to make new compositions from a prototype.",
    "builder.vacancy": "Create vacancies or dopants in a structure.",
    "builder.strain": "Apply strain or scale the lattice.",
    "builder.slab": "Cut a surface slab with vacuum.",
    "builder.interface": "Build an interface between two structures.",
    "builder.set_moments": "Set initial magnetic moments on sites.",
    "builder.magnetic_orderings": "Enumerate the magnetic orderings of a structure.",
    "builder.symmetrise": "Symmetrise and standardise a cell.",
    "builder.identity_check": "Check that a structure matches its source: composition, space group, ID.",
    "aiida.scf": "Run a self-consistent DFT calculation at fixed geometry on HPC.",
    "aiida.relax": "Relax the atomic positions with the cell fixed, on HPC.",
    "aiida.vc_relax": "Relax the atomic positions and the cell, on HPC.",
    "aiida.bands": "Compute a band structure along high-symmetry lines, on HPC.",
    "aiida.dos": "Compute the density of states and projected DOS, on HPC.",
    "aiida.phonons": "Compute phonons by DFPT, on HPC.",
    "aiida.convergence_scan": "Scan the cutoff or k-point convergence of a structure, on HPC.",
    "aiida.job_status": "Show the state of submitted jobs.",
    "aiida.diagnose": "Explain why a job failed.",
    "aiida.cancel": "Cancel a running job.",
    "mlip.single_point": "Compute energy and forces with an MLIP.",
    "mlip.optimise": "Optimise a geometry with an MLIP.",
    "mlip.descriptors": "Compute MLIP descriptors of structures.",
    "mlip.prescreen": "Rank many candidate structures with an MLIP.",
    "analysis.gap_bands": "Band gap and band structure from finished calculations.",
    "analysis.dos": "Analyse a density of states from finished calculations.",
    "analysis.phonons": "Phonon dispersion, DOS and stability from finished calculations.",
    "analysis.hull": "Convex hull and energy above hull.",
    "analysis.symmetry": "Classify the symmetry of structures.",
    "analysis.ground_state": "Rank magnetic orderings by energy and pick the ground state.",
    "analysis.mlip_errors": "MLIP-against-DFT errors by structure and local environment.",
    "analysis.rank": "Rank candidates on several objectives.",
    "analysis.compare": "Compare parameter rules or methods on accuracy and cost.",
    "literature.search": "Search scholarly works.",
    "literature.get": "Get one work's metadata.",
    "literature.fetch_text": "Fetch the open-access text of a work.",
    "literature.index_search": "Search the indexed text of fetched papers.",
    "literature.verify_quote": "Check a quote, a number and its unit against a paper.",
    "literature.citations": "Resolve citations and their update status.",
}
DISTRACTORS = {
    "md.classical": "Run classical molecular dynamics with a force field.",
    "md.trajectory": "Analyse a molecular dynamics trajectory.",
    "plot.export_png": "Export a plot as a PNG image.",
    "files.list": "List the files in the task folder.",
    "files.read": "Read a text file from the task folder.",
    "units.convert": "Convert a value between units.",
    "notify.email": "Send an email notification.",
    "calendar.remind": "Schedule a reminder.",
    "web.search": "Search the web.",
    "chem.smiles_to_xyz": "Convert a SMILES string to 3D coordinates.",
    "chem.conformers": "Generate molecular conformers.",
    "spectra.xrd": "Simulate an X-ray diffraction pattern.",
    "spectra.ir": "Simulate an infrared spectrum.",
    "spectra.raman": "Simulate a Raman spectrum.",
    "elastic.tensor": "Compute elastic constants.",
    "transport.boltztrap": "Compute transport coefficients from bands.",
    "optics.dielectric": "Compute the optical dielectric function.",
    "defects.formation": "Compute defect formation energies.",
    "surfaces.energy": "Compute surface energies.",
    "neb.path": "Compute a minimum energy path between two states.",
    "wannier.fit": "Construct Wannier functions.",
    "gw.quasiparticle": "Run a GW calculation.",
    "tddft.absorption": "Compute optical absorption with TDDFT.",
    "eos.fit": "Fit an equation of state.",
    "phase.diagram_plot": "Plot a phase diagram.",
    "data.export_csv": "Export results as CSV.",
    "report.write": "Write a report of results.",
    "ml.train_potential": "Train a new machine-learning potential.",
    "queue.priority": "Change a job's queue priority.",
    "storage.archive": "Archive a finished task's files.",
}
MAX_TOOLS = 10
SIZES = {"short": (RECIPES, TOOLS), "long": (RECIPES, {**TOOLS, **DISTRACTORS})}
SYSTEM = (
    "You plan the first step of a materials-science request. From the catalogue below, pick the recipe that fits "
    "the request, or none, and the tools the work will need. Pick only from the catalogue. Answer in JSON.\n\n"
    "Catalogue:\n{catalogue}"
)
# The same with one sentence more. In the first smoke run the model named a recipe for almost every request, even
# "Cancel the band structure job"; the "guided" variant measures how much of that the wording causes.
SYSTEM_GUIDED = SYSTEM.replace(
    "Pick only from the catalogue.",
    "A recipe is a whole multi-step task; most requests need none. Pick only from the catalogue.",
)
VARIANTS = {"short": ("short", SYSTEM), "long": ("long", SYSTEM), "short-guided": ("short", SYSTEM_GUIDED)}

DB = {"databases.search", "databases.get_structure"}


@dataclass(frozen=True)
class Goal:
    id: str
    request: str
    recipes: frozenset[str]
    groups: tuple[frozenset[str], ...] = ()
    no_tools: bool = False  # a chat-only request: the pick must name no tool


def goal(gid: str, request: str, recipes: Iterable[str], *groups: Iterable[str], no_tools: bool = False) -> Goal:
    return Goal(gid, request, frozenset(recipes), tuple(frozenset(g) for g in groups), no_tools)


ONE, FUNNEL, MLIPV, METHOD, MAG = (
    f"recipe.{n}" for n in ("one_material", "screening_funnel", "mlip_validation", "method_study", "magnetic_screening")
)
GOALS = [
    goal(
        "g01",
        "Take silicon from Materials Project, compute its band structure, DOS and phonons on SCARF, and "
        "write a report.",
        [ONE],
        DB,
        {"aiida.bands"},
        {"aiida.dos"},
        {"aiida.phonons"},
    ),
    goal(
        "g02",
        "Compute the band gap of GaAs with Quantum ESPRESSO, starting from a database structure.",
        ["none", ONE],
        DB,
        {"aiida.bands", "aiida.dos"},
        {"analysis.gap_bands"},
    ),
    goal(
        "g03",
        "Screen the spinel oxides in Materials Project for stability: pre-screen them with an MLIP and run "
        "DFT on the best five.",
        [FUNNEL],
        {"databases.search"},
        {"mlip.prescreen"},
        {"aiida.scf", "aiida.relax", "aiida.vc_relax"},
    ),
    goal(
        "g04",
        "How well does the MLIP reproduce DFT forces on these 50 structures, and where does it fail?",
        [MLIPV],
        {"mlip.single_point"},
        {"aiida.scf"},
        {"analysis.mlip_errors"},
    ),
    goal(
        "g05",
        "Compare our current cutoff rule with a fixed 60 Ry cutoff for accuracy and core-hours on ten oxides.",
        [METHOD],
        {"analysis.compare"},
        {"aiida.convergence_scan", "aiida.scf"},
    ),
    goal(
        "g06",
        "Find the magnetic ground state of NiO.",
        [MAG, "none"],
        {"builder.magnetic_orderings"},
        {"aiida.scf", "aiida.relax", "aiida.vc_relax"},
        {"analysis.ground_state"},
    ),
    goal(
        "g07",
        "Relax the atoms of the slab file I attached, keeping the cell fixed.",
        ["none"],
        {"dft.open_structure"},
        {"aiida.relax"},
    ),
    goal("g08", "Fully relax the cell of MgO from Materials Project.", ["none", ONE], DB, {"aiida.vc_relax"}),
    goal(
        "g09",
        "Make a 2x2x2 supercell of the open structure and replace one Ti with Zr.",
        ["none"],
        {"builder.supercell"},
        {"builder.substitute"},
    ),
    goal("g10", "Cut a (111) slab of platinum with 15 angstrom of vacuum.", ["none"], {"builder.slab"}),
    goal("g11", "What cutoff and k-points does goldilocks-dft recommend for this structure?", ["none"], {"dft.review"}),
    goal("g12", "Set the k-point grid to 8x8x8 and the cutoff to 60 Ry.", ["none"], {"dft.set"}),
    goal("g13", "Why did my last relaxation job fail?", ["none"], {"aiida.diagnose"}),
    goal("g14", "Is my phonon job still running?", ["none"], {"aiida.job_status"}),
    goal("g15", "Cancel the band structure job.", ["none"], {"aiida.cancel"}),
    goal(
        "g16",
        "Find papers that report the band gap of hexagonal boron nitride and check the number they give.",
        ["none"],
        {"literature.search"},
        {"literature.verify_quote", "literature.fetch_text", "literature.index_search"},
    ),
    goal("g17", "Is LiFePO4 on the convex hull according to my finished calculations?", ["none"], {"analysis.hull"}),
    goal(
        "g18",
        "Pre-screen these 200 candidate structures with an MLIP and give me the top 20.",
        ["none", FUNNEL],
        {"mlip.prescreen"},
    ),
    goal("g19", "Optimise this structure quickly with an MLIP before any DFT.", ["none"], {"mlip.optimise"}),
    goal(
        "g20", "Check whether the structure I fetched matches the database entry.", ["none"], {"builder.identity_check"}
    ),
    goal("g21", "Run a k-point convergence test for aluminium.", ["none", METHOD], {"aiida.convergence_scan"}),
    goal(
        "g22",
        "Compute the phonons of NaCl at its current geometry and tell me whether it is stable.",
        ["none", ONE],
        {"aiida.phonons"},
        {"analysis.phonons"},
    ),
    goal(
        "g23",
        "Enumerate the antiferromagnetic orderings of this iron structure.",
        ["none", MAG],
        {"builder.magnetic_orderings"},
    ),
    goal("g24", "Which tasks and codes does goldilocks-dft support?", ["none"], {"dft.capabilities"}),
    goal("g25", "Hello, what can you do?", ["none"], no_tools=True),
    goal("g26", "Thanks, that is all for today.", ["none"], no_tools=True),
    goal("g27", "In two sentences, what does smearing do in a metal?", ["none"], no_tools=True),
    goal("g28", "Rank these finished candidates by band gap and stability.", ["none"], {"analysis.rank"}),
    goal("g29", "Build a heterostructure of graphene on hexagonal boron nitride.", ["none"], {"builder.interface"}),
    goal(
        "g30",
        "Compute the projected DOS of iron from its Materials Project structure.",
        ["none", ONE],
        DB,
        {"aiida.dos"},
    ),
]


def catalogue(size: str) -> str:
    recipes, tools = SIZES[size]
    return "\n".join(f"{name}: {text}" for name, text in {**recipes, **tools}.items())


def schema(size: str) -> dict[str, Any]:
    recipes, tools = SIZES[size]
    return {
        "title": "StepOnePick",
        "description": "The recipe that fits the request, or none, and the tools the work needs.",
        "type": "object",
        "properties": {
            "recipe": {"type": "string", "enum": [*recipes, "none"]},
            "tools": {"type": "array", "items": {"type": "string", "enum": list(tools)}, "maxItems": MAX_TOOLS},
        },
        "required": ["recipe", "tools"],
        "additionalProperties": False,
    }


@dataclass
class Pick:
    passed: bool
    outcome: str
    detail: dict[str, Any] = field(default_factory=dict)


def score_pick(
    parsed: Any, recipes: frozenset[str], groups: Sequence[frozenset[str]], size: str, no_tools: bool = False
) -> Pick:
    """Whether a step-1 pick names an allowed recipe and at least one tool from each group."""
    allowed_recipes, allowed_tools = SIZES[size]
    if not isinstance(parsed, Mapping) or set(parsed) != {"recipe", "tools"} or not isinstance(parsed["tools"], list):
        return Pick(False, "invalid", {"parsed": parsed})
    recipe, tools = parsed["recipe"], [str(t) for t in parsed["tools"]]
    if recipe not in [*allowed_recipes, "none"] or any(t not in allowed_tools for t in tools):
        return Pick(False, "invalid", {"parsed": parsed})
    picked = set(tools)
    missing = [sorted(g) for g in groups if not g & picked]
    needed = set().union(*groups) if groups else set()
    tools_ok = not missing and not (no_tools and picked)
    detail = {
        "recipe": recipe,
        "tools": sorted(picked),
        "missing": missing,
        "extra": len(picked - needed),
        "distractors": sorted(picked & set(DISTRACTORS)),
        "recipe_ok": recipe in recipes,
        "tools_ok": tools_ok,
    }
    if recipe not in recipes:
        return Pick(False, f"recipe:{recipe}", detail)
    if no_tools and picked:
        return Pick(False, "tools-on-chat", detail)
    if missing:
        return Pick(False, "missing:" + "+".join("|".join(g) for g in missing), detail)
    return Pick(True, "pass", detail)
