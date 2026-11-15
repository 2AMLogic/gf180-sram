#!/usr/bin/env bash
# test-check-repo-hygiene.sh — self-tests for scripts/ci/check-repo-hygiene.sh
# (issue #361).
#
# Runs the real gate against this repo's HEAD (the clean-ref pass) and
# against throwaway fixture repos built under mktemp, one per rule and
# edge case, mirroring the Test Plan in issue #361:
#   - clean pass (including an allowlisted layout/**/*.gds binary, a
#     nested one, and an empty tracked file),
#   - each of the three rules firing individually and naming the
#     offending path (and size for the size cap),
#   - the exact 8 MiB boundary passing while one byte over fails,
#   - a .gds binary outside layout/ failing the allowlist,
#   - a path containing spaces surviving enumeration without word-split,
#   - "site-packages" as a filename substring NOT firing the venv rule.
#
# Fixtures live outside the repo (mktemp -d) and are removed on exit; the
# offending PR-branch commit from the incident is deliberately NOT pinned
# here — it lives on an unmerged branch and may be garbage-collected,
# which would rot the test (issue #361, Test Plan).

set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="$TEST_DIR/../check-repo-hygiene.sh"
REPO_ROOT="$(cd "$TEST_DIR/../../.." && pwd)"

FX=/tmp/loom-test-repo-hygiene.$$
trap 'rm -rf "$FX"' EXIT

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1" >&2; FAIL=$((FAIL + 1)); }

# expect_ok <label> <fixture-dir> [gate args...]
expect_ok() {
    local label="$1" dir="$2"
    shift 2
    if (cd "$dir" && "$GATE" "$@" >/tmp/loom-test-repo-hygiene.out 2>&1); then
        pass "$label"
    else
        fail "$label — gate did not pass; output:"
        sed 's/^/    /' /tmp/loom-test-repo-hygiene.out >&2
    fi
}

# expect_fail <label> <fixture-dir> <expected-output-substring> [gate args...]
expect_fail() {
    local label="$1" dir="$2" want="$3"
    shift 3
    if (cd "$dir" && "$GATE" "$@" >/tmp/loom-test-repo-hygiene.out 2>&1); then
        fail "$label — gate passed but should have failed"
        return
    fi
    if grep -qF -- "$want" /tmp/loom-test-repo-hygiene.out; then
        pass "$label"
    else
        fail "$label — failed as expected but output does not name '$want':"
        sed 's/^/    /' /tmp/loom-test-repo-hygiene.out >&2
    fi
}

new_fixture() {
    rm -rf "$FX"
    mkdir -p "$FX"
    git -C "$FX" init -q -b main
    git -C "$FX" config user.email ci@test.local
    git -C "$FX" config user.name "CI fixture"
}

commit_fixture() { git -C "$FX" add -A && git -C "$FX" commit -qm "fixture"; }

echo "=== 1. clean-ref pass: this repo's HEAD (no explicit ref argument) ==="
if (cd "$REPO_ROOT" && "$GATE" >/tmp/loom-test-repo-hygiene.out 2>&1); then
    pass "gate is green on the current repo HEAD"
else
    fail "gate is not green on the current repo HEAD:"
    sed 's/^/    /' /tmp/loom-test-repo-hygiene.out >&2
fi

echo "=== 2. clean fixture: text files, allowlisted .gds binaries, empty file ==="
new_fixture
mkdir -p "$FX/layout/macro/nested" "$FX/docs"
echo hello > "$FX/README.md"
printf 'GDS\0II fake gds payload' > "$FX/layout/macro/cell.gds"
printf 'GDS\0II nested allowlist entry' > "$FX/layout/macro/nested/deep.gds"
: > "$FX/docs/empty.txt"
echo "site-packages notes" > "$FX/docs/site-packages.md"
mkdir -p "$FX/some dir"
echo "spaces are fine" > "$FX/some dir/plain text.md"
commit_fixture
expect_ok "no violations in a clean tree (incl. .gds binaries, empty file, spaced path, site-packages filename)" "$FX" HEAD

echo "=== 3. size rule: >8 MiB text blob fires; exactly 8 MiB does not ==="
new_fixture
mkdir -p "$FX/views"
head -c $((8 * 1024 * 1024 + 1)) /dev/zero | tr '\0' 'a' > "$FX/views/big.lef"
commit_fixture
expect_fail "9-byte-over cap file fails and names path+size" "$FX" "views/big.lef is 8.00 MiB (cap 8388608 bytes" HEAD
new_fixture
mkdir -p "$FX/views"
head -c $((8 * 1024 * 1024)) /dev/zero | tr '\0' 'a' > "$FX/views/at-cap.lef"
commit_fixture
expect_ok "file at exactly the 8 MiB cap passes" "$FX" HEAD

echo "=== 4. binary rule: NUL byte outside layout/**/*.gds fires ==="
new_fixture
mkdir -p "$FX/klayout"
printf 'GDS\0II' > "$FX/klayout/lib_db.so"
commit_fixture
expect_fail "binary outside the allowlist fails and names path" "$FX" "klayout/lib_db.so is binary to Git" HEAD
new_fixture
mkdir -p "$FX/docs"
printf 'PDF\0binary' > "$FX/docs/spec.pdf"
commit_fixture
expect_fail "binary .gds outside layout/ still fails (allowlist is path-shaped)" "$FX" "docs/spec.pdf is binary to Git" HEAD

echo "=== 5. venv rule: pyvenv.cfg and site-packages/ components fire ==="
new_fixture
: > "$FX/pyvenv.cfg"
commit_fixture
expect_fail "tracked pyvenv.cfg fails and names path" "$FX" "pyvenv.cfg (pyvenv.cfg must never be tracked)" HEAD
new_fixture
mkdir -p "$FX/.venv-x/lib/site-packages/pkg"
echo x > "$FX/.venv-x/lib/site-packages/pkg/__init__.py"
commit_fixture
expect_fail "path under a site-packages/ component fails and names path" "$FX" ".venv-x/lib/site-packages/pkg/__init__.py (inside a site-packages/ directory)" HEAD

echo "=== 6. enumeration: paths with spaces are never word-split ==="
new_fixture
mkdir -p "$FX/a dir with spaces"
head -c $((9 * 1024 * 1024)) /dev/zero | tr '\0' 'a' > "$FX/a dir with spaces/huge blob.txt"
commit_fixture
expect_fail "oversize file with spaces in path fails, whole path intact" "$FX" "a dir with spaces/huge blob.txt is 9.00 MiB" HEAD

echo "=== 7. usage/ref errors ==="
new_fixture
if (cd "$FX" && "$GATE" no-such-ref >/dev/null 2>&1); then
    fail "nonexistent ref must be rejected"
else
    pass "nonexistent ref is rejected"
fi

echo ""
echo "repo-hygiene gate self-tests: $PASS passed, $FAIL failed"
(( FAIL == 0 ))
