# S4: interrupts and resume through our server

Spike S4 (workbench plan, Phase 1, "S4 interrupts and resume through our server"; it gates M7 and M8).

- Run on 2026-11-28 by Claude, on the owner's Mac. No model, no network and no AiiDA: the model is a script
  (`spikes/S4/s4_model.py`), and the executor's jobs are pauses that the driver answers.
- Scripts: `spikes/S4/s4_app.py`, `s4_graphs.py`, `s4_experiments.py`, `s4_facts.py`; the runs used them at
  `01f4c8d`, the commit before the one that adds this file. Tables: `spikes/S4/s4_report.py`. The raw JSON lines are
  not committed.
- Each figure below comes from one run of every experiment with that code: 155 records (140 trials, 7 library facts,
  7 end-of-experiment records, 1 environment record). Where a figure comes from a later check, the item says so.
- Earlier runs, made while the harness was being fixed, agree with these. One fix changed what a figure read: the
  scripted model first read the system prompt with `str()` of its content blocks, which hid the skills list from its
  log; it now reads the message's text (item 7).

**How Claude read the plan's words.**
- "A subgraph run from a separate executor thread": the executor's graph runs on a LangGraph thread of its own
  (`run-` and a uuid5 of the conversation and the tool call, D34.2). It is driven from an OS thread of its own, not
  from the server's event loop.
- "A real OS restart (SIGKILL, new process, AsyncSqliteSaver)": the server's process is killed with SIGKILL while
  paused, and a new process opens the same SQLite file. The machine is not restarted.

**Isolation.** Each experiment ran its own server on 127.0.0.1, with its own SQLite file, skills folder and effects
file in a fresh folder under `~/.cache/goldilocks-spikes/s4/`, deleted afterwards. After each experiment no server
process of its run was alive (7 of 7 experiments).

## Environment

| | |
|---|---|
| System | macOS 27.2.1, arm64 (Apple M5 Pro, 48 GB) |
| Python | 3.12.13; SQLite 3.50.4 |
| Libraries | deepagents 0.7.42, langgraph 1.2.24, langgraph-checkpoint 4.3.2, langgraph-checkpoint-sqlite 3.1.3 (added by this PR to the dev group, for spikes only), langchain 1.5.2, langchain-core 1.8.5, fastapi 0.165.0, uvicorn 0.54.0, aiosqlite 0.22.1, httpx 0.27.2 |
| Server | FastAPI with its own `EventSourceResponse` (`fastapi.sse`), under uvicorn; one AsyncSqliteSaver on the server's event loop |
| Agent | `create_deep_agent` with the scripted model; a FilesystemBackend (virtual mode) rooted in the run's folder; skills from `/skills/`; two tools: `choose_structure`, which calls `interrupt()` with `response_schema` set to a Pydantic model, and `start_run`, which takes a typed plan |
| Executor | one graph per run: `Send` to a `step` node for each of three candidates (x, y, z); the node invokes the step subgraph (submit, then a node that pauses with `interrupt()`, then check); `finish` after all three |

## Answers

1. **A tool's `interrupt()` in the Deep Agents loop surfaces as a card on our SSE stream and resumes with
   `Command(resume=...)`: 20 of 20.**
   - The turn's stream ended with a `card` frame (pause ID, kind, payload, and the answer's JSON Schema) and `end`
     with status "paused". The answer, `Command(resume={pause ID: value})`, streamed the rest of the turn, which
     ended "chose mp-2".
   - The card came 0.01 s (median) and 0.03 s (max) after the turn started; the answered turn ended within 0.01 s.
   - Each conversation ended with no pause pending and one result of the tool (20 of 20).
   - Deep Agents ran the synchronous tool on a worker thread of the event loop's default executor (`asyncio_0`), and
     `interrupt()` works there. The tool's body ran twice per trial: once up to the pause, once on resume. This and
     the thread names in item 3 come from a one-trial run with `--keep`, made after the run above with the same code.

2. **After SIGKILL and a new process, the same: 20 of 20.**
   - At start-up the new process read every thread from the checkpointer and put a catch-up card in the
     conversation's outbox: 20 of 20. The card carried the same pause ID as before the kill: 20 of 20.
   - The IDs are the same in every process because LangGraph derives them from the checkpoint namespace and the
     number of answers the task already has (`langgraph/types.py`, `_interrupt_id`).
   - From the SIGKILL to the new server answering `/health`: 0.49 s (median), 0.54 s (max).

