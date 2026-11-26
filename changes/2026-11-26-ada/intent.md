# Intent: goldilocks-Ada, built now

Author: Junwen Yin (owner), written down with Claude. Size: large (v4-process D8). Status: draft.
Date: 2026-11-26.
Source: none (v4-process D13).

## In the owner's words

The owner, after PR 1 of `changes/2026-11-25-workbench/plan.md` (#3) had merged and its PR 2 (#4) was open:

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
  goldilocks-chat, and the import boundary that the plan's PR 2 added (#4, merged on 2026-11-26) fails when a
  package imports a form it does not depend on (`tools/checks/import_boundary.py`). Ada could not use the light
  agent where it is planned.
- **Structure Builder is planned for the agent only.** The plan's module table lists the agent as the only
  form with Structure Builder, and M18 gives chat Find in Databases and DFT. D12 limits only MLIP and AiiDA
  to the agent, and D15 does not name the forms.
- **D2's reason for the light form may no longer hold.** D2 rejected goldilocks-agent installed in an Ada
  Workspace because "Ada is a network deployment with limited resources, which suits a light form". The owner
  now says that Ada "in essence creates a VM for each user, so in fact it is not shared". D2's revisit clause
  names only long tasks, so it does not cover this. The spec checks D2's choice of a light form; it does not
  inherit it.
- **SCARF credentials are an open concern.** The workbench spec's Concerns: SCARF's terms forbid one
  shared account submitting for everyone, so a shared network deployment of Ada would need each user's own
  SCARF credentials, while v4-process D21 says agents never handle credentials. Ada's deployment decision
  has to settle this (D19).
- **The repository is empty of features.** The plan's PR 2 (#4) added three empty packages (goldilocks-workbench,
  goldilocks-chat, goldilocks-agent), two blank web apps and the full check. M1 (registry and tool
  contract), M2 (model layer, server kit, store), M3 (shared tools) and M4 (frontend foundation) come
  next; the agent's core is M5 to M9.
- **Building Ada now changes the plan's order and risk 4.** The plan's owner decision 1 is "goldilocks-agent
  first, goldilocks-chat after", and the light agent is built in M18, after the agent's core (M2 builds only
  D3's card contract). Risk 4, scope for one maintainer, lists "agent first" and the "Not in the first version"
  list, which names goldilocks-Ada, among its mitigations. Building Ada after M1 to M4 and before M5 to M9
  removes those two mitigations, and brings the light agent ahead of the agent's core, which changes owner
  decision 1 in part. Why Ada goes before the agent's core: no reason recorded.

## Proposed outcome

- **goldilocks-Ada is built in the first version**, after M1 to M4 and before M5 to M9 (owner). It starts
  from the light form of D2: chat that can reach SCARF, sharing the light agent with chat (D3). The spec checks
  that choice (see Problem).
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
- **Accepted records** in `changes/2026-11-25-workbench/`: D2's last sentence (and its choice of a light
  form, if the spec overturns it), D11's line on Ada's model and D19 in the spec; the plan's scope, package and
  module tables, order of work, owner decision 1 in part, and risk 4's mitigations.
- **Users**: STFC's internal users on Ada (D2); users of goldilocks-chat, who gain Structure Builder.
- **Interfaces**: Ada's server and command line (new external contracts); SCARF's scheduler, a new
  execution target outside AiiDA while Ada is a light form; goldilocks-dft over HTTP from Ada.
- **ddmms/goldilocks**: details of Ada's deployment that are not public stay there (`AGENTS.md`, rule 8).

## Constraints

- While Ada is a light form (see Problem): no Deep Agents loop and not goldilocks-agent installed on Ada
  (D2); one light agent shared with chat (D3); no shell (D35); Ada never imports agent code, Deep Agents,
  AiiDA or MLIP packages (`AGENTS.md` rule 4, extended).
- `AGENTS.md`: no native input files and every DFT setting through goldilocks-dft (rule 6); goldilocks-dft
  over HTTP only (rule 7); nothing private (rule 8).
- v4-process D21: the code never reads, stores or prints SCARF credentials.
- SCARF's terms: no shared account submits for everyone (workbench spec, Concerns).
- Order (owner): after M1 to M4, before M5 to M9.
- One maintainer (workbench plan, risk 4), with two of its mitigations removed (see Problem).

## Out of scope

None stated by the owner.

## Open questions

- **Whether Ada stays a light form**, or becomes goldilocks-agent on each user's VM, the option D2 rejected
  (see Problem). As a light form, Ada sends jobs straight to SCARF's scheduler, outside AiiDA (D12: AiiDA
  only in the agent); as goldilocks-agent, its jobs would go through AiiDA (D4).
- **How a user's Ada VM reaches SCARF**: scheduler commands run directly, or SSH with the session's own
  configuration; whether uv and Python can be installed; how a web app is exposed to the user; whether the
  model endpoint and goldilocks-dft can be reached. Only someone with an Ada login can check this.
- **Shared service or one instance per user** (owner: "not very clear at the moment"), and what that
  means for SCARF credentials.
- **Ada's model** (D11 left it to when Ada is built).
- **Where goldilocks-dft runs for Ada**: inside each VM, or as a service Ada reaches.
- **How Ada reads the results it fetches**: which parser, and through which package.
- **Size limits for Structure Builder** on the shared chat instance (supercells, slabs, interfaces).
- **Where the light agent lives**, so that chat and Ada can share it.
