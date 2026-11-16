#!/usr/bin/env bash
# check-repo-hygiene.sh — hygiene gate for the *tracked* tree of a ref.
#
# Every other CI job in this repo (harness, evidence-format, signoff,
# array-schematics) is a content-correctness gate: they check that tracked
# evidence is well formed. None of them bounds *what* may be tracked at
# all. Issue #361 was filed after a PR ran green through all four gates
# while adding 216.4 MiB / 1054 files of a checked-in virtualenv
# (.venv-klt080/), so "files that should never be tracked" was an
# uncovered category, not a check that failed. Under this repo's
# merge-commit strategy such blobs enter history permanently, and the only
# recovery is a coordinated rewrite — this gate exists so the PR fails
# instead, for a few seconds of CI.
#
# Three independent assertions over every tracked path, each failing with
# the offending path (and size where applicable):
#
#   1. Size cap: no tracked blob may exceed SIZE_CAP_BYTES (8 MiB).
#        Derived from measurement on origin/main @ b818322 (2026-11-15;
#        re-confirmed on this PR's merged main @ 2406 tracked files,
#        2026-11-16 — same maximum, no new near-cap blobs):
#        the largest legitimately-tracked blob is
#        views/sram_256x32_array.lef at 4.97 MiB, followed by design/*.sch
#        at ~3.5 MiB and sim/ corner reports at ~2.4 MiB. 8 MiB is ~1.6x
#        headroom above the legitimate maximum (room for a larger macro's
#        LEF/schematic) while still catching the incident's 57.19 MiB and
#        12.51 MiB klayout .so blobs. NO path carve-out: the measured top
#        blobs live under views/, design/ AND sim/, so any per-path
#        allowlist (e.g. a sim/-only one) would false-fire on the other
#        two — that is the design decision issue #361 asked to settle.
#   2. Binary allowlist: a tracked file Git treats as binary (a NUL byte
#        in its first 8000 bytes — the same heuristic `git grep -I` uses)
#        must match layout/**/*.gds.
#        Derived from measurement on origin/main @ b818322 (2026-11-15;
#        re-confirmed on this PR's merged main @ 2406 tracked files,
#        2026-11-16 — still exactly 10, all GDSII under layout/):
#        exactly 10 tracked files are binary to Git and all of them are
#        GDSII under layout/ (largest layout/macro/sram_256x32.gds at
#        0.93 MiB); there were no other tracked binaries, which is what
#        makes a one-line allowlist enough.
#   3. Venv-shape denylist: a tracked pyvenv.cfg, or any path with a
#        site-packages/ path *component*, fails. Component match, not
#        substring: "docs/site-packages.md" is a filename, not a venv.
#        This targets the issue's named category directly and catches a
#        hypothetical all-text venv that rules 1 and 2 would miss.
#
# Usage: scripts/ci/check-repo-hygiene.sh [<ref>]
#   <ref> defaults to HEAD. The argument exists so the test suite can run
#   this exact script against fixture commits (see
#   scripts/ci/tests/test-check-repo-hygiene.sh), not as a feature.
#
# Rejected alternatives (issue #361, Implementation Guidance):
#   - total-repo-size / added-bytes delta threshold: sim/ is append-only
#     evidence that grows legitimately every run, so a delta bound either
#     drifts upward forever or false-fires on normal evidence commits;
#   - a sim/-only size allowlist: measured false, the largest legitimate
#     blobs are under views/ and design/;
#   - pattern-matching venv directory names here: redundant once
#     .gitignore covers the siblings and rules 1-3 are in place;
#   - a pre-commit hook instead of CI: the incident arrived via an
#     agent's remediation commit, so the gate has to run where it cannot
#     be bypassed.
set -euo pipefail

SIZE_CAP_BYTES=$((8 * 1024 * 1024))  # 8 MiB; derivation in the header comment
GDS_ALLOWLIST_PATTERN='layout/*.gds' # in [[ == ]], * crosses '/', i.e. layout/**/*.gds

die() {
    echo "check-repo-hygiene: $*" >&2
    exit 2
}

