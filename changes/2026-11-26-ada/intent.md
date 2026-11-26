# Intent: goldilocks-Ada, built now

Author: Junwen Yin (owner), written down with Claude. Size: large (D8). Status: draft.
Date: 2026-11-26.
Source: none (D13).

## In the owner's words

The owner, after PR 3 of `changes/2026-11-25-workbench/plan.md` had merged and PR 4 was open:

> "Since we have already started writing code, can we first use `/engineering:system-design` to plan the
> packages' architecture as a whole? Also, I want to change one design: build the goldilocks-Ada part now as well,
> and change it later if there are problems. Do you agree with my idea?"

Claude agreed to the system design, and proposed building Ada's skeleton now but holding its SCARF
features until the SCARF-credentials concern of the workbench spec was settled. The owner answered:

> "The Ada version will be deployed on Ada. Once a user logs in to Ada, the ability to connect to SCARF
> comes built in, so we need not worry too much. Even if there are problems, we can change things when
> the time comes."

Claude then presented a system design and asked three questions: where Ada goes in the order of work,
which tools Ada offers besides SCARF, and whether Ada runs once per user or as a shared service. The owner
answered:

> "1. Ada's features go after the shared foundation (M1 to M4) and before the agent's core (M5 to M9).
> 2. Add Structure Builder; chat should also get Structure Builder.
> 3. Ada is a shared service deployed on Ada, but the Ada system in essence creates a VM for each user, so
> in fact it is not shared. This point is rather complicated and not very clear at the moment; let's go
> ahead with it and change it later if we find it is wrong."

(Translated from Chinese by Claude. Content on GitHub is in English only, at the owner's request.)

## Problem

Checked on 2026-11-26, in this repository unless noted:

- **Ada is not built in the first version.** The workbench spec (accepted) decides that goldilocks-Ada is
  its own light form, "chat that can reach SCARF", with tools to submit a job to SCARF, poll it and fetch
  its results, and no Deep Agents planning loop; and that "Ada is not built now (owner, 2026-11-25)"
  (`changes/2026-11-25-workbench/spec.md`, D2). Its deployment is decided when Ada is built (D19), and so
  is its model (D11). The accepted plan lists "goldilocks-Ada is not built (D2, D19)" under "What the first
  version is", and goldilocks-Ada under "Not in the first version" (`changes/2026-11-25-workbench/plan.md`).
- **The light agent sits in goldilocks-chat.** D3 decides that chat and Ada share one light agent built
  with LangChain's `create_agent`. The plan's package table places "light agent, chat server" in
  goldilocks-chat, and the import boundary of PR 4 (open on 2026-11-26) fails when one form imports
  another. Ada could not use the light agent where it is planned.
- **Structure Builder is planned for the agent only.** The plan's module table lists the agent as the only
  form with Structure Builder, and M18 gives chat Find in Databases and DFT. D12 limits only MLIP and AiiDA
  to the agent, and D15 does not name the forms.
- **SCARF credentials are an open concern.** The workbench spec's Concerns: SCARF's terms forbid one
  shared account submitting for everyone, so a shared network deployment of Ada would need each user's own
  SCARF credentials, while v4-process D21 says agents never handle credentials. Ada's deployment decision
  has to settle this (D19).
- **The repository is empty of features.** PR 4 adds three empty packages (goldilocks-workbench,
  goldilocks-chat, goldilocks-agent), two blank web apps and the full check. M1 (registry and tool
  contract), M2 (model layer, server kit, store), M3 (shared tools) and M4 (frontend foundation) come
  next; the agent's core is M5 to M9.

## Proposed outcome

- **goldilocks-Ada is built in the first version**, after M1 to M4 and before M5 to M9 (owner). It stays
  the light form of D2: chat that can reach SCARF, sharing the light agent with chat (D3).
- **Ada runs on the Ada platform**, which creates a VM for each user (owner), and reaches SCARF with the
  logged-in user's own access, which Ada provides (owner).
- **Ada's tools**: Find in Databases, DFT, Structure Builder, and SCARF jobs (submit, status, fetch).
- **chat also offers Structure Builder** (owner).
- **The packages' architecture is planned as a whole first** (owner), so that the three forms divide
  cleanly before features arrive.
- **Where Ada turns out to work differently, the design changes then** (owner).

## Affected

- **This repository**: a fourth package, goldilocks-ada; a third web app; the shared part (the light
  agent); chat's profile (Structure Builder); the import boundary and an environment check for Ada; CI;
  `AGENTS.md` rule 4 (chat's limits, to cover Ada); `REVIEW.md`'s high-risk paths.
- **Accepted records** in `changes/2026-11-25-workbench/`: D2's last sentence, D11's line on Ada's model and
  D19 in the spec; the plan's scope, package and module tables, and order of work.
- **Users**: STFC's internal users on Ada (D2); users of goldilocks-chat, who gain Structure Builder.
- **Interfaces**: Ada's server and command line (new external contracts); SCARF's scheduler, a new
  execution target outside AiiDA; goldilocks-dft over HTTP from Ada.
- **ddmms/goldilocks**: details of Ada's deployment that are not public stay there (`AGENTS.md`, rule 8).

## Constraints

- The rest of D2 stands: a light form, no Deep Agents loop, not goldilocks-agent installed on Ada.
- D3: one light agent shared with chat. D35: Ada has no shell.
- `AGENTS.md`: Ada never imports agent code, Deep Agents, AiiDA or MLIP packages (rule 4, extended); no
  native input files and every DFT setting through goldilocks-dft (rule 6); goldilocks-dft over HTTP only
  (rule 7); nothing private (rule 8).
- v4-process D21: the code never reads, stores or prints SCARF credentials.
- SCARF's terms: no shared account submits for everyone (workbench spec, Concerns).
- Order (owner): after M1 to M4, before M5 to M9.
- One maintainer (workbench plan, risk 4).

## Out of scope

None stated by the owner.

## Open questions

- **How a user's Ada VM reaches SCARF**: scheduler commands run directly, or SSH with the session's own
  configuration; whether uv and Python can be installed; how a web app is exposed to the user; whether the
  model endpoint and goldilocks-dft can be reached. Only someone with an Ada login can check this.
- **Shared service or one instance per user** (owner: "not very clear at the moment"), and what that
  means for SCARF credentials.
- **Ada's model** (D11 left it to when Ada is built).
- **Where goldilocks-dft runs for Ada**: inside each VM, or as a service Ada reaches.
- **Whether Ada's jobs go through AiiDA**, or straight to SCARF's scheduler.
- **How Ada reads the results it fetches**: which parser, and through which package.
- **Size limits for Structure Builder** on the shared chat instance (supercells, slabs, interfaces).
- **Where the light agent lives**, so that chat and Ada can share it.
