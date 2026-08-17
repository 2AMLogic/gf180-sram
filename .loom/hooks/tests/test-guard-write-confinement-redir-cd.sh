#!/usr/bin/env bash
# Test suite for two write-confinement false positives (and one confinement
# BYPASS) in guard-destructive-generic.sh's extract_write_targets() (gf180-sram
# issue #68), found while reproducing #63:
#
#   1. `>`/`>>` redirection tokens (bare `>`, attached `2>/dev/null`, etc.) had
#      no exclusion analogous to the `<` `stdin_redir` exclusion (#5369), so
#      `tee`/`sed -i`/`cp`/`mv` misread a trailing redirection as one of their
#      own operands:
#        - tee/sed -i: a phantom EXTRA target (e.g. `<repo>/2>/dev/null`),
#          false-DENYing an otherwise-harmless command.
#        - cp/mv (which pick the LAST non-flag token as the destination): the
#          redirection token could DISPLACE the real destination entirely --
#          a genuine #4178 worktree-confinement BYPASS, not just a false deny
#          (mirrors the "false ALLOW" half of the #5369 `<` fix).
#
#   2. The `cd` branch never ran the SAME-COMMAND `resolve_var()` resolution
#      (#4881) already applied to write-idiom TARGETS, so `cd "$SB/repo"`
#      threaded the RAW, unresolved token into curcwd even when `$SB` was
#      assigned earlier in the same command -- misjudging an out-of-repo `cd`
#      destination as in-repo and denying a write that never lands in the
#      main checkout.
#
# This suite pins:
#   (a) the issue's five exact repro commands -> allow
#   (b) the cp/mv confinement BYPASS this fix closes -> deny (the important
#       anti-regression case: a real main-checkout destination must not be
#       displaced by a following `>`/`2>` redirection)
#   (c) `cd` fail-closed cases (AMBIG/conflicting reassignment, wholly
#       unresolved var, a resolved var landing INSIDE the repo) -> deny
#   (d) edge cases from the issue's Test Plan (dup-to-fd, multiple redirects,
#       a literal `$FOO`-named directory) -> unaffected
#   (e) unrelated write-confinement / `<`-exclusion behaviour -> unchanged
#
# Hermetic: the hook under test is copied into an isolated `mktemp -d` git
# tree with a `.loom-managed` worktree fixture, driven purely via stdin JSON.
# No forge, no network. Exit 0 = all pass.

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
printf 'fixture\n' > "$MAIN/CLAUDE.md"
git -C "$MAIN" add -A >/dev/null 2>&1
git -C "$MAIN" -c user.email=t@example.invalid -c user.name=test commit -qm init >/dev/null 2>&1

WT="$MAIN/.loom/worktrees/issue-68"
git -C "$MAIN" worktree add -q "$WT" -b feature/issue-68 >/dev/null 2>&1
touch "$WT/.loom-managed"
mkdir -p "$WT/sim"
touch "$WT/a" "$WT/b" "$WT/sim/a.spice"
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

echo "=== guard-destructive-generic.sh >/>> exclusion + cd resolve_var() tests (#68) ==="

# --- (a) the issue's five exact repro commands, from inside the worktree ----
assert_decision "(a1) cp a b/ 2>/dev/null -> allow" \
    allow "$(run_guard "$WT" "cp a b/ 2>/dev/null")"

assert_decision "(a2) mv a b >log -> allow" \
    allow "$(run_guard "$WT" "mv a b >log")"

assert_decision "(a3) tee f 2>/dev/null -> allow" \
    allow "$(run_guard "$WT" "tee f 2>/dev/null")"

assert_decision '(a4) sed -i "" "s/a/b/" f 2>/dev/null -> allow' \
    allow "$(run_guard "$WT" 'sed -i "" "s/a/b/" f 2>/dev/null')"

assert_decision '(a5) SB=/tmp/scratch; cd "$SB/repo"; echo x > sim/a.spice -> allow' \
    allow "$(run_guard "$WT" "SB=$TMPROOT/scratch
cd \"\$SB/repo\"
echo x > sim/a.spice")"

# --- (b) the cp/mv confinement BYPASS this fix closes -----------------------
# Before the fix, the trailing `>`/`2>` redirection could displace the REAL
# cp/mv destination -- a genuine worktree-isolation bypass, not just a false
# deny. The real destination here is inside the MAIN checkout and must still
# be caught.
assert_decision "(b1) cp a <main-checkout>/evil.sh 2>/dev/null -> deny (no bypass)" \
    deny "$(run_guard "$WT" "cp a $MAIN/evil.sh 2>/dev/null")"

