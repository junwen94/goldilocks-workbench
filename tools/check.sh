#!/bin/bash
# The single check for this repository (v4-process D22). Calls no model.
# Usage: bash tools/check.sh
# Ends with "check: all passed" and exit 0, or "check: FAILED" and exit 1.
# Needs uv and Node.js with npm (README, "Working here"). The Python and frontend tools write to a log, which is
# printed only when their step fails.

root="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
step() { printf '\n== %s\n' "$1"; }
tmp=$(mktemp -d) || exit 2
trap 'rm -rf "$tmp"' EXIT
log="$tmp/log"
show_log() { sed 's/^/    /' "$log" | head -60; [ "$(wc -l <"$log")" -gt 60 ] && echo "    ... (log cut at 60 lines)"; }
run() {  # run <label> <command...>: prints "<label>: ok", or "<label>: FAILED" and the log
  local label=$1; shift
  if "$@" >"$log" 2>&1; then echo "$label: ok"; return 0; fi
  echo "$label: FAILED"; show_log; fail=1; return 1
}
need() {  # need <command>: fails the check if the command is missing
  command -v "$1" >/dev/null && return 0
  echo "$1: not found; install it (README, \"Working here\")"; fail=1; return 1
}
uvr() { uv --directory "$root" "$@"; }

step "change records (tools/lint-records.sh)"
bash "$root/tools/lint-records.sh" "$root" || fail=1
fx="$root/tools/lint-records-fixtures"
if bash "$root/tools/lint-records.sh" "$fx/good" >/dev/null; then echo "fixture good: passes, as it should"
else echo "fixture good: FAILS, but should pass"; fail=1; fi
for bad in "$fx"/*/; do
  name=$(basename "$bad"); [ "$name" = good ] && continue
  if bash "$root/tools/lint-records.sh" "$bad" >/dev/null; then echo "fixture $name: PASSES, but should fail"; fail=1
  else echo "fixture $name: fails, as it should"; fi
done

step "tests of the checks below (tools/checks/test.sh)"
bash "$root/tools/checks/test.sh" || fail=1

step "English only (tools/checks/english_only.sh)"
bash "$root/tools/checks/english_only.sh" "$root" || fail=1

step "NOTICE (tools/checks/notice.sh)"
bash "$root/tools/checks/notice.sh" "$root" || fail=1

step "Markdown links (tools/checks/md_links.sh)"
bash "$root/tools/checks/md_links.sh" "$root" || fail=1

step "Python: lock, environment, ruff, mypy, pytest (uv)"
if need uv && run "uv lock --check" uvr lock --check && run "uv sync --locked --all-packages" uvr sync --locked --all-packages; then
  run "ruff check" uvr run --no-sync ruff check
  run "ruff format --check" uvr run --no-sync ruff format --check
  run "mypy (strict)" uvr run --no-sync mypy
  if uvr run --no-sync pytest -q -m "not live" >"$log" 2>&1; then
    echo "pytest: ok ($(tail -n 1 "$log" | sed -E 's/ in [0-9.]+s.*//'))"
  else echo "pytest: FAILED"; show_log; fail=1; fi

  step "import boundary (tools/checks/import_boundary.py)"
  uvr run --no-sync python tools/checks/import_boundary.py "$root" || fail=1

  step "light-form environments (tools/checks/light_env.py)"
  # A fresh environment per light form, with its package and dependencies only, as the website and an Ada VM
  # install it (ada D8).
  for form in chat ada; do
    if run "uv sync --package goldilocks-$form" \
        env UV_PROJECT_ENVIRONMENT="$tmp/$form-env" uv --directory "$root" sync --locked --package "goldilocks-$form" --no-dev; then
      "$tmp/$form-env/bin/python" "$root/tools/checks/light_env.py" "$form" || fail=1
    fi
  done
fi

step "frontend: npm ci, eslint, tsc, vitest, vite build"
fe="$root/frontend"
if need npm && run "npm ci" npm --prefix "$fe" ci --no-audit --no-fund; then
  run "eslint" npm --prefix "$fe" run lint
  run "tsc (strict)" npm --prefix "$fe" run typecheck
  run "vitest" npm --prefix "$fe" test
  run "vite build (three apps)" npm --prefix "$fe" run build
fi

echo
if [ "$fail" -eq 0 ]; then echo "check: all passed"; exit 0; fi
echo "check: FAILED"; exit 1
