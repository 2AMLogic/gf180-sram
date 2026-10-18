#!/usr/bin/env bash
# sim/macro-smoke/run.sh -- run the macro write/read smoke testbench at ONE
# corner (default tt_25c_3.30v), locally. Functional smoke only: this is not a
# corner sweep (use a `klt sim` corner request for that; the fleet runs grids).
#
# Usage: sim/macro-smoke/run.sh [process temp vdd [ctrl]]   e.g. run.sh tt 25 3.30
#   (no 4th arg)  macro write/read smoke (the 3-4 minute run)
#   ctrl          control-block pulse widths only (seconds); prints the .meas results
# Output: scratch dir printed on stderr; RESULT: lines on stdout; exit 1 on FAIL.
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
process="${1:-tt}"; temp="${2:-25}"; vdd="${3:-3.30}"
# shellcheck source=../lib/pdk_env.sh
source "$repo/sim/lib/pdk_env.sh"
case "$process" in tt) lib=typical;; ff) lib=ff;; ss) lib=ss;; *) echo "bad process" >&2; exit 2;; esac
scratch="$(mktemp -d)"
echo "scratch: $scratch" >&2
cat > "$scratch/corner.inc" <<INC
* corner: process=$process temp=${temp}C vdd=${vdd}V
.include '$GF180_DESIGN_INC'
.lib '$GF180_MODEL_FILE' $lib
.temp $temp
.param VDDC=$vdd
INC
if [[ "${4:-}" == "ctrl" ]]; then
  sed "s#@@REPO_ROOT@@#$repo#" "$repo/sim/macro-smoke/testbench/tb_ctrl_pulse.spice" > "$scratch/tb.spice"
  (cd "$scratch" && nice -n 10 ngspice -b -o run.log tb.spice >/dev/null 2>&1) || true
  grep -E '^(wr_|rd_)' "$scratch/run.log" | sed 's/^/RESULT: /'
  cp "$scratch/run.log" "$scratch/../ctrl-pulse-$process-${temp}c-${vdd}v.log"
  exit 0
fi
# drop the array subckt from the macro netlist; the testbench supplies a reduced one
awk '/^\.subckt sram_64x128_array /{skip=1} !skip{print} skip&&/^\.ends/{skip=0}' \
  "$repo/design/netlist/sram_256x32.spice" > "$scratch/sram_256x32.noarray.spice"
sed "s#@@REPO_ROOT@@#$repo#" "$repo/sim/macro-smoke/testbench/tb_macro_write_read.spice" > "$scratch/tb.spice"
(cd "$scratch" && OMP_NUM_THREADS=2 nice -n 10 ngspice -b -o run.log tb.spice >/dev/null 2>&1) || true
cp "$scratch/run.log" "$scratch/../macro-smoke-$process-${temp}c-${vdd}v.log" 2>/dev/null || true
python3 -I "$repo/sim/macro-smoke/smoke.py" check "$scratch/run.log"
