#!/usr/bin/env bash
# Thin wrapper so the CI workflow (and local runs) have a single stable
# entry point, independent of how the underlying check is implemented.
#
# Usage: scripts/ci/check-evidence-format.sh
#
# See scripts/ci/check_evidence_format.py for what this validates.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec python3 "$SCRIPT_DIR/check_evidence_format.py"
