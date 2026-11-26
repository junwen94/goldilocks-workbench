#!/bin/bash
# English only on GitHub (AGENTS.md, "Never"). Fails on any CJK character in tracked or new files, except the
# user-interface translation files in frontend/packages/ui/i18n/ (owner, 2026-11-26).
# Usage: bash tools/checks/english_only.sh [repo-root]

root=${1:-"$(cd "$(dirname "$0")/../.." && pwd)"}
cd "$root" || exit 2

pattern='[\x{3000}-\x{303f}\x{3040}-\x{30ff}\x{3400}-\x{4dbf}\x{4e00}-\x{9fff}\x{ac00}-\x{d7af}\x{ff00}-\x{ffef}]'
hits=$(git grep --untracked -nIP "$pattern" -- . ':(exclude)frontend/packages/ui/i18n/**' 2>&1)
status=$?
if [ "$status" -eq 1 ]; then echo "english-only: ok"; exit 0; fi
if [ "$status" -ne 0 ]; then echo "english-only: git grep failed: $hits"; exit 2; fi
echo "$hits" | head -20
echo "english-only: non-English characters found outside frontend/packages/ui/i18n/"
exit 1
