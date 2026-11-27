# S1: qwen3.8 27B on Ollama

The first spike of the workbench plan ([`plan.md`](../../changes/2026-11-25-workbench/plan.md), "S1"). It gates
M2 (the model layer) and M6 (plans). It is in two parts:

- **S1a, the mechanics**: `s1_mechanics.py`. Result:
  [`S1a-qwen-mechanics.md`](../../changes/2026-11-25-workbench/spikes/S1a-qwen-mechanics.md).
- **S1b, the routing**: `s1_routing.py`. It covers the predecessor's 36 tool-choice cases, GENIUS's request
  strings, and D27 step-1 picks on a draft catalogue. Result:
  [`S1b-qwen-routing.md`](../../changes/2026-11-25-workbench/spikes/S1b-qwen-routing.md).

## Files

- `s1_common.py`: the shared parts.
  - Three clients, set up with thinking off, temperature 0.7, top_p 0.8 and an explicit `num_ctx`: ChatLiteLLM
    (D11's layer), ChatOllama, and raw HTTP to Ollama.
  - A capture proxy. With `stream_through=True` (S1b) it passes streamed replies on as they arrive.
  - The call recorder, the environment record, bootstrap intervals, and the argument classifier.
- `s1_mechanics.py`: S1a's nine experiments and their cases. Its docstring lists them.
- `s1_routing.py`: S1b's three experiments. Its docstring lists them. `summary()` gives the figures that the tables
  leave out.
- `s1_predecessor_cases.py`, `s1_predecessor_prompt.py`, `predecessor/`: carried from `stfc/goldilocks-agent` at
  `ea757c7` (spec D13). They hold the 36 cases with their judges, the prompt, the 8 web tools and 4 recorded
  goldilocks-core responses. `NOTICE` lists them, and each file's header lists its changes.
- `s1_genius.py`: fetches GENIUS's 295 request strings from a pinned commit into a cache outside the repository
  (`~/.cache/goldilocks-spikes/`). The text is never committed. It also checks their sha256 and labels them with a
  keyword rule.
- `s1_catalogue.py`: the draft D27 catalogue (51 lines, or 81 with distractors), 30 labelled goals, and the scoring
  of a step-1 pick.
- `s1_report.py`: the tables for a written result.
- `test_s1.py`, `test_s1_routing.py`: offline tests. The check runs them; they call no model and use no network.

## Running it

It needs Ollama on `127.0.0.1:11434` with `qwen3.8:latest` pulled. S1b's GENIUS experiment also needs network
access to GitHub the first time, to fill the cache.

```
caffeinate -i uv run python spikes/S1/s1_mechanics.py --out spikes/S1/runs/<new folder> --runs 3
caffeinate -i uv run python spikes/S1/s1_routing.py --out spikes/S1/runs/<new folder> --runs 3
uv run python spikes/S1/s1_report.py spikes/S1/runs/<folder>
```

- `caffeinate -i` keeps the Mac awake.
- `--only choice,schemas` runs some experiments only.
- A run folder holds `calls.jsonl` (one line per call), `requests.jsonl` (a summary of each request Ollama
  received, captured by the proxy) and `environment.json`. Run folders are not committed (`.gitignore`).

Three runs of every S1a experiment took 1.1 hours of model time on an Apple M5 Pro with 48 GB (1,188 calls). Ollama
reuses the cached prefix of the padded degradation prompts, so even the 30K-token ones took about 5 seconds each.
