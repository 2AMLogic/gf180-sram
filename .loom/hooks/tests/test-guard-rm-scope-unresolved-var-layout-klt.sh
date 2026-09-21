#!/usr/bin/env bash
# Test suite for the klt/KLayout layout-flow scratch-var exemption at the
# *rm-scope* unresolved-var deny site in .loom/hooks/guard-destructive-generic.sh
# (issue #127 -- the layout-side sibling of the #64/#65/#82 pdk_env.sh
# exemption).
#
# Usage: ./.loom/hooks/tests/test-guard-rm-scope-unresolved-var-layout-klt.sh
#
# Background: the #64/#65/#82 pdk_env.sh exemption covers this repo's
# documented "cold-start ngspice invocation" (sim/README.md) but its gate (1)
# requires the SAME command to source sim/lib/pdk_env.sh -- a sim-flow-specific
# anchor. The layout flow's own committed recipe (layout/verify.sh: the
# mktemp -d scratch + `klt`/generator tool runs + trailing `rm -rf` shape that
# layout/README.md says "is reproduced end-to-end by ./layout/verify.sh") has
# no reason to source a sim script, so gate (1) could never pass for it and
# the guard denied the session's inline layout cold-start reproduction
# (guard-decisions.log 2026-08-22T06:37 `rm-scope-unresolved-var`, and the
# related 06:59 write-confinement denial, both filed as issue #127).
#
# #127 extends the exemption's provenance with an alternative gate (1-alt):
# the SAME command invokes this repo's own committed layout tools --
#   (a) the layout generator committed at layout/sram_256x32/generate.py
#       (any relative/absolute spelling; naming the committed file IS
#       invoking it), OR
#   (b) a `klt drc`, `klt extract`, or `klt lvs` subcommand word
# -- instead of sourcing sim/lib/pdk_env.sh. The shape contract (the literal
# `NAME=$(mktemp -d ...)` argument allowlist + same-command whole-dir
# `rm -rf "$NAME"` self-clean + TMPDIR gates + PR #65 confinement
# re-validation) is UNCHANGED, and every fail-closed control below
# re-asserts it.
#
# This suite exercises the rm-scope deny site IN ISOLATION: every case below
# is deliberately free of the `>`/`tee`/`sed -i`/`cp `/`mv ` idioms that gate
# the Bash-write-confinement block (mirroring the sibling
# test-guard-rm-scope-unresolved-var-pdk-env.sh design), so the only check
# that can fire here is the rm-scope one. The write-confinement site is
# covered by the sibling test-guard-worktree-unresolved-var-layout-klt.sh.
#
# It asserts:
#   - the layout cold-start idiom (generator + klt drc/extract/lvs variants,
#     uppercase `W` scratch var as the denied session actually spelled it) is
#     ALLOWED
#   - each (1-alt) arm alone carries the exemption: a generate.py-invoking
#     command with no `klt` anywhere, and klt-only commands with no
#     generator, both ALLOW
#   - the sim/pdk_env.sh arm still works through the combined provenance
#     gate (sim idiom with no layout tools ALLOW)
#   - mktemp -d + rm -rf with NO provenance anchor (no pdk_env.sh source,
#     no layout tool, and `klt precheck` -- an out-of-allowlist subcommand)
#     still DENIES -- the exemption is not a general mktemp+rm-rf allow
#   - the unchanged shape contract still holds: rm -rf on a scratch SUBPATH,
#     a second untracked unresolved var, a same-command `TMPDIR=<protected>`,
#     an AMBIENT `$TMPDIR=<protected>`, `mktemp -d -p`/`--tmpdir=<protected>`,
#     and a positional TEMPLATE under the protected area all still DENY
#   - the PR #65 path-confinement re-validation applies: a `..` chain that
#     escapes the scratch dir still DENIES, a `..` contained within it is
#     still ALLOWED
#   - the exemption is PER-TARGET: a literal out-of-repo-scope rm target in
#     the very same (otherwise exempt) command still DENIES
#
# The hook under test is copied into an isolated temp git tree (mirroring
# the .loom/worktrees/issue-<N> layout this guard inspects) so REPO_ROOT /
# the main-checkout root resolve there, never against the real repo.
#
# Runs under the repo's DEFAULT guard config: guards.rmScope / LOOM_RM_SCOPE
# are deliberately NOT set here (the temp repo ships no .loom/config.json, so
# rm_scope_repo_enabled() resolves to its "repo" default) -- that is the
# whole point of #82. LOOM_RM_SCOPE is explicitly unset below so an ambient
# value inherited from a dispatching agent cannot silently neuter the suite.
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

