#!/usr/bin/env bash
# layout/reports/generate.sh -- issue #23 (T1 items 3/4: DRC clean, LVS
# clean). Regenerates every committed report in this directory from the
# committed layout + design sources and overwrites them in place -- these
# reports are a *current-state signoff snapshot*, not append-only evidence
# like sim/*/records/ (see layout/reports/README.md "Freshness" for why that
# distinction is deliberate here).
#
# Run from the repo root:
#     ./layout/reports/generate.sh                  # everything (step 5 is ~26 min)
#     ./layout/reports/generate.sh --column-path    # only step 0, the column path (#205)
#     ./layout/reports/generate.sh --column-path --native   # ... plus the PDK-native DRC deck
#     ./layout/reports/generate.sh --row-path       # only the row decoder strip (#204)
#     ./layout/reports/generate.sh --control        # only sram_ctrl + col_decode (#246)
#     ./layout/reports/generate.sh --macro          # only the assembled macro, DRC (#326)
#     ./layout/reports/generate.sh --array64        # only the 64 x 128 array trio (#327)
#
# Requires: klt (klayout-tools) on PATH, python3. No PDK install needed --
# klt's curated gf180mcu deck is bundled, same as layout/verify.sh.
#
# Steps 3-4 (klt lvs, T1 item 4) additionally need a klt that records LVS
# `provenance.input.content_hash` -- klayout-tools#1969-era or later; the
# released 0.5.0 predates it and would mint LVS reports whose input pin is
# `null`, silently regressing the signoff manifest's item-4 citation back
# to `stale_evidence` (issue #128 minted the committed reports with a
# post-#1969 checkout klt). Re-minting the LVS pair alone, ERC-style, is:
# bump PATH to a post-#1969 klt and re-run the step 3-4 blocks below.
#
# Step 5 (klt erc, issues #124/#159 / T1 item 11) needs the released klt
# 0.6.0 (status+provenance block, #1968; ties[] incl. well_boxes, #2255;
# erc_coverage, #2179); the committed report was minted with it. It is also
# slow on this design (~26 min on the fleet host): klt erc walks every
# gate net x stackup level over the full array (16,640 gate nets).
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

# --- 0. column path (issue #205) -------------------------------------------
# precharge_slice / io_slice are checked per cell (DRC, extract, LVS against
# design/netlist/<cell>.spice), the 32-slice bands for DRC, and the bands
# abutted to the committed 64x128 array (issue #204) for the bit-line seam DRC.
# The abutted composite is a scratch file; the array and the bands are committed.
# `./layout/reports/generate.sh --column-path` runs only this block (~2 min);
# adding `--native` also runs it against the PDK's own DRC deck (~3 min more).
COLUMN_DIR=layout/periphery/column

# --- 0r. row decoder / wordline-driver strip (issue #204) -------------------
# One flat cell (16 predecoders + 64 rowdrv), checked against
# design/netlist/row_path.spice. Strip only: nothing here is a physical-fit or
# wordline-RC claim (layout/README.md "Row path").
# `./layout/reports/generate.sh --row-path` runs only this block (~10 s).
ROW_GDS=layout/periphery/row/row_path.gds

# --- 0m. the assembled macro (issue #326) -----------------------------------
# One hierarchical top cell, `sram_256x32` (layout/macro/sram_256x32.gds), checked
# with the curated gf180mcu deck. Macro-level DRC only: no timing, parasitic,
# wordline-RC or area claim (layout/README.md).
# `./layout/reports/generate.sh --macro` runs only this block (~1 min).
#
# There is deliberately no macro extract/LVS counterpart here. Hierarchical macro
# LVS is blocked on klayout-tools#5322 and stays on issue #247, so this block mints
# drc-macro.json and nothing else -- neither extraction nor LVS runs, and no stub
# stands in for either.
MACRO_GDS=layout/macro/sram_256x32.gds
run_macro() {
hr "0m. macro (issue #326): DRC"
klt drc --deck gf180mcu --format json "$MACRO_GDS" | tee "$OUT/drc-macro.json" >/dev/null
python3 -c "
import json
d = json.load(open('$OUT/drc-macro.json'))
print('drc-macro:', d['status'], '| violations:', d['violation_count'])
"
}
if [ "${1:-}" = "--macro" ]; then run_macro; exit 0; fi

