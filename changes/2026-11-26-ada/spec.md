# Spec: goldilocks-Ada, built now
Superseded by changes/2026-11-26-ada/plan.md

From: `intent.md` (same folder). Status: in progress; accepted when its PR merges. Eight decisions come
from the system-design session of 2026-11-26: the owner chose ada D1, ada D2 and ada D6; Claude proposed
ada D3 to ada D5, ada D7 and ada D8 in a design the owner read before answering, and the owner did not
object to them. Claude proposed ada D9 after the review of #5 and ada D10 after the review of #6; the
owner confirmed both after the review of #6, and chose ada D11 then.

Supersedes: changes/2026-11-25-workbench/spec.md

That spec stands except where a decision below says it overturns part of it: in D2, the sentence on how
Ada is deployed (ada D2) and the last sentence (ada D1); and D19 (ada D2). In this spec, "ada D*n*" is a
decision below; a bare "D*n*" is a decision of the workbench spec, as everywhere in this repository
(`AGENTS.md`).

Only large changes (v4-process D8) have a spec. Each decision uses the five parts below. Where the owner gave no
reason, say so; do not supply one.

## D1. goldilocks-Ada is built in the first version, after M1 to M4 and before M5 to M9 (2026-11-26)

**Decision.** goldilocks-Ada is part of the first version. Its work comes after the shared foundation
(the workbench plan's M1 to M4) and before the agent's core (M5 to M9). Ada stays the light form of D2
(checked in ada D9): chat that can reach SCARF, with no Deep Agents loop. The light agent that chat and
Ada share (D3, ada D3) is built with Ada, and chat's milestone (M18) reuses it.

**Reason.** Owner's call (2026-11-26): "build the goldilocks-Ada part now as well, and change it later if
there are problems", and "Ada's features go after the shared foundation (M1 to M4) and before the agent's
core (M5 to M9)". (Translated from Chinese by Claude.) No further reason recorded.

**Rejected.**
- *Ada's skeleton now, its SCARF features after the SCARF-credentials concern is settled.* Claude
  proposed it. The owner answered that Ada gives each logged-in user SCARF access, "so we need not worry
  too much" (translated from Chinese by Claude); see ada D2.
- *Ada after the agent's core.* Claude offered it as the other order; the owner chose this one.

**Revisit if** Ada's work stalls on facts about the Ada platform (the spike of ada D2) while the agent's
core could go ahead.

**Overturns** D2's last sentence, "Ada is not built now (owner, 2026-11-25)"; and, in the workbench plan
(which may still change), item 3 of "What the first version is", goldilocks-Ada under "Not in the first
version", the order of work, and in part owner decision 1, "goldilocks-agent first, goldilocks-chat after":
the light agent, planned for M18, now comes before the agent's core. It also removes two of the plan's
risk 4 mitigations, "agent first" and the "Not in the first version" list (see Concerns).

## D2. Ada runs on the Ada platform, one VM per user, with the user's own SCARF access (2026-11-26)

**Decision.**
1. goldilocks-Ada is deployed on STFC's Ada platform. Ada creates a VM for each user, so each user's
   goldilocks-Ada runs in that user's own VM and reaches SCARF with the access Ada gives the logged-in
   user. The design assumes one instance per user VM, serving only that user.
2. The code never reads, stores or prints SCARF credentials (v4-process D21). It uses the access the VM
   already has, through the transport of ada D5.
3. Before Ada's SCARF features are built, a spike on the Ada platform checks this assumption and what a
   VM can reach (the plan defines it). It needs an Ada login, so the owner runs it.

**Reason.** Owner's call (2026-11-26): "The Ada version will be deployed on Ada. Once a user logs in to
Ada, the ability to connect to SCARF comes built in, so we need not worry too much"; and "Ada is a shared
service deployed on Ada, but the Ada system in essence creates a VM for each user, so in fact it is not
shared. This point is rather complicated and not very clear at the moment; let's go ahead with it and
change it later if we find it is wrong." (Translated from Chinese by Claude.)

Claude's note, not the owner's reason: with one instance per user VM, no shared account submits for
everyone, which is what the workbench spec's SCARF-credentials concern requires.

**Rejected.** *Settling D19's deployment question in full before building.* Claude proposed it; the owner
chose to go ahead and change the design if it proves wrong.

**Revisit if** the spike or later use shows that one goldilocks-Ada instance serves several users, or that
SCARF is reached through anything other than the logged-in user's own access. The SCARF-credentials
concern then applies again, and Ada's SCARF features stop until it is settled.

**Overturns** D2's fourth sentence, "How it is deployed is not decided: the owner says it is a network
deployment, with the solution to be decided", and the same point at the end of D2's Overturns part
("where it runs is open"); and D19, "How goldilocks-Ada is deployed is decided when Ada is built, not in
this change". How Ada is deployed is decided here, as an assumption to check.

## D3. The light agent lives in goldilocks-workbench, shared by chat and Ada (2026-11-26)

**Decision.** The light agent of D3 is a factory in the shared package,
`goldilocks_workbench/light_agent/`. Given a form's profile (its tool modules and prompt), it returns
LangChain's `create_agent` with the shared middleware: limits on calls per turn, human-in-the-loop, the
checkpointer and the fixes carried from the predecessor. chat and Ada each supply their profile, their
server configuration and what only they need. goldilocks-workbench gains `langchain` as a dependency.

**Reason.** Proposed by Claude in the system-design session (2026-11-26); the owner did not object.
Claude's reasons:
- D3 says chat and Ada share one light agent, and D1 puts what the forms share in the shared part.
- It needs no new package. The carried fixes and the checkpointer are already planned for the shared
  part (M2); the call limits and human-in-the-loop, which the plan puts in goldilocks-chat (M18), move
  into the factory.
- `langchain` is already in the agent's environment through deepagents, and chat needs it anyway.

**Rejected.**
- *A separate package for the light agent.* The line would be cleaner, but it is one more package to
  maintain for one factory.
- *Ada depending on goldilocks-chat.* Least code, but one form would import another, and chat's own parts
  (the anonymous owner key, retention) would come along.

**Revisit if** the light agent grows beyond the factory and its middleware, or the shared package becomes
too heavy for Ada's VMs.

**Overturns** the workbench plan's package table, which puts the light agent in goldilocks-chat.

## D4. Ada sends jobs to SCARF through its scheduler, not through AiiDA (2026-11-26)

**Decision.** Ada's scheduler module (ada D5) submits, queries and fetches through SCARF's Slurm
scheduler directly. goldilocks-Ada installs no AiiDA. Its job records (key, scheduler job ID, state,
remote folder, digest of the inputs) live in Ada's store.

**Reason.** Proposed by Claude in the system-design session (2026-11-26); the owner did not object.
Claude's reasons:
- Ada is a light form (D2, ada D9). AiiDA would put a database, a daemon and a broker in each user's VM.
- The AiiDA module lives in goldilocks-agent, so Ada would have to depend on the agent.
- D43 asks for AiiDA for every calculation in a plan; Ada has no plans.

**Rejected.** *AiiDA, with SCARF as a computer.* Provenance and caching would match the agent's, but it is
heavy, and Ada would depend on goldilocks-agent.

**Revisit if** Ada's users need provenance or caching across jobs, or long tasks (ada D9's revisit
clause).

