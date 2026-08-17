#!/usr/bin/env bash
# Test suite for the Bash-tool write-confinement scan in
# guard-destructive-generic.sh — specifically the `for NAME in <words>`
# loop-variable binding (gf180-sram issue #63).
#
# Usage: ./.loom/hooks/tests/test-guard-write-confinement-loopvar.sh
#
# Background (from the guard-decision telemetry review in gf180-sram #63): a
# Builder working in its OWN issue worktree ran the documented `sim/`
# `.include` path-rewrite loop
#
#     cd <worktree>
#     for f in sim/a.spice sim/b.spice; do
#         sed -i "" "s|old|new|" "$f"
#     done
#
# and was denied twice in a row by the `worktree-write-confinement` family.
# The `cd` tracking was NOT at fault (an equivalent loop-free command with a
# literal relative target was already allowed) — the deny came from `"$f"`,
# which the target extractor could not resolve and therefore fail-closed on
# per #4921, regardless of where the write actually lands.
#
# The fix binds a `for` loop variable to its word list, but ONLY when every
# word is a literal relative path that cannot leave the resolved cwd. This
# suite pins both halves of that contract:
#   (a) the reported false positive now allows,
#   (b) every out-of-worktree / traversal / unresolvable shape still denies,
#   (c) unrelated write-confinement behaviour is unchanged.
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
mkdir -p "$MAIN/sim/access-time/testbench" "$MAIN/.loom/hooks" "$MAIN/.loom/scripts/lib"
cp "$SRC_HOOK" "$MAIN/.loom/hooks/guard-destructive-generic.sh"
[[ -f "$SRC_LIB_DIR/config-resolver.sh" ]] && \
    cp "$SRC_LIB_DIR/config-resolver.sh" "$MAIN/.loom/scripts/lib/config-resolver.sh"
HOOK="$MAIN/.loom/hooks/guard-destructive-generic.sh"

git -C "$MAIN" init -q . >/dev/null 2>&1
git -C "$MAIN" symbolic-ref HEAD refs/heads/main >/dev/null 2>&1
printf 'x\n' > "$MAIN/sim/access-time/testbench/tb_read_access_time.spice"
printf 'fixture\n' > "$MAIN/CLAUDE.md"
git -C "$MAIN" add -A >/dev/null 2>&1
git -C "$MAIN" -c user.email=t@example.invalid -c user.name=test commit -qm init >/dev/null 2>&1

WT="$MAIN/.loom/worktrees/issue-24"
git -C "$MAIN" worktree add -q "$WT" -b feature/issue-24 >/dev/null 2>&1
touch "$WT/.loom-managed"
if ! git -C "$MAIN" rev-parse HEAD >/dev/null 2>&1 || [[ ! -f "$WT/.loom-managed" ]]; then
    echo "SKIP: could not build the main-checkout + managed-worktree fixture"
    exit 0
fi

# --- second fixture: main checkout reached through a SYMLINKED ancestor -----
# (gf180-sram#69). The default Linux $TMPDIR (/tmp) is not itself a symlink,
# so the macOS bug (TMPDIR=/var/folders/... -> /private/var/folders/...)
# can't reproduce by luck of the host here — it has to be built deliberately.
# SYMROOT is a symlink pointing at a second mktemp -d tree; every path fed to
# the hook below (cwd AND command text) is spelled through the symlink, the
# same way a real macOS TMPDIR write target would be, while the hook's own
# `pwd -P` resolution of _WT_MAIN_ROOT still canonicalizes it away.
SYMTARGET="$(mktemp -d)"
SYMROOT="${SYMTARGET}-symlink"
ln -s "$SYMTARGET" "$SYMROOT"
trap 'rm -rf "$TMPROOT" "$SYMTARGET" "$SYMROOT"' EXIT

SMAIN="$SYMROOT/repo"
mkdir -p "$SMAIN/sim/access-time/testbench" "$SMAIN/.loom/hooks" "$SMAIN/.loom/scripts/lib"
cp "$SRC_HOOK" "$SMAIN/.loom/hooks/guard-destructive-generic.sh"
[[ -f "$SRC_LIB_DIR/config-resolver.sh" ]] && \
    cp "$SRC_LIB_DIR/config-resolver.sh" "$SMAIN/.loom/scripts/lib/config-resolver.sh"
