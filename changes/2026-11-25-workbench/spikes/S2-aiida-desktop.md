# S2: AiiDA on the desktop

Spike S2 (workbench plan, Phase 1, "S2 AiiDA on the desktop"; it gates M5 and M8).

- Run on 2026-11-27 by Claude, on the owner's Mac and in a Linux container on it. The laptop-sleep test was run by
  the owner on 2026-11-28 on the same Mac (owner's answer, 2026-11-27).
- Scripts: `spikes/S2/s2_experiments.py`, `s2_inside.py`, `s2_app.py`, `s2_sleep.py`, at the commit that adds
  this file. Tables: `spikes/S2/s2_report.py`. The raw JSON lines are not committed.
- Each figure below comes from one run of every experiment per system with the final code: 224 records on macOS,
  and the same set in Linux.
- Earlier runs, made while the harness was being fixed, agree with these. Their one difference is reported as a
  finding (item 10).

**Isolation.** Every experiment made its own profile ("s2") in a fresh folder under `~/.cache/goldilocks-spikes/s2/`,
with `AIIDA_PATH` set before AiiDA was imported.
- After each experiment no daemon or broker of its run was alive (10 of 10 experiments on each system).
- The names and modification times under the owner's `~/.aiida` were the same before and after. Their contents
  were never read.

## Environment

| | macOS | Linux |
|---|---|---|
| System | macOS 27.2.1, arm64 (Apple M5 Pro, 48 GB) | Debian (python:3.12-slim), aarch64, Docker 29.8.0 on the same Mac |
| Python | 3.12.13 | 3.12.16 |
| AiiDA | aiida-core 2.9.4, plumpy 0.26.1, kiwipy 0.9.0, aiida-quantumespresso 5.1.0 | the same, from `uv.lock` |
| Profile | `verdi presto --use-zeromq`: `core.sqlite_dos` storage, the `core.zeromq` broker, presto's `localhost` (`core.local`, `core.direct`) | the same |
| Jobs | `core.arithmetic.add` with `/bin/bash` as the code (`pw.x` is not installed), `metadata.options.sleep` for long jobs, and a work chain that raises | the same |

## Answers

1. **A profile with SQLite and the ZeroMQ broker sets up without any service,** on both systems. `verdi status`
   reports the storage open and the daemon stopped. The broker's folder appears only when the
   daemon starts.
2. **The daemon can be driven from Python** (`get_daemon_client()`):
   - start, 0.69 s;
   - the broker ready 0.61 s later (0.41 s in Linux), because circus starts it just after the daemon returns;
   - 1 to 2 workers and back;
   - a restart in 0.13 s, during which the broker kept its process;
   - stop, 1.12 s; the broker stops with the daemon.

   All steps succeeded on both systems.
3. **Wakes from a FastAPI process: the plan's pass holds, but only if the app registers as an RPC subscriber.**
   - The app ran under uvicorn with one AiiDA owner thread that runs the runner loop.
   - It submitted 20 jobs per round, 3 rounds per mode, and registered `call_on_process_finish` for each job.
   - The poll interval was 30 s, so a broadcast wake (under a second) is told apart from a poll wake.

   | mode | system | jobs woken | broadcasts seen | woken within 5 s | wake delay, median and max |
   |---|---|---|---|---|---|
   | plain (the app only submits) | macOS | 60 of 60 | 0 of 60 | 0 of 60 | 23.19 s, 25.79 s |
   | plain | Linux | 60 of 60 | 0 of 60 | 0 of 60 | 24.05 s, 26.26 s |
   | RPC subscriber registered | macOS | 60 of 60 | 60 of 60 | 60 of 60 | 0.00 s, 0.01 s |
   | RPC subscriber registered | Linux | 60 of 60 | 60 of 60 | 60 of 60 | 0.00 s, 0.15 s |

   - The ZeroMQ broker forwards broadcasts only to clients it knows as task or RPC subscribers
     (`aiida/brokers/zeromq/server.py:433-448`). An app that only submits never receives one, and
     `call_on_process_finish` falls back to polling.
   - Registering a do-nothing RPC subscriber made every round pass: 20 of 20, 3 times, on both systems.
   - All 120 jobs per system ended with exit 0.
4. **Finished, excepted and killed processes all wake the app** (3 of each per mode and system):
   - 9 of 9 per system with the RPC subscriber, by broadcast, within 0.16 s;
   - 9 of 9 per system without it, by polling, 21.7 to 29.9 s later.
5. **When the broker fails:**
   - **Frozen (SIGSTOP) while 10 jobs ended:** the jobs still finished (10 of 10, exit 0). Backup polling woke the
     app for all 10, 5.46 to 6.46 s after each job's last change on macOS (6.29 to 6.38 s in Linux), within the
     10 s poll interval; no broadcast arrived. After SIGCONT, 5 new jobs woke it by broadcast (5 of 5).
   - **Killed:** circus started a new broker in 1.0 s (1.5 s in Linux), with a new socket. Every process that held
     the old socket was then stranded:

     | step | jobs finished so far | the broker's on-disk queue |
     |---|---|---|
     | 5 submitted from the app that held the old socket | 0 of 5 | empty: they never reached a broker |
     | 5 submitted from a restarted app (new socket) | 0 of 10 | 5 pending: the workers held the old socket |
     | `verdi daemon restart` | 5 of 15 | the restart also replaced the broker (a new process). The 5 pending ran; 5 submitted by the same app after the restart were lost |
     | daemon stop and start, and a restarted app | 10 of 20 | the new app's 5 ran |

     The same on both systems. The 10 lost submissions stayed in state `created` with no task anywhere. Nothing
     reported an error.
   - **A worker-only restart kept the broker's process in a clean daemon,** but replaced it after a respawn
     (1 run of each; the cause is not established).
6. **Laptop sleep: everything recovered.** The owner ran `spikes/S2/s2_sleep.py`.
   - The Mac slept 4.3 minutes while 5 jobs of 4 minutes ran. The time asleep is the gap between the wall clock and
     macOS's monotonic clock, which stops during sleep.
   - The app ran in RPC mode with a 10 s poll interval.
   - After waking, the 5 jobs finished with exit 0, and each woke the app by broadcast with no measurable delay
     (5 of 5).
   - The broker kept its process and resumed rewriting its status file, and the daemon's workers were still listed.
   - 3 jobs submitted after waking finished and woke the app by broadcast (3 of 3).
   - No process of the run was left, and `~/.aiida` was unchanged.
7. **Caching** (enabled for `core.arithmetic.add`), the same on both systems:

   | job | exit | from the cache |
   |---|---|---|
   | identical to an earlier job | 0 | yes, from it |
   | same inputs, on a Code whose `prepend_text` names version 2, after version 1 | 0 | no |
   | the version-1 Code again | 0 | yes, from the version-1 job |
   | identical, with `metadata.disable_cache` | 0 | no |
   | a finished job that failed with exit 410 (not invalidating), repeated | 410 | **yes: the failure is reused** |
   | a job whose code writes no output (exit 320, invalidating), repeated | 320 | no |

   - `prepend_text` is part of the Code's hash, so one Code per code version (the plan's resolution of D39) does
     keep versions apart.
   - aiida-quantumespresso's 370 exit codes over 19 calculations, read from the plugin's process specs: every code
     below 400 invalidates the cache, and none at or above (19 of 19 calculations).
     - For `quantumespresso.pw`, 23 codes do not invalidate: 400, 410, 461–468, 481, 500–503, 510, 511, 520,
       521, 531, 541, 542 and 710.
     - So a finished pw.x run that failed with any of these is reused by an identical job.
