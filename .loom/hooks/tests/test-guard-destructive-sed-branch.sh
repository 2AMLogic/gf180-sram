#!/usr/bin/env bash
# Test suite for the `sed` branch of extract_write_targets() in
# .loom/hooks/guard-destructive-generic.sh (issue #49).
#
# Usage: ./.loom/hooks/tests/test-guard-destructive-sed-branch.sh
#
# Covers the #49 false-DENY: a BSD/macOS `sed -i EXTENSION SCRIPT FILE`
# invocation (the `-i ''` / `-i ""` "no backup" idiom this repo's own SPICE
# testbench-editing pattern uses) passes its mandatory extension argument as
# a SEPARATE token from the script -- unlike GNU sed's attached-only
# `-i[SUFFIX]` form. The sed branch's stock assumption ("the first non-flag
# argument after `-i` is always the sed SCRIPT, skip only that one") then
# misidentifies the extension as the script-to-skip and lets the REAL script
# text leak through as a phantom write-target candidate. If the script text
# happens to contain a `../`-shaped substring (common in prose-like
# replacement text, and this repo's own `.include '../../../design/netlist/
# ...'`-style SPICE path rewriting), resolving that phantom candidate can
# walk outside the worktree and produce a false DENY that names a garbled
# script fragment instead of the real, safe write target.
#
# This suite asserts:
#   - the exact minimal reproduction from #49 is now ALLOWED
#   - the exact real-world SPICE `.include` rewrite pattern from the two
#     logged denials (2026-08-17T01:16:49Z / 01:45:51Z) is now ALLOWED
#   - both cited "control" shapes (space-no-.. / ..-no-space) stay/become
#     ALLOWED
#   - the GNU-style attached `-i` form (no separate extension argument),
#     which was already correct, is unchanged
#   - a GENUINE out-of-worktree write via the real file argument (not a
#     script-text fragment) still DENIES -- fail-closed is preserved
#
# The hook under test is copied into an isolated temp git tree (mirroring
# the .loom/worktrees/issue-<N> layout this guard inspects) so REPO_ROOT /
# the main-checkout root resolve there, never against the real repo. Exit
# 0 = all pass, 1 = fail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SRC_HOOK="$REPO_ROOT/.loom/hooks/guard-destructive-generic.sh"

PASS=0
FAIL=0
TOTAL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
git init -q "$TMPROOT"
git -C "$TMPROOT" config user.email "test@example.com"
git -C "$TMPROOT" config user.name "Test"
touch "$TMPROOT/README.md"
git -C "$TMPROOT" add README.md
git -C "$TMPROOT" commit -q -m "init"

mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
# Best-effort: stage the real config-resolver.sh so the guards.worktreeIsolation
# read exercises the actual tiered resolver rather than the source-missing
# fallback. Not fatal if absent -- the hook's own `source ... || true` covers it.
if [[ -f "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" ]]; then
    cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
fi
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

# --- Fixture: one managed worktree at $TMPROOT/.loom/worktrees/issue-1 -----
WT="$TMPROOT/.loom/worktrees/issue-1"
mkdir -p "$WT"
cat > "$WT/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF
echo "old text" > "$WT/README.md"

# Run the hook with COMMAND as the Bash tool_input.command and CWD as the
# acting session's cwd (the managed worktree, the canonical builder setup).
# Prints "<exit_code>|<stdout>".
run_hook() {
    local cmd="$1" cwd="$2"
    local exit_code=0 output
    output=$(jq -n --arg cmd "$cmd" --arg cwd "$cwd" \
        '{tool_name:"Bash", tool_input:{command:$cmd}, cwd:$cwd}' \
        | bash "$HOOK" 2>/dev/null) || exit_code=$?
    printf '%s|%s' "$exit_code" "$output"
}

assert_allow() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    local decision
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    if [[ "$code" == "0" && "$decision" != "deny" ]]; then
        pass "$desc"
    else
        fail "$desc (expected allow, got exit=$code output=$out)"
    fi
}

