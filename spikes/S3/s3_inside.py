"""S3's experiments that run inside a run's profile, as `python s3_inside.py <experiment> [options] --out FILE`.

Imports AiiDA: s3_experiments runs this only as a subprocess with the run's AIIDA_PATH (s3_env.python). Each experiment
writes one JSON line per measurement to --out. The submit node of D17.1 is `submit_node`: it asks AiiDA for a process
with the key, takes it over if there is one, and submits only if there is none.
"""

import argparse
import hashlib
import json
import os
import signal
import sys
import time
import traceback
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import s3_env as e
from s3_compare import compare, executables, verdict

# A key's reserved prefix in `metadata.label` (the plan's "Key at job creation"); M8 derives the key from the thread,
# step, candidate and repair index, S3 from the trial's name.
KEY_PREFIX = "s3-key:"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "goldilocks-workbench/spikes/S3")
# Namelist keys whose value aiida-quantumespresso's PwCalculation writes itself, with the value it writes
# (aiida_quantumespresso/calculations/__init__.py:487-512 at 5.1.0): three folder and file names it fixes
# (`_blocked_keywords`), and `verbosity`, which it adds as 'high' unless the input sets it (`_default_verbosity`).
PLUMBING = {
    "CONTROL.pseudo_dir": "./pseudo/",
    "CONTROL.outdir": "./out/",
    "CONTROL.prefix": "aiida",
    "CONTROL.verbosity": "high",
}
PHASES = ("none", "before-submit", "node-stored", "checkpoint-saved", "task-sent")
# A process that has not started: `created`, or no state at all when its submitter died between storing the node and
# entering `created` (aiida/engine/processes/process.py: _setup_db_record sets the state to None, on_entered sets it).
NOT_STARTED = (None, "created")


def write(out: Path, entry: dict[str, Any]) -> None:
    with out.open("a") as stream:
        stream.write(json.dumps(entry, default=str) + "\n")


def error_text(error: BaseException) -> str:
    return "".join(traceback.format_exception_only(error)).strip()[:400]


def run_folder() -> Path:
    return Path(os.environ["AIIDA_PATH"])


def key_for(name: str) -> str:
    return KEY_PREFIX + str(uuid.uuid5(NAMESPACE, name))


def load() -> None:
    from aiida import load_profile

    load_profile()


def fresh_reads() -> None:
    """Ends the current read transaction, so reads see what the daemon committed (as aiida's control.py does)."""
    from aiida.manage import get_manager

    storage = get_manager().get_profile_storage()
    if hasattr(storage, "get_session"):
        storage.get_session().commit()


def die() -> None:
    """SIGKILL this process: no exception handler, atexit hook or buffered ZeroMQ message gets to run."""
    sys.stdout.flush()
    os.kill(os.getpid(), signal.SIGKILL)


def pw_builder(bundle: Path, name: str, code: str, wall: int = 3600) -> Any:
    """A PwCalculation builder from one of goldilocks-core's pw.x inputs, by aiida-quantumespresso's own parser: the
    interim route of the workbench plan (M9), with no translation of ours."""
    from aiida_quantumespresso.tools.pwinputparser import create_builder_from_file  # type: ignore[import-untyped]

    metadata = {
        "options": {"resources": {"num_machines": 1, "num_mpiprocs_per_machine": 1}, "max_wallclock_seconds": wall}
    }
    return create_builder_from_file(
        str(bundle), name, f"{code}@localhost", metadata, pseudo_folder_path=str(bundle / "pseudo")
    )


def base_builder(calc: Any, key: str | None = None) -> Any:
    """A PwBaseWorkChain builder around a PwCalculation builder's inputs; the key goes on the work chain only."""
    from aiida.plugins import WorkflowFactory

    factory: Any = WorkflowFactory("quantumespresso.pw.base")
    builder: Any = factory.get_builder()
    inputs = dict(calc._inputs(prune=True))
    builder.kpoints = inputs.pop("kpoints")
    for name, value in inputs.items():
        setattr(builder.pw, name, value)
    if key:
        builder.metadata.label = key
    return builder