if (( $# > 1 )); then
    die "usage: $0 [<ref>]  (default: HEAD)"
fi
REF="${1:-HEAD}"

COMMIT="$(git rev-parse --verify --quiet "$REF^{commit}" || true)"
[[ -n "$COMMIT" ]] || die "not a commit-ish: $REF"

# Git's own binary heuristic (buffer_is_binary): a NUL byte in the first
# 8000 bytes. `|| true` because `head -c` closing the pipe early can
# SIGPIPE `git cat-file` (exit 141) under pipefail; wc still reports the
# full count of the bytes head passed through, which is what we want.
blob_is_binary() {
    local nuls
    nuls="$(git cat-file blob "$COMMIT:$1" | head -c 8000 | tr -d -c '\0' | wc -c)" || true
    (( nuls > 0 ))
}

violations=0
files=0
report() { # report <rule> <detail...>
    echo "repo-hygiene: $1: $2"
    violations=$((violations + 1))
}

mib() { awk -v b="$1" 'BEGIN { printf "%.2f MiB", b / 1048576 }'; }

# One -z enumeration of the tracked tree feeds all three rules; -z keeps
# paths with spaces intact (they are never word-split).
while IFS= read -r -d '' entry; do
    # Entry format: "<mode> <type> <object> <size>\t<path>"
    meta="${entry%%$'\t'*}"
    path="${entry#*$'\t'}"
    rawsize="${meta##* }"
    files=$((files + 1))

    # Rule 3: venv-shape denylist. Path-component matches only; applies
    # to gitlink paths too (a submodule under site-packages/ is still a
    # venv shape).
    if [[ "/$path" == */pyvenv.cfg ]]; then
        report "venv-shape" "$path (pyvenv.cfg must never be tracked)"
    elif [[ "/$path/" == */site-packages/* ]]; then
        report "venv-shape" "$path (inside a site-packages/ directory)"
    fi

    # Gitlinks (submodules) have size "-"; they are not blobs, so the
    # blob rules below do not apply. This guard must precede the size
    # arithmetic: $((10#-)) is an arithmetic error that would abort the
    # read loop mid-tree, and a truncated enumeration must never reach
    # the success path (cross-checked after the loop).
    [[ "$rawsize" == "-" ]] && continue
    size="$((10#$rawsize))"

    # Rule 1: size cap (a blob at exactly the cap passes; one byte over fails).
    # Raw bytes first: the MiB figure rounds, so a one-byte-over blob would
    # otherwise read "8.00 MiB vs 8.00 MiB" and look like a false fire.
    if (( size > SIZE_CAP_BYTES )); then
        report "size-cap" "$path is $size bytes ($(mib "$size")), cap ${SIZE_CAP_BYTES} bytes ($(mib "$SIZE_CAP_BYTES"))"
    fi

    # Rule 2: binary allowlist. Allowlisted .gds files skip the blob read.
    # Glob matching is intended here: in [[ == ]], an unquoted * crosses
    # '/', so layout/*.gds means layout/**/*.gds.
    # shellcheck disable=SC2053
    [[ "$path" == $GDS_ALLOWLIST_PATTERN ]] && continue
    if blob_is_binary "$path"; then
        report "binary" "$path is binary to Git but outside the allowlist ($GDS_ALLOWLIST_PATTERN)"
    fi
done < <(git ls-tree -r -l -z "$COMMIT")

# A partial enumeration must never look like a pass: before the gitlink
# guard above existed, one $((10#-)) arithmetic error aborted the read
# loop and the gate reported PASS on a truncated tree. Cross-check the
# loop's count against a second, sizeless enumeration so ANY future
# abort — whatever its cause — dies here instead of passing green.
expected="$(git ls-tree -r -z "$COMMIT" | tr -cd '\0' | wc -c)"
(( files == expected )) || die "enumerated $files of $expected tracked entries at $COMMIT — refusing to report a verdict on a partial tree"
(( files > 0 )) || die "ref $COMMIT tracks no files — refusing to pass vacuously"

if (( violations > 0 )); then
    echo "repo-hygiene: FAILED — $violations violation(s) across $files tracked files at $COMMIT"
    exit 1
fi

echo "repo-hygiene check passed: $files tracked files at $COMMIT ($REF), 0 violations" \
    "(size cap $(mib "$SIZE_CAP_BYTES"), binary allowlist layout/**/*.gds, venv-shape denylist)"
