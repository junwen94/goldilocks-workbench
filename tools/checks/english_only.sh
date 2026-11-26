#!/bin/bash
# English only on GitHub (AGENTS.md, "Never"). Fails on any CJK character in tracked files and in new files that
# .gitignore does not exclude, except the user-interface translation files frontend/packages/ui/i18n/*.json
# (owner, 2026-11-26). Prints only file:line for each hit, never the line itself, so a secret on the same line
# cannot end up in pasted output.
# Usage: bash tools/checks/english_only.sh [repo-root]

root=${1:-"$(cd "$(dirname "$0")/../.." && pwd)"}
cd "$root" || exit 2
# git grep -P reads \x{...} and \p{...} as Unicode only under a UTF-8 locale; without one it errors out.
export LC_ALL=C.UTF-8

# The CJK scripts, plus the CJK blocks of radicals, symbols and punctuation: radicals and ideographic description
# (2E80-2FFF), punctuation, kana, Bopomofo, Hangul compatibility Jamo, enclosed CJK and CJK compatibility
# (3000-33FF), compatibility forms (FE30-FE4F), half- and full-width forms (FF00-FFEF).
pattern='[\p{Han}\p{Hangul}\p{Hiragana}\p{Katakana}\p{Bopomofo}\x{2e80}-\x{2fff}\x{3000}-\x{33ff}\x{fe30}-\x{fe4f}\x{ff00}-\x{ffef}]'
err=$(mktemp) || exit 2
hits=$(git grep --untracked -nIP "$pattern" -- . ':(exclude,glob)frontend/packages/ui/i18n/*.json' 2>"$err")
status=$?
msg=$(cat "$err"); rm -f "$err"
if [ "$status" -eq 1 ]; then echo "english-only: ok"; exit 0; fi
if [ "$status" -ne 0 ]; then echo "english-only: git grep failed: $msg"; exit 2; fi
printf '%s\n' "$hits" | cut -d: -f1,2 | head -20
echo "english-only: non-English characters at the file:line above; only frontend/packages/ui/i18n/*.json may have them"
exit 1
