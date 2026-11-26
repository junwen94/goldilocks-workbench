# Review instructions

How the AI review checks a pull request in this repository. Source: ddmms/goldilocks, `templates/REVIEW.md`
(v4-process D18), with this repository's high-risk paths and two compliance checks added.

## Passes

Run six passes. Tag each finding with its pass.

1. **Bugs**: logic errors, broken edge cases, regressions.
2. **Security**: secrets in the diff, injection, authentication gaps, personal data in logs or error
   messages.
3. **Compliance**:
   - Medium and large changes: the diff does what `plan.md` (and `spec.md`) say, and nothing else.
   - Every change: the PR description matches the diff (v4-process D11), and the declared size is right
     (v4-process D8).
   - No code, prose or assets copied from other projects (D23). A file carried from `stfc/goldilocks-agent`
     starts with a "Carried from stfc/goldilocks-agent" line citing `ea757c7` and is listed in `NOTICE` (D13).
     A file ported from another Goldilocks repository cites its source repository, path and commit.
   - Nothing private: no details of the unpublished study behind D7, no reference data, no deployment details.
4. **High-risk**: the declared "High-risk: yes (category N) / no" matches what the diff touches
   (v4-process D17). Use the paths below as hints, not as the whole rule.
5. **Provenance of physics values**: every new or changed physics value (a default parameter, a
   constant, a value in a table, a threshold in a check) states where it comes from: goldilocks-dft, a paper or
   DOI, a data table, or a calculation. A value with no source is Important.
6. **Tests**: a bug fix that deletes or weakens an existing test is Important. New behaviour without a
   test is Important.

## What Important means here

Important is reserved for findings that would:
- make the program behave wrongly;
- give users wrong physics numbers;
- leak data;
- break a rule of this repository (`AGENTS.md`); or
- leave the size or high-risk declaration wrong.

Everything else is a nit.

## Cap the nits

Report at most five nits per review, and summarise the rest as a count.

## Do not report

Generated files, lock files, and anything CI already enforces (formatting, lint).

## When a finding repeats

If a review flags the same kind of mistake for the second time, add the correction to `AGENTS.md` in
the same PR, so the mistake is not repeated.

## High-risk paths

Paths that do not exist yet are listed so that the rule holds when they arrive (plan, "Files that change").

1. **Physics**: `packages/agent/src/goldilocks_agent/aiida/routes/**`, `packages/agent/src/goldilocks_agent/aiida/checks/**`,
   `packages/agent/src/goldilocks_agent/mlip/**`, `**/post_analysis/**` (the shared functions, the
   agent's calcfunctions and their panels; ada D11),
   `**/structure_builder/**` (the backend module and its frontend panel), `**/units*`, `**/checks/*.toml`,
   `**/dft_client/pin.json`, `evals/scoring/**`.
2. **External contracts**: `**/server/**`, `frontend/packages/types/**`, `**/cli.py`, the research-record schema,
   the D31 receipt and answers format, the evaluation task-package format.
3. **Security and deployment**: `**/server/security.py`, `**/server/pauses.py`,
   `packages/agent/src/goldilocks_agent/sandbox/**`, `packages/agent/src/goldilocks_agent/executor/caps.py`,
   `packages/agent/src/goldilocks_agent/aiida/profile.py`, `packages/ada/src/goldilocks_ada/slurm/**` (the commands
   Ada runs on SCARF; ada D5), `**/config.py`, `deploy/**`, `desktop/**`,
   `.github/workflows/**`, dependency declarations (`pyproject.toml`, `uv.lock`, `package.json`,
   `package-lock.json`).
4. **Process guardrails**: `AGENTS.md`, `REVIEW.md`, `NOTICE`, `tools/**`, `budgets.toml`, `changes/**`,
   `docs/developer/skills/**`.
5. **User data**: `**/store/**`, `packages/chat/src/goldilocks_chat/retention.py`,
   `packages/agent/src/goldilocks_agent/memory.py`, code that writes or deletes task folders and research
   records, AiiDA profile creation and migration.
