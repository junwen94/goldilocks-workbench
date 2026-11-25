# Spec: Goldilocks Workbench in three forms, with the agent on Deep Agents

From: `intent.md` (same folder). Status: ready for the owner's review (2026-11-25); accepted
when its PR merges. Decisions D1 to D22 were made one at a time with the owner on 2026-11-25.

Only large changes (D8) have a spec. Each decision uses the five parts below. Where the owner gave no
reason, say so; do not supply one.

## D1. All three forms live in this repository, with one shared part (2026-11-25)

**Decision.** goldilocks-chat, goldilocks-agent and goldilocks-Ada all live in this repository,
`ddmms/goldilocks-workbench`. The repository has one shared part and one entry point per form. The
shared part holds what the forms have in common, such as the tools, the goldilocks-core client and
the frontend components. Each form adds its own dependencies, build and deployment. The plan decides
which code goes where and the folder layout.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). Claude's reasons:
- The forms share most of their code today. On `stfc/goldilocks-agent` main (`ea757c7`), the web
  and local editions run one graph, one set of tools and one frontend (`app/`). They differ only in
  a profile (`agent_profile.py`) and in their Docker images.
- A change that touches several forms is one PR, with no version pins between repositories.
- The process files exist once: `AGENTS.md`, `REVIEW.md`, `check` and CI.
- The owner is the only maintainer (v4-process D10). Keeping several repositories in step was the
  owner's stated worry (ddmms/goldilocks, `changes/2026-11-25-reposition/intent.md`).
- It matches the intent: one Goldilocks Workbench, in three forms.

**Rejected.**
- *Three repositories plus a shared library* (goldilocks-chat, goldilocks-agent, goldilocks-ada).
  Each form could release on its own. But a change across forms would need several PRs and version
  pins, and the process files would exist four times.
- *Two repositories*: one for chat, and one for agent with Ada, both of which use Deep Agents and
  reach HPC. This split follows the owner's line between light use and heavy use. But the two still
  share tools and frontend, so the problem of keeping them in step remains, only smaller.

**Known costs.**
- The forms have different dependencies; only the agent uses Deep Agents. So they need separate
  dependency groups or packages.
- They have three deployment targets: the shared web instance, a local install and an Ada
  Workspace. Each needs its own build.
- CI runs for every form.

**Revisit if** one form needs a release schedule or access rules that the others cannot share, or if
changes made for one form break or block another more than once in a month.

## D2. goldilocks-Ada is a light form of its own: chat that can reach SCARF (2026-11-25)

**Decision.** goldilocks-Ada is its own light form, close to goldilocks-chat: it is chat that can reach
SCARF. It adds tools to submit a job to SCARF, poll it and fetch its results. It has no Deep Agents
planning loop, and it is not goldilocks-agent installed in an Ada Workspace. How it is deployed is not
decided: the owner says it is a network deployment, with the solution to be decided. Ada is not built
now (owner, 2026-11-25).

**Reason.** Owner's call (2026-11-25). The owner, after choosing:

> "Ada is for STFC's internal users and needs to connect to SCARF. But it is also a network
> deployment with limited resources, so it is more like a goldilocks chat that can connect to SCARF."

(Translated from Chinese by Claude.)

**Rejected.** *goldilocks-Ada as goldilocks-agent installed in an Ada Workspace*, with the HPC
connection as a replaceable executor: AiiDA for the local agent, SSH and Slurm for Ada. Claude
recommended it. The agent would have one codebase, Ada users could run long tasks on SCARF, and Ada's
framework would follow (Deep Agents). It lost because Ada is a network deployment with limited
resources, which suits a light form.

**Revisit if** Ada users need long tasks: work on SCARF that spans several jobs and needs planning, or
checking results between jobs.

**Overturns**, in part, section 20.2 of the agent design doc (`stfc/goldilocks-agent`, branch
`docs/ada-version`, `1b21109`, not on main). That section is the agent session's 2026-11-24 proposal,
recorded at the owner's request. It treated the Ada edition as the local edition installed in each
user's own Ada Workspace, with a different way of executing jobs. Ada is now a light form, and where
it runs is open.

## D3. chat and Ada share one light agent built with LangChain's `create_agent` (2026-11-25)

**Decision.** goldilocks-chat and goldilocks-Ada share one light agent, built with LangChain's
`create_agent` on the LangGraph runtime. The two differ in their tools and prompt, as the web and
local profiles do today. Behaviour that the hand-built graph implements in its own code moves to the
following:
- **Limits on each turn:** `ToolCallLimitMiddleware` and `ModelCallLimitMiddleware`.
- **Confirming and editing a tool call:** `HumanInTheLoopMiddleware` (approve, edit, reject).
- **Choosing**, for example a structure from search results: `interrupt()` inside the tool. The
  user's choice comes back as the tool's result.
- **State across pauses:** a checkpointer.

The contract between server and frontend stays the same: the server pauses, the frontend shows a
card, and the user's answer resumes the run.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). The owner chose it after Claude had
also offered to keep the hand-built graph for now. Claude's reasons:
- The chat's graph is the standard loop that `create_agent` provides: an `llm` node and a `tool`
  node joined by a conditional edge.
- The chat's interactive steps (choosing, confirming, editing) are covered by built-in middleware and
  by `interrupt()` in tools. This is from the LangChain and LangGraph docs, read 2026-11-25.