def lookup(key: str) -> list[dict[str, Any]]:
    from aiida.orm import ProcessNode, QueryBuilder

    rows = QueryBuilder().append(ProcessNode, filters={"label": key}, project=["id", "attributes.process_label"]).all()
    return [{"pk": pk, "process_label": label} for pk, label in rows]


def describe(pk: int) -> dict[str, Any]:
    from aiida.orm import load_node

    node: Any = load_node(pk)
    queue = e.broker_tasks(run_folder())
    return {
        "pk": pk,
        "process_label": node.process_label,
        "state": node.process_state.value if node.process_state else None,
        "exit_status": node.exit_status,
        "checkpoint": node.checkpoint is not None,
        "sealed": node.is_sealed,
        "in_broker_pending": pk in queue["pending"],
        "in_broker_processing": pk in queue["processing"],
    }


def classify(key: str, wait: float) -> dict[str, Any]:
    """What the submit node finds for its key, read-only. A process in `created` whose task the broker holds is
    queued; one whose task it does not hold is watched for `wait` seconds, in case its task is still on its way, and
    one that does not start is left for the user ("needs check", D17.3). State and checkpoint alone cannot tell a
    queued process from a lost one: S3's tasks experiment found both in `created` with a checkpoint."""
    found = lookup(key)
    if not found:
        return {"action": "none found", "found": 0}
    if len(found) > 1:
        return {"action": "needs check: two or more processes with one key", "found": len(found), "nodes": found}
    first = describe(found[0]["pk"])
    if first["state"] not in NOT_STARTED:
        return {"action": "took over", "found": 1, **first}
    if first["in_broker_pending"] or first["in_broker_processing"]:
        return {"action": "took over (queued in the broker)", "found": 1, **first}
    start = time.monotonic()
    while time.monotonic() - start < wait:
        time.sleep(0.5)
        fresh_reads()
        now = describe(found[0]["pk"])
        if now["state"] not in NOT_STARTED:
            waited = round(time.monotonic() - start, 1)
            return {"action": "took over (it started)", "found": 1, "waited": waited, "at_first_look": first, **now}
    return {"action": "needs check: not started", "found": 1, "waited": wait, **first}


def install_hooks(phase: str, confirmed: bool) -> None:
    """Kills this process at `phase` inside aiida-core 2.9.4's own `submit()` (aiida/engine/launch.py:146-170):
    instantiate_process stores the node, runner.persister.save_checkpoint saves its checkpoint, and
    runner.controller.continue_process sends the task. With `confirmed`, the task is sent with no_reply=False and the
    broker's acknowledgement, which it sends once the task is on disk (aiida/brokers/zeromq/server.py:288-325), is
    awaited before submit() goes on."""
    import aiida.engine.launch
    from aiida.manage import get_manager

    runner: Any = get_manager().get_runner()
    instantiated = [False]
    launch: Any = aiida.engine.launch  # submit() calls the module's instantiate_process, so the hook replaces it
    original_instantiate = launch.instantiate_process

    def instantiate(*args: Any, **kwargs: Any) -> Any:
        process = original_instantiate(*args, **kwargs)
        instantiated[0] = True
        if phase == "node-stored":
            die()
        return process

    launch.instantiate_process = instantiate

    persister = runner.persister
    original_save = persister.save_checkpoint

    def save_checkpoint(process: Any, tag: str | None = None) -> Any:
        result = original_save(process, tag)
        if phase == "checkpoint-saved" and instantiated[0]:  # submit's own call, not the one inside instantiate
            die()
        return result

    persister.save_checkpoint = save_checkpoint

    controller = runner.controller
    original_continue = controller.continue_process

    def continue_process(*args: Any, **kwargs: Any) -> Any:
        if confirmed:
            kwargs["no_reply"] = False
        result = original_continue(*args, **kwargs)
        if confirmed:
            result.result(timeout=30)
        if phase == "task-sent":
            die()
        return result

    controller.continue_process = continue_process


