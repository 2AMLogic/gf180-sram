#!/usr/bin/env bash
# Test suite for the Bash-tool write-confinement scan in
# guard-destructive-generic.sh -- specifically the leading shell-keyword
# strip (do/then/else/elif/{) applied before the write-idiom scan
# (gf180-sram issue #67).
#
# Usage: ./.loom/hooks/tests/test-guard-write-confinement-keyword.sh
#
# Background: extract_write_targets() splits a command into segments on
# `;`/`&&`/`||`/newline (qsplit()), then keys every write-idiom branch
# (tee/sed -i/cp/mv) on toks[1], the FIRST whitespace-split token of the
# segment. A one-line compound statement puts a shell keyword -- `do`,
# `then`, `else`, `elif`, or a brace-group opener `{` -- in that first-token
# position instead of the real command word:
#
#   for f in x; do sed -i "" "s|a|b|" /main/checkout/f.spice; done
#   if true; then sed -i "" "s|a|b|" /main/checkout/f.spice; fi
#
# Both reach the scan as a segment whose toks[1] is literally "do"/"then",
# so none of the tee/sed/cp/mv branches ever match and the write target is
# silently missed -- a #4178 worktree-write-confinement BYPASS an agent
# denied on Edit/Write could retry through Bash. The identical command with
# its body on its own line (not one-line) was already correctly denied,
# since there the keyword and the body land in DIFFERENT segments and the
# body segment's toks[1] IS the real command word.
#
# The fix strips a leading do/then/else/elif/{ from each segment before the
# write-idiom scan, mirroring the existing leading-`sudo` strip a few lines
# above in extract_write_targets(). This suite pins:
#   (a) the exact one-line bypass repros from #67 now deny,
#   (b) other one-line compound-keyword shapes (else, elif, brace-group,
#       nested sudo) also deny,
#   (c) ordinary compound commands using these same keywords that should
#       stay ALLOWED are not broken by the new stripping,
#   (d) unrelated write-confinement behaviour (multi-line form, plain
#       commands) is unchanged.
#
# Hermetic: the hook under test is copied into an isolated `mktemp -d` git
# tree (so its REPO_ROOT, error log and decision log all resolve there) and
# driven purely via stdin JSON. No forge, no network. Exit 0 = all pass.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source of truth: `defaults/` in the Loom source repo, the installed
# `.loom/hooks/` copy in a consumer repo. Prefer defaults/ so this suite can
# be lifted upstream verbatim.
if [[ -f "$REPO_ROOT/defaults/hooks/guard-destructive-generic.sh" ]]; then
    SRC_HOOK="$REPO_ROOT/defaults/hooks/guard-destructive-generic.sh"
    SRC_LIB_DIR="$REPO_ROOT/defaults/scripts/lib"
else
    SRC_HOOK="$REPO_ROOT/.loom/hooks/guard-destructive-generic.sh"
    SRC_LIB_DIR="$REPO_ROOT/.loom/scripts/lib"
fi

if [[ ! -f "$SRC_HOOK" ]]; then
    echo "SKIP: guard-destructive-generic.sh not found (looked at $SRC_HOOK)"
    exit 0
fi
for tool in jq git awk; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "SKIP: required tool '$tool' not available"
        exit 0
    fi
done

PASS=0
FAIL=0
TOTAL=0
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

# --- isolated fixture repo ---------------------------------------------------
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

MAIN="$TMPROOT/repo"
mkdir -p "$MAIN/sim" "$MAIN/.loom/hooks" "$MAIN/.loom/scripts/lib"
cp "$SRC_HOOK" "$MAIN/.loom/hooks/guard-destructive-generic.sh"
[[ -f "$SRC_LIB_DIR/config-resolver.sh" ]] && \
    cp "$SRC_LIB_DIR/config-resolver.sh" "$MAIN/.loom/scripts/lib/config-resolver.sh"
HOOK="$MAIN/.loom/hooks/guard-destructive-generic.sh"

git -C "$MAIN" init -q . >/dev/null 2>&1
git -C "$MAIN" symbolic-ref HEAD refs/heads/main >/dev/null 2>&1
printf 'x\n' > "$MAIN/sim/a.spice"
printf 'fixture\n' > "$MAIN/CLAUDE.md"
git -C "$MAIN" add -A >/dev/null 2>&1
git -C "$MAIN" -c user.email=t@example.invalid -c user.name=test commit -qm init >/dev/null 2>&1

WT="$MAIN/.loom/worktrees/issue-67"
git -C "$MAIN" worktree add -q "$WT" -b feature/issue-67-fixture >/dev/null 2>&1
touch "$WT/.loom-managed"
if ! git -C "$MAIN" rev-parse HEAD >/dev/null 2>&1 || [[ ! -f "$WT/.loom-managed" ]]; then
    echo "SKIP: could not build the main-checkout + managed-worktree fixture"
    exit 0
fi

