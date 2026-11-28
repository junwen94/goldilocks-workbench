"""Offline tests of S3's harness: the round trip's comparison on hand-written pw.x inputs, the summaries behind the
result's tables (AGENTS.md rule 10), the read-only broker scan, the isolated environment, and that no script touches
the user's ~/.aiida. No AiiDA profile, daemon, goldilocks-core or network."""

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import s3_env as e
import s3_report as r
from s3_compare import cards, compare, executables, verdict

HERE = Path(__file__).resolve().parent

CORE = """&CONTROL
   calculation      = 'scf'
   outdir           = './out'
   prefix           = 'pwscf'
   max_seconds      = 41040
   pseudo_dir       = './pseudo'
/
&SYSTEM
   ibrav            = 0
   nat              = 2
   ntyp             = 2
   starting_magnetization(1) = 0.3125
   starting_magnetization(2) = -0.3125
   ecutwfc          = 106.0
   nspin            = 2
/
&ELECTRONS
   conv_thr         = 1.6e-09
   mixing_beta      = 0.4
/

ATOMIC_SPECIES
  Fe1  55.845  Fe.upf
  Fe2  55.845  Fe.upf

CELL_PARAMETERS angstrom
  2.867  0  0
  0  2.867  0
  0  0  2.867

ATOMIC_POSITIONS crystal
  Fe1  0  0  0
  Fe2  0.5  0.5  0.5

K_POINTS automatic
  9  9  9  0  0  0
{hubbard}"""

HUBBARD = """
HUBBARD (ortho-atomic)
  U  Fe1-3d  3
"""

# What aiida-quantumespresso writes for CORE: its folder and file names, verbosity, and positions in Angstrom.
AIIDA = """&CONTROL
  calculation = 'scf'
  max_seconds = 41040
  outdir = './out/'
  prefix = 'aiida'
  pseudo_dir = './pseudo/'
  verbosity = 'high'
/
&SYSTEM
  ecutwfc =   1.0600000000d+02
  ibrav = 0
  nat = 2
  nspin = 2
  ntyp = 2
  starting_magnetization(1) =   3.1250000000d-01
  starting_magnetization(2) =  -3.1250000000d-01
/
&ELECTRONS
  conv_thr =   1.6000000000d-09
  mixing_beta =   4.0000000000d-01
/
ATOMIC_SPECIES
Fe1    55.845 Fe.upf
Fe2    55.845 Fe.upf
ATOMIC_POSITIONS angstrom
Fe1          0.0000000000       0.0000000000       0.0000000000
Fe2          1.4335000000       1.4335000000       1.4335000000
K_POINTS automatic
9 9 9 0 0 0
CELL_PARAMETERS angstrom
      2.8670000000       0.0000000000       0.0000000000
      0.0000000000       2.8670000000       0.0000000000
      0.0000000000       0.0000000000       2.8670000000
"""

PLUMBING = {
    "CONTROL.pseudo_dir": "./pseudo/",
    "CONTROL.outdir": "./out/",
    "CONTROL.prefix": "aiida",
    "CONTROL.verbosity": "high",
}


def core(hubbard: str = "") -> str:
    return CORE.replace("{hubbard}", hubbard)


def test_a_faithful_input_has_no_problem_beyond_the_plumbing() -> None:
    result = compare(core(), AIIDA)
    assert verdict(result, PLUMBING) == []
    assert {entry["key"] for entry in result["changed"]} == {"CONTROL.outdir", "CONTROL.prefix", "CONTROL.pseudo_dir"}
    assert result["only_generated"] == {"CONTROL.verbosity": "high"}
    assert "SYSTEM.starting_magnetization(2)" in result["same"]
    assert result["structure_kept"] and result["species_equal"] and result["k_points_equal"]


def test_without_the_plumbing_list_its_keys_are_reported() -> None:
    problems = verdict(compare(core(), AIIDA), {})
    assert "changed CONTROL.prefix: 'pwscf' -> 'aiida'" in problems
    assert "added CONTROL.verbosity" in problems


def test_a_changed_value_is_reported() -> None:
    problems = verdict(compare(core(), AIIDA.replace("4.0000000000d-01", "3.2000000000d-01")), PLUMBING)
    assert problems == ["changed ELECTRONS.mixing_beta: 0.4 -> 0.32"]