# --- Fixture: one managed worktree at $TMPROOT/.loom/worktrees/issue-103,
# mirroring the layout the #127 denials ran in (the native-DRC/LVS session
# worked in an issue-103 worktree). -------------------------------------------
WT="$TMPROOT/.loom/worktrees/issue-103"
mkdir -p "$WT/layout/sram_256x32" "$WT/layout/bitcell" "$WT/sim/lib" "$WT/sim/read-snm/testbench"
cat > "$WT/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF
echo "x" > "$WT/sim/read-snm/testbench/tb_read_snm.spice"
# Stand-ins for the committed layout tools -- content is irrelevant to the
# guard, which only pattern-matches the command text, never executes it.
echo "# generate.py stand-in" > "$WT/layout/sram_256x32/generate.py"
echo "binary stand-in" > "$WT/layout/bitcell/sram_bitcell_6t.gds"
echo "# stand-in for the real pdk_env.sh (sim provenance control case)" \
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
# deny from some unrelated check (in particular, these cases must deny at the
# rm-scope site, not at the write-confinement site).
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

echo "=== guard-destructive-generic.sh rm-scope layout/klt scratch-var exemption tests (#127) ==="

CMDDIR="$TMPROOT/cmds"
mkdir -p "$CMDDIR"

# (A) The denied session's layout cold-start idiom, reduced to the parts the
# rm-scope check sees: mktemp -d scratch + generator/klt runs + trailing
# rm -rf. NOTE: no `>`/tee/sed/cp/mv anywhere, so the write-confinement block
# is never entered and this exercises the rm-scope deny site alone. This is
# the shape of the 2026-08-22T06:37 rm-scope-unresolved-var denial (uppercase
# W, as the session spelled it).
cat > "$CMDDIR/A.txt" <<EOF
cd $WT && W=\$(mktemp -d) && uv run --with klayout python3 layout/sram_256x32/generate.py --rows 3 --cols 3 -o "\$W/tile3x3.gds" && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/A.txt" "$WT")
assert_allow "(A) layout cold-start idiom, trailing rm -rf \"\$W\" -> allow" "$result"

# (B) Gate (1-alt-a) alone: the committed generator is invoked (here via the
# documented `uv run --with klayout python3` spelling) and NO `klt`
# subcommand appears anywhere.
cat > "$CMDDIR/B.txt" <<EOF
cd $WT && W=\$(mktemp -d) && uv run --with klayout python3 layout/sram_256x32/generate.py --rows 3 --cols 3 -o "\$W/tile3x3.gds" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/B.txt" "$WT")
assert_allow "(B) generate.py invocation alone (no klt anywhere) -> allow" "$result"

# (C) Gate (1-alt-b) alone: a `klt drc` run with no generator, no pdk_env.sh.
cat > "$CMDDIR/C.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/C.txt" "$WT")
assert_allow "(C) klt drc alone (no generator, no pdk_env.sh) -> allow" "$result"

# (C2) The other two allowed klt subcommands -- extract and lvs -- carry the
# same provenance. The lvs case also proves a quoted positional JSON argument
# does not defeat the `klt lvs` command-word match.
cat > "$CMDDIR/C2.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" && klt lvs '{"layout":{"netlist":"\$W/bitcell.spice","top":"sram_bitcell_6t"},"reference":{"netlist":"design/netlist/bitcell_6t.spice","form":"subckt-call"}}' ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/C2.txt" "$WT")
assert_allow "(C2) klt extract + klt lvs (quoted positional args) -> allow" "$result"

# (N) The sim arm of the combined provenance gate still fires: the #64/#65/#82
# pdk_env.sh idiom with no layout tools anywhere -> still ALLOW (regression
# control: extending gate (1) must not re-narrow the original sim exemption).
cat > "$CMDDIR/N.txt" <<EOF
cd $WT && scratch=\$(mktemp -d) && source sim/lib/pdk_env.sh && ngspice -b -o out.log sim/read-snm/testbench/tb_read_snm.spice ; rm -rf "\$scratch"
EOF
result=$(run_hook "$CMDDIR/N.txt" "$WT")
assert_allow "(N) sim/pdk_env.sh idiom with no layout tools -> still allow" "$result"

# (D) Fail-closed control: mktemp -d + same-command rm -rf with NO provenance
# anchor at all (no pdk_env.sh source, no generator, no klt) must still DENY
# -- the exemption is not a general mktemp+rm-rf allow.
cat > "$CMDDIR/D.txt" <<EOF
cd $WT && W=\$(mktemp -d) && ngspice -b -o out.log sim/read-snm/testbench/tb_read_snm.spice ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/D.txt" "$WT")
assert_deny_because "(D) mktemp -d + rm -rf, no provenance anchor -> still deny" "$result" "$RMSCOPE"

# (E) The klt subcommand allowlist holds: `klt precheck` (in layout/verify.sh
# but NOT one of drc|extract|lvs) is out of the #127 allowlist, so the
# provenance gate fails and the command keeps its fail-closed deny.
cat > "$CMDDIR/E.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt precheck --deck gf180mcu --grid-um 0.005 layout/bitcell/sram_bitcell_6t.gds ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/E.txt" "$WT")
assert_deny_because "(E) klt precheck (out-of-allowlist subcommand) -> still deny" "$result" "$RMSCOPE"

