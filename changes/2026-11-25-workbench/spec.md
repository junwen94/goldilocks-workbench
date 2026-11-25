# Spec: Goldilocks Workbench in three forms, with the agent on Deep Agents

From: `intent.md` (same folder). Status: in progress. Decisions are made one at a time with the
owner and added here. The spec is accepted when its PR merges.

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
the predecessor: MLIP, DFT, Find in Databases, Post Analysis and AiiDA. More will be added. How a tool
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

## Open

From the intent, still to decide one at a time:

- How is goldilocks-Ada deployed? (Owner: a network deployment, with the solution to be decided. Ada
  is not urgent.)
- What does "a real materials science agent" need, concretely? D7 fixes the first target task. Still
  open: which other long tasks come first, and what the workflow runtime needs, such as waking the
  agent when an AiiDA job ends instead of polling. The owner points to MatOS (arXiv 2610.34203,
  github.com/DingyangLyu/MatOS) as the reference.
- How does a tool plug in (D6)? Options include packages in this repository (the predecessor's
  pattern), MCP servers, and installable plugins.
- What is carried over from `stfc/goldilocks-agent` (frontend, tools, tests, deployment), and what is
  rewritten?
- How does the live website move from the old agent to goldilocks-chat without breaking it for users?
- Which models does each form use? (D7: the agent must work with a local small model.)
- Does any of this need changes in `goldilocks-core`? If so, that part gets its own cross-repository
  record in `ddmms/goldilocks` (v4-process D1).