- Deep Agents builds on the same agent loop and middleware. So all three forms share tools,
  middleware and runtime (D1's shared part), and there is less loop code of our own to maintain.

**Rejected.**
- *Keep the hand-built LangGraph graph* for chat, and use it for Ada too. It is proven in production
  and carries fixes for real edge cases. But the repository would have two styles of agent, and we
  would keep maintaining our own loop code.
- *Keep the hand-built graph for now and migrate after the agent is built.* Claude called this the
  safer path, since the agent is the priority. The owner chose to have the forms share one approach
  from the start.
- *Deep Agents for all three forms.* Planning, files and subagents are for long tasks. They would
  also give the small models on the shared instance more tools and prompt to handle (an untested
  guess).

**Known costs.**
- The chat's graph (`graph.py`, 581 lines) is rewritten. Most of those lines are domain logic, such
  as the prompt, confirmation labels and fixes, which moves into middleware and tools. So the code
  saved is mainly the loop itself.
- Two fixes must be checked again under middleware: the one for a user who types while a card is
  still unanswered, and the parallel tool-call fix (stfc/goldilocks-agent#149).
- The chat's end-to-end tests (`app/e2e`) must pass.

**Revisit if** a behaviour the chat needs cannot be expressed in middleware without working around
`create_agent`, or LangChain's model layer blocks something the models need that calling them
directly allowed.

**Overturns** section 17 of the agent design doc (`stfc/goldilocks-agent` main,
`docs/goldilocks-agent-design.md`, decided 2026-09-10): "use LangGraph, not LangChain's model
abstraction". `create_agent` calls models through LangChain's model layer. The intent's choice of Deep
Agents for the agent already did the same for the agent form; D3 extends it to chat and Ada.

## D4. goldilocks-agent reaches HPC through AiiDA (2026-11-25)

**Decision.** goldilocks-agent submits, monitors and retrieves its HPC calculations through AiiDA.

**Reason.** Owner's call (2026-11-25); no reason recorded.

**Rejected.** *Direct SSH and Slurm*, the approach first designed for Ada (agent design doc, section
20.3, branch `docs/ada-version`). Claude raised it as an option on 2026-11-25. The owner did not
choose it; no reason recorded.

**Facts** (checked 2026-11-25). In the predecessor, the AiiDA path is not built. The tools package
names AiiDA as one tool group, but has no backend. Section 20 of the agent design doc notes that
AiiDAlab-QE has no backend yet (stfc/goldilocks-agent#84).

**Revisit if** installing or running AiiDA on users' machines turns out to block people from using the
agent.

This continues section 15 of the agent design doc (the local edition reaches HPC through AiiDA). It
overturns nothing.

## D5. goldilocks-agent loads Agent Skills, such as AtomisticSkills (2026-11-25)

**Decision.** goldilocks-agent can load skills in the Agent Skills format (a `SKILL.md` with `name` and
`description`, optionally with scripts and references). AtomisticSkills is one example of a source.
Goldilocks's own skills use the same format.

**Reason.** Owner's call (2026-11-25): the agent should be able to load "AtomisticSkills and various
skills like it". No further reason recorded.

**Facts** (checked 2026-11-25):
- Deep Agents skills follow the Agent Skills specification (agentskills.io). Each skill is a directory
  with a `SKILL.md` and optional supporting files (docs.langchain.com/oss/python/deepagents/skills).
- AtomisticSkills (github.com/learningmatter-mit/AtomisticSkills, MIT licence) holds 130 skills in
  this format, for example MLIP-based bond dissociation energies. 120 of them tell the agent to run
  Python or shell scripts, so they need an environment to execute code in, with packages such as
  MLIPs, ASE and RDKit.

**Rejected.** None was discussed.

**Revisit if** most useful skills cannot run without heavy setup on users' machines, or the skill format
used by Deep Agents and by skill authors drifts apart.

## D6. Tools are extensible: adding a tool does not change the agent (2026-11-25)

**Decision.** The forms take their tools from an extensible set. Adding a tool, or a group of tools,
must not require changing the agent loop or the forms themselves. The starting groups are those of
the predecessor: MLIP, DFT, Find in Databases, Post Analysis and AiiDA. A sixth group, for building
and modifying structures, was added the same day: **Structure Builder** (D15; the owner's working
name was "structure manipulator"). More will be added. How a tool
plugs in is decided separately (see Open).

**Reason.** Owner's call (2026-11-25): the agent must be extensible to connect all kinds of tools.
The earlier tools included MLIP, DFT, Find in Databases, Post Analysis and AiiDA, and more tools will
be connected. No further reason recorded.

**Facts** (checked 2026-11-25):
- In the predecessor, the UI lists six Tools: Find in Databases, DFT Workbench, MLIP Playground,
  Beyond DFT, Post Analysis and AiiDA (agent design doc, section 12). Only three have code
  (`dft_workbench`, `mlip_playground`, `structure_search`). Each is a subpackage that owns both its
  implementation and the tool schema the model sees.
- Deep Agents takes custom functions, APIs and tools from any MCP server
  (docs.langchain.com/oss/python/deepagents/tools). goldilocks-core ships an MCP server
  (`stfc/goldilocks-core` main `2d579df5`, version 0.3.3, `server/mcp.py`, optional extra `mcp`). The
  predecessor's DFT tools call core over HTTP instead (stfc/goldilocks-agent#142).

**Rejected.** None was discussed.

**Revisit if** adding a tool regularly requires changes outside that tool.

## D7. The first target task: an earlier screening study, reproduced with a local small model (2026-11-25)

**Decision.** goldilocks-agent's first target task is a three-round screening study of magnetic
materials. The owner ran it in November 2026 with an advanced LLM in a coding agent, alongside
goldilocks-core. goldilocks-agent should reach similar results with a local small model. It does so
by writing the method down as explicit workflows, loops and skills, so that it does not depend on
what the model can work out for itself. The model makes only the open decisions.

**Reason.** Owner's call (2026-11-25):

> "I want the project we did in goldilocks-core to be implemented in goldilocks-agent. That one
> used an advanced LLM. I hope that by defining specific workflows, loops and skills,
> goldilocks-agent can achieve a similar effect even with a local small model."

(Translated from Chinese by Claude.)

**What the study involved** (from the records of the earlier sessions). Its steps:
1. Generate candidates from databases or prototype structures.
2. Validate the MLIP against reference DFT results before using it.
3. Enumerate magnetic orderings.
4. Rank them with an MLIP.
5. Classify them by symmetry.
6. Check thermodynamic stability against an MLIP convex hull.
7. Check novelty against databases and the literature.
8. Narrow the candidates in a funnel.
9. Write DFT inputs for the shortlist, with figures and a report.

Its pitfalls are the places a small model is most likely to go wrong:
- The MLIP failed for one class of compounds, which then needed a different route.
- The symmetry classifier had a bug.
- Names were inconsistent across folders, figures and tables.
- Intermediate data was lost from a temporary directory.
- At several branch points the owner had to choose.

The research is unpublished, so its details stay out of this public repository (v4-process D12).

**How this maps onto the agent** (Claude, following MatOS's design):
- **Deterministic steps** become workflow steps, run by code rather than the model.
- **Known pitfalls** become checks.
- **The owner's choices** become steps that pause for the user (D3's mechanism).
- **Steps repeated per candidate** become loops.
- **The method** becomes skills (D5).

**Rejected.** *Rely on a stronger model*, as the earlier study did. The owner wants local small models
to be enough.

**Revisit if** a local small model cannot reach results close to the earlier study's, even with the
method written down. Then some roles need a larger model, or the agent needs a cloud model option.

## D8. The first version runs five tasks end to end (2026-11-25)

**Decision.** The first version of goldilocks-agent runs these five tasks end to end:
1. **One material, start to finish.** Start from a structure. Take goldilocks-core's recommended
   parameters, run convergence tests and a relaxation, and compute band structure, DOS and phonons on
   HPC through AiiDA. Check the results and write a report.
2. **A screening funnel.** Take candidates from databases, pre-screen them with an MLIP (for example
   with AtomisticSkills, D5), run DFT through AiiDA on the top few, then rank them and report.
3. **MLIP validation.** Compare an MLIP with DFT over a set of structures and find the local atomic
   environments where it errs.
4. **Method development support**, like the two new methods that MatOS supported. D16 defines it.
5. **The target task of D7.**

**Reason.** Owner's call (2026-11-25); no reason recorded. Claude drew tasks 1 to 4 from MatOS's
research cases and Goldilocks's strengths.

**Rejected.** *Leave method development support (task 4) for later*, which Claude suggested because it
is the hardest and the least defined. The owner kept it in the first version.

**Revisit if** the first version cannot be finished with all five tasks. Then move task 4 later first.

## D9. Workflows are LangGraph subgraphs under the Deep Agents agent (2026-11-25)

**Decision.** The workflows, loops and checks of D7 and D8 are written as LangGraph subgraphs. The
Deep Agents agent delegates a task to its subgraph, registered as a `CompiledSubAgent`. Inside a
subgraph:
- deterministic steps and checks are nodes;
- loops are conditional edges, or a fan-out over candidates;
- steps that need the user pause with `interrupt()` (D3's mechanism);
- HPC jobs go through AiiDA (D4).

**Reason.** Owner's call (2026-11-25), made before Claude had set out the options; no reason
recorded. Facts (docs.langchain.com, read 2026-11-25): Deep Agents accepts a custom compiled LangGraph
graph as a subagent (`CompiledSubAgent`).

**Rejected.** These were not discussed:
- *AiiDA WorkChains as the workflow layer.*
- *A workflow runtime of our own, as in MatOS.*

**Revisit if** the subgraphs cannot wait for long AiiDA jobs and resume cleanly, or if keeping both
LangGraph's state and AiiDA's provenance proves error-prone (see Concerns).

## D10. A tool is a module in this repository, with an optional GUI (2026-11-25)

**Decision.** Each tool group is a module in this repository. A module has up to three parts:
- the tools the agent calls (Python);
- an optional GUI panel in the app (React);
- an optional backend.

A registry lists the modules. Adding a tool means adding a module and its registry entry, with no
change to the agent loop or the forms (D6). A module may use outside packages for the science it
does, such as goldilocks-core, goldilocks-ml, ASE or pymatgen. The module itself, with its tool
definitions and GUI, lives here.

**Reason.** Owner's call (2026-11-25):

> "I want a tool, where needed, to have its own GUI inside this app, and that makes it hard to ship
> as a separate dependency."

(Translated from Chinese by Claude.)

**Facts** (checked 2026-11-25, `stfc/goldilocks-agent` main). The predecessor already has one tool
whose GUI is a separate dependency: DFT Workbench. goldilocks-core publishes its Workbench GUI as an
npm package, which the agent's frontend installs from a vendored tarball
(`app/vendor/goldilocks-workbench-0.3.3.tgz`). The agent's server starts core's server on demand and
forwards requests to it. This approach costs three things:
- versions have to be kept in step on both sides (the tarball and `core_pin.json`);
- forwarding routes have to be maintained;
- core's first cold start took more than 20 minutes.

**Rejected.**
- *A separate package with a backend and a GUI package*, as DFT Workbench is today. Each new tool
  would need the frontend rebuilt, and the versions kept in step.
- *A separate service over MCP*, with a GUI through MCP Apps in a sandboxed iframe. Tools could be
  added at run time, including tools from third parties. But the GUI would sit apart from the chat,
  and each tool would be its own process.
- *Tiers*, recommended by Claude: built-in modules for Goldilocks's own tools, the package route kept
  for core's Workbench, and MCP for third-party tools.

**Revisit if** people outside the project want to add tools without a PR to this repository, or a
tool's dependencies cannot live alongside the app's.

## D11. One model layer; qwen3.8 27B is the agent's target model (2026-11-25)

**Decision.**
- All forms reach models through one configurable layer: LangChain chat models, with litellm
  underneath through `langchain-litellm`. Local and cloud models can both be configured, so a user
  with an API key can use a cloud model.
- **goldilocks-agent's target model is qwen3.8 27B.** The workflows (D9) are designed and tested
  against it, and D7's comparison uses it.
- **goldilocks-chat keeps the model the shared instance serves today:** qwen3.8 27B, thinking off,
  through Ollama. This change does not change it.
- **goldilocks-Ada's model** is decided when Ada is built (D2).
- **"Local small model" (D7)** means an open-weight model that runs either on the user's own machine
  or on a server we run, for example a GPU belonging to the group or to STFC (owner, 2026-11-25).

**Reason.** Proposed by Claude, chosen by the owner ("go with what you recommend"). Claude's reasons:
- qwen3.8 27B did best in the project's own test of tool choice (stfc/goldilocks-agent#68).
- It is already served on the shared instance, so chat and agent can share one model.
- It is safer to show D7 working on 27B first, then try smaller models, than to start with a smaller
  model.

**Facts** (checked 2026-11-25):
- The shared instance (`stfc/goldilocks-agent` main, `deploy/stfc-cloud/docker-compose.yml`) serves
  `qwen3.8:27b` through Ollama on the VM's A100, with thinking off and 4 parallel slots.
- In #68 (2026-11-09), 19 tool-choice cases were run 3 times each. qwen3.8 27B made 100% of tool
  decisions correctly, with and without a short system prompt. Ministral 3 scored 94/100% at 14B,
  86/88% at 8B and 94/100% at 3B. Ollama sometimes failed to parse Ministral's native tool-call
  format.
- That test measured the chat's simple tool choices only. Nothing has measured long tasks.

**Rejected.**
- *Ministral 3 14B as the target.* It runs on more machines, but it scored lower, and its tool-call
  format is parsed unreliably by Ollama.
- *Both models as targets*, with 27B as the main one and 14B as a check. It would show how sensitive
  the workflows are to model size, but it doubles the testing.

**Known costs.** qwen3.8 27B at 4-bit needs about 17 GB (Claude's estimate). That means a 24 GB GPU, a
32 GB Mac, or a self-hosted server.

**Revisit if** 27B cannot reach D7's results even with the method written down (then see D7), or if
it reaches them easily (then try a smaller target).

## D12. Every tool has a GUI panel and chat cards; DFT's GUI moves into this repository (2026-11-25)

**Decision.**
1. **Panels and cards.** A tool gets a panel when the user needs to browse, compare or edit many
   things, and a card in the chat for a single result or a confirmation. On that rule, all six tool
   modules have both:

   | Tool | Panel | Card in the chat |
   |---|---|---|
   | Find in Databases | result list with preview, to pick a structure | search summary |
   | DFT | parameter settings | parameter review |
   | MLIP | comparison of predictions | result of one calculation |
   | Structure Builder | 3D view and editing | before and after |
   | Post Analysis | plots | key values |
   | AiiDA | job list, status and provenance, where the user follows the agent's long tasks | job submitted, job finished |

   Which tools each form offers follows the profiles, as today: MLIP and AiiDA only in the agent.
2. **DFT's GUI.** The DFT module's GUI lives in this repository. It no longer mounts goldilocks-core's
   Workbench GUI package.

**Reason.** Part 1: proposed by Claude, chosen by the owner (2026-11-25). Part 2: owner's call; no
reason recorded.

**Rejected.** For part 2: *keep mounting core's Workbench GUI package inside a thin DFT module.* Claude
recommended it. It continues the predecessor's choice of one implementation, but costs the version
coupling, the forwarding routes and the name clash described under D10.

**Revisit if** this repository's DFT GUI and core's own drift apart, or keeping this GUI in step with
core's capabilities costs more than mounting core's GUI would.

**Overturns** the predecessor's decision of 2026-09-24 (`stfc/goldilocks-agent` main,
`src/goldilocks_agent/tools/__init__.py`, and the merge decision in its design doc). That decision
deleted the agent's own DFT Workbench panel and embedded core's published Workbench GUI instead, so
that there would be one implementation and one state.

## D13. Start fresh and carry over chosen parts; the old site runs until chat catches up (2026-11-25)

**Decision.**
1. **Carrying code over.** This repository starts with the new structure (D1, D10). It takes chosen
   parts of `stfc/goldilocks-agent` from a list that the plan writes:
   - tool logic;
   - the fixes for known edge cases, such as a user typing while a card is unanswered, and parallel
     tool calls (stfc/goldilocks-agent#149);
   - the unit and end-to-end tests, as a safety net;
   - the deployment files.

   Each copied part cites the predecessor commit it came from. The predecessor's history stays in
   `stfc/goldilocks-agent`. Its design doc, written in Chinese, is not copied. What this repository
   needs from it is restated in English in this repository's records.
2. **Switching the live site.** workbench.goldilocks.ac.uk keeps running the predecessor's image until
   goldilocks-chat matches it, meaning the same tools with its end-to-end tests passing. Then the
   deployment switches to goldilocks-chat's image. To roll back, pin the previous image, as
   `ops/rollback.md` in `ddmms/goldilocks` describes.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). Claude's reasons:
- D3, D9, D10 and D12 change most of the structure anyway.
- Importing the history would bring the Chinese design doc into this repository's history, against
  the English-only rule (`ddmms/goldilocks` `AGENTS.md`).
- The tests guard against regressions.
- For the switch: it is the simplest path, and its rollback is already written down.

**Facts** (checked 2026-11-25):
- `stfc/goldilocks-agent` main has 253 commits. Its parts are roughly 6,800 lines of backend, 13,000
  lines of frontend (of which `App.tsx` is 10,900), 6,300 lines of tests, 1,400 lines of deployment
  files and 6,100 lines of docs.
- It is licensed BSD-3-Clause, copyright Junwen Yin. Copied code keeps that notice.

**Rejected.**
- *Import the predecessor's history and restructure in place.* Every line would stay traceable, but
  the Chinese design doc would come along, and so would the 10,900-line `App.tsx`.
- *Rewrite from scratch, reading the old code for reference.* It is the cleanest, but it is the most
  work and the most likely to regress.
- *Run goldilocks-chat at a test address alongside the old site before switching.* Real users could
  try it first, but the VM would carry a second deployment.

**Revisit if** fixes that the old code had keep going missing after copying, or goldilocks-chat cannot
catch up with the old site in reasonable time.

## D14. This repository is licensed BSD-3-Clause (2026-11-25)

**Decision.** `ddmms/goldilocks-workbench` is licensed BSD-3-Clause.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). Claude's reasons:
- It matches the other Goldilocks repositories. `stfc/goldilocks-core`, `-ml`, `-data` and `-agent`
  are all BSD-3-Clause (checked 2026-11-25).
- Code copied from the predecessor is already BSD-3-Clause (D13).
- It is compatible with MIT-licensed skill sources such as AtomisticSkills (D5).

**Rejected.** *MIT*, which is shorter, and *Apache-2.0*, which adds a patent grant. Either would make
the Goldilocks repositories inconsistent.

**Revisit if** a dependency or a funder requires a different licence.

## D15. Structure Builder: its name and first operations (2026-11-25)

**Decision.** The structure tool group of D6 is named **Structure Builder**. Its first operations
come from what D8's five tasks need:

| Operation | Needed by |
|---|---|
| Import and export structures (CIF, POSCAR, xyz) | every task |
| Supercells | magnetic orderings, phonons |
| Element substitution, to make new compositions from a prototype | D7, the screening funnel |
| Vacancies and dopants | method development, screening |
| Strain and lattice scaling | convergence tests, MLIP validation |
| Surfaces and slabs, with vacuum | 2D materials (D7 has 2D candidates) |
| Interfaces between two structures | heterostructures; added by the owner after the survey (Masgent has it) |
| Setting magnetic moments, for orderings | D7 |
| Symmetrising and standardising cells | every task |

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). The owner asked for "a structure
manipulator, or a better name"; Claude suggested Structure Builder, which matches the style of the
existing tool names (Find in Databases, DFT Workbench, MLIP Playground).

**Rejected.** None was discussed.

**Revisit if** the tasks keep needing operations outside this list.

## D16. Task 4 means improving goldilocks-core's parameter rules (2026-11-25)

**Decision.** In the first version, method development support (D8, task 4) means improving
goldilocks-core's rules for choosing calculation parameters. The agent:
1. takes a proposed rule, for example a new way to choose the k-point density, smearing or
   plane-wave cutoff;
2. designs a comparison over a set of materials;
3. runs convergence studies with core's current rule as the baseline and with the proposed rule;
4. compares accuracy and computational cost;
5. reports.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). Claude's reasons:
- It is Goldilocks's main line, "Towards Smarter & Greener Materials Simulations".
- Core's current recommendations give a ready baseline.
- The results can improve core directly.

**Rejected.**
- *Improving an MLIP*: adding training data or fine-tuning for a class of materials where it fails,
  such as the one found in D7. It was offered as a second example and not chosen for the first
  version.
- *Developing a new analysis method*, such as a descriptor or a classifier.

**Revisit if** the parameter-rule studies turn out too expensive to run as an agent task, or another
kind of method work becomes more pressing.

## D17. A watcher wakes a paused subgraph when its AiiDA job ends (2026-11-25)

**Decision.**
1. **Pausing.** A subgraph that submits an AiiDA job records the job's process identifier, then pauses
   with `interrupt()`. LangGraph keeps the paused state in its checkpointer.
2. **Waking.** A watcher in the agent's server waits for the job to end, using AiiDA's own
   `call_on_process_finish`. It then resumes the subgraph with `Command(resume=...)`, passing the
   job's outcome.
3. **Catching up after a restart.** When the server starts, for example after a laptop was closed,
   the watcher first checks every paused job. Any that have already ended are resumed at once.
4. **Notifying the user.** The same watcher raises the "job finished" card of the AiiDA module (D12).

The model never polls.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). Claude's reasons:
- It reacts as soon as a job ends, and the model spends no calls on waiting.
- AiiDA's own pattern combines a broadcast subscription with polling as a fail-safe, and that
  pattern is proven.