## D5. Ada's scheduler module runs fixed commands only, and each submission is approved (2026-11-26)

**Decision.**
1. **One module, `slurm`, in goldilocks-ada**, with SCARF as its one site. The site's settings
   (partitions, limits, module names) are data taken from SCARF's public documentation.
2. **No shell (D35, ada D10).** The module runs only fixed programs: `sbatch`, `squeue`, `sacct`,
   `scancel` and a file-transfer program. Code builds their arguments from typed inputs, and no text the
   model writes becomes part of a command. On the VM itself nothing runs through a shell. Over SSH one
   cannot be avoided: sshd runs the command with the remote user's login shell, and a file transfer may
   pass remote paths through it too. So, on either transport, every argument and remote path is checked
   against a short list of allowed characters (letters, digits and `-_./=:,`) before it runs, and anything
   else is refused. A test runs both transports with arguments that carry shell metacharacters.
3. **A transport interface** hides how the VM reaches SCARF: commands on the VM itself, or SSH with the
   VM's own configuration. The spike of ada D2 decides which. The code never opens key files.
4. **Remote files** stay in one folder per task under the user's SCARF work area.
5. **What is submitted** is goldilocks-dft's bundle, with the site's scheduler options. This repository
   writes no native input file (`AGENTS.md`, rule 6).
6. **Approval.** Each submission needs the user's approval on a card that shows the resources it asks
   for. Each session has caps on jobs and core-hours, in the manner of D25. Cancelling a job is
   destructive and approved each time (D10).
