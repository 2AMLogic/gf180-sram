#!/usr/bin/env bash
# PDK-free functional check of the behavioural model views/sram_256x32.v
# (issue #468): pin list vs the #198 macro boundary, then the self-checking
# Icarus bench through `klt functional-verification`. One command, works
# from a fresh clone, needs no PDK, no klayout, no ngspice:
#
#     ./views/check_model.sh
#
# klt resolution: `uvx --from klayout-tools==0.8.0 klt` when uv is present
# (the repo pin, the same way views/verify.sh and signoff/regenerate.sh pin
# it -- never a klt already on the host), else a `klt` on PATH (how CI's
# harness job provides it, pip-installed at the same version).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

KLT_VERSION="0.8.0"
if command -v uvx >/dev/null 2>&1; then
  KLT="uvx --from klayout-tools==$KLT_VERSION klt"
else
  KLT="klt"
fi

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. pin list: views/sram_256x32.v vs the #198 macro boundary"
python3 design/check_macro_pins.py views/sram_256x32.v

hr "2. klt functional-verification (klayout-tools $KLT_VERSION, icarus) on views/fv_sram_256x32.json"
$KLT functional-verification views/fv_sram_256x32.json

echo
echo "Model check passed: pin list + self-checking bench."
