#!/usr/bin/env bash
# sim/lib/run_corner_sweep.sh -- sweep one testbench across the ratified
# 9-corner PVT matrix (spec/sram.md "Characterization" -> "Corner set":
# process {ff,tt,ss} x temperature {-40,25,125}C x supply {2.97,3.30,3.63}V)
# and write an append-only evidence record, following the directory/naming
# convention documented in sim/README.md (adapted from 2AMLogic/gf180-bandgap's
# sim/README.md).
#
# Usage:
#   sim/lib/run_corner_sweep.sh <experiment-dir> <testbench-file> <mode> <claim>
#
#   <experiment-dir>   e.g. sim/read-snm  (must contain testbench/, and this
#                       script creates netlist-snapshots/, corners/, records/
#                       inside it if not already present)
#   <testbench-file>   path to the .spice testbench (must `.include
#                       './corner.inc'` -- this script writes that file into
#                       a scratch directory alongside a copy of the
#                       testbench before every corner run)
#   <mode>              direct -- the testbench's own `.control` block
#                        already `echo`s `RESULT: <key> = <value>` lines;
#                        this script only needs to capture the ngspice log.
#                       snm:<datafile>:<label> -- the testbench `wrdata`s a
#                        two-column DC sweep to <datafile> (relative to the
#                        scratch cwd); this script additionally invokes
#                        sim/lib/snm_extract.py on it and appends its
#                        `RESULT:` lines to the same log.
#   <claim>             free-text description of the spec/sram.md claim this
#                        run substantiates, written verbatim into the
#                        generated record's Claim field (quote it).
#   <supersedes>        optional record id (plus any explanation) this run
#                        supersedes, written into the generated record's
#                        Supersedes field. Pass it whenever the testbench
#                        changed since the previous record for this claim --
#                        the older record stays committed (append-only) but
#                        stops being the current answer.
#
# Requires: ngspice on PATH; python3 on PATH (snm mode only); PDK resolvable
# per sim/lib/pdk_env.sh (PDK_ROOT+PDK, GF180_PDK_PATH, or a standard
# install prefix).
#
# Output: one <record-id> = <YYYYMMDD>-<HHMMSS>-<short-git-sha> per
# invocation, with per-corner logs under
# <experiment-dir>/corners/<record-id>/<corner-id>.log
# (<corner-id> = <process>_<temp>c_<supply>v, e.g. ff_-40c_2.97v), a
# testbench snapshot under
# <experiment-dir>/netlist-snapshots/<record-id>.spice, and a summary
# under <experiment-dir>/records/<record-id>.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ $# -lt 3 ]]; then
  echo "usage: $0 <experiment-dir> <testbench-file> <mode> [claim] [supersedes-record-id]" >&2
  exit 2
fi

EXPERIMENT_DIR="$(cd "$1" && pwd)"
TESTBENCH_FILE="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
MODE="$3"
CLAIM="${4:-(no claim text provided)}"
# Optional 5th argument: the record id this run supersedes. Required whenever
# the testbench itself changed, so the record trail says which earlier record
# a reader should stop treating as current (the append-only rule keeps the
# superseded record in place; it does not keep it authoritative).
SUPERSEDES="${5:-}"

if [[ ! -f "$TESTBENCH_FILE" ]]; then
  echo "run_corner_sweep.sh: testbench not found: $TESTBENCH_FILE" >&2
  exit 1
fi

# shellcheck source=./pdk_env.sh
source "$SCRIPT_DIR/pdk_env.sh"

RECORD_ID="$(date -u +%Y%m%d-%H%M%S)-$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo nogit)"
CORNERS_DIR="$EXPERIMENT_DIR/corners/$RECORD_ID"
RECORDS_DIR="$EXPERIMENT_DIR/records"
SNAPSHOT_DIR="$EXPERIMENT_DIR/netlist-snapshots"
mkdir -p "$CORNERS_DIR" "$RECORDS_DIR" "$SNAPSHOT_DIR"

cp "$TESTBENCH_FILE" "$SNAPSHOT_DIR/$RECORD_ID.spice"

# Ratified 9-corner matrix, spec/sram.md "Corner set".
PROCESSES=(ff tt ss)
TEMPS=(-40 25 125)
VDDS=(2.97 3.30 3.63)

# Process-corner label -> gf180mcu model .LIB section name (sm141064.ngspice
# defines `.LIB typical` / `.LIB ff` / `.LIB ss` for the nfet_03v3/pfet_03v3
# devices this bitcell uses; "tt" is this repo's/spec's label for gf180mcu's
# "typical" section).
declare -A LIB_SECTION=([ff]=ff [tt]=typical [ss]=ss)

RESULT_LINES=()
OVERALL_OPEN=0

echo "record-id: $RECORD_ID"
echo "testbench: $TESTBENCH_FILE"
echo "pdk: $GF180_VARIANT_DIR (open_pdks ${GF180_PDK_VERSION:-unknown})"

