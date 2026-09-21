#!/usr/bin/env bash
# Test suite for quoted same-command write-target variable resolution in
# extract_write_targets(), .loom/hooks/guard-destructive-generic.sh (issue
# #130 -- the quote-handling sibling of the #127 klt suite and the #4881
# same-command resolver it extends).
#
# Background: the deny message recorded at all three
# worktree-write-confinement-unresolved-var call sites teaches the remedy
# "Declare it literally in the SAME command, before the write:
# VAR=/literal/path; <write> -- the guard's same-command resolver
# (record_assign()/resolve_var(), #4881) substitutes it before this check
# runs". Before #130 that promise was only true for UNQUOTED write-target
# spellings ($WORK/f.log, ${WORK}/f.log): resolve_var() requires the token to
# start with "$", a token carrying its quotes verbatim starts with a quote
# character, so every double-quoted spelling denied even though the assigner
# did exactly what the deny message told it to:
#   $WORK/...  |  ${WORK}/...   -> resolved, judged on the real path -> allow
#   "$WORK/..." | "$WORK"/...   | "$WORK" | cp x "$WORK/y" | 2> "$W/e.log"
#                             -> UNRESOLVED -> fail-closed deny (the 06:59
#                                shape of the 2026-08-22 layout session)
#
# #130 widens resolution to the quoted spelling at the write-target entry
# point only (resolve_wtarget()): a balanced, shell-accurate double-quote
# strip of the RESOLUTION INPUT when the stripped token leads with a bare
# $NAME/${NAME} reference. The resolved value flows into the UNCHANGED
# downstream absolute/relative classification and containment test, so the
# #6172 contract (a resolved path can never grant an allow beyond writing
# the literal path outright) is preserved by construction. When the strip
# cannot prove a substitution (no matching assignment, AMBIG poison,
# non-$-leading form, unbalanced quotes), the RAW token is emitted
# unchanged, so every unresolvable shape keeps today's verdict
# byte-for-byte.
#
# This suite asserts, at the write-confinement block:
#   - every quoted spelling whose same-command literal assignment resolves
#     lands outside the protected area now ALLOWs: fully wrapped
#     "$WORK/f.log", cp destination "$WORK/copy", leading-quoted-segment
#     "$WORK"/f.log, bare fully-wrapped full target "$WORK", the byte-exact
#     06:59 klayout runbook shape (both > and 2> targets), a tee target,
#     a `;`-separated assignment chain, and quoted assignment VALUES
#     (WORK="/tmp/x", WORK='/tmp/x' -- record_assign already strips value
#     quotes; pre-existing behavior, now actually reachable)
#   - the unquoted controls ($WORK/f.log, ${WORK}/f.log) keep allowing
#   - single quotes stay literal: '$WORK/f.log' is a relative file really
#     named `$WORK/f.log`, judged in-worktree -> still ALLOW, never resolved
#   - fail-closed floor holds: an unset $NOVAR still DENIES; a conflicting
#     reassignment (AMBIG poison) still DENIES; an UNBALANCED opening quote
#     keeps today's verdict (DENY) -- the strip never repairs what it cannot
#     prove
#   - containment re-check preserved (#6172): WORK=<main-checkout-root> with
#     a quoted target still DENIES -- now via the containment rule, NOT via
#     the unresolved-var reason (asserted by reason text)
#   - unprovable quoted shapes keep their verdicts: "/$X/evil.sh"
#     (root-unknown via /$), "$<main-root>/sub/$X/f.log" (known prefix inside
#     the protected area, $X an unresolvable directory component), and the
#     ~user-root and <main-root>/../ known-prefix controls
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

# --- Fixture: one managed worktree at $TMPROOT/.loom/worktrees/issue-130,
# the shape the #130 reproduction matrix ran in. -----------------------------
WT="$TMPROOT/.loom/worktrees/issue-130"
mkdir -p "$WT/layout/drc"
cat > "$WT/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF
echo "x" > "$WT/README.md"
# Stand-in for the committed DRC runbook -- content is irrelevant to the
# guard, which only pattern-matches the command text, never executes it.
echo "# runbook.py stand-in" > "$WT/layout/drc/runbook.py"

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