# --- 0a. the 64 x 128 array (issue #327) -------------------------------------
# The 4:1 tiling the macro floorplan is built on (spec/periphery-architecture.md,
# layout/README.md "The array"), emitted by the same generator as the 256 x 32
# array. `./layout/reports/generate.sh --array64` runs only this block (~15 min,
# extract-dominated on 8,192 bitcells).
#
# Minted under the pinned released klt with the engine pinned on both sides
# (`--with klayout==0.30.12`), the same two-sided pin layout/README.md
# "Reproduce this locally" documents for drc-macro.json -- never the bare host
# `klt` the older blocks still call (signoff/README.md; converting them is out
# of scope for #327). Under klt 0.8.0 the DRC/extract `file` field is already
# emitted repo-relative (`scope: repo`); the rewrites below cover both that
# object form and the older string form, plus the three fields that do leak
# host paths (`netlist_path` on extract, `layout` and `reference` on lvs),
# and a final assert that nothing host-specific slipped through.
ARRAY64_GDS=layout/sram_64x128/sram_64x128_array.gds
ARRAY64_REF=design/netlist/sram_64x128_array.spice
KLT64=(uvx --from klayout-tools==0.8.0 --with klayout==0.30.12 klt)
run_array64() {
hr "0a. 64 x 128 array (issue #327): DRC, extract, LVS"
"${KLT64[@]}" drc --deck gf180mcu --format json "$ARRAY64_GDS" > "$WORK/drc-array64-raw.json"
python3 -c "
import json
d = json.load(open('$WORK/drc-array64-raw.json'))
f = d.get('file')
if isinstance(f, dict):
    if f.get('path') == '$ROOT/$ARRAY64_GDS':
        f['path'] = '$ARRAY64_GDS'
elif f == '$ROOT/$ARRAY64_GDS':
    d['file'] = '$ARRAY64_GDS'
json.dump(d, open('$OUT/drc-array-64x128.json', 'w'), indent=2)
open('$OUT/drc-array-64x128.json', 'a').write('\n')
print('drc-array-64x128:', d['status'], '| violations:', d['violation_count'])
"
"${KLT64[@]}" extract --deck gf180mcu --format json "$ARRAY64_GDS" -o "$WORK/array64.spice" > "$WORK/extract-array64-full.json"
# Same bulk omission step 4 applies to the 256 x 32 extract (8,192 bitcells
# either way -- ~18 MB unabridged): drop devices[]/nets[], keep every other
# field incl. counts and provenance.
python3 -c "
import json
d = json.load(open('$WORK/extract-array64-full.json'))
d.pop('devices', None)
d.pop('nets', None)
d['_note'] = ('devices[]/nets[] omitted from this committed report (%d devices / %d nets -- see device_count/net_count/pin_count above); full output reproducible via layout/reports/generate.sh --array64' % (d['device_count'], d['net_count']))
f = d.get('file')
if isinstance(f, dict):
    if f.get('path') == '$ROOT/$ARRAY64_GDS':
        f['path'] = '$ARRAY64_GDS'
elif f == '$ROOT/$ARRAY64_GDS':
    d['file'] = '$ARRAY64_GDS'
if d.get('netlist_path') == '$WORK/array64.spice':
    d['netlist_path'] = 'array64.spice'  # a temp dir at generation time
json.dump(d, open('$OUT/extract-array-64x128.json', 'w'), indent=2)
open('$OUT/extract-array-64x128.json', 'a').write('\n')
print('extract-array-64x128:', d['status'], '| devices:', d['device_count'], '| nets:', d['net_count'], '| pins:', d['pin_count'])
"
# `reference.netlist` must stay absolute for the run to work at all (klt lvs
# resolves it against the request document's own directory -- see step 4's
# comment); the echoed fields are rewritten post-hoc below. `layout` names the
# scratch extract, NOT the committed GDS: its hash does not bind the GDS (the
# #285 defect, disclosed in layout/reports/README.md), so it stays labelled as
# a scratch file instead of claiming the repo-relative GDS as its input.
cat > "$WORK/lvs-array64-request.json" <<EOF
{"layout":{"netlist":"$WORK/array64.spice","top":"sram_64x128_array"},
 "reference":{"netlist":"$ROOT/$ARRAY64_REF","form":"subckt-call"},
 "options":{"flatten_reference":true}}
EOF
"${KLT64[@]}" lvs "$WORK/lvs-array64-request.json" --format json > "$WORK/lvs-array64-raw.json"
# Under klt 0.8.0 the echoed `layout` field is {"path": null, "scope":
# "external"} (nothing to leak); `reference` still echoes the absolute path
# and is rewritten. The `_note` states what the layout input actually binds
# to, so the report cannot be read as GDS-fresh evidence.
python3 -c "
import json
d = json.load(open('$WORK/lvs-array64-raw.json'))
if d.get('layout') == '$WORK/array64.spice':
    d['layout'] = 'array64.spice (scratch extract at generation time, see #285)'
if d.get('reference') == '$ROOT/$ARRAY64_REF':
    d['reference'] = '$ARRAY64_REF'
d['_note'] = ('layout input is the scratch extracted netlist array64.spice (klt extract of '
              'the committed GDS into a temp dir at generation time): environment.layout_sha256 '
              'and provenance.input.content_hash hash that scratch netlist, not the GDS, and '
              'environment.extracted_netlist is null -- nothing in this report binds it to '
              'layout/sram_64x128/sram_64x128_array.gds (issue #285). Regenerate via '
              'layout/reports/generate.sh --array64.')
json.dump(d, open('$OUT/lvs-array-64x128.json', 'w'), indent=2)
open('$OUT/lvs-array-64x128.json', 'a').write('\n')
print('lvs-array-64x128:', d['status'], '| mismatches:', d['mismatch_count'], '| errors:', d['error_count'])
"
# Issue #327: no host path may reach a committed 64 x 128 report -- stricter
# than the older blocks, whose committed reports still leak theirs.
python3 -c "
import json, sys
bad = []
for fn in ('drc-array-64x128.json', 'extract-array-64x128.json', 'lvs-array-64x128.json'):
    def walk(o, path=fn):
        if isinstance(o, dict):
            for k, v in o.items(): walk(v, path + '.' + k)
        elif isinstance(o, list):
            for i, v in enumerate(o): walk(v, path + '[%d]' % i)
        elif isinstance(o, str) and ('$ROOT/' in o or '$WORK/' in o):
            bad.append((path, o))
    walk(json.load(open('$OUT/' + fn)))
if bad:
    for path, val in bad: print('host path leaked:', path, '=', val, file=sys.stderr)
    sys.exit(1)
print('no host paths in the three 64 x 128 reports')
"
}
if [ "${1:-}" = "--array64" ]; then run_array64; exit 0; fi