3. **The same inside a subgraph run from a separate executor thread: 20 of 20 with all three pauses answered at
   once, 20 of 20 answered one at a time, and 20 of 20 across a restart.**
   - `start_run` returned the run's thread ID at once. The turn ended "finished", and a second turn in the same
     conversation, while the run was paused, finished too (60 of 60).
   - The run's three pauses, each inside the step subgraph inside its fan-out task, came as one card on the
     conversation's events stream. The first card of each run was raised from the executor's OS thread, not the
     event loop's (60 of 60). It came 0.02 s to 0.03 s (median) after the plan's turn started.
   - The executor drove the graph with LangGraph's synchronous API. The AsyncSqliteSaver hands each synchronous call
     to the server's event loop (`run_coroutine_threadsafe`). LangGraph's synchronous engine ran the three fan-out
     tasks, and so the subgraph's nodes, on a thread pool of its own; `finish` ran on the executor's thread.
   - Answers given as a map of pause IDs reached the right candidate: z's "failed" made z's check fail and x's and
     y's pass, in 60 of 60 runs.
   - Answering one pause resumed that candidate only, and the other pauses kept their IDs: 20 of 20 one at a time.
     Across a restart, the catch-up card listed y's and z's pauses with the IDs they had before the kill: 20 of 20.
   - What each node ran, counted from the effects file:

     | run | submit | wait (the pausing node) | check | finish | trials |
     |---|---|---|---|---|---|
     | answered at once | x 1, y 1, z 1 | x 2, y 2, z 2 | x 1, y 1, z 1 | 1 | 20 |
     | one at a time | x 1, y 1, z 1 | x 2, y 3, z 4 | x 1, y 1, z 1 | 1 | 20 |
     | across a restart (x before it, y and z after) | x 1, y 1, z 1 | x 2, y 3, z 3 | x 1, y 1, z 1 | 1 | 20 |

   - So no submission ran twice: 180 of 180 ran once, also across the 20 restarts.
   - **Every resume of a run runs again the pausing node of each candidate still paused, up to `interrupt()`.**
     Answered one at a time, z's ran 4 times: once at first, then on x's, y's and its own resume.

4. **Wrong answers (20 of 20 trials of the answers experiment).**
   - With a Pydantic `response_schema`, an answer that fails the schema raises `ValidationError` inside the tool.
     The agent's tool node passes it out rather than returning it to the model as a tool error; nothing is saved,
     and the pause stays with its ID. Our server sent an `invalid_answer` frame with the errors and the card again;
     the valid answer then finished the turn.
   - Our server refused a pause ID that was not pending, and one already answered, before anything ran (20 of 20
     each). LangGraph does not refuse them by itself (item 5).
   - The run's answer endpoint refused an unknown pause ID with 409 (60 of 60 in the three executor experiments).