assert_decision "(b2) mv a <main-checkout>/evil2.sh >log -> deny (no bypass)" \
    deny "$(run_guard "$WT" "mv a $MAIN/evil2.sh >log")"

assert_decision "(b3) a genuine cp destination inside the main checkout, no redirection at all -> deny (unchanged)" \
    deny "$(run_guard "$WT" "cp a $MAIN/evil3.sh")"

assert_decision "(b4) tee <main-checkout>/evil.sh 2>/dev/null -> deny (the real tee target is still scanned)" \
    deny "$(run_guard "$WT" "tee $MAIN/evil.sh 2>/dev/null")"

assert_decision "(b5) sed -i '' 's|a|b|' <main-checkout file> 2>/dev/null -> deny (real sed target still scanned)" \
    deny "$(run_guard "$WT" "sed -i '' 's|a|b|' $MAIN/CLAUDE.md 2>/dev/null")"

# --- (c) `cd` fail-closed cases ----------------------------------------------
assert_decision "(c1) cd \$A where A conflicts (A=<in-repo> || A=/tmp/outside) -> deny (AMBIG, fail closed)" \
    deny "$(run_guard "$WT" "A=$MAIN/sub || A=$TMPROOT/outside
cd \"\$A/repo\"
echo x > sim/a.spice")"

assert_decision "(c2) cd \$A where A is reassigned a DIFFERENT value (A=x; A=y) -> deny (fail closed)" \
    deny "$(run_guard "$WT" "A=$MAIN/subx
A=$TMPROOT/outsidey
cd \"\$A/repo\"
echo x > sim/a.spice")"

assert_decision "(c3) cd \$NOPE with NO assignment at all -> deny (fail closed, unchanged #4921)" \
    deny "$(run_guard "$WT" 'cd "$NOPE/repo"
echo x > sim/a.spice')"

assert_decision "(c4) cd \$SB resolves INSIDE the repo -> a later ../ escape into the main checkout still denies" \
    deny "$(run_guard "$WT" "SB=$MAIN
cd \"\$SB/sim\"
echo x > ../CLAUDE.md")"

assert_decision "(c5) cd \$SB resolves to the MAIN checkout -> a relative write there still denies (curcwd correctly followed the resolved cd, this is a genuine main-checkout write)" \
    deny "$(run_guard "$WT" "SB=$MAIN
cd \"\$SB/sim\"
echo x > a.spice")"

# --- (d) edge cases from the issue's Test Plan -------------------------------
assert_decision "(d1) dup-to-fd: cp a b >&2 (no main-checkout path involved) -> allow" \
    allow "$(run_guard "$WT" "cp a b >&2")"

assert_decision "(d2) multiple redirects: mv a b/ 2>/dev/null 1>/dev/null -> allow" \
    allow "$(run_guard "$WT" "mv a b/ 2>/dev/null 1>/dev/null")"

assert_decision "(d3) literal single-quoted \$FOO-named directory, no matching assignment -> unaffected (allow, in-worktree write)" \
    allow "$(run_guard "$WT" "cd '\$FOO/sub'
echo x > sim/a.spice")"

# --- (e) unrelated write-confinement / pre-existing `<` behaviour unchanged -
assert_decision "(e1) tee f < /tmp/in (pre-existing #5369 stdin exclusion) -> allow" \
    allow "$(run_guard "$WT" "tee f < $TMPROOT/in")"

assert_decision "(e2) cp /tmp/a <main-checkout>/p.sh < /tmp/in (pre-existing #5369 bypass fix) -> deny" \
    deny "$(run_guard "$WT" "cp $TMPROOT/a $MAIN/p.sh < $TMPROOT/in")"

assert_decision "(e3) plain read-only command -> allow" \
    allow "$(run_guard "$WT" "git status --short")"

assert_decision "(e4) absolute write into the main checkout, no redirection idiom -> deny" \
    deny "$(run_guard "$WT" "echo x > $MAIN/CLAUDE.md")"

assert_decision "(e5) absolute scratch write outside the repo -> allow" \
    allow "$(run_guard "$WT" "echo x > $TMPROOT/scratch.txt")"

echo "=== $PASS/$TOTAL passed ==="
[[ "$FAIL" -eq 0 ]]
