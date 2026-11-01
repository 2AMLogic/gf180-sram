#!/usr/bin/env bash
# design/regen_periphery.sh -- regenerate the 4:1 array + periphery schematics
# and netlist every new block with `klt netlist` (never raw xschem).
#
# Usage: design/regen_periphery.sh [--check]
#   (default)  rewrite design/*.sch, *.sym and design/netlist/*.spice
#   --check    regenerate the schematics, then verify each committed netlist
#              still matches (`klt netlist --check`, exit 3 on drift)
#
# Netlists use design/xschemrc.lvs so each sheet's .subckt is live and a wrapped
# pin list keeps its '+' continuation lines.
set -euo pipefail
cd "$(dirname "$0")/.."
export PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}" PDK="${PDK:-gf180mcuD}"

python3 design/generate_array.py --rows 64 --cols 128 --out design/sram_64x128_array.sch
python3 design/generate_periphery.py --outdir design

BLOCKS=(sram_64x128_array inv inv_x4 inv_x8 inv_x16 inv_dly nand2 nand3 and2 and3 and4
        rowdrv nor3 tg_s tg_mux dff sa_latch wdrv precharge_slice io_slice
        row_path col_decode sram_ctrl sram_256x32)
extra=()
[[ "${1:-}" == "--check" ]] && extra=(--check)
for b in "${BLOCKS[@]}"; do
  klt netlist "design/$b.sch" -o "design/netlist/$b.spice" \
      --rcfile design/xschemrc.lvs "${extra[@]}" >/dev/null
done
echo "design: ${#BLOCKS[@]} netlists ${1:-regenerated}"
