#!/usr/bin/env bash
# Test suite for the klt/KLayout layout-flow scratch-var exemption in
# extract_write_targets()'s write-confinement block,
# .loom/hooks/guard-destructive-generic.sh (issue #127 -- the write-site
# sibling of test-guard-rm-scope-unresolved-var-layout-klt.sh).
#
# Usage: ./.loom/hooks/tests/test-guard-worktree-unresolved-var-layout-klt.sh
#
# Background: the `worktree-write-confinement-unresolved-var` catastrophic
# deny fires on ANY Bash-tool write target (`>`/`>>`, `tee`, `sed -i`,
# `cp`/`mv` destination) whose path root is an unexpanded shell variable the
# guard cannot statically resolve. The #64/#65 exemption covers the sim
# cold-start idiom but its gate (1) requires sourcing sim/lib/pdk_env.sh --
# a sim-flow-specific anchor the layout flow has no reason to satisfy. Issue
# #127 extends the provenance with an alternative gate (1-alt): the SAME
# command invokes this repo's own committed layout tools --
#   (a) the layout generator committed at layout/sram_256x32/generate.py
#       (any relative/absolute spelling; naming the committed file IS
#       invoking it), OR
#   (b) a `klt drc`, `klt extract`, or `klt lvs` subcommand word
# -- instead of sourcing sim/lib/pdk_env.sh. Everything else about the
# exemption (shape contract, TMPDIR gates, per-variable scoping, PR #65
# confinement re-validation) is byte-for-byte the #64/#65 machinery.
#
# This suite asserts, at the WRITE-confinement deny site:
#   - the byte-exact 2026-08-22T06:37 denied command shape from
#     guard-decisions.log (generator via `uv run --with klayout`, klt
#     drc/extract/lvs runs, writes landing in the mktemp -d scratch dir,
#     trailing whole-dir `rm -rf`) is now ALLOWED
#   - a `cp` INTO the scratch dir and a `>` redirect INTO the scratch dir,
#     both inside a klt-anchored command, ALLOW (the write-target side is
#     where the related 2026-08-22T06:59 session friction showed up)
#   - the generate.py arm alone (no `klt` anywhere) carries the exemption
#   - the sim arm of the combined provenance gate still fires (#64's exact
#     reproduction, no layout tools -> still ALLOW)
#   - fail-closed controls, all still DENY: an unrelated unresolved var
#     write; mktemp -d + rm -rf + scratch write with NO provenance anchor;
#     `klt precheck` (out-of-allowlist subcommand) as the anchor; no
#     same-command `rm -rf` cleanup; a DIFFERENT untracked var as the write
#     target; `..` traversal after the exempted var escaping into the main
#     checkout
#   - the TMPDIR/mktemp-argument gates hold at this site: `-p`, `--tmpdir=`,
#     and a same-command `TMPDIR=<protected area>` assignment all still DENY
#   - anti-over-correction: a `..` segment that stays INSIDE the scratch dir
#     is still ALLOWED
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
# Command text is passed via a temp file + --rawfile so multi-line commands
# survive intact. Prints "<exit_code>|<stdout>".
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

echo "=== guard-destructive-generic.sh worktree layout/klt scratch-var exemption tests (#127) ==="

CMDDIR="$TMPROOT/cmds"
mkdir -p "$CMDDIR"

# (A) The byte-exact shape of the 2026-08-22T06:37 guard-decisions denial:
# mktemp -d scratch mirrored through the committed layout recipe's own steps
# (generator via `uv run --with klayout`, klt drc/extract/lvs, writes into
# "$W/...", trailing whole-dir `rm -rf "$W"`, uppercase W as the session
# spelled it). Must now ALLOW.
cat > "$CMDDIR/A.txt" <<EOF
cd $WT && W=\$(mktemp -d) && uv run --with klayout python3 layout/sram_256x32/generate.py --rows 3 --cols 3 -o "\$W/tile3x3.gds" >/dev/null && echo "--- DRC 3x3 tile ---" && klt drc --deck gf180mcu "\$W/tile3x3.gds" ; echo "--- extract+LVS bitcell ---" ; klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" && python3 layout/lvs_reference.py design/netlist/bitcell_6t.spice --layout-netlist "\$W/bitcell.spice" -o "\$W/bitcell_ref.spice" && klt lvs "{\\\"layout\\\":{\\\"netlist\\\":\\\"\$W/bitcell.spice\\\",\\\"top\\\":\\\"sram_bitcell_6t\\\"},\\\"reference\\\":{\\\"netlist\\\":\\\"\$W/bitcell_ref.spice\\\",\\\"form\\\":\\\"subckt-call\\\"}}" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/A.txt" "$WT")
assert_allow "(A) byte-exact 06:37 denied command (generator + klt drc/extract/lvs + trailing rm -rf) -> allow" "$result"

# (B) Writes INTO the scratch dir through the two write idioms the layout
# session actually used (a `>` redirect log and a `cp` in), inside a
# klt-anchored command with the same-command self-clean.
cat > "$CMDDIR/B.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds > "\$W/drc.log" 2>&1 && cp layout/bitcell/sram_bitcell_6t.gds "\$W/" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/B.txt" "$WT")
assert_allow "(B) '> \$W/drc.log' + cp into \$W inside klt command -> allow" "$result"

