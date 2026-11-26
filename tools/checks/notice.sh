#!/bin/bash
# NOTICE and carried files agree (spec D13; AGENTS.md rule 1).
# - Every entry "- <path> <- <source>@ea757c7" under "Carried files" in NOTICE names an existing file whose
#   first comment lines say "Carried from stfc/goldilocks-agent".
# - Every file that starts with such a comment line is listed in NOTICE.
# Usage: bash tools/checks/notice.sh [repo-root]

root=${1:-"$(cd "$(dirname "$0")/../.." && pwd)"}
cd "$root" || exit 2
problems=0
bad() { printf 'notice: %s\n' "$1"; problems=$((problems + 1)); }

[ -f NOTICE ] || { echo "notice: NOTICE is missing"; exit 1; }
grep -q "Copyright (c) 2026, Junwen Yin" NOTICE || bad "NOTICE lacks stfc/goldilocks-agent's copyright line"

marker='^[[:space:]]*(#|//|/\*|\*|<!--)[[:space:]]*Carried from stfc/goldilocks-agent'
listed=$(sed -n '/^Carried files$/,$p' NOTICE | sed -nE 's/^- +([^ ]+) +<- +([^ ]+)@ea757c7 *$/\1/p')

for path in $listed; do
  if [ ! -f "$path" ]; then bad "NOTICE lists $path, which does not exist"; continue; fi
  head -n 5 "$path" | grep -qE "$marker" || bad "$path is listed in NOTICE but has no 'Carried from stfc/goldilocks-agent' line at its top"
done

while IFS= read -r path; do
  [ -n "$path" ] || continue
  printf '%s\n' "$listed" | grep -qxF "$path" || bad "$path says it is carried from stfc/goldilocks-agent but NOTICE does not list it"
done < <(git ls-files --cached --others --exclude-standard -z | xargs -0 grep -lE "$marker" 2>/dev/null \
           | while IFS= read -r f; do head -n 5 "$f" | grep -qE "$marker" && printf '%s\n' "$f"; done)

count=$(printf '%s\n' "$listed" | grep -c . || true)
if [ "$problems" -eq 0 ]; then echo "notice: ok ($count carried files)"; exit 0; fi
echo "notice: $problems problem(s)"; exit 1