assert_deny() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with deny JSON, got NONZERO exit=$code)"
        return
    fi
    local decision
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    if [[ "$decision" == "deny" ]]; then
        pass "$desc"
    else
        fail "$desc (expected permissionDecision=deny, got: $out)"
    fi
}

echo "=== guard-destructive-generic.sh sed-branch tests (#49) ==="

# (A) Exact minimal reproduction from #49: BSD `-i ""`, script contains a
# space AND a `../`-shaped substring, real target is a literal in-worktree
# file. Must now ALLOW (was falsely DENIED before the fix).
result=$(run_hook 'sed -i "" "s|old text|../../../etc/passwd|" README.md' "$WT")
assert_allow "(A) minimal repro: BSD -i \"\", space+../ in script, real in-worktree target -> allow" "$result"

# (B) Exact real-world SPICE .include rewrite pattern from the two logged
# denials (2026-08-17T01:16:49Z / 01:45:51Z, Builder work on issue #24).
result=$(run_hook "sed -i '' \"s|\\.include '\\.\\./\\.\\./\\.\\./design/netlist/bitcell_6t\\.spice'|.include '@@REPO_ROOT@@/design/netlist/bitcell_6t.spice'|\" README.md" "$WT")
assert_allow "(B) real-world SPICE .include rewrite pattern -> allow" "$result"

# (C) Control: BSD -i \"\" with a ../-shaped substring but NO space in the
# script. Must ALLOW (this was already a latent false-deny too -- the #49
# report's own control-test claim about this shape not denying does not hold
# against direct hook replay; both shapes are fixed by the same change).
result=$(run_hook 'sed -i "" "s|old|../../../etc/passwd|" README.md' "$WT")
assert_allow "(C) BSD -i \"\" script with ../ but no space -> allow" "$result"

# (D) Control: BSD -i \"\" with a space but no ../ in the script. Was already
# allowed; must stay allowed (no regression).
result=$(run_hook 'sed -i "" "s|old text|newtext|" README.md' "$WT")
assert_allow "(D) BSD -i \"\" script with space but no ../ -> allow (unchanged)" "$result"

# (E) Control: GNU-style attached -i (no separate extension argument). Was
# already correct; must stay unchanged.
result=$(run_hook 'sed -i "s|old text|../../../etc/passwd|" README.md' "$WT")
assert_allow "(E) GNU-style sed -i (no separate extension argument) -> allow (unchanged)" "$result"

# (F) Fail-closed check: a GENUINE out-of-worktree write via the REAL file
# argument (not a script-text fragment) must still DENY.
result=$(run_hook 'sed -i "" "s|a|b|" ../../../etc/passwd' "$WT")
assert_deny "(F) genuine out-of-worktree file target still denied (fail-closed)" "$result"

# (G) Fail-closed check: same as (F) but with multiple file targets after
# the script -- every real file argument must still be scanned.
result=$(run_hook 'sed -i "" "s|old text|foo|" a.txt ../../../etc/passwd' "$WT")
assert_deny "(G) genuine out-of-worktree target among multiple file args still denied" "$result"

# (H) Fail-closed check: BSD -i \"\" with only ONE non-flag argument after
# the extension (ambiguous -- could be a GNU-style empty script + file, or a
# malformed BSD invocation). The fix must never WIDEN the skip in this
# under-determined 2-arg case, so an out-of-worktree target here still
# denies exactly as before the fix.
result=$(run_hook 'sed -i "" ../../../etc/passwd' "$WT")
assert_deny "(H) 2-arg -i \"\" <out-of-worktree file> still denied (skip_first not widened)" "$result"

# (I) Deny reason names the REAL target, not a script fragment, when a
# genuine escape occurs (F above) -- confirms the fix corrects candidacy,
# not just the verdict.
raw=$(run_hook 'sed -i "" "s|a|b|" ../../../etc/passwd' "$WT")
out="${raw#*|}"
reason=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null || true)
if [[ "$reason" == *"etc/passwd"* && "$reason" != *"s|a|b|"* ]]; then
    pass "(I) deny reason names the real file target, not the sed script text"
else
    fail "(I) deny reason names the real file target, not the sed script text (got: $reason)"
fi

echo
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
