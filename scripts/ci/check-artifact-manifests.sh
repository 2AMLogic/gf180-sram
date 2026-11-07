#!/usr/bin/env bash
# Thin wrapper so the CI workflow (and local runs) have a single stable
# entry point for the stored-evidence manifest check.
#
# Usage: scripts/ci/check-artifact-manifests.sh
#
# See scripts/check_artifact_manifests.py for what this validates.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec python3 "$SCRIPT_DIR/../check_artifact_manifests.py"