7. **No double submission.** A submission is written to the store, with a key, before the scheduler is
   called. The job's name carries the key, and the scheduler's job ID is written as soon as `sbatch`
   returns it. After a restart, the records are reconciled, so a retry never submits twice:
   - a record with a job ID, with `sacct -j <job ID>`, which searches all of the accounting history when
     `-j` is given without `-S`;
   - a record without one (the scheduler was called, but its answer was lost), by name: with `squeue`
     for queued and running jobs, and with `sacct -S <time the record was written>` for finished ones;
   - a record that neither finds counts as never submitted, and may be submitted again, only if both
     queries succeeded and the record is younger than SCARF's accounting retention. Otherwise it is
     "needs check", as in the workbench plan's S3, and is not submitted again without the user.

   `scontrol show job` is not used to reconcile: Slurm drops a finished job from it after `MinJobAge`
   (300 seconds by default).
8. **Waiting is never a tool** (hook 14). A light poller in Ada's server updates job states and shows a
   card when a job ends. The status tool only reads.

**Reason.** Proposed by Claude in the system-design session (2026-11-26); the owner did not object.
Item 2's rule for SSH and item 7's reconciliation were revised after the review of #6, item 7 after the
owner asked why jobs are not looked up by job ID; the owner agreed to both (2026-11-26). Claude's reasons:
- D35 and ada D10 forbid a shell in Ada, so no command may come from the model.
- Over SSH, a list of allowed characters holds whatever the remote login shell is; quoting would depend
  on that shell's rules.
- D10 makes approval follow a tool's side-effect class, and D25 approves HPC jobs once per plan, within
  caps checked in code. Ada has no plans, so each submission is approved instead, with caps per session
  in D25's manner.
- The key and the reconciliation follow the design of the workbench plan's M8 for submitting without
  duplicates.
- The job ID finds a job on any day; the name is needed only when the answer to `sbatch` was lost.
  `sacct` searches only from midnight of the current day when it is given neither `-j` nor `-S`, so a
  lookup by name always gives `-S`. Slurm's documentation (`sacct`, "Default time window"; `slurm.conf`,
  `MinJobAge`) states both defaults.
- A module for Slurm with SCARF as data costs the same as a SCARF-only module, and a second cluster would
  need no rename.

**Rejected.**
- *A module named for SCARF.* The same cost, but another cluster would mean renaming it.
- *A tool with which the model waits or polls in a loop.* It spends a small model's calls on waiting and
  breaks hook 14.
- *A general command tool, limited by the prompt.* That is the shell D35 and ada D10 rule out for chat
  and Ada.
- *Quoting each argument for the remote shell instead of limiting characters.* Any argument would pass,
  but quoting rules differ between login shells (bash, tcsh), and the arguments the module builds
  (scheduler options, job names, paths in the work area) should need no other characters.

**Revisit if** the spike shows that a VM reaches SCARF in a way the transport interface does not cover,
users need jobs that one bundle cannot describe, or an argument needs a character outside item 2's list.

## D6. chat and Ada offer Structure Builder too (2026-11-26)

**Decision.** goldilocks-chat and goldilocks-Ada offer Structure Builder (D15), as goldilocks-agent does.
On the shared chat instance it runs within size limits (atoms per structure, supercell size) that the
plan sets, so that one user cannot take over the instance. Magnetic orderings still come from
goldilocks-dft (D15).

**Reason.** Owner's call (2026-11-26): "Add Structure Builder; chat should also get Structure Builder."
(Translated from Chinese by Claude.) No reason recorded. The size limits are Claude's addition; the owner
confirmed them after the review of #6 (2026-11-26), with no reason recorded.

**Rejected.** None was discussed.

**Revisit if** users of the shared instance often reach the size limits, or Structure Builder's load slows
the shared instance.

**Overturns** the workbench plan's module table, which gives Structure Builder to the agent only, and
M18's chat profile (Find in Databases and DFT).

## D7. A third web app, built from the shared frontend packages (2026-11-26)

**Decision.** goldilocks-Ada has its own app, `frontend/apps/ada`, built from the shared UI, type and
module packages that M4 creates. The scheduler module's panel (the job list) and cards (job submitted,
job finished) join the module packages.

**Reason.** Proposed by Claude in the system-design session (2026-11-26); the owner did not object.
Claude's reasons: each app is a shell with its profile's modules, and D12 gives every tool a panel and
cards.

**Rejected.** *Ada as a mode of the chat app.* One app fewer, but chat's deployment would carry Ada's code,
and the profiles would be mixed at run time.

