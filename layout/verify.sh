#!/usr/bin/env bash
# Regenerate the committed layout and re-run every check layout/README.md
# reports a number for. Run from the repo root:
#
#     ./layout/verify.sh            # bitcell + 3x3 abutment tile + full array
#     ./layout/verify.sh --quick    # skip the two full-array (minutes) steps
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

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. regenerate (determinism: the committed GDS must not change)"
$PY layout/bitcell/generate.py
$PY layout/sram_256x32/generate.py
if git diff --quiet -- "$BITCELL_GDS" "$ARRAY_GDS"; then
  echo "PASS: re-running both generators reproduced the committed GDS byte-for-byte"
else
  echo "FAIL: regenerated GDS differs from the committed GDS"
  git diff --stat -- "$BITCELL_GDS" "$ARRAY_GDS"
  exit 1
fi

hr "2. layout hygiene (klt precheck, 5 nm grid)"
klt precheck --deck gf180mcu --grid-um 0.005 "$BITCELL_GDS"
klt precheck --deck gf180mcu --grid-um 0.005 "$ARRAY_GDS"

hr "3. DRC: bitcell (klt drc --deck gf180mcu)"
klt drc --deck gf180mcu "$BITCELL_GDS"

hr "4. DRC: 3x3 abutment tile (proves tiling adds no violation)"
$PY layout/sram_256x32/generate.py --rows 3 --cols 3 -o "$WORK/tile3x3.gds" >/dev/null
klt drc --deck gf180mcu "$WORK/tile3x3.gds"

hr "5. device extraction + LVS: bitcell vs design/netlist/bitcell_6t.spice"
klt extract --deck gf180mcu "$BITCELL_GDS" -o "$WORK/bitcell.spice"
python3 layout/lvs_reference.py design/netlist/bitcell_6t.spice \
  --layout-netlist "$WORK/bitcell.spice" -o "$WORK/bitcell_ref.spice"
klt lvs "{\"layout\":{\"netlist\":\"$WORK/bitcell.spice\",\"top\":\"sram_bitcell_6t\"},\
\"reference\":{\"netlist\":\"$WORK/bitcell_ref.spice\",\"form\":\"subckt-call\"}}"

if [ "$QUICK" = "1" ]; then
  hr "skipped (--quick): full-array DRC and extraction"
  exit 0
fi

hr "6. DRC: full 256x32 array (~1 min)"
klt drc --deck gf180mcu "$ARRAY_GDS"

hr "7. device extraction: full 256x32 array (~1.5 min)"
klt extract --deck gf180mcu "$ARRAY_GDS" -o "$WORK/array.spice"
