# goldilocks-workbench

Goldilocks Workbench is the user-facing part of Goldilocks, towards smarter and greener materials simulations. It
comes in three forms, all in this repository:

- **goldilocks-agent**: a materials-science agent that plans and runs long DFT and MLIP studies on HPC through
  AiiDA, with a local model. It ships as a container image and a macOS app.
- **goldilocks-chat**: the website, for conversation and light computation.
- **goldilocks-Ada**: a form for STFC's Ada platform, not built yet.

DFT parameters come from goldilocks-dft (the renamed goldilocks-core), reached over HTTP.

## Status

Under construction. The design and the order of work are in `changes/2026-11-25-workbench/`:

- [`intent.md`](changes/2026-11-25-workbench/intent.md): what is wanted and why;
- [`spec.md`](changes/2026-11-25-workbench/spec.md): the decisions, D1 to D53;
- [`plan.md`](changes/2026-11-25-workbench/plan.md): files, order of work, risks and proof.

The predecessor, `stfc/goldilocks-agent`, keeps serving the current website until goldilocks-chat matches it.

## Working here

Read [`AGENTS.md`](AGENTS.md) first: it has the check command, the record rules and the PR template.
[`REVIEW.md`](REVIEW.md) is what the review checks.

You need [uv](https://docs.astral.sh/uv/) 0.12.9 or later and Node.js 22.12 or later with npm. uv installs Python
3.12 itself. The layout:

- `packages/workbench`, `packages/chat`, `packages/agent`: the shared part and two forms, one uv workspace with
  one lock (`uv.lock`); `uv sync --all-packages` installs all three into `.venv`;
- `frontend/apps/chat`, `frontend/apps/agent`: the two web apps, one npm workspace (`frontend/package-lock.json`).

Run the check with:

```
bash tools/check.sh
```

## Licence

BSD 3-Clause; see [`LICENSE`](LICENSE). Parts carried from `stfc/goldilocks-agent` keep their notice; see
[`NOTICE`](NOTICE).
