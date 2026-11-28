# S3: the submission key through aiida-quantumespresso

The third spike of the workbench plan ([`plan.md`](../../changes/2026-11-25-workbench/plan.md), "S3"). It gates
M8 (watcher and recovery) and M9 (Quantum ESPRESSO routes and task 1). Result:
[`S3-submission-key.md`](../../changes/2026-11-25-workbench/spikes/S3-submission-key.md).

## Isolation

As in S2, every experiment makes its own AiiDA profile ("s3") in a fresh folder under `~/.cache/goldilocks-spikes/s3/`,
and runs everything that imports AiiDA as a subprocess with `AIIDA_PATH` set to that folder.
- The profile, the daemon and the ZeroMQ broker live and stop there.
- Any AiiDA set-up you already have in `~/.aiida` is never read or written. The driver compares the names and
  modification times there before and after each run, never the files' contents.
- goldilocks-core runs from PyPI in its own environment (uvx). The bundles come over HTTP (AGENTS.md rule 7); the
  three structures come through its CLI and its package folder, which is outside rule 7's "over HTTP only" (see
  `s3_core.py`).

## Files

- `s3_core.py` (no AiiDA): starts goldilocks-core 0.3.3, fetches one bundle per case with `POST /run`, and stops it.
  Its HTTP API serves no example structures, so the structures are the three bundled with goldilocks-core, read from
  the folder its CLI prints.
- `s3_env.py` (no AiiDA): run folders, profile set-up with `verdi presto --use-zeromq`, a stand-in pw.x, daemon start
  and stop, a read-only scan of the broker's task files, leftovers, the `~/.aiida` snapshot.
- `s3_compare.py` (no AiiDA): compares two pw.x inputs value by value with qe-tools' parser.
- `s3_inside.py`: experiments that run inside a profile; `submit_node` is D17.1's submit node.
- `s3_experiments.py`: the driver. Its docstring lists the experiments.
- `s3_report.py`: the tables for the result.
- `Dockerfile`, `Dockerfile.dockerignore`, `run_container.sh`: the same experiments in Linux, with Debian's
  Quantum ESPRESSO, so that the caching experiment has a real pw.x.
- `test_s3.py`: offline tests. The check runs them; they start no daemon and reach no service.

## Running it

```
uv run python spikes/S3/s3_core.py
caffeinate -i uv run python spikes/S3/s3_experiments.py --out ~/.cache/goldilocks-spikes/s3/results/macos.jsonl
bash spikes/S3/run_container.sh
uv run python spikes/S3/s3_report.py ~/.cache/goldilocks-spikes/s3/results/macos.jsonl <linux results>
```

`--only kills,roundtrip` runs some experiments; `--keep` keeps each run folder for inspection. The caching experiment
needs pw.x on `PATH` and is skipped without it. The driver refuses an `--out` that exists, so that two runs never mix
in one file; move or rename the earlier results before running again.
