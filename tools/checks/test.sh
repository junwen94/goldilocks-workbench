#!/bin/bash
# Tests for english_only.sh, notice.sh and md_links.sh. Each case builds a small git repository in a temporary
# folder, runs one check on it and compares the exit code with the expected one. Non-English test text is
# written as byte escapes, so this file stays English. Run by tools/check.sh.
# Usage: bash tools/checks/test.sh

here="$(cd "$(dirname "$0")" && pwd)"
tmp=$(mktemp -d) || exit 2
trap 'rm -rf "$tmp"' EXIT
repo="$tmp/r"
fail=0
count=0

fresh() { rm -rf "$repo"; mkdir -p "$repo"; git -C "$repo" init -q; }          # an empty repository
put() { mkdir -p "$(dirname "$repo/$1")"; printf '%b' "$2" > "$repo/$1"; }   # put <path> <text with escapes>
expect() {  # expect <exit code> <check> <case>; leaves the check's output in $out
  count=$((count + 1))
  out=$(bash "$here/$2.sh" "$repo" 2>&1)
  local got=$?
  [ "$got" -eq "$1" ] && return 0
  echo "test $2: $3: exit $got, expected $1"
  printf '%s\n' "$out" | sed 's/^/    /'
  fail=1
}
lacks() {  # lacks <text> <case>: the last check's output must not contain <text>
  case "$out" in *"$1"*) echo "test: $2: output contains '$1'"; fail=1 ;; esac
}

# --- english_only ---------------------------------------------------------------------------------------------
fresh; put README.md 'Plain English, caf\xc3\xa9, na\xc3\xafve, \xe2\x80\x94 dash, 20 \xc2\xb0C, \xce\xb1\xce\xb2.\n'
expect 0 english_only "English with accents, dashes, symbols and Greek"
LC_ALL=C expect 0 english_only "the same under a locale without UTF-8"

# Han, compatibility ideograph, Extension B, Bopomofo, enclosed CJK, Hangul Jamo, radical, full-width comma,
# ideographic full stop, Hangul syllable, Hiragana, compatibility form.
for bytes in '\xe4\xb8\xad' '\xef\xa4\x80' '\xf0\xa0\x80\x80' '\xe3\x84\x85' '\xe3\x88\xb1' '\xe1\x84\x80' \
             '\xe2\xba\x80' '\xef\xbc\x8c' '\xe3\x80\x82' '\xed\x95\x9c' '\xe3\x81\x82' '\xef\xb8\xb0'; do
  fresh; put notes.md "text $bytes\n"
  expect 1 english_only "CJK character $bytes"
done
fresh; put notes.md 'text \xe4\xb8\xad\n'
LC_ALL=C expect 1 english_only "a CJK character under a locale without UTF-8"

fresh; put frontend/packages/ui/i18n/zh.json '{"hello": "\xe4\xbd\xa0\xe5\xa5\xbd"}\n'
expect 0 english_only "a translation file in frontend/packages/ui/i18n/"
fresh; put frontend/packages/ui/i18n/sub/index.ts '// \xe4\xb8\xad\n'
expect 1 english_only "code in a subfolder of i18n/"
fresh; put frontend/packages/ui/i18n/sub/x.json '{"a": "\xe4\xb8\xad"}\n'
expect 1 english_only "JSON in a subfolder of i18n/"

fresh; put .gitignore '.venv/\n'; put .venv/lib/README.md '\xe4\xb8\xad\n'
expect 0 english_only "an ignored folder"
fresh; put settings.txt 'token=abc123 \xe4\xb8\xad\n'
expect 1 english_only "a hit in an untracked file"
lacks "abc123" "english_only prints file:line, not the line"

# --- notice ---------------------------------------------------------------------------------------------------
notice() {  # notice <entry lines>: NOTICE with the copyright line, the format line and the given entries
  put NOTICE "Copyright (c) 2026, Junwen Yin\n\nCarried files\n\nFormat: - <path> <- <source>@ea757c7\n\n$1\n"
}
good_marker='# Carried from stfc/goldilocks-agent, graph.py@ea757c7\nx = 1\n'

fresh; notice '(none yet)'
expect 0 notice "no carried files"
fresh; notice '- app/a.py <- graph.py@ea757c7'; put app/a.py "$good_marker"
expect 0 notice "one carried file"
fresh; notice '  - app/a.py <- graph.py@ea757c7'; put app/a.py "$good_marker"
expect 0 notice "an indented entry, as the format line shows"
fresh; notice '- app/pin.json <- core_pin.json@ea757c7'; put app/pin.json '{"version": "0.3.3"}\n'
expect 0 notice "a JSON file, listed in NOTICE only"
fresh; notice '- app/a.py <- graph.py@ea757c8'; put app/a.py "$good_marker"
expect 1 notice "an entry with the wrong commit"
fresh; notice '- app/missing.py <- x.py@ea757c8'
expect 1 notice "an unreadable entry for a file that does not exist"
fresh; notice '- app/missing.py <- x.py@ea757c7'
expect 1 notice "an entry for a file that does not exist"
fresh; notice '- app/missing.json <- x.json@ea757c7'
expect 1 notice "an entry for a JSON file that does not exist"
fresh; notice '(none yet)'; put app/a.py "$good_marker"
expect 1 notice "a carried file that NOTICE does not list"
fresh; notice '- app/a.py <- graph.py@ea757c7'; put app/a.py 'x = 1\n'
expect 1 notice "a listed file without the comment"
fresh; notice '- app/a.py <- graph.py@ea757c7'; put app/a.py '# Carried from stfc/goldilocks-agent\nx = 1\n'
expect 1 notice "a comment without the source path and commit"
fresh; put NOTICE 'Carried files\n\n(none yet)\n'
expect 1 notice "NOTICE without the copyright line"

# --- md_links -------------------------------------------------------------------------------------------------
fresh; put a.md '# a\n'; put 'my file.md' '# b\n'
put docs/b.md '[1](../a.md) [2](/a.md) [3](<../a.md>) [4](../a.md?plain=1) [5](../a.md "title")
[6](../a.md#part) [7](#here) [8](https://example.org/x.md) [9](../my%20file.md)
Code is not a link: `[c](missing.md)` and
```
funcs[0](arg) [e](missing.md)
```
'
expect 0 md_links "valid links, and link-like text in code"
fresh; put a.md '[x](missing.md)\n'
expect 1 md_links "a broken relative link"
fresh; put docs/a.md '[x](/missing.md)\n'
expect 1 md_links "a broken link from the repository root"

if [ "$fail" -eq 0 ]; then echo "check tests: ok ($count cases)"; exit 0; fi
echo "check tests: FAILED"; exit 1