def submit_node(
    key: str, phase: str, confirmed: bool, bundle: Path, wait: float, code: str = "pw-standin"
) -> dict[str, Any]:
    """D17.1's submit node: look the key up; take the process over if AiiDA has one; submit only if it has none."""
    from aiida.engine import submit

    found = classify(key, wait)
    if found["action"] != "none found":
        return {"key": key, **found}
    builder = base_builder(pw_builder(bundle, "scf.in", code), key)
    install_hooks(phase, confirmed)
    print("SUBMITTING", flush=True)
    if phase == "before-submit":
        die()
    start = time.monotonic()
    node: Any = submit(builder)
    seconds = round(time.monotonic() - start, 3)
    checkpoints = run_folder() / "agent-checkpoints"
    checkpoints.mkdir(exist_ok=True)
    (checkpoints / f"{node.pk}.json").write_text(json.dumps({"key": key, "pk": node.pk}))
    return {"key": key, "action": "submitted", "pk": node.pk, "submit_seconds": seconds, "confirmed": confirmed}


def wait_terminated(pks: Sequence[int], timeout: float) -> list[Any]:
    from aiida.orm import load_node

    deadline = time.monotonic() + timeout
    while True:
        fresh_reads()
        nodes = [load_node(pk) for pk in pks]
        if all(node.is_terminated for node in nodes) or time.monotonic() > deadline:
            return nodes
        time.sleep(1)


def experiment_submit(args: argparse.Namespace) -> None:
    load()
    entry = submit_node(args.key, args.phase, args.confirmed, args.bundle, args.wait)
    write(args.out, {"experiment": "kills", "step": args.step, "phase": args.phase, **entry})


def experiment_audit(args: argparse.Namespace) -> None:
    """After the kill trials: how many processes each key has, and whether a process that never started runs when its
    task is sent again (aiida-core's revive_processes, the documented last resort), one process at a time."""
    load()
    from aiida.engine.processes.control import revive_processes
    from aiida.orm import QueryBuilder, WorkflowNode, load_node

    keys = json.loads(args.keys.read_text())
    wait_terminated([row["pk"] for key in keys for row in lookup(key) if row["process_label"] == "PwBaseWorkChain"], 90)
    stuck = []
    for key in keys:
        found = lookup(key)
        nodes = [describe(row["pk"]) for row in found]
        write(args.out, {"experiment": "kills", "step": "audit", "key": key, "found": len(found), "nodes": nodes})
        stuck += [node for node in nodes if node["state"] in NOT_STARTED]
    work_chains = QueryBuilder().append(
        WorkflowNode, filters={"attributes.process_label": "PwBaseWorkChain"}, project=["label"]
    )
    labels = [label for (label,) in work_chains.all()]
    write(
        args.out,
        {
            "experiment": "kills",
            "step": "audit totals",
            "keys": len(keys),
            "work_chains": len(labels),
            "work_chains_without_key": sum(not label.startswith(KEY_PREFIX) for label in labels),
            "keys_with_more_than_one": sum(len(lookup(key)) > 1 for key in keys),
            "not_started": [node["pk"] for node in stuck],
        },
    )
    for before in stuck:
        try:
            stuck_node: Any = load_node(before["pk"])
            revive_processes([stuck_node], wait=True)
            revive_error = None
        except Exception as caught:
            revive_error = error_text(caught)
        (after,) = wait_terminated([before["pk"]], 60)
        write(
            args.out,
            {
                "experiment": "kills",
                "step": "revive",
                "pk": before["pk"],
                "state_before": before["state"],
                "checkpoint_before": before["checkpoint"],
                "error": revive_error,
                "state": after.process_state.value if after.process_state else None,
                "exit_status": after.exit_status,
            },
        )