- Jobs keep running on HPC through the AiiDA daemon whether or not the agent's server is up, and the
  catch-up step means no finished job is missed.

**Facts** (checked 2026-11-25):
- In aiida-core (`src/aiida/engine/runners.py`), `call_on_process_finish` subscribes to the process's
  broadcast state changes to finished, killed or excepted. "As a fail-safe, a polling-mechanism is
  used ... should the broadcast message be missed."
- The predecessor's server already resumes paused runs with `Command(resume=...)` when the user
  answers a card.

**Rejected.**
- *A timer that queries AiiDA's database every few minutes.* It is simpler, but it can respond up to
  a full interval late. Option A already includes polling as its fail-safe.
- *The model polls*, calling a status tool repeatedly. It wastes model calls and context, and a small
  model drifts over a long wait. MatOS's design avoids this too.

**Revisit if** broadcasts are routinely missed, so that the fail-safe polling does all the work, or
AiiDA profiles without a message broker become the norm for users.

## D18. goldilocks-core, to be renamed goldilocks-dft, keeps its own GUI inside its package (2026-11-25)

**Decision.**
1. goldilocks-core will be renamed **goldilocks-dft**, in a new repository under `ddmms` (owner, 2026-11-25).
2. It keeps its own browser GUI, built from its `web/` sources and shipped inside its Python package,
   as release builds already do.
