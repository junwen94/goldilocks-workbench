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

## Concerns

- **SCARF credentials for a network deployment of Ada.** SCARF's terms treat access under someone
  else's identity as a Computer Misuse Act matter, so one shared account cannot submit for everyone
  (agent design doc, section 20.1, branch `docs/ada-version`). If Ada runs as a shared network
  service, it would need each user's own SCARF credentials. That runs against v4-process D21: agents
  never handle credentials. Ada's deployment decision has to settle this.

## Open

From the intent, still to decide one at a time:

- Which framework do chat and Ada use? (Owner: not yet known.) Both are now light forms (D2): can
  they share one light agent? The owner's concern (2026-11-25): chat keeps steps that need the user,
  such as choosing a structure from search results to import, confirming, and editing.
- How is goldilocks-Ada deployed? (Owner: a network deployment, with the solution to be decided. Ada
  is not urgent.)
- What does "a real materials science agent" need, concretely? Which long tasks should it handle,
  what does it plan, what does it check, and how does it reach HPC?
- What is carried over from `stfc/goldilocks-agent` (frontend, tools, tests, deployment), and what is
  rewritten?
- How does the live website move from the old agent to goldilocks-chat without breaking it for users?
- Which models does each form use?
- Does any of this need changes in `goldilocks-core`? If so, that part gets its own cross-repository
  record in `ddmms/goldilocks` (v4-process D1).