if [ "${1:-}" != "--control" ]; then
hr "0r. row path (issue #204): DRC, extract, LVS"
klt drc --deck gf180mcu --format json "$ROW_GDS" | tee "$OUT/drc-row-path.json" >/dev/null
klt extract --deck gf180mcu --format json "$ROW_GDS" -o "$WORK/row_path.spice" > "$WORK/extract-row-raw.json"
python3 -c "
import json
d = json.load(open('$WORK/extract-row-raw.json'))
d['netlist_path'] = 'row_path.spice'  # a temp dir at generation time
json.dump(d, open('$OUT/extract-row-path.json', 'w'), indent=2)
open('$OUT/extract-row-path.json', 'a').write('\n')
"
cat > "$WORK/lvs-row-request.json" <<EOF
{"layout":{"file":"$ROOT/$ROW_GDS","deck":"gf180mcu","top":"row_path"},
 "reference":{"netlist":"$ROOT/design/netlist/row_path.spice","form":"subckt-call"},
 "options":{"flatten_reference":true}}
EOF
klt lvs "$WORK/lvs-row-request.json" --format json > "$WORK/lvs-row-raw.json"
python3 -c "
import json
d = json.load(open('$WORK/lvs-row-raw.json'))
if d.get('layout') == '$ROOT/$ROW_GDS':
    d['layout'] = '$ROW_GDS'