3. goldilocks-workbench does not embed that GUI (D12). The component-library build of core's `web/`,
   which exists only so that the agent could embed core's components, therefore loses its only
   consumer and can be dropped. No separate GUI package is needed.
4. **goldilocks-ml is no longer a separate dependency.** Its ML code moves into goldilocks-dft
   (owner, 2026-11-25). goldilocks-core depends on `goldilocks-ml==0.4.0` today, and 8 of its source
   files import it. The predecessor agent's MLIP Playground uses janus-core, not goldilocks-ml. The
   MLIP module (D10) takes its ML from goldilocks-dft.
5. The rename, the merge of goldilocks-ml and the other changes on core's side span repositories,
   so they get their own record in `ddmms/goldilocks` (v4-process D1).

**Reason.** Parts 1 and 2: owner's call (2026-11-25); no reason recorded. Part 3 answers the owner's
question, "can't the frontend be included in goldilocks-core?" It already is.

**Facts** (checked 2026-11-25, `stfc/goldilocks-core` main `2d579df5`):
- core's README documents the GUI as a standalone way to use core, through Docker or
  `goldilocks serve http`, with a guide in `docs/workbench.md`.
- `release.yml` builds `web/` and copies the result into the package as `goldilocks_core/webapp/`
  (#122). `goldilocks serve http` serves it from there.
- `web/package.json` also builds a component library (`dist-lib/`). The package is marked private,
  is not on the npm registry, and is named `goldilocks-workbench`. The predecessor agent vendors it as
  a tarball.

**Rejected.**
- *core drops its GUI and becomes an engine only.* Claude recommended it as a direction: one GUI,
  and the name clash would go. But users who install only core would lose the GUI.
- *Leave core undecided for now.*

**Revisit if** the two DFT GUIs drift apart in ways users notice (see Concerns).

## D19. Ada's deployment is decided when Ada is built (2026-11-25)

**Decision.** How goldilocks-Ada is deployed is decided when Ada is built, not in this change. What is
known so far, from the owner: it is a network deployment with limited resources, for STFC's internal
users, and it reaches SCARF (D2).

**Reason.** Owner's call (2026-11-25): "Ada's deployment is decided when we build Ada." Ada is not
urgent (D2).

**Rejected.** None was discussed.

**Revisit if** Ada is scheduled. The decision then has to settle the SCARF-credentials concern below.

## D20. goldilocks-agent ships both as a container and as a desktop app, macOS first (2026-11-25)

**Decision.** goldilocks-agent is released in two ways:
- **As a container image**, as the predecessor's local version is today.
- **As a desktop application**, first for macOS.

goldilocks-chat stays a container on the shared instance. Ada is decided later (D19).

**Reason.** Owner's call (2026-11-25): "a container as well, and an app as well". No further reason
recorded.

**Facts** (checked 2026-11-25):
- The predecessor's local version is a container image, `ghcr.io/stfc/goldilocks-agent-local`, built
  for linux/amd64 and linux/arm64 (`.github/workflows/docker-publish.yml`). It bundles chat (with
  the user's own API key, or Qwen3.8-27B on the user's computer), Find in Databases, DFT Workbench
  with goldilocks-core, and MLIP Playground.
- AiiDA 2.9 added a built-in ZeroMQ message broker. With SQLite storage, it runs "without external
  services", which the AiiDA docs class as "getting started, light production". So the app does not
  need PostgreSQL or RabbitMQ (aiida.readthedocs.io, quick install).
- Claude's note, not the owner's reason: on macOS a container runs inside a Linux virtual machine,
  which has no access to the Apple GPU. MLIPs and a local model running natively in the app can use
  it.

**Rejected.**
- *A container only*, as the predecessor does.
- *An app only, replacing the container.* This was Claude's first reading of the owner's words, and
  the owner corrected it the same day.

**Revisit if** keeping two distributions in step costs too much, or most app users turn out to be on
Linux or Windows.

## D21. The macOS app: Electron, a backend that uv installs on first launch, and Ollama (2026-11-25)

**Decision.** The app wraps the same backend and frontend that the container runs. It has four
parts:
1. **Shell: Electron.** The shell starts the backend process and opens the GUI in a window.
2. **Backend: installed by uv on the first launch.** The app ships the `uv` executable inside the
   `.app`. On the first launch, it runs uv itself, with a progress window. uv downloads a
   self-contained Python and installs the locked environment into the app's data folder. When the
   lock file changes, the app runs uv again and installs only what changed. The user never runs a
   command.
3. **AiiDA: SQLite storage with the built-in ZeroMQ broker** (AiiDA 2.9). The app manages the
   daemon, and no external services are needed.
4. **Local model: Ollama, installed separately.** The app detects Ollama, pulls the target model
   (D11) through Ollama's API with a progress bar, and guides the user to install Ollama if it is
   missing. Any other endpoint can be configured instead (D11), for example a group GPU server.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). The owner chose Electron over