# Deny asserting the decision went through a reason OTHER than the
# unresolved-var family (all three of those deny messages carry the exact
# phrase "unexpanded shell variable"). Used for the #6172 containment
# discriminator: the quoted twin of a containment-bound variable must
# still deny, but post-#130 via containment, not via unresolved-var.
assert_deny_reason_not_unresolved_var() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with deny JSON, got NONZERO exit=$code)"
        return
    fi
    local decision reason
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    reason=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null || true)
    if [[ "$decision" == "deny" && "$reason" != *"unexpanded shell variable"* ]]; then
        pass "$desc"
    else
        fail "$desc (expected deny via NON-unresolved-var reason, got decision=$decision reason=$reason)"
    fi
}

echo "=== guard-destructive-generic.sh quoted same-command write-target resolution tests (#130) ==="

CMDDIR="$TMPROOT/cmds"
mkdir -p "$CMDDIR"

# ---- Resolution now covers the quoted spellings (the #130 fix) --------------
#
# Every row below declares a literal same-command assignment whose value is a
# spelled-out /tmp path -- exactly the recorded deny-message remedy -- and
# writes through a QUOTED target token. Pre-#130 every one of these denied
# with worktree-write-confinement-unresolved-var because the token started
# with a quote character and resolve_var() never matched it. Post-#130 the
# quoted spelling resolves like its unquoted twin and is judged on the real
# resolved path (outside the protected area -> ALLOW).

# (C) Fully wrapped "$WORK/f.log" redirect target -- the exact shape from the
# 06:59 denied session.
cat > "$CMDDIR/C.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && echo a > "\$WORK/f.log"
EOF
result=$(run_hook "$CMDDIR/C.txt" "$WT")
assert_allow '(C) same-command assignment + fully wrapped "\$WORK/f.log" target -> allow' "$result"

# (D) Quoted cp destination.
cat > "$CMDDIR/D.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && cp README.md "\$WORK/copy"
EOF
result=$(run_hook "$CMDDIR/D.txt" "$WT")
assert_allow '(D) quoted cp destination "\$WORK/copy" -> allow' "$result"

# (F) Leading-quoted-segment spelling "$WORK"/f.log -- the partial-quote shape
# the original filing extended to (closes mid-token).
cat > "$CMDDIR/F.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && echo a > "\$WORK"/f.log
EOF
result=$(run_hook "$CMDDIR/F.txt" "$WT")
assert_allow '(F) leading-quoted-segment "\$WORK"/f.log target -> allow' "$result"

# (FF) Bare fully-wrapped full target "$WORK" -- the whole write target is
# one quoted variable reference.
cat > "$CMDDIR/FF.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && echo a > "\$WORK"
EOF
result=$(run_hook "$CMDDIR/FF.txt" "$WT")
assert_allow '(FF) bare fully-wrapped full target "\$WORK" -> allow' "$result"

# (H) The byte-exact 06:59 runbook shape that survived #127/#131: a literal
# /tmp scratch var declared in the same command, a raw klayout -b -r
# invocation, and BOTH redirect targets quoted (one fd-prefixed with 2>).
# No mktemp -d, no same-command rm -rf -- the klt scratch exemption
# deliberately does not cover this shape; quoted resolution is what makes
# the deny message's own remedy finally work for it.
cat > "$CMDDIR/H.txt" <<EOF
cd $WT && WORK=/tmp/tmp.t6jorcRq0v && klayout -b -r layout/drc/runbook.py > "\$WORK/after2.stdout.log" 2> "\$WORK/after2.stderr.log"
EOF
result=$(run_hook "$CMDDIR/H.txt" "$WT")
assert_allow '(H) 06:59 klayout runbook shape, quoted > and 2> targets -> allow' "$result"

# (T) Quoted tee target -- the tee write-idiom emission site.
cat > "$CMDDIR/T.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && echo a | tee "\$WORK/t.log" >/dev/null
EOF
result=$(run_hook "$CMDDIR/T.txt" "$WT")
assert_allow '(T) quoted tee target "\$WORK/t.log" -> allow' "$result"