5. **What LangGraph does by itself** (`s4_facts.py`, run once each; `test_s4.py` asserts them):
   - A pause ID that is not pending: no error. The paused tool ran again (1 more run of its body) and paused again,
     with the same pause ID.
   - A plain value, with one pause pending, resumes it. With three pending it raises `RuntimeError` ("When there are
     multiple pending interrupts, you must specify the interrupt id when resuming."), and all three stay pending.
   - A typed answer that fails its schema raises `ValidationError`; the same pause stays pending, and the card
     carries the JSON Schema.
   - A synchronous call to the saver from its own loop's thread raises `InvalidStateError`; from another OS thread
     it works.
   - Two event loops on one saver: 200 concurrent reads from the server's loop and 200 from a second loop in another
     thread. 200 of the 400 failed with `RuntimeError` ("... asyncio.locks.Lock ... is bound to a different event
     loop").
   - The saver's default serializer is `JsonPlusSerializer` with `pickle_fallback` off.

6. **How Deep Agents reads a skills directory** (deepagents 0.7.42, `deepagents/middleware/skills.py`; docstrings
   checked by `s4_facts.py`):
   - Each source is a folder in the backend; with a FilesystemBackend, it is relative to the backend's root. Every
     subfolder that holds a `SKILL.md` is a skill. Its YAML front matter gives the name and the description. Later
     sources override earlier ones for a skill of the same name.
   - SkillsMiddleware loads the skills in `before_agent`, only when the thread's state has no `skills_metadata` or
     has it set to `None`, and keeps them in that state: "Skills are loaded once per thread and cached in state."
   - The system prompt lists each skill's name, description and path. The model reads a skill's body with
     `read_file` when it needs it.

7. **Whether skill state survives a resume: the list does, the bodies do not.** In each of 20 trials (20 of 20
   resumed): a turn paused; on disk, alpha's description and body went from version 1 to version 2, beta was deleted
   and gamma added; SIGKILL; a new process; the answer. The model then read alpha's and beta's `SKILL.md`.

   | point in the trial | what the model was shown or read | trials |
   |---|---|---|
   | first model call, before the pause | alpha v1, beta v1 | 20 |
   | first model call after the resume, in the new process | alpha v1, beta v1 | 20 |
   | alpha's `SKILL.md`, read after the resume | version 2 | 20 |
   | beta's `SKILL.md`, read after the resume | an error (file not found) | 20 |
   | a later turn on the same thread | alpha v1, beta v1 | 20 |
   | a later turn that sets `skills_metadata` to `None` | alpha v2, gamma v1 | 20 |
   | a new thread | alpha v2, gamma v1 | 20 |

   - The list survives resumes and restarts because it is in the checkpoint. The bodies are read from disk when
     opened.
   - So after a change on disk, the model was shown one version's description and given another version's body, and
     it was offered a skill whose file was gone (20 of 20).

8. **HarnessProfile is public, and beta.** `deepagents` exports it (`__all__`); it is defined in
   `deepagents.profiles.harness.harness_profiles`. The module's and the class's docstrings both say "!!! beta" and
   "`deepagents.profiles` exposes beta APIs that may receive minor changes in future releases".

**The plan's pass**, "20/20 on all resume paths with a scripted fake model", is met: 20 of 20 on each of the six
resume paths (tool, tool after a restart, run answered at once, one at a time, across a restart, and the skills trial
across a restart), and on the answers experiment.

## Decisions this touches

Checked against the workbench spec and plan; the decisions are the owner's to revisit.

- **D3** ("Choosing ...: `interrupt()` inside the tool. The user's choice comes back as the tool's result"; "The
  contract between server and frontend stays the same"): S4 ran it in Deep Agents' loop, which builds on the same
  agent loop as `create_agent`. The user's choice was the tool's result in 60 of 60 conversations (tool, tool after
  a restart, answers). S4 did not test `HumanInTheLoopMiddleware` (approve, edit, reject) or `create_agent` itself;
  A1 builds those.
- **D9** is to be revisited "if the long steps cannot wait for long AiiDA jobs and resume cleanly, or keeping both
  LangGraph's state and AiiDA's provenance proves error-prone". As Claude reads it, S4 does not meet the first part:
  paused steps resumed cleanly, also across restarts. But the pauses were answered by the driver, not by AiiDA jobs,
  and within seconds, not days. S4 did not test the second part.
- **D9 with D34, the plan's row "D9 'registered as CompiledSubAgent', read with D34"** ("No CompiledSubAgent in the
  first version unless S4 shows a need"): S4 shows no such need. The executor ran as a graph of its own on a thread
  of its own, started by a tool, and its pauses reached the user through our server.
- **D17.1** ("A subgraph submits an AiiDA job in one node and pauses with `interrupt()` in the next, because LangGraph
  runs a node again from its start when it resumes"): it held. Submission ran once per candidate in 180 of 180,
  while the pausing node ran again on every resume of the run, also for candidates other than the one answered
  (item 3). As Claude reads it, nothing before `interrupt()` in a pausing node may have an effect that must not
  repeat.
- **D17.2** ("It then resumes the subgraph with `Command(resume=...)`, passing the job's outcome"): it works one
  candidate at a time with the pause's ID. A run with several pauses pending refuses a resume without IDs (item 5).
- **D17.3** and **D33.1** (catching up at start-up): S4's server found every pending pause from the checkpointer
  alone: 60 of 60 restarts. It found the threads by reading every checkpoint, which grows with history. How M8 finds
  them is M8's.
- **D31** (receipts list each pending pause "with its ID, its kind and its content"; answers "whose IDs do not match
  the pending pauses" are refused): pause IDs stayed the same across processes (60 of 60 restarts), so a receipt's
  IDs stay valid after a restart. LangGraph does not refuse an ID that is not pending (item 5), so D31.3's refusal
  is code of ours, as in S4's server.
- **D33** is to be revisited "if recovering agent turns from checkpoints alone proves hard to get right". S4
  recovered paused turns and runs from checkpoints after SIGKILL in 60 of 60. It killed only while paused, never
  inside a node, a model call or a checkpoint write; that is M8's crash test (D33.3). As Claude reads it, S4 does
  not meet the condition, and it did not test the harder half.
- **D34.1 to D34.5**: the conversation was free at once (60 of 60); the run's thread ID was derived from the
  conversation and the tool call (a replayed start was not tested); the run's cards came back to the original
  conversation (60 of 60); cards waited in the conversation's outbox until read, but no card arrived during a
  running turn; each card gathered all of the run's pending pauses.
- **D5, with M12's "a flat per-run snapshot with manifest"**: Deep Agents keeps a thread's skill list in its
  checkpoint but reads each body from the backend when it is opened (item 7). As Claude reads it, a snapshot from
  which both come keeps them the same, which M12 plans. D5's revisit condition (the skill format "used by Deep Agents
  and by skill authors drifts apart") is not touched.
- **M2's protocol** (plan text): "a stale pause ID is refused" has to be our own check (item 5). "AsyncSqliteSaver
  with `pickle_fallback=False` on one loop": `pickle_fallback` is already off by default, and a second loop failed
  under load (item 5). For "CatMaster-style strict validator", LangGraph 1.2's `response_schema` checks a typed
  answer and keeps the pause when it fails (item 4); whether M2 uses it is M2's.
- **The plan's "Risks", row 5** ("pinned minor versions; public API only; S4 tests kept as regression tests"):
  `test_s4.py` keeps them, and the check runs it. HarnessProfile is public but beta (item 8). No milestone names it;
  whether "public API only" admits a beta API is the owner's decision.

## What this means for M2, M5, M7, M8 and M12

Claude's reading of the results. Where one touches a decision, the owner decides in the milestone's PR.

- **M2**: FastAPI's own `EventSourceResponse` streams the frames; no other SSE package is needed. A card can carry
  LangGraph's interrupt ID as its pause ID, which stays the same across restarts, and the interrupt's JSON Schema
  for the answer. The server checks that a pause ID is pending before it resumes anything.
- **M5**: LangGraph's synchronous engine runs a run's parallel tasks on its own thread pool (item 3). A node that
  needs AiiDA hands the call to the owner thread, as M5 plans; it does not run AiiDA code on the thread it is given.
- **M7**: each run is driven from an OS thread with the graph's synchronous API on the shared saver. No code on the
  event loop's thread calls that synchronous API: an `async` tool that did would raise `InvalidStateError` (item 5).
  A run with several pauses is resumed only with a map of pause IDs.
- **M8**: the watcher resumes one candidate at a time with its pause ID. The pausing node does nothing before
  `interrupt()` that cannot repeat, since every resume of the run runs it again for every candidate still paused.
- **M12**: the snapshot is a copy of the skill files, and both the list and the bodies are read from it.

## Limits

- The model is a script, so no model behaviour is measured; S1 measured qwen3.8.
- The pauses were answered by the driver within seconds, not by AiiDA jobs over hours or days.
- Every SIGKILL came while paused. None came inside a node, a model call or a checkpoint write (M8's crash test).
- One server ran the trials one after another: no concurrent conversations or runs, and no card arriving during a
  running turn (D34.4).
- macOS only. The check runs `test_s4.py`, with one SIGKILL restart of each kind through the server, on Linux and
  macOS in CI.
- `start_run` took the plan document, as D34.1's text has it ("a typed tool whose argument is the approved plan
  document itself"). The plan's row "`start_run`'s argument" resolves it as a plan ID whose document code loads and
  checks by hash. S4 tests neither.
- Deep Agents' `interrupt_on` and LangChain's `HumanInTheLoopMiddleware` were not tested.
- The machine was not restarted; only the server's process was killed.

## Reproducing

```
caffeinate -i uv run python spikes/S4/s4_experiments.py
uv run python spikes/S4/s4_report.py ~/.cache/goldilocks-spikes/s4/results/darwin.jsonl
```