8. **An observe-only monitor works, if its module has a version.**
   - A monitor that returns None, registered as an entry point, was called 19 times during a 20 s job on macOS
     (20 in Linux). The job ended with exit 0.
   - The monitor input changes the job's hash, so a job with a monitor is not a cache hit for one without.
   - A monitor whose top-level module has no `__version__` makes job creation fail with `KeyError: 'plugin'`, on
     both systems. aiida-core 2.9.4's `CalcJob._setup_version_info` reads a version that its own version helper
     treats as optional.
9. **Threads.**
   - A node loaded in one thread fails in another: `InvalidRequestError: Instance ... is not persistent within this
     Session`, both for reading and for setting an extra.
   - Passing the PK and loading the node in the worker works.
   - A LangGraph `ToolNode` (inside a graph) ran 3 calls of a sync tool in 3 different threads, each loading by PK,
     without error.
   - Under contention, 4 threads writing extras for 30 s while the daemon ran 20 jobs made 7,631 writes on macOS
     (6,659 in Linux) with 0 errors, and all 20 jobs finished.
10. **Linux: the same results, once the image has `ps` and a compiler.**
    - `pycifrw` (from aiida-core's `atomic-tools` extra) has no wheel for Linux arm64 with Python 3.12, so the
      image needs a C compiler to build it.
    - The slim image also lacks `ps`, which AiiDA's `core.direct` scheduler uses to list jobs. In the first Linux
      run, without it:
      - all 147 jobs looked finished at once;
      - their parser failed with exit 320;
      - the 20 s monitor job was never observed;
      - nothing stopped the run.
    - With `procps` installed, every Linux figure above matches macOS.

## Decisions this touches

Checked against the workbench spec and plan; the decisions are the owner's to revisit.

- **D17 (the watcher wakes a paused subgraph)** is to be revisited "if broadcasts are routinely missed, so that the
  fail-safe polling does all the work". Read literally, a watcher that only submits meets that condition: it received
  0 broadcasts in 69 jobs per system (the plain-mode wakes and states), and polling did all the work.
  - With a do-nothing RPC subscriber registered, every broadcast arrived.
  - That registration rests on the broker's forwarding rule as read in its code, not on a documented API.
  - Whether that is enough for D17 to stand is the owner's decision.
- **D17.3 (catching up after a restart).** A restarted app could adopt earlier jobs and be woken for them. But
  submissions lost to a stale broker socket leave nodes in `created` with no task. D17.3 sends a job "whose state is
  unclear" to "needs check"; these are such jobs, and nothing in AiiDA flags them.
- **D17.6 (no monitoring code of our own; AiiDA's may observe):** observe-only monitors work, with the
  `__version__` condition in item 8.
- **D21.3 (SQLite with the built-in ZeroMQ broker; the app manages the daemon)** holds on macOS and Linux, and
  across a 4.3-minute laptop sleep (item 6). D17.3's example of a restart, "after a laptop was closed", needed no
  catch-up here: the daemon, the broker and the app's subscription all survived the sleep.
- **D39 (caching on by default)** is to be revisited "if cached results are reused where users expected a fresh
  run".
  - A finished failure with a code of 400 or more is reused from the cache. For pw.x that is 23 codes.
  - The plan's resolution, that retries after failures turn caching off for themselves, guards this for retries.
  - An identical job submitted fresh would still reuse the failure. Whether that meets D39's condition is the
    owner's decision.
- **D4 (HPC through AiiDA)** is to be revisited if installing or running AiiDA "turns out to block people". Nothing
  here blocks; the Linux image needs the two additions in item 10.
- **D33 (no separate durable-execution layer)** rests on D17's recovery. The silent loss of submissions in item 5
  bears on it: without a check that the broker received each task, a crash-free run can still lose a job.

## What this means for M5, M8 and M10

Claude's reading of the results. Where one touches a decision, the owner decides in the milestone's PR.

- **M5's owner thread is needed, not just tidy.**
  - AiiDA nodes cannot cross threads, and `call_on_process_finish` needs a running runner loop.
  - One thread that loads the profile, runs the loop, and takes every call from a queue worked on both systems.
  - Tools pass PKs or UUIDs, as the plan says; ToolNode's worker threads then work.
- **The watcher (M8) registers as an RPC subscriber,** so broadcasts reach it, and keeps backup polling. A poll
  interval of 10 s caught every job within the interval when broadcasts stopped.
- **The doctor and the watcher (M5, M8) must notice a broker restart:** a changed broker pid or socket path. Then
  they reconnect the app's communicator, and restart the daemon's workers if they are stranded.
  - A submission should be confirmed by the broker, not sent fire-and-forget. The code reading points to
    `continue_process(..., no_reply=False)`; this run did not test it.
  - A node left in `created` with no task goes to "needs check" (D17.3). S3 tests the submission key against this.
- **M5's monitors,** if any are used to observe (D17.6), live in a module with `__version__`; goldilocks-agent's
  package would need to define one.
- **D39's pitfall is concrete.** A retry that must not reuse a failure sets `metadata.disable_cache`; this run
  showed it misses the cache. A repeated identical job reuses any finished failure of 400 or more; the card can say
  "reused from" (the plan's resolution).
- **M10's image** needs `procps` (without it, AiiDA's local scheduler reports every job as finished and the results
  are wrong) and a compiler in its build stage, or a prebuilt `pycifrw` wheel. The doctor could check that `ps`
  exists.

## Limits

- **The jobs were stand-ins** (`core.arithmetic.add`), not pw.x. The quantumespresso facts come from the plugin's
  specs, not from runs.
- **One machine.** The Linux runs are a container on the same Mac (Docker's arm64 VM), not a Linux host or an HPC
  login node.
- **The RPC-subscriber registration is undocumented.** It relies on the broker's code; a later aiida-core may change
  how broadcasts are routed.
- **Some figures are single runs:** the broker restart sequence is one run per system, and so is each caching case.
  The wake figures are 3 rounds of 20 jobs per mode and system.
- **Laptop sleep is one run** of 4.3 minutes. A night's sleep, and a change of network during sleep, were not
  tested.

## Reproducing

```
caffeinate -i uv run python spikes/S2/s2_experiments.py --out ~/.cache/goldilocks-spikes/s2/results/macos.jsonl
bash spikes/S2/run_container.sh
uv run python spikes/S2/s2_sleep.py
uv run python spikes/S2/s2_report.py ~/.cache/goldilocks-spikes/s2/results/macos.jsonl <linux results>
```
