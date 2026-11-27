# S1b: qwen3.8 27B on Ollama, the routing

Spike S1, second part (workbench plan, Phase 1, "S1 qwen3.8 27B on Ollama"; it gates M2 and M6). The first part
is [`S1a-qwen-mechanics.md`](S1a-qwen-mechanics.md).

- Run on 2026-11-27, on the owner's Mac (owner's choice), by Claude.
- Script: `spikes/S1/s1_routing.py`, at the commit that adds this file. Tables: `spikes/S1/s1_report.py`, plus
  `s1_routing.summary()` for the figures the tables leave out.
- 1,410 calls, 3 runs per case, 1.4 hours of model time. That is the main run (1,314 calls) and a rerun of S1a's
  parallel-call experiment (96 calls). The raw calls are not committed.
- Every request went through the capture proxy. Unlike in S1a, it now passes streamed replies on as they arrive
  (`stream_through`). The streamed predecessor replies came in a median of 2 pieces and up to 424.

## Environment

As in S1a:
- Ollama 0.40.16, with `qwen3.8:latest` = `qwen3.8:27b-q4_K_M`, digest `22130167c4c2...`;
- Apple M5 Pro, 48 GB;
- langchain-litellm 0.4.0 with litellm 1.83.0;
- thinking off, temperature 0.7, top_p 0.8 (through `model_kwargs`, S1a item 1), `num_ctx` 32,768.

One exception: #68's own path (`litellm-raw`, below) sets no `num_ctx`, as #68 did not.

## What was run

1. **The predecessor's 36 tool-choice cases**, carried from `stfc/goldilocks-agent` at `ea757c7` with their judges,
   prompt, 8 web tools and recorded goldilocks-core responses (spec D13; `NOTICE`).
   - 19 of them are the cases of stfc/goldilocks-agent#68 (groups R, N, D, M); 17 came later (G, S, V1).
   - 7 prompts were in Chinese and are translated to English. Their "answer in Chinese" checks now ask for English.
     G2 became the same as G1.
   - Three paths:
     - ChatLiteLLM without streaming (`litellm`, our layer);
     - ChatLiteLLM streaming (`litellm-stream`);
     - #68's own path (`litellm-raw`): `litellm.completion`, streaming, with the predecessor's options. Its
       streamed tool-call pieces are joined by index, and a new id starts a new call (the predecessor's split fix,
       6473803).
2. **D27 step-1 picks on 30 goals** written for S1 and labelled by Claude (`s1_catalogue.py`), using S1a's
   forced-choice route (schema-constrained output). Each pick names a recipe or none, and the tools the work needs.
   - The draft catalogue has one line per recipe (D8's five tasks) and per tool (the plan's module table): 51 lines.
   - The long variant adds 30 plausible distractor tools: 81 lines.
   - A pick passes if the recipe is allowed and it includes at least one tool from each required group. Extra tools
     do not fail it; they are counted.
   - The "guided" variant adds one sentence to the prompt: "A recipe is a whole multi-step task; most requests need
     none."
