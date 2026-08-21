#!/usr/bin/env bash
# Test suite for the pdk_env.sh scratch-var exemption at the *rm-scope*
# unresolved-var deny site in .loom/hooks/guard-destructive-generic.sh
# (issue #82).
#
# Usage: ./.loom/hooks/tests/test-guard-rm-scope-unresolved-var-pdk-env.sh
#
# Background: the hook has TWO independent unresolved-`$`-var fail-closed
# denies that both fire on this repo's documented "cold-start ngspice
# invocation" (sim/README.md):
#
#   1. `worktree-write-confinement-unresolved-var` -- scans WRITE_TARGETS,
#      exempted for this idiom by #64/#65 (covered by the sibling suite
#      test-guard-worktree-unresolved-var-pdk-env.sh).
#   2. `rm-scope-unresolved-var` (guards.rmScope=repo, ON BY DEFAULT) --
#      scans RM_TARGETS, runs EARLIER in the file, and `deny()` exits the
#      hook immediately. Every real invocation of the idiom ends with
#      `rm -rf "$scratch"`, so this deny fired first and the #64/#65
#      exemption was never reached under the default guard config: the
#      restoration was correct but completely masked (#82).
#
# This suite exercises deny site (2) IN ISOLATION: every command below is
# deliberately free of the `>`/`tee`/`sed`/`cp `/`mv ` idioms that gate the
# Bash-write-confinement block, so the only check that can fire is the
# rm-scope one. A regression that re-broke site (2) while leaving site (1)
# intact would keep the sibling suite green and fail here.
#
# It asserts:
#   - the cold-start idiom's trailing `rm -rf "$scratch"` (and the
#     trailing-slash `"$scratch/"` spelling, and the POSIX `.` sourcing
#     spelling) is ALLOWED
#   - an unrelated unresolved-var rm target (no pdk_env.sh, no mktemp -d)
#     still DENIES -- the pre-existing fail-closed behaviour is intact
#   - mktemp -d + rm -rf with NO pdk_env.sh source still DENIES
#   - `rm -rf "$scratch/subdir"` (a subpath, never the whole scratch dir)
#     still DENIES
#   - the mktemp-argument allowlist holds here too: `-p <protected>`,
#     `--tmpdir=<protected>`, a positional TEMPLATE under the protected
#     area, a same-command `TMPDIR=<protected>`, and an AMBIENT
#     `$TMPDIR=<protected>` inherited from the session (#97) all still DENY
#   - the exemption is PER-VARIABLE: a second, untracked unresolved var in
#     the same command still DENIES
#   - the PR #65 path-confinement re-validation applies at THIS site: a
#     `..` chain after the exempted var that escapes the scratch dir still
#     DENIES, while a `..` contained within it is still ALLOWED
#   - the exemption is PER-TARGET: a literal out-of-repo-scope rm target in
#     the very same (otherwise exempt) command still DENIES
#
# The hook under test is copied into an isolated temp git tree (mirroring
# the .loom/worktrees/issue-<N> layout this guard inspects) so REPO_ROOT /
# the main-checkout root resolve there, never against the real repo.
#
# Runs under the repo's DEFAULT guard config: guards.rmScope / LOOM_RM_SCOPE
# are deliberately NOT set here (the temp repo ships no .loom/config.json, so
# rm_scope_repo_enabled() resolves to its "repo" default) -- that is the whole
# point of #82. LOOM_RM_SCOPE is explicitly unset below so an ambient value
# inherited from a dispatching agent cannot silently neuter the suite.
#
# Exit 0 = all pass, 1 = fail.

set -euo pipefail

unset LOOM_RM_SCOPE || true

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
# Best-effort: stage the real config-resolver.sh so the guards.* reads exercise
# the actual tiered resolver rather than the source-missing fallback. Not fatal
# if absent -- the hook's own `source ... || true` covers it.
if [[ -f "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" ]]; then
    cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
fi
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

# --- Fixture: one managed worktree at $TMPROOT/.loom/worktrees/issue-24,
# mirroring the layout the #64/#82 reproduction ran in. --------------------
WT="$TMPROOT/.loom/worktrees/issue-24"
mkdir -p "$WT/sim/read-snm/testbench" "$WT/sim/read-snm/records" "$WT/sim/lib"
cat > "$WT/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF
echo "x" > "$WT/sim/read-snm/testbench/tb_read_snm.spice"
echo "# stand-in for the real pdk_env.sh -- content is irrelevant to the" \
     "guard, which only pattern-matches the source/. line, never executes it" \
     > "$WT/sim/lib/pdk_env.sh"