Claude's suggestion of Tauri, asked whether uv would make users run commands (it does not), and
chose Ollama. Claude's reasons for parts 2 to 4:
- The app stays small, and the backend can be updated without a new app download.
- The local model runs on the most mature tool for that on a Mac.

**Facts** (checked 2026-11-25):
- uv "will automatically download Python versions if they cannot be found on the system". It uses
  self-contained python-build-standalone distributions (docs.astral.sh/uv).
- Ollama's API pulls a model with `POST /api/pull` (ollama/ollama `docs/api.md`).
- The predecessor's goldilocks-core autostart also installed its dependencies on first start, which
  took more than 20 minutes.

**Rejected.**
- *Tauri* (Claude's suggestion). It is small and uses the system WebKit, but needs a Rust toolchain.
  The owner chose Electron.
- *A Python-native shell* (pywebview, Briefcase). Packaging torch-sized dependencies this way is
  hard.
- *Bundling the whole Python environment in the app.* It would install offline, but the app would be
  several GB and every update would mean downloading all of it again.
- *Bundling a model runtime* such as llama.cpp. We would maintain it ourselves.

**Known costs.** The first launch needs a network connection and takes a while (torch and MLIP
models are large). The user installs two apps: Goldilocks and Ollama.

**Revisit if** the first-launch install fails often on users' machines, or Ollama stops being the
usual way to run local models on a Mac.

## D22. Four DFT codes in the first version: Quantum ESPRESSO, VASP, CP2K and CASTEP (2026-11-25)

**Decision.** The first version supports VASP, CP2K and CASTEP as well as Quantum ESPRESSO. The work
falls in two places:
- **goldilocks-dft** (core, renamed, D18): parameter recommendations and input generation for each
  code. This goes into the cross-repository record that D18 calls for, in `ddmms/goldilocks`.
- **This repository**:
  - the DFT module's GUI lets the user choose the code;
  - the AiiDA module runs each code through its own AiiDA plugin (`aiida-quantumespresso`,
    `aiida-vasp`, `aiida-cp2k`, `aiida-castep`). **goldilocks-dft's parameters always set the
    inputs**: as protocol overrides for Quantum ESPRESSO and VASP, and directly for CP2K and
    CASTEP. The workflows call the plugins' own workchains, for example Quantum ESPRESSO's
    `PwBaseWorkChain`, which restarts failed runs. Neither AiiDA Common Workflows nor the AiiDAlab
    apps are used. AiiDAlab-QE serves as a reference for how to combine workchains (bands, PDOS,
    phonons). Because both use the same AiiDA profile, a user who also has AiiDAlab can browse the
    agent's calculations there;
  - the workflows (D9) stay independent of the code wherever they can;
  - the parameter-rule studies of D16 can span codes.

**Reason.** Claude proposed VASP, CP2K and CASTEP as candidates, VASP first. The owner chose all
three (2026-11-25). Claude's reasons, code by code:
- **VASP** is the most widely used, and the reference results for D7 came from VASP.
- **CP2K** is open source, and its Gaussian-and-plane-wave basis complements Quantum ESPRESSO and
  VASP.
- **CASTEP** is developed in the UK and distributed through STFC, which puts it close to STFC's
  users.

On the AiiDA layer, the owner chose the four per-code plugins over AiiDA Common Workflows
(2026-11-25), and chose them over the AiiDAlab apps, as Claude recommended. Claude's reasons for the
plugins over the apps: they fit D9 (subgraphs drive the workchains), D10 and D12 (our own GUI) and
D21 (Electron), and they make sure goldilocks-dft's parameters take effect.

**Facts** (checked 2026-11-25):
- goldilocks-core supports only Quantum ESPRESSO. VASP appears in its source only as the method behind
  literature Hubbard U values (`advisors/hubbard_u.py`).
- AiiDA's plugin registry lists `aiida-vasp`, `aiida-cp2k`, `aiida-castep` and
  `aiida-quantumespresso` as stable.
- CASTEP has "a cost-free worldwide source code licence ... for academic use", offered per research
  group through STFC's licence site, subject to checks of academic status (castep.org/get_castep,
  read 2026-11-25).
