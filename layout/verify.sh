#!/usr/bin/env bash
# Regenerate the committed layout and re-run every check layout/README.md
# reports a number for. Run from the repo root:
#
#     ./layout/verify.sh            # bitcell + 3x3 tile + full arrays + column path
#     ./layout/verify.sh --quick    # skip the full-array and column-seam (minutes) steps
#
# This is a *layout self-check*, not the signoff flow: DRC/LVS/PEX sign-off
# evidence (with a recorded, append-only evidence trail) is issue #23's job.
# Nothing here writes into sim/.
set -euo pipefail

QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PY="uv run --with klayout python3"
BITCELL_GDS=layout/bitcell/sram_bitcell_6t.gds
ARRAY_GDS=layout/sram_256x32/sram_256x32_array.gds
COLUMN_DIR=layout/periphery/column
PRECHARGE_GDS=$COLUMN_DIR/precharge_slice.gds
IO_GDS=$COLUMN_DIR/io_slice.gds
BAND_GDS=$COLUMN_DIR/column_band.gds
ARRAY64_GDS=layout/sram_64x128/sram_64x128_array.gds
ROW_GDS=layout/periphery/row/row_path.gds
CTRL_DIR=layout/periphery/control
CTRL_GDS=$CTRL_DIR/sram_ctrl.gds
COLDEC_GDS=$CTRL_DIR/col_decode.gds

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. regenerate (determinism: the committed GDS must not change)"
$PY layout/bitcell/generate.py
$PY layout/sram_256x32/generate.py
$PY $COLUMN_DIR/generate.py
# The ratified 4:1 organization (spec/periphery-architecture.md): same
# generator, 64 rows x 128 cols (issue #204).
$PY layout/sram_256x32/generate.py --rows 64 --cols 128 \
  --top-name sram_64x128_array -o "$ARRAY64_GDS"
# The row-decoder + wordline-driver strip (issue #204).
$PY layout/periphery/row/generate.py
# The control block and the column decoder (issue #246).
$PY $CTRL_DIR/generate.py
GENERATED_GDS="$BITCELL_GDS $ARRAY_GDS $ARRAY64_GDS $PRECHARGE_GDS $IO_GDS $BAND_GDS $ROW_GDS $CTRL_GDS $COLDEC_GDS"
if git diff --quiet -- $GENERATED_GDS; then
  echo "PASS: re-running the generators reproduced the committed GDS byte-for-byte"
else
  echo "FAIL: regenerated GDS differs from the committed GDS"
  git diff --stat -- $GENERATED_GDS
  exit 1
fi

hr "2. layout hygiene (klt precheck, 5 nm grid)"
klt precheck --deck gf180mcu --grid-um 0.005 "$BITCELL_GDS"
klt precheck --deck gf180mcu --grid-um 0.005 "$ARRAY_GDS"
klt precheck --deck gf180mcu --grid-um 0.005 "$ARRAY64_GDS"
for gds in "$PRECHARGE_GDS" "$IO_GDS" "$BAND_GDS" "$ROW_GDS" "$CTRL_GDS" "$COLDEC_GDS"; do
  klt precheck --deck gf180mcu --grid-um 0.005 "$gds"
done

hr "3. DRC: bitcell (klt drc --deck gf180mcu)"
klt drc --deck gf180mcu "$BITCELL_GDS"

hr "4. DRC: 3x3 abutment tile (proves tiling adds no violation)"
$PY layout/sram_256x32/generate.py --rows 3 --cols 3 -o "$WORK/tile3x3.gds" >/dev/null
klt drc --deck gf180mcu "$WORK/tile3x3.gds"

hr "5. device extraction + LVS: bitcell vs design/netlist/bitcell_6t.spice"
klt extract --deck gf180mcu "$BITCELL_GDS" -o "$WORK/bitcell.spice"
klt lvs "{\"layout\":{\"netlist\":\"$WORK/bitcell.spice\",\"top\":\"sram_bitcell_6t\"},\
\"reference\":{\"netlist\":\"$ROOT/design/netlist/bitcell_6t.spice\",\"form\":\"subckt-call\"}}"

hr "5b. DRC: column path -- both slices and the 32-slice bands (issue #205)"
for gds in "$PRECHARGE_GDS" "$IO_GDS" "$BAND_GDS"; do
  klt drc --deck gf180mcu "$gds"
done