if d.get('reference') == '$ROOT/design/netlist/row_path.spice':
    d['reference'] = 'design/netlist/row_path.spice'
json.dump(d, open('$OUT/lvs-row-path.json', 'w'), indent=2)
open('$OUT/lvs-row-path.json', 'a').write('\n')
print('row_path LVS status:', d['status'], '| mismatches:', d['mismatch_count'], '| errors:', d['error_count'])
d = json.load(open('$OUT/drc-row-path.json'))
print('drc-row-path:', d['status'], '| violations:', d['violation_count'])
"
fi
if [ "${1:-}" = "--row-path" ]; then exit 0; fi

# --- 0c. control block + column decoder (issue #246) ------------------------
# Two flat cells, each checked against its own design/netlist/<cell>.spice.
# Block level only: no timing, delay-chain calibration or parasitic claim.
# `./layout/reports/generate.sh --control` runs only this block (~1 min).
CTRL_DIR=layout/periphery/control

hr "0c. control block + column decoder (issue #246): DRC, extract, LVS"
for cell in sram_ctrl col_decode; do
  name="${cell//_/-}"
  klt drc --deck gf180mcu --format json "$CTRL_DIR/$cell.gds" | tee "$OUT/drc-$name.json" >/dev/null
  klt extract --deck gf180mcu --format json "$CTRL_DIR/$cell.gds" -o "$WORK/$cell.spice" > "$WORK/extract-$cell-raw.json"
  python3 -c "
import json
d = json.load(open('$WORK/extract-$cell-raw.json'))
d['netlist_path'] = '$cell.spice'  # a temp dir at generation time
json.dump(d, open('$OUT/extract-$name.json', 'w'), indent=2)
open('$OUT/extract-$name.json', 'a').write('\n')
"
  cat > "$WORK/lvs-$cell-request.json" <<EOF
{"layout":{"file":"$ROOT/$CTRL_DIR/$cell.gds","deck":"gf180mcu","top":"$cell"},
 "reference":{"netlist":"$ROOT/design/netlist/$cell.spice","form":"subckt-call"},
 "options":{"flatten_reference":true}}
EOF
  klt lvs "$WORK/lvs-$cell-request.json" --format json > "$WORK/lvs-$cell-raw.json"
  python3 -c "
import json
d = json.load(open('$WORK/lvs-$cell-raw.json'))
if d.get('layout') == '$ROOT/$CTRL_DIR/$cell.gds':
    d['layout'] = '$CTRL_DIR/$cell.gds'
if d.get('reference') == '$ROOT/design/netlist/$cell.spice':
    d['reference'] = 'design/netlist/$cell.spice'
json.dump(d, open('$OUT/lvs-$name.json', 'w'), indent=2)
open('$OUT/lvs-$name.json', 'a').write('\n')
print('$cell LVS status:', d['status'], '| mismatches:', d['mismatch_count'], '| errors:', d['error_count'])
d = json.load(open('$OUT/drc-$name.json'))
print('drc-$name:', d['status'], '| violations:', d['violation_count'])
"
done
if [ "${1:-}" = "--control" ]; then exit 0; fi

if [ "${1:-}" != "--row-path" ]; then
hr "0. column path (issue #205): DRC, extract, LVS, bit-line seam"
for cell in precharge_slice io_slice; do
  name="${cell//_/-}"
  klt drc --deck gf180mcu --format json "$COLUMN_DIR/$cell.gds" | tee "$OUT/drc-column-$name.json" >/dev/null
  klt extract --deck gf180mcu --format json "$COLUMN_DIR/$cell.gds" -o "$WORK/$cell.spice" > "$WORK/extract-$cell-raw.json"
  python3 -c "
