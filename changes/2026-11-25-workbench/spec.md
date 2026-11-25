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

## D2. goldilocks-Ada is a light form of its own, not the agent (2026-11-25)

**Decision.** goldilocks-Ada is its own light form, close to goldilocks-chat. It adds tools to submit
a job to SCARF, poll it and fetch its results, but has no Deep Agents planning loop. It is not
goldilocks-agent installed in an Ada Workspace. Where it runs does not change from 2026-11-24: in the
user's own Ada Workspace, with the user's own SSH key, because SCARF's terms do not allow one shared
account to submit for everyone.

**Reason.** Owner's call (2026-11-25); no reason recorded.

**Rejected.** *goldilocks-Ada as goldilocks-agent installed in an Ada Workspace*, with the HPC
connection as a replaceable executor: AiiDA for the local agent, SSH and Slurm for Ada. Claude
recommended it. The agent would have one codebase, Ada users could run long tasks on SCARF, and Ada's
framework would follow (Deep Agents). The owner did not choose it; no reason recorded.

**Revisit if** Ada users need long tasks: work on SCARF that spans several jobs and needs planning, or
checking results between jobs.

**Overturns**, in part, section 20.2 of the agent design doc (`stfc/goldilocks-agent`, branch
`docs/ada-version`, `1b21109`, not on main). That section is the agent session's 2026-11-24 proposal,
recorded at the owner's request. It treated the Ada edition as the local edition with a different way
of executing jobs. Where Ada runs, and that it uses the user's own key, are unchanged.

## Concerns

None yet.

## Open

From the intent, still to decide one at a time:

- Which framework do chat and Ada use? (Owner: not yet known.) Both are now light forms (D2): can
  they share one light agent?
- What does "a real materials science agent" need, concretely? Which long tasks should it handle,
  what does it plan, what does it check, and how does it reach HPC?
- What is carried over from `stfc/goldilocks-agent` (frontend, tools, tests, deployment), and what is
  rewritten?
- How does the live website move from the old agent to goldilocks-chat without breaking it for users?
- Which models does each form use?
- Does any of this need changes in `goldilocks-core`? If so, that part gets its own cross-repository
  record in `ddmms/goldilocks` (v4-process D1).
