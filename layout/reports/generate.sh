#!/usr/bin/env bash
# layout/reports/generate.sh -- issue #23 (T1 items 3/4: DRC clean, LVS
# clean). Regenerates every committed report in this directory from the
# committed layout + design sources and overwrites them in place -- these
# reports are a *current-state signoff snapshot*, not append-only evidence
# like sim/*/records/ (see layout/reports/README.md "Freshness" for why that
# distinction is deliberate here).
#
# Run from the repo root:
#     ./layout/reports/generate.sh
#
# Requires: klt (klayout-tools) on PATH, python3. No PDK install needed --
# klt's curated gf180mcu deck is bundled, same as layout/verify.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT="layout/reports"
BITCELL_GDS=layout/bitcell/sram_bitcell_6t.gds
ARRAY_GDS=layout/sram_256x32/sram_256x32_array.gds
BITCELL_REF=design/netlist/bitcell_6t.spice
ARRAY_REF=design/netlist/sram_256x32_array.spice

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. DRC: bitcell (klt drc --deck gf180mcu)"
klt drc --deck gf180mcu --format json "$BITCELL_GDS" | tee "$OUT/drc-bitcell.json" >/dev/null
python3 -c "import json,sys; d=json.load(open('$OUT/drc-bitcell.json')); print('status:', d['status'], '| violations:', d['violation_count'])"

hr "2. DRC: full 256x32 array (klt drc --deck gf180mcu, ~30-60s)"
klt drc --deck gf180mcu --format json "$ARRAY_GDS" | tee "$OUT/drc-array.json" >/dev/null
python3 -c "import json,sys; d=json.load(open('$OUT/drc-array.json')); print('status:', d['status'], '| violations:', d['violation_count'])"

hr "3. Extract + LVS: bitcell vs $BITCELL_REF"
klt extract --deck gf180mcu --format json "$BITCELL_GDS" -o "$WORK/bitcell.spice" | tee "$OUT/extract-bitcell.json" >/dev/null
python3 layout/lvs_reference.py "$BITCELL_REF" \
  --layout-netlist "$WORK/bitcell.spice" -o "$WORK/bitcell_ref.spice"
cat > "$WORK/lvs-bitcell-request.json" <<EOF
{"layout":{"netlist":"$WORK/bitcell.spice","top":"sram_bitcell_6t"},
 "reference":{"netlist":"$WORK/bitcell_ref.spice","form":"subckt-call"}}
EOF
klt lvs "$WORK/lvs-bitcell-request.json" --format json | tee "$OUT/lvs-bitcell.json" >/dev/null
python3 -c "import json,sys; d=json.load(open('$OUT/lvs-bitcell.json')); print('status:', d['status'], '| mismatches:', d['mismatch_count'])"

hr "4. Extract + LVS: full array vs $ARRAY_REF (flatten_reference -- klayout-tools#1085)"
klt extract --deck gf180mcu --format json "$ARRAY_GDS" -o "$WORK/array.spice" > "$WORK/extract-array-full.json"
# The full per-device/per-net report is ~18 MB (49,152 devices) -- not
# useful to commit verbatim. Keep every field except the two bulk arrays;
# device_count/net_count/pin_count (still present) already summarize them.
python3 -c "
import json
d = json.load(open('$WORK/extract-array-full.json'))
d.pop('devices', None)
d.pop('nets', None)
d['_note'] = 'devices[]/nets[] omitted from this committed report (49152 devices / 16706 nets -- see device_count/net_count/pin_count above); full output reproducible via layout/reports/generate.sh'
json.dump(d, open('$OUT/extract-array.json', 'w'), indent=2)
print('status:', d['status'], '| devices:', d['device_count'], '| nets:', d['net_count'], '| pins:', d['pin_count'])
"
cat > "$WORK/lvs-array-request.json" <<EOF
{"layout":{"netlist":"$WORK/array.spice","top":"sram_256x32_array"},
 "reference":{"netlist":"$ROOT/$ARRAY_REF","form":"subckt-call"},
 "options":{"flatten_reference":true}}
EOF
klt lvs "$WORK/lvs-array-request.json" --format json | tee "$OUT/lvs-array.json" >/dev/null
python3 -c "import json,sys; d=json.load(open('$OUT/lvs-array.json')); print('status:', d['status'], '| mismatches:', d['mismatch_count'])"

hr "done -- reports written under $OUT/"
