#!/usr/bin/env bash
# Test suite for the pdk_env.sh-sourced / mktemp -d / same-command rm -rf
# scratch-var exemption in extract_write_targets()'s write-confinement block,
# .loom/hooks/guard-destructive-generic.sh (issue #64).
#
# Usage: ./.loom/hooks/tests/test-guard-worktree-unresolved-var-pdk-env.sh
#
# Background: the `worktree-write-confinement-unresolved-var` catastrophic
# deny fires on ANY Bash-tool write target whose path root is an unexpanded
# shell variable the guard cannot statically resolve -- a reasonable
# default, but it blocked this repo's own documented "cold-start ngspice
# invocation" (sim/README.md):
#
#   scratch=$(mktemp -d) && \
#   source sim/lib/pdk_env.sh && \
#   cp testbench.spice "$scratch/" && cat > "$scratch/corner.inc" <<EOF
#   ...
#   EOF
#   ngspice -b -o out.log ... ; rm -rf "$scratch"
#
# Replaying the issue's exact reproduction against this hook shows the deny
# actually fires on `$scratch` (assigned via `scratch=$(mktemp -d)`), not on
# `$GF180_DESIGN_INC`/`$GF180_MODEL_FILE` -- those only ever appear inside the
# `cat > ... <<EOF` heredoc BODY, which extract_write_targets() already masks
# out before the scan ever sees them. The fix narrows the deny for exactly
# this shape: a variable that is (1) assigned via a literal `NAME=$(mktemp
# ... -d ...)` command substitution AND (2) later `rm -rf`'d WHOLE (not a
# subpath) in the SAME command, gated on the SAME command also sourcing this
# repo's own sim/lib/pdk_env.sh (`source` or `.` form) -- never a general
# unresolved-var allow.
#
# This suite asserts:
#   - the exact minimal reproduction from #64 is now ALLOWED (both the
#     `source` and POSIX `.` sourcing spellings, and both `$scratch`/
#     `${scratch}` reference spellings)
#   - a trailing-slash `rm -rf "$scratch/"` self-clean still counts
#   - a GENUINE out-of-worktree write via an unrelated unresolved var (no
#     mktemp -d, no pdk_env.sh) still DENIES -- fail-closed is preserved
#   - a mktemp -d + same-command rm -rf scratch write with NO pdk_env.sh
#     source still DENIES (Safety Note: the exemption is not a general
#     mktemp+rm-rf allow)
#   - a pdk_env.sh-sourced, mktemp -d scratch write with NO same-command
#     rm -rf cleanup still DENIES (no self-clean guarantee -> no exemption)
#   - a pdk_env.sh-sourced, mktemp -d + rm -rf command whose WRITE TARGET
#     uses a *different*, untracked unresolved var still DENIES (the
#     exemption is per-variable, not per-command)
#   - `rm -rf` on a SUBPATH of the scratch dir (not the whole directory)
#     does not count as self-cleaning -> still DENIES
#   - PR #65 review regressions: the exemption must never skip path
#     confinement, only the "unresolved variable" deny REASON --
#       * `..` traversal AFTER the exempted variable that escapes the
#         scratch dir and lands in the main checkout still DENIES
#       * `mktemp -d -p <protected-area>` / `--tmpdir=` / a same-command
#         `TMPDIR=<protected-area>` (which make the "scratch lands outside
#         the guarded tree" assumption unsound) still DENY
#       * a `..` that stays INSIDE the scratch dir is still ALLOWED (the
#         re-validation is a confinement check, not a blanket `..` ban)
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

# --- Fixture: one managed worktree at $TMPROOT/.loom/worktrees/issue-24,
# mirroring the exact layout the #64 reproduction ran in. -------------------
WT="$TMPROOT/.loom/worktrees/issue-24"
mkdir -p "$WT/sim/read-snm/testbench" "$WT/sim/read-snm/records" "$WT/sim/lib"
cat > "$WT/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF
echo "x" > "$WT/sim/read-snm/testbench/tb_read_snm.spice"
echo "tt_25c_3.30v foo" > "$WT/sim/read-snm/records/r1.md"
echo "# stand-in for the real pdk_env.sh -- content is irrelevant to the" \
     "guard, which only pattern-matches the source/. line, never executes it" \
     > "$WT/sim/lib/pdk_env.sh"

