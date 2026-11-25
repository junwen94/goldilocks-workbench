# Intent: Goldilocks Workbench in three forms, with the agent on Deep Agents

Author: Junwen Yin (owner), written down with Claude. Size: large (D8). Status: draft.
Date: 2026-11-25.
Source: none (D13).

## In the owner's words

> "Next we build goldilocks-workbench. Its predecessor is goldilocks-agent. The main change in the
> new version is that we provide three forms: goldilocks-chat (the old web edition), goldilocks-agent
> (the old local edition) and goldilocks-Ada (which did not exist before). We also move to Deep Agents
> to replace LangGraph. The agent form uses Deep Agents; for chat and Ada we do not know yet."

Claude asked what the owner wants Deep Agents to bring:

> "I want it to become a real materials science agent. I mean that in contrast to the web edition:
> the web edition does not suit long tasks or connecting to HPC. It only suits light computation and
> conversation. That is also why I position the new website as chat."

(Translated from Chinese by Claude. Content on GitHub is in English only, at the owner's request.)

The owner agreed that this change is large and that its records live in this repository.

## Problem

Checked on 2026-11-25, on `stfc/goldilocks-agent` main (`ea757c7`) unless noted:

- **One hand-built graph serves both editions.** `src/goldilocks_agent/graph.py` (581 lines) builds a
  LangGraph `StateGraph` with an `llm` node and a `tool` node joined by conditional edges.
  `src/goldilocks_agent/agent_profile.py` (stfc/goldilocks-agent#151, following the owner's
  2026-11-16 direction) sets three things for each deployment: which tools the model is offered, the
  system prompt, and how far one turn may go. The two deployments are the website's chatbot, with a
  few tool calls a turn, and the local agent, with more tools and a longer turn.
- **The local agent's own loop does not exist yet.** The profile's comment says that the local agent's
  planning and its checking of results "comes with its loop".
- **The web edition is a chatbot.** The shared instance at workbench.goldilocks.ac.uk (STFC Cloud)
  changes Tool parameters from what the user says. It does not connect to HPC. The owner judges that
  it does not suit long tasks or HPC, and suits light computation and conversation.
- **The Ada edition was decided on 2026-11-24, with no code.** Ada (ada.stfc.ac.uk) is STFC's
  Workspace platform for ISIS, Diamond and CLF users, formerly IDAaaS. The agent would run as the user,
  in the user's own Ada Workspace. It would use the user's SSH key to submit core's bundle and
  `submit.sh` to SCARF through Slurm, without AiiDA. How it is installed on Ada, and which model it
  uses, were not decided. Sources: the OneDrive `1-docs/README.md` (2026-11-24 entry), and section 20
  of the agent design doc on branch `docs/ada-version` (`1b21109`), which has no PR and is not on
  main.
- **The stack today** is `langgraph>=1.0`, `langgraph-checkpoint-sqlite` and `langchain-core>=1.0`.
- **Deep Agents runs on LangGraph.** The Deep Agents documentation
  (docs.langchain.com/oss/python/deepagents/overview, read 2026-11-25) says: "deepagents is a
  standalone library built on top of LangChain's core building blocks for agents. It uses the
  LangGraph runtime for durable execution, streaming, human-in-the-loop, and other features." It adds
  planning, a virtual filesystem, subagents and long-term memory. Moving to it replaces the hand-built
  graph. The LangGraph runtime stays.
- **This repository**, `ddmms/goldilocks-workbench`, is public, was created on 2026-10-07, and holds
  only a README. It has no `AGENTS.md`, `REVIEW.md` or `check` yet.
- **The `stfc` repositories will be retired** (v4-process premise, 2026-11-25), so the agent's
  successor is built here.

## Proposed outcome

Goldilocks Workbench comes in three forms:

- **goldilocks-chat**, the website. It handles conversation and light computation. It succeeds the
  web edition.
- **goldilocks-agent**, a real materials science agent built on Deep Agents. It takes on long tasks
  and connects to HPC. It succeeds the local edition.
- **goldilocks-Ada**, a new form for STFC's Ada platform.

## Affected

- This repository, the new home of all three forms.
- `stfc/goldilocks-agent`, the predecessor. It retires, and its code, tests and deployment are the
  starting point.
- Users of workbench.goldilocks.ac.uk.
- `goldilocks-core`, which the agent uses for calculation parameters and bundles. Whether core has
  to change is not yet known.
- The shared deployment on STFC Cloud. Its private details live in `ddmms/goldilocks` (D12).

## Constraints

- The agent form uses Deep Agents (owner, 2026-11-25).
- The V4 process applies. Records live in this repository (D1). This repository is public, so
  deployment details and anything else private go in `ddmms/goldilocks` (D12).
- A change to the physics values users get is high-risk, category 1 (D17).

## Out of scope

None stated by the owner.

## Open questions

The spec takes these one at a time.

- Do the three forms live in one repository, or in several? What do they share: tools, the core
  client, the frontend?
- Which framework do chat and Ada use? (Owner: not yet known.)
- What does "a real materials science agent" need, concretely? Which long tasks should it handle,
  what does it plan, what does it check, and how does it reach HPC?
- How does goldilocks-Ada differ from goldilocks-agent, given that both reach HPC?
- What is carried over from `stfc/goldilocks-agent` (frontend, tools, tests, deployment), and what is
  rewritten?
- How does the live website move from the old agent to goldilocks-chat without breaking it for users?
- Which models does each form use?
- Does any of this need changes in `goldilocks-core`? If so, that part gets its own cross-repository
  record in `ddmms/goldilocks` (D1).