for process in "${PROCESSES[@]}"; do
  for temp in "${TEMPS[@]}"; do
    for vdd in "${VDDS[@]}"; do
      corner_id="${process}_${temp}c_${vdd}v"
      log_file="$CORNERS_DIR/${corner_id}.log"
      scratch="$(mktemp -d)"
      tb_base="$(basename "$TESTBENCH_FILE")"
      # Substitute the @@REPO_ROOT@@ token (see e.g.
      # sim/write-margin/testbench/tb_write_margin.spice's header) with
      # this checkout's absolute path -- testbenches that `.include` the
      # DUT netlist need an absolute path since they run from a scratch
      # directory outside the repo tree, not the repo-relative path that
      # would resolve if run in place.
      sed "s|@@REPO_ROOT@@|$REPO_ROOT|g" "$TESTBENCH_FILE" > "$scratch/$tb_base"

      cat > "$scratch/corner.inc" <<EOF
* Generated by sim/lib/run_corner_sweep.sh -- do not edit, do not commit.
* corner: process=$process temp=${temp}C vdd=${vdd}V
.include '$GF180_DESIGN_INC'
.lib '$GF180_MODEL_FILE' ${LIB_SECTION[$process]}
.temp $temp
.param VDDC=$vdd
EOF

      set +e
      (cd "$scratch" && ngspice -b -o "$log_file" "$tb_base") >/dev/null 2>&1
      ngspice_status=$?
      set -e
      {
        echo "=== corner: $corner_id (process=$process temp=${temp}C vdd=${vdd}V) ==="
        echo "=== ngspice exit status: $ngspice_status ==="
      } >> "$log_file"

      if [[ "$MODE" == snm:* ]]; then
        IFS=':' read -r _ datafile label <<< "$MODE"
        if [[ -f "$scratch/$datafile" ]]; then
          set +e
          python3 "$SCRIPT_DIR/snm_extract.py" "$scratch/$datafile" "$label" >> "$log_file" 2>&1
          set -e
        else
          echo "RESULT-ERROR: ${label} -- expected data file $datafile not produced (ngspice exit $ngspice_status)" >> "$log_file"
        fi
      fi

      rm -rf "$scratch"
      result_line="$(grep -E '^RESULT:' "$log_file" | tr '\n' '; ' || true)"
      error_line="$(grep -E '^RESULT-ERROR:' "$log_file" | tr '\n' '; ' || true)"
      if [[ -n "$error_line" ]]; then
        RESULT_LINES+=("- **${corner_id}**: OPEN -- ${error_line}")
        OVERALL_OPEN=1
      elif [[ -n "$result_line" ]]; then
        RESULT_LINES+=("- **${corner_id}**: ${result_line}")
      else
        RESULT_LINES+=("- **${corner_id}**: OPEN -- no RESULT line captured (ngspice exit ${ngspice_status}; see corners/${RECORD_ID}/${corner_id}.log)")
        OVERALL_OPEN=1
      fi
      echo "  $corner_id: ${result_line:-$error_line}"
    done
  done
done

RECORD_FILE="$RECORDS_DIR/$RECORD_ID.md"
{
  echo "# Record $RECORD_ID"
  echo
  echo "- **Record ID**: $RECORD_ID"
  echo "- **Claim**: $CLAIM"
  echo "- **Netlist provenance**: schematic (\`$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$TESTBENCH_FILE" "$REPO_ROOT")\`, DUT per \`design/netlist/bitcell_6t.spice\` at \`$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo nogit)\`)"
  echo "- **Corner matrix run**:"
  echo "  - Process: ${PROCESSES[*]}"
  echo "  - Temperature: ${TEMPS[*]} C"
  echo "  - Supply: ${VDDS[*]} V"
  echo "  - (9 corner points total -- full process x temp x supply matrix, per spec/sram.md's ratified corner set)"
  echo "- **Statistical convention**: N/A (corner-matrix claim, not a distribution claim)"
  echo "- **Result**:"
  for line in "${RESULT_LINES[@]}"; do
    echo "  $line"
  done
  if [[ "$OVERALL_OPEN" -eq 1 ]]; then
    echo "  - **Overall: OPEN** -- at least one corner did not produce a valid measured result (see per-corner notes above); per spec/sram.md's Signoff definition this corner is recorded as an open result, not dropped from the corner set."
  else
    echo "  - **Overall: recorded** -- all 9 corners produced a measured result; see sim/README.md for how to interpret sign-off against spec/sram.md's positive-margin requirement."
  fi
  echo "- **Links**:"
  echo "  - Testbench: \`$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$TESTBENCH_FILE" "$REPO_ROOT")\`"
  echo "  - Netlist snapshot: \`$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$SNAPSHOT_DIR/$RECORD_ID.spice" "$REPO_ROOT")\`"
  echo "  - Raw logs: \`$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$CORNERS_DIR" "$REPO_ROOT")/\`"
  echo "- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder"
  if [[ -n "$SUPERSEDES" ]]; then
    echo "- **Supersedes**: $SUPERSEDES"
  else
    echo "- **Supersedes**: (none -- first record for this claim)"
  fi
} > "$RECORD_FILE"

echo
echo "Wrote 9 corner logs under $CORNERS_DIR"
echo "Wrote netlist snapshot: $SNAPSHOT_DIR/$RECORD_ID.spice"
echo "Wrote record: $RECORD_FILE"
echo "record-id: $RECORD_ID"
