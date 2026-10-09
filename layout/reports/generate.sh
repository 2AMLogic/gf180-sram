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
#     uvx --from "klayout-tools==0.6.0" klt
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

hr "done -- reports written under $OUT/"
