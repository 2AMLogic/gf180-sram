#!/usr/bin/env bash
# sim/pex/write-margin/generate.sh -- issue #95. Regenerates the by-hand
# write-margin PEX evidence end to end:
#   1. (re)extracts a --pdk-bound parasitic netlist (./dut/generate.sh)
#   2. runs sim/lib/run_corner_sweep.sh against the schematic-side and
#      extracted-side testbenches (./testbench/tb_write_margin_*.spice)
#   3. computes the per-corner delta table (./compare_records.py)
#
# See ../README.md for why this by-hand workflow exists instead of `klt
# pex` itself (write-margin's bisection search has no `.meas`-only
# equivalent klt sim's request format can express).
#
# Run from the repo root:
#     ./sim/pex/write-margin/generate.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

echo "=== 1/3: (re)extract --pdk-bound parasitic netlist ==="
./sim/pex/write-margin/dut/generate.sh

echo
echo "=== 2/3: run_corner_sweep.sh -- schematic leg ==="
sch_out="$(./sim/lib/run_corner_sweep.sh sim/pex/write-margin \
  sim/pex/write-margin/testbench/tb_write_margin_schematic.spice "direct" \
  "spec/sram.md Characterization -- write margin (write trip voltage), post-layout PEX by-hand workflow (issue #95), SCHEMATIC leg")"
echo "$sch_out"
sch_record_id="$(echo "$sch_out" | grep '^record-id:' | tail -1 | awk '{print $2}')"

echo
echo "=== 2/3: run_corner_sweep.sh -- extracted leg ==="
ext_out="$(./sim/lib/run_corner_sweep.sh sim/pex/write-margin \
  sim/pex/write-margin/testbench/tb_write_margin_extracted.spice "direct" \
  "spec/sram.md Characterization -- write margin (write trip voltage), post-layout PEX by-hand workflow (issue #95), EXTRACTED leg")"
echo "$ext_out"
ext_record_id="$(echo "$ext_out" | grep '^record-id:' | tail -1 | awk '{print $2}')"

echo
echo "=== 3/3: compare_records.py ==="
python3 sim/pex/write-margin/compare_records.py "$sch_record_id" "$ext_record_id"