def test_a_plumbing_key_with_another_value_is_reported() -> None:
    problems = verdict(compare(core(), AIIDA.replace("prefix = 'aiida'", "prefix = 'other'")), PLUMBING)
    assert problems == ["changed CONTROL.prefix: 'pwscf' -> 'other'"]


def test_a_dropped_key_is_reported() -> None:
    problems = verdict(compare(core(), AIIDA.replace("  max_seconds = 41040\n", "")), PLUMBING)
    assert problems == ["dropped CONTROL.max_seconds"]


def test_a_lost_card_is_reported_though_qe_tools_cannot_read_it() -> None:
    result = compare(core(HUBBARD), AIIDA)
    assert result["cards_lost"] == ["HUBBARD"]
    assert verdict(result, PLUMBING) == ["card lost: HUBBARD"]


def test_swapped_species_are_reported() -> None:
    swapped = AIIDA.replace("Fe1    55.845", "FeX    55.845").replace("Fe2    55.845", "Fe1    55.845")
    swapped = swapped.replace("FeX    55.845", "Fe2    55.845")
    problems = verdict(compare(core(), swapped), PLUMBING)
    assert problems == ["species differ"]


def test_a_moved_atom_and_another_mesh_are_reported() -> None:
    moved = AIIDA.replace("1.4335000000       1.4335000000       1.4335000000", "1.4335000000 1.4335000000 1.5")
    assert verdict(compare(core(), moved), PLUMBING) == ["structure differs"]
    assert compare(core(), moved)["positions_max_difference_angstrom"] == pytest.approx(0.0665)
    assert verdict(compare(core(), AIIDA.replace("9 9 9 0 0 0", "8 8 8 0 0 0")), PLUMBING) == ["k-points differ"]


def test_cards_are_found_by_name_at_the_start_of_a_line() -> None:
    assert cards(core(HUBBARD)) == ["ATOMIC_POSITIONS", "ATOMIC_SPECIES", "CELL_PARAMETERS", "HUBBARD", "K_POINTS"]
    assert cards("&SYSTEM\n  occupations = 'smearing'\n/\n") == []


def test_executables_come_from_the_bundles_submit_script() -> None:
    script = """
  srun pw.x -npool 8 -in scf.in > scf.out
  srun ph.x -npool 8 -in ph.in > ph.out || goldilocks_status=$?
  srun --nodes=1 --ntasks=1 q2r.x -in q2r.in > q2r.out
  goldilocks_check_stdout_marker "q2r" "q2r.out" "JOB DONE"
  srun --nodes=1 --ntasks=1 matdyn.x -in dispersion.in > dispersion.out
"""
    assert executables(script) == {"scf.in": "pw.x", "ph.in": "ph.x", "q2r.in": "q2r.x", "dispersion.in": "matdyn.x"}


def trial(key: str, phase: str, killed: bool = True, confirmed: bool = False) -> dict[str, Any]:
    return {
        "experiment": "kills",
        "origin": "macos",
        "step": "trial",
        "key": key,
        "phase": phase,
        "killed": killed,
        "confirmed": confirmed,
    }


def rerun(key: str, action: str, **found: Any) -> dict[str, Any]:
    return {"experiment": "kills", "origin": "macos", "step": "rerun", "key": key, "action": action, **found}


def test_kill_summary_groups_by_point_and_reads_the_rerun() -> None:
    rows = [
        trial("a", "node-stored"),
        rerun("a", "needs check: not started", found=1, state="created", checkpoint=True, in_broker_pending=False),
        trial("b", "node-stored"),
        rerun("b", "needs check: not started", found=1, state=None, checkpoint=False, in_broker_pending=False),
        trial("c", "task-sent", confirmed=True),
        rerun("c", "took over", found=1, state="waiting", checkpoint=True, in_broker_processing=True),
        trial("d", "random", killed=False),
        rerun("d", "submitted"),
        {"experiment": "kills", "origin": "macos", "step": "trial", "key": "d", "phase": "none", "action": "submitted"},
    ]
    summary = {row["kill point"]: row for row in r.kill_summary(rows)}
    assert set(summary) == {"node-stored", "task-sent (confirmed)", "random"}
    stored = summary["node-stored"]
    assert stored["trials"] == 2 and stored["killed"] == 2
    assert stored["rerun actions"] == {"needs check: not started": 2}
    assert stored["states found"] == {"created": 1, "None": 1}
    assert stored["not started, with checkpoint"] == 1 and stored["not started, task in broker"] == 0
    assert summary["task-sent (confirmed)"]["rerun actions"] == {"took over": 1}
    assert summary["random"]["killed"] == 0 and summary["random"]["states found"] == {}


