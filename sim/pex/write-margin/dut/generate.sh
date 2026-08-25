#!/usr/bin/env bash
# sim/pex/write-margin/dut/generate.sh -- issue #95. Regenerates a
# PDK-model-bound parasitic-annotated extracted netlist for the bitcell,
# used by ../testbench/tb_write_margin_extracted.spice.
#
# Differs from sim/pex/generate.sh's own `klt extract --deck gf180mcu
# --parasitics` (PR #96, no `--pdk`): that netlist's `M`-card model names
# are gf180mcu's bare, unbindable curated-deck class labels (`nfet`/`pfet`
# -- see docs/cli/extract.md "SPICE model binding"), which no real PDK
# ships as a directly-simulatable model, so it cannot be `.lib`'d against
# sm141064.ngspice and simulated as-is. Adding `--pdk` binds each device to
# a real `X nfet_03v3`/`pfet_03v3` subcircuit call instead, which the
# by-hand write-margin workflow (and sim/pex/access-time/'s klt-pex-native
# testbenches) both need to actually run ngspice against.
#
# Run from the repo root:
#     ./sim/pex/write-margin/dut/generate.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT"

# shellcheck source=../../lib/pdk_env.sh
source "$ROOT/sim/lib/pdk_env.sh"
PDK_ROOT_RESOLVED="$(dirname "$GF180_VARIANT_DIR")"
PDK_VARIANT="$(basename "$GF180_VARIANT_DIR")"

OUT="sim/pex/write-margin/dut"
LAYOUT="layout/bitcell/sram_bitcell_6t.gds"

klt extract --deck gf180mcu --pdk "$PDK_VARIANT" --pdk-root "$PDK_ROOT_RESOLVED" \
  --parasitics --format json \
  "$LAYOUT" -o "$OUT/extracted-netlist.spice" \
  > "$OUT/extract-report.json"

# Issue #109: `klt extract --pdk-root ...`'s JSON report carries a
# top-level `pdk.root` field that echoes the (necessarily absolute, since a
# PDK install is outside this repo) `--pdk-root` argument verbatim --
# redundant with, and leakier than, the same report's own
# `provenance.pdk` block, which already carries this PDK's identity
# ({name, source, version}) with no path at all. Null the redundant field
# before committing rather than leak this host's install location; nothing
# else in this report depends on it. Filed as klayout-tools#1376 (this
# field should follow the no-location model `provenance.pdk` already
# establishes in the same report) -- see sim/pex/README.md "Follow-up".
python3 -c "
import json
path = '$OUT/extract-report.json'
d = json.load(open(path))
if isinstance(d.get('pdk'), dict) and 'root' in d['pdk']:
    d['pdk']['root'] = None
json.dump(d, open(path, 'w'), indent=2)
open(path, 'a').write('\n')
print('status:', d['status'], '| devices:', d['device_count'], '| nets:', d['net_count'])
print('provenance:', d.get('provenance'))
"
echo "Wrote $OUT/extracted-netlist.spice"