# Run the hook with COMMAND as the Bash tool_input.command and CWD as the
# acting session's cwd (the managed worktree, the canonical builder setup).
# Command text is passed via a temp file + --rawfile so multi-line heredoc
# commands survive intact. Prints "<exit_code>|<stdout>".
run_hook() {
    local cmdfile="$1" cwd="$2"
    local exit_code=0 output
    output=$(jq -n --rawfile cmd "$cmdfile" --arg cwd "$cwd" \
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

echo "=== guard-destructive-generic.sh pdk_env.sh scratch-var exemption tests (#64) ==="

CMDDIR="$TMPROOT/cmds"
mkdir -p "$CMDDIR"

# (A) Exact reproduction from #64. Must now ALLOW (was falsely DENIED before
# the fix).
cat > "$CMDDIR/A.txt" <<'EOF'
cd /tmp/wt && \
scratch=$(mktemp -d) && \
source sim/lib/pdk_env.sh && \
cp sim/read-snm/testbench/tb_read_snm.spice "$scratch/" && \
cat > "$scratch/corner.inc" <<CORNERINC
.include '$GF180_DESIGN_INC'
.lib '$GF180_MODEL_FILE' typical
.temp 25
.param VDDC=3.30
CORNERINC
(cd "$scratch" && ngspice -b -o out.log tb_read_snm.spice; echo "exit=$?")
python3 sim/lib/snm_extract.py "$scratch/read_snm_sweep.txt" read_snm
echo "--- committed record value for tt_25c_3.30v ---"
grep "tt_25c_3.30v" -A0 sim/read-snm/records/*.md
rm -rf "$scratch"
EOF
sed -i "s#/tmp/wt#$WT#" "$CMDDIR/A.txt"
result=$(run_hook "$CMDDIR/A.txt" "$WT")
assert_allow "(A) exact #64 reproduction (source, cp+cat targets, trailing rm -rf) -> allow" "$result"

# (B) POSIX `.` sourcing spelling instead of `source`.
cat > "$CMDDIR/B.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && . sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/B.txt" "$WT")
assert_allow "(B) POSIX '.' sourcing spelling -> allow" "$result"

# (C) Braced \${scratch} reference + trailing-slash rm -rf "\$scratch/" self-clean.
cat > "$CMDDIR/C.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\${scratch}/" && rm -rf "\$scratch/"
EOF
result=$(run_hook "$CMDDIR/C.txt" "$WT")
assert_allow "(C) braced \${scratch} target + trailing-slash rm -rf self-clean -> allow" "$result"

# (D) Fail-closed control: a GENUINE out-of-worktree write via an unrelated
# unresolved var (no mktemp -d, no pdk_env.sh anywhere) must still DENY.
cat > "$CMDDIR/D.txt" <<EOF
cd $WT && dest=\$(get_dest) && echo "x" > "\$dest/evil.sh"
EOF
result=$(run_hook "$CMDDIR/D.txt" "$WT")
assert_deny "(D) unrelated unresolved var, no mktemp/pdk_env -> still deny (fail-closed)" "$result"

# (E) mktemp -d + same-command rm -rf, but NO pdk_env.sh source anywhere ->
# must still DENY (Safety Note: not a general mktemp+rm-rf allow).
cat > "$CMDDIR/E.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/E.txt" "$WT")
assert_deny "(E) mktemp -d + rm -rf but no pdk_env.sh source -> still deny" "$result"

# (F) pdk_env.sh sourced + mktemp -d, but NO same-command rm -rf cleanup ->
# must still DENY (no self-clean guarantee, no exemption).
cat > "$CMDDIR/F.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/"
EOF
result=$(run_hook "$CMDDIR/F.txt" "$WT")
assert_deny "(F) pdk_env.sh sourced + mktemp -d, no rm -rf -> still deny" "$result"

# (G) pdk_env.sh sourced + mktemp -d + rm -rf on \$scratch, but the WRITE
# TARGET uses a *different*, untracked unresolved var (\$dest) -> the
# exemption is per-variable, must still DENY.
cat > "$CMDDIR/G.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && dest=\$(get_other) && cp sim/read-snm/testbench/tb_read_snm.spice "\$dest/" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/G.txt" "$WT")
assert_deny "(G) different untracked unresolved var as write target -> still deny" "$result"

# (H) pdk_env.sh sourced + mktemp -d, rm -rf on a SUBPATH of scratch (not the
# whole directory) -- does not count as self-cleaning -> must still DENY.
cat > "$CMDDIR/H.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/" && rm -rf "\$scratch/subdir"
EOF
result=$(run_hook "$CMDDIR/H.txt" "$WT")
assert_deny "(H) rm -rf on a scratch SUBPATH only (not the whole dir) -> still deny" "$result"

# (I) A write target unrelated to \$scratch entirely, in a command that
# otherwise matches the pattern -- confirms the exemption is scoped to the
# marked variable actually at the target's path root, not "any command that
# looks like this repo's sim pattern".
cat > "$CMDDIR/I.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && echo "x" > /tmp/not-a-worktree-path-but-literal.txt && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/I.txt" "$WT")
assert_allow "(I) unrelated LITERAL /tmp write target (not the guard's concern here) -> allow" "$result"

# --- PR #65 review regressions ------------------------------------------------
# (J) Path traversal AFTER the exempted variable. Every ingredient is genuine
# (real mktemp -d, real pdk_env.sh source, real trailing rm -rf that only
# removes the now-empty scratch dir), but the `..` segments walk the write
# straight back out of the scratch dir and into the MAIN CHECKOUT's README.md.
# The exemption must only skip the "unresolved variable" deny reason, never
# path confinement -> must DENY.
cat > "$CMDDIR/J.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && echo PWNED > "\$scratch/../../../../../../..$TMPROOT/README.md" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/J.txt" "$WT")
assert_deny "(J) '..' traversal after the exempted var into the main checkout -> deny" "$result"

# (K) `mktemp -d -p <main-checkout-root>` points the "self-cleaning scratch
# dir" INSIDE the protected area, so the exemption's core assumption (the
# scratch dir lands outside the guarded tree) no longer holds -> must DENY.
cat > "$CMDDIR/K.txt" <<EOF
cd $WT && scratch=\$(mktemp -d -p $TMPROOT) && source sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/K.txt" "$WT")
assert_deny "(K) mktemp -d -p <protected area> as the scratch parent -> deny" "$result"

# (K2) Same, via the long spelling `--tmpdir=<main-checkout-root>`.
cat > "$CMDDIR/K2.txt" <<EOF
cd $WT && scratch=\$(mktemp -d --tmpdir=$TMPROOT) && source sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/K2.txt" "$WT")
assert_deny "(K2) mktemp -d --tmpdir=<protected area> as the scratch parent -> deny" "$result"

# (K3) Same, via a positional TEMPLATE argument naming a directory inside the
# protected area (`mktemp -d <main-root>/XXXXXX`) -- no flag involved at all.
cat > "$CMDDIR/K3.txt" <<EOF
cd $WT && scratch=\$(mktemp -d $TMPROOT/scratch.XXXXXX) && source sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/K3.txt" "$WT")
assert_deny "(K3) mktemp -d <protected area>/XXXXXX positional template -> deny" "$result"

# (L) A same-command `TMPDIR=<main-checkout-root>` assignment redirects a bare
# `mktemp -d` into the protected area just as effectively as `-p` -> deny.
cat > "$CMDDIR/L.txt" <<EOF
cd $WT && TMPDIR=$TMPROOT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/L.txt" "$WT")
assert_deny "(L) same-command TMPDIR= assignment redirecting mktemp -> deny" "$result"

# (M) Anti-over-correction control: a `..` segment that stays INSIDE the
# scratch dir resolves back under it, so the write is still confined and must
# remain ALLOWED. The fix is a confinement re-check, not a blanket `..` ban.
cat > "$CMDDIR/M.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && cp sim/read-snm/testbench/tb_read_snm.spice "\$scratch/sub/../corner.inc" && rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/M.txt" "$WT")
assert_allow "(M) '..' contained within the scratch dir -> still allow" "$result"

echo
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
