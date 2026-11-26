#!/bin/bash
# Relative links in Markdown files point at files that exist.
# Reads inline links [text](target) outside code: fenced blocks and inline code spans are skipped. Skips web
# links, mail links and pure anchors. A target starting with "/" is read from the repository root, as GitHub
# does. Drops angle brackets, a title, the anchor and the query; decodes %20.
# Not checked: reference-style links ([text][ref] with "[ref]: target") and HTML href or src.
# Usage: bash tools/checks/md_links.sh [repo-root]

root=${1:-"$(cd "$(dirname "$0")/../.." && pwd)"}
cd "$root" || exit 2
problems=0

# Prints a Markdown file without its fenced code blocks and inline code spans.
strip_code() {
  awk '
    /^[[:space:]]*(```|~~~)/ { fence = !fence; next }
    fence { next }
    { gsub(/`[^`]*`/, ""); print }
  ' "$1"
}

while IFS= read -r -d '' md; do
  dir=$(dirname "$md")
  while IFS= read -r target; do
    case "$target" in
      \<*) target=${target#<}; target=${target%%>*} ;;
      *) target=${target%% *} ;;  # drops a title, as in [a](file.md "title")
    esac
    case "$target" in
      http://*|https://*|mailto:*|\#*|'') continue ;;
    esac
    file=${target%%#*}
    file=${file%%\?*}
    file=${file//%20/ }
    [ -n "$file" ] || continue
    case "$file" in
      /*) path=".$file" ;;
      *) path="$dir/$file" ;;
    esac
    if [ ! -e "$path" ]; then
      printf 'md-links: %s: broken link to %s\n' "$md" "$target"
      problems=$((problems + 1))
    fi
  done < <(strip_code "$md" | grep -oE '\]\([^)]+\)' | sed -E 's/^\]\((.*)\)$/\1/')
done < <(git ls-files --cached --others --exclude-standard -z -- '*.md')

if [ "$problems" -eq 0 ]; then echo "md-links: ok"; exit 0; fi
echo "md-links: $problems broken link(s)"; exit 1
