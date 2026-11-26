# AGENTS.md: goldilocks-workbench

Goldilocks Workbench: one repository for the three forms of the Goldilocks assistant, goldilocks-chat,
goldilocks-agent and goldilocks-Ada (spec D1). The change being built is `changes/2026-11-25-workbench/`
(intent, spec with decisions D1 to D53, plan). In this repository a bare "D*n*" is a decision of that spec. The
shared process's decisions are written "v4-process D*n*" (ddmms/goldilocks,
`changes/2026-11-24-v4-process/spec.md`).

## Check (v4-process D22)

```
bash tools/check.sh
```

A healthy run ends with `check: all passed`:

```
== change records (tools/lint-records.sh)
lint-records: ok
fixture good: passes, as it should
fixture bad-folder: fails, as it should
...                                    (one line per failing fixture)

== tests of the checks below (tools/checks/test.sh)
check tests: ok (35 cases)

== English only (tools/checks/english_only.sh)
english-only: ok

== NOTICE (tools/checks/notice.sh)
notice: ok (0 carried files)

== Markdown links (tools/checks/md_links.sh)
md-links: ok

== Python: lock, environment, ruff, mypy, pytest (uv)
uv lock --check: ok
uv sync --locked --all-packages: ok
ruff check: ok
ruff format --check: ok
mypy (strict): ok
pytest: ok (77 passed)

== import boundary (tools/checks/import_boundary.py)
import-boundary: ok (8 files)

== chat environment (tools/checks/chat_env.py)
uv sync --package goldilocks-chat: ok
chat-env: ok

== frontend: npm ci, eslint, tsc, vitest, vite build
npm ci: ok
eslint: ok
tsc (strict): ok
vitest: ok
vite build (both apps): ok

check: all passed
```

It needs uv and Node.js with npm (`README.md`, "Working here"). CI runs it on Linux and macOS.

Before you report a task done or open a PR, run it and paste the output. If it fails, fix the cause, never the
check.

## Change records

- **Size first (v4-process D8).** Small: no records. Medium: `intent.md` and `plan.md`. Large: `intent.md`,
  `spec.md` and `plan.md`. State the size on the first line. When in doubt, go up.
- **Where (v4-process D1, D15).** A change that touches only this repository keeps its records here, in
  `changes/<YYYY-MM-DD>-<short-name>/`. A change that spans repositories keeps them in ddmms/goldilocks.
- **Templates (v4-process D14).** Use the `goldilocks-records` skill. The headings are required; extra sections
  are allowed.
- **Frozen once accepted (v4-process D4).** Never edit an accepted record. To overturn one, write a new record
  that explains what it overturns and why, with a line `Supersedes: changes/<old>/<file>.md`. The old record
  gets exactly one line, `Superseded by changes/<new>/<file>.md`. A `plan.md` may change until the last PR that
  implements it merges. `tools/lint-records.sh` checks the headings and the Supersedes pairs.
- **Living files** (`README.md`, this file, `NOTICE`) state only the current position. History is in git.
- **Issues are the inbox (v4-process D13).** `intent.md` is the record of what is wanted.
- **Reasons.** Never supply a reason the owner did not give. Write "no reason recorded".

## Pull requests (v4-process D11, D17)

The description has these parts:

```
Size: <small | medium | large>. Implements: <issue or intent>. High-risk: <yes (category N) | no>.
What: <what changed>
Why: <why>

Written by an agent on behalf of the owner.
```

High-risk categories (v4-process D17): 1 physics, 2 external contracts, 3 security and deployment, 4 the
process's own guardrails, 5 user data. `REVIEW.md` lists this repository's paths. Paste the check's output in
the PR conversation.

## Only the owner (v4-process D5, D6, D16)

Merging, approving, pushing to `main`, tags, releases and publishing. The owner gate blocks them. Open the PR and
stop. Before approving, the owner runs `/goldilocks-process:goldilocks-review <PR>` in a new session, from a
checkout of `main` (v4-process D19, D20). CI's `review-comment` check fails until that review is posted for the
PR's latest commit.

## Never

- Read, edit or write credential files (`~/.ssh`, gcloud credentials, `.env`, …), or print tokens. The gate
  blocks it (v4-process D21).
- Put a secret in a commit, a PR or a comment.
- Edit an accepted change record, except to add its `Superseded by` line.
- Write anything on GitHub in a language other than English: files, PR titles and descriptions, comments,
  reviews, commit messages and branch names. The one exception is the user-interface translation files,
  `frontend/packages/ui/i18n/*.json` (owner, 2026-11-26). When a record quotes the owner, give only the English
  translation, marked "(Translated from Chinese by Claude.)". The check includes an English-only test.

## Rules for this repository

1. **No copied code (D23).** Copy no code, prose or assets from other projects. Re-implement from the design and
   cite `path@commit` in the PR. Two exceptions:
   - parts of `stfc/goldilocks-agent` carried under D13: the file's first comment line contains "Carried from
     stfc/goldilocks-agent" with its source path and `ea757c7`, and `NOTICE` lists it. A file in a format
     without comments, such as JSON, is listed in `NOTICE` only;
   - files ported from other Goldilocks repositories (same copyright holder, BSD-3-Clause), such as
     goldilocks-core's web components: the file's first comment line cites the source repository, path and
     commit.

   Dependencies and skills loaded at run time are not affected.
2. **Physics values** come only from goldilocks-dft, from calculations or from the user. Every threshold in a
   check names its source.
3. **Tools** enter only as registry modules, with examples and a return schema (D10). No tool calls an LLM
   (D11).
4. **goldilocks-chat** never imports agent code, Deep Agents, AiiDA or MLIP packages, and has no shell (D1, D35).
5. **Shipped configurations** never set LangSmith variables (D48).
6. **Inputs.** Neither the Workbench nor the model writes native input files. Every DFT input setting comes
   through goldilocks-dft (D37); MLIP settings come from the Workbench's typed MLIP tools.
7. **goldilocks-dft** (goldilocks-core until its rename) is reached over HTTP only; this repository never
   imports it.
8. **Nothing private**: no details of the unpublished study behind D7, no reference data, no deployment details
   of the shared instance. They live in ddmms/goldilocks.
