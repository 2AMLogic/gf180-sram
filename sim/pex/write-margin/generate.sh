#!/usr/bin/env bash
# sim/pex/write-margin/generate.sh -- issue #95. Regenerates the by-hand
# write-margin PEX evidence end to end:
#   1. (re)extracts a --pdk-bound parasitic netlist (./dut/generate.sh)
#   2. runs the schematic-side and extracted-side testbenches
#      (./testbench/tb_write_margin_*.spice) through the deck-mode path
#      (#437): `deck_adapter.py build` stages each leg's DUT file per unit,
#      `klt sim` runs the 27-corner grid on the batch fleet, `reduce` grades
#      it, and `mint_corner_records.py` mints the append-only record
#   3. computes the per-corner delta table (./compare_records.py)
#
# See ../README.md for why this by-hand workflow exists instead of `klt
# pex` itself (write-margin's bisection search has no `.meas`-only
# equivalent klt sim's request format can express), and for the deck-mode
# migration history (#230 cutover, #437 port).
#
# Run from the repo root:
#     ./sim/pex/write-margin/generate.sh
#
# Grids go through `klt sim --backend batch --wait-for-capacity 600` --
# never a local ngspice loop (host policy; sim/README.md "Staged migration
# to `klt sim` deck mode"). A leg mints its record only when its full-grid
# grading is `recorded` -- an OPEN grid refuses rather than minting a
# partially-open regeneration of append-only evidence.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

# One leg: build -> fleet run -> grade -> mint. Echoes everything (the
# caller captures it for the record-id grep), and aborts on any non-zero
# step or a grading that is not `recorded` (set -e).
run_leg() {
  local family="$1" leg="$2" claim="$3"
  echo "--- $leg leg ($family) ---"
  python3 sim/lib/deck_adapter.py build "$family" \
    --stage-dir "$scratch/$family" \
    --request-out "$scratch/$family/request.json"

  klt sim "$scratch/$family/request.json" \
    --backend batch --wait-for-capacity 600 \
    -o "$scratch/out-$family" \
    --report-out "$scratch/report-$family.json" --format json

  python3 sim/lib/deck_adapter.py reduce "$family" "$scratch/report-$family.json" \
    --request "$scratch/$family/request.json" \
    --outdir "$scratch/out-$family" \
    --json-out "$scratch/reduced-$family.json"

  python3 - "$scratch/reduced-$family.json" <<'EOF'
import json, sys
with open(sys.argv[1]) as f:
    reduced = json.load(f)
if reduced.get("overall") != "recorded":
    sys.exit(f"{sys.argv[1]}: grading is {reduced.get('overall')!r} -- an OPEN grid "
             "never mints a record; fix the OPEN corners above and re-run")
EOF

  python3 sim/lib/mint_corner_records.py "$family" "$scratch/reduced-$family.json" \
    --request "$scratch/$family/request.json" \
    --report "$scratch/report-$family.json" \
    --unit-dir "$scratch/out-$family" \
    --claim "$claim"
}

echo "=== 1/3: (re)extract --pdk-bound parasitic netlist ==="
./sim/pex/write-margin/dut/generate.sh

echo
echo "=== 2/3: deck-mode 27-corner grid + record mint, per leg ==="
sch_out="$(run_leg pex-write-margin-schematic SCHEMATIC \
  "spec/sram.md Characterization -- write margin (write trip voltage), post-layout PEX by-hand workflow (issue #95), SCHEMATIC leg")"
echo "$sch_out"
sch_record_id="$(echo "$sch_out" | grep '^record-id:' | tail -1 | awk '{print $2}')"

ext_out="$(run_leg pex-write-margin-extracted EXTRACTED \
  "spec/sram.md Characterization -- write margin (write trip voltage), post-layout PEX by-hand workflow (issue #95), EXTRACTED leg")"
echo "$ext_out"
ext_record_id="$(echo "$ext_out" | grep '^record-id:' | tail -1 | awk '{print $2}')"

echo
echo "=== 3/3: compare_records.py ==="
python3 sim/pex/write-margin/compare_records.py "$sch_record_id" "$ext_record_id"
