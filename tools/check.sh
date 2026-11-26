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

step "English only (tools/checks/english_only.sh)"
bash "$root/tools/checks/english_only.sh" "$root" || fail=1

step "NOTICE (tools/checks/notice.sh)"
bash "$root/tools/checks/notice.sh" "$root" || fail=1

step "Markdown links (tools/checks/md_links.sh)"
bash "$root/tools/checks/md_links.sh" "$root" || fail=1

echo
if [ "$fail" -eq 0 ]; then echo "check: all passed"; exit 0; fi
echo "check: FAILED"; exit 1
