#!/bin/bash
# Relative links in Markdown files point at files that exist.
# Skips web links, mail links and pure anchors; ignores the anchor part of a relative link.
# Usage: bash tools/checks/md_links.sh [repo-root]

root=${1:-"$(cd "$(dirname "$0")/../.." && pwd)"}
cd "$root" || exit 2
problems=0

while IFS= read -r -d '' md; do
  dir=$(dirname "$md")
  while IFS= read -r target; do
    case "$target" in
      http://*|https://*|mailto:*|\#*|'') continue ;;
    esac
    file=${target%%#*}
    file=${file%% *}
    [ -n "$file" ] || continue
    if [ ! -e "$dir/$file" ]; then
      printf 'md-links: %s: broken link to %s\n' "$md" "$target"
      problems=$((problems + 1))
    fi
  done < <(grep -oE '\]\([^)]+\)' "$md" | sed -E 's/^\]\((.*)\)$/\1/')
done < <(git ls-files --cached --others --exclude-standard -z -- '*.md')

if [ "$problems" -eq 0 ]; then echo "md-links: ok"; exit 0; fi
echo "md-links: $problems broken link(s)"; exit 1