def experiment_key(args: argparse.Namespace) -> None:
    """Where a key can be stored at node creation, and what a lookup by label finds."""
    load()
    from aiida.engine import submit
    from aiida.orm import load_node

    def attempt(case: str, action: Callable[[], Any]) -> Any:
        try:
            result, error = action(), None
        except Exception as caught:
            result, error = None, error_text(caught)
        write(args.out, {"experiment": "key", "case": case, "ok": error is None, "result": result, "error": error})
        return result

    calc = pw_builder(args.bundle, "scf.in", "pw-standin")

    def extras_on_builder() -> str:
        builder = base_builder(calc)
        builder.metadata.extras = {"goldilocks_key": "x"}
        return "accepted"

    def extras_in_inputs() -> str:
        from aiida.plugins import WorkflowFactory

        builder = base_builder(calc)
        inputs = dict(builder._inputs(prune=True))
        inputs["metadata"] = {**inputs.get("metadata", {}), "extras": {"goldilocks_key": "x"}}
        factory: Any = WorkflowFactory("quantumespresso.pw.base")
        submit(factory, **inputs)
        return "accepted"

    attempt("extras set on the builder's metadata", extras_on_builder)
    attempt("extras passed in metadata to submit()", extras_in_inputs)

    key = key_for("key-on-work-chain")
    node: Any = submit(base_builder(calc, key))
    start = time.monotonic()
    found = lookup(key)
    write(
        args.out,
        {
            "experiment": "key",
            "case": "label on the work chain: lookup right after submit()",
            "found": found,
            "lookup_seconds": round(time.monotonic() - start, 4),
            "label": node.label,
        },
    )
    probe = key_for("key-in-pw-namespace")
    labelled = base_builder(calc, key_for("key-on-work-chain-2"))
    labelled.pw.metadata.label = probe
    other: Any = submit(labelled)
    finished = wait_terminated([node.pk, other.pk], 120)
    for case, chain in (("key on the work chain only", finished[0]), ("pw.metadata.label also set", finished[1])):
        children = [child for child in chain.called]
        write(
            args.out,
            {
                "experiment": "key",
                "case": f"children's labels: {case}",
                "work_chain_label": chain.label,
                "children": [{"process_label": c.process_label, "label": c.label} for c in children],
                "lookup_of_pw_label": len(lookup(probe)) if case.startswith("pw") else None,
            },
        )
    terminated: Any = load_node(node.pk)

    def relabel() -> str:
        terminated.label = "changed by a user"
        changed = load_node(node.pk).label
        terminated.label = key
        return str(changed)

    attempt("relabel a terminated, sealed work chain", relabel)


def experiment_tasks(args: argparse.Namespace) -> None:
    """How a queued job, a running job and a lost one look, and what aiida-core's get_process_tasks() does to the
    ZeroMQ broker's files while the daemon runs (it builds a PersistentQueue, whose _load moves every task in
    processing/ back to pending/: aiida/brokers/zeromq/queue.py)."""
    load()
    from aiida.engine import submit
    from aiida.engine.processes.control import get_process_tasks
    from aiida.manage import get_manager

    run = run_folder()
    pks = []
    for index in range(3):
        builder = pw_builder(args.bundle, "scf.in", "pw-standin")
        builder.metadata.label = key_for(f"tasks-{index}")
        node: Any = submit(builder)
        pks.append(node.pk)
    time.sleep(4)
    write(args.out, {"experiment": "tasks", "step": "4 s after 3 submissions", "queue": e.broker_tasks(run)})
    for index in range(3):
        write(args.out, {"experiment": "tasks", "step": "classified", **classify(key_for(f"tasks-{index}"), 0)})
    broker: Any = get_manager().get_broker()
    listed = get_process_tasks(broker)
    write(
        args.out,
        {"experiment": "tasks", "step": "after get_process_tasks()", "listed": listed, "queue": e.broker_tasks(run)},
    )
    nodes = wait_terminated(pks, 240)
    write(
        args.out,
        {
            "experiment": "tasks",
            "step": "all ended",
            "states": {n.pk: [n.process_state.value if n.process_state else None, n.exit_status] for n in nodes},
            "queue": e.broker_tasks(run),
            "pks": pks,
        },
    )