# (F) rm -rf on a SUBPATH of the scratch dir only -- never the whole
# directory, so there is no self-clean guarantee -> still DENY.
cat > "$CMDDIR/F.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W/subdir"
EOF
result=$(run_hook "$CMDDIR/F.txt" "$WT")
assert_deny_because "(F) rm -rf on a scratch SUBPATH only (not the whole dir) -> still deny" "$result" "$RMSCOPE"

# (G) A same-command TMPDIR=<protected area> assignment relocates the
# "self-cleaning scratch dir" INSIDE the guarded tree -> exemption refused.
cat > "$CMDDIR/G.txt" <<EOF
cd $WT && TMPDIR=$TMPROOT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/G.txt" "$WT")
assert_deny_because "(G) same-command TMPDIR=<protected area> -> still deny" "$result" "$RMSCOPE"

# (G2) The same hazard via an AMBIENT $TMPDIR inherited from the session --
# no `TMPDIR=` text in the command at all, so only the ambient half of the
# TMPDIR safety gate can catch it. Command text is byte-identical to (A).
cat > "$CMDDIR/G2.txt" <<EOF
cd $WT && W=\$(mktemp -d) && uv run --with klayout python3 layout/sram_256x32/generate.py --rows 3 --cols 3 -o "\$W/tile3x3.gds" && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W"
EOF
result=$(run_hook_tmpdir "$CMDDIR/G2.txt" "$WT" "$TMPROOT")
assert_deny_because "(G2) ambient TMPDIR=<protected area> -> still deny" "$result" "$RMSCOPE"

# (H) mktemp argument allowlist, checked at this site too: `-p <protected>`.
cat > "$CMDDIR/H.txt" <<EOF
cd $WT && W=\$(mktemp -d -p $TMPROOT) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/H.txt" "$WT")
assert_deny_because "(H) mktemp -d -p <protected area> -> still deny" "$result" "$RMSCOPE"

# (H2) ...the long spelling `--tmpdir=<protected>`.
cat > "$CMDDIR/H2.txt" <<EOF
cd $WT && W=\$(mktemp -d --tmpdir=$TMPROOT) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/H2.txt" "$WT")
assert_deny_because "(H2) mktemp -d --tmpdir=<protected area> -> still deny" "$result" "$RMSCOPE"

# (H3) ...and a positional TEMPLATE under the protected area (no flag at all).
cat > "$CMDDIR/H3.txt" <<EOF
cd $WT && W=\$(mktemp -d $TMPROOT/scratch.XXXXXX) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/H3.txt" "$WT")
assert_deny_because "(H3) mktemp -d <protected area>/XXXXXX positional template -> still deny" "$result" "$RMSCOPE"

# (I) The exemption is PER-VARIABLE, not per-command: a second, untracked
# unresolved var removed in the same otherwise-exempt command still DENIES.
cat > "$CMDDIR/I.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$other" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/I.txt" "$WT")
assert_deny_because "(I) second untracked unresolved var in the same command -> still deny" "$result" "$RMSCOPE"

# (J) PR #65 path-confinement re-validation, applied at THIS site: every
# ingredient is genuine, but the `..` chain after the exempted variable walks
# the removal out of the scratch dir entirely -> must DENY.
cat > "$CMDDIR/J.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W/../../../.." ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/J.txt" "$WT")
assert_deny_because "(J) '..' chain escaping the scratch dir -> still deny" "$result" "$RMSCOPE"

# (K) Anti-over-correction control: a `..` that stays INSIDE the scratch dir
# resolves back under it, so the removal is still confined -> ALLOW. The #65
# re-validation is a confinement check, not a blanket `..` ban.
cat > "$CMDDIR/K.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf "\$W/sub/.." ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/K.txt" "$WT")
assert_allow "(K) '..' contained within the scratch dir -> still allow" "$result"

# (L) The exemption is PER-TARGET: it must not turn into a blanket allow for
# every other rm target in the same command. A LITERAL path outside repo
# scope, in an otherwise-exempt command, still denies -- at the
# rm-scope-outside-repo site this time.
cat > "$CMDDIR/L.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; rm -rf $HOME/no-such-dir-issue-127/stuff ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/L.txt" "$WT")
assert_deny_because "(L) literal out-of-repo-scope target in the same command -> still deny" "$result" "rm target outside repo scope"

# (M) Baseline control: an ordinary literal in-worktree removal, in a command
# with none of this machinery, is unaffected.
cat > "$CMDDIR/M.txt" <<EOF
cd $WT && rm -rf layout/sram_256x32/generated-tile-scratch
EOF
result=$(run_hook "$CMDDIR/M.txt" "$WT")
assert_allow "(M) plain literal in-worktree rm -rf -> allow (unchanged)" "$result"

echo
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
