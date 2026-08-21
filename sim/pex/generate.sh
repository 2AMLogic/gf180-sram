#!/usr/bin/env bash
# sim/pex/generate.sh -- issue #23, item 7 (post-layout PEX). Regenerates
# the one artifact this issue could produce for real: a parasitic-annotated
# extracted netlist for the bitcell, via `klt extract --deck gf180mcu
# --parasitics`. See ./README.md for why this directory stops there instead
# of a per-corner `klt pex` schematic-vs-extracted delta report.
#
# Run from the repo root:
#     ./sim/pex/generate.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT="sim/pex"
BITCELL_GDS=layout/bitcell/sram_bitcell_6t.gds

mkdir -p "$OUT/extracted-netlist"

klt extract --deck gf180mcu --parasitics --format json \
  "$BITCELL_GDS" -o "$OUT/extracted-netlist/sram_bitcell_6t.spice" \
  | tee "$OUT/extract-report.json" >/dev/null

python3 -c "
import json
d = json.load(open('$OUT/extract-report.json'))
print('status:', d['status'], '| devices:', d['device_count'], '| nets:', d['net_count'])
print('parasitics:', d.get('parasitics'))
"
