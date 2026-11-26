# Plan: goldilocks-Ada, built now (ada)

From: `intent.md`, `spec.md` (same folder). Size: large (v4-process D8). Status: accepted by the owner in plan mode
on 2026-11-26 (v4-process D5, gate 3). Committed as `changes/2026-11-26-ada/plan.md`, the first commit of PR A0; it
may change until the last PR that implements it merges (v4-process D4).

References: "ada D*n*" is a decision in this change's spec; a bare "D*n*" is one in
`changes/2026-11-25-workbench/spec.md`; "M*n*", "S*n*", "PR *n*", "hook *n*" and "risk *n*" are items of
`changes/2026-11-25-workbench/plan.md` (the workbench plan); "A*n*" and "S10" are this plan's. Large changes keep
their decisions in the spec, so this plan has no Decisions section; where the spec leaves a choice to the plan,
"Spec items resolved here" settles it.

Supersedes: changes/2026-11-26-ada/spec.md

This plan overturns one item of the ada spec: ada D5.1 lists module names among SCARF's site settings, and owner's
answer 5 (below) drops them, so Ada's site file holds partitions and limits only. No reason recorded. The rest of
the ada spec stands. Decisions that rest on it:
- ada D5.5 still holds, on Claude's reasons: Ada submits goldilocks-dft's bundle with the site's scheduler options,
  which are partitions and limits; the bundle's `submit.sh` loads the modules.
- D47 still holds, on the owner's reason: it records `module load` lines when the agent registers AiiDA codes, and
  Ada registers no code (ada D4).

## Context

**Why.** The owner decided to build goldilocks-Ada in the first version, after the shared foundation (M1 to M4) and
before the agent's core (M5 to M9) (ada D1). The ada spec (ada D1 to D11, accepted in #6) overturns parts of the
workbench spec and of the workbench plan, and leaves the order of Ada's work, the spike of ada D2, the size limits of
ada D6 and the reader of fetched results to this plan.

**What Ada's first version is.** A light form (ada D9): chat that reaches SCARF from the user's own Ada VM (ada D2).
It offers Find in Databases, DFT, Structure Builder (ada D6), Post Analysis on fetched results (ada D11) and SCARF
jobs (submit, status, fetch, cancel) through a `slurm` module that runs fixed commands only (ada D5). It shares the
light agent with chat (ada D3), installs no AiiDA (ada D4), has no shell (ada D10) and has its own web app (ada D7).

**Owner's answers for this plan** (2026-11-26; options Claude offered, the owner chose; no reasons recorded)
1. PR A0 (this plan, the edits to the workbench plan, an empty goldilocks-ada package, a blank Ada app, Ada's
   import-boundary and environment checks) goes in now, before the workbench spikes and M1. The option also put
   S10's script in A0; this plan gives the script its own PR, so that A0 is smaller (Claude's change). A0 is above
   ~800 changed lines even without it. After the review of #8 the owner kept the script's own PR.
2. Fetched Quantum ESPRESSO outputs are read by a reader in the shared package (`goldilocks_workbench/post_analysis/`),
   not by goldilocks-dft.
3. Structure Builder on the shared chat instance: at most 500 atoms in any structure it returns, supercells at most
   64 times the input cell, each operation stopped after 30 s. Claude's proposal; nothing was measured.
4. Ada's caps on SCARF submissions: 10 jobs and 1,000 core-hours per conversation by default.
5. SCARF's site settings in Ada hold no module names; this overturns that part of ada D5.1 (see Supersedes, above).
   Claude had left them out without asking, because the bundle's `submit.sh` loads goldilocks-dft's modules
   (`AGENTS.md`, rule 6); the review of #8 found it, and the owner chose this over keeping them.

**Not in Ada's first version** (with risk 4, below)
- Work that one goldilocks-dft bundle cannot describe: several jobs that depend on each other, planning or checking
  results between jobs (ada D5's and ada D9's revisit clauses); a Deep Agents loop (ada D9).
