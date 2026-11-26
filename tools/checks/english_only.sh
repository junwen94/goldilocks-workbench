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

# Explicit code-point ranges, not script properties: newer PCRE2 makes \p{Han} match Script_Extensions, which
# include the middle dot U+00B7, so the result would depend on the PCRE2 version. The ranges: Hangul Jamo
# (1100-11FF); radicals and ideographic description (2E80-2FFF); punctuation, kana, Bopomofo, Hangul
# compatibility Jamo, enclosed CJK, CJK compatibility, Extension A and unified ideographs (3000-9FFF); Hangul
# Jamo Extended-A (A960-A97F); Hangul syllables and Jamo Extended-B (AC00-D7FF); compatibility ideographs
# (F900-FAFF); compatibility forms (FE30-FE4F); half- and full-width forms (FF00-FFEF); kana supplements
# (1AFF0-1B16F); enclosed ideographic supplement (1F200-1F2FF); Extensions B to I and the compatibility
# supplement (20000-3FFFF).
pattern='[\x{1100}-\x{11ff}\x{2e80}-\x{2fff}\x{3000}-\x{9fff}\x{a960}-\x{a97f}\x{ac00}-\x{d7ff}\x{f900}-\x{faff}\x{fe30}-\x{fe4f}\x{ff00}-\x{ffef}\x{1aff0}-\x{1b16f}\x{1f200}-\x{1f2ff}\x{20000}-\x{3ffff}]'
err=$(mktemp) || exit 2
hits=$(git grep --untracked -nIP "$pattern" -- . ':(exclude,glob)frontend/packages/ui/i18n/*.json' 2>"$err")
status=$?
msg=$(cat "$err"); rm -f "$err"
if [ "$status" -eq 1 ]; then echo "english-only: ok"; exit 0; fi
if [ "$status" -ne 0 ]; then echo "english-only: git grep failed: $msg"; exit 2; fi
printf '%s\n' "$hits" | cut -d: -f1,2 | head -20
echo "english-only: non-English characters at the file:line above; only frontend/packages/ui/i18n/*.json may have them"
exit 1
