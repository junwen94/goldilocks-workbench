# S1: qwen3.8 27B on Ollama

The first spike of the workbench plan ([`plan.md`](../../changes/2026-11-25-workbench/plan.md), "S1"). It gates
M2 (the model layer) and M6 (plans). It is in two parts:

- **S1a, the mechanics**: `s1_mechanics.py`. Result:
  [`S1a-qwen-mechanics.md`](../../changes/2026-11-25-workbench/spikes/S1a-qwen-mechanics.md).
- **S1b, the routing**: the predecessor's 36 tool-choice cases, GENIUS's request strings and D27 step-1 picks. It
  comes in a later PR.

## Files

- `s1_common.py`: the three clients, a capture proxy, the call recorder, the environment record, bootstrap intervals
  and the argument classifier.
  - The clients are ChatLiteLLM (D11's layer), ChatOllama, and raw HTTP to Ollama.
  - They are set up with thinking off, temperature 0.7, top_p 0.8 and an explicit `num_ctx`.
- `s1_mechanics.py`: the eight experiments and their cases. Its docstring lists them.
- `s1_report.py`: the tables for the written result.
- `test_s1.py`: offline tests. The check runs them; they call no model.

## Running it

It needs Ollama on `127.0.0.1:11434` with `qwen3.8:latest` pulled.

```
caffeinate -i uv run python spikes/S1/s1_mechanics.py --out spikes/S1/runs/<name> --runs 3
uv run python spikes/S1/s1_report.py spikes/S1/runs/<name>
```

- `caffeinate -i` keeps the Mac awake.
- `--only choice,schemas` runs some experiments only.
- A run folder holds `calls.jsonl` (one line per call), `requests.jsonl` (a summary of each request Ollama
  received, captured by the proxy) and `environment.json`. Run folders are not committed (`.gitignore`).

Three runs of every S1a experiment took 1.1 hours of model time on an Apple M5 Pro with 48 GB (1,188 calls). Ollama
reuses the cached prefix of the padded degradation prompts, so even the 30K-token ones took about 5 seconds each.