- Phonon tasks: a bundle can hold ph.x, q2r.x and matdyn.x, but their analysis needs D53's labels and the phonon
  viewer of hook 16, which come with M9. Ada's DFT profile offers SCF, relaxation, variable-cell relaxation, bands
  and DOS.
- Clusters other than SCARF; codes other than those goldilocks-dft delivers (Quantum ESPRESSO now).
- AiiDA, provenance and caching (ada D4); MLIP (D12); Literature; memory (D51).
- A shell or side analysis outside tools (ada D10); one instance serving several users (ada D2).
- Resuming a job from a later step (`GOLDILOCKS_FROM_STEP` in goldilocks-dft's `submit.sh`).

**Facts this plan relies on** (checked 2026-11-26)
- This repository, `main` at `ebdd7db`: three packages (workbench, chat, agent) with entry points and no
  features; two blank Vite apps; `tools/checks/import_boundary.py` fails on a package folder without a rule;
  `tools/checks/chat_env.py` checks the chat environment; `REVIEW.md` already lists `**/post_analysis/**` (ada D11).
- goldilocks-core @ `junwen94/goldilocks-core` main `a6d4c19` (0.3.3):
  - `POST /run` with `respond_with: "archive"` returns a ZIP (`server/documents.py:95`).
  - A bundle holds every step of a task, each step's inputs, the pseudopotentials, a SLURM `submit.sh` that runs the
    steps in order in one job (`submission/slurm.py:264`), a `README.md`, and the manifest `goldilocks.json`
    (schema version 3: `request`, `records`, `warnings`, `citations`, `steps`, `files` with sha256 per file;
    `bundle.py:90-105`).
  - The manifest's `steps` give each step's name and files, not its executable, which is only in `submit.sh`.
  - Tasks and their steps are in `plan.py:77-112`: `scf_single_point`, `relax`, `vc-relax`, `band`, `dos`, `phonon`
    and the relax-then-phonon tasks.
  - The resource estimate is the record `job` (`JobDecision`: partition, nodes, ntasks, ntasks_per_node,
    walltime_h, memory, account; `advisors/job_resources.py:193`). `submit.sh` turns it into `#SBATCH` lines.
  - A SCARF HPC profile (partitions, limits, the QE module) "verified against live `sinfo` ... output (2026-09-14)"
    is in `inputs/profiles/scarf.toml` and listed in `/capabilities` as `hpc_profiles`.
  - goldilocks-core parses no QE output in Python. Only `submit.sh` reads `exit_status` from pw.x's XML, and
    `JOB DONE` from the other programs' output.
- `ddmms/goldilocks-dft` holds a README only.

## Files that change

```
changes/2026-11-26-ada/plan.md                     this plan (first commit of A0)
changes/2026-11-26-ada/spikes/S10-ada-platform.md  S10's written result (generic facts only)
changes/2026-11-25-workbench/plan.md               the edits listed under "Edits to the workbench plan"
spikes/S10/                                        the script the owner runs on an Ada VM (not packaged)
pyproject.toml  uv.lock                            fourth workspace member; ruff and mypy settings
packages/ada/                                      goldilocks-ada (depends on goldilocks-workbench only)
  src/goldilocks_ada/
    cli.py  config.py  profile.py  server.py       entry point (serve, doctor, status), settings, Ada's profile
    slurm/                                         ada D5: site.py, sites/scarf.toml, transport.py (local, SSH),
                                                   args.py (allowed characters), jobs.py (records), submit.py,
                                                   reconcile.py, poller.py, fetch.py, tools.py (registry module)
  tests/                                           incl. fake Slurm and SSH stand-ins (tests/standins/)
packages/workbench/src/goldilocks_workbench/
  light_agent/                                     ada D3: the factory and its middleware wiring
  post_analysis/                                   ada D11: readers/qe.py, scf.py, relax.py, bands.py, dos.py, units.py
  modules/structure_builder/                       (M3) takes a profile's size and time limits (ada D6)
packages/chat/src/goldilocks_chat/profile.py       (M18) chat's profile with Structure Builder and its limits
frontend/apps/ada/                                 ada D7: the Ada app
frontend/packages/modules/slurm/                   job-list panel; cards: submit (approval), submitted, finished,
                                                   needs check, cancel, cap reached
tools/checks/import_boundary.py (+ tests)          rule for packages/ada; goldilocks_ada importable by no package
tools/checks/light_env.py (+ tests)                replaces chat_env.py; checks the chat and the Ada environment
tools/checks/no_shell.py (+ tests)                 (A4) no shell in the light packages
tools/check.sh                                     the Ada environment; three app builds
fixtures/qe-outputs/                               (A3) recorded pw.x XML and dos.x outputs of public structures
deploy/ada/                                        (A5) how Ada is installed in a VM; public, generic
AGENTS.md  REVIEW.md  README.md                    rule 4 covers Ada; high-risk paths; layout and status
```

**Package boundaries after this change** (the workbench plan's table is edited to match)

| Package | Holds | Depends on | Never imports |
|---|---|---|---|
| goldilocks-workbench | as before, plus the light agent factory (ada D3) and Post Analysis functions and readers (ada D11) | as before, plus `langchain` | goldilocks_chat, goldilocks_ada, goldilocks_agent, deepagents, aiida, torch, janus_core |
| goldilocks-chat | chat server, chat profile, retention | goldilocks-workbench | the above, any shell |
| goldilocks-ada | Ada server, Ada profile, the `slurm` module | goldilocks-workbench | goldilocks_chat, goldilocks_agent, deepagents, aiida and its plugins, MLIP packages; no shell (ada D8, ada D10) |
| goldilocks-agent | as before; Post Analysis as calcfunctions wrapping the shared functions (ada D11) | as before | goldilocks_chat, goldilocks_ada |

## Order of work

**How each PR works.** As in the workbench plan: one PR per heading, each under ~800 changed lines excluding
generated files; a v4-process D11 description with high-risk categories and the pasted check output; the owner runs
`goldilocks-review`, approves and merges. A spike result that contradicts a spec decision stops the dependent
milestones and goes to the owner as a new record.

**Sequence.** A0 → S10's script (the owner runs it when an Ada login allows) → the workbench plan's Phase 1 (S1 to
S9) and Phase 2 (M1 to M4) → A1 → A2 → A3 → A4 → A5 → the workbench plan's Phase 3 (M5 onwards).

**Gates.** M2 before A1; M3 and M4 before A2; recorded outputs before A3; S10 before A4 and A5. If S10 has no result
when A3 is done, the owner is asked whether M5 starts before A4 (ada D1's revisit clause).

**PR A0: the Ada plan and the fourth package** (categories 2, 3, 4). This plan first, then the edits to the workbench
plan; `packages/ada` with the `goldilocks-ada` entry point (`--version`, help) and its test, as chat's;
`frontend/apps/ada` blank, as the other two; the import boundary gets the rule of ada D8 (goldilocks_ada imports
none of goldilocks_chat, goldilocks_agent, Deep Agents, AiiDA, AiiDA plugins, MLIP packages; no package imports
goldilocks_ada); `chat_env.py` becomes `light_env.py <form>`, which checks a fresh environment of either light form
(also forbidding the other light form); `tools/check.sh` builds and checks the Ada environment and builds three apps;
`AGENTS.md` rule 4 names Ada and the healthy run is updated; `REVIEW.md` adds category 3
`packages/ada/src/goldilocks_ada/slurm/**`; `README.md` gives Ada's status and the layout. Implements ada D7 (app
shell), ada D8. Proof: planted imports fail (below); `light_env.py ada` passes on a fresh `uv sync --package
goldilocks-ada --no-dev`; the check ends `check: all passed` on Linux and macOS.

**S10: the Ada platform** (gates A4, A5; the owner runs it; ada D2.3). A script under `spikes/S10/` that prints only
generic facts and exit codes, opens no key file and prints no secret; host names, accounts and paths stay in the
owner's copy and in ddmms/goldilocks (`AGENTS.md`, rule 8). It answers:
1. *One user per VM*: whether the VM persists between logins and is used by one person; CPU, memory, disk; OS and
   architecture.
2. *How SCARF is reached*: whether `sbatch`, `squeue`, `sacct`, `scancel` run on the VM against SCARF; otherwise
   whether `ssh -o BatchMode=yes <host> true` succeeds with the VM's own configuration, and the remote login shell;
   whether SCARF's work area is mounted on the VM; which of `rsync`, `scp`, `sftp` exist.
3. *What a VM can install and reach*: Python and uv; a container runtime; HTTPS to PyPI, GitHub and GHCR; the model
   endpoint and goldilocks-dft, if the owner gives their URLs (status codes only).
4. *How the user reaches a web app in the VM*: a browser inside the VM, Ada's proxy, or a forwarded port (the owner's
   observation).
5. *Slurm on SCARF*: `MinJobAge` from `scontrol show config`; how far back `sacct` finds the user's jobs; the
   accounting retention, from SCARF's documentation or its administrators.

Pass: each item answered; the transport (local or SSH) chosen; the owner decides where the model and goldilocks-dft
run for Ada; the result written as `changes/2026-11-26-ada/spikes/S10-ada-platform.md`. If one instance would serve
several users, or SCARF is reached other than with the user's own access, A4 and A5 stop (ada D2's revisit clause).