import json
d = json.load(open('$WORK/extract-$cell-raw.json'))
d['netlist_path'] = '$cell.spice'  # a temp dir at generation time
json.dump(d, open('$OUT/extract-column-$name.json', 'w'), indent=2)
open('$OUT/extract-column-$name.json', 'a').write('\n')
"
  # LVS from the GDS (inline extraction, `layout.file` + `deck`), not from a
  # pre-extracted netlist: only the inline form carries the drawn labels that
  # `net.supply_fragmented` and the body-tie verification need (a pre-extracted
  # netlist with three disjoint `VDD`s -- `VDD`, `VDD$1`, `VDD$2` -- compares
  # without naming the cause; see layout/README.md "Known tool gaps").
  cat > "$WORK/lvs-$cell-request.json" <<EOF
{"layout":{"file":"$ROOT/$COLUMN_DIR/$cell.gds","deck":"gf180mcu","top":"$cell"},
 "reference":{"netlist":"$ROOT/design/netlist/$cell.spice","form":"subckt-call"},
 "options":{"flatten_reference":true}}
EOF
  klt lvs "$WORK/lvs-$cell-request.json" --format json > "$WORK/lvs-$cell-raw.json"
  # The echoed `layout`/`reference` paths are host-specific (this checkout):
  # rewrite them to stable repo-relative names before committing, as the array
  # LVS block below does for `reference`.
  python3 -c "
import json
d = json.load(open('$WORK/lvs-$cell-raw.json'))
if d.get('layout') == '$ROOT/$COLUMN_DIR/$cell.gds':
    d['layout'] = '$COLUMN_DIR/$cell.gds'
if d.get('reference') == '$ROOT/design/netlist/$cell.spice':
    d['reference'] = 'design/netlist/$cell.spice'
json.dump(d, open('$OUT/lvs-column-$name.json', 'w'), indent=2)
open('$OUT/lvs-column-$name.json', 'a').write('\n')
print('$cell LVS status:', d['status'], '| mismatches:', d['mismatch_count'], '| errors:', d['error_count'])
"
done
klt drc --deck gf180mcu --format json "$COLUMN_DIR/column_band.gds" | tee "$OUT/drc-column-band.json" >/dev/null
uv run --with klayout python3 "$COLUMN_DIR/generate.py" --abut layout/sram_64x128/sram_64x128_array.gds -o "$WORK/column_abut.gds"
klt drc --deck gf180mcu --format json "$WORK/column_abut.gds" > "$WORK/drc-column-abut-raw.json"
python3 -c "
import json
d = json.load(open('$WORK/drc-column-abut-raw.json'))
d['file'] = ('(scratch composite) committed 64x128 array + io_band + precharge_band, '
             '$COLUMN_DIR/generate.py --abut')
json.dump(d, open('$OUT/drc-column-abut.json', 'w'), indent=2)
open('$OUT/drc-column-abut.json', 'a').write('\n')
"
for f in precharge-slice io-slice band abut; do
  python3 -c "import json; d=json.load(open('$OUT/drc-column-$f.json')); print('drc-column-$f:', d['status'], '| violations:', d['violation_count'])"