SHOOK="$SMAIN/.loom/hooks/guard-destructive-generic.sh"

git -C "$SMAIN" init -q . >/dev/null 2>&1
git -C "$SMAIN" symbolic-ref HEAD refs/heads/main >/dev/null 2>&1
printf 'x\n' > "$SMAIN/sim/access-time/testbench/tb_read_access_time.spice"
printf 'fixture\n' > "$SMAIN/CLAUDE.md"
git -C "$SMAIN" add -A >/dev/null 2>&1
git -C "$SMAIN" -c user.email=t@example.invalid -c user.name=test commit -qm init >/dev/null 2>&1

SWT="$SMAIN/.loom/worktrees/issue-24"
git -C "$SMAIN" worktree add -q "$SWT" -b feature/issue-24 >/dev/null 2>&1
touch "$SWT/.loom-managed"
SYMLINK_FIXTURE_OK=1
if ! git -C "$SMAIN" rev-parse HEAD >/dev/null 2>&1 || [[ ! -f "$SWT/.loom-managed" ]]; then
    SYMLINK_FIXTURE_OK=""
fi

# Run the hook with the given cwd + command. Echoes the permissionDecision
# ("allow" when the hook stays silent, which is its allow contract).
#
# Optional third argument pins LOOM_SED_FLAVOR ("gnu"/"bsd", same convention
# as test-guard-destructive-sed-branch.sh) for the handful of assertions below
# that specifically exercise the BSD "no backup" `sed -i ''` idiom: its
# real-vs-phantom write target depends on which sed would actually execute
# the command (gf180-sram #49 review), so those cases must not depend on the
# flavor of sed installed on whatever host runs this suite.
#
# Optional fourth argument overrides which hook copy to invoke (default
# $HOOK) -- used by the symlinked-ancestor fixture below, which runs against
# its own $SHOOK copy.
run_guard() {
    local cwd="$1" cmd="$2" flavor="${3:-}" hook="${4:-$HOOK}" out rc=0
    out=$(jq -n --arg cwd "$cwd" --arg cmd "$cmd" \
            '{cwd:$cwd, tool_name:"Bash", tool_input:{command:$cmd}}' \
          | env -u LOOM_FORCE_SCOPE -u LOOM_GUARD_DECISION_LOG \
                ${flavor:+LOOM_SED_FLAVOR="$flavor"} \
                bash "$hook" 2>/dev/null) || rc=$?
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

# The exact shape reported in #63: a leading `cd` into the acting worktree,
# then a for-loop whose body rewrites each file by RELATIVE path.
LOOP_CMD_IN_WORKTREE="cd $WT
for f in sim/access-time/testbench/tb_read_access_time.spice sim/access-time/testbench/tb_write_access_time.spice; do
  sed -i \"\" \"s|.include '../../../design/netlist/bitcell_6t.spice'|.include '/abs/design/netlist/bitcell_6t.spice'|\" \"\$f\"
done"

# --- (a) the reported false positive now allows -------------------------------
# Pinned "bsd": the reported #63 idiom is BSD/macOS-specific (`sed -i ""` with
# the backup suffix as a separate argument) -- on an actual GNU host this
# exact command would behave differently at runtime (see the #49 review), so
# the assertion pins the flavor it was written to describe rather than
# depending on whatever sed happens to be on PATH for this suite run.
assert_decision "(a1) cd into own worktree + for-loop relative sed -i -> allow" \
    allow "$(run_guard "$MAIN" "$LOOP_CMD_IN_WORKTREE" bsd)"

assert_decision "(a2) already cwd'd in the worktree, for-loop relative sed -i -> allow" \
    allow "$(run_guard "$WT" "for f in sim/a.spice sim/b.spice; do
  sed -i '' 's|a|b|' \"\$f\"
done")"

assert_decision "(a3) \${f} brace spelling -> allow" \
    allow "$(run_guard "$WT" "for f in sim/a.spice; do
  sed -i 's|a|b|' \"\${f}\"
done")"

assert_decision "(a4) bare \$f, redirection idiom -> allow" \
    allow "$(run_guard "$WT" "for f in sim/a.spice; do
  echo x > \$f
done")"

assert_decision "(a5) ./-prefixed relative words -> allow" \
    allow "$(run_guard "$WT" "for f in ./sim/a.spice; do
  cp /tmp/src \"\$f\"
done")"

# --- (b) every escape shape still denies --------------------------------------
assert_decision "(b1) same loop from the MAIN checkout cwd -> deny" \
    deny "$(run_guard "$MAIN" "for f in sim/access-time/testbench/tb_read_access_time.spice; do
  sed -i 's|a|b|' \"\$f\"
done")"

assert_decision "(b2) loop word is an ABSOLUTE main-checkout path -> deny" \
    deny "$(run_guard "$WT" "for f in $MAIN/sim/a.spice; do
  sed -i 's|a|b|' \"\$f\"
done")"

assert_decision "(b3) loop word carries a .. traversal -> deny" \
    deny "$(run_guard "$WT" "for f in ../../../sim/a.spice; do
  sed -i 's|a|b|' \"\$f\"
done")"

assert_decision "(b4) loop word is itself an unexpanded variable -> deny" \
    deny "$(run_guard "$WT" "for f in \$TARGETS; do
  sed -i 's|a|b|' \"\$f\"
done")"

assert_decision "(b5) loop word is a glob -> deny" \
    deny "$(run_guard "$WT" "for f in sim/*.spice; do
  sed -i 's|a|b|' \"\$f\"
done")"

assert_decision "(b6) loop word is a command substitution -> deny" \
    deny "$(run_guard "$WT" "for f in \$(ls); do
  sed -i 's|a|b|' \"\$f\"
done")"

assert_decision "(b7) \$f with NO binding loop at all -> deny (unchanged #4921)" \
    deny "$(run_guard "$WT" "sed -i 's|a|b|' \"\$f\"")"

assert_decision "(b8) explicit assignment still wins over a loop binding -> deny" \
    deny "$(run_guard "$WT" "f=$MAIN/sim/a.spice
for f in sim/a.spice; do
  sed -i 's|a|b|' \"\$f\"
done")"

assert_decision "(b9) single-quoted '\$f' is a literal name, not a binding -> allow in worktree" \
    allow "$(run_guard "$WT" "for f in sim/a.spice; do
  sed -i 's|a|b|' '\$f'
done")"

# --- (c) unrelated write-confinement behaviour is unchanged -------------------
assert_decision "(c1) literal .. traversal target into the main checkout -> deny" \
    deny "$(run_guard "$WT" "sed -i '' 's|a|b|' ../../../sim/a.spice")"

assert_decision "(c2) literal relative target inside the worktree -> allow" \
    allow "$(run_guard "$MAIN" "cd $WT && sed -i '' 's|a|b|' sim/a.spice")"

assert_decision "(c3) absolute write into the main checkout -> deny" \
    deny "$(run_guard "$WT" "echo x > $MAIN/CLAUDE.md")"

assert_decision "(c4) absolute scratch write outside the repo -> allow" \
    allow "$(run_guard "$WT" "echo x > $TMPROOT/scratch.txt")"

assert_decision "(c5) plain read-only command -> allow" \
    allow "$(run_guard "$WT" "git status --short")"

# --- (d) BSD `sed -i ''` empty backup suffix ---------------------------------
# The BSD/macOS spelling passes the backup suffix as a SEPARATE argument, so
# an empty suffix used to shift the operand list by one and the sed SCRIPT
# was scanned as a file target. A rewrite script whose text contains `../`
# (exactly the documented `sim/` `.include` fix-up) then resolved out of the
# worktree and denied an edit that never leaves it.
assert_decision "(d1) in-worktree sed -i '' whose SCRIPT text contains ../ -> allow" \
    allow "$(run_guard "$WT" "sed -i '' \"s|.include '../../../design/n.spice'|.include '/abs/design/n.spice'|\" sim/a.spice" bsd)"

assert_decision "(d2) sed -i '' writing an actual MAIN-checkout file -> deny" \
    deny "$(run_guard "$WT" "sed -i '' 's|a|b|' $MAIN/sim/access-time/testbench/tb_read_access_time.spice")"

assert_decision "(d3) GNU attached suffix sed -i.bak into the main checkout -> deny" \
    deny "$(run_guard "$WT" "sed -i.bak 's|a|b|' $MAIN/CLAUDE.md")"

assert_decision "(d4) GNU sed -i -e <script> into the main checkout -> deny" \
    deny "$(run_guard "$WT" "sed -i -e 's|a|b|' $MAIN/CLAUDE.md")"

assert_decision "(d5) non-empty BSD suffix is still an operand-shaped token -> deny" \
    deny "$(run_guard "$WT" "sed -i .bak 's|a|b|' $MAIN/CLAUDE.md")"

# Documented behaviour CHANGE, pinned deliberately (see the PR for #63): a
# `sed -i ''` whose only real target is an out-of-repo scratch path now
# allows. It denied before ONLY because the phantom script target resolved
# into the main checkout — this guard has never protected /tmp, and its own
# deny text points agents at "a spelled-out /tmp path for scratch".
assert_decision "(d6) sed -i '' on an out-of-repo scratch file -> allow" \
    allow "$(run_guard "$MAIN" "sed -i '' \"s|x|y|\" $TMPROOT/bitcell_check.sp" bsd)"

# --- (e) symlinked-ancestor main checkout (gf180-sram#69) ---------------------
# Reproduces the macOS-symlinked-TMPDIR bug deliberately on any host: SMAIN /
# SWT sit under $SYMROOT, a symlink to a second mktemp -d tree. The hook's
# `_WT_MAIN_ROOT` is always resolved via `pwd -P` (physical), but a write
# TARGET built from raw command text stays in whatever spelling the command
# used — here, the symlinked one. Every case below has an exact analogue in
# section (c)/(d) above (against the un-symlinked $MAIN fixture); pairing them
# pins that the symlinked-ancestor path gets the SAME verdict, not a
# different (bypassed) one.
if [[ -n "$SYMLINK_FIXTURE_OK" ]]; then
    assert_decision "(e1 = c1) .. traversal target into a symlinked-ancestor main checkout -> deny" \
        deny "$(run_guard "$SWT" "sed -i '' 's|a|b|' ../../../sim/a.spice" "" "$SHOOK")"

    assert_decision "(e2 = c3) absolute write into a symlinked-ancestor main checkout -> deny" \
        deny "$(run_guard "$SWT" "echo x > $SMAIN/CLAUDE.md" "" "$SHOOK")"

    assert_decision "(e3 = c4) absolute scratch write outside a symlinked-ancestor repo -> allow" \
        allow "$(run_guard "$SWT" "echo x > $SYMROOT/scratch.txt" "" "$SHOOK")"

    assert_decision "(e4 = d2) sed -i '' writing an actual file in a symlinked-ancestor main checkout -> deny" \
        deny "$(run_guard "$SWT" "sed -i '' 's|a|b|' $SMAIN/sim/access-time/testbench/tb_read_access_time.spice" "" "$SHOOK")"

    assert_decision "(e5 = d3) GNU attached suffix sed -i.bak into a symlinked-ancestor main checkout -> deny" \
        deny "$(run_guard "$SWT" "sed -i.bak 's|a|b|' $SMAIN/CLAUDE.md" "" "$SHOOK")"

    assert_decision "(e6 = d4) GNU sed -i -e <script> into a symlinked-ancestor main checkout -> deny" \
        deny "$(run_guard "$SWT" "sed -i -e 's|a|b|' $SMAIN/CLAUDE.md" "" "$SHOOK")"

    assert_decision "(e7 = d5) non-empty BSD suffix into a symlinked-ancestor main checkout -> deny" \
        deny "$(run_guard "$SWT" "sed -i .bak 's|a|b|' $SMAIN/CLAUDE.md" "" "$SHOOK")"

    assert_decision "(e8 = c2) literal relative target inside a symlinked-ancestor worktree -> allow" \
        allow "$(run_guard "$SMAIN" "cd $SWT && sed -i '' 's|a|b|' sim/a.spice" "" "$SHOOK")"
else
    echo "SKIP: symlinked-ancestor fixture unavailable on this host -- (e) cases not run"
fi

echo "=== $PASS/$TOTAL passed ==="
[[ "$FAIL" -eq 0 ]]