- `aiida-quantumespresso`'s `get_builder_from_protocol` takes `overrides` that "override the defaults
  of the protocol". `aiida-vasp` also has `get_builder_from_protocol`. No protocol builder was found
  in `aiida-cp2k` or `aiida-castep`.
- AiiDA Common Workflows has one base workflow, Common Relax (11 codes, including all four here),
  plus an equation-of-state and a dissociation-curve workflow built on it. Its parameters come from
  per-plugin protocols named fast, moderate and precise.

**Rejected.**
- *Quantum ESPRESSO only*, as today.
- *Add the codes one at a time, VASP first*, as Claude suggested. The owner chose all three for the
  first version.
- *AiiDA Common Workflows as the layer for all codes.* Claude suggested it after the survey, then
  withdrew it. Its protocols choose the parameters, which would bypass goldilocks-dft, and it covers
  only relaxation and what is built on it. The owner rejected it.
- *The AiiDAlab apps* (AiiDAlab-QE and counterparts for the other codes). They bring their own
  workflows and a Jupyter-based GUI, which does not fit D12 or D21. Whether apps exist for CP2K,
  CASTEP and VASP was not verified.

**Known costs.**
- Each code needs its own parameter rules in goldilocks-dft. Cutoffs depend on the pseudopotentials,
  PAW datasets or basis sets, and CP2K's convergence parameters differ in kind (a Gaussian basis plus
  plane-wave grids).
