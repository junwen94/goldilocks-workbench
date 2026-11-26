#!/bin/bash
# NOTICE and carried files agree (spec D13; AGENTS.md rule 1).
# - Every line under "Carried files" in NOTICE that starts with "-", indented or not, is an entry of the form
#   "- <path> <- <source path>@ea757c7". A line that does not parse is reported, never skipped.
# - Each entry names an existing file. Unless the file is JSON, which has no comments, one of its first five
#   lines is a comment saying it was carried from stfc/goldilocks-agent, naming the source path and ea757c7.
# - Every file whose first five lines carry such a comment is listed in NOTICE.
# Usage: bash tools/checks/notice.sh [repo-root]

root=${1:-"$(cd "$(dirname "$0")/../.." && pwd)"}
cd "$root" || exit 2
problems=0
bad() { printf 'notice: %s\n' "$1"; problems=$((problems + 1)); }

[ -f NOTICE ] || { echo "notice: NOTICE is missing"; exit 1; }
grep -q "Copyright (c) 2026, Junwen Yin" NOTICE || bad "NOTICE lacks stfc/goldilocks-agent's copyright line"

marker='^[[:space:]]*(#|//|/\*|\*|<!--)[[:space:]]*Carried from stfc/goldilocks-agent'
entry='^[[:space:]]*-[[:space:]]+([^[:space:]]+)[[:space:]]+<-[[:space:]]+([^[:space:]]+)@ea757c7[[:space:]]*$'
listed=""
count=0

while IFS= read -r line; do
  [[ $line =~ ^[[:space:]]*- ]] || continue
  if ! [[ $line =~ $entry ]]; then
    bad "cannot read this NOTICE line (expected '- <path> <- <source path>@ea757c7'): $line"
    continue
  fi
  path=${BASH_REMATCH[1]}
  source=${BASH_REMATCH[2]}
  listed="$listed$path"$'\n'
  count=$((count + 1))
  if [ ! -f "$path" ]; then bad "NOTICE lists $path, which does not exist"; continue; fi
  case "$path" in *.json) continue ;; esac  # no comments in JSON: the NOTICE entry is the record
  first=$(head -n 5 "$path" | grep -E "$marker" | head -n 1)
  if [ -z "$first" ]; then
    bad "$path is listed in NOTICE but has no 'Carried from stfc/goldilocks-agent' comment in its first 5 lines"
  elif [[ $first != *"$source"* || $first != *ea757c7* ]]; then
    bad "$path: its 'Carried from' comment must name $source and ea757c7, as its NOTICE entry does"
  fi
done < <(sed -n '/^Carried files$/,$p' NOTICE)

while IFS= read -r path; do
  [ -n "$path" ] || continue
  printf '%s' "$listed" | grep -qxF "$path" || bad "$path says it is carried from stfc/goldilocks-agent but NOTICE does not list it"
done < <(git ls-files --cached --others --exclude-standard -z | xargs -0 grep -lE "$marker" 2>/dev/null \
           | while IFS= read -r f; do head -n 5 "$f" | grep -qE "$marker" && printf '%s\n' "$f"; done)

if [ "$problems" -eq 0 ]; then echo "notice: ok ($count carried files)"; exit 0; fi
echo "notice: $problems problem(s)"; exit 1