# Run the hook with the given cwd + command. Echoes the permissionDecision
# ("allow" when the hook stays silent, which is its allow contract).
run_guard() {
    local cwd="$1" cmd="$2" out rc=0
    out=$(jq -n --arg cwd "$cwd" --arg cmd "$cmd" \
            '{cwd:$cwd, tool_name:"Bash", tool_input:{command:$cmd}}' \
          | env -u LOOM_FORCE_SCOPE -u LOOM_GUARD_DECISION_LOG \
                bash "$HOOK" 2>/dev/null) || rc=$?
    if [[ "$rc" -ne 0 ]]; then
        printf 'HOOK-EXIT-%s' "$rc"   # fail-open contract violation
        return
    fi
    if [[ -z "$out" ]]; then
        printf 'allow'
        return
    fi
    printf '%s' "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "malformed"')"
}

assert_decision() {
    local desc="$1" expected="$2" got="$3"
    if [[ "$got" == "$expected" ]]; then
        pass "$desc"
    else
        fail "$desc (expected $expected, got $got)"
    fi
}

# --- (a) exact #67 one-line bypass repros now deny -----------------------
assert_decision "(a1) one-line for/do sed -i into main checkout -> deny" \
    deny "$(run_guard "$MAIN" "for f in x; do sed -i \"\" \"s|a|b|\" $MAIN/CLAUDE.md; done")"

assert_decision "(a2) one-line if/then sed -i into main checkout -> deny" \
    deny "$(run_guard "$MAIN" "if true; then sed -i \"\" \"s|a|b|\" $MAIN/CLAUDE.md; fi")"

# --- (b) other one-line compound-keyword shapes also deny -----------------
assert_decision "(b1) one-line if/then/else, write in the else branch -> deny" \
    deny "$(run_guard "$MAIN" "if false; then :; else sed -i \"\" \"s|a|b|\" $MAIN/CLAUDE.md; fi")"

assert_decision "(b2) one-line if/elif, write in the elif branch -> deny" \
    deny "$(run_guard "$MAIN" "if false; then :; elif true; then sed -i \"\" \"s|a|b|\" $MAIN/CLAUDE.md; fi")"

assert_decision "(b3) one-line brace-group write into the main checkout -> deny" \
    deny "$(run_guard "$MAIN" "{ sed -i \"\" \"s|a|b|\" $MAIN/CLAUDE.md; }")"

assert_decision "(b4) one-line for/do with sudo-prefixed write -> deny" \
    deny "$(run_guard "$MAIN" "for f in x; do sudo sed -i \"\" \"s|a|b|\" $MAIN/CLAUDE.md; done")"

assert_decision "(b5) one-line for/do tee redirection into the main checkout -> deny" \
    deny "$(run_guard "$MAIN" "for f in x; do echo y | tee $MAIN/CLAUDE.md; done")"

assert_decision "(b6) one-line for/do cp into the main checkout -> deny" \
    deny "$(run_guard "$MAIN" "for f in x; do cp /tmp/src $MAIN/CLAUDE.md; done")"

assert_decision "(b7) one-line for/do redirection idiom (>) into the main checkout -> deny" \
    deny "$(run_guard "$MAIN" "for f in x; do echo y > $MAIN/CLAUDE.md; done")"

# --- (c) ordinary compound commands using these keywords stay ALLOWED -----
assert_decision "(c1) one-line for/do sed -i, in-worktree relative target -> allow" \
    allow "$(run_guard "$WT" "for f in sim/a.spice; do sed -i '' 's|a|b|' \"\$f\"; done")"

assert_decision "(c2) one-line if/then write, in-worktree relative target -> allow" \
    allow "$(run_guard "$WT" "if true; then sed -i '' 's|a|b|' sim/a.spice; fi")"

assert_decision "(c3) one-line if/then/else write, in-worktree relative target -> allow" \
    allow "$(run_guard "$WT" "if false; then :; else sed -i '' 's|a|b|' sim/a.spice; fi")"

assert_decision "(c4) one-line brace-group write, in-worktree relative target -> allow" \
    allow "$(run_guard "$WT" "{ sed -i '' 's|a|b|' sim/a.spice; }")"

assert_decision "(c5) one-line for/do write to an out-of-repo scratch path -> allow" \
    allow "$(run_guard "$MAIN" "for f in x; do echo y > $TMPROOT/scratch.txt; done")"

assert_decision "(c6) one-line for/do, no write idiom at all (read-only body) -> allow" \
    allow "$(run_guard "$MAIN" "for f in x; do echo \"\$f\"; done")"

assert_decision "(c7) one-line if/then, no write idiom at all -> allow" \
    allow "$(run_guard "$MAIN" "if true; then git status --short; fi")"

# --- (d) unrelated write-confinement behaviour is unchanged ---------------
assert_decision "(d1) multi-line for/do sed -i into main checkout -> deny (already correct)" \
    deny "$(run_guard "$MAIN" "for f in x; do
  sed -i \"\" \"s|a|b|\" $MAIN/CLAUDE.md
done")"

assert_decision "(d2) plain (non-compound) sed -i into main checkout -> deny" \
    deny "$(run_guard "$MAIN" "sed -i '' 's|a|b|' $MAIN/CLAUDE.md")"

assert_decision "(d3) plain (non-compound) sed -i, in-worktree relative target -> allow" \
    allow "$(run_guard "$WT" "sed -i '' 's|a|b|' sim/a.spice")"

assert_decision "(d4) plain read-only command -> allow" \
    allow "$(run_guard "$WT" "git status --short")"

echo "=== $PASS/$TOTAL passed ==="
[[ "$FAIL" -eq 0 ]]
