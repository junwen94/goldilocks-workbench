# Spec: Goldilocks Workbench in three forms, with the agent on Deep Agents

From: `intent.md` (same folder). Status: in progress; accepted when its PR merges. Decisions D1 to
D22 were made one at a time with the owner on 2026-11-25. D23 onward come from the code-review
sessions, in which the owner reviews the surveyed agents one at a time (from 2026-11-25).

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

## D5. goldilocks-agent loads Agent Skills, such as AtomisticSkills (2026-11-25; amended 2026-11-25)

**Decision.** goldilocks-agent can load skills in the Agent Skills format (a `SKILL.md` with `name` and
`description`, optionally with scripts and references). AtomisticSkills is one example of a source.
Goldilocks's own skills use the same format.

**Sources** (amended). Skills come only from Goldilocks itself or from sources that the user adds. A
`.agents/skills/` folder inside a workspace is never read on its own.

**Reason.** Owner's call (2026-11-25): the agent should be able to load "AtomisticSkills and various
skills like it". No further reason recorded.

The sources were settled in the ChemGraph code-review session (question 7, second part). Claude laid
out three options and recommended asking the user once for each workspace. The owner chose the
strictest (2026-11-25, translated from Chinese): "C. Skills must be provided by us or by the user."
No further reason recorded.

**Facts** (checked 2026-11-25):
- Deep Agents skills follow the Agent Skills specification (agentskills.io). Each skill is a directory
  with a `SKILL.md` and optional supporting files (docs.langchain.com/oss/python/deepagents/skills).
- AtomisticSkills (github.com/learningmatter-mit/AtomisticSkills, MIT licence) holds 130 skills in
  this format, for example MLIP-based bond dissociation energies. 120 of them tell the agent to run
  Python or shell scripts, so they need an environment to execute code in, with packages such as
  MLIPs, ASE and RDKit.

**Rejected.** Nothing was discussed when D5 was first decided. At the amendment:
- *Load a workspace's `.agents/skills/` automatically.* It is convenient, but skills that others put
  there would steer the agent unseen.
- *Ask once for each workspace*, as Claude recommended, and remember the answer. The owner did not
  choose it.

**Revisit if** most useful skills cannot run without heavy setup on users' machines, or the skill format
used by Deep Agents and by skill authors drifts apart.

**Overturns** nothing in this spec. The amendment sets aside one part of ChemGraph's skill plumbing that
the code review proposed borrowing: discovery under `<workspace>/.agents/skills/`.

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
what the model can work out for itself. The model makes only the open decisions. Since D9 was
amended (2026-11-25), the method is a recipe of tools; the model may adapt it, and code checks the
result.

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
   with a Goldilocks skill, D40), run DFT through AiiDA on the top few, then rank them and report.
3. **MLIP validation.** Compare an MLIP with DFT over a set of structures and find the local atomic
   environments where it errs.
4. **Method development support**, like the two new methods that MatOS supported. D16 defines it.
5. **The target task of D7.**

Since D9 was amended (2026-11-25), each task is a recipe: a ready-made graph of tools, which the
agent may also adapt.

**Reason.** Owner's call (2026-11-25); no reason recorded. Claude drew tasks 1 to 4 from MatOS's
research cases and Goldilocks's strengths.

**Rejected.** *Leave method development support (task 4) for later*, which Claude suggested because it
is the hardest and the least defined. The owner kept it in the first version.

**Revisit if** the first version cannot be finished with all five tasks. Then move task 4 later first.

## D9. Workflows are plans composed from tools and run as LangGraph graphs (2026-11-25; amended twice 2026-11-25)

**Decision.**
1. **Steps are tools.** Each step of a plan is a tool from D10's registry, for example a database
   search, a relaxation, a convergence test, a band structure, an MLIP pre-screen, DFT over a list of
   structures, a ranking, or a comparison of an MLIP with DFT. Every tool has typed inputs and outputs
   and carries its own checks, which no plan can remove; for example, a relaxation always checks that
   it converged. A long step, one that waits for AiiDA, is a tool built as a LangGraph subgraph. The
   same tools are used directly in the conversation and on their panels (D10).
2. **Recipes.** A recipe is a ready-made graph of tools. The five tasks of D8 are the first five
   recipes.
3. **Plans.** For a request, the model uses a recipe as it is, adapts it (adds, removes or replaces
   tools), or composes a new graph from tools. The result is a plan: a document that names the tools,
   how they connect, and their inputs.
4. **Checking.** Before anything runs, code checks the plan: every tool exists, every output matches
   the input it feeds, no tool's own checks are removed, and the plan stays within its caps (D25). A
   plan that fails goes back to the model with the reasons.