def test_revive_summary_counts_endings_by_what_was_found() -> None:
    rows: list[dict[str, Any]] = [
        {"experiment": "kills", "origin": "a", "step": "revive", "state_before": None, "checkpoint_before": False,
         "error": None, "state": "excepted", "exit_status": None},
        {"experiment": "kills", "origin": "a", "step": "revive", "state_before": "created", "checkpoint_before": True,
         "error": None, "state": "finished", "exit_status": 402},
        {"experiment": "kills", "origin": "a", "step": "revive", "state_before": "created", "checkpoint_before": True,
         "error": "boom", "state": "created", "exit_status": None},
    ]  # fmt: skip
    summary = r.revive_summary(rows)
    assert [(x["state before"], x["revived"], x["errors"]) for x in summary] == [("None", 1, 0), ("created", 2, 1)]
    assert summary[1]["ended"] == {"finished 402": 1, "created None": 1}


def test_roundtrip_summary_shows_routes_problems_and_the_work_chains_additions() -> None:
    rows: list[dict[str, Any]] = [
        {"experiment": "roundtrip", "origin": "m", "case": "fe_u", "file": "scf.in", "executable": "pw.x",
         "route": "dry run", "problems": ["card lost: HUBBARD"], "pseudos_identical": {"pseudo/Fe.upf": True},
         "work_chain": {"first_input_identical_to_dry_run": False,
                        "differences": {"only_generated": {"CONTROL.max_seconds": 3420.0}}}},
        {"experiment": "roundtrip", "origin": "m", "case": "si_band", "file": "bands.in", "executable": "pw.x",
         "route": "the plugin's parser failed", "error": "ParsingError: K_POINTS card not found in\n&CONTROL"},
        {"experiment": "roundtrip", "origin": "m", "case": "si_phonon", "file": "ph.in", "executable": "ph.x",
         "route": "no input parser in aiida-quantumespresso for this executable"},
    ]  # fmt: skip
    summary = r.roundtrip_summary(rows)
    assert summary[0]["problems beyond the plumbing"] == "card lost: HUBBARD"
    assert summary[0]["pseudopotentials identical"] is True
    assert summary[0]["work chain added"] == "CONTROL.max_seconds = 3420.0"
    assert summary[1]["error"] == "ParsingError: K_POINTS card not found in"
    assert summary[2]["pseudopotentials identical"] == "" and summary[2]["problems beyond the plumbing"] == ""


def test_caching_summary_names_sources_and_lists_a_work_chains_calculations() -> None:
    rows: list[dict[str, Any]] = [
        {"experiment": "caching", "origin": "l", "case": "failure, first", "uuid": "u1", "exit_status": 410,
         "from_cache": False, "source": None},
        {"experiment": "caching", "origin": "l", "case": "failure, more wall time", "uuid": "u2", "exit_status": 410,
         "from_cache": True, "source": "u1"},
        {"experiment": "caching", "origin": "l", "case": "chain", "work_chain": True, "exit_status": 401,
         "children": [
             {"case": "chain", "uuid": "u3", "exit_status": 410, "from_cache": True, "source": "u1",
              "mixing_beta": 0.4, "restart_mode": None, "disable_cache": None},
             {"case": "chain", "uuid": "u4", "exit_status": 410, "from_cache": False, "source": None,
              "mixing_beta": 0.32, "restart_mode": "restart", "disable_cache": None},
         ]},
        {"experiment": "caching", "origin": "m", "skipped": "no pw.x on PATH"},
    ]  # fmt: skip
    summary = r.caching_summary(rows)
    assert summary[1]["source"] == "failure, first"
    assert [x["case"] for x in summary[2:5]] == ["chain", "  calculation 1", "  calculation 2"]
    assert summary[3]["source"] == "failure, first" and summary[4]["mixing_beta"] == 0.32
    assert summary[5]["case"] == "skipped: no pw.x on PATH"


