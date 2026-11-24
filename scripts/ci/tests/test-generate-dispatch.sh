#!/usr/bin/env bash
# test-generate-dispatch.sh — regression guard for the flag-dispatch
# contract of layout/reports/generate.sh (issue #504).
#
# PR #502 (issue #500) replaced generate.sh's interleaved negative `if`
# guards with one `case` dispatcher whose contract is explicit: exactly
# one flag selects exactly one block, zero arguments selects the full
# run, anything else prints usage on stderr and exits 2 without invoking
# any tool. That contract regressed once inside the PR's own lifetime —
# the first head (7eb73ea) routed a single EMPTY argument to the
# full-run branch, so `generate.sh "$mode"` with an unset `mode` would
# have overwritten the entire committed report set; caught by review,
# not by a test, and fixed in 0d20c24. A mis-dispatch here overwrites
# committed signoff reports in place (layout/reports/README.md
# "Freshness"), so this table is pinned by a test, in the same
# fault-injection style as test-check-repo-hygiene.sh.
#
# klt, uv, uvx and python3 are replaced by stubs on PATH that append
# "<tool> <argv>" to a call log and then exit $STUB_EXIT. Two modes:
#   fail-fast (exit 1) — the script runs under `set -e`, so the first
#     stubbed call both proves a work function was entered and stops the
#     run before anything is written; this covers every row of the table
#     measured during review of PR #502 at 0d20c242;
#   pass-through (exit 0) — every stubbed tool "succeeds" writing
#     nothing (commit_report IS python3, so no committed report can be
#     written), letting the run play through for the two rows fail-fast
#     cannot observe: the no-arg full-run ORDER (0r,0c,0,1-5,0a,0m,done
#     — the trailing `done` banner is printed only by the full-run
#     branch), and `--column-path --native` reaching the native
#     sub-branch (`0n.`), with GF180_PDK_PATH pointed at a nonexistent
#     dir so sim/lib/pdk_env.sh refuses the install check right after
#     the 0n. banner — deterministic, no PDK needed.
#
# The last section re-introduces the pre-0d20c24 defect (empty first
# argument routed to the full run) in a scratch COPY of the script and
# asserts the `''` row's expectations now fail — proving this guard
# catches the exact regression it exists for. The copy's ROOT resolves
# outside the repo, so it cannot touch anything committed either.
#
# Needs no PDK, no klt, no network; runs in seconds.

set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEN="$TEST_DIR/../../../layout/reports/generate.sh"
REPO_ROOT="$(cd "$TEST_DIR/../../.." && pwd)"

FX=/tmp/loom-test-generate-dispatch.$$
trap 'rm -rf "$FX"' EXIT
mkdir -p "$FX/bin"

CALL_LOG="$FX/calls.log"
RC=0

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1" >&2; FAIL=$((FAIL + 1)); }

# One stub under four names. It never touches the filesystem beyond the
# call log — that is what makes a played-through run safe.
cat > "$FX/bin/stub" <<'STUB'
#!/usr/bin/env bash
printf '%s %s\n' "${0##*/}" "$*" >> "$STUB_LOG"
exit "${STUB_EXIT:-1}"
STUB
chmod +x "$FX/bin/stub"
for tool in klt uv uvx python3; do ln -s stub "$FX/bin/$tool"; done

# run_gen <ff|pt> [args...] — run the real script with stubbed tools,
# capturing stdout/stderr/rc. ff = fail-fast stubs (exit 1),
# pt = pass-through stubs (exit 0). Sets RC.
run_gen() {
    local mode="$1" rc=0
    shift
    : > "$CALL_LOG"
    STUB_LOG="$CALL_LOG" \
    STUB_EXIT="$([ "$mode" = pt ] && echo 0 || echo 1)" \
    PATH="$FX/bin:$PATH" \
    "$GEN" "$@" >"$FX/out" 2>"$FX/err" || rc=$?
    RC="$rc"
}

# The stage banners generate.sh's hr() prints on stdout, reduced to
# their stage keys (first token): "0r." "0c." "0." "0n." "1." ... "0a."
# "0m." "done".
banner_keys() { grep -E '^=== ' "$1" | sed -e 's/^=== //' -e 's/ ===$//' | awk '{print $1}'; }
keys_line() { banner_keys "$1" | paste -sd ' ' -; }

# ff_row <label> <expected-stage-keys|none> [args...] — accepted form
# under fail-fast stubs: rc 1 (the first stub stops the run), exactly
# the named stage banners, and at least one stubbed call.
ff_row() {
    local label="$1" want="$2" got
    shift 2
    run_gen ff "$@"
    [ "$RC" -eq 1 ] || { fail "$label — rc $RC, want 1 (fail-fast stub)"; return; }
    got="$(keys_line "$FX/out")"
    [ "$got" = "$want" ] || { fail "$label — stage banners '$got', want '$want'"; return; }
    [ -s "$CALL_LOG" ] || { fail "$label — no stubbed tool ran (stage never entered)"; return; }
    pass "$label"
}

# rej_row <label> <expected-stderr-substring> [args...] — rejected form:
# rc 2, no stage banner, the diagnostic + usage on stderr, and an EMPTY
# call log (no tool ran at all).
rej_row() {
    local label="$1" want="$2"
    shift 2
    run_gen ff "$@"
    [ "$RC" -eq 2 ] || { fail "$label — rc $RC, want 2"; return; }
    [ -z "$(keys_line "$FX/out")" ] || { fail "$label — entered stage '$(keys_line "$FX/out")'"; return; }
    [ -s "$CALL_LOG" ] && { fail "$label — a stubbed tool ran ($(head -n1 "$CALL_LOG"))"; return; }
    if grep -qF -- "$want" "$FX/err" && grep -qF 'usage: ./layout/reports/generate.sh' "$FX/err"; then
        pass "$label"
    else
        fail "$label — stderr lacks '$want' + usage:"
        sed 's/^/    /' "$FX/err" >&2
    fi
}