**Revisit if** the apps come to differ only in configuration, so that one app built per profile would be
simpler.

## D8. Ada keeps chat's limits, and the check enforces them (2026-11-26)

**Decision.** goldilocks-ada never imports goldilocks_agent, goldilocks_chat, Deep Agents, AiiDA, AiiDA
plugins or MLIP packages, and has no shell. No other package imports goldilocks_ada. The import boundary
gets a rule for Ada, the check builds Ada's environment and checks it as it does chat's, and `AGENTS.md`
rule 4 covers Ada.

**Reason.** Proposed by Claude in the system-design session (2026-11-26); the owner did not object.
Claude's reasons: D2 and ada D9 make Ada light, D35 and ada D10 leave it without a shell, as chat is, and
a check makes that hold.

**Rejected.** None was discussed.

**Revisit if** Ada needs a package the rule forbids; ada D9's revisit clause applies first.

## D9. Ada stays a light form, checked against one VM per user (2026-11-26)

**Decision.** goldilocks-Ada stays the light form of D2: chat that can reach SCARF, show the status of its
jobs and fetch their results for post analysis, with no Deep Agents loop, and not goldilocks-agent
installed on each user's VM. The choice rests on the owner's call and the reasons below, not on D2's
reason, which ada D2 puts in question.

**Reason.** Proposed by Claude after the review of #5 (2026-11-26). The owner confirmed it after the review
of #6 (2026-11-26): "Ada stays a light form: it can connect to SCARF, see the status of its jobs, and fetch
the results to do post analysis." (Translated from Chinese by Claude.) No further reason recorded. D2
rejected goldilocks-agent on Ada because "Ada is a network deployment with limited resources, which suits
a light form". With one VM per user (ada D2), Ada is no longer a shared network deployment, so that reason
may not hold, and D2's revisit clause (long tasks) does not cover the change.
Claude's reasons for keeping the light form all the same:
- Under ada D1's order, goldilocks-agent does not exist when Ada is built: its core is M5 to M9, after
  Ada. A light form is the only one that can be built then.
- goldilocks-agent runs every calculation through AiiDA (D4, D43), which would put a database, a daemon
  and a broker in each user's VM. What a VM offers is unknown until the spike of ada D2.
- Nothing yet shows that Ada's users need long tasks (D2's revisit clause): Ada has no users yet.

**Rejected.** *goldilocks-agent on each user's VM*, the option D2 rejected. One VM per user removes the
shared deployment, and Ada's users could run long tasks on SCARF. It loses for now because the agent is not
built when Ada is, and because what it needs from a VM is unknown.

**Revisit if** the agent has shipped and the spike shows that a user's VM can run it, AiiDA included; or
Ada's users need long tasks (D2's revisit clause).

**Overturns** the workbench plan's module table (which may still change), which gives Post Analysis to
the agent only.

## D10. Ada keeps D35's rule of no shell, checked against one VM per user (2026-11-26)

**Decision.** goldilocks-Ada has no shell, as D35's third rule says: no tool with which the model runs
commands it writes. Reaching SCARF over SSH is not a shell in this sense: ada D5's module runs ssh
itself, with fixed commands. For Ada the rule rests on the reasons below, not on the premise D35 states,
which ada D2 removes. For goldilocks-chat, which still runs on a shared instance, D35 stands as it is.

**Reason.** Proposed by Claude after the review of #6 (2026-11-26). The owner asked whether reaching SCARF
over SSH needs a shell; Claude answered with the distinction above, and the owner then confirmed
the decision (2026-11-26). No reason recorded from the owner. D35's third rule says that chat and Ada,
"which run on shared network servers", never have a shell. With one VM per user (ada D2), Ada does not run
on a shared server, so that premise does not hold for Ada. Claude's reasons for keeping the rule all the
same:
- The VM holds the user's SCARF access (ada D2). A shell there could reach SCARF, and the user's files
  and jobs on it, with no card to approve it; ada D5's approval of each submission would not hold.
- D35 gives goldilocks-agent a shell only inside D29's sandbox, which holds no credentials. Ada has no
  such sandbox, and no decision here builds one.
- The post analysis Ada does (ada D9) comes through tools, as D6's Post Analysis group does. D35 gives
  the agent a shell only for side analysis beyond the tools, such as a quick plot or a statistic.

**Rejected.** *A shell on the user's VM.* One VM per user removes D35's premise for Ada, and users could
do side analysis. It loses because the shell would hold the user's SCARF access, and Ada has no sandbox.

