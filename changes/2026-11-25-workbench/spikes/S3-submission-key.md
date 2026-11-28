# S3: the submission key through aiida-quantumespresso

Spike S3 (workbench plan, Phase 1, "S3 submission key through aiida-quantumespresso"; it gates M8 and M9).

- Run on 2026-11-28 by Claude, on the owner's Mac and in a Linux container on it.
- Scripts: `spikes/S3/s3_core.py`, `s3_experiments.py`, `s3_inside.py`, `s3_compare.py`, at the commit that adds this
  file; the runs used them. Tables: `spikes/S3/s3_report.py`. The raw JSON lines and the bundles are not committed.
- Each figure below comes from one run of every experiment per system with the final code.
- Earlier runs, made while the harness was being fixed, agree with these. One fix changed how a finding is counted:
  the submit node first took a process with no state at all for a running one; it now treats it as not started
  (item 3).
- The inputs are 11 bundles from goldilocks-core 0.3.3 (PyPI, the predecessor's pin), fetched once over HTTP
  (AGENTS.md rule 7) and used by both systems. Its HTTP API serves no example structures, so the three structures
  (Si, Fe bcc, Pt fcc) are the ones bundled with goldilocks-core, read from the folder its CLI prints.

**Isolation.** As in S2, every experiment made its own profile ("s3") in a fresh folder under
`~/.cache/goldilocks-spikes/s3/`, with `AIIDA_PATH` set before AiiDA was imported.
- After each experiment no daemon or broker of its run was alive (6 of 6 experiments on each system).
- The names and modification times under the owner's `~/.aiida` were the same before and after. Their contents
  were never read.

## Environment

   | | macOS | Linux |
|---|---|---|
| System | macOS 27.2.1, arm64 (Apple M5 Pro, 48 GB) | Debian 13 (python:3.12-slim), aarch64, Docker 29.8.0 on the same Mac |
| Python | 3.12.13 | 3.12.16 |
| AiiDA | aiida-core 2.9.4, aiida-quantumespresso 5.1.0, aiida-pseudo 1.11.0, qe-tools 2.3.0, plumpy 0.26.1 | the same, from `uv.lock` |
| Profile | `verdi presto --use-zeromq`: SQLite storage, the ZeroMQ broker, presto's `localhost` | the same |
| pw.x | none: a stand-in script that sleeps 1 s and writes nothing | the same stand-in, and Debian's Quantum ESPRESSO 6.7 (`6.7MaX`) for the caching experiment |
| goldilocks-core | 0.3.3, HPC profile `scarf` (its only one) | the bundles fetched on macOS |

With the stand-in, aiida-quantumespresso's parser fails each PwCalculation (exit 305) and PwBaseWorkChain, which has no
handler for that code, ends with exit 402. The kill trials need jobs that run and end, not physics.

## Answers

1. **The key route: a reserved prefix in `metadata.label`, set at node creation. Extras cannot be set then.**
   - A process's `metadata` takes `label`, `description`, `store_provenance`, `call_link_label` and `disable_cache`
     (and `dry_run` and `options` for a CalcJob). Extras were refused both ways: on the builder ("Unknown builder
     parameter: extras") and passed to `submit()` ("Unexpected ports {'extras': ...}, for a non dynamic namespace").
   - aiida-core copies the label onto the node in `_setup_metadata` (`aiida/engine/processes/process.py:784-795`)
     before the node is first stored (`store_all()`, `process.py:665`).
   - No work chain of the kill trials lacked its key, including those killed while the node was being stored
     (48 of 48 work chains on each system; item 2).
   - A lookup by label found the work chain right after `submit()` returned, in 2 ms on both systems.
   - The work chain's PwCalculation has an empty label. If `pw.metadata.label` is also set, the PwCalculation carries
     that label, and a lookup of it finds the child.
   - The label of a terminated, sealed work chain could be changed, and read back changed.
2. **0 duplicates in 45 kill trials per system.** The submit node (`s3_inside.submit_node`) looks the key up, takes
   the process over if AiiDA has one, and submits a PwBaseWorkChain only if it has none (D17.1). Each trial killed it
   with SIGKILL at one point of aiida-core 2.9.4's own `submit()` (`aiida/engine/launch.py:160-169`):

   | kill point | where |
   |---|---|
   | before-submit | the lookup found nothing; `submit()` not yet called |
   | node-stored | `instantiate_process` returned: the node is stored and has entered `created` |
   | checkpoint-saved | `submit()` saved the checkpoint; the task not yet sent |
   | task-sent | `continue_process` returned: the task was sent, the agent's own checkpoint not yet written |
   | task-sent (confirmed) | the same, with the task sent with `no_reply=False` and the broker's acknowledgement awaited (item 6) |
   | random | SIGKILL from outside, at a random time from 0 to 1.5 times the median `submit()` duration (0.055 s on macOS, 0.080 s in Linux) |

   After each trial the submit node ran again in a new process, as D17.3 has it ("that node runs again").

   | kill point | system | trials | the submit node, run again | states found |
   |---|---|---|---|---|
   | before-submit | macOS | 5 | submitted 5 | none |
   | node-stored | macOS | 5 | needs check 5 | created 5 |
   | checkpoint-saved | macOS | 5 | needs check 5 | created 5 |
   | task-sent | macOS | 5 | took over 5 | waiting 5 |
   | task-sent (confirmed) | macOS | 5 | took over 5 | waiting 5 |
   | random | macOS | 20 | submitted 8, needs check 7, took over 5 | created 5, no state 2, waiting 5 |
   | before-submit | Linux | 5 | submitted 5 | none |
   | node-stored | Linux | 5 | needs check 5 | created 5 |
   | checkpoint-saved | Linux | 5 | needs check 5 | created 5 |
   | task-sent | Linux | 5 | took over 5 | waiting 5 |
   | task-sent (confirmed) | Linux | 5 | took over 5 | waiting 5 |
   | random | Linux | 20 | submitted 7, needs check 5, took over 8 | created 2, no state 3, waiting 8 |

   - Afterwards, on each system: 48 keys (45 trials and 3 calibration submissions), 48 work chains, 0 work chains
     without a key, 0 keys with more than one process.
   - The plan's pass, "0 duplicates in 20 kill trials", holds.
3. **What a process that never started looks like.**
   - Its state is `created`, or it has no process state at all. aiida-core stores the node with the state unset and
     sets `created` a moment later (`process.py`, `_setup_db_record` and `on_entered`); 2 of the 20 random kills on
     macOS and 3 in Linux fell in between.
   - Its checkpoint is there if the kill came after the node entered `created` (every node of the node-stored and
     checkpoint-saved points). It is missing if the kill came before: 4 of the 7 random kills that left a process
     that never started on macOS (2 with no state, 2 in `created`), and 4 of 5 in Linux (3 with no state, 1 in
     `created`).
   - The broker's files hold no task for it, pending or processing.
   - Nothing in AiiDA marks it. These are S2's lost submissions, made by a crash of the submitter instead of the
     broker.
   - **A queued process looks the same on the node.** With one process slot, two jobs waiting for the slot were in
     `created` with a checkpoint, like the lost ones; only the broker's queue held their tasks (the tasks experiment,
     the same on both systems). The submit node therefore reads the queue before it decides (item 5).
4. **Sending the task again runs it, if the node has a checkpoint.** After the trials, each process that had not
   started was revived by hand with aiida-core's `revive_processes`, the documented last resort, one at a time:

   | system | state before | checkpoint | revived | ended |
   |---|---|---|---|---|
   | macOS | created | yes | 13 | finished, exit 402 (the stand-in's failure): 13 |
   | macOS | created | no | 2 | excepted: 2 |
   | macOS | no state | no | 2 | excepted: 2 |
   | Linux | created | yes | 11 | finished, exit 402: 11 |
   | Linux | created | no | 1 | excepted: 1 |
   | Linux | no state | no | 3 | excepted: 3 |

   - No revive created a second process.
   - Without a checkpoint, aiida-core's persister refuses to load the process
     (`aiida/engine/persistence.py:119-120`), and the worker marks it excepted
     (`aiida/engine/processes/launcher.py:124-127`).
5. **aiida-core's way of listing the broker's tasks rewrites them while the daemon runs.**
   - `get_process_tasks()` reads the ZeroMQ broker's queue by building a `PersistentQueue` on its folder
     (`aiida/brokers/zeromq/broker.py:215-220`). Building one moves every task in `processing/` back to `pending/`
     (crash recovery, `aiida/brokers/zeromq/queue.py:57-65`).
   - In the tasks experiment the running job's task moved so, on both systems. When the job ended, the broker's
     acknowledgement deleted nothing (`unlink(missing_ok=True)`, `queue.py:166`), and the task stayed on disk as
     pending.
   - After a daemon restart, the broker loaded it, the queue emptied, and the finished job was unchanged. The
     daemon's log said nothing about it.
   - `verdi process repair`, which uses the same call, refuses to run while the daemon runs
     (`aiida/cmdline/commands/cmd_process.py:512`).
   - S3 reads the task files without changing them instead (`s3_env.broker_tasks`). Their layout is not a documented
     interface.
6. **A confirmed submission costs one round trip; S3 saw no loss without it.**
   - `submit()` sends the task with `no_reply=True` (`launch.py:169`), through a non-blocking ZeroMQ send
     (`aiida/brokers/zeromq/communicator.py:474`), and returns without waiting.
   - With `no_reply=False`, the broker acknowledges once it has written the task to disk
     (`aiida/brokers/zeromq/server.py:288-325`).
   - Every trial killed right after the send found its task at the broker: 5 of 5 plain and 5 of 5 confirmed per
     system, and the random kills that came after the send (5 on macOS, 8 in Linux).
   - S2's case, a submitter holding a stale socket after a broker restart, was not tested here.
7. **The interim route keeps every value of goldilocks-core's pw.x inputs, except the Hubbard U, and cannot read band
   paths or any input of another executable.** Each pw.x input went through aiida-quantumespresso's own parser
   (`create_builder_from_file`, `aiida_quantumespresso/tools/pwinputparser.py:64`), a dry run
   (`store_provenance=False`), and a value-by-value comparison with core's file (`s3_compare.py`).

   | | files |
   |---|---|
   | pw.x inputs in the 11 bundles | 13 |
   | built and dry-run | 12 |
   | every value kept, beyond the plumbing below | 11 |
   | Hubbard U lost (fe_u) | 1 |
   | refused by the parser (si_band's `bands.in`) | 1 |
   | inputs of other executables: ph.x, q2r.x, matdyn.x (2), dos.x, bands.x | 6, no parser |

   - "Kept" means: every namelist value parses to the same value; the species, their masses, pseudopotential names
     and order are the same; the cell and the atoms' Cartesian positions differ by 0.0 Å; the k-point mesh is the
     same.
   - fe_afm1's `starting_magnetization(1) = 0.3125` and `(2) = -0.3125` stayed on species Fe1 and Fe2, in that order.
   - The pseudopotential files of all 12 dry runs were byte-identical to the sha256 in core's manifest.
   - **fe_u lost its U.** Core writes QE's `HUBBARD (ortho-atomic)` card. qe-tools 2.3.0 does not read that card, and
     `create_builder_from_file` makes no Hubbard input, so the dry run's input and the work chain's had no U. Nothing
     reported it.
   - **si_band's bands step was refused:** "K_POINTS card not found", on core's `K_POINTS crystal_b` path.
   - aiida-quantumespresso 5.1.0 has input parsers for pw.x and cp.x only (`aiida_quantumespresso/tools/`).
   - The plumbing, the same in all 12:

     | key | core | in the dry run | why |
     |---|---|---|---|
     | `CONTROL.pseudo_dir` | `'./pseudo'` | `'./pseudo/'` | the plugin fixes it (`_blocked_keywords`, `calculations/pw.py:27-40`; `calculations/__init__.py:509`) |
     | `CONTROL.outdir` | `'./out'` | `'./out/'` | the same (`__init__.py:510`) |
     | `CONTROL.prefix` | `'pwscf'` | `'aiida'` | the same (`__init__.py:511`) |
     | `CONTROL.verbosity` | not set | `'high'` | the plugin's default when the input sets none (`__init__.py:512`) |

     `ibrav`, `nat` and `ntyp` are rewritten by the plugin with the same values.
   - **PwBaseWorkChain passed the dry run's input on unchanged in 11 of 12 cases.** For si_phonon's `scf.in`, which
     has no `max_seconds` (core writes none for its phonon tasks), the work chain added `max_seconds = 3420`,
     0.95 of the job's 3,600 s (`aiida_quantumespresso/workflows/pw/base.py:428-434`).
   - In Linux, core's Si SCF through this route ran to exit 0 under PwBaseWorkChain with the real pw.x (item 9).
8. **PwBaseWorkChain's handlers** (aiida-quantumespresso 5.1.0; exit codes read from each handler's decorator, actions
   from `workflows/pw/base.py`). "Repair-table row" is the plan's retry list ("Spec items resolved here", code-review
   decisions-log row 81). The class is Claude's reading of D9.7's words.

   | handler | runs for | what it changes | D9.7 class (Claude's reading) | repair-table row |
   |---|---|---|---|---|
   | `handle_electronic_convergence_stuck` | 150 (its monitor's message only) | relax: `IONS.upscale` × 0.3; full restart | numerical stability | SCF: handler |
   | `handle_relax_recoverable_ionic_convergence_bfgs_history_error` | 520, 521 | relax with fewer than 5 symmetries: **moves the atoms at random once** (standard deviation 0.01 Å) and aborts if it fails again; other relax: `ion_dynamics = 'damp'`; vc-relax: `trust_radius_min` × 0.1, then `damp` and `damp-w` | algorithm; the random move changes the structure, not a setting | — |
   | `handle_known_unrecoverable_failure` | **none**: its list is empty, so it never runs | — | — | — |
   | `handle_diagonalization_errors` | 462–468 | `ELECTRONS.diagonalization` to another algorithm, cg last; then aborts | algorithm | SCF: diagonalisation |
   | `handle_out_of_walltime` | 400 | full restart from the last structure, with the same wall time | continuation | wall time: the handler continues, asking for no more |
   | `handle_ionic_interrupted_partial_trajectory` | 503 | restart from scratch from the last structure | continuation | — |
   | `handle_vcrelax_converged_except_final_scf` | 501 | accepts the structure, ends with exit 501 | none | — |
   | `handle_relax_recoverable_ionic_convergence_error` | 500, 502, 520, 521 | restart from the last structure | continuation | ionic step limit: it continues |
   | `handle_vcrelax_recoverable_fft_significant_volume_contraction_error` | 542 | `CELL.cell_factor` doubled | numerical stability | — |
   | `handle_relax_recoverable_electronic_convergence_error` | 510, 511 | `mixing_beta` × 0.8, restart from the last structure | numerical stability | SCF: mixing |
   | `handle_electronic_convergence_warning` | 710 | ends with exit 710 (only when `scf_must_converge` is false; core does not set it) | none | — |
   | `handle_electronic_convergence_not_reached` | 410 | `mixing_beta` × 0.8, full restart | numerical stability | SCF: mixing |
   | `sanity_check_insufficient_bands` | 0, with smearing | **after a successful run**, if the highest band is occupied: `nbnd` + max(5 %, 4), restart from the charge density | a value core sets (`nbnd`) | — |

   - Priority order, highest first: 602, 601, 590, 585, 580, 575, 570, 560, 555, 550, 420, 410, 0.
   - A failure no handler takes ends the work chain: `on_unhandled_failure` has no default and reads as `abort`
     (`aiida/engine/processes/workchains/restart.py:315`). That covers every code below 400 except 150, and four
     codes the cache keeps: 461, 481, 531, 541. The retry list's "wall time and memory: more resources" rows
     (scheduler codes 110 and 120) are among them.
   - `max_iterations` defaults to 5.
   - `handler_overrides` accepted `sanity_check_insufficient_bands` by name and refused an unknown name.
   - The 410 handler fired with the real pw.x in Linux: `mixing_beta` 0.4, then 0.32, with `restart_mode = 'restart'`
     (item 9).
9. **Caching** (Linux, real pw.x, caching on for every process as D39 has it):

   | case | exit | from the cache |
   |---|---|---|
   | a PwCalculation with `electron_maxstep = 1` (one SCF step: a real failure) | 410 | no |
   | the same, identical | 410 | **yes**, the failure reused |
   | the same, asking for twice the wall time | 410 | **yes**, the failure reused |
   | the same, asking for 2 MPI processes | 410 | no |
   | the same, with `metadata.disable_cache` | 410 | no |
   | PwBaseWorkChain on the same input (`max_iterations` 2), calculation 1 | 410 | no (see below) |
   | its calculation 2: `mixing_beta` 0.4 to 0.32, `restart_mode = 'restart'` | 410 | no; the work chain ended with 401 |
   | the same work chain, identical: calculation 1 | 410 | **yes**, from the first work chain's calculation 1 |
   | its calculation 2 | 410 | **yes**, from the first work chain's calculation 2; the work chain ended with 401 |
   | the same work chain with `pw.metadata.disable_cache`: calculations 1 and 2 | 410, 410 | no, no; both carried `disable_cache` |
   | PwBaseWorkChain on core's Si SCF | 0 | no |
   | the same, identical | 0 | **yes**, the success reused |

   - aiida-core leaves the wall time and the memory asked for out of a CalcJob's hash (`_hash_ignored_attributes`,
     `aiida/orm/nodes/process/calculation/calcjob.py:180-189`), and not the number of processes. S3 tested the wall
     time and the processes.
   - The work chain's first calculation was not served from the direct one's cache: the work chain always passes a
     `settings` input, empty here (`workflows/pw/base.py:373`; `restart.py:241`), and the direct one had none.
   - An identical failed work chain replays from the cache: each restart's inputs are the same as the first run's
     restart, so every calculation is found again.
   - `pw.metadata.disable_cache` reached both calculations of the work chain, the handler's restart included.

## Decisions this touches

Checked against the workbench spec and plan; the decisions are the owner's to revisit.

- **D17's amendment** is to be revisited if "a plugin's jobs cannot carry the key from the moment they are created,
  so that 'not found' no longer means 'never submitted'". As Claude reads it, S3 does not meet it: PwBaseWorkChain's
  node carries its key from its first stored version, and every kill that left no node was followed by exactly one
  submission. The converse does not hold: a found process may never have been submitted (item 3).
- **D17.3** ("anything that cannot be decided ... goes to a 'needs check' state"; "A job whose state is unclear is
  never resubmitted automatically"):
  - The processes that never started are such cases, and nothing in AiiDA marks them (item 3).
  - Reviving one creates no second process (item 4). Whether the watcher may revive without asking, or the card
    offers it, is the owner's decision under D17.3.
  - One without a checkpoint cannot be revived; it ends excepted.
- **D17.1** ("The key is stored in AiiDA together with the job"): the label is that place, but it can be changed
  after the fact, by a user or by another tool working on the same profile (item 1).
- **D22** ("goldilocks-dft's parameters always set the inputs") and **D37** ("Every setting in a calculation's input
  comes through goldilocks-dft's rules"):
  - Through the interim route, a Hubbard U set in goldilocks-core does not reach pw.x, and nothing reports it
    (item 7).
  - The plugin adds `verbosity` and changes three folder and file names; PwBaseWorkChain adds `max_seconds` where
    core writes none. The plan's round-trip test allows "a reviewed list of plugin plumbing keys"; item 7's table and
    the work chain's `max_seconds` are that list for the owner to review.
- **D9.7** ("A failed step is first repaired by the AiiDA plugin's own handlers"; "Repairs change only settings for
  numerical stability"):
  - Two handlers do more than D9.7's examples (mixing, algorithm, step limits): `sanity_check_insufficient_bands`
    raises `nbnd`, a value goldilocks-core sets, after a successful run; the BFGS handler moves the atoms of a
    low-symmetry relaxation at random once.
  - Whether these count as numerical-stability repairs is the owner's decision. `handler_overrides` can switch either
    off per work chain (item 8).
- **D39** (caching on by default) is to be revisited "if cached results are reused where users expected a fresh
  run". Read literally, S3 meets that condition in the cases a retry is likely to take:
  - A job identical to a finished pw.x failure, or one that asks only for more wall time, got the old failure back.
  - An identical failed work chain replayed both of its failed calculations and ended as before.
  - The plan's resolution, that retries after failures turn caching off for themselves, prevents this:
    `pw.metadata.disable_cache` reached every calculation of a work chain.
  - An identical submission without that switch still reuses the failure. Whether that is enough for D39 to stand is
    the owner's decision.
- **D33** (no durable-execution layer) is to be revisited "if ... users lose work to crashes that a durable engine
  would have saved". A crash inside `submit()` left a process that never started in 17 of 45 trials on macOS and 15
  of 45 in Linux. Of these, 13 and 11 had a checkpoint and ran when revived; 4 and 4 had none and could only end
  excepted (item 4). No computed result was lost. This run tested no durable engine. Whether D33's condition is met
  is the owner's decision.
- **M9's interim route and goldilocks-dft dependency 2** (plan text, not a spec decision): the plan's fallback for a
  late dependency 2 is "the plugin's own parser on goldilocks-core's native input", with "no translation logic of
  ours" (M9), which follows owner's decision 5 ("put the translation layer into dft").
  - S3 finds that fallback covers pw.x inputs without a Hubbard U or a band path.
  - It does not cover task 1's phonons (ph.x, q2r.x, matdyn.x), the DOS step (dos.x), the bands step, or any +U
    calculation.
  - Carrying those before dependency 2 arrives would need a translation of ours, which M9's text and owner's decision
    5 rule out. Claude's reading: M9's phonon and +U parts wait on dependency 2 unless the owner decides otherwise in a
    new record.

## What this means for M5, M8 and M9

Claude's reading of the results. Where one touches a decision, the owner decides in the milestone's PR.

- **M8's key** goes in `metadata.label` of the work chain only, never in `pw.metadata`. The lookup should filter on
  the work chain's process type, so that a child that carries a label is never taken for the job.
- **M8's submit node** can decide as `submit_node` does:

  | it finds | it does |
  |---|---|
  | nothing | submits |
  | two or more processes | needs check |
  | one, running, waiting or ended | takes it over |
  | one that has not started, whose task the broker holds | takes it over: it is queued |
  | one that has not started, with no task, after a short wait | needs check |

  - The broker's queue must be read without changing it: by reading its files (an undocumented layout), or with the
    daemon stopped. Never with `get_process_tasks()` while the daemon runs (item 5).
- **A confirmed submission** (`no_reply=False`, wait for the broker's acknowledgement) closes the gap between
  `submit()` returning and the broker holding the task, by construction. It needs `submit()`'s steps re-done around
  aiida-core's `instantiate_process`, which is not a documented interface. S3 saw no loss without it (item 6).
- **The "needs check" card** can tell the two kinds apart: with a checkpoint the process can be continued (item 4);
  without one it cannot, and only a new submission would compute the step. Which the card offers is the owner's
  decision under D17.3.
- **M9's round-trip test** can take item 7's comparison as it is: every value of core's input, the four plumbing
  keys, and the work chain's `max_seconds`.
- **Wall time is split two ways.**
  - Core writes each pw.x step's `max_seconds` as its share of 95 % of one Slurm job's wall time: si_band's two steps
    have 35,249 s and 539,310 s of the `scarf` profile's 168 h. Its submit script runs every step in that one job.
  - AiiDA runs each step as its own job, whose `max_wallclock_seconds` M5 sets from goldilocks-dft's estimate,
    clamped to the computer's limits.
  - If the two disagree, pw.x does not stop cleanly before the scheduler ends it. For the phonon tasks, core writes
    no `max_seconds` and relies on its job timer creating `pwscf.EXIT`, which AiiDA does not run (and AiiDA's prefix
    is `aiida`).
  - So the per-step wall time is something goldilocks-dft and the Workbench must agree on: an item for the
    dependency list that feeds D18's record.
- **D39's pitfall for retries** is real and has a switch. A retry with the same physics inputs gets the old failure
  back from the cache unless it sets `pw.metadata.disable_cache`: an identical work chain replayed its failures, and
  a PwCalculation asking only for more wall time got its failure back (item 9). Asking for more processes changed the
  hash. Memory is left out of the hash too, by aiida-core's code; S3 did not test it.
- **M9's handlers**: `handler_overrides` per the owner's reading of D9.7 (item 8).

## Limits

- **The jobs were stand-ins,** except in the caching experiment in Linux: 10 cases, of which 8 ran pw.x and 2 came
  from the cache. That pw.x is Quantum ESPRESSO 6.7, Debian's package, older than what goldilocks-core writes for
  (its HUBBARD card needs 7.1 or later), so fe_u was never run.
- **One machine.** The Linux runs are a container on the same Mac, not a Linux host or an HPC login node.
- **The kill points are aiida-core's own steps,** reached by self-SIGKILL, plus 20 kills at random times per system.
  A power cut, which can also lose SQLite's last transaction, was not tested.
- **The broker's file layout** that the submit node reads is not a documented interface (item 5).
- **The inputs are goldilocks-core 0.3.3's,** not goldilocks-dft's plugin-shaped tables (dependency 2): 11 cases on
  three structures.
- **Single runs.** Each kill point has 5 trials per system; each caching case is one run.

## Reproducing

```
uv run python spikes/S3/s3_core.py
caffeinate -i uv run python spikes/S3/s3_experiments.py --out ~/.cache/goldilocks-spikes/s3/results/macos.jsonl
bash spikes/S3/run_container.sh
uv run python spikes/S3/s3_report.py ~/.cache/goldilocks-spikes/s3/results/macos.jsonl <linux results>
```