# (C) Gate (1-alt-a) alone: generate.py invocation with a `>` write into the
# scratch dir, no `klt` anywhere, no pdk_env.sh anywhere.
cat > "$CMDDIR/C.txt" <<EOF
cd $WT && W=\$(mktemp -d) && uv run --with klayout python3 layout/sram_256x32/generate.py --rows 3 --cols 3 -o "\$W/tile3x3.gds" > "\$W/gen.log" 2>&1 ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/C.txt" "$WT")
assert_allow "(C) generate.py alone, redirect into scratch -> allow" "$result"

# (D) Braced \${W} write target + trailing-slash rm -rf "\$W/" self-clean.
cat > "$CMDDIR/D.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" && cp "\$W/bitcell.spice" "\${W}/copy.spice" ; rm -rf "\$W/"
EOF
result=$(run_hook "$CMDDIR/D.txt" "$WT")
assert_allow "(D) braced \${W} target + trailing-slash rm -rf self-clean -> allow" "$result"

# (N) The sim arm of the combined provenance gate still fires: #64's
# reproduction shape (cp + heredoc write into the pdk_env.sh scratch), with no
# layout tools anywhere -> still ALLOW. Regression control: extending the
# provenance must not re-narrow the original sim exemption at this site.
cat > "$CMDDIR/N.txt" <<'EOF'
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
rm -rf "$scratch"
EOF
# Portable in-place edit: `sed -i <script> <file>` is GNU-only -- BSD/macOS sed
# reads the argument after -i as the backup SUFFIX and then fails on the real
# script ("invalid command code"), which aborted this whole suite on macOS
# before the first assertion ran. Redirect through a temp file instead so the
# suite runs identically on both seds.
sed "s#/tmp/wt#$WT#" "$CMDDIR/N.txt" > "$CMDDIR/N.subst" && mv "$CMDDIR/N.subst" "$CMDDIR/N.txt"
result=$(run_hook "$CMDDIR/N.txt" "$WT")
assert_allow "(N) sim/pdk_env.sh idiom (#64 reproduction, no layout tools) -> still allow" "$result"

# (E) Fail-closed control: a GENUINE out-of-worktree write via an unrelated
# unresolved var (no mktemp -d, no pk provenance anchor) must still DENY.
cat > "$CMDDIR/E.txt" <<EOF
cd $WT && dest=\$(get_dest) && echo "x" > "\$dest/evil.sh"
EOF
result=$(run_hook "$CMDDIR/E.txt" "$WT")
assert_deny "(E) unrelated unresolved var, no provenance anchor -> still deny (fail-closed)" "$result"

# (F) mktemp -d + same-command rm -rf + a scratch write, but NO provenance
# anchor (no layout tool, no pdk_env.sh) -> must still DENY. The exemption is
# not a general mktemp+rm-rf allow.
cat > "$CMDDIR/F.txt" <<EOF
cd $WT && W=\$(mktemp -d) && cp layout/bitcell/sram_bitcell_6t.gds "\$W/" && rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/F.txt" "$WT")
assert_deny "(F) mktemp -d + rm -rf + scratch write, no provenance anchor -> still deny" "$result"

# (F2) The klt subcommand allowlist holds at this site too: `klt precheck`
# is NOT one of drc|extract|lvs, so the scratch write keeps its fail-closed
# deny even though a `klt` invocation is present.
cat > "$CMDDIR/F2.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt precheck --deck gf180mcu --grid-um 0.005 layout/bitcell/sram_bitcell_6t.gds > "\$W/precheck.log" 2>&1 ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/F2.txt" "$WT")
assert_deny "(F2) klt precheck anchor (out-of-allowlist subcommand) -> still deny" "$result"