- Testing grows with every code.
- VASP and CASTEP need licences that users hold themselves (see Concerns).

**Revisit if** four codes in the first version delay it too much. Then stage them, VASP first.

## Concerns

- **SCARF credentials for a network deployment of Ada.** SCARF's terms treat access under someone
  else's identity as a Computer Misuse Act matter, so one shared account cannot submit for everyone
  (agent design doc, section 20.1, branch `docs/ada-version`). If Ada runs as a shared network
  service, it would need each user's own SCARF credentials. That runs against v4-process D21: agents
  never handle credentials. Ada's deployment decision has to settle this.
- **The reasons behind section 17 of the agent design doc** (2026-09-10, overturned by D3 and by the
  intent's Deep Agents choice). Those reasons were as follows. Only four model providers are needed,
  two of which share a protocol. The agent is the only package that needs an LLM SDK, and another
  dependency tree erodes the benefit of standalone packages. And a framework could block structured
  output through vLLM's guided decoding. Where they stand on 2026-11-25:
  - The dependency cost remains.
  - litellm can stay underneath through LangChain's `langchain-litellm` (`ChatLiteLLM`), and Ollama
    has an official LangChain integration.
  - vLLM was set aside on the shared instance (OneDrive `1-docs/README.md`, entry for 2026-11-23), so
    guided decoding is not in use now.
- **MatOS is a design reference only.** It is licensed under PolyForm Noncommercial 1.0.0. Learn from
  its design; never copy its code or prose into this repository.
- **Third-party skills run code on the user's machine.** Skills such as AtomisticSkills run scripts.
  Two things are not decided: which skill sources are trusted, and where their code executes (the
  local shell, or a sandbox).
- **"Similar results" needs a reference comparison.** Checking D7 means comparing the agent's results
  with the earlier study's: the funnel and the final picks. That is an evaluation of the product.
  v4-process D23 deferred evaluations of the agent configuration. The plan has to define this
  comparison and keep the reference data private.
- **Two records of a run.** Under D9, LangGraph checkpoints hold the subgraph's state, and AiiDA holds
  the provenance of HPC calculations. MLIP and analysis steps run in the subgraph are not in AiiDA's
  provenance unless they are run through AiiDA as well. Two questions are open: which record is
  authoritative, and how a subgraph waits for an AiiDA job without polling.
- **Name clash (resolved by D18).** goldilocks-core's `web/package.json` uses the name
  `goldilocks-workbench`. The package is private and was never published, so it is renamed along
  with core's rename to goldilocks-dft.
- **Two DFT GUIs.** Under D12, this repository has its own DFT GUI. If goldilocks-core keeps
  publishing its Workbench GUI, there are two, which is what the 2026-09-24 decision avoided. To
  limit drift, the GUI can be driven by core's published capabilities, as the chat's draft rules
  already are (stfc/goldilocks-agent#142). The owner chose to keep core's GUI (D18), so
  this risk is accepted.
- **Signing a macOS app.** Apps from outside the App Store are blocked by Gatekeeper unless they are
  signed with a Developer ID and notarised. That needs an Apple Developer Program membership, held by
  someone; who holds it is not known.
- **AiiDA without RabbitMQ.** D17 relies on AiiDA's broadcasts. Whether they work the same with the
  built-in ZeroMQ broker (D20) has to be checked before the watcher is built.
- **Licensed codes and potentials.** Neither the container nor the app may ship VASP, CASTEP or VASP's
  POTCAR files. Users bring their own licences and point the agent at the codes and potentials
  installed on their HPC system (D22).
- **Related systems, and what is distinctive here.** A survey of more than 30 agents for DFT and
  atomistic simulation was run on 2026-11-25. It found precedents for each part of this design:
  - CatMaster uses the same stack (Deep Agents, LangGraph, LangChain, FastAPI, React). It runs long
    work in durable background threads with DBOS, and it is licensed Apache-2.0.
  - `dft-agent` already ships as a desktop app for macOS and Windows and drives five DFT codes on the
    user's own cluster.
  - The AiiDA team's `aiida-agents` gates every database write at the tool. It has no licence file.

  What none of them was found to combine: goldilocks-dft's parameter recommendations, explicit
  subgraphs that let a local small model do the work, AiiDA provenance, four DFT codes, and both a
  container and a macOS app. The plan starts by reading CatMaster's code and reusing what fits,
  under its Apache-2.0 terms. Every surveyed agent's code is reviewed with the owner, one system at a
  time (2026-11-25).

## Open

None. Every open item was decided with the owner on 2026-11-25.