**Changes to M1 to M4** (made in those milestones; listed in the workbench plan): M1's side-effect classes include
"submits to a cluster" and "destructive", which Ada's tools use; M3's Structure Builder takes size limits and a
time limit per operation from the form's profile (ada D6), refuses a larger result and stops a longer operation,
each with a typed error naming the limit; M3's DFT module keeps goldilocks-dft's archive with its manifest, which Ada
submits; M4's shared packages build three apps.

**A1: the light agent factory** (categories 2, 3). `goldilocks_workbench/light_agent/`: given a form profile
(modules, prompt, limits), returns `create_agent` with M2's model layer, ToolCallLimitMiddleware (6 calls a turn,
from `budgets.toml`) with a wrap-up note, ModelCallLimitMiddleware, HumanInTheLoopMiddleware on tools whose registry
side-effect class needs confirmation, `interrupt()` for choices inside tools, M2's carried fixes and error
middleware, and M2's checkpointer. `langchain` joins the shared package's dependencies. Implements D3, ada D3.
Proof: scripted-model tests: the seventh call in a turn is refused with the wrap-up note; a confirmation tool pauses
and resumes on approve, edit and reject; a choice returns the user's pick; a paused run resumes after a real process
restart; text typed at a pending card is a rejection (M2's rule); `light_env.py chat` still passes. Waits on M2.

**A2: Ada's server, profile and app, without SCARF** (categories 2, 3). `goldilocks-ada serve` on M2's server kit
and security model; `config.py`; Ada's profile (Find in Databases, DFT limited to the tasks above, Structure Builder
without limits, Post Analysis once A3 lands); `frontend/apps/ada` from M4's packages. Implements ada D7, ada D10.
Proof: Playwright smoke on the recorded-reply model (search, structure, DFT settings, bundle); no shell tool in Ada's
registry. Waits on M3, M4.