5. **Approval and running.** The plan card (D25) shows the graph. Once the user approves it, an
   executor built on LangGraph runs it under the Deep Agents agent. Inside a long step:
   - deterministic steps and checks are nodes;
   - loops are conditional edges, or a fan-out over candidates;
   - steps that need the user pause with `interrupt()` (D3's mechanism);
   - HPC jobs go through AiiDA (D4, D17).
6. **Tools and skills.** Computation is written as tools. Guidance, experience and the reading of
   results are written as skills (D5, D40).
7. **Repairs.** A failed step is first repaired by the AiiDA plugin's own handlers, for example
   `PwBaseWorkChain`'s restarts. Beyond that, the agent may choose only among repair options that code
   computes from the failure diagnosis, at most twice per step, and then asks the user. A repair that
   changes the plan goes through D42 (added in the DFT Agent (Cui) code-review session; Claude's proposal, to which the owner did not object).
8. **Branch points.** At a branch point, the model chooses among the next steps that the plan allows,
   through structured output limited to them; a failed choice is reported, never guessed. A step whose
   inputs are fully determined runs without asking the model. "Router" is a configuration role of its
   own (D11), starting as qwen3.8 27B (added in the El Agente code-review session; Claude's proposal, to which the owner did not object).
9. **Invalid output.** When the model's structured output is invalid, it gets the list of errors and
   rewrites once; if it is still invalid, the step pauses and asks the user, and never crashes. Code
   keeps the state, and the model returns only what changes (added in the ORNL matsim-agents code-review session; Claude's proposal, to which the owner did not object).

**Reason.** The first version (2026-11-25), one fixed subgraph per task, was the owner's call, made
before Claude had set out the options; no reason recorded.

The amendment came from the owner's question (2026-11-25, translated from Chinese): "I don't really
understand, but I feel these graphs are very predefined. I thought there would be some very flexible
nodes, and the LLM would compose them into all sorts of graphs." Claude set out three options.
Proposed by Claude, chosen by the owner. Claude's reasons:
- It gives the flexibility the owner asked for and keeps what lets a small model work. The model
  picks and connects steps, which are bounded choices; it does not write a procedure's insides, and
  the checks inside the steps cannot be skipped.
- A recipe is a good starting point for a small model. Adapting one is easier than composing from
  nothing, and following one still completes the five tasks.
- It fits D17, D25 and D26: the plan card shows the graph, parameters can be edited on it, and
  submitting and waking work the same inside every step.

The second amendment (2026-11-25, AtomisticSkills code-review session) came from the owner's remark
(translated from Chinese): "I feel some of the blocks you describe are our original tools." Claude had
called the steps "blocks", a second idea beside D10's tools, and proposed merging the two: one idea,
tools, each usable in the conversation, on its panel, and as a plan step. Proposed by Claude, chosen by
the owner. The owner also chose the split of part 6: "computation as tools, guidance as skills".

**Facts** (checked 2026-11-25):
- Deep Agents accepts a custom compiled LangGraph graph as a subagent (`CompiledSubAgent`)
  (docs.langchain.com, read 2026-11-25).
- MatOS's Compute role tells the model to write a workflow at run time from 14 curated node
  templates. Its runtime checks the model's changes to a graph: it computes their risk itself,
  refuses restricted fields, and holds risky changes, such as adding a compute node or rewiring a
  check, for review (`src/matos/workflows/dynamicPatch.ts`, `src/matos/workflows/nodeTemplates.ts`
  @a50fd76; design only).
- In the code review, aiida-agents' authors saw a local model ignore a prompt instruction five times
  out of five, and judged local models unreliable for procedures driven by prompts. AutoDFT validates
  the plans its model edits: it drops unknown fields, rejects empty plans and checks that
  dependencies hold (`workflow_controller.py:239-308` @4c8e16f; design only).

**Rejected.**
- *Fixed workflows*, one subgraph per task, as first decided. The model would only pick one of five
  graphs and fill in its inputs. It is the most reliable for a small model, but it can do only those
  five tasks.
- *Free planning*: the model arranges every step in text or code, as Deep Agents does by default and
  as ChemGraph does. It is the most flexible, but the least reliable for a small model, and it goes
  against D7.
- At the second amendment: *keep blocks and tools as two layers*, registered apart. Users and
  contributors would have one more idea to learn, and two lists that can drift apart. For the split:
  *everything as skills*, so that key computations rest on a small model following text; and
  *everything as tools*, which would leave the marketplace little to contribute.
- These were not discussed when D9 was first decided:
  - *AiiDA WorkChains as the workflow layer.*
  - *A workflow runtime of our own, as in MatOS.* The executor is built on LangGraph instead.

**Known costs.** More to build: typed tool interfaces fit for plans, the plan checker and the
executor. How well a 27B model adapts and composes plans is not known; evaluations have to show it
(see the Concern on the reference comparison).

**Revisit if** the long steps cannot wait for long AiiDA jobs and resume cleanly, or keeping both
LangGraph's state and AiiDA's provenance proves error-prone (see Concerns). For the amendment: the
27B model's plans often fail the checks or miss what a recipe would have done, so that recipes are
almost always used as they are; or the plan checker cannot stop unsafe plans.

**Overturns** the first version of this decision (2026-11-25), in which the agent delegated each task
to its own fixed subgraph. D8's five tasks are now read as recipes. The second amendment drops the
first amendment's separate idea of blocks: plan steps are D10's tools.

## D10. A tool is a module in this repository, with an optional GUI (2026-11-25; amended 2026-11-25)

**Decision.** Each tool group is a module in this repository. A module has up to three parts:
- the tools the agent calls (Python);
- an optional GUI panel in the app (React);
- an optional backend.

A registry lists the modules. Adding a tool means adding a module and its registry entry, with no
change to the agent loop or the forms (D6).

**Plan steps** (amended, with D9's second amendment). Every tool can also be a step in a plan (D9): it
declares typed inputs and outputs, and its checks. A long step that waits for AiiDA is a tool built as
a LangGraph subgraph. Every number a tool returns carries its unit (added in the El Agente code-review session; Claude's proposal, to which the owner did not object). Each tool also declares its side-effect class: run it again, skip it if done,
reconcile before resubmitting, or wait for the user. The catch-up of D17 and D33 acts on that class
(added in the MatOS code-review session; Claude's proposal, to which the owner did not object). A module may use outside packages for the science it
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

## D15. Structure Builder: its name and first operations (2026-11-25; amended 2026-11-25)

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
| Enumerating magnetic orderings (amended), from goldilocks-dft | D7 |

**Magnetic orderings** (amended). Structure Builder does not enumerate orderings itself. It calls
goldilocks-dft's enumeration, which uses spinforge instead of enumlib: supercells up to twice the
primitive cell, antiferromagnetic candidates labelled `afm-1`, `afm-2`, ... and ferrimagnetic ones
listed separately as `fim-1`, `fim-2`, ... (owner's decision of 2026-11-24, junwen94/goldilocks-core#308).
Moments are held in µB and converted for each code when inputs are written.

**Reason.** The magnetic-orderings amendment comes from the ORNL matsim-agents code-review session:
Claude had proposed pymatgen's enumerator with enumlib, and the owner pointed to the decision already
taken for goldilocks-core (translated from Chinese): "Didn't we discuss this in the latest issue? Use
spinforge." That decision (junwen94/goldilocks-core#308) cites spinforge (github.com/spglib/spinforge,
BSD-3-Clause; Nomoto et al., Phys. Rev. X 16, 041052, 2026) and compares it with enumlib on six
benchmarks. That enumeration lives in goldilocks-dft is Claude's reading of D18.

Proposed by Claude, chosen by the owner (2026-11-25). The owner asked for "a structure
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

## D17. A watcher wakes a paused subgraph when its AiiDA job ends (2026-11-25; amended 2026-11-25)

**Decision.**
1. **Submitting, then pausing.** A subgraph submits an AiiDA job in one node and pauses with
   `interrupt()` in the next, because LangGraph runs a node again from its start when it resumes.
   - Each submission carries a fixed key, derived from the thread and the node, never random. The key
     is stored in AiiDA together with the job.
   - Before submitting, the node asks AiiDA for a job with that key, and takes that job over if there
     is one.
   - The subgraph's state holds the job's process identifier. Where the user approved the inputs, it
     also holds their digest, and the node submits only inputs that match it.

   LangGraph keeps the paused state in its checkpointer.
2. **Waking.** A watcher in the agent's server waits for the job to end, using AiiDA's own
   `call_on_process_finish`. It then resumes the subgraph with `Command(resume=...)`, passing the
   job's outcome.
3. **Catching up after a restart.** When the server starts, for example after a laptop was closed,
   the watcher reconciles every unfinished subgraph with AiiDA:
   - paused with a process identifier: resumed at once if the job has ended, otherwise left waiting;
   - stopped inside its submit node: that node runs again, takes over the job with its key if AiiDA
     has one, and submits only if AiiDA has none;
   - anything that cannot be decided, for example two jobs with one key, goes to a "needs check"
     state and a card for the user.

   A job whose state is unclear is never resubmitted automatically.
4. **Notifying the user.** The same watcher raises the "job finished" card of the AiiDA module (D12).
5. **Which record counts.** AiiDA is the only record of what ran on HPC and how it ended. LangGraph's
   checkpoint records where each subgraph is in its procedure. There is no separate submission ledger.

The model never polls.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25). Claude's reasons:
- It reacts as soon as a job ends, and the model spends no calls on waiting.
- AiiDA's own pattern combines a broadcast subscription with polling as a fail-safe, and that
  pattern is proven.
- Jobs keep running on HPC through the AiiDA daemon whether or not the agent's server is up, and the
  catch-up step means no finished job is missed.

Parts 1, 3 and 5 were amended in the first code-review session (ChemGraph, question 2): proposed by
Claude, chosen by the owner (2026-11-25). Claude's reasons:
- AiiDA already keeps a permanent record of every job it submits. A second ledger would repeat it and
  could disagree with it.
- ChemGraph's journal needs an operator for every "uncertain" record, because it has no outside record
  to ask. Here AiiDA is that record, so most cases after a restart resolve on their own.
- Under D23 every borrowed design is written anew, so the smaller design costs less.

**Facts** (checked 2026-11-25):
- In aiida-core (`src/aiida/engine/runners.py`), `call_on_process_finish` subscribes to the process's
  broadcast state changes to finished, killed or excepted. "As a fail-safe, a polling-mechanism is
  used ... should the broadcast message be missed."
- The predecessor's server already resumes paused runs with `Command(resume=...)` when the user
  answers a card.
- "When execution resumes ..., the runtime restarts the entire node from the beginning", so code
  before `interrupt()` in the same node runs again (LangGraph docs, `oss/python/langgraph/interrupts`,
  read 2026-11-25).
- In the code review: CatMaster gives each submission a new random identity, so a restart probably
  submits a duplicate, and Aitomia runs a calculation again when its process dies inside a node.
  ChemGraph's `recover()` turns an interrupted call into "uncertain" for an operator to settle
  (`src/chemgraph/runtime/journal.py:210-235` @dcb129e). matsim-agents saves "submitting" before it
  contacts the scheduler, and after a restart an unconfirmed submission becomes `needs_manual_check`.

**Rejected.**
- *A timer that queries AiiDA's database every few minutes.* It is simpler, but it can respond up to
  a full interval late. Option A already includes polling as its fail-safe.
- *The model polls*, calling a status tool repeatedly. It wastes model calls and context, and a small
  model drifts over a long wait. MatOS's design avoids this too.
- *A separate submission ledger* (at the amendment), written anew after ChemGraph's operation
  journal: a SQLite table that takes each submission through prepared, approved, submitting,
  submitted and finished. It records the most states (approved but not yet submitted, expired
  approvals, a full audit trail). But it is a second record of each job that can disagree with
  AiiDA, and it is the most code to write.
- *Keep parts 1 and 3 as first written* (at the amendment), with only the process identifier in the
  subgraph's state. A resumed node would submit again, and a crash between submitting and saving the
  identifier would leave an orphan job that a restart submits a second time.

**Known costs.** "Approved but not yet submitted" is recorded only in LangGraph's checkpoint.

**Revisit if** broadcasts are routinely missed, so that the fail-safe polling does all the work, or
AiiDA profiles without a message broker become the norm for users. For the amendment: a plugin's jobs
cannot carry the key from the moment they are created, so that "not found" no longer means "never
submitted"; or users need a record of approvals that outlives the checkpoint.

**Overturns** parts 1 and 3 as first written on 2026-11-25: one step recorded the identifier and
paused, and catching up only resumed jobs that had ended. The amendment also answers half of the
Concern "Two records of a run".

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
5. **Setting up clusters.** AiiDA computers and codes are set up through a guided wizard with ready
   configurations for common clusters, such as SCARF, and each set-up is verified by a test job.
   Letting a model probe a cluster to propose its set-up comes later (added in the DFT Agent (Cui) code-review session; Claude's proposal, to which the owner did not object).

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

## D22. Four DFT codes in the first version: Quantum ESPRESSO, VASP, CP2K and CASTEP (2026-11-25; amended 2026-11-25)

**Decision.** The first version supports VASP, CP2K and CASTEP as well as Quantum ESPRESSO. The work
falls in two places:
- **goldilocks-dft** (core, renamed, D18): parameter recommendations and input generation for each
  code. It takes each value from one of four sources: ML, heuristics, the human, or the LLM. The
  agent's model may recommend values to goldilocks-dft, and may even set them, for example the
  pseudopotential or the exchange-correlation functional. This goes into the cross-repository record
  that D18 calls for, in `ddmms/goldilocks`.
- **This repository**:
  - the DFT module's GUI lets the user choose the code;
  - the AiiDA module runs each code through its own AiiDA plugin (`aiida-quantumespresso`,
    `aiida-vasp`, `aiida-cp2k`, `aiida-castep`). **goldilocks-dft's parameters always set the
    inputs**, whichever of its four sources each value came from: as protocol overrides for
    Quantum ESPRESSO and VASP, and directly for CP2K and CASTEP. The workflows call the plugins' own workchains, for example Quantum ESPRESSO's
    `PwBaseWorkChain`, which restarts failed runs. Neither AiiDA Common Workflows nor the AiiDAlab
    apps are used. AiiDAlab-QE serves as a reference for how to combine workchains (bands, PDOS,
    phonons). Because both use the same AiiDA profile, a user who also has AiiDAlab can browse the
    agent's calculations there;
  - the workflows (D9) stay independent of the code wherever they can;
  - the parameter-rule studies of D16 can span codes.

**Not a source** (amended). Statistics of past runs in the user's AiiDA profile, such as median
cutoffs, are used neither by the model nor on the card.

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

On where parameters come from, the owner added (2026-11-25, translated from Chinese): "The model can
recommend parameters to goldilocks-dft, and even set them, for example the pseudo or the xc. This is
also something we have to deliver in the new goldilocks-dft: four sources, ml, heuristic, human,
llm." The owner said it to correct Claude, who had said in the ChemGraph code-review session that
D22 does not let the model set parameters. D22's text never said so; the claim came from Claude's
reading of the code review.

On statistics of past runs, the owner chose not to use them (2026-11-25), in the aiida-agents
code-review session (question 5). Claude had recommended showing them to the user only. No reason
recorded.

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
- goldilocks-core already resolves each setting by source, in the order `human > ml > llm >
  heuristic` (`src/goldilocks_core/resolution.py`, stfc/goldilocks-core main at `2d579df5`).
  junwen94/goldilocks-core#258 (open) adds a request field through which a caller sends LLM values
  for the functional and the pseudopotential table. Core itself never calls an LLM.
- aiida-agents takes median `ecutwfc` and `kpoints_distance` over the first 20 successful runs of one
  workflow label, from a query with no set order and without regard to elements, and its prompt tells
  the model to rely on them (`src/aiida_agents/tools/run_context.py:266-392`,
  `src/aiida_agents/agents/execution/prompt.md:260` @28314e7).

**Rejected.**
- *Quantum ESPRESSO only*, as today.
- *Add the codes one at a time, VASP first*, as Claude suggested. The owner chose all three for the
  first version.
- *AiiDA Common Workflows as the layer for all codes.* Claude suggested it after the survey, then
  withdrew it. Its protocols choose the parameters, which would bypass goldilocks-dft, and it covers
  only relaxation and what is built on it. The owner rejected it.
- At the amendment, for statistics of past runs: *show them to the user only*, as Claude recommended,
  and *let the model use them*, which repeats aiida-agents' mistake. The owner did not choose them; no
  reason recorded.
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

**Overturns** nothing in this spec. The owner's addition corrects Claude's statement in the ChemGraph
code-review session, and the code-review note that AiiDA gets "never what the model proposed".

## D23. Code from other projects is re-implemented from its design, never copied (2026-11-25)

**Decision.** This repository copies no source code from other projects, whatever their licences
allow. Where a design is borrowed from another project, for example ChemGraph's operation journal,
it is written anew here. So every file in this repository is BSD-3-Clause (D14). As Claude reads the
decision, it covers the following:
- Installing a library as a dependency is not copying.
- Code carried over from `stfc/goldilocks-agent` (D13) is this project's own BSD-3-Clause code, so
  D13 stands.
- Third-party skills (D5) are loaded at run time from a source the user chooses. They are not bundled
  into this repository or the app.

**Reason.** Owner's call (2026-11-25), in the first code-review session (ChemGraph), from three options
that Claude laid out. Claude had recommended a `third_party/` directory (rejected below). No reason
recorded.

**Facts** (checked 2026-11-25):
- The code review covers 40 agents for DFT and atomistic simulation. The licences of 26 allow copying
  with their notices (17 MIT, 6 Apache-2.0, 3 BSD). Two are LGPL, which allows use as a library only.
  For the other 12, only the design may be learned from.
- Apache-2.0 requires copied files to keep its licence text and notices, and changed files to say
  that they were changed (section 4).

**Rejected.**
- *Copy files into this repository's source, each keeping its licence notice and marking changes.*
  Licences would be mixed through the source. The owner did not choose it; no reason recorded.
- *Keep copied code apart in `third_party/<project>/`, each with its licence and source commit*, as
  Claude recommended. The owner did not choose it; no reason recorded.

**Known costs.** Re-implementing is the most work, and it gives up code that its authors have already
tested. Both were stated when the options were laid out.

**Revisit if** re-implementing a borrowed design costs much more than copying it would have, or a
re-implementation repeats a bug that the original had already fixed.

**Overturns** the plan step in Concerns ("Related systems"), which said the plan reuses what fits from
CatMaster "under its Apache-2.0 terms". The plan now borrows CatMaster's design only.

## D24. Backend updates wait while subgraphs are paused (2026-11-25; amended 2026-11-25)

**Decision.** While any subgraph is paused, for example waiting for an AiiDA job (D17), the macOS app
(D21) does not update its backend. It tells the user that an update is waiting, and why. As Claude
reads "or ask the user", the user may install the update anyway, for example for a security fix.
Paused runs that then fail to resume go to D17's "needs check" state; their AiiDA jobs and results
stay in AiiDA. Subgraphs carry no version for resuming across updates.

**In the container** (amended). Whoever runs the container updates it by pulling a new image, which
the software inside cannot hold back. So each paused run records the backend version that paused it.
When a newer version starts and finds runs paused by an older one, it lists them in the interface and
in the log. It tells the operator that they can go back to the previous image (D13) or carry on; runs
that then fail to resume go to "needs check". A status command lists the paused runs, so that an
operator can check before updating. The recorded version serves only this warning; it is not the
versioning for resuming that this decision rejects.

**Reason.** Owner's call (2026-11-25), in the ChemGraph code-review session (question 3), from four
options that Claude laid out. Claude had recommended versioning the changes that break resuming
(rejected below). No reason recorded.

The container part was settled in the same session, as a follow-up to question 3: proposed by Claude,
chosen by the owner (2026-11-25). Claude's reason: it is this decision's "tell the user, who may
update anyway" in the form that a container allows.

**Facts** (checked 2026-11-25):
- LangGraph's docs (`oss/python/langgraph/backward-compatibility`): a paused run fails to resume if
  the node it stopped in is renamed or removed, if a state key it holds is renamed or removed, or if
  a state field is tightened, for example by a new required field with no default. Adding, removing
  or rerouting edges is safe. LangGraph keeps no index of paused threads.
- ChemGraph refuses to resume when a fingerprint of its prompts, its tool and worker catalogues and
  its `deepagents` version changes (`src/chemgraph/agent/configuration.py:121-136`,
  `src/chemgraph/agent/main_session.py:263-308` @dcb129e).

**Rejected.**
- *Refuse to resume after any change*, as ChemGraph does. It is the simplest, but a prompt edit would
  break a run that has waited for days.
- *Version only the changes that break resuming*, as Claude recommended. Each subgraph has a version,
  raised only for the changes listed under Facts; a raised version needs a migration, or old runs go
  to "needs check". Developers must remember to raise it, and it needs its own test. The owner did
  not choose it; no reason recorded.
- *Keep old backends installed beside new ones*, each paused run pinned to the backend it started on.
  It is the most robust, but the app would carry several backends.
- For the container (at the amendment): *only document it*, so that an operator who has not read the
  documentation would not know; or *do nothing special*, so that runs would break with no warning.

**Known costs.** A long screening funnel can hold updates for weeks, unless the user chooses to
update.

**Revisit if** users often put off updates for long because runs are paused, or often update anyway
and lose paused runs. Then reconsider versioning.

## D25. goldilocks-agent's HPC jobs are approved once per plan, within hard caps (2026-11-25)

**Decision.**
1. **One approval per plan.** Before a plan (D9) submits HPC jobs, the user approves it on one card.
   The card shows the plan's graph of steps, the most jobs it may submit, the most compute time it
   may request, the most model calls and the longest wall time it may take, and the code and AiiDA
   computer it uses. (Model calls and wall time were added in the MatOS code-review session; Claude's
   proposal, to which the owner did not object.) Parameters come only through goldilocks-dft,
   from its four sources (D22); D26 lets the user edit them on the card.
2. **Within the caps, no more questions.** The subgraph then submits without asking, also when the
   watcher wakes it with nobody present (D17).
3. **Beyond the caps, it asks.** A job that would exceed any cap, or leave the plan (another code or
   computer, or parameters not from goldilocks-dft), pauses the subgraph and asks the user. A smaller
   cap, for example one that covers one round of a funnel, makes it ask again after that round.
4. **Two rules for every approval.** Only the user, through the interface, can approve; no model tool
   can. Caps are checked in code, never in prompt text.

Each job's inputs are in AiiDA's provenance, so they can be checked afterwards.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the ChemGraph code-review session
(question 4). Claude's reasons:
- The design already bounds most risks in code: the funnel's logic is code (D7, D9), parameters come
  from goldilocks-dft (D22), and the model sets no commands or paths. What is left for a person is
  mostly how many jobs and how much compute time, and that is what the caps control.
- One card lets a funnel run overnight. A smaller cap gives control round by round, so approving each
  batch becomes a special case.
- The code review found precedents. MatOS keeps budgets per run and per node and pauses when one is
  exceeded. Paimon's user profiles set how often the user may be asked, enforced in code. DFT Agent
  (Cui) binds an approval to a digest of the plan and its inputs, and checks it again at launch.

**Facts** (checked 2026-11-25):
- ChemGraph offers review of each call, an exact digest with an expiry in its scoped mode, or
  `--dangerously-skip-approvals` for runs without a terminal (`src/chemgraph/cli/main.py:715-717`
  @dcb129e). Its CLI's auto mode approves at most 50 actions in a row
  (`src/chemgraph/cli/commands.py:562` @dcb129e).
- MatOS's agent-facing `workflow_run` tool can approve, respond and deny, so its model can pass its own
  gates.
- The precedents above: MatOS `src/matos/workflows/types.ts:67-100` and
  `src/matos/workflows/workflowRuntime.ts:349-386` @a50fd76 (design only); Paimon
  `paimon/src/paimon/runtime/user_preference.py:12-80` @617e0b0; DFT Agent (Cui)
  `src/vasp_slurm_agent/project_execution.py:536-617` @e447736.

**Rejected.**
- *Approve each job.* It is the safest, but a funnel with many jobs needs many clicks, and it stops
  overnight.
- *Approve each batch*, for example each round of a funnel. It is not a separate mode: a cap that
  covers one batch does the same.
- *Skip approvals when nobody is present*, as ChemGraph's `--dangerously-skip-approvals` does. Nobody
  would guard HPC time.

**Known costs.** The caps must be defined and checked in code. The user does not see each job's inputs
before it is submitted, only in AiiDA afterwards.

**Revisit if** users raise the caps so as not to be asked, so that the caps guard nothing, or jobs
within the caps waste HPC time that a review of each batch would have caught.

## D26. On the plan card, the user can edit both the plan and the parameters (2026-11-25; amended 2026-11-25)

**Decision.** On D25's plan card, the user can edit:
- the plan: the most jobs, the most compute time, the code and the AiiDA computer;
- the parameters, as values for every job in the plan, for example a cutoff of 520 eV.

Edited parameters go to goldilocks-dft as human values (D22), and goldilocks-dft validates them and
records which values the user set. AiiDA holds the final inputs. Code checks the edited card against
the caps again, for example when a higher cutoff would need more compute time than the cap allows.
As Claude reads this decision together with D25: once a plan is approved, a later change to its
parameters from any source counts as leaving the plan, so the subgraph asks again.

**Below the recommendation** (amended). When the user's value is below goldilocks-dft's
recommendation, the card says so and names the recommendation's source, but never blocks: the user's
value stands. As Claude reads the option the owner chose, values that are not valid input at all, such
as the wrong type, are still refused, as AiiDA's own input validation does.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the ChemGraph code-review session
(question 5). Claude's reasons:
- The users know DFT, and reproducing an earlier study (D7) often needs set values.
- The predecessor's DFT draft already holds the user's overrides (stfc/goldilocks-agent#142, decided
  by the owner on 2026-11-12).
- goldilocks-dft still validates every value.

Claude also argued that without editing on the card the user could not change parameters at all,
because the model may not set them. That premise was wrong, and the owner corrected it the same day
(D22).

The amendment was the owner's call (2026-11-25), in the aiida-agents code-review session (question 4),
from three options that Claude laid out. Claude had recommended two levels, blocking values outside
hard ranges that goldilocks-dft sets and warning below the recommendation (rejected below). No reason
recorded.

**Facts** (checked 2026-11-25):
- In goldilocks-core's order of sources, a human value outranks ML, LLM and heuristic values
  (`src/goldilocks_core/resolution.py`, stfc/goldilocks-core main at `2d579df5`). Every value that a
  request sends lands in the human slot today (junwen94/goldilocks-core#258).
- ChemGraph's reviews allow approve or reject only, with no edit (`src/chemgraph/graphs/workspace.py:22-29`
  @dcb129e).
- aiida-agents compares cutoffs with the pseudopotential family's recommendation, flags values below 0.9
  times or above 3 times it, and never blocks (`src/aiida_agents/tools/execution/ranges.py:56-64,
  222-324`, `docs/adr/07-validator.md:138-192` @28314e7).

**Rejected.**
- *Approve or reject only*, with feedback that the agent acts on, as ChemGraph does. Changing one
  number would take a round trip through the model, which a small model may misread.
- *Edit the plan but not the parameters.* Parameters could then change only through the model.
- At the amendment: *block every value below the recommendation*, which would overrule the user's
  judgement; and *two levels*, as Claude recommended, which would need hard ranges from goldilocks-dft.
  The owner did not choose them; no reason recorded.

**Known costs.** The card grows more complex. The three new codes (D22) need goldilocks-dft to take
and validate human values, as it does for Quantum ESPRESSO today.

**Revisit if** users' edits often fail goldilocks-dft's checks, or users seldom edit parameters on the
card.

## D27. The model plans in two steps: a short catalogue, then the chosen tools' interfaces (2026-11-25)

**Decision.** The model makes a plan (D9) in two steps:
1. From a short catalogue, with one line for each recipe and each tool, it picks a recipe, or none,
   and the tools it needs.
2. Code then gives it the full interfaces of the chosen tools only: typed inputs, outputs and
   parameters. The model fills in the connections and the inputs, and the plan goes to D9's checks.

The two steps are themselves a fixed graph. The same two steps apply when the agent calls tools directly
in the conversation: a short catalogue first, then the full interfaces of the tools it picked (added in
the LLaMP code-review session; Claude's proposal, to which the owner did not object).

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the ChemGraph code-review session
(question 6, asked again after D9 was amended). Claude's reasons:
- The catalogue is always in view, so no tool is missed for want of a search.
- Full details go only to the tools in use, which keeps each prompt short for a 27B model.
- Deep Agents loads skills the same way: names and descriptions first, the full text when needed (D5).
- Each step is a bounded choice. Step 1 is close to a classification, which small models do best.

**Facts** (checked 2026-11-25):
- In the code review, the names and descriptions of Scientific Agent Skills' 177 skills come to about
  17k tokens, about half of a 32K local context window.
- ChemGraph makes its model search for and load workers and tools before it can use them
  (`src/chemgraph/registry/agent_middleware.py:55-93`, `src/chemgraph/registry/middleware.py:37-92`
  @dcb129e). Its IRI example claims, without data, that a flat set of 43 tools scored higher than 7
  categories with discovery (`examples/iri/README.md` @dcb129e).

**Rejected.**
- *List everything*: every recipe and every tool's full interface in each planning prompt. The prompt
  grows with every tool.
- *Let the model search*, as ChemGraph does. It adds model calls, and a small model may not find the
  tool it needs.

**Revisit if** the catalogue itself grows too long for one prompt, or the model often picks the wrong
recipe or misses a tool in step 1.

## D28. goldilocks-agent's capabilities are evaluated with LangSmith (2026-11-25)

**Decision.** goldilocks-agent's capabilities are evaluated with LangSmith: datasets of tasks,
experiments that run the agent over them, and evaluators that score the results. This includes D7's
reference comparison. As Claude reads it, this is about the product's agent; v4-process D23, which
deferred evals of the agents that develop Goldilocks, stands.

**Reason.** Owner's call (2026-11-25), raised in the ChemGraph code-review session; no reason
recorded.

**Facts** (docs.langchain.com, read 2026-11-25):
- LangSmith can evaluate LangGraph graphs and agent trajectories, with code evaluators,
  LLM-as-a-judge evaluators and a pytest integration.
- LangSmith Cloud runs in five regions, one of them in the EU; an organisation's data is stored in the
  region where it signed up. Self-hosted LangSmith is an add-on to the Enterprise plan.

**Rejected.** None was discussed.

**Revisit if** LangSmith cannot hold the private reference data on acceptable terms (see Concerns), or
its cost or limits get in the way of regular evaluation runs.

## D29. Skill scripts run in a local sandbox (2026-11-25)

**Decision.** Scripts that a skill (D5) runs execute in an isolated subprocess on the machine where the
agent runs:
- it gets only allowed environment variables, and no credentials, such as API keys or the SSH
  configuration for HPC;
- it cannot reach the AiiDA database;
- it reads and writes only in the current task's folder.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the ChemGraph code-review session
(question 7). Claude's reasons:
- Third-party code is untrusted by default. A sandbox keeps it away from credentials and from AiiDA's
  data at the least cost, as the code review advises.
- Heavy computation, such as an MLIP pre-screen over many structures, belongs in tools (D9), so skill
  scripts need not go through AiiDA.

**Facts** (checked 2026-11-25):
- 120 of AtomisticSkills' 130 skills tell the agent to run Python or shell scripts (D5).
- In the code review, ChemGraph, CatMaster, ToolUniverse, CASCADE, QUASAR and MDForge run skill
  scripts in the host's shell with the agent's environment. ToolUniverse's script runner passes a
  copy of `os.environ`.
- Claude Code's sandbox uses macOS's built-in Seatbelt framework, and bubblewrap on Linux
  (code.claude.com/docs/en/sandboxing).

**Rejected.**
- *Run scripts on the user's machine after approval*, as ChemGraph does. A script could read the SSH
  configuration and API keys, and change any of the user's files.
- *Run scripts as AiiDA jobs.* They would get provenance, and the open half of "Two records of a run"
  would close for them, but every short script would go through a job.

**Known costs.** A sandbox for each platform: macOS for the app, Linux for the container, which is
isolated already.

**Revisit if** useful skills cannot run inside the sandbox, for example because they need network or
GPU access that it blocks, or the sandbox proves unreliable on macOS.

## D30. The GUI's Tools section becomes "Tools and skills" (2026-11-25)

**Decision.** The app's Tools section becomes "Tools and skills". Next to the tool modules (D10), it
holds the skills (D5). As Claude reads the owner's words together with D5, this is where the user adds
skill sources and manages the skills. Whether MCP servers and plugins belong there too is to be
considered (see Open).

**Reason.** Owner's call (2026-11-25), in the ChemGraph code-review session (translated from Chinese):
"About this I want to add one thing: we need to design the skills part in the GUI; the original tools
become tools and skills (and we should even consider MCP, plugins and the like)." No further reason
recorded.

**Facts** (checked 2026-11-25). The predecessor's app has a resizable pane labelled "Tools"
(`app/src/App.tsx:9538`, stfc/goldilocks-agent main at `ea757c7`).

**Rejected.** None was discussed.

**Revisit if** skills and tools turn out to need separate places, for example because users manage
them in different ways.

## D31. Runs with nobody present answer their pauses through receipts and answers (2026-11-25)

**Decision.** goldilocks-agent can run with nobody at the interface, for LangSmith evaluations (D28)
and for batch runs in the container (D20). When such a run reaches a pause (a question, a plan card
under D25, or a parameter edit under D26), it:
1. writes a receipt that lists each pending pause with its ID, its kind and its content;
2. takes the answers from one of two places:
   - an answers file that a person wrote in advance, keyed by pause ID;
   - a fixed responder for evaluations, which approves plans within their caps, picks the default of
     each choice, and never supplies a physics parameter;
3. refuses answers whose IDs do not match the pending pauses.

Every answer, and where it came from, goes into the run's record. As Claude reads this together with
D25: the person who starts the run chooses the answers file or the responder, and that choice counts
as the user's approval; a model tool still cannot approve.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the ChemGraph code-review session
(question 8). Claude's reasons:
- Evaluations finish, and they can be repeated: the same answers give the same run, and stale answers
  are refused.
- The responder never supplies a physics parameter, so a score measures the agent, not the answers.
- Batch runs in the container use the same mechanism.

**Facts** (checked 2026-11-25):
- ChemGraph's runs without a terminal write a receipt of pending interrupts (ID, kind, payload) and
  resume from an answers file whose IDs must match exactly (`src/chemgraph/cli/headless.py:37-95,
  104-122` @dcb129e). The file answers only questions; tool reviews must be resumed by hand
  (`headless.py:57-60, 84-94`).
- VASP Agent's unattended evaluations use a deterministic responder that answers approvals and
  environment questions and refuses to supply parameters (`answer_script.py:1-10, 51-69`; design
  only). It always accepts the convergence test, a choice of scope that is not the model's own
  (`answer_script.py:26, 54`).

**Rejected.** *No mode for runs without a person in the first version.* Each evaluation would answer
cards through the server's API with code of its own, and batch runs in the container would have no
common way.

**Revisit if** the responder's answers drift from what users would choose, so that evaluations stop
reflecting real use, or receipts and answers prove awkward for batch runs.

## D32. In evaluations, code decides the score and an LLM judge only advises (2026-11-25)

**Decision.**
1. **Code decides.** In LangSmith (D28), code evaluators decide whether a run passes and what it
   scores. For D7 they compare, round by round, the funnel's decisions, the overlap of the final picks
   with the reference, values within tolerance, and the artefacts each step must produce.
2. **An LLM judge advises.** An LLM judge may score the report and its explanations. That score is
   kept apart and changes no verdict.
3. **Three rules for every evaluation:**
   - the reference answers and the evaluators are out of the agent's reach;
   - every failed run counts;
   - each task runs several times.
4. **What is reported.** Results give pass^k (every run of a task succeeds) as well as pass@k (at
   least one does), and score the procedure and the answer separately (added in the El Agente code-review session; Claude's proposal, to which the owner did not object).

The three rules came with the options; the owner answered "b" and did not object to them.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the ChemGraph code-review session
(question 9). Claude's reasons: code judges the science and an LLM advises on the writing, which is
the code review's principle that checks decide and LLM review only advises.

**Facts** (checked 2026-11-25):
- ChemGraph has a deterministic structured-output judge (numeric tolerances, canonical SMILES,
  structure tolerances) and an LLM judge (`src/chemgraph/eval/structured_output_judge.py:1-21, 62-83`,
  `src/chemgraph/eval/llm_judge.py` @dcb129e).
- In the code review: MASTER's LLM reviewer contradicted its own band test in about 11% of verdicts;
  DREAMS's LLM guards pass everything when the judge is missing; Paimon's critics needed a stronger
  model than the executor.
- Reference answers within the agent's reach: LAMMPS-Agents preloads the benchmark answer into the
  agent's memory, and DFT-Agent Bench's pseudopotential path points into the tree that holds the
  ground truth.
- Failures left out of the score: CASCADE and ChatMOF. Two runs of one CACTUS configuration differ by
  73 points, because one of them has 431 tool crashes among its 500 answers.

**Rejected.**
- *Code evaluators only.* Reproducible and cheap, but nothing would look at the reports.
- *Mainly an LLM judge.* The most flexible, but LLM judges erred often in the code review, and a
  frontier judge would send data to an outside service.

**Known costs.** A judge to maintain, beside the code evaluators.

**Revisit if** the judge's advisory scores turn out useless or misleading, or code evaluators cannot
capture what matters in a task.

## D33. No separate durable-execution layer; checkpoints and D17 recover from crashes (2026-11-25)

**Decision.** goldilocks-agent adds no durable workflow engine such as DBOS. Recovery after a crash
rests on LangGraph's checkpoints and on D17:
1. At start-up, D17's catch-up also finds agent turns that stopped part-way. Each either continues
   from its last checkpoint or is offered to the user to retry; the plan decides which, case by case.
2. The watcher keys each wake on the thread and the AiiDA process, so a notice that arrives twice
   resumes nothing twice.
3. A crash test kills the process at chosen phases, including one in which an AiiDA job ends while
   the server is down.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the CatMaster code-review session
(question 1). Claude's reasons:
- The crashes that cost most come around HPC jobs, and D17 with AiiDA covers them.
- What remains, an agent turn cut off part-way, can continue from a checkpoint. That does not justify
  a third record.
- DBOS's two strongest points, delivering each completion once and a crash test, can be built to the
  same design.

**Facts** (checked 2026-11-25):
- CatMaster runs background agent work as DBOS workflows on SQLite and enqueues each completion under
  a deterministic ID, `"completion-" + uuid5(run_id)` (`catmaster/runtime/execution.py:1-198, 77-83`;
  `catmaster/webui/local_execution.py:437-443` @06b8568). Its crash test kills a subprocess at
  defined phases (`tests/test_local_execution_recovery.py:11-40` @06b8568).
- In the code review, one CatMaster run is recorded in DBOS, in LangGraph checkpoints, in
  `workspace.sqlite`, in receipts, in an observability database and in a memory store.

**Rejected.** *Run each agent turn as a durable DBOS workflow*, as CatMaster does. It restarts cut-off
work by itself and delivers each completion once, but it adds a third store beside LangGraph's
checkpoints and AiiDA, against D17's part 5, and another dependency.

**Known costs.** Crash recovery is ours to write and to test.

**Revisit if** recovering agent turns from checkpoints alone proves hard to get right, or users lose
work to crashes that a durable engine would have saved.

## D34. Approved plans run in the background, and the conversation stays free (2026-11-25; amended 2026-11-25)

**Decision.**
1. Once the user approves a plan (D25), the executor (D9) runs it in a background thread of its own.
   The conversation is free at once: the user can keep talking, or start another plan. The agent
   starts the run with a typed tool whose argument is the approved plan document itself, so the plan
   is never retold as text on its way to the executor (amended).
2. The background thread's ID is derived from the parent turn and the tool call, so a replayed start
   does not open a second task.
3. When the plan ends, or needs the user (for example for a card beyond its caps, D25), a card comes
   back to the original conversation.
4. Each conversation runs one turn at a time. A card that arrives while a turn is running waits in a
   queue. Completion notices are de-duplicated as in D33.
5. When the user must decide something for each candidate, the decisions of one round come together
   on one card (added in the MatOS code-review session; Claude's proposal, to which the owner did not
   object).

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the CatMaster code-review session
(question 2). Claude's reasons:
- A task that takes days should not hold a conversation. It also fits D12's AiiDA panel, which follows
  the agent's long tasks.
- CatMaster has designs for both hard parts: child thread IDs derived from the parent, and one turn at
  a time per conversation, with a queue.
- D33's de-duplication applies as it is.

The amendment came from the LLaMP code-review session (question 1): proposed by Claude, chosen by the
owner (2026-11-25). Claude's reasons: the document the user approved is exactly what runs, which keeps
D25's approval meaningful; it fits running in the background; and it does not depend on how Deep Agents
passes state to subagents. In LLaMP, a user's thermostat requirement was lost when one agent retold a
task to another in text (`experiments/00-notebook-chat.ipynb:185, 425, 442` @77991f0), and Deep Agents'
`task` tool likewise starts a subagent from a text description (deepagents 0.7.41,
`deepagents/middleware/subagents.py:930-933`).

**Facts** (checked 2026-11-25):
- CatMaster's Research agent starts a background Experiment task with `start_async_task`, whose child
  thread ID is `uuid5(run_id + ":" + tool_call_id)` (`catmaster/webui/local_execution.py:576-630, 610`
  @06b8568). On completion, the task enqueues one follow-up turn on the parent
  (`local_execution.py:414-443`). Messages queue per workspace and thread, one at a time
  (`catmaster/runtime/execution.py:23-26, 59-84` @06b8568).
- ChemGraph's session driver refuses to start a run while interrupts are pending
  (`src/chemgraph/agent/main_session.py:185-206` @dcb129e).

**Rejected.** *Pause in the foreground*: the plan pauses in the conversation, which cannot go on until
the job ends. It is the simplest, but a conversation could be held for days. At the amendment: *start
the executor with Deep Agents' `task` and put the plan in a shared state key*, which depends on Deep
Agents' internals; and *retell the plan in text and parse it back*, the step where LLaMP lost
information.

**Known costs.** Cards that arrive during a running turn must queue, and cards beyond a plan's caps
must show in the original conversation.

**Revisit if** users lose track of their background tasks, or cards arriving in a busy conversation
confuse them.

## D35. goldilocks-agent's shell runs only in D29's sandbox; chat and Ada have none (2026-11-25)

**Decision.**
1. goldilocks-agent has a shell for side analysis, for example a quick plot or a statistic. It runs
   only in D29's sandbox: no credentials, no AiiDA database, the task's folder only. Because of the
   sandbox, commands need no approval one by one; approvals (D25) are for HPC submission.
2. The shell is for side analysis. Scientific procedures still go through tools in plans (D9), so
   D9's checks are not bypassed.
3. goldilocks-chat and goldilocks-Ada, which run on shared network servers, never have a shell.

The third rule came with the options; the owner answered "B" and did not object to it.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the CatMaster code-review session
(question 5). Claude's reasons:
- Side analysis is a real need; D6 already has a Post Analysis group.
- The sandbox removes the main dangers, so commands need no approval one by one and users are not
  flooded with cards.
- Science stays in tools and plans.

**Facts** (checked 2026-11-25):
- CatMaster gives every agent that may write an `execute` tool on an unsandboxed local shell. It
  inherits the environment, including provider API keys, with a 4-hour timeout; its boundary is a line
  in the prompt; Review gates only the two submission tools, and the default mode is `auto`
  (`catmaster/specialists/runtime.py:2167-2178, 2866-2869, 409-412` @06b8568).
- ChemGraph's main agent reviews shell commands by default (`src/chemgraph/graphs/workspace.py:22-29`
  @dcb129e), and its web UI keeps the shell workflow off unless the operator enables it
  (`src/ui/deepagent_policy.py:1-20` @dcb129e).

**Rejected.**
- *No shell.* The safest, but side analysis would be limited to the existing tools.
- *A shell on the user's machine, with approval for each command*, as ChemGraph's main agent has.
  A small model issues many commands, so approving each is tedious, and an approved command still
  reaches credentials and the user's files.

**Known costs.** Code that a small model writes may fail; the damage stays in the task's folder.

**Revisit if** side analysis needs what the sandbox blocks, or the model uses the shell for science
that belongs in tools.

## D36. Each plan run writes a research record, as a file (2026-11-25)

**Decision.** While it runs a plan, the executor (D9) writes a structured record to the task's folder:
for each step, its inputs, its AiiDA processes and its check results, and at each branch point the
model's choice with the reason it gave. Reports, evaluations (D32) and the GUI's view of past runs read
it. The record is an output and drives nothing, so D17's rule on which record counts stands: AiiDA for
jobs, the checkpoint for progress.

Results say which convergence they mean: the geometry or SCF converged, or the parameters were
convergence-tested. A bare "converged" is not used (added in the ORNL matsim-agents code-review session; Claude's proposal, to which the owner did not object).

Each task has its folder in the app's (or the container's) data folder; calculation files stay in
AiiDA (D43). Structures are named by their source ID, formula and space group, and the names are kept
in the record (added in the LLaMP code-review session; Claude's proposal, to which the owner did not
object).

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the CatMaster code-review session
(question 6). Claude's reasons:
- The decisions of each round must be recorded anyway, for D32's evaluations and for reports.
- As an output, it does not become one more record to keep in step.
- If queries across runs are ever needed, a graph can be built from these files later.

**Facts** (checked 2026-11-25). CatMaster's Research Graph keeps Hypothesis, Experiment and Result
nodes with typed edges, revisions and decisions in SQLite. Agents query it through a read-only SQL
surface, and a panel shows it (`catmaster/research/knowledge_graph/models.py:9-210, 535-620`,
`catmaster/research/knowledge_graph/query.py:13-24, 82-90`,
`catmaster/webui/frontend/src/v2/components/ResearchTechTreePanel.jsx` @06b8568). Its
`catmaster/research/` package has about 11,200 lines.

**Rejected.**
- *No record.* The reasons would stay scattered in the conversation and the report, and evaluations
  would have to dig each round's decisions out of them.
- *A full research graph*, as CatMaster has. It is one more live record, and much work.

**Known costs.** One more file per run, whose format evaluations depend on.

**Revisit if** users often need to query across runs, which would argue for a graph built from these
files.

## D37. No input setting that goldilocks-dft does not know; new settings are added to it first (2026-11-25)

**Decision.** Every setting in a calculation's input comes through goldilocks-dft's rules. The model can
set values only for settings that goldilocks-dft knows (its LLM source, D22). A setting it does not know
yet, for example a CP2K input section without a rule, is added to goldilocks-dft first; the model never
writes it into an input, and never writes a whole native input file. As Claude reads the option the
owner chose, the same holds for values the user enters on D26's card.

**Reason.** Owner's call (2026-11-25), in the CatMaster code-review session (question 7), from three
options that Claude laid out. Claude had recommended letting the model pass settings without a rule
through goldilocks-dft, checked against the code's own input definitions (rejected below). No reason
recorded.

**Facts** (checked 2026-11-25). In the code review, CatMaster's model writes the whole native input for
CP2K and ORCA (`catmaster/tools/geometry_inputs/cp2k_prepare.py:21-38` @06b8568), and one of its demos
has inconsistent van der Waals settings in an INCAR
(`demos/examples/key_files/demo_llm_o2_spin_compare/o2_box/triplet/INCAR:10` @06b8568).

**Rejected.**
- *Settings without a rule pass through goldilocks-dft as LLM values*, checked against the code's own
  input definitions and marked "no rule, from the model", as Claude recommended. The owner did not
  choose it; no reason recorded.
- *The model writes whole native input files*, as CatMaster does for CP2K and ORCA. Nothing could be
  compared or audited.

**Known costs.** A new setting waits until goldilocks-dft has a rule for it, so D18's cross-repository
record has to cover the settings that the four codes of D22 need.

**Revisit if** users often need settings that goldilocks-dft does not know yet, and waiting for it
blocks real work.

## D38. D7's evaluation compares five arms on the same tasks and evaluators (2026-11-25; amended 2026-11-25)

**Decision.** In LangSmith (D28), with D32's evaluators, the same set of tasks runs in five arms:
1. our design with qwen3.8 27B, the main arm;
2. no LLM: the recipes run as written, and every branch point takes its default;
3. free planning: qwen3.8 27B calls the same tools freely, with prose skills, without recipes or
   checked plans;
4. our design with a frontier model;
5. our design with qwen3.8 27B and no skills loaded (amended).

The tasks are written by us. AtomisticSkills' benchmark informs their design, but none is copied
(D23).

Where an arm asks for a calculation whose inputs exactly match one already run, AiiDA's caching (D39)
reuses the earlier result instead of running it again on HPC.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25, translated from Chinese: "Go with your
recommendation"), in the CatMaster code-review session (question 9). Claude's reasons:
- Without arm 2, nobody can tell whether the model helps at all.
- Without arm 3, the recipes and checked plans cannot show their worth, and D9's revisit clause
  needs that evidence.
- Without arm 4, the gap to a frontier model, which the earlier study used, stays unknown.

Arm 5 was added in the AtomisticSkills code-review session: proposed by Claude, chosen by the owner
(2026-11-25). Claude's reason: the skills marketplace (D40) is a long-term investment, and only this
comparison shows what skills give a small model in our multi-step tasks.

**Facts** (checked 2026-11-25, in the code review):
- In matsim-agents' experiment E2, an arm without an LLM scored 1.00 on verdicts, against 0.903 for
  cross-critique between LLMs, which used about 11 times the tokens of a single LLM. The arm without
  an LLM scored near zero on reasoning and uncertainty.
- VASP Agent runs an ablation with and without its procedure, scored on accuracy, launches,
  relaunches, HPC hours, model calls, tokens and cost (`experiments/08_skill_ablation/`; design only).
- AtomisticSkills' benchmark (31 tasks with hidden verifiers, a separate Apache-2.0 repository; figures
  from its website, not verified in code): Qwen3.8-27B passes 51.6% (16/31) without skills and 77.4%
  (24/31) with them. Its tasks are short and mostly use one skill each.

**Rejected.**
- *Evaluate our design alone.* It would not show what the model, the recipes or the model's size
  contribute.
- *Fewer arms.* Each arm left out leaves one of the questions above unanswered. At the amendment: *no
  arm without skills*, which would leave the value of skills unmeasured.

**Known costs.** Each arm repeats the task set several times (D32), which costs compute; replaying
cached results reduces it. Arm 4 sends task data to an outside model service (see Concerns).

**Revisit if** the replay cache cannot cover most calculations, so that the arms cost too much HPC
time.

## D39. AiiDA caching is on by default (2026-11-25)

**Decision.** In the AiiDA profiles that goldilocks-agent sets up (D20, D21), caching is on by default.
Before a calculation runs, AiiDA looks for a finished calculation with the same inputs and, if it finds
one, reuses its results instead of running it again. D38's replay uses this.

**Reason.** Owner's call (2026-11-25), raised by the owner in the aiida-agents code-review session
(translated from Chinese): "Yes, I mean caching; I think it should be on by default." Claude had
proposed caching for D38's replay and leaving the default for daily use to the plan. No further reason
recorded.

**Facts** (AiiDA documentation, "How to save compute time with caching" and the caching topic, read
2026-11-25):
- With caching on, AiiDA searches the database for a calculation with the same hash. If it finds one,
  it copies the calculation node and its results, so the provenance graph is the same whether caching
  is on or not.
- Caching works on calculations, not on workflows.
- By default, successful and failed calculations both enter the cache once they have finished;
  excepted and killed calculations do not. Plugins can mark exit codes that invalidate the cache.
- Caching is off by default. It is set per profile (`verdi config set caching.default_enabled True`)
  or for chosen kinds of calculation.

**Rejected.** *Caching for evaluations only*, with the default for daily use left to the plan, as
Claude proposed. The owner chose on by default.

**Known costs**, for the plan to handle:
- A failed calculation that finished normally is reused too, unless its exit code invalidates the
  cache.
- If a code is upgraded in place, at the same path, AiiDA may not see a new version and may reuse old
  results. This has to be checked; one remedy is a new `Code` for each version.

**Revisit if** cached results are reused where users expected a fresh run.

## D40. A Goldilocks skills marketplace, in its own repository, modelled on AtomisticSkills (2026-11-25)

**Decision.**
1. **The marketplace.** Goldilocks has a skills marketplace of its own, modelled on AtomisticSkills.
   Users can use Goldilocks's skills, contribute skills of their own, and install custom skills.
2. **Its own repository.** It lives in a repository of its own (working name
   `ddmms/goldilocks-skills`), versioned apart from the app.
3. **Format.** Skills follow the Agent Skills format (D5). Being installable in other agents, such as
   Claude Code or Codex, is welcome but not required.
4. **The first official skills** are rewritten after AtomisticSkills' designs (D23), citing its paper.
   A user may still add AtomisticSkills itself as a source (D5).
5. **In this repository**, "Tools and skills" (D30) is where the user browses and installs skills from
   the marketplace, and adds custom ones from a local folder or a git address (D5). Every skill script
   runs in D29's sandbox.

The rest of the marketplace's design is to be decided one item at a time (see Open). Because it is a
new repository, the marketplace gets its own record in `ddmms/goldilocks` (v4-process D1).

**Reason.** Owner's call (2026-11-25), in the AtomisticSkills code-review session (translated from
Chinese): "We will rewrite these skills ourselves and provide them ourselves", and "my idea is to
design a Goldilocks skills marketplace modelled on AtomisticSkills, so that users not only use
Goldilocks skills: they can also contribute, and also install custom skills" (one word read as "not
only", taken as a typo). On other agents: "No need to insist on also publishing it as a Claude Code
plugin marketplace, or for Codex and other tools; of course it is best if they can install it."

The separate repository was proposed by Claude and chosen by the owner. Claude's reasons: contributors
need not touch the app's code; skills are versioned and released apart from the app; and other tools
can use them directly, which is where AtomisticSkills' reach comes from.

**Facts** (checked 2026-11-25, in the code review). AtomisticSkills (MIT, arXiv:2605.24002) holds 133
skills from 27 authors, contributed through pull requests and checked in CI by a skill lint
(`tests/test_skill_runtime.py:107-186` @0aee5ec). It is published as a Claude Code plugin marketplace
(`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` @0aee5ec), and `configure_mcp.py`
writes configuration for Claude, Codex, Gemini, Cursor and Windsurf. Its skills rely on Claude Code's
`${CLAUDE_SKILL_DIR}` substitution and on its own launcher, and run natively on Linux only.

**Rejected.**
- For AtomisticSkills itself, three routes that Claude laid out before the owner's idea: *a
  user-installed add-on* as the main route (Claude's recommendation), *bundling its runtime* into the
  app and container, and *a compatibility layer* that runs its code in our environment. The owner chose
  to rewrite the skills and provide them instead.
- *The marketplace inside this repository.* Contributors would open pull requests against the app,
  skills would ship only with app releases, and other tools could not take them on their own.

**Known costs.** One more repository, with its own record; rewriting skills is work; a review process
for contributions has to be run.

**Revisit if** few skills are contributed, so that a separate repository adds overhead for nothing.

**Overturns** D8 task 2's example, which named AtomisticSkills for the MLIP pre-screen; it now names
a Goldilocks skill.

## D41. The MLIP tools run on aiida-mlip and janus-core; only MACE for now (2026-11-25; amended 2026-11-25)

**Decision.** The MLIP tools (D6, D10) run their calculations through aiida-mlip, which is built on
janus-core, so that MLIP calculations go through AiiDA like every other calculation (D43). Our tools
add typed inputs and outputs and their checks on top (D9): for example, a relaxation always
reports whether it converged, and every run records the model and the version actually used. At this
stage, only MACE is used.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the AtomisticSkills code-review
session. The owner added (translated from Chinese): "and at this stage we only plan to use MACE." No
reason recorded for that. Claude's reasons for janus-core:
- It comes from the same institution under the same licence (BSD-3-Clause), and it covers far more
  than AtomisticSkills' MLIP layer. The predecessor already uses it.
- D23 forbids copying code, not using libraries.
- What is worth taking from AtomisticSkills, such as a relaxation result that carries whether it
  converged, belongs in our tool layer.

The amendment is the owner's (2026-11-25, translated from Chinese): "For MLIP we want to use aiida-mlip
(github.com/stfc/aiida-mlip)." No further reason recorded.

**Facts** (checked 2026-11-25):
- janus-core (github.com/stfc/janus-core) is BSD-3-Clause; v0.9.9 was released on 2026-10-28. It
  supports MACE, CHGNet, SevenNet, NequIP, DPA3/DPA4, Orb, MatterSim, GRACE, UMA and PET-MAD, and
  offers single points, geometry optimisation, molecular dynamics (NVE, NVT, NPT), NEB, phonons
  (phonopy), equations of state, elasticity, and training and fine-tuning. MLIPs install as extras,
  and its README warns that it cannot support automatic installation of every combination of MLIPs on
  every platform.
- The predecessor calls janus-core's `janus` command line from an isolated environment
  (`mlip-cli/pyproject.toml`, stfc/goldilocks-agent main at `ea757c7`).
- AtomisticSkills' MLIP layer wraps MACE, MatGL and FairChem, selects CUDA or MPS devices, and returns
  relaxations that carry `converged` (`src/utils/mlips/` @0aee5ec; design only, D23).

**Rejected.** *Our own MLIP layer, written after AtomisticSkills' design.* It would reinvent a mature
library, cost more to maintain, and cover fewer models.

**Known costs.** Heavy dependencies, such as torch. Installing MACE on each platform, and MPS on a
Mac, has to be checked in the plan. Updates follow janus-core's releases.

**Revisit if** janus-core cannot run MACE well on users' Macs, or MLIPs other than MACE become needed;
janus-core's other extras are then the first place to look.

## D42. A running plan changes only as a revised plan, checked and approved again (2026-11-25)

**Decision.** While a plan runs, the agent may propose a change, for example an extra step after a round
of a funnel. The change is a revised plan: code checks it as in D9, the card shows what changed, and the
user approves it. The run then continues without redoing finished steps (D17's keys, D39's caching). No
change applies by itself.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the MatOS code-review session
(question 3). Claude's reasons:
- Adjusting a long task part-way is a real need.
- Every change passes the same checks and approval as the plan did (D25).
- Finished steps are not computed again.

**Facts** (checked 2026-11-25). MatOS lets the model patch a workflow graph: add, update or delete a
node, add or remove an edge. Restricted fields are refused; the runtime computes the risk itself and
keeps the higher of the computed and the declared risk; a patch applies by itself only when that risk is
low and the workflow's approval mode is `bypass`, and is otherwise recorded as proposed
(`src/matos/workflows/dynamicPatch.ts:13-25, 175-189, 419-536`,
`src/matos/workflows/dynamicNodeRunner.ts:280-295, 453-491` @a50fd76; design only).

**Rejected.**
- *No change once approved*: the user would stop the run and make a new plan. The simplest, but awkward
  for long tasks.
- *Small changes apply by themselves*, as in MatOS. What counts as small is hard to define, and a
  rewired edge can bypass a check.

**Known costs.** Showing the difference between two plans, and continuing a run from the middle.

**Revisit if** revised plans come so often that approving each one slows work down.

## D43. Every calculation in a plan goes through AiiDA (2026-11-25)

**Decision.** Every calculation in a plan runs through AiiDA, so that AiiDA is the one record of what
was computed:
- DFT through the four codes' plugins (D22);
- MLIP calculations through aiida-mlip, which is built on janus-core (D41);
- analysis steps as AiiDA `calcfunction`s, which store their inputs and outputs in the provenance graph.

The AiiDA node's UUID is the one ID that links structures and results across steps, the GUI and
reports; D36's readable names are labels (added in the El Agente code-review session; Claude's proposal, to which the owner did not object).

Skill scripts (D29) and the side-analysis shell (D35) are not plan steps, and stay outside. The checks
of D9 read what AiiDA stored, such as exit status and outputs, and decide what happens next; how they
are written is for the plan.

**Reason.** The owner raised it (2026-11-25, translated from Chinese): "If all our calculations go
through AiiDA, AiiDA's own database stores this." Claude laid out three options and recommended this
one; the owner chose it and added: "For MLIP we want to use aiida-mlip." Claude's reasons:
- AiiDA becomes the one record of computation, which closes the rest of the Concern "Two records of a
  run".
- D39's caching then covers MLIP calculations too.
- aiida-mlip and janus-core come from the same team at STFC.

**Facts** (checked 2026-11-25):
- aiida-mlip (github.com/stfc/aiida-mlip) is BSD-3-Clause; v0.5.0 was released on 2026-09-17, and the
  repository was updated on 2026-11-18. Its features, marked "in development", cover MACE, M3GNet and
  CHGNet; single points, geometry optimisation and molecular dynamics (NVE, NVT, NPT); training and
  fine-tuning MACE; and MACE descriptors. It "relies heavily on janus-core". Phonons are not listed.
- AiiDA's `calcfunction` decorator "transforms a regular python function in a calculation process,
  which automatically stores the provenance of its output in the provenance graph" (AiiDA
  documentation, calculation concepts).

**Rejected.**
- *Only HPC calculations through AiiDA*, as before: two records, and MLIP results without provenance or
  caching.
- *MLIP through AiiDA, analysis outside*: analysis results would still lack provenance.

**Known costs.** aiida-mlip is in development; what it lacks, such as phonons, waits for it or is added
by us upstream. Short steps also go through AiiDA.

**Revisit if** aiida-mlip lacks what the five tasks need and cannot be extended in time, or AiiDA's
overhead makes short steps too slow.

**Overturns** nothing accepted. It extends D4 from HPC calculations to every calculation in a plan, and
closes the open half of the Concern "Two records of a run".

## D44. The agent may draft skills from verified runs; no draft applies by itself (2026-11-25)

**Decision.** After a run that passed all its checks, the agent may draft what it learned as a new skill
or as a change to one, with the run's research record (D36) as evidence. The draft is saved locally.
The user decides whether to keep it as a custom skill or to submit it to the marketplace, where it is
reviewed like any contribution (D40). No draft applies by itself, and none touches goldilocks-dft's
parameter rules, which change only through D16's rule studies.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the MatOS code-review session
(question 5). Claude's reasons:
- What a verified run learned is worth keeping; CASCADE keeps only what passed verification.
- Changes that applied by themselves would make the agent's behaviour drift between runs, so D7's and
  D38's evaluations could not be repeated, and users would not know why the agent changed.
- D40's review is reused, not a second process.

**Facts** (checked 2026-11-25, in the code review):
- CatMaster promotes self-evolved skill edits automatically by default, after an LLM reviewer approves
  (`catmaster/runtime/self_evolution/settings.py:9`, `catmaster/runtime/self_evolution/effective.py:259-300`
  @06b8568). MatOS's evolution defaults to automatic unless `MATOS_STANDALONE=1` is set
  (`evolutionApprovalPolicy.ts:64-67` @a50fd76).
- CASCADE saves a skill only after verification, storing the code but not the answer
  (`deep_solver_benchmark/single_question_runner.py:257-311` @e81d0e6). DFT Agent (Cui) gives each
  lesson a status (verified, candidate, rejected, deprecated) with evidence, and retrieves only verified
  ones (`src/vasp_slurm_agent/knowledge.py:22, 168-206, 267-315` @e447736).

**Rejected.**
- *No drafting by the agent.* What runs learn would be lost.
- *Improvements that apply by themselves*, as CatMaster and MatOS do by default. Behaviour would drift
  between runs, evaluations could not be repeated, and safety would suffer.

**Known costs.** A flow for drafting, reviewing and submitting skills.

**Revisit if** drafts are seldom useful, or reviewing them becomes a burden.

## D45. No LLM reviewer at run time in the first version (2026-11-25)

**Decision.** The first version has no LLM reviewer (critic) at run time. Code checks (D9) and the
user's approval (D25) are the safeguards. If a reviewer is considered later, it is first tried as an
extra arm in D38's evaluation.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the Paimon code-review session
(question 1). Claude's reasons:
- Paimon's critics helped when they ran on a stronger model than the executor.
- A local 27B model that reviews its own work tends to repeat its own mistakes.
- It keeps D32's principle: code decides, and an LLM at most advises.

**Facts** (checked 2026-11-25, in the code review). Paimon's critics gate job submission and task
completion (`paimon/src/paimon/world/critic.py:307-372, 375-453` @617e0b0); after a first pass, the
critic's ticket lets later submissions through unreviewed (`critic.py:316-319`). Its paper ran GPT-5
critics over a GPT-5-mini executor (paper-level). MASTER's LLM reviewer contradicted its own band test
in about 11% of verdicts.

**Rejected.**
- *The same local 27B model as reviewer*, which would tend to repeat the executor's mistakes.
- *An optional cloud reviewer* when the user supplies a key, advising only. Data would go to an outside
  service, and it costs money.

**Revisit if** evaluations (D38) show that a reviewer catches errors that the code checks miss.

## D46. Numbers in reports and cards come from data, and every number the model writes is checked (2026-11-25)

**Decision.**
1. Tables and key numbers in reports and cards are rendered by code from the research record (D36)
   and from AiiDA; the model writes only the prose around them.
2. Every number in the model's prose must trace to the research record or to AiiDA, with matching
   value and unit.
3. When a number does not trace, the model is given the list of mismatches and rewrites once. If a
   number still does not trace, it is marked visibly in the report.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the DFT Agent (Cui) code-review
session (question 5). Claude's reasons: a wrong number in a scientific report is costly; numbers that
code renders from data are the most reliable; and checking the prose catches what remains.

**Facts** (checked 2026-11-25, in the code review). DFT Agent (Cui) gates its explanations by evidence,
checking numbers against cited facts (`src/vasp_slurm_agent/explanation.py` @e4477364). aiida-agents
checks that numbers with units in a reply appear in tool output; it tightened the check after a "60 Ry"
claim passed because an unrelated identifier was 60, and it warns without withholding the answer
(`src/aiida_agents/grounding.py:130-148, 176-219` @28314e7).

**Rejected.**
- *Mark mismatches only, with no rewrite*: the user would fix the report by hand.
- *No check*: a wrong number could reach a paper or a report.

**Known costs.** A number checker that handles units and conversions.

**Revisit if** the checker flags too many correct numbers, for example after unit conversions, or misses
wrong ones.

## D47. Goldilocks never installs DFT codes; it registers the codes the user already has (2026-11-25)

**Decision.** Goldilocks never installs a DFT code, open-source ones included. It registers, as AiiDA
codes, the codes the user already has: a path on the local machine, or on an HPC system either the
`module load` commands that make a code available or its path. The set-up wizard of D21 records these.

**Reason.** Owner's call (2026-11-25), in the DFT Agent (Cui) code-review session (question 9),
translated from Chinese: "Never install; only record the local install path, or the module load method
on HPC, or the path on HPC." Claude had recommended not installing in the first version and leaving an
optional local install of open-source codes for later. No further reason recorded.

**Facts** (checked 2026-11-25):
- An AiiDA code records an executable path on a computer (`filepath_executable`) and can carry
  commands to run before it (`prepend_text`), for example `module load` lines (AiiDA documentation,
  "How to run external codes").
- In the code review, DFT Agent (Cui) installs open-source engines for the user, pinned, checked by hash
  and followed by a smoke run.

**Rejected.**
- *An optional local install of QE or CP2K from conda-forge*, pinned and smoke-tested, as Claude
  suggested for later.
- *Bundling open-source codes into the app or container*, which would carry GPL obligations and make
  the app larger.

**Revisit if** users who have neither HPC access nor a local install cannot use the agent at all.

## D48. The shipped app and container send no traces by default; users may opt in (2026-11-25)

**Decision.** The app and the container that users run send no traces to LangSmith or to any other
outside service by default. A user may turn tracing on in the settings. Our own evaluations use
LangSmith as D28 says.

**Reason.** Proposed by Claude, chosen by the owner (2026-11-25), in the El Agente code-review session
(question 9). Claude's reasons: users' research is often unpublished and must stay on their machines by
default; users who want to help can turn tracing on.

**Facts** (checked 2026-11-25):
- LangSmith tracing turns on through environment variables, such as `LANGSMITH_TRACING=true` with an
  API key (LangSmith documentation), so shipped builds must not set them.
- In the code review, El Agente's graphs capture every HTTP body (`instrument_httpx(capture_all=True)`)
  and export to a hosted service whenever a token is present (`mof_paper_mining/graph.py:26-28`;
  design only).

**Rejected.**
- *On by default, with a switch to turn it off*: users' unpublished data would leave their machines by
  default.
- *Never*: users who want to help could not.

**Revisit if** opt-in traces are too few to diagnose the problems users report.

**Overturns** nothing; it closes the Open item on traces from shipped builds.

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
  D29 decides where their code executes: a local sandbox. D5's amendment decides which sources are
  trusted: only Goldilocks's own and those the user adds.
- **"Similar results" needs a reference comparison.** Checking D7 means comparing the agent's results
  with the earlier study's: the funnel and the final picks. That is an evaluation of the product.
  v4-process D23 deferred evaluations of the agent configuration. The plan has to define this
  comparison and keep the reference data private. D28 runs it in LangSmith.
- **Evaluation data in LangSmith.** Under D28, D7's reference data and the traces of evaluation runs
  (structures, compounds, results) would be stored in LangSmith, a hosted service, unless LangSmith
  is self-hosted (an Enterprise add-on). The details of the unpublished study must stay private. The
  plan and the owner decide the region, what is uploaded, and whether the reference data stays local
  with only scores sent. LangSmith's API key is a credential, which agents never handle (v4-process
  D21). Arm 4 of D38 also sends task data to a frontier model's service.
- **Two records of a run.** Under D9, LangGraph checkpoints hold the subgraph's state, and AiiDA holds
  the provenance of HPC calculations. MLIP and analysis steps run in the subgraph are not in AiiDA's
  provenance unless they are run through AiiDA as well. D17 answers how a subgraph waits for an AiiDA
  job without polling, and its amendment answers which record counts for HPC jobs: AiiDA. D43 closes
  the rest: every calculation in a plan goes through AiiDA.
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
  someone; who holds it is not known. Early internal builds may be signed ad hoc; the public release is
  signed with a Developer ID and notarised (added in the DFT Agent (Cui) code-review session; Claude's proposal, to which the owner did not object).
- **AiiDA without RabbitMQ.** D17 relies on AiiDA's broadcasts. Whether they work the same with the
  built-in ZeroMQ broker (D20) has to be checked before the watcher is built.
- **Resuming a composed plan.** After a restart (D17), the executor must run exactly the plan that
  was approved. It can rebuild the graph from the stored plan, or be one fixed graph that reads the
  plan from its state. Which of the two is for the plan to decide.
- **The submission key must reach AiiDA with the job.** D17's catch-up treats "no job with this key
  in AiiDA" as "never submitted". That holds only if the key is stored at the moment the job is
  created, not in a later step. How to do this through each plugin's builder has to be checked before
  the watcher is built.
- **What D18's cross-repository record must carry**, collected so far (2026-11-25): the rename to
  goldilocks-dft and its new ddmms repository; goldilocks-ml's merge into it; parameters and inputs for
  the four codes of D22, each value from one of four sources (ML, heuristics, the human, the LLM), with
  LLM values for the functional and the pseudopotential table as in junwen94/goldilocks-core#258; human
  values validated for all four codes, with a warning below the recommendation (D26); every setting the
  four codes need, since nothing else may enter an input (D37); pinned pseudopotential manifests with
  checksums and provenance, a method signature on every result so that results with different
  signatures are never compared directly, Hubbard U values labelled by code and projector, and magnetic
  moment units for each code (matsim-agents code-review session); and, later, offering its rules to the
  AiiDA ecosystem in a general form (owner's choice in the aiida-agents code-review session).
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
  container and a macOS app. The plan starts by reading CatMaster's code and borrowing what fits as
  design; no code is copied (D23). Every surveyed agent's code is reviewed with the owner, one system
  at a time (2026-11-25). Borrow and Avoid items that no question covers go to the plan as candidates; the plan
  states which it uses, which it does not, and why (owner's choice, 2026-11-25).

## Open

The code-review sessions are under way, one surveyed agent at a time (from 2026-11-25). Their
decisions are added here as new decisions, or as amendments that say what they change.

- The skills marketplace's design (D40), item by item: how contributions are checked and reviewed;
  levels of trust (for example official, community and custom); what each skill declares it needs
  (GPU, network, licensed codes, API keys); how installed skills are pinned and updated; whether
  official skills ship with the app; which skills come first.
- Whether MCP servers and plugins join tools and skills, in the GUI (D30) and for the agent. D10
  rejected MCP for third-party tools, as part of the "Tiers" option; the owner asked on 2026-11-25 to
  consider it again. An MCP server is a separate program, so D29's question of where code runs would
  apply to it too. A related question, from the aiida-agents session: whether this repository's own
  tools, such as the AiiDA tools, are offered read-only over MCP to other clients, as aiida-agents
  does.
