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
# Step 5 (klt erc, issue #124 / T1 item 11) additionally needs a klt whose
# erc envelope carries the #1968 status+provenance block -- klayout-tools at
# d5893304 or later (this report was minted with klt 0.5.0+gd5893304afc2);
# the released 0.5.0 predates it and would omit provenance.input.
# content_hash, the freshness pin the report exists to carry. It is also
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

hr "5. ERC: array supply read vs erc-supply-spec.json (klt erc, T1 item 11, ~26 min)"
# T1 item 11 (power delivery, structural), issue #124. The declared supplies
# (VDD/VSS) must each resolve to exactly ONE electrical island:
# erc_finding_count counts erc.unconnected_net/erc.supply_short findings
# naming them -- zero is the pass condition, not the report's top-level
# status (which reads "not_checked" because klt has no transcribed gf180mcu
# antenna-limit table; the antenna half of the report is informational).
ERC_SPEC=layout/sram_256x32/erc-supply-spec.json
klt erc "$ARRAY_GDS" "$ERC_SPEC" --format json > "$WORK/erc-array-full.json"
# The full report is ~29.7 MB (16,640 gate nets x 4 stackup levels in
# gates[], plus 66,560 coverage-row entries) -- the same bulk-omission
# treatment extract-array.json applies to devices[]/nets[]. Every field the
# item 11 supply read grades (status, erc_findings, erc_finding_count,
# provenance) is kept in full.
ERC_WORK="$WORK" ERC_OUT="$OUT" python3 - <<'PYEOF'
import json, os

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
d.pop('gates', None)
d['_note'] = (
    'gates[] and the bulk of coverage row arrays are omitted from this committed '
    'report, exactly as extract-array.json omits devices[]/nets[] (~18 MB): gates[] '
    'is %d gate nets x 4 stackup levels (~29.7 MB unabridged at this array size), '
    'every antenna_verdict reading "%s"; coverage.checked/skipped/inapplicable '
    'collapsed the same way (%d checked, %d skipped all reason %s, %d inapplicable '
    'all reason %s) -- coverage\'s scalar summary (known, nothing_checked, '
    'nothing_checked_reasons) is kept. Every field the T1 item 11 supply read '
    'grades -- status, erc_findings, erc_finding_count, and provenance (input '
    'content_hash matching the committed GDS; spec content_hash) -- is kept in '
    'full. Full output reproducible via layout/reports/generate.sh step 5.'
) % (gate_count, '", "'.join(verdicts), n_checked, n_skipped,
     '/'.join(skip_reasons), n_inapplicable, '/'.join(inapp_reasons))
ordered = {k: d[k] for k in ['schema_version', 'status', 'file', 'spec', 'pdk',
                             'gate_role', 'gate_count', 'erc_finding_count',
                             'erc_findings', 'coverage', 'provenance', '_note']
           if k in d}
out_path = os.path.join(os.environ['ERC_OUT'], 'erc-array-supply.json')
with open(out_path, 'w') as f:
    json.dump(ordered, f, indent=2)
    f.write('\n')
print('status:', d['status'], '| gates:', d['gate_count'],
      '| erc_findings:', d['erc_finding_count'])
PYEOF

hr "done -- reports written under $OUT/"
