#!/usr/bin/env bash
# sim/pex/access-time/generate.sh -- issue #95. Regenerates the
# klt-pex-native access-time evidence: runs `klt pex` (Phase 1a of
# klayout-tools Epic #709) against the bitcell layout and the two request
# documents in ./requests/, producing a genuine per-corner
# schematic-vs-extracted delta for each of read/write access time, and
# writes the JSON reports to ./reports/.
#
# Invokes `klt pex` with cwd = ./testbench/ (NOT the repo root) -- the two
# testbench bodies' own DUT `.include '../dut/...'` line is written
# relative to that directory deliberately, to satisfy both klt pex's own
# Python-side include resolution (relative to the testbench file's own
# directory, used for the JSON report's `reference_netlist`) and ngspice's
# own nested-`.include` resolution (relative to its process cwd) at once --
# see either testbench file's header for the full explanation. Every other
# path below is therefore passed absolute.
#
# Requires: `klt` (klayout-tools) on PATH, a gf180mcu PDK install resolvable
# the same way sim/lib/pdk_env.sh resolves one (PDK_ROOT+PDK,
# GF180_PDK_PATH, or a standard install prefix).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SELF_DIR="$ROOT/sim/pex/access-time"

# shellcheck source=../../lib/pdk_env.sh
source "$ROOT/sim/lib/pdk_env.sh"
# Normalize to PDK_ROOT/PDK regardless of which of pdk_env.sh's three
# resolution branches fired -- ./requests/*.request.json's
# `models.lib: "$PDK_ROOT/$PDK/..."` field needs both set consistently.
export PDK_ROOT
export PDK
PDK_ROOT="$(dirname "$GF180_VARIANT_DIR")"
PDK="$(basename "$GF180_VARIANT_DIR")"

LAYOUT="$ROOT/layout/bitcell/sram_bitcell_6t.gds"
OUT_DIR="$SELF_DIR/reports"
mkdir -p "$OUT_DIR"

for name in write-access-time read-access-time; do
  echo "=== klt pex: $name ==="
  request="$SELF_DIR/requests/${name}.request.json"
  report="$OUT_DIR/${name}.pex.json"
  set +e
  # -o: redirect klt extract's own written netlist under this issue's own
  # sim/pex/ tree -- klt pex's default (`<layout>` with its extension
  # replaced by `.spice`) would otherwise write next to the layout GDS
  # under layout/bitcell/, outside this issue's scope.
  (cd "$SELF_DIR/testbench" && klt pex "$LAYOUT" "$request" --deck gf180mcu \
    --pdk "$PDK" --pdk-root "$PDK_ROOT" \
    -o "$OUT_DIR/klt-pex-artifacts/${name}/extracted-netlist.spice" \
    --outdir "$OUT_DIR/klt-pex-artifacts/${name}" \
    --format json) >"$report"
  status=$?
  set -e
  # Exit 0 (all delta rows pass) and 3 (a delta row failed its declared
  # limits, none declared here -- so not expected in practice) both mean
  # the run completed; only 1 (failed to run at all) is a hard error. See
  # docs/cli/pex.md "Exit codes".
  if [[ "$status" -eq 1 ]]; then
    echo "klt pex exited 1 (failed to run) for $name -- see $report" >&2
    exit 1
  fi
  python3 -c "
import json
d = json.load(open('$report'))
print('status:', d.get('status'), '| corners:', d.get('corner_count'), '| delta rows:', len(d.get('delta') or []), '| passed/failed/errored:', d.get('passed'), d.get('failed'), d.get('errored'))
print('reference_netlist:', d.get('reference_netlist'))
pcm = d.get('pin_count_mismatch')
print('pin_count_mismatch:', 'null' if pcm is None else pcm)
"
  echo "Wrote $report"
done
