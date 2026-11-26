#!/bin/bash
# The single check for this repository (v4-process D22). Calls no model.
# Usage: bash tools/check.sh
# Ends with "check: all passed" and exit 0, or "check: FAILED" and exit 1.
# PR 2 of the plan extends it with the Python and frontend checks.

root="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
step() { printf '\n== %s\n' "$1"; }

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

echo
if [ "$fail" -eq 0 ]; then echo "check: all passed"; exit 0; fi
echo "check: FAILED"; exit 1
