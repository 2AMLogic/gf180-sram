#!/usr/bin/env bash
# Thin wrapper so the CI workflow (and local runs) have a single stable
# entry point, independent of how the underlying check is implemented —
# the same shape as scripts/ci/check-signoff-freshness.sh.
#
# Usage: scripts/ci/check-provenance-hygiene.sh [--self-test]
#
# Runs `klt env-provenance scan` over the tracked JSON evidence reports under
# layout/reports/ and views/reports/ and fails on any home-directory-shaped
# path that is not named in scripts/ci/provenance-leak-baseline.txt (issue
# #340, enforcing issue #109's provenance-hygiene rule). The grandfathered
# entries are printed on every run, pass or fail, so a green build still shows
# which known leaks exist. `--self-test` checks that the guard can actually
# fail, on synthetic fixtures.
#
# Requires klt on PATH — the pinned released version, installed by
# .github/workflows/ci.yml's `provenance-hygiene` job. `env-provenance scan`
# has shipped since klayout-tools 0.8.0.
set -euo pipefail

if ! command -v klt >/dev/null 2>&1; then
    echo "FATAL: klt (klayout-tools) is required on PATH." >&2
    echo "       pip install klayout-tools==0.8.0   # pinned released version" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec python3 "$SCRIPT_DIR/check_provenance_hygiene.py" "$@"
