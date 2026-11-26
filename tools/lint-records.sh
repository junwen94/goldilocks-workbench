#!/bin/bash
# Ported from ddmms/goldilocks tools/lint-records.sh @ f0f4681 (Goldilocks shared process tooling).
# Lint change records (spec v4-process, D4 and D14).
# Usage: bash tools/lint-records.sh [repo-root]   (default: this repository)
#
# 1. Required headings (D14) in changes/<date>-<name>/{intent,spec,plan}.md, for records dated
#    2026-11-25 or later. Older records predate D14 and are frozen (D4), so they are skipped.
# 2. Supersedes pairs (D4), in every record of any date. Paths are repository-relative:
#      new record:  a line "Supersedes: changes/<old>/<file>.md"
#      old record:  a line "Superseded by changes/<new>/<file>.md"
#    Each must point at an existing record that points back.
# Exits 1 and lists every problem if any check fails.

root=${1:-"$(cd "$(dirname "$0")/.." && pwd)"}
cd "$root" || exit 2
D14_FROM=2026-11-25
problems=0
bad() { printf 'lint-records: %s\n' "$1"; problems=$((problems + 1)); }
need() {  # need <file> <fixed-string> <label>
  grep -qF -- "$2" "$1" || bad "$1: missing $3"
}

for dir in changes/*/; do
  [ -d "$dir" ] || continue
  dir=${dir%/}
  name=$(basename "$dir")
  date=${name:0:10}
  [[ $date =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { bad "$dir: folder name must start with YYYY-MM-DD (D15)"; continue; }
  [[ "$date" < "$D14_FROM" ]] && continue

  f="$dir/intent.md"
  if [ -f "$f" ]; then
    need "$f" "Size:" "'Size:' in the header"
    need "$f" "Source:" "'Source:' in the header"
    for h in "## In the owner's words" "## Problem" "## Proposed outcome" "## Affected" \
             "## Constraints" "## Out of scope" "## Open questions"; do
      need "$f" "$h" "heading '$h'"
    done
  else
    bad "$dir: no intent.md"
  fi

  f="$dir/spec.md"
  if [ -f "$f" ]; then
    need "$f" "## Concerns" "heading '## Concerns'"
    need "$f" "## Open" "heading '## Open'"
    grep -qE '^## D[0-9]+\.' "$f" || bad "$f: no decision headings ('## D1. ...')"
    # Every decision section carries the four required parts.
    awk -v f="$f" '
      function check() {
        if (sec == "") return
        if (!dec) print f ": " sec ": missing **Decision.**"
        if (!rea) print f ": " sec ": missing **Reason.**"
        if (!rej) print f ": " sec ": missing **Rejected.**"
        if (!rev) print f ": " sec ": missing **Revisit if**"
      }
      /^## / { check(); sec = ""; if ($0 ~ /^## D[0-9]+\./) { sec = $2; dec = rea = rej = rev = 0 }; next }
      sec != "" && /\*\*Decision\.\*\*/  { dec = 1 }
      sec != "" && /\*\*Reason\.\*\*/    { rea = 1 }
      sec != "" && /\*\*Rejected\.\*\*/  { rej = 1 }
      sec != "" && /\*\*Revisit if\*\*/  { rev = 1 }
      END { check() }
    ' "$f" | while IFS= read -r line; do printf 'lint-records: %s\n' "$line"; done
    n=$(awk -v f="$f" '
      function check() { if (sec != "" && (!dec || !rea || !rej || !rev)) bad++ }
      /^## / { check(); sec = ""; if ($0 ~ /^## D[0-9]+\./) { sec = $2; dec = rea = rej = rev = 0 }; next }
      sec != "" && /\*\*Decision\.\*\*/ { dec = 1 }
      sec != "" && /\*\*Reason\.\*\*/   { rea = 1 }
      sec != "" && /\*\*Rejected\.\*\*/ { rej = 1 }
      sec != "" && /\*\*Revisit if\*\*/ { rev = 1 }
      END { check(); print bad + 0 }
    ' "$f")
    problems=$((problems + n))
  fi

  f="$dir/plan.md"
  if [ -f "$f" ]; then
    need "$f" "Size:" "'Size:' in the header"
    for h in "## Files that change" "## Order of work" "## Risks" "## Proof"; do
      need "$f" "$h" "heading '$h'"
    done
    if grep -qE 'Size: *medium' "$f"; then need "$f" "## Decisions" "heading '## Decisions' (medium change, D8)"; fi
  fi
done

# Supersedes pairs, all records.
for f in changes/*/*.md; do
  [ -f "$f" ] || continue
  while IFS= read -r target; do
    [ -f "$target" ] || { bad "$f: 'Superseded by $target' points at no file"; continue; }
    grep -qE "^Supersedes: *$f *$" "$target" || bad "$f: '$target' has no matching 'Supersedes: $f'"
  done < <(sed -nE 's/^Superseded by +([^ ]+) *$/\1/p' "$f")
  while IFS= read -r target; do
    [ -f "$target" ] || { bad "$f: 'Supersedes: $target' points at no file"; continue; }
    grep -qE "^Superseded by +$f *$" "$target" || bad "$f: '$target' has no matching 'Superseded by $f'"
  done < <(sed -nE 's/^Supersedes: *([^ ]+) *$/\1/p' "$f")
done

if [ "$problems" -eq 0 ]; then echo "lint-records: ok"; exit 0; fi
echo "lint-records: $problems problem(s)"; exit 1
