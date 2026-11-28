# S4: interrupts and resume through our server

The fourth spike of the workbench plan ([`plan.md`](../../changes/2026-11-25-workbench/plan.md), "S4"). It gates
M7 (the executor) and M8 (watcher and recovery). Result:
[`S4-interrupts-resume.md`](../../changes/2026-11-25-workbench/spikes/S4-interrupts-resume.md).

## Isolation

No model, no network and no AiiDA. The model is a script (`s4_model.py`). Each server experiment runs its own server
on 127.0.0.1, with its own SQLite checkpoint file, skills folder and effects file in a fresh folder under
`~/.cache/goldilocks-spikes/s4/`, deleted afterwards unless `--keep` is given.

## Files

- `s4_model.py`: the scripted chat model. It decides each reply from the conversation, so a turn resumed in a new
  process gets the same reply.
- `s4_graphs.py`: the conversation agent (Deep Agents, with a tool that pauses and `start_run`) and the executor (a
  fan-out over three candidates, each running a submit, pause and check subgraph).
- `s4_app.py`: the FastAPI server. Cards come as server-sent events, answers resume with `Command(resume=...)`, the
  executor is driven from OS threads of its own, and the catch-up runs at start-up.
- `s4_facts.py`: what LangGraph and Deep Agents do on their own, in one process.
- `s4_judge.py`: the verdict of each trial, and the skills tally.
- `s4_experiments.py`: the driver. Its docstring lists the experiments.
- `s4_report.py`: the tables for the result.
- `test_s4.py`: offline tests of the parser, the model, the judges and the report. It also keeps S4 as regression
  tests on the pinned libraries (plan, "Risks", row 5), including one SIGKILL restart of each kind through the
  server. The check runs it.

## Running it

```
caffeinate -i uv run python spikes/S4/s4_experiments.py
uv run python spikes/S4/s4_report.py ~/.cache/goldilocks-spikes/s4/results/darwin.jsonl
```

`--only tool,executor` runs some experiments, `--trials N` changes the number of trials (20 by default), and `--keep`
keeps each run folder for inspection.