**Revisit if** Ada gets a sandbox without the user's SCARF access, or Ada's users need side analysis that
its tools cannot do.

## D11. Post Analysis lives in the shared package; the agent wraps it as calcfunctions (2026-11-26)

**Decision.**
1. Post Analysis's analysis functions are plain Python functions in the shared package,
   `goldilocks_workbench/post_analysis/`. Every number they return carries its unit (D10), and they
   import no AiiDA.
2. goldilocks-Ada calls them directly, as tools, on the results it fetches (ada D9). Whether chat's
   profile offers them is not decided here.
3. In goldilocks-agent, an analysis that is a step in a plan wraps the same function as an AiiDA
   `calcfunction`, so D43 holds: its inputs and outputs are in the provenance graph, and D9's checks read
   them from AiiDA.
4. Plots and viewers, such as a phonon viewer that plays frames, are renderers, as in the workbench
   plan's hook 16, and are not wrapped as calcfunctions.

**Reason.** Owner's call, after the review of #6 (2026-11-26). The owner first asked why post analysis
should be AiiDA calcfunctions at all: "I don't see why post analysis has to be made into AiiDA
calcfunctions; I think it is unnecessary. Our earlier phonon visualizer's post analysis could not be made
into a calcfunction either, could it?" (Translated from Chinese by Claude.) Claude answered that the
requirement comes from D43, which covers computed values in the agent's plans, not plots or viewers, and
which does not reach Ada, as Ada has no plans. The owner then chose this option from the three Claude
offered. No further reason recorded. Claude's reasons:
- ada D9 gives Ada post analysis, while ada D4 and ada D8 keep AiiDA and goldilocks_agent out of Ada; the
  workbench plan puts Post Analysis in goldilocks-agent, as calcfunctions.
- One implementation gives the same numbers in every form, and D1 puts what the forms share in the
  shared part.
- D43 stands: the agent's wrapper is thin, and its analysis steps keep their provenance.

**Rejected.**
- *No calcfunctions in any form*, overturning D43's analysis part. The simplest, but the agent's analysis
  results would lack provenance, the reason D43 rejected "MLIP through AiiDA, analysis outside".
- *Leaving the module's place to the plan.* Ada's work comes before the agent's core (ada D1), so it is
  needed first.
- *A separate analysis module in goldilocks-ada.* The code would be written twice, and the two forms'
  numbers could differ.

**Known costs.** The shared package gains the analysis's dependencies. The plan says whether they are an
optional extra, so that chat's environment stays small.

**Revisit if** an analysis cannot be wrapped as a calcfunction, because its inputs or outputs cannot be
stored as AiiDA data; or the analysis's dependencies are too heavy for Ada's VMs.

**Overturns** the workbench plan's package and module tables (which may still change), which put Post
Analysis in goldilocks-agent.

## Concerns

- **SCARF credentials** (workbench spec, Concerns). ada D2 rests on one goldilocks-Ada instance per user
  VM, reaching SCARF with the user's own access. If that proves wrong, SCARF's terms and v4-process D21
  apply again, and Ada's SCARF features stop until the concern is settled.
- **The Ada platform is unknown to this repository.** The spike's facts may change ada D4 and ada D5.
- **The agent waits, and risk 4 loses two mitigations.** Ada now comes before the agent's core, which is
  the first version's first item and carries D7's target task. This is the owner's call (ada D1); the cost
  is the time Ada takes. The workbench plan's risk 4, scope for one maintainer, loses "agent first" and the
  "Not in the first version" list among its mitigations; the plan that follows says how risk 4 is met
  without them.
- **Private details.** Details of Ada's deployment that are not public stay in ddmms/goldilocks
  (`AGENTS.md`, rule 8).

## Open

- **Ada's model** (D11): which endpoint, for example the shared instance's model, an STFC GPU server or a
  key the user brings. Decided once the spike shows what a VM can reach.
- **Where goldilocks-dft runs for Ada**: inside each VM, or as a service Ada reaches.
- **How Ada reads the results it fetches**: which parser, in which package. Physics values come only from
  goldilocks-dft, calculations or the user (`AGENTS.md`, rule 2).
- **The size limits of ada D6**: their values, set in the plan.
- **How the app is reached inside a VM**: Ada's proxy, if any, and how the workbench plan's M2 security
  model (localhost, a per-launch token, Host and Origin checks) applies there.