BEFORE="$(git -C "$REPO_ROOT" status --porcelain -- layout/reports)"

echo "=== 1. accepted forms: exactly their own stage entered (fail-fast stubs, rc 1) ==="
ff_row "no args enter the full run's first stage (0r.)" "0r."
ff_row "--row-path enters only the row decoder strip" "0r." --row-path
ff_row "--control enters only the control block" "0c." --control
ff_row "--column-path enters only the column path" "0." --column-path
ff_row "--column-path --native enters the column path (0n. sub-branch covered in section 4)" "0." --column-path --native
ff_row "--macro enters only the assembled-macro block" "0m." --macro
ff_row "--array64 enters only the 64 x 128 array block" "0a." --array64

echo "=== 2. rejected forms: rc 2, usage on stderr, no tool invoked ==="
rej_row "single EMPTY argument is rejected (the PR #502 regression)" "unknown flag:" ''
rej_row "unknown flag --bogus" "unknown flag: --bogus" --bogus
rej_row "--native alone is rejected" "unknown flag: --native" --native
rej_row "-h is rejected like any unknown flag" "unknown flag: -h" -h
rej_row "--column-path '' (empty second arg) is bad arguments" "bad arguments:" --column-path ''
rej_row "--macro --native is bad arguments" "bad arguments:" --macro --native
rej_row "--column-path --foo is bad arguments" "bad arguments:" --column-path --foo
rej_row "three arguments are bad arguments" "bad arguments:" --row-path --control extra

echo "=== 3. no-arg full run: dispatch reached the full-run branch, full order (pass-through stubs) ==="
run_gen pt
[ "$RC" -eq 0 ] || { fail "no-arg pass-through run — rc $RC, want 0 (stubs succeed, nothing to write)"; }
GOT="$(keys_line "$FX/out")"
WANT="0r. 0c. 0. 1. 2. 3. 4. 5. 0a. 0m. done"
if [ "$RC" -eq 0 ] && [ "$GOT" = "$WANT" ]; then
    pass "full ordered stage list by banner order (0r,0c,0,1-5,0a,0m,done — done is full-run-only)"
else
    fail "no-arg pass-through run — banners '$GOT', want '$WANT'"
fi

echo "=== 4. --column-path --native reaches the native sub-branch (pass-through stubs) ==="
: > "$CALL_LOG"
rc=0
STUB_LOG="$CALL_LOG" STUB_EXIT=0 PATH="$FX/bin:$PATH" GF180_PDK_PATH="$FX/no-such-pdk" \
    "$GEN" --column-path --native >"$FX/out" 2>"$FX/err" || rc=$?
GOT="$(keys_line "$FX/out")"
if [ "$rc" -eq 1 ] && [ "$GOT" = "0. 0n." ]; then
    pass "0. then 0n. entered; pdk_env.sh refuses the fake install right after the 0n. banner (rc 1, no PDK needed)"
else
    fail "--column-path --native pass-through — rc $rc, banners '$GOT', want rc 1 / '0. 0n.'"
fi

echo "=== 5. mutation self-check: '' routed to the full run (pre-0d20c24 defect) is caught ==="
MUT="$FX/mut"
mkdir -p "$MUT"
sed -e 's/^if \[ \$# -eq 0 \]; then$/if [ $# -eq 0 ] || [ -z "${1:-}" ]; then/' \
    "$GEN" > "$MUT/generate.sh"
if ! grep -q '^if \[ \$# -eq 0 \] || \[ -z "\${1:-}" \]; then$' "$MUT/generate.sh"; then
    fail "mutation template drifted — sed no longer matches generate.sh's dispatch; update it"
else
    chmod +x "$MUT/generate.sh"
    : > "$CALL_LOG"
    mrc=0
    STUB_LOG="$CALL_LOG" STUB_EXIT=1 PATH="$FX/bin:$PATH" \
        "$MUT/generate.sh" '' >"$FX/out" 2>"$FX/err" || mrc=$?
    GOT="$(keys_line "$FX/out")"
    if [ "$mrc" -eq 1 ] && [ "$GOT" = "0r." ] && [ -s "$CALL_LOG" ]; then
        pass "mutated dispatch reroutes '' to the full run (rc 1, 0r. entered, tool called) — the section-2 row fails on it"
    else
        fail "mutated dispatch no longer exhibits the regression (rc $mrc, banners '$GOT') — mutation check is vacuous; update it"
    fi
fi

echo "=== 6. committed reports untouched ==="
AFTER="$(git -C "$REPO_ROOT" status --porcelain -- layout/reports)"
if [ "$BEFORE" = "$AFTER" ]; then
    pass "git status --porcelain -- layout/reports unchanged (stubs never write committed reports)"
else
    fail "layout/reports changed during the test:"
    echo "$AFTER" | sed 's/^/    /' >&2
fi

echo
if [ "$FAIL" -eq 0 ]; then
    echo "test-generate-dispatch: $PASS passed, 0 failed"
else
    echo "test-generate-dispatch: $PASS passed, $FAIL FAILED" >&2
    exit 1
fi
