#!/usr/bin/env bash
# Regenerate the socket descriptor + LEF abstract and re-run every check
# views/README.md reports a number for. Run from the repo root:
#
#     ./views/verify.sh
#
# Mirrors layout/verify.sh's own "regenerate, diff, re-check" shape. This is
# a *views self-check*, not a substitute for reading views/README.md's own
# "Pin geometry" section on what geometry_source: synthesized/none mean here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PY="uv run --with klayout python3"
# Released klt pinned the same way signoff/regenerate.sh pins it -- never the
# klt already on the host.
KLT_VERSION="0.6.0"
KLT="uvx --from klayout-tools==$KLT_VERSION klt"

ARRAY_GDS=layout/sram_256x32/sram_256x32_array.gds
SOCKET=views/sram_256x32_array.socket.json
LEF=views/sram_256x32_array.lef
SOCKET_REPORT=views/reports/sram_256x32_array.socket-check.json
LEF_REPORT=views/reports/sram_256x32_array.lef-abstract.json
CELL_LIBRARY=gf180mcu_fd_sc_mcu9t5v0
PDK_VARIANT=gf180mcuD

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. regenerate the socket descriptor (determinism: must not change)"
$PY views/gen_socket.py
if git diff --quiet -- "$SOCKET"; then
  echo "PASS: regenerated socket is byte-identical to the committed descriptor"
else
  echo "FAIL: regenerated socket differs from the committed descriptor"
  git diff --stat -- "$SOCKET"
  exit 1
fi

hr "2. klt socket-check (released klt $KLT_VERSION)"
$KLT socket-check "$ARRAY_GDS" --socket "$SOCKET" --format json > "$WORK/socket-check.json"
cat "$WORK/socket-check.json"
SOCKET_STATUS="$(python3 -c "import json; print(json.load(open('$WORK/socket-check.json'))['status'])")"
if [ "$SOCKET_STATUS" != "pass" ]; then
  echo "FAIL: klt socket-check status=$SOCKET_STATUS (expected pass)"
  exit 1
fi
echo "PASS: klt socket-check status=pass (outline + all 322 pins)"

hr "3. klt lef-abstract (released klt $KLT_VERSION)"
$KLT lef-abstract "$ARRAY_GDS" \
  --socket "$SOCKET" \
  --macro-name sram_256x32_array \
  --cell-library "$CELL_LIBRARY" \
  --class BLOCK \
  --pdk "$PDK_VARIANT" \
  --format json \
  -o "$WORK/regen.lef" > "$WORK/regen.lef-abstract.json"
echo "wrote $WORK/regen.lef"

if diff -q "$WORK/regen.lef" "$LEF" >/dev/null; then
  echo "PASS: regenerated LEF is byte-identical to the committed $LEF"
else
  echo "FAIL: regenerated LEF differs from the committed $LEF"
  diff "$WORK/regen.lef" "$LEF" | head -60
  exit 1
fi

echo
echo "All views/ checks passed."
echo "(The two committed reports under views/reports/ carry host-specific"
echo " provenance -- klt/klayout versions, PDK content hashes -- that is"
echo " expected to vary by install; only the .lef and .socket.json above"
echo " are checked byte-identical, matching layout/verify.sh's convention"
echo " of not diffing JSON reports.)"