# Run the hook with COMMAND as the Bash tool_input.command and CWD as the
# acting session's cwd (the managed worktree, the canonical builder setup).
# Command text is passed via a temp file + --rawfile so the exact bytes
# survive intact. Prints "<exit_code>|<stdout>".
run_hook() {
    local cmdfile="$1" cwd="$2"
    local exit_code=0 output
    output=$(jq -n --rawfile cmd "$cmdfile" --arg cwd "$cwd" \
        '{tool_name:"Bash", tool_input:{command:$cmd}, cwd:$cwd}' \
        | bash "$HOOK" 2>/dev/null) || exit_code=$?
    printf '%s|%s' "$exit_code" "$output"
}

# As run_hook, but with an AMBIENT $TMPDIR ($3) in the hook's environment --
# the second half of the TMPDIR safety gate (a relocated temp root inherited
# from the session, with no `TMPDIR=` text in the command itself).
run_hook_tmpdir() {
    local cmdfile="$1" cwd="$2" ambient_tmpdir="$3"
    local exit_code=0 output
    output=$(jq -n --rawfile cmd "$cmdfile" --arg cwd "$cwd" \
        '{tool_name:"Bash", tool_input:{command:$cmd}, cwd:$cwd}' \
        | TMPDIR="$ambient_tmpdir" bash "$HOOK" 2>/dev/null) || exit_code=$?
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

# Deny, AND the deny reason must contain $3 -- so a test cannot pass on a
# deny from some unrelated check (in particular, these cases must deny at
# the rm-scope site, not at the write-confinement site).
assert_deny_because() {
    local desc="$1" result="$2" needle="$3"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with deny JSON, got NONZERO exit=$code)"
        return
    fi
    local decision reason
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    reason=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null || true)
    if [[ "$decision" != "deny" ]]; then
        fail "$desc (expected permissionDecision=deny, got: $out)"
    elif [[ "$reason" != *"$needle"* ]]; then
        fail "$desc (denied for the WRONG reason -- wanted '$needle', got: $reason)"
    else
        pass "$desc"
    fi
}

# Every rm-scope unresolved-var deny message carries this marker.
RMSCOPE="guards.rmScope=repo"

echo "=== guard-destructive-generic.sh rm-scope pdk_env.sh scratch-var exemption tests (#82) ==="

CMDDIR="$TMPROOT/cmds"
mkdir -p "$CMDDIR"

# (A) The documented cold-start idiom, reduced to the parts the rm-scope
# check sees: mktemp -d scratch + pdk_env.sh source + trailing rm -rf.
# NOTE: no `>`/tee/sed/cp/mv anywhere, so the write-confinement block is
# never entered and this exercises the rm-scope deny site alone.
cat > "$CMDDIR/A.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && ngspice -b -o out.log sim/read-snm/testbench/tb_read_snm.spice ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/A.txt" "$WT")
assert_allow "(A) cold-start idiom, trailing rm -rf \"\$scratch\" -> allow" "$result"

# (B) POSIX `.` sourcing spelling instead of `source`.
cat > "$CMDDIR/B.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && . sim/lib/pdk_env.sh && ngspice -b -o out.log sim/read-snm/testbench/tb_read_snm.spice ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/B.txt" "$WT")
assert_allow "(B) POSIX '.' sourcing spelling -> allow" "$result"

# (C) Trailing-slash self-clean spelling.
cat > "$CMDDIR/C.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && ngspice -b -o out.log sim/read-snm/testbench/tb_read_snm.spice ; rm -rf "\$scratch/"
EOF
result=$(run_hook "$CMDDIR/C.txt" "$WT")
assert_allow "(C) trailing-slash rm -rf \"\$scratch/\" -> allow" "$result"

# (D) Fail-closed control: an unrelated unresolved-var rm target, with no
# pdk_env.sh source and no mktemp -d anywhere, must still DENY. This is the
# pre-existing rjwalters/repo#244 behaviour and must not regress.
cat > "$CMDDIR/D.txt" <<EOF
cd $WT && dest=\$(get_dest) && rm -rf "\$dest"
EOF
result=$(run_hook "$CMDDIR/D.txt" "$WT")
assert_deny_because "(D) unrelated unresolved var, no mktemp/pdk_env -> still deny (fail-closed)" "$result" "$RMSCOPE"

# (E) mktemp -d + rm -rf, but NO pdk_env.sh source -> not a general
# mktemp+rm-rf allow.
cat > "$CMDDIR/E.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && ngspice -b -o out.log sim/read-snm/testbench/tb_read_snm.spice ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/E.txt" "$WT")
assert_deny_because "(E) mktemp -d + rm -rf but no pdk_env.sh source -> still deny" "$result" "$RMSCOPE"

# (F) rm -rf on a SUBPATH of the scratch dir only -- never the whole
# directory, so there is no self-clean guarantee -> still DENY.
cat > "$CMDDIR/F.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && ngspice -b -o out.log sim/read-snm/testbench/tb_read_snm.spice ; rm -rf "\$scratch/subdir"
EOF
result=$(run_hook "$CMDDIR/F.txt" "$WT")
assert_deny_because "(F) rm -rf on a scratch SUBPATH only (not the whole dir) -> still deny" "$result" "$RMSCOPE"