# (G) Layout tool + mktemp -d + scratch WRITE, but NO same-command rm -rf
# cleanup -> must still DENY (no self-clean guarantee, no exemption). The cp
# INTO "$W/" is what makes this a write-target case at this site -- `-o`
# flag operands are not Bash write idioms, so they never reach this check.
cat > "$CMDDIR/G.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" && cp layout/bitcell/sram_bitcell_6t.gds "\$W/"
EOF
result=$(run_hook "$CMDDIR/G.txt" "$WT")
assert_deny "(G) layout anchor + mktemp -d scratch write, no rm -rf -> still deny" "$result"

# (H) Layout tool + mktemp -d + rm -rf on \$W, but the WRITE TARGET uses a
# *different*, untracked unresolved var (\$dest) -> per-variable scoping ->
# must still DENY.
cat > "$CMDDIR/H.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" && dest=\$(get_other) && cp layout/bitcell/sram_bitcell_6t.gds "\$dest/" && rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/H.txt" "$WT")
assert_deny "(H) different untracked unresolved var as write target -> still deny" "$result"

# (I) Layout tool + mktemp -d, rm -rf on a SUBPATH of scratch (not the whole
# directory) -- does not count as self-cleaning -> must still DENY.
cat > "$CMDDIR/I.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" && rm -rf "\$W/subdir"
EOF
result=$(run_hook "$CMDDIR/I.txt" "$WT")
assert_deny "(I) rm -rf on a scratch SUBPATH only (not the whole dir) -> still deny" "$result"

# --- Confinement and TMPDIR/mktemp-argument gates (unchanged #65 machinery) --
# (J) Path traversal AFTER the exempted variable. Every ingredient is genuine
# (real mktemp -d, real layout-tool invocation, real trailing rm -rf that only
# removes the now-empty scratch dir), but the `..` segments walk the write
# straight out of the scratch dir and into the MAIN CHECKOUT's README.md.
# The exemption must only skip the "unresolved variable" deny reason, never
# path confinement -> must DENY.
cat > "$CMDDIR/J.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt drc --deck gf180mcu "\$W/tile3x3.gds" && echo PWNED > "\$W/../../../../../../..$TMPROOT/README.md" && rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/J.txt" "$WT")
assert_deny "(J) '..' traversal after the exempted var into the main checkout -> deny" "$result"

# (K) `mktemp -d -p <main-checkout-root>` points the "self-cleaning scratch
# dir" INSIDE the protected area, so the exemption's core assumption (the
# scratch dir lands outside the guarded tree) no longer holds -> must DENY.
cat > "$CMDDIR/K.txt" <<EOF
cd $WT && W=\$(mktemp -d -p $TMPROOT) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/K.txt" "$WT")
assert_deny "(K) mktemp -d -p <protected area> as the scratch parent -> deny" "$result"

# (K2) Same, via the long spelling `--tmpdir=<main-checkout-root>`.
cat > "$CMDDIR/K2.txt" <<EOF
cd $WT && W=\$(mktemp -d --tmpdir=$TMPROOT) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/K2.txt" "$WT")
assert_deny "(K2) mktemp -d --tmpdir=<protected area> as the scratch parent -> deny" "$result"

# (K3) Same, via a positional TEMPLATE argument naming a directory inside the
# protected area (`mktemp -d <main-root>/XXXXXX`) -- no flag involved at all.
cat > "$CMDDIR/K3.txt" <<EOF
cd $WT && W=\$(mktemp -d $TMPROOT/scratch.XXXXXX) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/K3.txt" "$WT")
assert_deny "(K3) mktemp -d <protected area>/XXXXXX positional template -> deny" "$result"

# (L) A same-command `TMPDIR=<main-checkout-root>` assignment redirects a bare
# `mktemp -d` into the protected area just as effectively as `-p` -> deny.
cat > "$CMDDIR/L.txt" <<EOF
cd $WT && TMPDIR=$TMPROOT && W=\$(mktemp -d) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/L.txt" "$WT")
assert_deny "(L) same-command TMPDIR= assignment redirecting mktemp -> deny" "$result"

# (M) Anti-over-correction control: a `..` segment that stays INSIDE the
# scratch dir resolves back under it, so the write is still confined and must
# remain ALLOWED. The fix is a confinement re-check, not a blanket `..` ban.
cat > "$CMDDIR/M.txt" <<EOF
cd $WT && W=\$(mktemp -d) && klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o "\$W/bitcell.spice" && cp "\$W/bitcell.spice" "\$W/sub/../bitcell_copy.spice" ; rm -rf "\$W"
EOF
result=$(run_hook "$CMDDIR/M.txt" "$WT")
assert_allow "(M) '..' contained within the scratch dir -> still allow" "$result"

echo
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