done
if [ "${2:-}" = "--native" ]; then
  # The PDK's own native KLayout deck (all FEOL+BEOL rule tables), driven by
  # `klt drc --engine klayout`. Needs a gf180mcuD install (`klt pdk find`) and
  # the `docopt` and `klayout` packages (run_drc.py). The deck script is materialized
  # with the PDK's own `--macro_gen` (its --path must exist but is unused there); --expect-rule-categories fails the run if
  # the deck silently declared fewer rule tables than the 640 it should (the
  # failure mode klayout-tools#1302 documented).
  hr "0n. column path vs the PDK's native DRC deck (klt drc --engine klayout)"
  RUN_DRC=""
  PDK_PIN="$(tr -d '[:space:]' < sim/lib/pdk_pin.txt)"
  for root in "${PDK_ROOT:-}" "$HOME/.ciel" "$HOME/.volare"; do
    if [ -n "$root" ] && [ -f "$root/gf180mcuD/libs.tech/klayout/tech/drc/run_drc.py" ]; then
      RUN_DRC="$root/gf180mcuD/libs.tech/klayout/tech/drc/run_drc.py"
      PDK_FOUND_ROOT="$root"
      break
    fi
  done
  [ -n "$RUN_DRC" ] || { echo "no gf180mcuD tech/drc/run_drc.py under \$PDK_ROOT, ~/.ciel or ~/.volare" >&2; exit 1; }
  # Same revision check as sim/lib/pdk_env.sh: the tree's open_pdks revision
  # (a /versions/<sha>/ path component, else its SOURCES file) must be the pin.
  PDK_RESOLVED="$(cd "$PDK_FOUND_ROOT/gf180mcuD" && pwd -P)"
  PDK_FOUND_REV=""
  case "$PDK_RESOLVED" in
    */versions/*) PDK_FOUND_REV="${PDK_RESOLVED#*/versions/}"; PDK_FOUND_REV="${PDK_FOUND_REV%%/*}" ;;
  esac
  if ! [[ "$PDK_FOUND_REV" =~ ^[0-9a-f]{40}$ ]]; then
    PDK_FOUND_REV=""
    for src in "$PDK_FOUND_ROOT/gf180mcuD/SOURCES" "$PDK_RESOLVED/../SOURCES"; do
      if [ -f "$src" ]; then
        PDK_FOUND_REV="$(grep -Eo '[0-9a-f]{40}' "$src" | head -n1 || true)"
        [ -n "$PDK_FOUND_REV" ] && break
      fi
    done
  fi
  if [ "$PDK_FOUND_REV" != "$PDK_PIN" ]; then
    echo "PDK revision mismatch for $PDK_FOUND_ROOT/gf180mcuD: found open_pdks '${PDK_FOUND_REV:-<undeterminable>}', pinned $PDK_PIN (sim/lib/pdk_pin.txt)." >&2
    echo "install the pin with: ciel enable --pdk-family gf180mcu -l gf180mcu_fd_pr $PDK_PIN (PDK root ~/.ciel)" >&2
    exit 1
  fi
  mkdir -p "$WORK/native"
  uv run --with docopt --with klayout python3 "$RUN_DRC" --macro_gen --variant=D \
    --run_dir="$WORK/native" --path="$COLUMN_DIR/io_slice.gds" > "$WORK/native/macro_gen.log" 2>&1 \
    || { cat "$WORK/native/macro_gen.log" >&2; exit 1; }
  NATIVE=(--engine klayout --deck-file "$WORK/native/main.drc"
          --deck-var feol=true --deck-var beol=true --deck-var metal_top=11K
          --deck-var metal_level=5LM --deck-var mim_option=B --deck-var offgrid=true
          --deck-var connectivity=false --expect-rule-categories 640)
  for target in "precharge-slice:$COLUMN_DIR/precharge_slice.gds" \
                "io-slice:$COLUMN_DIR/io_slice.gds" \
                "abut:$WORK/column_abut.gds"; do
    name="${target%%:*}"
    gds="${target#*:}"
    klt drc "${NATIVE[@]}" --format json "$gds" > "$WORK/native-$name-raw.json"
    python3 -c "
import json
d = json.load(open('$WORK/native-$name-raw.json'))
d['deck'] = 'main.drc (gf180mcuD tech/drc/run_drc.py --macro_gen --variant=D)'
if '$name' == 'abut':
    d['file'] = ('(scratch composite) committed 64x128 array + io_band + precharge_band, '
                 '$COLUMN_DIR/generate.py --abut')
json.dump(d, open('$OUT/drc-native-column-$name.json', 'w'), indent=2)
open('$OUT/drc-native-column-$name.json', 'a').write('\n')
print('drc-native-column-$name:', d['status'], '| violations:', d['violation_count'])
"
  done
fi
fi
if [ "${1:-}" = "--column-path" ]; then exit 0; fi

hr "1. DRC: bitcell (klt drc --deck gf180mcu)"
klt drc --deck gf180mcu --format json "$BITCELL_GDS" | tee "$OUT/drc-bitcell.json" >/dev/null
python3 -c "import json,sys; d=json.load(open('$OUT/drc-bitcell.json')); print('status:', d['status'], '| violations:', d['violation_count'])"

hr "2. DRC: full 256x32 array (klt drc --deck gf180mcu, ~30-60s)"
klt drc --deck gf180mcu --format json "$ARRAY_GDS" | tee "$OUT/drc-array.json" >/dev/null
python3 -c "import json,sys; d=json.load(open('$OUT/drc-array.json')); print('status:', d['status'], '| violations:', d['violation_count'])"

hr "3. Extract + LVS: bitcell vs $BITCELL_REF"
klt extract --deck gf180mcu --format json "$BITCELL_GDS" -o "$WORK/bitcell.spice" | tee "$OUT/extract-bitcell.json" >/dev/null
cat > "$WORK/lvs-bitcell-request.json" <<EOF
{"layout":{"netlist":"$WORK/bitcell.spice","top":"sram_bitcell_6t"},
 "reference":{"netlist":"$ROOT/$BITCELL_REF","form":"subckt-call"}}
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
# `klt lvs` resolves a request document's "reference.netlist" relative to
# the *request document's own directory* (verified empirically -- a
# repo-cwd-relative path here fails with "reference netlist not found",
# resolved against `$WORK`, not `$ROOT`), so this has to stay `$ROOT/
# $ARRAY_REF` (absolute) for the run to work at all; `klt lvs` then echoes
# that argument back verbatim into the "reference" field of the JSON report
# below (klayout-tools#1205's response-echo behavior). Issue #109: rewrite
# just that one echoed field to the known repo-relative equivalent
# ($ARRAY_REF) before committing the report, rather than leak this host's
# absolute checkout path (previously e.g. a `.loom/worktrees/issue-N/...`
# path) -- the same "strip what shouldn't be committed" treatment this
# script's own extract-array.json step already applies to the bulk
# devices[]/nets[] arrays below.
cat > "$WORK/lvs-array-request.json" <<EOF
{"layout":{"netlist":"$WORK/array.spice","top":"sram_256x32_array"},
 "reference":{"netlist":"$ROOT/$ARRAY_REF","form":"subckt-call"},
 "options":{"flatten_reference":true}}
EOF
klt lvs "$WORK/lvs-array-request.json" --format json > "$WORK/lvs-array-raw.json"
python3 -c "
import json
d = json.load(open('$WORK/lvs-array-raw.json'))
if d.get('reference') == '$ROOT/$ARRAY_REF':
    d['reference'] = '$ARRAY_REF'
json.dump(d, open('$OUT/lvs-array.json', 'w'), indent=2)
open('$OUT/lvs-array.json', 'a').write('\n')
print('status:', d['status'], '| mismatches:', d['mismatch_count'])
"

hr "5. ERC: array supply + tie read vs erc-supply-spec.json (klt erc, T1 item 11, ~26 min)"
# T1 item 11 (power delivery, structural), issues #124 and #159. The declared
# supplies (VDD/VSS) must each resolve to exactly ONE electrical island, and
# every declared tie (ties[]: the Nwell/VDD tap and the undrawn-well
# substrate/VSS tap) must be CHECKED and satisfied. erc_finding_count counts
# erc.unconnected_net/erc.supply_short/erc.missing_tie findings -- zero is the
# pass condition, not the report's top-level status (which reads
# "not_checked" because klt has no transcribed gf180mcu antenna-limit table;
# the antenna half of the report is informational). A zero count only counts
# if erc_coverage lists each tie as checked and none as skipped: a tie
# reported degenerate lands in erc_coverage.skipped[] and is NOT evidence.
# Needs the released klt 0.6.0 (ties[].well_layer:null + well_boxes,
# klayout-tools#2255; tie fix klayout-tools#2186), e.g. put
#     uvx --from "klayout-tools==0.8.0" klt
# in place of `klt` below.
ERC_SPEC=layout/sram_256x32/erc-supply-spec.json
klt erc "$ARRAY_GDS" "$ERC_SPEC" --format json > "$WORK/erc-array-full.json" || test $? -eq 4
# (klt erc exits 4 when its overall status is not a clean antenna pass; this
# run's antenna half reads not_checked by design -- see above.)
# The full report is ~30 MB (16,640 gate nets x 4 stackup levels in gates[],
# plus 66,560 antenna-coverage row entries). Bulk omission, same treatment
# extract-array.json applies to devices[]/nets[]:
#  * gates[] is kept as a list (klt signoff 0.6.0 recognizes a klt erc
#    envelope by a top-level `gates` list plus `gate_role`) but truncated to
#    its first GATES_KEPT real entries, verbatim; gate_count keeps the true
#    total and _note says so. No gate data is invented.
#  * coverage (antenna) row arrays are collapsed as before.
#  * erc_coverage (connectivity -- the tie-check evidence) is kept IN FULL,
#    as are erc_status, erc_findings, erc_finding_count, ties_disclosure and
#    provenance.
ERC_WORK="$WORK" ERC_OUT="$OUT" python3 - <<'PYEOF'
import json, os

GATES_KEPT = 4
d = json.load(open(os.path.join(os.environ['ERC_WORK'], 'erc-array-full.json')))
gate_count = d['gate_count']
verdicts = sorted({g['antenna_verdict'] for g in d['gates']})
cov = d['coverage']
n_checked = len(cov.get('checked', []))
n_skipped = len(cov.get('skipped', []))
n_inapplicable = len(cov.get('inapplicable', []))
skip_reasons = sorted({e.get('reason') for e in cov.get('skipped', [])})
inapp_reasons = sorted({e.get('reason') for e in cov.get('inapplicable', [])})
for key in ('checked', 'skipped', 'inapplicable'):
    n = {'checked': n_checked, 'skipped': n_skipped, 'inapplicable': n_inapplicable}[key]
    cov[key] = ['<%d entries omitted as bulk -- see _note>' % n]
d['gates'] = d['gates'][:GATES_KEPT]
d['_note'] = (
    'gates[] is truncated to its first %d of %d entries (verbatim; ~29.7 MB '
    'unabridged at this array size: %d gate nets x 4 stackup levels, every '
    'antenna_verdict reading "%s") so the envelope stays recognizable to klt '
    'signoff (top-level gates list + gate_role) -- gate_count is the true total. '
    'The antenna `coverage` row arrays are collapsed (%d checked, %d skipped all '
    'reason %s, %d inapplicable all reason %s); its scalar summary is kept. '
    '`erc_coverage` (the connectivity half: which ERC work was checked, '
    'skipped, or inapplicable -- including each declared ties[] entry) is kept '
    'in full, as are status, erc_status, erc_findings, erc_finding_count, '
    'ties_disclosure and provenance (input content_hash matching the committed '
    'GDS; spec content_hash). Full output reproducible via '
    'layout/reports/generate.sh step 5.'
) % (GATES_KEPT, gate_count, gate_count, '", "'.join(verdicts), n_checked,
     n_skipped, '/'.join(skip_reasons), n_inapplicable, '/'.join(inapp_reasons))
ordered = {k: d[k] for k in ['schema_version', 'status', 'erc_status', 'file',
                             'spec', 'pdk', 'findings_only', 'gate_role',
                             'gate_count', 'gates', 'erc_finding_count',
                             'erc_findings', 'coverage', 'erc_coverage',
                             'ties_disclosure', 'provenance', '_note']
           if k in d}
out_path = os.path.join(os.environ['ERC_OUT'], 'erc-array-supply.json')
with open(out_path, 'w') as f:
    json.dump(ordered, f, indent=2)
    f.write('\n')
print('status:', d['status'], '| gates:', d['gate_count'],
      '| erc_findings:', d['erc_finding_count'],
      '| erc_checked:', len(d['erc_coverage']['checked']),
      '| erc_skipped:', len(d['erc_coverage']['skipped']))
PYEOF

run_array64

run_macro

hr "done -- reports written under $OUT/"