hr "5c. extraction + LVS: column slices vs design/netlist/{precharge,io}_slice.spice"
# The reference netlists are hierarchical (dff -> inv/tg_s); the layout is
# drawn flat per slice, so the reference is flattened (same option, and the same
# disclosed topology.flattened warning, as the array LVS -- see README). The
# layout side is extracted inline (layout.file + deck): only that form carries
# the drawn labels `net.supply_fragmented` needs, which matters here because
# each slice has several same-net supply rails.
for cell in precharge_slice io_slice; do
  klt extract --deck gf180mcu "$COLUMN_DIR/$cell.gds" -o "$WORK/$cell.spice"
  klt lvs "{\"layout\":{\"file\":\"$ROOT/$COLUMN_DIR/$cell.gds\",\"deck\":\"gf180mcu\",\"top\":\"$cell\"},\
\"reference\":{\"netlist\":\"$ROOT/design/netlist/$cell.spice\",\"form\":\"subckt-call\"},\
\"options\":{\"flatten_reference\":true}}"
done

hr "5d. DRC + extraction + LVS: row decoder / wordline-driver strip vs design/netlist/row_path.spice (issue #204)"
# Strip only: 16 predecoders + 64 rowdrv, one flat cell. This says nothing about
# the strip fitting the array or the wordline RC (README "Row path").
klt drc --deck gf180mcu "$ROW_GDS"
klt extract --deck gf180mcu "$ROW_GDS" -o "$WORK/row_path.spice"
klt lvs "{\"layout\":{\"file\":\"$ROOT/$ROW_GDS\",\"deck\":\"gf180mcu\",\"top\":\"row_path\"},\
\"reference\":{\"netlist\":\"$ROOT/design/netlist/row_path.spice\",\"form\":\"subckt-call\"},\
\"options\":{\"flatten_reference\":true}}"

hr "5e. DRC + extraction + LVS: sram_ctrl and col_decode vs design/netlist/{sram_ctrl,col_decode}.spice (issue #246)"
# Block level only: two flat cells, each its own top. Says nothing about timing,
# delay-chain calibration or parasitics, nor about how the macro places or routes
# to the pins (README "Control block and column decoder").
for cell in sram_ctrl col_decode; do
  klt drc --deck gf180mcu "$CTRL_DIR/$cell.gds"
  klt extract --deck gf180mcu "$CTRL_DIR/$cell.gds" -o "$WORK/$cell.spice"
  klt lvs "{\"layout\":{\"file\":\"$ROOT/$CTRL_DIR/$cell.gds\",\"deck\":\"gf180mcu\",\"top\":\"$cell\"},\
\"reference\":{\"netlist\":\"$ROOT/design/netlist/$cell.spice\",\"form\":\"subckt-call\"},\
\"options\":{\"flatten_reference\":true}}"
done

if [ "$QUICK" = "1" ]; then
  hr "skipped (--quick): full-array DRC and extraction, column-seam DRC"
  exit 0
fi

hr "6. DRC: full 256x32 array (~1 min)"
klt drc --deck gf180mcu "$ARRAY_GDS"

hr "7. device extraction: full 256x32 array (~1.5 min)"
klt extract --deck gf180mcu "$ARRAY_GDS" -o "$WORK/array.spice"

hr "8. DRC: full 64x128 array (~1 min)"
klt drc --deck gf180mcu "$ARRAY64_GDS"

hr "9. device extraction + LVS: full 64x128 array vs design/netlist/sram_64x128_array.spice"
klt extract --deck gf180mcu "$ARRAY64_GDS" -o "$WORK/array64.spice"
klt lvs "{\"layout\":{\"netlist\":\"$WORK/array64.spice\",\"top\":\"sram_64x128_array\"},\
\"reference\":{\"netlist\":\"$ROOT/design/netlist/sram_64x128_array.spice\",\"form\":\"subckt-call\"},\
\"options\":{\"flatten_reference\":true}}"

hr "10. DRC: column bands abutted to the committed 64x128 array (bit-line seam, ~1 min)"
# #202 row 1: the 4:1 array is 64 rows x 128 columns (committed, step 8).
# `generate.py --abut` places io_slice x32 under it and precharge_slice x32
# above it at the array's own column x, so the Metal1 bit-line seam (and the
# first/last slice against the array's edges) is checked in one run. The
# composite is a scratch file; only its inputs are committed.
$PY $COLUMN_DIR/generate.py --abut "$ARRAY64_GDS" -o "$WORK/column_abut.gds" >/dev/null
klt drc --deck gf180mcu "$WORK/column_abut.gds"