**A3: Post Analysis functions and the QE reader** (category 1). `goldilocks_workbench/post_analysis/`: a reader for
pw.x's XML output (`<prefix>.save/data-file-schema.xml`, QE's machine-readable output) and for dos.x's data file,
using the standard library with `defusedxml`; one conversion table in `units.py`, each factor citing its source;
functions that return M1's value records with units: SCF summary (exit status, convergence, total and Fermi energy,
total and per-site magnetisation), relaxation summary (final structure with its record, energy, largest residual
force and stress, converged), band gap (direct or indirect) from eigenvalues, DOS with the Fermi level. A run that did
not end normally or did not converge returns a typed "not converged" result and no values. Plots are renderers
(hook 16), not functions. Dependencies already planned for the shared package (ase, pymatgen, numpy) and
`defusedxml`; anything heavier goes into an `analysis` extra that chat does not install (ada D11's known cost).
Implements ada D11.1, ada D11.4. Proof: on recorded outputs of public structures (Si: SCF, bands, DOS; bcc Fe: spin-
polarised SCF), each value equals what QE printed in the same run's output, within print precision; a truncated and a
non-converged output give "not converged"; every factor in `units.py` names its source. Waits on recorded outputs,
which the owner makes once by running goldilocks-dft bundles on SCARF.

**A4: the `slurm` module and SCARF** (categories 3, 5; riskiest). As ada D5, with these choices:
- **Site.** `sites/scarf.toml` holds the partitions and limits Ada checks a request against, taken from SCARF's public
  documentation with URL and date. A test compares them with goldilocks-dft's SCARF profile (recorded
  `/capabilities`); at run time the stricter limit wins and the doctor reports a mismatch.
