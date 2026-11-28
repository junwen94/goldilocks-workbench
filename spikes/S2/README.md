# S2: AiiDA on the desktop

The second spike of the workbench plan ([`plan.md`](../../changes/2026-11-25-workbench/plan.md), "S2"). It gates
M5 (the AiiDA module) and M8 (watcher and recovery). Result:
[`S2-aiida-desktop.md`](../../changes/2026-11-25-workbench/spikes/S2-aiida-desktop.md).

## Isolation

Every experiment makes its own AiiDA profile ("s2") in a fresh folder under `~/.cache/goldilocks-spikes/s2/`, and
runs everything that imports AiiDA as a subprocess with `AIIDA_PATH` set to that folder.
- The profile, the daemon and the ZeroMQ broker live and stop there.
- Any AiiDA set-up you already have in `~/.aiida` is never read or written. The driver compares the names and
  modification times there before and after each run, never the files' contents.
- The folder is outside cloud-synced storage, which SQLite does not cope with.

## Files

- `s2_env.py` (no AiiDA import): run folders, profile set-up with `verdi presto --use-zeromq`, codes, daemon start
  and stop, broker pid and queue, leftovers, the `~/.aiida` snapshot.
- `s2_processes.py`, `s2_unversioned.py`: the job builder, a work chain that raises, and two observe-only monitors.
  The monitors are registered through a run-local `dist-info` folder, so nothing is installed.
- `s2_inside.py`: experiments that run inside a profile (daemon control, caching, aiida-quantumespresso's exit
  codes, monitors, threads).
- `s2_app.py`: a FastAPI app with one AiiDA owner thread that submits jobs and records how it is woken.
- `s2_experiments.py`: the driver. Its docstring lists the experiments.
- `s2_sleep.py`: the laptop-sleep test, which the owner runs.
- `s2_report.py`: the tables for the result.
- `Dockerfile`, `Dockerfile.dockerignore`, `run_container.sh`: the same experiments in Linux, except sleep.
- `test_s2.py`: offline tests. The check runs them; they start no daemon.

## Running it

```
caffeinate -i uv run python spikes/S2/s2_experiments.py --out ~/.cache/goldilocks-spikes/s2/results/macos.jsonl
bash spikes/S2/run_container.sh
uv run python spikes/S2/s2_sleep.py      # the owner; not under caffeinate
uv run python spikes/S2/s2_report.py ~/.cache/goldilocks-spikes/s2/results/*.jsonl
```

`--only wakes,states` runs some experiments; `--keep` keeps each run folder for inspection.
