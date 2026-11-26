# S1a: qwen3.8 27B on Ollama, the mechanics

Spike S1, first part (workbench plan, Phase 1, "S1 qwen3.8 27B on Ollama"; it gates M2 and M6). The second part,
S1b, covers routing: the predecessor's 36 cases, GENIUS's requests, and D27 step-1 picks.

- Run on 2026-11-26, on the owner's Mac (owner's choice), by Claude.
- Script: `spikes/S1/s1_mechanics.py`, at the commit that adds this file. Tables: `spikes/S1/s1_report.py`.
- 1,188 calls, 3 runs per case, 1.1 hours of model time. The raw calls are not committed.
- Every request went through a localhost capture proxy, so "reaches Ollama" means "seen in the request Ollama
  received".

## Environment

| | |
|---|---|
| Ollama | 0.40.16 |
| Model | `qwen3.8:latest` = `qwen3.8:27b-q4_K_M`, digest `22130167c4c2...`, 27.3B, Q4_K_M, family qwen35, context length 262,144 |
| Machine | Apple M5 Pro, 48 GB, macOS (arm64) |
| Clients | langchain-litellm 0.4.0 with litellm 1.83.0 (`ollama_chat/`); langchain-ollama 1.2.0; raw `POST /api/chat` |
| Settings | thinking off, temperature 0.7, top_p 0.8 (qwen's non-thinking sampling, as the predecessor set it), `num_ctx` 32,768 |

## Answers

1. **Options reach Ollama, with one fix.**
   - Through ChatOllama and raw requests, temperature, top_p, `num_ctx` and `think: false` all reach Ollama (3 of 3
     each).
   - **ChatLiteLLM drops its own `top_p` field**: it was missing from every request (3 of 3). Putting `top_p` in
     `model_kwargs` fixes it (3 of 3 reached).
   - **Thinking-off is needed**: with `think` left out, qwen3.8 thinks by default (3 of 3).
   - With `num_ctx` left out, a 12,339-token prompt was not cut. The server's default context is at least that on
     this machine; it is not a reason to leave `num_ctx` out.
2. **The forced-choice route is Ollama's `format` (a JSON schema).** On 20 labelled choices among goldilocks-dft's
   eight tasks, all three routes were 100% schema-valid and 100% correct (60 calls each; 95% interval 100% to 100%):
   - ChatLiteLLM's `with_structured_output(method="json_schema")`;
   - ChatOllama's;
   - raw `format`.

   The schema reached Ollama as `format` on every call. **The stop rule passes**: a route is schema-valid in at
   least 99% of calls, and its accuracy's lower bound is at least 90%.
3. **`tool_choice` is not honoured.** Neither client sends it to Ollama: it was absent from all 180 tool-choice
   requests. Results by mode:
   - forcing a named tool: 0 of 30 per client;
   - "required": 0 of 15;
   - "none": 0 of 15;
   - the same prompts without `tool_choice` ("auto"): 30 of 30 per client.
4. **Tools and `format` in one request: the model never calls a tool.** All 54 answers were JSON:
   - On the 9 requests per client that naturally call a tool, it described results it never fetched, for example
     "Found 1 structure(s) for GaAs.", "I searched the databases for GaAs structures."
   - Or it claimed the tool did not exist.
5. **Parallel calls work.** Two independent searches in one request gave two clean calls:
   - 24 of 24 per client without streaming;
   - 24 of 24 through ChatOllama with streaming;
   - 23 of 24 through ChatLiteLLM with streaming. Once (p08, run 1), the second call was missing. It was not
     merged into a malformed call. With one miss in 24, this run cannot tell a streaming fault from the model's
     own variance.
6. **Flat vs nested schemas: no measurable difference.** Every answer was schema-valid. Exact extraction of four DFT
   settings from 15 requests (45 calls per row):

   | | flat, ChatLiteLLM | flat, raw | nested, ChatLiteLLM | nested, raw |
   |---|---|---|---|---|
   | prompt with a hint naming a smearing | 93% (87% to 100%) | 91% (80% to 100%) | 89% (76% to 100%) | 87% (71% to 100%) |
   | prompt without the hint | 78% (58% to 93%) | 91% (78% to 100%) | 93% (80% to 100%) | 93% (80% to 100%) |

   - **The errors are in the values, not the schema.** With the hint ("Cold smearing is marzari-vanderbilt"), 14 of
     the 19 wrong fields were that smearing, put in where the user named none. A hint in the prompt leaked into
     answers.
   - Without the hint, those disappeared. Instead, "cold smearing" was mapped to the wrong enum value in 12 of 12
     calls. Stated values were missed in 7 calls, and a value was invented in 2.
7. **Robustness: one rewrite fixed every broken call.**
   - The test: 10 deliberately broken calls (missing, extra and mistyped arguments), each answered with a typed
     error list (field, problem, "did you mean").
   - The next call was valid and carried the intended values in 30 of 30 calls per client.
   - Of all 341 tool calls the model made in the tool-choice, parallel and rewrite experiments, none had a missing,
     extra or mistyped argument.
8. **No degradation up to 30.7K tokens for choices.** Earlier turns (search results) padded each prompt; the lengths
   are Ollama's counts:

   | prompt tokens | choice (30 calls) | settings, flat (30 calls) | median seconds |
   |---|---|---|---|
   | 2,954 | 100% | 80% (57% to 100%) | 4.1 / 6.5 |
   | 10,560 | 100% | 90% (77% to 100%) | 4.5 / 6.7 |
   | 20,776 | 100% | 67% (43% to 87%) | 5.0 / 7.5 |
   | 30,716 | 100% | 80% (60% to 93%) | 5.5 / 8.1 |

   - Settings extraction shows no trend with length. Its intervals overlap, and its errors are the hint's smearing,
     as in item 6.
   - Ollama reused the cached prefix, so a 30K-token prompt took about 5 seconds, not the 85 seconds a cold
     prefill would take at about 360 tokens a second.

## What this means for M2 and M6

Claude's reading of the results. Where one touches a decision, the owner decides in the milestone's PR.

- **Model layer (M2).** ChatLiteLLM stays (D11), with `top_p` in `model_kwargs`, `reasoning_effort: "none"` and an
  explicit `num_ctx`. A test checks the captured request, as `options` does here.
- **Forced choices (D9.8, D27).** Use `format` through `with_structured_output(method="json_schema")`, never
  `tool_choice`. The plan's resolution ("if `tool_choice` is ignored, forced choices use a schema-constrained
  `format`") applies, because it is ignored.
- **Never send tools and `format` together.** Each call either offers tools or asks for structured output. Doing
  both produced invented tool results, which is the failure D46's number checker exists for. M2's model layer should
  refuse the combination.
- **The parallel-call split.** Keep the carried fix's behaviour under test in M2. ChatLiteLLM's streaming lost one
  of two calls once in 24; non-streaming calls never did. Calling tools without streaming is the simpler guard.
- **Values the model extracts are not reliable enough to use silently**: 78% to 93% exact, in the best case per
  row. They go to the card as the model's values, with a reason (D26, D37). The user confirms them, as the spec
  already requires. Hints and examples in prompts must not name values: here one leaked into answers. Synonyms
  belong in the schema's descriptions or the tool's validation ("did you mean"), not in the prompt.
- **Flat schemas.** Nested schemas brought no gain here. Flat ones are simpler to validate and to explain in an
  error list (code-review candidate 4).
- **Error envelope (M1).** The typed problems with "did you mean" worked: one rewrite fixed 60 of 60 calls. This
  supports M1's design and D9.9's single rewrite.
- **Budgets (D11).** Nothing here argues for changing the plan's values: `num_ctx` 32,768, reply reserve 4,096,
  verbatim history 12,000. Choices held to 30.7K tokens. S1b measures the catalogue and step-1 budgets.

## Limits

- The cases were written for S1: short, mostly unambiguous, 10 to 20 per experiment. Intervals over so few cases are
  wide. An interval of 100% to 100% means every case passed every run; it does not mean the rate is certainly 100%.
- One machine and one quantisation. The shared instance runs `qwen3.8:27b` on an A100 with 4 parallel slots; its
  results may differ.
- The degradation padding is synthetic search results. Real histories have more varied content.
- The tools were stand-ins with one to two arguments. The Workbench's tools will be larger; S1b runs the
  predecessor's real ones.

## Reproducing

```
caffeinate -i uv run python spikes/S1/s1_mechanics.py --out spikes/S1/runs/s1a --runs 3
caffeinate -i uv run python spikes/S1/s1_mechanics.py --out spikes/S1/runs/s1a --runs 3 --only schemas_plain
uv run python spikes/S1/s1_report.py spikes/S1/runs/s1a
```
