#!/bin/bash
# Ported from ddmms/goldilocks tools/lint-records.sh @ f0f4681 (Goldilocks shared process tooling), with changes:
# headings must be whole lines outside code fences; "Size:" and "Source:" are read from the header (the lines
# before the first "## " heading), and the size case-insensitively; decisions are cited as "v4-process Dn".
# Lint change records (spec v4-process, D4 and D14).
# Usage: bash tools/lint-records.sh [repo-root]   (default: this repository)
#
# 1. Required headings (v4-process D14) in changes/<date>-<name>/{intent,spec,plan}.md, for records dated
#    2026-11-25 or later. Older records predate D14 and are frozen (v4-process D4), so they are skipped.
#    Which files a size needs (v4-process D8) is not checked: records are written and accepted one at a time.
# 2. Supersedes pairs (v4-process D4), in every record of any date. Paths are repository-relative:
#      new record:  a line "Supersedes: changes/<old>/<file>.md"
#      old record:  a line "Superseded by changes/<new>/<file>.md"
#    Each must point at an existing record that points back.
# Exits 1 and lists every problem if any check fails.

root=${1:-"$(cd "$(dirname "$0")/.." && pwd)"}
cd "$root" || exit 2
D14_FROM=2026-11-25
problems=0
bad() { printf 'lint-records: %s\n' "$1"; problems=$((problems + 1)); }
header() { awk '/^## /{ exit } { print }' "$1"; }                         # lines before the first "## "
body() { awk '/^[[:space:]]*(```|~~~)/{ fence = !fence; next } !fence' "$1"; }  # without fenced code blocks
need_header() {  # need_header <file> <fixed-string>
  header "$1" | grep -qF -- "$2" || bad "$1: missing '$2' in the header"
}
need_heading() {  # need_heading <file> <heading> [why]: a whole line, outside code fences
  body "$1" | sed 's/[[:space:]]*$//' | grep -qxF -- "$2" || bad "$1: missing heading '$2'${3:+ ($3)}"
}
size_of() {  # prints small, medium or large from the header's "Size:", or nothing
  header "$1" | grep -oiE 'Size:[[:space:]]*(small|medium|large)' | head -n 1 \
    | sed -E 's/^[^:]*:[[:space:]]*//' | tr '[:upper:]' '[:lower:]'
}
need_size() {
  [ -n "$(size_of "$1")" ] || bad "$1: missing 'Size: small|medium|large' in the header"
}

for dir in changes/*/; do
  [ -d "$dir" ] || continue
  dir=${dir%/}
  name=$(basename "$dir")
  date=${name:0:10}
  [[ $date =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { bad "$dir: folder name must start with YYYY-MM-DD (v4-process D15)"; continue; }
  [[ "$date" < "$D14_FROM" ]] && continue

  f="$dir/intent.md"
  if [ -f "$f" ]; then
    need_size "$f"
    need_header "$f" "Source:"
    for h in "## In the owner's words" "## Problem" "## Proposed outcome" "## Affected" \
             "## Constraints" "## Out of scope" "## Open questions"; do
      need_heading "$f" "$h"
    done
  else
    bad "$dir: no intent.md"
  fi

  f="$dir/spec.md"
  if [ -f "$f" ]; then
    need_heading "$f" "## Concerns"
    need_heading "$f" "## Open"
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
    need_size "$f"
    for h in "## Files that change" "## Order of work" "## Risks" "## Proof"; do
      need_heading "$f" "$h"
    done
    if [ "$(size_of "$f")" = medium ]; then need_heading "$f" "## Decisions" "medium change, v4-process D8"; fi
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
