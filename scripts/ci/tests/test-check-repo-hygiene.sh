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
#   - "site-packages" as a filename substring NOT firing the venv rule,
#   - a tracked gitlink (submodule): a clean submodule tree passes, a
#     violation sorted after the gitlink is still reported (regression:
#     $((10#-)) on the gitlink's size "-" used to abort enumeration and
#     report PASS), and a truncated enumeration dies instead of passing.
#
# Fixtures and captured gate output live outside the repo under /tmp, at
# $$-suffixed paths so concurrent runs cannot read each other's state;
# they are removed on exit. The offending PR-branch commit from the
# incident is deliberately NOT pinned here — it lives on an unmerged
# branch and may be garbage-collected, which would rot the test
# (issue #361, Test Plan).

set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="$TEST_DIR/../check-repo-hygiene.sh"
REPO_ROOT="$(cd "$TEST_DIR/../../.." && pwd)"

FX=/tmp/loom-test-repo-hygiene.$$
OUT=/tmp/loom-test-repo-hygiene.$$.out
trap 'rm -rf "$FX" "$FX-subsrc" "$OUT"' EXIT

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1" >&2; FAIL=$((FAIL + 1)); }

# expect_ok <label> <fixture-dir> [gate args...]
expect_ok() {
    local label="$1" dir="$2"
    shift 2
    if (cd "$dir" && "$GATE" "$@" >"$OUT" 2>&1); then
        pass "$label"
    else
        fail "$label — gate did not pass; output:"
        sed 's/^/    /' "$OUT" >&2
    fi
}

# expect_fail <label> <fixture-dir> <expected-output-substring> [gate args...]
expect_fail() {
    local label="$1" dir="$2" want="$3"
    shift 3
    if (cd "$dir" && "$GATE" "$@" >"$OUT" 2>&1); then
        fail "$label — gate passed but should have failed"
        return
    fi
    if grep -qF -- "$want" "$OUT"; then
        pass "$label"
    else
        fail "$label — failed as expected but output does not name '$want':"
        sed 's/^/    /' "$OUT" >&2
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
if (cd "$REPO_ROOT" && "$GATE" >"$OUT" 2>&1); then
    pass "gate is green on the current repo HEAD"
else
    fail "gate is not green on the current repo HEAD:"
    sed 's/^/    /' "$OUT" >&2
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
expect_fail "9-byte-over cap file fails and names path+raw bytes+size" "$FX" "views/big.lef is 8388609 bytes (8.00 MiB), cap 8388608 bytes (8.00 MiB)" HEAD
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

echo "=== 6. gitlinks: clean submodule passes; violations after it still fire ==="
# Regression: a tracked gitlink's ls-tree size field is "-", and the gate
# once computed $((10#-)) on it, aborting enumeration mid-tree and
# reporting PASS on everything sorted after the gitlink.
git_add_submodule() { # git_add_submodule <name>  (adds a fresh sub-source at <name>)
    local src="$FX-subsrc"
    rm -rf "$src"
    git init -q -b main "$src"
    git -C "$src" config user.email ci@test.local
    git -C "$src" config user.name "CI fixture"
    echo submodule > "$src/s.txt"
    git -C "$src" add -A && git -C "$src" commit -qm submodule
    git -C "$FX" -c protocol.file.allow=always submodule add -q "$src" "$1"
}
new_fixture
git_add_submodule aaa-sub
echo hello > "$FX/README.md"
commit_fixture
expect_ok "clean tree containing a tracked gitlink passes" "$FX" HEAD
new_fixture
git_add_submodule aaa-sub
mkdir -p "$FX/zzz-views"
head -c $((9 * 1024 * 1024)) /dev/zero | tr '\0' 'a' > "$FX/zzz-views/huge.lef"
commit_fixture
expect_fail "oversize file sorted after a gitlink is still reported (no silent PASS)" "$FX" "zzz-views/huge.lef is 9437184 bytes" HEAD
new_fixture
git_add_submodule zzz-sub
mkdir -p "$FX/aaa-bin"
printf 'GDS\0II' > "$FX/aaa-bin/lib_db.so"
commit_fixture
expect_fail "binary violation sorted BEFORE a gitlink is still reported" "$FX" "aaa-bin/lib_db.so is binary to Git" HEAD

echo "=== 7. partial enumeration dies instead of passing ==="
# Pins the gate's count cross-check directly: a git shim truncates the
# size-bearing enumeration (`ls-tree -r -l -z`) to its first entry while
# the sizeless count enumeration passes through, simulating any future
# abort of the read loop. The gate must die, not report a verdict.
new_fixture
echo a > "$FX/a.txt"
echo b > "$FX/b.txt"
commit_fixture
mkdir -p "$FX/shim"
REAL_GIT="$(command -v git)"
cat > "$FX/shim/git" <<SHIM
#!/usr/bin/env bash
# Generated by test-check-repo-hygiene.sh: pass through to the real git
# ($REAL_GIT) except for ls-tree -r -l -z, whose output is truncated to
# the first NUL-delimited entry — simulating a mid-tree enumeration abort.
if [ "\$1" = ls-tree ] && [ "\$2" = -r ] && [ "\$3" = -l ] && [ "\$4" = -z ]; then
    "$REAL_GIT" "\$@" | head -z -n 1
else
    exec "$REAL_GIT" "\$@"
fi
SHIM
chmod +x "$FX/shim/git"
if (cd "$FX" && PATH="$FX/shim:$PATH" "$GATE" >"$OUT" 2>&1); then
    fail "truncated enumeration must not exit 0"
else
    if grep -qF "refusing to report a verdict on a partial tree" "$OUT"; then
        pass "truncated enumeration dies with the partial-tree message"
    else
        fail "truncated enumeration failed but not via the partial-tree guard; output:"
        sed 's/^/    /' "$OUT" >&2
    fi
fi

echo "=== 8. enumeration: paths with spaces are never word-split ==="
new_fixture
mkdir -p "$FX/a dir with spaces"
head -c $((9 * 1024 * 1024)) /dev/zero | tr '\0' 'a' > "$FX/a dir with spaces/huge blob.txt"
commit_fixture
expect_fail "oversize file with spaces in path fails, whole path intact" "$FX" "a dir with spaces/huge blob.txt is 9437184 bytes (9.00 MiB)" HEAD

echo "=== 9. usage/ref errors ==="
new_fixture
if (cd "$FX" && "$GATE" no-such-ref >/dev/null 2>&1); then
    fail "nonexistent ref must be rejected"
else
    pass "nonexistent ref is rejected"
fi

echo ""
echo "repo-hygiene gate self-tests: $PASS passed, $FAIL failed"
(( FAIL == 0 ))