3. **D27 step-1 picks on GENIUS's requests.** These are the 295 request strings of the GENIUS benchmark
   (KIT-Workflows/agentic-workflow-framework at `83e32ac`, MIT), fetched at run time. The text is not committed.
   - A committed keyword rule (`s1_genius.py`, owner's choice) labels them:
     - 181 relaxation (relax or vc-relax, either accepted);
     - 43 single-point SCF;
     - 11 vc-relax;
     - 5 relax;
     - 55 studies that vary a setting (several calculations), left out;
     - 0 it could not place.
   - Not one request asks for bands, DOS or phonons, so this set tests the relaxation and SCF tools only.
   - Expected pick: a database tool (the requests name a formula, and no file is attached) and the label's
     calculation tool; recipe none or Task 1.
   - 20 labels drawn at random (seed 2026) were shown to the owner in the conversation, not on GitHub, for a spot
     check. The owner's verdict is recorded in the PR.

## Answers

1. **The 36 cases still pass, at 96% to 98% by every path.** #68 scored qwen3.8 27B 57 of 57 on its 19 cases
   (2026-11-09); this run's intervals include 100%.

   | path | #68's 19 cases (57 calls) | the 17 later cases (51 calls) |
   |---|---|---|
   | ChatLiteLLM | 96% (91% to 100%) | 98% (94% to 100%) |
   | ChatLiteLLM, streaming | 96% (91% to 100%) | 98% (94% to 100%) |
   | #68's path | 98% (95% to 100%) | 98% (94% to 100%) |

   The 8 failures in 324 calls:
   - 4 answers repeated the parameter card (M2 twice, M7 twice);
   - M7 once called `dft_settings` where the judge wants an answer;
   - G5 once made no tool call;
   - S7 and S7b each once gave `dft_set` wrong arguments.

   Prompts ran to a median of 3,239 tokens for the first group and 6,414 for the second, which carries the review
   results.
2. **The parallel-call split is not needed with litellm 1.83.0.** With streamed replies now passed on as they
   arrive, S1a's parallel experiment gave two clean calls in 96 of 96 replies:
   - 24 of 24 per client, streamed or not;
   - none merged, none missing.

   S1a's one missing call under its buffered proxy did not recur. In the predecessor cases, no reply on #68's path
   held two calls, so the split never changed a count there.
3. **Step 1 picks the right tools, but names a recipe too readily.** The 30 goals (90 calls per row):

   | catalogue | prompt tokens (median) | pass | recipe right | tools right | extra tools per pick |
   |---|---|---|---|---|---|
   | 51 lines | 955 | 64% (49% to 79%) | 58/90 | 89/90 | 1.19 |
   | 81 lines | 1,303 | 56% (40% to 71%) | 51/90 | 88/90 | 1.51 |
   | 51 lines, guided | 969 | 94% (88% to 99%) | 85/90 | 90/90 | 0.69 |

   - Almost every failure named a recipe for a one-tool request: Task 1 for "Cancel the band structure job", or the
     screening funnel for "Rank these finished candidates".
   - One sentence in the prompt fixed most of it.
   - The longer catalogue did not hurt tool recall. Its only distractor ever picked was `report.write` (20 calls),
     a plausible choice for tasks that end in a report.
4. **On GENIUS, step 1 picks the right calculation, but not a database.** 720 calls:
   - **The calculation tool was picked in 712 (99%):**
     - relaxation 542 of 543;
     - single-point SCF 129 of 129;
     - relax 15 of 15;
     - vc-relax 26 of 33; the other 7 picked relax, for requests that need the cell to move.
   - **A database tool was picked in only 256 (36%).** The rate was 73% for the short single-point requests and
     27% for the relaxation requests, most of which describe the cell, space group and atom counts.
   - **Opening a file the user gives (`dft.open_structure`) was picked in 681 (95%),** though no file is attached.
   - **With a database tool required, as labelled, the pass rate is 32% (28% to 36%).**
   - **Recipes:** Task 1 was named in 699, and magnetic screening in 21, all for total-magnetisation requests.
   - **Over-picking:** each pick named 6.1 tools, 4.5 of them beyond the labelled groups, most often `dft.set`
     (703), `dft.review` (674), `aiida.job_status` (306) and `aiida.diagnose` (171).

## Token sizes measured

Counted by Ollama's own tokenizer:

| what | tokens |
|---|---|
| the predecessor's system prompt | 413 |
| its 8 tool schemas, as JSON | 2,034 (about 254 per tool) |
| the draft catalogue | about 865 for 51 lines (17 a line); about 1,190 for 81 lines |
| the predecessor's tool results | 9 distinct: five reviews of 2,867 to 2,923; four others of 70 to 458 |
| the longest model reply in S1a and S1b | 372 |

## What this means for M1, M2, M6 and the budgets

Claude's reading of the results. Where one touches a decision, the owner decides in the milestone's PR.

- **The model layer (M2)** can call tools with or without streaming. The split fix need not be carried as code; a
  test of two parallel calls under real streaming guards it instead.
- **The step-1 prompt (M6, D27)** must say that a recipe is a whole task and that most requests need none. Without
  that sentence, step 1 named a recipe for most one-tool requests. The checker (D9) should also refuse a recipe
  whose first step the request does not need, rather than trust the pick.
- **The structure source.** Step 1 seldom plans to fetch a structure from a database when the request names only a
  formula. It plans to open a file the user has not given. The checker can add Find in Databases, or the card can
  ask, when a plan's calculation has no structure source. The step-1 prompt can also say that the user has
  attached no file, when none is attached. Whether a request that describes a cell should search a database or build
  the cell is a design choice. This run does not settle it.
- **vc-relax vs relax.** When a request needs the cell to move, step 1 chose relax in 7 of 33 picks.
  goldilocks-dft's task and the card's review should decide this, not step 1 alone.
- **Over-picking.** GENIUS picks named 6.1 tools on average, for a request that needs 2. At about 254 tokens a
  tool, step 2 would show about 1,550 tokens of interfaces: within the plan's 4,000-token step-2 budget, but most of
  it unneeded. Code can drop picked tools that the chosen recipe or calculation does not use.
- **Budgets (D10, D11; the plan says S1 calibrates them):**
  - **Catalogue:** at most 1,300 tokens instead of 2,000, the longest catalogue measured here (81 lines, about
    1,190 tokens). Tool recall held to that length; nothing longer was tested. A longer catalogue needs a new
    measurement before the budget grows. At about 17 tokens a line, ≤ 40 per line stays as planned.
  - **D10's output cap stays at 1,200 tokens.** The predecessor's review results are about 2,900 tokens, and the
    cases that carry them passed at 98%. So the model can read larger results, and the cap is not needed for
    accuracy. A larger cap would fill the 12,000-token verbatim history after four results.
  - **The other values stand, on S1a's and S1b's evidence:**
    - `num_ctx` 32,768;
    - reply reserve 4,096 (the longest reply was 372 tokens);
    - system prompt ≤ 1,500 (the predecessor's is 413);
    - step-2 prompt ≤ 4,000;
    - verbatim history ≤ 12,000.

    S1 did not measure the skills, router, checkpoint and chat-turn budgets; they stay as planned.

## Limits

- **The labels are Claude's.** The 30 goals and the GENIUS rule were written for S1. GENIUS's requests are all
  relaxation or SCF, so its coverage of the catalogue is narrow.
- **The database expectation for GENIUS is a choice.** The requests do not say where the structure comes from; the
  32% depends on it, and the 99% for the calculation does not.
- **The guided prompt was written after the base prompt's failures were seen,** on the same goals. Its 94% is an
  upper estimate for that wording.
- **The 36 cases are the predecessor's chat tools,** not the agent's planning tools. They test tool choice in
  conversation with real tool schemas and recorded results.
- **One machine and one quantisation,** as in S1a.

## Reproducing

```
caffeinate -i uv run python spikes/S1/s1_routing.py --out spikes/S1/runs/s1b --runs 3 --only predecessor,catalogue,genius
caffeinate -i uv run python spikes/S1/s1_routing.py --out spikes/S1/runs/s1b-parallel --runs 3 --only parallel
uv run python spikes/S1/s1_report.py spikes/S1/runs/s1b
```

The first GENIUS run fetches the requests into `~/.cache/goldilocks-spikes/` and checks their sha256.
