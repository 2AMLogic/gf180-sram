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
# see either testbench file's header for the full explanation. Issue #109:
# `layout`/`request`/`-o` are passed relative to that same cwd (so the
# report's echoed copies of them land repo-relative too); `--pdk-root` and
# `--outdir` stay absolute (see the inline comments below for why each
# specific one does).
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
TESTBENCH_DIR="$SELF_DIR/testbench"
mkdir -p "$OUT_DIR"

# Issue #109: `klt pex` echoes its `layout`/`netlist`/`request` CLI-argument
# paths back verbatim into the committed *.pex.json report -- pass every
# CLI-argument path relative to the cwd `klt pex` actually runs from
# (`$TESTBENCH_DIR`, per the header comment above) instead of absolute, so
# those three echoed fields land repo-relative in the committed report (klt
# does not re-normalize a relative CLI argument to an absolute one before
# echoing it back -- verified against this repo's own `klt extract`'s
# `"file"` field, which already preserves a relative argument as-is).
# `--pdk-root` stays absolute (a PDK install is genuinely outside the repo,
# and this report's `provenance.pdk` block already carries its identity
# without a path -- verified this does not leak here).
#
# `reference_netlist`/`testbenches[].schematic_netlist` are a separate case:
# klt resolves those internally from the testbench's own DUT `.include` line
# and *does* re-normalize that resolved path to absolute before echoing it
# back, regardless of whether the CLI arguments above were relative or
# absolute (verified 2026-08-25, `klt 0.2.0`) -- a tool-side normalization
# this repo's invocation has no lever over. Since the DUT file both
# testbenches `.include` is fixed (`./dut/bitcell_6t_subckt.spice`, always
# resolving to the same repo-relative path), the post-processing step below
# rewrites that one known absolute value back to its repo-relative
# equivalent rather than leaving it leaked, the same "rewrite what's echoed
# back" pattern layout/reports/generate.sh's array-LVS `reference` field
# fix and write-margin/dut/generate.sh's `pdk.root` fix use. Filed as
# klayout-tools#1378 (both the `--outdir` relative-path join bug noted below
# and this `reference_netlist`/`schematic_netlist` absolute-echo).
DUT_NETLIST="$SELF_DIR/dut/bitcell_6t_subckt.spice"
DUT_NETLIST_REL="$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$DUT_NETLIST" "$ROOT")"
relpath() { python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$1" "$2"; }

for name in write-access-time read-access-time; do
  echo "=== klt pex: $name ==="
  request="$SELF_DIR/requests/${name}.request.json"
  report="$OUT_DIR/${name}.pex.json"
  layout_rel="$(relpath "$LAYOUT" "$TESTBENCH_DIR")"
  request_rel="$(relpath "$request" "$TESTBENCH_DIR")"
  out_netlist_rel="$(relpath "$OUT_DIR/klt-pex-artifacts/${name}/extracted-netlist.spice" "$TESTBENCH_DIR")"
  set +e
  # -o: redirect klt extract's own written netlist under this issue's own
  # sim/pex/ tree -- klt pex's default (`<layout>` with its extension
  # replaced by `.spice`) would otherwise write next to the layout GDS
  # under layout/bitcell/, outside this issue's scope.
  #
  # --outdir stays absolute: passing it as a relative path (with a leading
  # `../`, since it climbs back out of $TESTBENCH_DIR into ./reports/)
  # empirically breaks `klt pex`'s own internal artifact-path join --
  # verified 2026-08-25, `klt 0.2.0` doubles the relative outdir segment
  # onto its own generated intermediate-testbench path (`.../reports/klt-
  # pex-artifacts/<name>/../reports/klt-pex-artifacts/<name>/...`) and
  # fails with "netlist not found". `--outdir` is a scratch-artifact
  # directory, not one of the leaking echoed fields (`layout`/`netlist`/
  # `reference_netlist`/`request`/`schematic_netlist` -- see the report's
  # own fields below), so keeping it absolute does not reintroduce the
  # leak this issue is fixing; filed as klayout-tools#1378.
  (cd "$TESTBENCH_DIR" && klt pex "$layout_rel" "$request_rel" --deck gf180mcu \
    --pdk "$PDK" --pdk-root "$PDK_ROOT" \
    -o "$out_netlist_rel" \
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
import json, os
path = '$report'
d = json.load(open(path))
# klt's echoed reference_netlist/schematic_netlist is not itself
# normalized (it may carry an unresolved 'requests/../testbench/../dut/...'
# traversal) -- compare on the normalized form, but only ever substitute
# the exact known-good repo-relative value, never a derived one.
dut_abs_norm = os.path.normpath('$DUT_NETLIST')
dut_rel = '$DUT_NETLIST_REL'
if os.path.normpath(d.get('reference_netlist') or '') == dut_abs_norm:
    d['reference_netlist'] = dut_rel
for tb in d.get('testbenches') or []:
    if os.path.normpath(tb.get('schematic_netlist') or '') == dut_abs_norm:
        tb['schematic_netlist'] = dut_rel
json.dump(d, open(path, 'w'), indent=2)
open(path, 'a').write('\n')
print('status:', d.get('status'), '| corners:', d.get('corner_count'), '| delta rows:', len(d.get('delta') or []), '| passed/failed/errored:', d.get('passed'), d.get('failed'), d.get('errored'))
print('reference_netlist:', d.get('reference_netlist'))
pcm = d.get('pin_count_mismatch')
print('pin_count_mismatch:', 'null' if pcm is None else pcm)
"
  echo "Wrote $report"
done