- **Transport.** `LocalTransport` and `SshTransport` (S10 picks the default) run only `sbatch`, `squeue`, `sacct`,
  `scancel` and the file-transfer program, with argument lists (`shell=False`); SSH uses `-o BatchMode=yes` and the
  VM's own configuration. Every argument and remote path is checked against `[A-Za-z0-9_./=:,-]` before it runs, on
  both transports.
- **Submit.** The bundle's files are checked against the manifest's sha256 values; the digest of the manifest is the
  inputs' digest. The record (key, conversation, digest, requested resources, remote folder) is written before
  `sbatch` runs. The remote folder is one per task under the user's work area. Ada runs
  `sbatch --parsable --job-name=gl-<key> --chdir=<folder> --partition --nodes --ntasks --ntasks-per-node --time
  [--account] submit.sh` with the values the user approved; command-line options take precedence over the script's
  `#SBATCH` lines, so what runs is what was approved. The job ID is written as soon as `sbatch` returns.
- **Approval and caps.** The card shows goldilocks-dft's `job` record (partition, nodes, tasks, wall time) and the
  core-hours; edits are human values checked against the site's limits. Caps per conversation: 10 jobs and 1,000
  core-hours (owner's answer 4), checked in code before the card and again before `sbatch`; reaching one shows a card
  on which the user may raise it, recorded. Cancel is destructive and confirmed each time.
- **Reconcile** at start-up exactly as ada D5.7: by job ID with `sacct -j`; by name with `squeue` and
  `sacct -S <record time>`; "not submitted" only if both queries succeeded and the record is younger than SCARF's
  accounting retention (S10); otherwise "needs check".
- **Poller and fetch.** A poller in Ada's server (interval in `config.py`) updates states and shows a card when a job
  ends; the status tool only reads (hook 14). Fetch copies back a fixed include list (the steps' outputs, XML and
  data files, `goldilocks.json`), never wavefunctions or charge densities, within a size limit, into the task folder.
- **No shell check.** `tools/checks/no_shell.py`: in workbench, chat and ada, `subprocess`, `os.system`, `os.popen`,
  `os.exec*`, `os.spawn*`, `pty` and `asyncio.create_subprocess_*` appear only in listed files (Ada's transport; the
  shared goldilocks-dft runner of M3), and `shell=True` nowhere.

Implements ada D4, ada D5, ada D10. Proof: the tests below on fake Slurm and SSH stand-ins. Waits on S10.

**A5: Ada on a VM** (category 3; with the owner). Installation as S10 allows (uv with the locked environment, or a
container), described generically in `deploy/ada/`; site details in ddmms/goldilocks. `goldilocks-ada doctor`
(numbered checks: store file permissions, transport, scheduler commands, work area writable, model reachable,
goldilocks-dft ready, SCARF limits agree). M2's security model in the VM: localhost and a per-launch token; with
Ada's proxy, Host and Origin allowed from configuration. No LangSmith variables (D48). The owner's choices of Ada's
model and goldilocks-dft's location are written into this plan. Proof: live, by the owner (below). Waits on S10, A4.

After A5, Phase 3 of the workbench plan starts. M18 (chat) reuses A1's factory and adds Structure Builder with
owner's answer 3's limits to chat's profile.

## Edits to the workbench plan (in A0)

Allowed while its implementation is open (v4-process D4); each edit names ada D*n*.
- "What the first version is", item 3: goldilocks-Ada is built after M4 and before M5 (ada D1; this plan).
- Owner decision 1: notes that ada D1 overturns it in part (the light agent and Ada come before the agent's core).
- "Not in the first version": goldilocks-Ada removed.
- "Files that change" and the package table: as in this plan's table (ada D3, D8, D11).
- Tool modules table: Structure Builder for chat (with limits), agent and Ada (ada D6); Post Analysis functions in the
  shared package, used by Ada, wrapped by the agent (ada D11); a `slurm` row for Ada (ada D5).
- Order of work: the gates above; a heading "Phase 2b: goldilocks-Ada" pointing here; M1, M3 and M4 as under
  "Changes to M1 to M4"; M9's Post Analysis calcfunctions wrap the shared functions, and a test checks that A3's
  reader and aiida-quantumespresso's parser give the same values on the recorded outputs; M18 as above.
- Proof: `chat_env.py` becomes `light_env.py`; the import-boundary and no-shell rows cover Ada.
- Risk 4: the mitigations below replace "agent first" and the "Not in the first version" list's mention of Ada.
- "Decisions to milestones" and "Spec items resolved here": a line pointing to this plan.

## Risks

| # | Risk | Where | Mitigation |
|---|---|---|---|
| 1 | **The Ada platform is unknown** (VM, transport, network, how the app is reached) | A4, A5 | S10 before any code that depends on it; A1 to A3 need none of it; the transport interface; ada D1's revisit clause |
| 2 | **Commands built for SCARF**: injection through a remote login shell | A4 | fixed programs; argument lists; the allowed-character list on both transports; tests with metacharacters; `no_shell.py` |
| 3 | **Double or lost submissions** | A4 (riskiest) | record before `sbatch`; key in the job name; reconcile by ID, then by name; "needs check"; the kill test |
| 4 | **SCARF credentials and terms** | A4, A5 | one instance per user VM (ada D2); the code never reads credentials (v4-process D21); ada D2's revisit clause stops SCARF features |
| 5 | **Wrong numbers from our reader** | A3 | QE's XML, not screen text; one units table with sources; fail closed; compared with QE's printed values now and with aiida-quantumespresso's parser in M9 |
| 6 | **Bundle or SCARF profile changes in goldilocks-dft** | A4 | manifest `schema_version` checked, unknown refused; sha256 per file; drift test against the recorded SCARF profile; the dependency rows below |
| 7 | **The model submits too much** | A4 | each submission approved by the user; caps in code; no model tool can answer a card |
| 8 | **Scope for one maintainer** (workbench risk 4, without "agent first" and without Ada on the "Not in" list) | all | Ada reuses M1 to M4 and adds one module (`slurm`); "Not in Ada's first version" above; S10 first; ada D1's revisit clause lets M5 start if Ada stalls; M18 shrinks, as chat reuses A1 |
| 9 | **Private deployment details** | S10, A5 | public records hold generic facts only; details in ddmms/goldilocks (rule 8) |

A4 is the riskiest step: it is the only place where Ada acts outside its own VM.

## Proof

**The check.** `bash tools/check.sh` ends `check: all passed`. After A0 it also builds the Ada environment
(`uv sync --locked --package goldilocks-ada --no-dev` in a temporary folder) and runs `light_env.py ada`, and builds
three apps. After A4 it runs `no_shell.py`. Tests marked `live` never run in CI; the owner runs them and records the
results in the PR.

**The stand-ins.** Fake `sbatch`, `squeue`, `sacct`, `scancel`, `ssh` and the transfer program, put first on `PATH` in
tests, record their arguments and keep job states in a JSON file, so A4's tests run offline on Linux and macOS.

| Test | Decision | A pass | Milestone |
|---|---|---|---|
| Import boundary | ada D8 | planted imports fail: goldilocks_ada importing goldilocks_chat, goldilocks_agent, deepagents, aiida, aiida_quantumespresso or torch; goldilocks_workbench, goldilocks_chat or goldilocks_agent importing goldilocks_ada | A0 |
| Ada environment | ada D8 | a fresh Ada environment imports goldilocks_ada and holds no goldilocks-agent, goldilocks-chat, deepagents, aiida-*, janus-core, mace-torch or torch | A0 |
| Light agent | D3, ada D3 | the seventh call refused with the wrap-up note; approve, edit, reject; a choice by `interrupt()`; resume after a real restart | A1 |
| Ada has no shell | ada D10, D35 | no shell tool in Ada's registry; `no_shell.py` fails on a planted `shell=True`, `os.system` or `subprocess` outside the listed files | A2, A4 |
| Reader | ada D11, rule 2 | values equal QE's printed values within print precision; truncated and non-converged outputs give "not converged" and no values; every unit factor names its source | A3 (and M9's cross-check) |
| Arguments | ada D5.2 | arguments and paths holding any character outside the list (semicolon, pipe, ampersand, dollar, backtick, parentheses, angle brackets, asterisk, question mark, quotes, backslash, space, newline) are refused on both transports before any program runs | A4 |
| No double submission | ada D5.7 | the server SIGKILLed before the record, between record and `sbatch`, and between `sbatch` and writing the job ID: 0 duplicates in 20 trials; a lost answer is found by name; a failed query or a record older than the retention gives "needs check" | A4 |
| Approval and caps | ada D5.6, D10 | no answer, no `sbatch`; a scripted model cannot answer a card; the eleventh job or a request beyond 1,000 core-hours stops at a cap card; cancel is confirmed each time | A4 |
| What runs is what was approved | ada D5.5 | `sbatch`'s arguments carry the approved values; a file whose sha256 differs from the manifest is refused; an unknown manifest version is refused | A4 |
| Site limits | ada D5.1 | a request beyond SCARF's limits is refused; the drift test against the recorded SCARF profile passes | A4 |
| Size limits | ada D6 | in chat's profile a result above 500 atoms or a supercell above 64 cells is refused with the limit named; an operation past 30 s is stopped; Ada's profile has no limit | M3, M18 |
| Live, on an Ada VM (owner) | ada D2, D5 | doctor green; an SCF bundle approved, run on SCARF, finished card, fetched, analysed; killing the server between record and `sbatch` leaves one job; cancel works | A5 |

## goldilocks-dft dependencies (Ada's rows; added to the workbench plan's list)

| # | Need | Decision | Waits | If late |
|---|---|---|---|---|
| A-1 | keep the bundle layout: ZIP from `/run`, `goldilocks.json` schema 3 with sha256 per file, `submit.sh`, the `job` record | ada D5.5 | A4 | pin goldilocks-core 0.3.3 |
| A-2 | the manifest names each step's executable and output files | ada D11 | A3, A4 | map step names to programs from `/capabilities`' task table; fetch by the fixed include list |
| A-3 | a SCARF HPC profile kept current | ada D5.1 | A4 | Ada's site file; the stricter limit wins |

## Spec items resolved here

| Item | Resolution | Owner to confirm? |
|---|---|---|
| ada D2's spike | S10, run by the owner | no |
| ada D5.1, site settings | partitions and limits in `sites/scarf.toml` from SCARF's public documentation; no module names, which overturns that part of ada D5.1 | decided (owner's answer 5) |
| ada D5.5, scheduler options | approved values on `sbatch`'s command line, over the script's `#SBATCH` lines | no |
| ada D5.6, caps | 10 jobs and 1,000 core-hours per conversation | decided (owner's answer 4) |
| ada D6, size limits | chat only: 500 atoms, 64 cells, 30 s | decided (owner's answer 3) |
| ada D11.2, Post Analysis in chat | not in chat's first profile: chat runs no jobs, so it has no results to analyse | no |
| ada D11, known costs | the shared package's planned dependencies plus `defusedxml`; heavier ones in an `analysis` extra | no |
| Open: how Ada reads fetched results | a QE reader in the shared package (A3) | decided (owner's answer 2) |
| Open: Ada's model; where goldilocks-dft runs for Ada | the owner decides after S10; A5 writes it here | yes, after S10 |
| Open: how the app is reached in a VM | S10 item 4; A5 | after S10 |
| Order | A0 now; A1 to A5 after M4, before M5 | decided (ada D1; owner's answer 1) |