# (SEMI) `;`-separated same-command assignment chain (the remedy's literal
# spelling) with a quoted cp destination.
cat > "$CMDDIR/SEMI.txt" <<EOF
cd $WT; WORK=/tmp/loom-qss; cp README.md "\$WORK/copy2"
EOF
result=$(run_hook "$CMDDIR/SEMI.txt" "$WT")
assert_allow '(SEMI) `;`-chain assignment + quoted cp destination -> allow' "$result"

# (QV) Double-quoted assignment VALUE -- record_assign() already strips a
# balanced quote pair from the VALUE (pre-existing behavior); with the
# quoted target now resolvable, the recorded value actually gets used.
cat > "$CMDDIR/QV.txt" <<EOF
cd $WT && WORK="/tmp/loom-qss" && echo a > "\$WORK/f.log"
EOF
result=$(run_hook "$CMDDIR/QV.txt" "$WT")
assert_allow '(QV) double-quoted assignment value + quoted target -> allow' "$result"

# (QS) Single-quoted assignment VALUE -- same pre-existing value-strip on the
# assignment side. Single quotes on the WRITE TARGET stay literal (rows E/E2
# below); on the VALUE side record_assign() has always unwrapped them.
cat > "$CMDDIR/QS.txt" <<EOF
cd $WT && WORK='/tmp/loom-qss' && echo a > "\$WORK/f.log"
EOF
result=$(run_hook "$CMDDIR/QS.txt" "$WT")
assert_allow '(QS) single-quoted assignment value + quoted target -> allow' "$result"

# ---- Unquoted controls: the resolver's pre-existing rows stay correct --------
#
# (A) Unquoted $WORK/f.log -- resolved since #4881; the #130 strip must not
# disturb it.
cat > "$CMDDIR/A.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && echo a > \$WORK/f.log
EOF
result=$(run_hook "$CMDDIR/A.txt" "$WT")
assert_allow '(A) unquoted \$WORK/f.log target (pre-existing) -> allow' "$result"

# (B) Braced, unquoted ${WORK}/f.log.
cat > "$CMDDIR/B.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && echo a > \${WORK}/f.log
EOF
result=$(run_hook "$CMDDIR/B.txt" "$WT")
assert_allow '(B) braced unquoted \${WORK}/f.log target (pre-existing) -> allow' "$result"

# ---- Single quotes stay literal (the shape the fix must NOT touch) ----------
#
# (E) '$WORK/f.log' with NO same-command assignment is a relative file really
# named `$WORK/f.log` judged in-worktree -> ALLOW, exactly as today. A
# single-quoted span never resolves -- not from inside the quotes, ever.
cat > "$CMDDIR/E.txt" <<EOF
cd $WT && echo a > '\$WORK/f.log'
EOF
result=$(run_hook "$CMDDIR/E.txt" "$WT")
assert_allow "(E) single-quoted literal '\$WORK/f.log' file -> still allow (no resolution)" "$result"

# (E2) Single-quoted spelling WITH a same-command assignment present: the
# assignment does not make a literal-quoted target expandable -- the shell
# would still write the file named \$WORK/f.log -> still ALLOW, in-worktree.
cat > "$CMDDIR/E2.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && echo a > '\$WORK/f.log'
EOF
result=$(run_hook "$CMDDIR/E2.txt" "$WT")
assert_allow '(E2) single-quoted literal with assignment present -> still allow (literal wins)' "$result"

# ---- Fail-closed controls: the floor the fix must not lower ------------------
#
# (J) No assignment at all -- an unset \$NOVAR is unresolvable, fail closed.
cat > "$CMDDIR/J.txt" <<EOF
cd $WT && echo a > \$NOVAR/f.log
EOF
result=$(run_hook "$CMDDIR/J.txt" "$WT")
assert_deny '(J) unset \$NOVAR, no assignment -> still deny (fail-closed floor)' "$result"

# (U) Unbalanced quote: a lone opening double quote is exactly the shape the
# strip must NOT repair ("return the token UNCHANGED when you cannot prove
# a value") -- today's verdict, a DENY, must survive.
cat > "$CMDDIR/U.txt" <<EOF
cd $WT && WORK=/tmp/loom-qss && echo a > "\$WORK/f.log
EOF
result=$(run_hook "$CMDDIR/U.txt" "$WT")
assert_deny '(U) unbalanced opening quote "\$WORK/f.log -> still deny (strip never repairs)' "$result"