# (G) A same-command TMPDIR=<protected area> assignment relocates the
# "self-cleaning scratch dir" INSIDE the guarded tree -> exemption refused.
cat > "$CMDDIR/G.txt" <<EOF
cd $WT && TMPDIR=$TMPROOT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/G.txt" "$WT")
assert_deny_because "(G) same-command TMPDIR=<protected area> -> still deny" "$result" "$RMSCOPE"

# (G2) The same hazard via an AMBIENT $TMPDIR inherited from the session --
# no `TMPDIR=` text in the command at all, so only the ambient half of the
# TMPDIR safety gate can catch it (#97). Command text is byte-identical to
# (A), the otherwise-allowed cold-start idiom.
cat > "$CMDDIR/G2.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && ngspice -b -o out.log sim/read-snm/testbench/tb_read_snm.spice ; rm -rf "\$scratch"
EOF
result=$(run_hook_tmpdir "$CMDDIR/G2.txt" "$WT" "$TMPROOT")
assert_deny_because "(G2) ambient TMPDIR=<protected area> -> still deny" "$result" "$RMSCOPE"

# (H) mktemp argument allowlist, checked at this site too: `-p <protected>`.
cat > "$CMDDIR/H.txt" <<EOF
cd $WT && scratch=\$(mktemp -d -p $TMPROOT) && source sim/lib/pdk_env.sh ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/H.txt" "$WT")
assert_deny_because "(H) mktemp -d -p <protected area> -> still deny" "$result" "$RMSCOPE"

# (H2) ...the long spelling `--tmpdir=<protected>`.
cat > "$CMDDIR/H2.txt" <<EOF
cd $WT && scratch=\$(mktemp -d --tmpdir=$TMPROOT) && source sim/lib/pdk_env.sh ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/H2.txt" "$WT")
assert_deny_because "(H2) mktemp -d --tmpdir=<protected area> -> still deny" "$result" "$RMSCOPE"

# (H3) ...and a positional TEMPLATE under the protected area (no flag at all).
cat > "$CMDDIR/H3.txt" <<EOF
cd $WT && scratch=\$(mktemp -d $TMPROOT/scratch.XXXXXX) && source sim/lib/pdk_env.sh ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/H3.txt" "$WT")
assert_deny_because "(H3) mktemp -d <protected area>/XXXXXX positional template -> still deny" "$result" "$RMSCOPE"

# (I) The exemption is PER-VARIABLE, not per-command: a second, untracked
# unresolved var removed in the same otherwise-exempt command still DENIES.
cat > "$CMDDIR/I.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh ; rm -rf "\$other" ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/I.txt" "$WT")
assert_deny_because "(I) second untracked unresolved var in the same command -> still deny" "$result" "$RMSCOPE"

# (J) PR #65 path-confinement re-validation, applied at THIS site: every
# ingredient is genuine, but the `..` chain after the exempted variable walks
# the removal out of the scratch dir entirely -> must DENY.
cat > "$CMDDIR/J.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh ; rm -rf "\$scratch/../../../.." ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/J.txt" "$WT")
assert_deny_because "(J) '..' chain escaping the scratch dir -> still deny" "$result" "$RMSCOPE"

# (K) Anti-over-correction control: a `..` that stays INSIDE the scratch dir
# resolves back under it, so the removal is still confined -> ALLOW. The #65
# re-validation is a confinement check, not a blanket `..` ban.
cat > "$CMDDIR/K.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh ; rm -rf "\$scratch/sub/.." ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/K.txt" "$WT")
assert_allow "(K) '..' contained within the scratch dir -> still allow" "$result"

# (L) The exemption is PER-TARGET: it must not turn into a blanket allow for
# every other rm target in the same command. A LITERAL path outside repo
# scope, in an otherwise-exempt command, still denies -- at the
# rm-scope-outside-repo site this time.
cat > "$CMDDIR/L.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh ; rm -rf $HOME/no-such-dir-issue-82/stuff ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/L.txt" "$WT")
assert_deny_because "(L) literal out-of-repo-scope target in the same command -> still deny" "$result" "rm target outside repo scope"

# (M) Baseline control: an ordinary literal in-worktree removal, in a command
# with none of this machinery, is unaffected.
cat > "$CMDDIR/M.txt" <<EOF
cd $WT && rm -rf sim/read-snm/testbench/scratch-dir
EOF
result=$(run_hook "$CMDDIR/M.txt" "$WT")
assert_allow "(M) plain literal in-worktree rm -rf -> allow (unchanged)" "$result"

echo
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