def experiment_tasks_after(args: argparse.Namespace) -> None:
    """After a daemon restart: the queue, and the states of the jobs whose tasks were left on disk."""
    load()
    from aiida.orm import load_node

    pks = json.loads(args.keys.read_text())
    time.sleep(10)
    fresh_reads()
    nodes = [load_node(pk) for pk in pks]
    write(
        args.out,
        {
            "experiment": "tasks",
            "step": "10 s after a daemon restart",
            "queue": e.broker_tasks(run_folder()),
            "states": {n.pk: [n.process_state.value if n.process_state else None, n.exit_status] for n in nodes},
            "daemon_log": e.daemon_log_lines(run_folder(), [str(pk) for pk in pks]),
        },
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def experiment_roundtrip(args: argparse.Namespace) -> None:
    """Every pw.x input of goldilocks-core's bundles through the interim route: the plugin's parser builds a
    PwCalculation, its dry run writes the input, and the written input is compared value by value with core's. Then
    a PwBaseWorkChain around the same inputs runs on the stand-in, and its first PwCalculation's stored input is
    compared with the dry run's. Inputs for other executables are listed with the parser the route would need."""
    load()
    from aiida.engine import run_get_node, submit

    cases = json.loads((args.bundles / "cases.json").read_text())
    for case in cases:
        if case["status"] != 200:
            write(args.out, {"experiment": "roundtrip", "case": case["case"], "error": case.get("error")})
            continue
        folder = args.bundles / case["case"]
        manifest = json.loads((folder / "goldilocks.json").read_text())
        runs_with = executables((folder / "submit.sh").read_text())
        for step in case["steps"]:
            for name in step["files"]:
                entry: dict[str, Any] = {
                    "experiment": "roundtrip",
                    "case": case["case"],
                    "task": case["task"],
                    "step": step["name"],
                    "file": name,
                    "executable": runs_with.get(name),
                }
                if runs_with.get(name) != "pw.x":
                    write(args.out, {**entry, "route": "no input parser in aiida-quantumespresso for this executable"})
                    continue
                original = (folder / name).read_text()
                try:
                    calc = pw_builder(folder, name, "pw-standin")
                except Exception as caught:
                    write(args.out, {**entry, "route": "the plugin's parser failed", "error": error_text(caught)})
                    continue
                calc.metadata.dry_run = True
                calc.metadata.store_provenance = False
                try:
                    _, node = run_get_node(calc)
                except Exception as caught:
                    write(args.out, {**entry, "route": "the dry run failed", "error": error_text(caught)})
                    continue
                dry = Path(node.dry_run_info["folder"])
                written = (dry / "aiida.in").read_text()
                result = compare(original, written)
                pseudos = {
                    f"pseudo/{path.name}": sha256(path)
                    == manifest["files"].get(f"pseudo/{path.name}", {}).get("sha256")
                    for path in sorted((dry / "pseudo").glob("*"))
                }
                entry.update(
                    {
                        "route": "dry run",
                        "problems": verdict(result, PLUMBING),
                        "compare": result,
                        "pseudos_identical": pseudos,
                        "settings": node.inputs.settings.get_dict() if "settings" in node.inputs else None,
                    }
                )
                try:
                    chain: Any = submit(base_builder(pw_builder(folder, name, "pw-standin")))
                    (chain,) = wait_terminated([chain.pk], 120)
                    child = next(iter(sorted(chain.called, key=lambda n: n.ctime)), None)
                    child_input = child.base.repository.get_object_content("aiida.in") if child else None
                    entry["work_chain"] = {
                        "state": chain.process_state.value,
                        "exit_status": chain.exit_status,
                        "first_input_identical_to_dry_run": child_input == written,
                        "differences": None if child_input in (None, written) else compare(written, child_input),
                    }
                except Exception as caught:
                    entry["work_chain"] = {"error": error_text(caught)}
                write(args.out, entry)


def experiment_handlers(args: argparse.Namespace) -> None:
    """PwBaseWorkChain's process handlers, read from the class, and BaseRestartWorkChain's inputs that govern them."""
    load()
    from aiida.engine.processes.workchains.restart import validate_handler_overrides
    from aiida.orm import Dict
    from aiida.plugins import CalculationFactory, WorkflowFactory

    chain: Any = WorkflowFactory("quantumespresso.pw.base")
    calc: Any = CalculationFactory("quantumespresso.pw")
    codes = {code.status: (label, bool(code.invalidates_cache)) for label, code in calc.spec().exit_codes.items()}
    handled: set[int] = set()
    for handler in chain.get_process_handlers():
        statuses = handler_exit_codes(handler)
        handled |= set(statuses or [])
        write(
            args.out,
            {
                "experiment": "handlers",
                "handler": handler.__name__,
                "priority": getattr(handler, "priority", None),
                "enabled": getattr(handler, "enabled", None),
                "exit_codes": None
                if statuses is None
                else [f"{status} {codes.get(status, ('FINISHED_OK', False))[0]}" for status in statuses],
                "doc": (handler.__doc__ or "").strip().splitlines()[0],
            },
        )
    ports = chain.spec().inputs

    def default(name: str) -> Any:
        if not ports[name].has_default():
            return None
        value = ports[name].default
        value = value() if callable(value) else value
        return getattr(value, "value", str(value))

    def override(handlers: dict[str, Any]) -> Any:
        node: Any = Dict(handlers)  # type: ignore[no-untyped-call]
        return validate_handler_overrides(chain, node, None)  # type: ignore[arg-type]

    write(
        args.out,
        {
            "experiment": "handlers",
            "handler": "inputs",
            "max_iterations": default("max_iterations"),
            "on_unhandled_failure": default("on_unhandled_failure"),
            "pause_on_max_iterations": default("pause_on_max_iterations"),
            "override of a handler by name": override({"sanity_check_insufficient_bands": {"enabled": False}}),
            "override of an unknown name": override({"no_such_handler": {"enabled": False}}),
        },
    )
    write(
        args.out,
        {
            "experiment": "handlers",
            "handler": "coverage",
            "cacheable_pw_codes_without_handler": [
                f"{status} {label}"
                for status, (label, invalidates) in sorted(codes.items())
                if not invalidates and status not in handled
            ],
        },
    )


def handler_exit_codes(handler: Any) -> list[int] | None:
    """The exit statuses a process handler runs for, read from aiida-core's process_handler wrapper, which keeps them
    in its closure: its body runs only when the calculation's status is among them, and an empty list therefore means
    never (aiida/engine/processes/workchains/utils.py:110-116). None means every status."""
    function = handler._self_wrapper
    cells = dict(
        zip(function.__code__.co_freevars, (cell.cell_contents for cell in function.__closure__ or ()), strict=True)
    )
    codes = cells.get("exit_codes")
    return None if codes is None else [code.status for code in codes]


def experiment_caching(args: argparse.Namespace) -> None:
    """With caching on for every process (D39) and a real pw.x: whether a finished pw.x failure is reused by an
    identical job, by one asking only for more wall time or more processes, and by PwBaseWorkChain's restarts; and
    whether `metadata.disable_cache` turns that off for a work chain's calculations. Runs in this interpreter."""
    load()
    from aiida.engine import run_get_node

    failing, passing = args.bundles / "si_maxstep1", args.bundles / "si_scf"

    def calc_entry(case: str, node: Any) -> dict[str, Any]:
        return {
            "experiment": "caching",
            "case": case,
            "pk": node.pk,
            "uuid": node.uuid,
            "state": node.process_state.value if node.process_state else None,
            "exit_status": node.exit_status,
            "from_cache": node.base.caching.is_created_from_cache,
            "source": node.base.caching.get_cache_source(),
            "hash": node.base.caching.get_hash(),
        }

    def calc(case: str, bundle: Path, change: Callable[[Any], None] = lambda b: None) -> Any:
        builder = pw_builder(bundle, "scf.in", "pw-real")
        change(builder)
        _, node = run_get_node(builder)
        entry = calc_entry(case, node)
        if node.exit_status == 0 or "output_parameters" in node.outputs:
            entry["creator"] = node.outputs.output_parameters.get_dict().get("creator_version")
        write(args.out, entry)
        return node

    def chain(case: str, bundle: Path, change: Callable[[Any], None] = lambda b: None) -> None:
        builder = base_builder(pw_builder(bundle, "scf.in", "pw-real"))
        builder.max_iterations = 2
        change(builder)
        _, node = run_get_node(builder)
        children = []
        for child in sorted(node.called, key=lambda n: n.ctime):
            parameters = child.inputs.parameters.get_dict()
            children.append(
                {
                    **calc_entry(case, child),
                    "mixing_beta": parameters.get("ELECTRONS", {}).get("mixing_beta"),
                    "restart_mode": parameters.get("CONTROL", {}).get("restart_mode"),
                    "disable_cache": (child.get_metadata_inputs() or {}).get("metadata", {}).get("disable_cache"),
                }
            )
        write(
            args.out,
            {
                "experiment": "caching",
                "case": case,
                "work_chain": True,
                "exit_status": node.exit_status,
                "children": children,
            },
        )

    def more_wall(builder: Any) -> None:
        builder.metadata.options.max_wallclock_seconds = 7200

    def more_processes(builder: Any) -> None:
        builder.metadata.options.resources = {"num_machines": 1, "num_mpiprocs_per_machine": 2}

    def no_cache(builder: Any) -> None:
        builder.metadata.disable_cache = True

    def chain_no_cache(builder: Any) -> None:
        builder.pw.metadata.disable_cache = True

    calc("failure, first (electron_maxstep 1)", failing)
    calc("failure, identical", failing)
    calc("failure, identical but twice the wall time", failing, more_wall)
    calc("failure, identical but 2 MPI processes requested", failing, more_processes)
    calc("failure, identical with disable_cache", failing, no_cache)
    chain("PwBaseWorkChain on the failure", failing)
    chain("PwBaseWorkChain on the failure, identical", failing)
    chain("PwBaseWorkChain on the failure, pw.metadata.disable_cache", failing, chain_no_cache)
    chain("PwBaseWorkChain on si_scf, first", passing)
    chain("PwBaseWorkChain on si_scf, identical", passing)


EXPERIMENTS: dict[str, Callable[[argparse.Namespace], None]] = {
    "submit": experiment_submit,
    "audit": experiment_audit,
    "key": experiment_key,
    "tasks": experiment_tasks,
    "tasks-after": experiment_tasks_after,
    "roundtrip": experiment_roundtrip,
    "handlers": experiment_handlers,
    "caching": experiment_caching,
}


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", choices=sorted(EXPERIMENTS))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundles", type=Path)
    parser.add_argument("--bundle", type=Path, help="one bundle folder (the kill trials use si_scf)")
    parser.add_argument("--key")
    parser.add_argument("--keys", type=Path, help="a JSON list of keys, or of PKs for tasks-after")
    parser.add_argument("--phase", choices=PHASES, default="none")
    parser.add_argument("--step", default="trial")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--wait", type=float, default=15)
    args = parser.parse_args(argv)
    if "AIIDA_PATH" not in os.environ:
        parser.error("run under a run's AIIDA_PATH (s3_env.python)")
    EXPERIMENTS[args.experiment](args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
