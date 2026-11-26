# Plan: Goldilocks Workbench, first version (workbench)

From: `intent.md`, `spec.md` (same folder). Size: large (v4-process D8). Status: accepted by the owner in plan mode
on 2026-11-26 (v4-process D5, gate 3). Committed as `changes/2026-11-25-workbench/plan.md`, the first commit of
the first implementation PR; it may change until the last implementation PR merges (v4-process D4). Work happens in the fork `junwen94/goldilocks-workbench`, with PRs inside the fork; how `main`
reaches `ddmms/goldilocks-workbench` is the owner's call.

References: "D*n*" is a decision in this change's spec; "v4-process D*n*" is one in `ddmms/goldilocks`
`changes/2026-11-24-v4-process/spec.md`; "hook *n*" is item *n* of the roadmap's "Hooks the first version keeps";
a "candidate" is an item from the code review of 40 agents. Large changes keep their decisions in the spec, so
this plan has no Decisions section; where the spec leaves a choice to the plan, "Spec items resolved here"
settles it.

## Context

**Why.** The predecessor runs both editions from one hand-built graph, its local agent loop was never built, and
the `stfc` repositories are retiring (intent). The spec (D1–D53, accepted 2026-11-25 in
junwen94/goldilocks-workbench#2) designs three forms in one repository. This plan builds the first version.

**What the first version is**
1. **goldilocks-agent**: a Deep Agents agent that runs D8's five tasks end to end with qwen3.8 27B on Ollama
   (D11). Every calculation goes through AiiDA (D4, D43). Quantum ESPRESSO first; VASP, CP2K and CASTEP as
   goldilocks-dft delivers them (D22). Shipped as a container image and a macOS app (D20, D21).
2. **goldilocks-chat, after the agent**: the light `create_agent` form (D3), reusing the agent's shared tools and
   frontend components. It replaces the website only when it matches the old site (same tools, end-to-end tests
   passing); until then the site keeps the `stfc/goldilocks-agent` image (D13).
3. **goldilocks-Ada is not built** (D2, D19).

**Owner's decisions for this plan** (2026-11-25/26; quotes translated from Chinese by Claude)
1. Order: goldilocks-agent first, goldilocks-chat after.
2. D7's private reference data and scoring definition live in the private `ddmms/goldilocks`; evaluation runs build
   LangSmith datasets from there. This repository holds only public tasks.
3. LICENSE: BSD-3-Clause, "Copyright (c) 2026, UKRI Science and Technology Facilities Council". Code carried over
   from `stfc/goldilocks-agent` keeps its notice ("Copyright (c) 2026, Junwen Yin") in `NOTICE`; each carried file
   cites its source commit (D13).
4. Phonon routes for task 1: Quantum ESPRESSO by DFPT (ph.x, q2r.x, matdyn.x); VASP by finite displacements
   (aiida-phonopy over aiida-vasp, with D53's LO-TO correction); **CP2K has no phonon route** in the first
   version; **CASTEP is decided when its route is built**. D53's rule applies to the phonon routes that exist.
5. Division of labour with goldilocks-dft: "goldilocks-dft generates parameters; it does not execute, so it does
   not need aiida-phonopy; only the agent needs the AiiDA plugins", and "put the translation layer into dft".
   goldilocks-dft returns plain data: parameters with sources, phonon supercell and displacement settings,
   Born-charge settings, and parameter tables shaped for each AiiDA plugin. It imports no AiiDA package and runs
   nothing. Every AiiDA plugin (aiida-quantumespresso, aiida-vasp, aiida-cp2k, aiida-castep, aiida-phonopy,
   aiida-mlip) and every execution lives in this repository.
6. Skill scripts in D29's sandbox may use the network by default (owner's choice over Claude's recommendation of
   deny-by-default). D29's other limits stand.
7. Local MLIP calculations through aiida-mlip need no approval of their own; they count against the plan card's
   caps (jobs, wall time), and going beyond a cap asks, as D25 does for HPC jobs.
8. User-interface languages: keep all five (English, French, German, Chinese, Italian). UI translation string files
   are the one exception to the English-only rule; everything else stays English.
9. DFT GUI (D12): settings forms are generated from goldilocks-dft's published capabilities, so both GUIs always
   show the same settings; the structure, magnetic-orderings and bundle cards are ported from goldilocks-core's
   `web/` components and adapted (same copyright holder, BSD-3-Clause; each ported file cites its source commit).

**Not in the first version**
- goldilocks-Ada (D2, D19); adaptive selection and streaming funnels (D8).
- MLIP equations of state, NEB and phonons (aiida-mlip lacks them, D43); MLIP molecular dynamics beyond a reserved
  input block (hook 12); ab initio molecular dynamics (goldilocks-dft, later; D37).
- CP2K phonons; CASTEP phonons until decided (owner's decision 4).
- Spin-orbit coupling and non-collinear magnetism (fields recorded, nothing computed; hook 1); partially occupied
  structures (a typed "needs ordering" state only; hook 11); charged cells (setting reserved and refused; hook 8).
- MLIPs other than MACE (D41); MLIP committees (T04-01); a model reviewer at run time (D45); a durable-execution
  engine (D33); a submission ledger (D17); killing jobs early or monitors of our own (D17.6).
- Canary or smoke runs (T08-06; the AiiDA dry run and the wizard's test job stay); packing small jobs (T08-04);
  reverting a task; resource estimates calibrated on past runs (allowed by D22, later).
- Our tools over MCP (roadmap) and outside MCP servers as tools (Open); installing DFT codes (D47); shipping VASP,
  CASTEP or POTCARs; general web search and browser automation (D35, D49).
- Memory in chat and user accounts on the shared instance (D51; T07-06); Windows and Linux desktop builds (X-03);
  a CUDA image; cluster set-up by a model (later); the skills marketplace's design (D40's record).

**Facts this plan relies on** (checked 2026-11-25, or 2026-11-26 where marked)
- This repository: the fork's `main` holds `README.md` and `changes/2026-11-25-workbench/{intent,spec}.md`; no
  LICENSE, `AGENTS.md`, `REVIEW.md` or check. `ddmms/goldilocks-workbench` holds a README only.
- `stfc/goldilocks-agent` @ `ea757c7`: FastAPI with SSE frames (`tool_status`, `tool_result`, `dft_draft`,
  `confirmation_needed`, `[DONE]`); a two-node LangGraph graph with fixes c7bfc57 (one tool call per node run),
  5a037d8 (orphaned tool-call repair), 6473803/#149 (Ollama parallel calls split by id), 22e6ee8/997558e/09a3da3
  (qwen thinking off), edcb5ee (single system message), b345ffe/#151 (tool budget with wrap-up); litellm; SQLite
  (AsyncSqliteSaver plus revisioned DFT drafts); goldilocks-core over HTTP only, pinned 0.3.3; 13 tools (2
  database, 5 MLIP through a `janus` subprocess, 6 DFT); React 19 + Vite 8, `App.tsx` 10,878 lines; 185 pytest,
  34 vitest, 18 manual Playwright tests; no auth and no thread-ownership checks on the website; five UI languages
  inside `App.tsx` (2026-11-26); `app/public/phonon/` is a third-party build without a licence file (2026-11-26).
- goldilocks-core @ `junwen94/goldilocks-core` main `a6d4c19` (0.3.3): HTTP `/capabilities`, `/inspect`, `/explain`
  (200 even when blocked), `/run`, `/magnetic-orderings` (ranking jobs in memory), `/health`, `/ready` (503 until
  assets are installed); Quantum ESPRESSO only; native input text only; per-file sha256 manifests for SSSP 1.3.0
  and PseudoDojo 0.4; human > ml > llm > heuristic with no LLM channel (#258 open); provenance without rule ID or
  version; orderings from enumlib (spinforge in #310, open); no per-site spins in records; MCP stdio only
  (#302–#304 open); base dependencies include goldilocks-ml (torch, mace-torch).
- `ddmms/goldilocks-dft` and `ddmms/goldilocks-skills` exist and are empty; D18's and D40's records are not
  written (2026-11-26).

**Dependencies on other repositories**

| Where | What the Workbench needs | Milestones that wait |
|---|---|---|
| `ddmms/goldilocks-dft` (through D18's record) | the ordered list in "goldilocks-dft dependencies" | M6, M9, M16, M20–M23 |
| `ddmms/goldilocks-skills` (through D40's record) | the official skills below, a skill lint, tagged commits to pin | M12, M13, M16 |
| `ddmms/goldilocks` (private) | D7 reference data, scoring file, leak list, shared-instance deployment and rollback notes, D18 and D40 records | M16, M19 |
| Owner's settings and accounts | ruleset (owner approval, required `check` and `review-comment`) and secret scanning on the fork and ddmms; GHCR and PyPI names; Apple Developer membership; LangSmith organisation and key | PR 1, M10, M16, M17 |

## Files that change

All paths in this repository; representative files, not every one.

```
LICENSE  NOTICE  AGENTS.md  REVIEW.md  README.md
changes/2026-11-25-workbench/plan.md
changes/2026-11-25-workbench/spikes/S1-qwen.md … S9-desk-notes.md   written spike results
pyproject.toml  uv.lock                uv workspace root (members packages/*), ruff, mypy, pytest
budgets.toml                           D10 output caps, D11 size budgets
tools/check.sh                         the single check (v4-process D22)
tools/lint-records.sh                  records lint, ported from ddmms/goldilocks; lint-records-fixtures/ test it
tools/checks/                          import_boundary.py, chat_env.py, registry_sync.py, budgets.py, examples_offline.py,
                                       english_only.sh (exempts frontend/packages/ui/i18n/*.json), notice.sh,
                                       md_links.sh, test.sh (tests the shell checks),
                                       no_tracing_defaults.py, frontend_types_sync.py, leaks.py
.github/workflows/                     check.yml (Linux, macOS), review-comment.yml, images.yml, desktop.yml (manual),
                                       weekly-live.yml (D10 live sweep; never gates), dependabot.yml
packages/workbench/src/goldilocks_workbench/      shared part (D1)
  contracts/  registry/  dispatch/  models/  server/  store/  dft_client/
  modules/{find_in_databases,structure_builder,dft,literature}/
packages/chat/src/goldilocks_chat/                agent.py (create_agent), middleware.py, profile.py, server.py, retention.py
packages/agent/src/goldilocks_agent/
  agent.py                             create_deep_agent: driver, tools, skills, sandboxed shell, memory
  planner/  executor/  runs/  watcher/
  aiida/                               owner thread, profile, wizard data, codes, routes/<code>/ (builders from
                                       goldilocks-dft's plugin-shaped tables), checks/
  mlip/  post_analysis/  skills/  sandbox/  memory.py  update.py  doctor.py  cli.py
packages/agent/mlip-env/               isolated janus environment, if S5 shows it is needed
frontend/                              npm workspaces
  packages/types/                      TypeScript generated from the Pydantic contracts
  packages/ui/                         chat shell, card renderer, panel frame, viewer, sanitised Markdown;
                                       i18n/{en,fr,de,zh,it}.json (owner's decision 8)
  packages/modules/                    each module's panel and cards; registry.gen.ts generated from the backend
  apps/chat/  apps/agent/  e2e/
desktop/                               Electron shell: main, preload, first-launch installer, updater
deploy/agent/  deploy/chat/            Dockerfiles, compose; shared-instance settings live in ddmms/goldilocks
evals/                                 public tasks, fetchers (CompMat-Bench C06/C07, GENIUS request strings),
                                       arm configurations, runner, code evaluators, schema of the private scoring file
fixtures/                              recorded goldilocks-core responses, recorded pw.x/ph.x/q2r.x/matdyn.x outputs
                                       for replay stand-ins, recorded model replies
spikes/                                scripts behind the spike results (not packaged)
docs/developer/                        adding a tool or recipe, with a developer skill
```

**Package boundaries (D1)**

| Package | Holds | Depends on | Never imports |
|---|---|---|---|
| goldilocks-workbench | contracts, registry, dispatch, model layer, server kit, store, goldilocks-dft client, light modules | langchain-core, langgraph, langchain-litellm, fastapi, pydantic, ase, pymatgen, mp-api, httpx | goldilocks_chat, goldilocks_agent, deepagents, aiida, torch, janus_core |
| goldilocks-chat | light agent, chat server | goldilocks-workbench, langchain (`create_agent` and middleware) | all of the above, any shell |
| goldilocks-agent | Deep Agents, planner, executor, watcher, AiiDA/MLIP/Post Analysis modules, skills, sandbox | goldilocks-workbench, deepagents, aiida-core 2.9 (pinned in PR 2, before S2; see below), aiida-quantumespresso, aiida-pseudo, aiida-mlip 0.3.0 (see below); later aiida-vasp, aiida-cp2k, aiida-castep, aiida-phonopy | goldilocks_chat; goldilocks_core/goldilocks_dft (HTTP only) |
| goldilocks-dft | not in this repository; own environment and process; returns plain data, including plugin-shaped tables; imports no AiiDA (owner's decision 5) | — | — |

**aiida-core and aiida-mlip versions (PR 2, 2026-11-26)**

- **aiida-core 2.9.** The built-in ZeroMQ broker came with AiiDA 2.9 (D21.3; the facts under D20). On 2026-11-26 the
  owner kept SQLite with the ZeroMQ broker: "We use ZeroMQ + SQLite; base the decision on this." (Translated from
  Chinese by Claude.) No further reason recorded. The other way round, aiida-core 2.7 with aiida-mlip 0.5.0, would
  lose that broker. S2 tests the pinned version.
- **aiida-mlip 0.3.0 from PyPI**, the newest release that installs with aiida-core 2.9 (checked 2026-11-26).
  aiida-mlip 0.5.0 requires `aiida-core~=2.7.4`, and 0.4.1 requires aiida-workgraph 0.7, which requires aiida-core
  below 2.8. D41's and D43's facts describe janus-core 0.9.9 and aiida-mlip 0.5.0; 0.3.0 brings instead:
  - janus-core below 0.8 (0.7.6 in the lock);
  - numpy below 2 for the whole workspace, chat included, because janus-core 0.7.6 and aiida-workgraph 0.5.3 both
    require it;
  - aiida-workgraph 0.5.3, which does not import with aiida-core 2.9.4 (its dependency aiida-pythonjob 0.2.5 imports
    `get_stack_size`, which aiida-core 2.9.4 does not have), so aiida-mlip's `ht_workgraph` workflow cannot be used.
    Its calculations and data types load; `packages/agent/tests/test_dependencies.py` checks that.
- **Weighed and not taken: a git source** for aiida-mlip pinned to commit 0a7becb on its main branch. Main requires
  `aiida-core~=2.8` since commit 3e10f0a (its `pyproject.toml` still says version 0.5.0), and 0a7becb resolves with
  aiida-core 2.9.4, janus-core 0.9.9, aiida-workgraph 0.9.0 and numpy 2. It would remove the three costs above, at the
  price of depending on unreleased code; it was not installed or imported. The owner chose 0.3.0 from PyPI on
  2026-11-26; no reason recorded.
- **Move up** when an aiida-mlip release supports aiida-core 2.9 (ddmms/goldilocks-workbench#2). The owner,
  2026-11-26: "Remember to open an issue: upgrade aiida-mlip later, because we want to use ZeroMQ." (Translated from
  Chinese by Claude.) S5 tests the version pinned then.

**Tool modules in the first version (D6, D10, D12)**

| Module | Package | Forms | Tools |
|---|---|---|---|
| Find in Databases | workbench | chat, agent | search (Materials Project with the user's key, OPTIMADE, JARVIS cache), get structure |
| DFT | workbench | chat, agent | open structure, review, settings, set (human values; LLM values once goldilocks-dft has the channel), bundle download (chat), capabilities |
| Structure Builder | workbench | agent | D15's operations, magnetic orderings from goldilocks-dft, identity check |
| AiiDA | agent | agent | long steps (SCF, relaxations, bands, DOS/PDOS, phonons, convergence scans); read-only job and group queries; failure diagnosis; cancel (destructive, approved each time) |
| MLIP | agent | agent | single point, geometry optimisation, descriptors, batch pre-screen |
| Post Analysis | agent | agent | gap and bands, DOS, phonon analysis, convex hull (one method signature), symmetry classification, ground-state ranking (aware of D52), MLIP-against-DFT errors, multi-objective ranking, D16 comparator |
| Literature | workbench | agent | search works, get work, acquire open-access text, index search, verify quote, resolve citations |

The agent's own tools: planner, `start_run`, history fetch, sandboxed shell, memory.

**Official skills the first version needs** (in `ddmms/goldilocks-skills`, rewritten after AtomisticSkills'
designs where one exists, fixed parameterised scripts only, pinned by commit): MLIP pre-screen (task 2); MLIP
validation conventions (task 3); reading DFT results (task 1); reading magnetic orderings and D52 marks (task 5);
convergence-study practice (task 4); literature queries (D49); units and conventions (all).

**Process files**
- `AGENTS.md`: the check at the top with a healthy run; the shared rules from ddmms/goldilocks (Change records,
  Pull requests, Only the owner, Never); and this repository's rules: no code, prose or assets copied from other
  projects (D23), except Goldilocks's own repositories, whose ported files cite their source commit (owner's
  decision 9); carried files keep NOTICE (D13); physics values come only from goldilocks-dft, calculations or the
  user, and every threshold names its source; tools enter only as registry modules with examples and a return
  schema; no LLM call inside a tool (D11); chat never imports agent code, Deep Agents, AiiDA or MLIP packages and has
  no shell (D1, D35); shipped configurations never set LangSmith variables (D48); no native input files (D37);
  nothing private (no D7 details or data, no deployment details); English only, except UI translation files.
- `REVIEW.md` high-risk paths: category 1 (physics) `packages/agent/**/{aiida/routes,aiida/checks,mlip,post_analysis}/**`,
  `**/structure_builder/**`, `**/units*`, `**/checks/*.toml`, `**/dft_client/pin.json`, `evals/scoring/**`;
  category 2 (external contracts) `**/server/**`, `frontend/packages/types/**`, `**/cli.py`, the research-record
  schema, the D31 format, the task-package format; category 3 (security and deployment) `**/server/security.py`,
  `**/server/pauses.py`, `packages/agent/**/{sandbox,executor/caps.py,aiida/profile.py}`, `**/config.py`,
  `deploy/**`, `desktop/**`, `.github/workflows/**`, dependency declarations; category 4 `AGENTS.md`, `REVIEW.md`,
  `tools/**`, `budgets.toml`, `changes/**`, `docs/developer/skills/**`; category 5 `**/store/**`,
  `packages/chat/**/retention.py`, `packages/agent/**/memory.py`, task-folder and record writing and deletion,
  AiiDA profile creation and migration.

## Order of work

**How each PR works.** One PR per heading below (a milestone may be several PRs of under ~800 changed lines,
excluding generated and carried files). Claude opens each PR with a v4-process D11 description, the high-risk
categories and the pasted check output; the owner runs `goldilocks-review`, approves and merges. Spikes come
first: a script under `spikes/S<n>/` and a written result under `changes/2026-11-25-workbench/spikes/`. A spike
result that contradicts a spec decision stops the dependent milestones and goes to the owner as a new record.

**Gates**: S1 before M2's model layer is final and before M6; S2 before M5; S2, S3 and S4 before M8; S5 before
M11; M9 end to end on the replay tier before M10's first image; M18's parity before M19; goldilocks-dft deliveries
before M20–M23. If the first version cannot carry all five tasks, M15 (task 4) moves later first (D8); if four
codes delay it, codes are staged with VASP first (D22).

### Phase 0: foundations
**PR 1: Foundations** (category 4). `plan.md` first; LICENSE, NOTICE (header), `AGENTS.md`, `REVIEW.md`, README; a
minimal check (records lint, English-only with the i18n exemption, NOTICE consistency, Markdown links, and tests
of these checks) and `check.yml`; `.gitignore`; `review-comment.yml` (on each review event, sets the required
commit status `review-comment` on the PR's latest commit: success if the PR has a `goldilocks-review` review of that
commit by the owner, a member or a collaborator, failure otherwise; no model call; v4-process D19's fallback for the
new public repositories). Implements D14, D23; v4-process D9, D17, D18, D21, D22. Proof: check ends
`check: all passed`; CI green; the owner then sets the ruleset and secret scanning, and confirms that a
`goldilocks-review` review unblocks the merge, also after an earlier review of the same commit set the status to
failure. It was first built as a check run that also ran on pushes; on PR 2 its failed run stayed beside the passing
one and kept the merge blocked, and a follow-up PR made it a commit status, of which the latest counts.

**PR 2: Workspace and full check** (categories 3, 4). uv workspace with three empty packages and entry points; two
blank Vite apps; the full check (lock, ruff, mypy, pytest, import boundary, chat environment, eslint, strict tsc,
vitest, vite build); macOS CI. Implements D1. Proof: one lock resolves aiida-core, aiida-quantumespresso,
aiida-pseudo, aiida-mlip, deepagents, langchain-litellm and FastAPI together; after `uv sync --package
goldilocks-chat`, `chat_env.py` finds no torch, aiida, deepagents or janus_core; a planted import of
`goldilocks_agent` from `goldilocks_workbench` fails; green on Linux and macOS.

### Phase 1: spikes
- **S1 qwen3.8 27B on Ollama** (gates M2, M6). Schema-constrained choices (Ollama `format`) through ChatLiteLLM and
  ChatOllama; whether `tool_choice` is honoured; tool calls with structured output in one request; whether the
  parallel-call split is still needed; flat vs nested schemas; robustness (missing, extra, mistyped arguments; one
  rewrite from the error list); routing on the predecessor's 19 tool-choice cases (translated), GENIUS's 295
  request strings (fetched at test time from a pinned commit with a checksum, never committed) and D27 step-1
  picks on a draft catalogue; degradation at 8K/16K/24K context; whether temperature, `num_ctx` and thinking-off
  reach Ollama (captured requests). 3 runs per case, bootstrap intervals, Ollama version and quantisation recorded.
  Pass: written rates, the forced-choice route, calibrated budget values. If schema-constrained choices are
  unreliable, stop and take D7's and D11's revisit clauses to the owner.
- **S2 AiiDA on the desktop** (gates M5, M8): profile on macOS arm64 and in the Linux container with SQLite and the
  built-in ZeroMQ broker, on aiida-core 2.9 as pinned in PR 2; daemon control from the app; `call_on_process_finish`
  from a FastAPI process for finished, excepted and killed states; polling fail-safe with the broker stopped; laptop
  sleep; caching (identical CalcJobs hit; a `prepend_text` version change misses; which aiida-quantumespresso exit codes
  invalidate); CalcJob monitors available (observe only); storage-thread binding and ToolNode threads. Pass: 20/20
  broadcast wakes within seconds; fail-safe wakes within the poll interval with the broker blocked; caching facts
  written.
- **S3 submission key through aiida-quantumespresso** (gates M8, M9): store the key at node creation (reserved
  prefix in `metadata.label`; extras only if settable at creation); kill between `submit()` and the checkpoint and
  find the node by key; what a created-but-never-sent node looks like ("needs check"); build a builder from
  goldilocks-dft's (or, interim, goldilocks-core's) parameters, dry-run it (`store_provenance=False`) and compare
  value by value; list PwBaseWorkChain handlers; whether a retry can turn caching off for itself. Pass: key route
  written; 0 duplicates in 20 kill trials; handlers mapped to the repair table.
- **S4 interrupts and resume through our server** (gates M7): `interrupt()` in a tool of the Deep Agents loop
  surfaces as a card on our SSE stream and resumes with `Command(resume=...)`; the same inside a subgraph run from a
  separate executor thread; both after a real OS restart (SIGKILL, new process, AsyncSqliteSaver); how Deep Agents
  reads a skills directory and whether skill state survives a resume; whether HarnessProfile is public API. Pass:
  20/20 on all resume paths with a scripted fake model.
- **S5 aiida-mlip with MACE** (gates M11), on the aiida-mlip version pinned then (0.3.0 with janus-core 0.7.6 in PR 2;
  see "aiida-core and aiida-mlip versions"): install on macOS arm64 (CPU, MPS) and in the container (CPU wheels);
  whether the `janus` executable can run from an isolated environment as a localhost AiiDA code; float32 MPS vs
  float64 CPU on energies, forces and relaxed volumes for a public set; install size and time; checksummed weights.
- **S6a, S7, S8, S9 desk checks** (one PR): S6a per-site moments parsed by aiida-quantumespresso (names, units,
  integration method) → D52's QE reader; S7 aiida-vasp's Born-charge and dielectric outputs vs aiida-phonopy's
  `nac_parameters` (units, axes, atom order; real test in M21); S8 whether aiida-vasp stores POTCAR contents in the
  AiiDA repository (hook 4); S9 aiida-hyperqueue maturity (T08-04), the monitoring AiiDA and the plugins provide,
  whether aiida-cp2k and aiida-castep have protocol builders.

### Phase 2: shared foundation
**M1 Registry and tool contract** (category 2). The Value record (number, unit, evidence kind, optional
uncertainty, accuracy target; missing never zero); typed results and an error envelope (`retriable`,
`next_steps`, also for returned errors); the registry as data (IDs `source:name`, versions, hashes, typed I/O with
units, side-effect class, output cap, origin, tags, availability, examples, return schema); one validate-before-
execute dispatch path (`extra="forbid"` with "did you mean" hints; JSON-type conversion only, never under `anyOf`,
never between units; no second call after an error; null results refused); error middleware that re-raises
LangGraph's interrupt; valid-JSON output caps with a pointer to the full result; catalogue and per-form profiles
generated from the registry; `budgets.toml` with a Qwen-tokenizer check; the offline examples gate; a module
scaffold command and developer skill. Implements D6, D10, D11, D27. Hooks 7, 14. Proof: a test per validation
rule; a tool without examples or return schema fails check; an over-budget prompt fails; adding a module changes no
dispatcher; a tool importing the model layer fails.

**M2 Model layer, server kit, store** (categories 2, 3, 5). ChatLiteLLM with roles (driver, router, planner; all
qwen3.8 27B by default), explicit `num_ctx`, thinking off, recorded-reply mode, per-role call and token counters
always on with a local event log, an outage state, a self-refreshing credential option; the carried fixes as
middleware (orphan repair, single system message, parallel-call split); typed SSE frames plus card frames; the
pause and card protocol (pause ID, kind, typed payload; CatMaster-style strict validator; text typed at a pending
card counts as a rejection with feedback); security (localhost, per-launch token, Host and Origin checks, CSP,
sanitised Markdown, bundled assets); store (owner and project keys with one default each, schema version,
migrations, 0600 files, AsyncSqliteSaver with `pickle_fallback=False` on one loop); notifier and one status.
Implements D3 (card contract), D11, D21.6, D33.4. Hooks 5, 13, 17, 18. Proof: carried fix tests pass under
middleware; a stale pause ID is refused; requests without token or with foreign Host/Origin refused; a fake outage
shows the outage card and resumes; counters count retries. Waits on S1.

**M3 Shared tools carried over** (category 2; 1 for Structure Builder). Find in Databases carried (Materials
Project records filled by code; typed structure requests; database text untrusted); the goldilocks-dft client
carried with its version gate, a runner for its own environment, `/ready` 503 shown as install progress; the DFT
module carried (revisioned drafts, 409 on conflict, all errors at once with closest keys, `error.kind` matching,
bundle path guards, review card with each value's source); Structure Builder (typed operation union with versions,
generator/version/seed/space group/parent-site mapping recorded, spglib before and after, short-contact check fails
the step, identity checks, occupancies kept with "needs ordering", moments as µB site properties, orderings from
goldilocks-dft). Implements D12, D13, D15, D50. Hooks 11, 19 (database part). Proof: carried suites pass against
recorded core fixtures; an identity mismatch stops the workflow; a seeded substitution repeats exactly; weekly live
sweep set up.

**M4 Frontend foundation** (category 2). Shared UI package, generated types, the five UI languages carried into
`i18n/` (owner's decision 8); panels and cards for Find in Databases, DFT and Structure Builder: DFT settings forms
generated from goldilocks-dft's capabilities; structure, magnetic-orderings and bundle cards ported from
goldilocks-core's `web/` (cite the commit; owner's decision 9); a viewer comparison (WEAS carried, MatterViz, 3Dmol:
frames, room for moment arrows, size, licence, offline bundle; WEAS stays unless MatterViz wins). Implements D12,
D21.6. Hook 16 (viewer that plays frames). Proof: eslint, strict tsc, vitest pass; types in sync; Playwright smoke
of both apps on the recorded-reply model; check finds no `dangerouslySetInnerHTML` and no CDN URLs.

### Phase 3: the agent's core, on Quantum ESPRESSO
**M5 AiiDA module foundation** (categories 3, 5). One owner thread holding the profile and running every AiiDA call
through a queue (graph state holds UUIDs only); profile creation (SQLite, ZeroMQ broker, caching on) and daemon
control; wizard data (computer templates with publicly documented settings plus a per-user part, SCARF first;
codes from a local path, `module load` or an HPC path, never installed; `core.direct` workstations; a test job per
set-up); one Code per code version (version in `prepend_text`); job options from goldilocks-dft's estimate,
clamped to the computer's limits; extras on every process (thread, step, tool call, plan, parameter source); one
group per task; read-only failure diagnosis; a doctor (profile, daemon stopped/zero workers/busy, broker round-trip
broadcast, transport, codes, pseudopotential families against goldilocks-dft's per-file checksums, model reachable);
the AiiDA panel; storage policy (remote folders kept for the plan's lifetime; cleaning is destructive).
Implements D4, D21.3, D21.5, D39, D43, D47. Hooks 3, 5, 17. Proof: integration tests on a test profile; the wizard's
test job on a stand-in code; the doctor detects a stopped daemon, zero workers and a dropped broadcast; a wrong
pseudopotential checksum is refused; S2's caching tests pass. Waits on S2.

**M6 Plans and the plan card** (category 3). Plan schema (steps by registry ID; inputs as literals, output
references or AiiDA UUIDs; branch points with allowed next steps; caps; a recipe is a plan with open slots and no
parameter values); the checker (tools exist and are enabled; types and units match; no bound check removed; DFT
settings only ones goldilocks-dft knows, each LLM value with a reason; UUIDs in the task's group; within caps
computed from goldilocks-dft's estimates); the D27 planning graph (schema-constrained catalogue pick → chosen
interfaces → plan → check → one rewrite → pause); the seven-part card (goal; system; steps as a graph; parameters
with source and reason; pseudopotentials; estimate and caps: jobs, compute time, model calls, wall time, local
MLIP jobs, room for GPU hours; code, computer, warnings, risks); D26 edits as human values, warnings below the
recommendation naming its source, re-check against caps; approval only from the interface, storing the plan hash
and each job's input digest; D31 receipts, answers files and the fixed responder; `start_run(plan_id)` loading the
approved document and checking its hash. Implements D9.2–9.4, D25, D26, D27, D31, D34.1, D37. Hooks 14, 15.
Proof: D25 cap tests; no model tool can answer an approval; D31 stale answer; a test per checker rejection; step-1
picks on the recorded set meet S1's bar. Waits on S1.

**M7 Executor, background runs, research record** (categories 2, 5). One fixed interpreter graph that reads the
approved plan from its state: select next step; run (long steps as subgraphs); check; branch (router picks among
allowed next steps, code's choice is the default, router skipped when inputs are fully determined); fan out per
candidate in strict rounds; pause in nodes that only call `interrupt()`. Caps checked before every submission.
Background threads `uuid5(parent thread, tool call)`, one turn at a time per conversation with a queue. The D36
record (header: schema version; app, goldilocks-dft, plugin and model versions with quantisation; UUIDs; parent
run; skills and recipes with hashes; user files with checksum and origin; licensed/private flags; code-written
events). Code-written step summaries and a history tool; stuck detection; invalid output → errors, one rewrite,
then pause; D42 revisions shown as a diff with finished steps kept; finishing decided by code and confirmed by the
user; an entry point with no model (plan in, record and UUIDs out, approval as an answers file). Implements D9.5,
D9.8–9.12, D34, D36, D42. Hooks 4, 9, 15, 18. Proof: scripted-model tests (failed route, one rewrite then pause,
stuck detection); a replayed start opens no second thread; a mid-turn card queues; checkpoint writes within budget;
the record validates; a revision skips finished steps. Waits on S4.

**M8 Watcher and recovery** (category 3; riskiest). Submit and pause in separate nodes; key `uuid5(thread, step,
candidate, repair index)` stored at job creation (S3's route) and looked up before submitting; inputs submitted
only if their digest matches the approved one; the watcher waits on `call_on_process_finish` with polling as
fail-safe, runs the step's checks on the owner thread and resumes with a typed outcome; de-duplication on (thread,
process UUID) plus a pending-pause check; catch-up at start-up (table in "Spec items resolved here"); excepted and
killed processes come back as failures to the repair rule, never resubmitted as they were; a bounded diagnostics
bundle reading only the job's folder; process groups for local subprocesses, killed at restart; D24 (version stamp
per paused run, start-up list of runs paused by an older version, `goldilocks-agent status`, updater hold).
Implements D17, D24, D33. Hooks 17, 18. Proof: the crash test with real restarts; two jobs with one key go to
"needs check"; a duplicate notice resumes nothing twice; a job that ends while the server is down resumes at
start-up; a forced update with a renamed node goes to "needs check". Waits on S2, S3, S4.

**M9 Quantum ESPRESSO routes and task 1** (categories 1, 2). Routes through aiida-quantumespresso: SCF
(PwBaseWorkChain), relaxation (PwRelaxWorkChain), bands (PwBandsWorkChain), DOS and PDOS, phonons by DFPT (ph.x →
q2r.x → matdyn.x), convergence scans. Builders are made from goldilocks-dft's QE plugin-shaped tables (dependency
2); **if that is late**, an interim route parses goldilocks-core's native input with the plugin's own parser, with
no translation logic of ours, removed in M20. Pseudopotential families from goldilocks-dft's pinned files; an AiiDA
dry run before the card, the card showing the resolved inputs; the DFT check list; D52 for QE (active on real runs
once records carry per-site spins, dependency 4); D53 labels for QE; Post Analysis calcfunctions and renderers; a
report with code-rendered tables and the D46 number checker; the task 1 recipe and the public cross-check set (QE
now); QE as a registry entry (rule set, plugin and workchain, parser, version, licence note, routes marked
implemented, validated or not integrated). Implements D8 task 1, D9.1, D9.7, D22, D36, D37, D46, D52, D53. Hooks
1, 2, 3, 8, 13, 16, 17, 20. Proof: D22/D37 round trip and the plumbing allowlist; replay tier for pw.x and ph.x;
D52, D53 and D46 tests; task 1 end to end on the replay tier in CI; one real cluster run by the owner. Waits on S3,
S6a.

**M10 Agent container** (category 3). Node build stage, slim uv Python 3.12, non-root, goldilocks-dft in its own
environment (enumlib only while it still needs it); compose with 127.0.0.1, token, `cap_drop: [ALL]`,
`no-new-privileges`, read-only root where possible; `images.yml` builds on PRs, pushes on `main` and owner tags;
the status command. Implements D20, D24, D48. Proof: no token refused; no `LANGSMITH_*`; runs paused by an older
image listed; non-root.

### Phase 4: tasks and remaining features
**M11 MLIP through aiida-mlip, task 3** (category 1). Routes (single point, optimisation, descriptors, batch
pre-screen) with a localhost code, one CalcJob per batch; typed MLIP settings with defaults and ranges in code (D37
as amended); model cards (training data and functional, elements, spin support, licence, weights hash) on every
run; explicit device; wall time, peak memory, hardware snapshot; sanity checks that fail the step (volume ratio out
of band, cell relaxation not converged on stress, step limit reached, species unknown to the model); the task 3
recipe (matched protocols; per-structure, per-model errors with source IDs; errors attributed to local environments;
admission rules: whole systems held out, unclear species mapping fails, model hash recorded, N/A never zero; a gate
on the bootstrap upper bound). Local MLIP jobs count against the card's caps (owner's decision 7). Implements D8
task 3, D37, D41, D43. Hook 12. Proof: replay with recorded janus outputs; a planted volume-ratio failure fails;
task 3 end to end on public structures; model card on every result. Waits on S5.

**M12 Skills, sandbox, shell, memory** (category 3). Loader (bundled official skills, pinned; user-added sources;
never a workspace's `.agents/skills/`; lock with source, commit, path, licence; triggers in code; a flat per-run
snapshot with manifest; vendor instructions detected and shown, never altered); sandbox (macOS: generated Seatbelt
profile; container: separate user ID, scrubbed environment, file permissions; allowlisted environment, task folder
only, no credentials, no AiiDA files; **network allowed by default**, owner's decision 6; an isolated environment
per third-party skill source); the shell tool inside the sandbox only; the "Tools and skills" panel (third-party
skills enabled one by one or by tag); D44 drafts with a typed evidence field; D51 memory (preferences and settings,
visible and editable, owner or project scope, off in evaluations, outside-channel preference off by default).
Implements D5, D29, D30, D35, D40.5, D40.7, D44, D51. Hooks 14, 17, 18. Proof: D29 tests on macOS and Linux;
skill budgets; a skill naming an unregistered tool fails; with memory off in an evaluation, the next run is
identical.

**M13 Task 2, the screening funnel** (category 1). Canonical candidate identity; per-candidate state; a selector
step (top-k by MLIP score, room for a seeded random selector); routing checks returning a category and reason with
thresholds as registry data; every cut recorded, dropped candidates kept and marked; strict rounds with one card
per round; multi-objective ranking and a stop condition in code; caps that count candidate structures; DFT on the
top few; the MLIP pre-screen skill; a "target unreachable" outcome that pauses. Implements D8 task 2, D34.5. Hook
10. Proof: a funnel on public candidates on the replay tier, each round's decisions in the record.

**M14 Literature** (category 2). OpenAlex first, then arXiv and Crossref, Semantic Scholar with the user's key;
legal open-access text with an honest User-Agent, throttled and cached; a check that the file is the expected
paper; FTS5 index with page locators; quote verification incl. number and unit; citation resolution with update
status; a folder for the user's PDFs with origin; the review recipe; LiteratureValue records reaching inputs only as
LLM values through goldilocks-dft and the card. Implements D49, D50. Hook 19. Proof: a fabricated quote fails; an
unresolvable DOI blocks the answer; the weekly sweep covers the services.

**M15 Task 4, parameter-rule studies** (category 1). A generic harness: rules as named, versioned objects; any
number of arms (current rule, proposed rule, naive fixed scan); fixed development and held-out labels; metric
written before the run; reference out of the agent's reach; accuracy and core-hours per material from AiiDA; a
comparator D32 can name. Implements D16. Hook 6. Proof: a study on a small public set on the replay tier with the
metric frozen first.

**M16 Task 5 and the evaluation harness** (category 2). The public magnetic-screening recipe (method only, open
slots; D7's inputs stay in ddmms/goldilocks); the D9.13 consistency check; the evaluation runner (CompMat-Bench
packages fetched at test time; arms 1–5; public/private/held-out labels; pass^k and pass@k; procedure and answer
scored separately; LangSmith runs by the owner with the owner's key; the schema of the private scoring file); the
D32 leak check in CI using salted hashes of the reference picks and key values held as a repository secret that
the owner manages, so CI fails on a leak without the values ever entering the public repository; a full leak check
the owner runs privately. Implements D7, D8 task 5, D9.13, D28, D31, D32, D38, D39. Hooks 2, 13. Proof: stages
E0–E2. Waits on dependency 4.

### Phase 5: the macOS app
**M17 macOS app** (category 3). Electron shell with uv bundled and checksummed; first launch with progress
(locked environments for the backend, goldilocks-dft and MLIP; AiiDA profile and daemon; MACE weights checksummed;
Ollama detected and the model pulled through `POST /api/pull`; the doctor); updates held while runs are paused
(D24) with the previous lock kept for one-step rollback; on quit with active runs, the daemon keeps running if the
user agrees; ad hoc signing for internal builds, Developer ID and notarisation once the owner holds a membership.
Implements D20, D21, D24, D48. Proof: a first launch on a clean macOS account reaches a green doctor; a forced update
with a paused run goes to "needs check"; a failed update rolls back.

### Phase 6: goldilocks-chat
**M18 goldilocks-chat** (categories 3, 5). `create_agent` with ToolCallLimitMiddleware (6 calls a turn),
ModelCallLimitMiddleware, HumanInTheLoopMiddleware for the predecessor's confirmation tools, `interrupt()` for
choices, a checkpointer; the chat profile (Find in Databases, DFT); the chat app; an anonymous owner key from a
signed session cookie, checked on every thread read and write; carried retention and concurrency limits; no shell,
MLIP or AiiDA. Implements D3, D12, D13, D35, D51. Hook 17. Proof: carried e2e specs pass on the recorded model in
CI and on live qwen when the owner runs them; D3's two fixes; the D35 test; another session's thread cannot be read.

**M19 Switching the website** (category 3; done by the owner). The chat image; switch-over and rollback notes in
ddmms/goldilocks. Proof: e2e parity first; the owner switches and rehearses the rollback.

### Phase 7: the other codes, as goldilocks-dft delivers them (none blocks chat)
- **M20 QE through goldilocks-dft's plugin-shaped tables**: the interim parse route, if it was used, is removed.
  Proof: the same round-trip and D37 tests, unchanged.
- **M21 VASP through aiida-vasp**: S6b (VASP per-site moments); phonons by finite displacements through
  aiida-phonopy over aiida-vasp with supercell and displacement settings from goldilocks-dft and NAC from
  aiida-vasp's Born charges and dielectric tensor (S7 as a real test, compared with QE's LO-TO splitting as a
  difference); S8's rule (no POTCAR content in exports); POTCARs from the user's library with substitutions shown on
  the card; aiida-vasp's handlers (custodian a reference only); a non-collinear executable allowed.
- **M22 CP2K through aiida-cp2k**: inputs from goldilocks-dft's plugin-shaped tables, validated against
  `Process.spec()`; D52 per S6c, or "not checked"; **no phonon route** (owner's decision 4).
- **M23 CASTEP through aiida-castep**: as M22; its phonon route is decided when CASTEP is built (owner's decision
  4), and if built, D53 applies.
- **M24 First release**: the owner's evaluation results (E2, then E3); user documentation; a "prepare release" PR;
  the owner releases (v4-process D24).

**Decisions to milestones**: D1 PR 2 · D3 M2, M18 · D4, D39, D47 M5 · D5, D29, D30, D35, D40, D44, D51 M12 · D6, D10,
D11 M1, M2 · D7, D28, D32, D38 M16 · D8 M9, M11, M13, M15, M16 · D9 M6–M9 · D12 M4 and each module · D13 M3, M18, M19
· D14, D23 PR 1 · D15 M3 · D16 M15 · D17, D33 M8 · D20, D21 M2, M5, M10, M17 · D22, D37 M9, M20–M23 · D24 M8, M10, M17
· D25–D27, D31 M6 · D34, D36, D42 M7 · D41, D43 M5, M11 · D46, D52, D53 M9 (and M21–M23) · D48 M10, M17 · D49, D50 M14,
M3.

## Risks

| # | Risk | Where | Mitigation |
|---|---|---|---|
| 1 | **goldilocks-dft is the critical path**: D18's record unwritten; plugin-shaped tables, VASP/CP2K/CASTEP, LLM channel, spinforge and per-site moments outstanding | M6, M9, M16, M20–M23 | QE over today's API; the interim parse route only if dependency 2 is late; safe degradations (no model-set values until #258; D52 "not checked" until #310; repairs stop at plugin handlers until the catalogue exists); D22's staging (VASP first); the dependency list feeds D18's record; round-trip and D37 tests as the contract |
| 2 | **qwen3.8 27B capability** | M6, M7, M16 | S1 first; constrained choices; code's choice as default; recipes used as they are; arms 2 and 4 measure the gap; D7's and D11's revisit clauses go to the owner |
| 3 | **AiiDA on a desktop** (SQLite + ZeroMQ broker, daemon, sleep) | M5, M8, M17 | S2; polling fail-safe; doctor; D4's revisit clause |
| 4 | **Scope for one maintainer** | all | agent first; gates; D8 (task 4 later first); D22 (stage codes); chat reuses shared parts; the "Not in the first version" list |
| 5 | **Deep Agents and LangGraph move fast** | M7, M12 | pinned minor versions; public API only; S4 tests kept as regression tests |
| 6 | **Security**: local server, sandbox (Seatbelt is deprecated by Apple; network allowed by default widens what a skill can send out), shared chat, container, supply chain | M2, M10, M12, M18 | M2 security tests; D29 tests on macOS and Linux; skills only from Goldilocks or sources the user adds (D5), enabled one by one (D30); owner key in chat; container defaults; locks, checksums, dependabot |
| 7 | **MACE install and speed on Macs** | M11, M17 | S5; CPU float64 default; isolated janus environment; install progress |
| 8 | **Privacy of D7 data and LangSmith** | M16 | private data only in ddmms/goldilocks; evaluators run locally; hashed leak check in CI; inputs hidden in private traces; owner holds the key; shipped builds never trace |
| 9 | **Licences** of carried and ported code and third-party assets | M3, M4, M9, M21 | NOTICE and its check; ported goldilocks-core files cite their commit; phonon viewer and third-party logos dropped; CompMat-Bench and GENIUS strings fetched at test time; VASP replay recordings checked for POTCAR content before commit |
| 10 | **Caching pitfalls** | M5, M9 | S2, S3; version in `prepend_text`; "reused from" on cards; retries that must not reuse a failure turn caching off |
| 11 | **Signing and notarisation** | M17 | ad hoc internally; Developer ID once the membership exists |
| 12 | **Two DFT GUIs drift** | M4 | settings forms from capabilities (owner's decision 9); ported cards accepted as a known cost (D18) |
| 13 | **Switching the website** | M19 | e2e parity first; rollback by pinning the image |

The riskiest steps are M8 (behaviour across crashes) and M9's parameter hand-over (physics).

## Proof

**The check.** `bash tools/check.sh` ends `check: all passed` (exit 0) or `check: FAILED`. It runs: `uv lock --check`
and `uv sync --locked --all-packages`; `ruff check`, `ruff format --check`, `mypy`; `pytest -m "not live"` (unit,
AiiDA integration on a test profile with SQLite, the broker, localhost and replay stand-ins, offline tool
examples, recorded-reply model tests, the import boundary); `chat_env.py`; `registry_sync.py` (frontend registry and
types in sync; prompts and skills name only registered tools; no duplicate IDs; examples and return schemas
present); `budgets.py`; `english_only.sh` (no CJK outside `frontend/packages/ui/i18n/*.json`), `notice.sh`,
`md_links.sh`, the records lint and the checks' own tests, `no_tracing_defaults.py`; frontend `npm ci`, eslint, strict `tsc --noEmit`, vitest, both Vite builds, Playwright on
the recorded-reply model. CI runs it on `ubuntu-latest` and `macos-latest` (macOS adds the Seatbelt tests and an
unsigned app build). Tests marked `live` (real Ollama, a real cluster, live services) never run in CI; the owner
runs them and records the results in the PR.

**The replay tier.** Stand-in executables for pw.x, ph.x, q2r.x and matdyn.x, registered as localhost codes, return
a recorded output only if the input is byte-identical, and fail loudly otherwise, so any change to the hand-over or
the rules fails offline. The owner records them once with a real code on public structures.

| Test | Decision | A pass | Milestone |
|---|---|---|---|
| Cap tests | D25 | a plan or job beyond any cap is refused before the card or pauses with a beyond-cap card; an edit that exceeds the compute-time cap is refused; a scripted model cannot answer an approval | M6 |
| Stale answer | D31 | an answers file whose ID is not pending is refused, the run stays paused, the refusal is recorded | M6 |
| Sandbox | D29 | a script cannot read an API key from the environment, the credentials file, the AiiDA profile or database, or files outside the task folder, and cannot write outside it; network access works by default (owner's decision 6); passes on macOS and in the container | M12 |
| Chat has no shell | D35 | no shell tool in the chat registry; no deepagents in the chat environment; no shell route | M18 |
| Round trip | D22, D37 | every goldilocks-dft value, non-default ones included, appears unchanged in the builder read back from the dry run; no key beyond those values and a reviewed list of plugin plumbing keys; the starting-magnetisation pattern matches the intended ordering | M9, M20–M23 |
| Ordering kept | D52 | an AFM run ending FM is "not kept" and left out of the ranking; a collapsed site gives "not kept"; a global sign flip is still "kept"; no parsed moments gives "not checked"; card and record show the final moments | M9, M16 |
| Polar flags | D53 | a gapped binary with non-zero Born charges gives "LO-TO correction applied"; a metal "not applicable"; a phonon route without NAC support shows "LO-TO correction not applied" on card and report; no renderer shows polar phonons without a note; CP2K offers no phonon route | M9, M21–M23 |
| Number checker | D46 | a number missing from the record triggers one rewrite, then a visible mark; a number that matches only an identifier is refused; Ry and eV conversions pass | M9 |
| Size budgets | D11 | an over-budget prompt or skill fixture fails check | M1, M12 |
| Import boundary | D1 | the planted import fails; the chat environment has no heavy packages | PR 2 |
| Offline examples | D10 | a tool without examples fails; every example passes on stand-ins | M1 |
| Crash test | D33, D17 | the server as a real subprocess, SIGKILLed and restarted after a model reply, inside a submit node before `submit()`, after `submit()` before the checkpoint, while paused, while a job ends with the server down, during a resume, while a card is answered, mid fan-out: every thread reaches its expected state, no key has two AiiDA processes, unclear cases go to "needs check" | M8 |
| Forced update | D24 | with a paused run, an update that renames the paused node gives "needs check"; the status command lists the run; the previous lock rolls back in one step | M8, M17 |
| Background start | D34 | a replayed `start_run` opens no second thread; a mid-turn card waits | M7 |
| Caching | D39 | a cached failure is not reused by a retry; a new code version gets a new Code and no cache hit | M5, M9 |
| No tracing | D48 | builds start with tracing off and no `LANGSMITH_*` defaults | M10, M17 |
| Leak check | D32 | a planted reference pick or key value in a recipe, skill or prompt fails CI through the hashed secret | M16 |

**Evaluation in stages (D38).** E0, during development: a small standing first-step set (T11-01; tool choice, D27
picks, structured output), on recorded replies in CI and live by the owner at each prompt or catalogue change. E1,
public tasks, run by the owner: task 1's cross-check set, task 3 on public structures, CompMat-Bench C06 and C07
(fetched at test time; only what the first version can do). E2, the first D7 evaluation: one funnel round on fixed
candidates, five arms, paired, failures scored zero, bootstrap intervals, the evaluator frozen and versioned first
with its hash recorded, private data from ddmms/goldilocks. E3: all three rounds plus held-out compositions.

## Carry-over list (D13)

Source `stfc/goldilocks-agent` @ `ea757c7`. Each carried file starts with a line citing its source path and
`ea757c7` and is listed in NOTICE; comments citing the Chinese design doc are rewritten in English.

| Component | Source | Action | Why |
|---|---|---|---|
| Self-hosted qwen options | `graph.py` `resolve_model`, `_self_hosted_options` (22e6ee8) | with changes | into the model layer |
| Single system message | `graph.py` `system_message` (edcb5ee) | with changes | prompt builder from the registry |
| Orphaned tool-call repair | `graph.py` `_repair_orphaned_tool_calls` (5a037d8) | with changes | middleware; also prevented at the source |
| Parallel tool-call split | `graph.py` `add_tool_call_delta` (6473803, #149) | with changes | re-checked under ChatLiteLLM (S1) |
| One tool call per node run | `graph.py` `call_tool` (c7bfc57) | rewrite | ToolNode in `create_agent`/Deep Agents; behaviour kept by tests |
| Tool budget with wrap-up | `graph.py` (b345ffe, #151) | rewrite | ToolCallLimitMiddleware plus a wrap-up note |
| Profiles and prompt | `agent_profile.py` | rewrite (prompt with changes) | profiles from the registry |
| SSE protocol and chat routes | `server.py` (chat, history, drafts, bundles, preferences, projects, conversations, structure match and fetch, concurrency) | with changes | server kit; typed frames; ownership checks |
| MLIP routes | `server.py` `/api/mlip/*` | drop | aiida-mlip (D41, D43) |
| Core GUI forwarding | `server.py` `core-server/ensure`, `_proxy_to_core` | drop | D12, D18 |
| Credentials endpoint | `server.py` `/api/credentials` | with changes | agent only; 0600; never visible to the sandbox |
| Configuration | `config.py` | with changes | per form; no tracing defaults |
| Store | `store.py` | with changes | owner and project keys, schema version |
| Idle-chat retention | `chat_retention.py` | as-is, re-keyed | shared-instance policy |
| DFT drafts | `dft_draft.py` (#150, #152, #153) | with changes | revisions, 409 |
| goldilocks-core client | `core_api.py` (e829897) | with changes | dft_client with version gate |
| Starting core | `core_server.py` (bf093bd) | with changes | goldilocks-dft in its own environment |
| Core pin | `core_pin.json` | with changes | 0.3.3, then goldilocks-dft |
| CLI | `cli.py` | rewrite | one entry per form; `status` |
| Tool plumbing | `tools/__init__.py`, `tools/context.py` | rewrite | the registry |
| DFT Workbench tools | `tools/dft_workbench/*.py` | with changes | the DFT module |
| Find in Databases | `tools/structure_search/*.py` (c07a6d7, e2cc552) | with changes | typed Materials Project records; declare pymatgen |
| MLIP Playground | `tools/mlip_playground/*.py` | rewrite | aiida-mlip; result models as a start |
| Isolated janus environment | `mlip-cli/pyproject.toml` | with changes, if S5 confirms | janus code environment |
| Band YAML renderer | `mlip-cli/render_band_yaml.py` | drop | no MLIP phonons |
| Unit tests | `tests/test_{core_api,core_pin,core_server,dft_draft,store,chat_retention}.py`, `tests/tools/test_{dft_*,structure_search}.py` | with changes | safety net |
| Graph and server tests | `tests/test_graph.py`, `tests/test_server.py` | with changes | re-targeted at middleware |
| MLIP, compose, README tests | `tests/tools/test_mlip_playground.py`, `tests/test_docker_compose.py`, `tests/test_readme.py` | drop or rewrite | replaced |
| Tool-choice evaluation (#68) | `tests/eval/tool_choice.py` | with changes | English prompts; seed of S1 and E0 |
| App shell | `app/src/App.tsx` | rewrite | 10,878 lines in one component |
| Structure files | `app/src/utils/structureFiles.ts` (+ test) | as-is | |
| Viewer | `app/src/components/WeasStructureViewport.tsx` | with changes | subject to M4's comparison |
| DFT review | `app/src/dftReview.ts` (+ test), `components/DftReviewCard.tsx` | with changes | the DFT card |
| Draft sync | `app/src/dftDraftSync.ts` (+ test) | with changes | drops the embedded workspace |
| Embedded core glue | `app/src/dftWorkbench.ts`, CoreWorkbench* components, `app/vendor/goldilocks-workbench-0.3.3.tgz` | drop | D12; cards are ported from core's sources instead (owner's decision 9) |
| Bug report | `components/BugReportDialog.tsx`/`.css` | with changes | target this repository; never auto-submits |
| Translations | `TRANSLATIONS` in `App.tsx` (en, fr, de, zh, it) | with changes, all five | into `i18n/` (owner's decision 8) |
| Recorded core fixtures | `app/src/__fixtures__/core/*.json`, `app/scripts/record-core-fixtures.mjs` | with changes | test fixtures |
| Phonon viewer | `app/public/phonon/**` | drop | third-party, no licence file |
| Third-party logos | `app/public/mode-icons/{aiida,janus-core}.png` | drop | our own icons; our SVGs carry as-is |
| Saved 404 page | `app/public/data.json` | drop | unused |
| End-to-end tests | `app/e2e/*.e2e.ts`, helpers, `Si.cif`, `Fe_bcc.cif` | with changes | chat's parity gate |
| Dockerfile, compose | `Dockerfile`, `docker-compose.yml` | with changes | `deploy/agent`, `deploy/chat`; D20 defaults |
| Image workflow | `.github/workflows/docker-publish.yml` | with changes | `images.yml` |
| Dependabot, issue template | `.github/dependabot.yml`, `ISSUE_TEMPLATE/agent-app-bug.yml` | with changes | |
| Shared-instance deployment | `deploy/stfc-cloud/**`, `app/.env.stfc-cloud` | not carried | ddmms/goldilocks (v4-process D12) |
| Docs | `mkdocs.yml`, `pages.yml`, `docs/*.md` | drop for now | Chinese design doc never copied; English docs later |
| Scripts | `scripts/bump_core.py`; `scripts/e2e_web.py` | rewrite; with changes | pin only; local chat e2e |
| Agent instructions | `AGENTS.md` | rewrite | V4 process |

## goldilocks-dft dependencies (input to D18's record)

goldilocks-dft returns plain data and runs nothing (owner's decision 5). In the order the Workbench needs it:

| # | Need | Decision | Waits | If late |
|---|---|---|---|---|
| 1 | keep the 0.3.x HTTP API; releases that can be pinned | QE first | M3, M9 | — |
| 2 | QE parameter tables shaped for aiida-quantumespresso (the translation layer, owner's decision 5) | D22, hook 8 | M9 | interim: the plugin's own parser on goldilocks-core's native input, removed in M20 |
| 3 | `/ready` that tells installing from failed, with progress | D21 | M17 | 503 as "installing", with a timeout |
| 4 | spinforge merged (#310), per-site spins in ordering records | D15, D52, hook 2 | M9 (D52 live), M16 | D52 reads "not checked" |
| 5 | LLM values for the functional and pseudopotential table (#258) | D22, D37 | M6 | the model sets no values; the user edits as human values |
| 6 | structured per-parameter reasons with rule ID and version | D26, hooks 8, 9 | M6 | show `source` and `source_note` |
| 7 | a settings catalogue marking physics vs numerical-stability settings | D9.7 | M8, M9 | plugin handlers, then the user |
| 8 | an LLM channel for every setting goldilocks-dft knows | D22, D37, D9.7 | M8, M9 | as rows 5 and 7 |
| 9 | a method signature on every result | hook 1 | M9, M21 | the Workbench assembles code and version, functional, pseudopotential checksums |
| 10 | intended per-site moments in µB with per-code conversion | D52, D15 | M16, M21 | — |
| 11 | Hubbard U keyed by code and projector | D22 | M21 (warning in M9) | the card warns when U came from another code |
| 12 | per-element pseudopotential manifests for POTCAR, CP2K, CASTEP | D22 | M21–M23 | — |
| 13 | VASP settings, rules and plugin-shaped tables; POTCAR substitution for approval | D22 | M21 | — |
| 14 | VASP phonon settings for finite displacements (supercell, displacement amplitude) and Born-charge/dielectric settings per code | D53, owner's decision 4 | M21 (M23 if CASTEP phonons are built) | "LO-TO correction not applied" |
| 15 | a polar-insulator rule (gap and non-zero Born charges) | D53 | M9, M21 | the Workbench's proposal in "Spec items resolved here" |
| 16 | CP2K settings, rules and plugin-shaped tables | D22 | M22 | — |
| 17 | CASTEP settings, rules and plugin-shaped tables | D22 | M23 | — |
| 18 | finding codes for each code's input rule checks | Concern list | M21–M23 | — |
| 19 | total-charge setting reserved and refused; cost class on method recommendations | hook 8 | M20 | — |
| 20 | spin space group in ordering records | hook 2 | M16 | field left empty |
| 21 | the rename, the ML merge, a PyPI package | D18 | M20 | keep the goldilocks-core pin |
| 22 | #302–#304 and #300 (MCP streamable HTTP, typed errors, publish root) | roadmap | not needed by the first version | — |
| 23 | ab initio MD settings | D37 | not in the first version | — |

## Code-review candidates

Design references only; no code from other projects is copied (D23). Avoid items from VASPilot, MatSciAgent, A3HT
and CACTUS are used only where another system supplies a code pointer (code-review decisions-log row 92).

**The top 15**

| # | Candidate | Used? | Where |
|---|---|---|---|
| 1 | every parameter reaches the builder unchanged (round trip) | yes | M9, with D37's allowlist |
| 2 | one validate-before-execute path; no automatic retry of side-effecting tools | yes | M1 |
| 3 | structured tool status; checks fail closed | yes | M1, check form |
| 4 | robustness suite and routing set for qwen; flat schemas; GENIUS strings fetched at test time | yes | S1, E0 |
| 5 | prompts and skills generated from the registry; CI for unknown and duplicate names | yes | M1, M12 |
| 6 | executor harness with scripted models: nested interrupts, real restart, forced update, crash phases | yes | S4, M7, M8 |
| 7 | requested-versus-produced check after every step | yes | check form |
| 8 | a concrete DFT check list | yes | M9 |
| 9 | a phonon route and phonon checks | yes | QE DFPT; VASP finite displacements; CP2K none |
| 10 | validated submission seam (builder validation, dry run, nothing stored before approval) | yes | M6, M9 |
| 11 | one AiiDA owner thread; state holds only references | yes | M5 |
| 12 | matched protocols and MLIP admission rules for task 3 | yes | M11 |
| 13 | MLIP sanity checks that fail the step | yes | M11 |
| 14 | write-ahead record for turns; process-group kills | process groups only | checkpoints with pending next nodes show cut-off turns; D33 rejects a third store and D17.5 a ledger |
| 15 | doctor with a broadcast round trip and daemon diagnosis | yes | M5, M17 |

**Conflicts, resolved**

| Conflict | Resolution |
|---|---|
| slips: reject with a reason, or alias silently? | reject with a reason and a "did you mean" (D10); JSON-type conversion only; no aliasing of names, paths or IDs |
| structure IDs: content hash or AiiDA UUID? | the UUID links everything (D43); the content hash is an attribute for de-duplication and identity checks |
| stopping a run | a user action, confirmed each time; stops new submissions; killing running jobs is a separate destructive confirmation; nothing killed automatically (D10, D17.6) |
| steering on resume | only as a revised plan (D42); text typed at a card is a rejection with feedback |
| resident MLIP service or aiida-mlip? | aiida-mlip with batched CalcJobs (D43) |
| canary runs | later; the dry run and the wizard's test job stay |
| unavailable tools | left out of the catalogue; shown disabled with the reason in the GUI |
| network in the sandbox | allowed by default (owner's decision 6) |
| approval for local MLIP CalcJobs | none; counted against the card's caps (owner's decision 7) |
| reverting a task | later |

**By component** ("no" means not used, with the reason)
- *Registry, tools, small-model robustness.* Used: ChemGraph's availability checks binding only chosen tools;
  aiida-agents' declared write access with the strictest default; ToolUniverse's descriptor split, validation layer
  (fixed as above) and error envelope; CatMaster's wrapper hygiene; LLaMP's typed database tools (units re-checked);
  Masgent's precondition validators; matsim-agents' registry and AST boundary test; IDs plus summaries (VASPilot,
  Paimon, MDCrow, El Agente); ChatMOF's one source for allowed values and the check; MatBrain's validation before
  dispatch; Masgent's history truncation keeping calls with results; ToolUniverse's valid-JSON truncation; Paimon's
  per-role token audit; aiida-agents' explicit `num_ctx`; matsim-agents' prompt saved before sending and staged
  qualification on the real structured-output path. No: ChemGraph's worker search (D27 keeps the catalogue in
  view); MatBrain's lower-temperature retry (D9.9: one rewrite); query plans before lookups (D50); an MCP adapter
  (D10).
- *Cards and approvals.* Used: CatMaster's strict validator (strict path only) and interrupt-safe error middleware;
  ChemGraph's required reasons (LLM values, destructive calls), skipping answered calls, free text as rejection;
  DFT Agent's digest-bound approval re-checked at launch; aiida-agents' triage (one rewrite); Aitomia's typed
  interrupt payloads; DFT AutoPilot's seven-part card with sources and reasons; resolved inputs shown; GENIUS's
  live step timeline; Masgent's one tool layer for GUI and agent. No: Paimon's interaction profiles (D25's caps);
  ChemGraph's automatic-approval cap (no automatic mode); "supply the result myself" (later).
- *Planner and executor.* Used: El Agente's constrained router, explicit routing failure, skip when inputs are
  determined; A3HT's typed single decision; matsim-agents' bounded LLM role with raw reply saved; Paimon's typed
  contracts; MatOS's closed set of check kinds with codes and hints; AutoDFT's plan validation (unknown fields
  rejected); GENIUS's repair budget in state; aiida-agents' IDs only from tool outputs; CatMaster's child thread IDs
  and one turn at a time; AtomisticSkills' funnel stage contracts; DREAMS's decision on every result before
  advancing. No: running plans through Deep Agents' subagent mechanism (D34 rejected it); MatOS's per-run version
  pin (D24); MASTER's selection loop (not in the first version); self-applying patches (D42).
- *AiiDA, watcher, recovery.* Used: aiida-agents' submission seam, UUID references (round-trip tested), thread
  discipline, failure diagnosis (without private attributes), daemon diagnosis and doctor; CatMaster's resume only
  on a matching pause, delivery once, crash test; MatOS's side-effect classes and run/node keys; ChemGraph's session
  driver with a real OS restart; matsim-agents' versioned recovery policy as recorded events; DREAMS's follow-up
  list on wake; Paimon's submit-stop-wait in code. No: ChemGraph's journal and a "submitting" marker (no ledger,
  D17); QUASAR's write-ahead file (see row 14); job packing (T08-04, S9); custodian handlers (aiida-vasp's).
- *DFT routes and checks.* Used: aiida-agents' `Process.spec()` validation for CP2K and CASTEP inputs and protocol
  introspection for QE and VASP; parser flags read from plugin outputs; DREAMS's convergence decision that refuses to
  guess; matsim-agents' method signature and replay tier; validation before submission as the dry run; POTCARs on
  the HPC side through goldilocks-dft; MDCrow's round trip with non-default values. No: keyword validation against
  installed versions, parameter bases, INCAR patching and accuracy floors (all goldilocks-dft's; it holds the one
  input writer); in-flight monitors (D17.6).
- *MLIP.* Used: matsim-agents' bootstrap gate; OpenClaw's admission rules; El Agente's hull with references relaxed
  by the same MLIP; MatBrain's sanity checks made to fail and its one-functional-family hull; model cards; device
  selection as a design. No: committee gates (T04-01); a resident service (D43).
- *Structure Builder.* Used: CatMaster's versioned operation union and contact check; a sanity check after each step
  that fails; Scientific Agent Skills' symmetry tolerance sweep; pymatgen's ZSL builder (dependency) for interfaces;
  matsim-agents' magnetism contract keyed by atom ID; DFT Agent's typed operations with a source site index. No:
  pymatgen's enumerator and Masgent's matcher (spinforge through goldilocks-dft, D15); adsorbate rules (surfaces
  line is later).
- *Skills, sandbox, shell.* Used: AtomisticSkills and Scientific Agent Skills lints (in goldilocks-skills and our
  loader); CatMaster's per-run snapshot; ChemGraph's read-only bundled skills and source precedence; triggers
  evaluated in code; promotion statuses for D44; skills offered only when their requirements are present. No:
  workspace discovery (D5); vendoring (D40's record); a network deny-by-default (owner's decision 6).
- *Literature and databases.* Used: CatMaster's legal acquisition, expected-paper check, FTS5 index and DOI check;
  metadata never presented as full text; database text as untrusted data. No: browser fallback (D49).
- *Reports and numbers.* Used: DFT Agent's evidence gate; aiida-agents' grounding (with the identifier lesson);
  DREAMS's cited numbers; CatMaster's closing gate; one ID function (AiiDA UUIDs plus D36 names).
- *Evaluation.* Used: MASTER's replay oracle and bootstrap; DFT-Agent Bench's scores re-derived from raw outputs,
  void runs and paired frozen subsets; CompMat-Bench packages fetched at test time; VASP Agent's ablation and
  responder; MatBrain's leakage audit; LLaMP's normalised self-consistency; AutoDFT's ablation flags; MDForge's
  stratified split. No: A3HT's replicate stop rule (T01-43).
- *Server, app, container.* Used: ToolUniverse's server security and uv launch protocol; AtomisticSkills' readiness
  marker keyed by the lock hash; numbered doctor checks; ChemGraph's saver discipline and headless receipts; DREAMS's
  WAL with full sync and atomic writes; container discipline (no moving-head pre-cache, no `.env` pass-through). No:
  engine installs (D47).
- *DFT AutoPilot session* (presented, never answered). Used: sources and reasons on the card with a reason required
  for overrides; VASP-calibrated U not used under QE's ortho-atomic projectors without approval; slips rejected; the
  seven-part card; moment checks before inputs are written. No: a goldilocks-dft package for other hosts (T10-02).

## Hooks checklist

Data fields and interface shapes only; anything needing new UI, a new parser, a new dependency or HPC time waits.

| # | Hook | First version implements | Milestone | Waits |
|---|---|---|---|---|
| 1 | method signature on every value | all fields (SOC and dispersion off/none), the comparison rule (same signature: values; different: trends and differences, never values), a production/rehearsal label | M9 | full signature from goldilocks-dft (9) |
| 2 | every magnetic ordering kept | energy per formula unit, label, initial and final moments with unit and integration method, D52 mark, symmetry, same settings for all orderings | M9, M16 | cell mapping, spin space group (4, 20) |
| 3 | expensive outputs kept | force constants, dielectric tensor and Born charges, stress tensors, ionic steps, DOS arrays as typed outputs; remote folders kept; an energy-volume field shape | M5, M9 | equations of state (T01-08) |
| 4 | research record ready for export | header fields, UUIDs, licensed/private flags | M7 | S8 decides the POTCAR flag |
| 5 | usage accounting; HPC only through AiiDA | model counters, job tags, requested beside used resources, empty estimate field, limits as data, templates with a per-user part, open transport options, resumable "cannot authenticate", CalcJob import as the only route in | M2, M5 | accounting confirmed on the target cluster (owner, live) |
| 6 | generic D16 harness | named versioned rules, any number of arms, fixed labels, pre-registered metric, pluggable reference, comparator | M15 | — |
| 7 | one value record | evidence kind, empty uncertainty, accuracy target | M1 | — |
| 8 | goldilocks-dft recommendation records | consumes them and the plugin-shaped tables; a computed U entered as a human value pointing to its process | M3, M9, M20 | goldilocks-dft (2, 6, 7, 19) |
| 9 | event entries written by code | failures and repairs, card edits, unknown settings, D27 picks, relaxation start and step counts | M7 | — |
| 10 | funnel as per-candidate state | identity, selector step, routing categories, recorded cuts, objectives, stop condition, candidate caps | M13 | seeded random selector is a slot |
| 11 | Structure Builder with a full record | occupancies with "needs ordering", seeds, mappings, identity checks, generator records, ranked substitutions with who chose each, typed strain/defect/slab parameters | M3 | — |
| 12 | MLIP layer ready for several models | list of model IDs, model cards, per-structure errors by model, device and hardware records, reserved MD block, room for GPU hours and "adopt model" | M11, M6 | other models (D41) |
| 13 | evaluation and model-layer plumbing | labels, generic package runner, prompt levels, step counts, dry-run export with reason codes, recorded replies, planning logs, self-refreshing credentials | M2, M9, M16 | — |
| 14 | registry as data | IDs, versions, hashes, typed I/O, classes, caps, origin, tags; recipes as plans with open slots; source-prefixed names; stateless AiiDA queries; waiting never a tool; MCP export off; one-command module template; typed evidence on drafts | M1, M6, M12 | the MCP decision (Open) |
| 15 | executor entry without a model | plan in, record and UUIDs out, answers file, plan hash on approval, headless typed endpoints | M6, M7 | — |
| 16 | Post Analysis as a registry | named calcfunctions with units, one spectrum type, plots from a typed spec with data saved, renderer Python API, a viewer that plays frames | M4, M9 | trajectory player (T06-01) |
| 17 | owner and project keys; queryable results | identity only from the session; keyed records; one group per task; key results as AiiDA values; read-only diagnosis; live reads only in the job's folder | M2, M5, M8, M9, M18 | project workspaces (X-01) |
| 18 | one notifier and one status | typed events; one status for the status command, GUI and self-check; outside-channel preference off by default | M2, M7, M12 | outside channels (T06-05) |
| 19 | literature and database records | citation update status, measured/computed marks, method context in goldilocks-dft's names, tagged index, reusable indexer, origin of user PDFs, Materials Project records by code, typed structure requests | M3, M14 | — |
| 20 | DFT codes as registry entries | rule set, plugin and workchain, parser, version, licence note, route status, non-collinear executable allowed, reader interface, reusable D26 comparison | M9, M21–M23 | — |

## Spec items resolved here

| Item | Resolution | Owner to confirm? |
|---|---|---|
| D1 layout | uv workspace with three packages, npm workspace, `desktop/`, `deploy/`; light modules in the shared package, AiiDA/MLIP/Post Analysis in the agent; AST and environment boundary tests | no |
| D9.8 qwen first | S1 before M2 and M6; if `tool_choice` is ignored, forced choices use a schema-constrained `format` | no |
| D9 known costs | typed interfaces (M1), checker (M6), executor (M7) | no |
| D9 "registered as CompiledSubAgent", read with D34 | D34 rejected running the executor through Deep Agents' `task` and a shared state key; approved plans start from `start_run` on their own background thread. No CompiledSubAgent in the first version unless S4 shows a need | no (settled by D34) |
| D10 output caps | 1,200 tokens of valid JSON per tool result, with a pointer to the full result | no; S1 calibrates |
| D11 size budgets | `num_ctx` 32,768; reply reserve 4,096; system prompt ≤ 1,500; catalogue ≤ 2,000 (≤ 40 per line); skill descriptions ≤ 1,500 total (≤ 60 each); one official SKILL.md ≤ 2,000 (third-party bodies over 4,000 refused at load); step-2 prompt ≤ 4,000; router prompt ≤ 3,000; verbatim history ≤ 12,000, then code-written summaries; checkpoint ≤ 16 KB per step; chat keeps 6 calls a turn; all in `budgets.toml`, checked with the Qwen tokenizer | no; S1 calibrates |
| D13 carry-over | as in the carry-over list; all five UI languages carried (owner's decision 8) | no |
| D32 tolerances and weights | weights in the owner's order: final picks 0.30, funnel decisions 0.22, key values 0.18, magnetic ground state 0.14, structure and symmetry 0.10, interventions 0.06; tolerances per field in the private file, fixed before any arm runs, none tighter than the reference workflow's measured spread or, for MLIP values, the MLIP's validated error; k = 3 | yes (numbers kept in ddmms/goldilocks) |
| D32 rule 6 leak check in CI | salted hashes of the reference picks and key values as a repository secret managed by the owner; CI fails on a match; full check run privately by the owner | no |
| D33.1 continue or retry | cut off in a conversation model call or tool: the user is offered a retry; in `start_run`: reconcile using the derived ID; executor in a "run again" or "skip if done" node: continue; in a submit node: rerun with the key; in a router call: continue, or wait out an outage; unclear: "needs check"; found from checkpoints' pending next nodes | no |
| D39 caching pitfalls | version in the Code's `prepend_text`, one Code per version; "reused from" on cards and in the record; retries after environmental failures turn caching off for themselves; S2 lists invalidating exit codes | no |
| D41 MACE per platform | CPU float64 default on macOS; MPS float32 only if S5 shows agreement within the check tolerances; CPU wheels in the container; isolated janus environment if S5 allows; weights checksummed at first launch | no |
| D43 how checks are written | check kinds in code, tested, with ID and version, reading AiiDA data only; thresholds as registry data with units and sources; outcomes passed, failed, not checked, insufficient data, check error (the last three of failed/insufficient/error block the step); derived values from calcfunctions | no |
| D52 tolerances | a site collapsed if \|m\| < max(0.1 µB, 0.1·\|m₀\|); flipped if its sign differs after one allowed global flip; "kept" if none collapsed or flipped; an ending matching another ordering is named but still left out; "not checked" when the plugin gives no per-site moments; rule and values recorded with each check; S6a/S6b calibrate | no (category 1 PR) |
| D53 polar detection and VASP hand-over | goldilocks-dft's rule decides (dependency 15); Workbench proposal: a gap, at least two elements, largest \|Z*\| > 0.1 e; VASP: a calcfunction builds aiida-phonopy's NAC parameters (units, cell frame, atom order, neutrality sum rule, symmetrised), tested against QE's LO-TO splitting on the same structure as a difference | threshold: in D18's record |
| Phonon route for task 1 | QE DFPT; VASP finite displacements through aiida-phonopy with settings from goldilocks-dft; CP2K none; CASTEP decided when built | decided (owner's decision 4) |
| Where parameters become plugin inputs | goldilocks-dft returns plugin-shaped plain data; the Workbench only builds builders from it (owner's decision 5); interim QE parse route only if dependency 2 is late | decided |
| Resuming a composed plan | one fixed interpreter graph reading the hash-checked plan from its state | no |
| Key at job creation | reserved prefix in `metadata.label`, set at node creation; extras only if available then; S3 confirms | no |
| ZeroMQ broadcasts | S2, before M5 and M8 | no |
| aiida-core and aiida-mlip versions | aiida-core 2.9 for SQLite with the ZeroMQ broker; aiida-mlip 0.3.0 from PyPI until a release supports aiida-core 2.9; a git source weighed and not taken ("aiida-core and aiida-mlip versions", under "Files that change") | decided (owner, 2026-11-26) |
| LangSmith data | an EU-region organisation; the owner holds the key; public tasks fully traced; private datasets carry inputs only, evaluators run locally, traces hide inputs and outputs; arm 4 runs private tasks only with a provider the owner approves | yes |
| D7 comparison with private data | evaluators run locally from ddmms/goldilocks; the public repository has the schema, runner and hashed leak check | no |
| Reading CatMaster's code | done in code-review memo 01; each PR re-reads the cited files, design only | no |
| Code-review README section 5 checks | broadcasts and monitors: S2; handlers: S3; Deep Agents skills and interrupts: S4 (M12 uses a flat snapshot); Ollama with qwen: S1; SSSP checksums: goldilocks-core's per-file manifest, verified in M5; ToolNode threads: made irrelevant by the owner thread; CP2K/CASTEP builders: S9 | no |
| `start_run`'s argument | a plan ID; code loads the approved document and checks its hash ("never retold as text") | no |
| Network in the sandbox | allowed by default | decided (owner's decision 6) |
| UI languages | all five kept in `i18n/`, the one exception to English only | decided (owner's decision 8) |
| DFT GUI | settings forms from capabilities; structure, magnetic-orderings and bundle cards ported from goldilocks-core | decided (owner's decision 9) |
| Chat history at the switch | no migration; the old database stays until its retention lapses | yes (category 5) |
| Scheduler options (hook 5) | goldilocks-dft estimates resources; the computer template holds site options and limits; the Workbench clamps; caps count requested resources | no |
| Official skills in builds | a pinned snapshot is bundled into the app and container | yes, in D40's record |
| Release channel | our wheels to PyPI; the app follows the release lock | yes (names) |
| Default MACE checkpoint | recorded with its model card | yes |
| aiida-hyperqueue (T08-04) | S9's written evaluation | no |
| Developer skill | `docs/developer/`, pointed to from `AGENTS.md` | no |
| Retry list (code-review decisions-log row 81) | SCF: handler, then mixing, steps or diagonalisation; ionic step limit: more steps; wall time and memory: more resources within caps; imaginary modes and orderings not kept: always the user; MLIP: more steps within range, else the step fails; at most two options per step, as LLM values (dependency 8) | no |
| Monitoring available (code-review decisions-log row 90) | S2 and S9 list it; observe only | no |
| If 27B falls short | not decided; the owner decides after E2 | yes |