# (AMB) Conflicting same-command reassignment poisons the variable
# (record_assign AMBIG sentinel). The quote handling must READ the
# poisoning, never bypass it, in the quoted spelling too.
cat > "$CMDDIR/AMB.txt" <<EOF
cd $WT && WORK=/tmp/loom-a1 && WORK=/tmp/loom-b2 && echo a > "\$WORK/f.log"
EOF
result=$(run_hook "$CMDDIR/AMB.txt" "$WT")
assert_deny '(AMB) conflicting reassignment, quoted target -> still deny (AMBIG poison read)' "$result"

# ---- Containment re-check preserved (#6172) ---------------------------------
#
# (CONT) The quoted twin of the containment control: the same-command
# assignment resolves -- but to the MAIN CHECKOUT ROOT, so the write is
# judged on the real resolved path and must still DENY. Post-#130 the deny
# fires via the containment rule, no longer via the unresolved-var reason
# (asserted by reason text: the message must NOT be the unresolved-var
# family's "unexpanded shell variable" phrasing).
cat > "$CMDDIR/CONT.txt" <<EOF
cd $WT && WORK=$TMPROOT && echo a > "\$WORK/evil.sh"
EOF
result=$(run_hook "$CMDDIR/CONT.txt" "$WT")
assert_deny_reason_not_unresolved_var '(CONT) WORK=<main-root> quoted twin -> still deny, via containment (#6172)' "$result"

# ---- Unprovable quoted shapes keep today's verdicts --------------------------
#
# (ROOTSLASH) A quoted "/\$X/evil.sh" -- root + variable. No assignment can
# prove \$X, the stripped form is not helped by resolution beyond what the
# unquoted twin already was: fail closed.
cat > "$CMDDIR/ROOTSLASH.txt" <<EOF
cd $WT && echo a > "/\$X/evil.sh"
EOF
result=$(run_hook "$CMDDIR/ROOTSLASH.txt" "$WT")
assert_deny '(ROOTSLASH) quoted "/\$X/evil.sh" root-unknown -> still deny' "$result"

# (KNOWN) A quoted target whose KNOWN prefix is inside the protected area
# with an unresolvable \$X in a directory component -- the site-6871 shape,
# unchanged for tokens the resolver cannot prove.
cat > "$CMDDIR/KNOWN.txt" <<EOF
cd $WT && echo a > "$TMPROOT/sub/\$X/f.log"
EOF
result=$(run_hook "$CMDDIR/KNOWN.txt" "$WT")
assert_deny '(KNOWN) known prefix <main-root>/sub/ + unresolved \$X dir component -> still deny' "$result"

# (REPOUP) The <repo>/../ known-prefix control: a quoted target escaping the
# protected area by one component before an unresolved \$X -- the known
# prefix (<main-root>/..) normalizes OUTSIDE the protected area, so today's
# verdict is ALLOW and must stay ALLOW (the strip only ever widens the
# leading-`$` literal-resolvable case; a non-`$`-leading stripped form falls
# back to today's raw token and verdict).
cat > "$CMDDIR/REPOUP.txt" <<EOF
cd $WT && echo a > "$TMPROOT/../\$X/f.log"
EOF
result=$(run_hook "$CMDDIR/REPOUP.txt" "$WT")
assert_allow '(REPOUP) quoted "<main-root>/../\$X/f.log" known-prefix control -> keeps current verdict (allow)' "$result"

# (TILDE) The ~user-root control: a quoted ~user-led target with an
# unresolved \$X -- not a leading-`$` reference, never a resolution input;
# keeps today's verdict.
cat > "$CMDDIR/TILDE.txt" <<EOF
cd $WT && echo a > "~root/\$X/f.log"
EOF
result=$(run_hook "$CMDDIR/TILDE.txt" "$WT")
assert_deny '(TILDE) quoted "~root/\$X/f.log" ~user-root control -> keeps current verdict' "$result"

echo
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