def test_report_renders_every_section(tmp_path: Path) -> None:
    results = tmp_path / "macos.jsonl"
    rows = [{"experiment": "environment", "platform": "test"}, trial("a", "task-sent"), rerun("a", "took over")]
    results.write_text("\n".join(json.dumps(x) for x in rows))
    text = r.report([results])
    for title in ("## Environment", "## Kill trials", "## Round trip", "## Handlers", "## Caching", "## Errors"):
        assert title in text
    assert "| macos | task-sent | 1 | 1 |" in text


def write_task(folder: Path, kind: str, name: str, pid: Any) -> None:
    path = folder / "storage" / "tasks" / kind
    path.mkdir(parents=True, exist_ok=True)
    (path / name).write_text(json.dumps({"id": name, "body": {"task": "continue", "args": {"pid": pid}}}))


def test_broker_tasks_reads_pids_without_moving_any_file(tmp_path: Path) -> None:
    broker = tmp_path / ".aiida" / "broker" / f"abc-{e.PROFILE}"
    write_task(broker, "pending", "1_a.json", 11)
    write_task(broker, "pending", "2_b.json", 16)
    write_task(broker, "processing", "0_c.json", 6)
    (broker / "storage" / "tasks" / "pending" / "3_d.json").write_text("not json")
    before = sorted(str(p.relative_to(broker)) for p in broker.rglob("*.json"))
    assert e.broker_tasks(tmp_path) == {"pending": [11, 16], "processing": [6]}
    assert sorted(str(p.relative_to(broker)) for p in broker.rglob("*.json")) == before
    assert e.broker_tasks(tmp_path / "nothing") == {"pending": [], "processing": []}


def test_daemon_log_lines_pick_mentions_and_errors(tmp_path: Path) -> None:
    log = tmp_path / ".aiida" / "daemon" / "log"
    log.mkdir(parents=True)
    (log / "aiida-s3.log").write_text("ok\nProcess<6> continued\n[ERROR] parser\nnothing here\n")
    assert e.daemon_log_lines(tmp_path, ["<6>"]) == [
        "aiida-s3.log: Process<6> continued",
        "aiida-s3.log: [ERROR] parser",
    ]


def test_the_environment_isolates_aiida_in_the_run(tmp_path: Path) -> None:
    env = e.environment(tmp_path)
    assert env["AIIDA_PATH"] == str(tmp_path)
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(HERE)
    assert "AIIDA_PROFILE" not in env


def test_the_standin_writes_nothing_and_is_executable(tmp_path: Path) -> None:
    path = e.write_standin(tmp_path, sleep=2)
    assert os.access(path, os.X_OK)
    assert "sleep 2" in path.read_text() and ">" not in path.read_text().split("\n", 2)[2]


def test_leftovers_read_the_run_folder(tmp_path: Path) -> None:
    broker = tmp_path / ".aiida" / "broker" / f"abc-{e.PROFILE}"
    broker.mkdir(parents=True)
    (broker / "broker.pid").write_text("aiida-zeromq-broker 999999999")
    assert e.broker_pid(tmp_path) == 999999999 and e.leftovers(tmp_path) == []
    (broker / "broker.pid").write_text(f"aiida-zeromq-broker {os.getpid()}")
    assert e.leftovers(tmp_path) == [f"broker.pid: {os.getpid()}"]


def test_home_snapshot_reads_names_and_times_only(tmp_path: Path) -> None:
    home = tmp_path / ".aiida"
    (home / "profiles").mkdir(parents=True)
    (home / "config.json").write_text("secret contents")
    snapshot = e.home_snapshot(home)
    assert any(line.endswith("config.json") for line in snapshot)
    assert not any("secret" in line for line in snapshot)


@pytest.mark.parametrize("path", sorted(HERE.glob("*.py")), ids=lambda p: p.name)
def test_no_script_names_the_users_aiida_folder_except_the_snapshot(path: Path) -> None:
    text = path.read_text()
    if path.name in ("s3_env.py", "test_s3.py"):
        return
    assert '".aiida"' not in text and "~/.aiida" not in text
