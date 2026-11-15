# sim/deck-parity -- parity receipts for the `klt sim` deck-mode migration (#230)

Evidence that `klt sim`'s **precomposed-deck** transport reproduces what the
hand-rolled local launchers (`sim/lib/run_corner_sweep.sh`, the
`sim/lib/run_mc_campaign.py` process pool) measure, at the same corner, from
the same unmodified testbench decks. This is blocker 2 of the staged migration
described in `sim/README.md` "Staged migration to `klt sim` deck mode".

**These are not characterization records.** Nothing here mints, edits or
supersedes a record under `sim/*/records/`, and no value here may be quoted as
a measurement of the cell. A receipt answers one question only: does the
migrated generator produce the committed number? Characterization evidence
stays in the per-experiment `records/` directories, which are append-only.

```
sim/deck-parity/
  <date>-<corner-id|full-grid>.md    # the receipt: what ran, job ids, executor
                                     # identity, the comparison table, the limits
  <date>-mc-<n>corner.md             # MC receipts name their corner count
  <date>-<corner-id|full-grid>/
    batch-set-envelope.json      # klt sim --batch-set aggregate envelope
    set-manifest.json            # per-member request -> job id mapping
    <family>/
      request.json               # the deck-list request as submitted
      report.json                # klt sim's deck report (environment.remote)
      reduced.json               # deck_adapter.py reduce --request output
                                 # (MC receipts: mc-reduce --json-out output);
                                 # each corner carries the raw RESULT: lines
                                 # its reducer matched -- see the
                                 # committed-bytes rule below
      parity-compare.md          # parity_compare.py's full comparison table
      parity-summary.json        # its machine-readable summary
      <corner-id>/               # one subdirectory per corner run
        corner.inc               # the generated corner include (MC receipts:
                                 # one representative per (corner, kind[, side]),
                                 # named corner.inc.<kind>[-<side>])
        stdout.log               # the worker's engine stdout -- see the
                                 # committed-bytes rule below
        *_sweep.txt              # declared sweep outputs the fleet returned
                                 # (MC receipts: ctrl + first 5 mm units only,
                                 # under <corner-id>/sweeps/<unit-id>/)
      open-units/                # MC receipts: captured streams of units that
                                 # graded other than recorded
```

A request's `units/` scratch tree is deliberately **not** committed: the decks
are already in the repo (`sim/*/testbench/`, `design/netlist/`) and each
request's `x_gf180_sram_adapter` block carries the source-testbench and
composed-deck sha256, which the report's `units[].deck_sha256` is checked
against. So a receipt is auditable without duplicating netlists.

**Committed-bytes rule** (introduced with the full-grid receipt; the MC
receipt extends it): per family, commit `request.json`, `report.json`,
`reduced.json` and the per-corner `corner.inc`; commit the returned
`*_sweep.txt` for the SNM families (they are what makes the pre-#213
crosscheck auditable); commit a unit's `stdout.log` **only** when that unit
graded anything other than `recorded`; and `reduced.json` must carry, per
corner, the raw `RESULT:` lines its reducer matched (`corners[].result_lines`)
so the graded numbers are re-derivable from committed bytes. That preserved
grading input is cheap -- measured ~9.6 KB across the five families of the
full-grid receipt (~3.9 KB of it for the three `RESULT:`-emitting ones, ~0.5%
of the ~2 MB full stdout would add) -- while omitting it leaves the three
`RESULT:`-emitting families' numbers unverifiable: their raw lines lived in
the per-unit `stdout.bin` this rule discards for clean runs, and only the two
SNM families stay re-derivable, via their committed sweeps. The one-corner
receipt (2026-11-14) predates this rule and committed each family's single
`stdout.log`/`corner.inc`/sweep flat at the family level; the full-grid
receipt (2026-11-15, 135 units) introduced the per-corner subdirectories and
the rule, because committing all 135 engine stdout streams would add ~2 MB of
raw stream that the graded `reduced.json` already summarises.

**MC receipts do not commit one sweep per unit** (a rule that does not
scale): one SNM sweep pair-side is ~22 KB, so per-unit sweeps would have been
~52 MB for the 2026-11-15 MC receipt's two corners alone. The MC rule
instead commits, per family: the five core files above; **one representative
`corner.inc` per (corner, kind[, side])** (every unit's seed is in the
committed request manifest); raw `*_sweep.txt` only for **all `ctrl` units
and the first 5 `mm` sample indices** per (family, corner), so the pre-#213
extractor path stays spot-auditable; `stdout`/`stderr` **only for units that
graded other than `recorded`**; and -- for the `RESULT:`-emitting family --
the raw `RESULT:` lines as one compact per-corner `result-lines.txt` so the
exact-match claim is re-derivable from committed bytes. The receipt must
state which claims are re-derivable from committed bytes and which are not
(the MC receipt has a section for exactly this).

## Receipts

| Receipt | Corner(s) | Families | Result |
|---|---|---|---|
| [`20261114-tt_25c_3.30v.md`](20261114-tt_25c_3.30v.md) | `tt_25c_3.30v` | all 5 characterization families | parity holds; the 3 `RESULT:`-emitting families match the committed value exactly, the 2 SNM families match to <= 3 uV once the documented #213 extractor change is held fixed |
| [`20261115-full-grid.md`](20261115-full-grid.md) | all 27 | all 5 characterization families | parity holds at every corner: 108/108 record metrics exact across the 3 `RESULT:`-emitting families, the 2 SNM families within 1 uV / 7 uV of the committed value (gate 30 uV) under the pre-#213 crosscheck, 0 `OPEN` units |
| [`20261115-mc-2corner.md`](20261115-mc-2corner.md) | `tt_25c_3.30v`, `ff_125c_2.97v` | the 3 MC families (`read-snm`, `hold-snm`, `write-margin`) | first live Monte Carlo run (3,040 units, one batch-set): every mm sample of the committed arrays reproduced -- `write-margin` exact, the SNM families exact under the pre-#213 `--pair` extractor (max delta 0.0 V) -- every ctrl anchor pinned, every nc errored count and surviving value matched; 5 `OPEN` nc units reported (committed record excluded the same draws) |

## Reproducing one

Deck-mode runs go to the batch fleet, never a local grid (host policy). The
exact commands for each receipt are in the receipt itself; the shape is:

```bash
python3 sim/lib/deck_adapter.py build <family> [--corner tt:25:3.30] \
  --stage-dir <scratch> --request-out <scratch>/<family>/request.json
klt sim [--batch-set <requests> ...] --backend batch --wait-for-capacity 600 \
  -o <out> --report-out <out>/report.json
python3 sim/lib/deck_adapter.py reduce <family> <out>/report.json \
  --request <scratch>/<family>/request.json
python3 sim/lib/parity_compare.py <family> <reduced.json> \
  --request <scratch>/<family>/request.json     # the mechanical comparison
```

Note the request lands *inside* its `--stage-dir`: `klt sim` resolves a deck
request's relative `units/...` paths against the request file's own directory.

The Monte Carlo counterpart uses `mc-build` / `mc-reduce` and the comparator's
`mc` mode (committed sample-sets are the comparison target, via
`MC_SAMPLE_SETS`; SNM families additionally need the pre-#213 extractor's
`--pair` mode and `--sweep-dir` pointing at the collected per-unit tree):

```bash
python3 sim/lib/deck_adapter.py mc-build <family> --corner tt:25:3.30 --corner ff:125:2.97 \
  --n 200 --n-control 4 --n-nc 100 --seed 20260817 [--nc-mismatch-scale N] [--nc-vdd V] \
  --stage-dir <scratch>/<family> --request-out <scratch>/<family>/request.json
klt sim --batch-set <scratch>/<fam1>/request.json ... --wait-for-capacity 600 \
  -o <out> --report-out <out>/batch-set-envelope.json
python3 sim/lib/deck_adapter.py mc-reduce <family> <request.json> <report.json> \
  --outdir <out>/<member> --json-out <family>-reduced.json
python3 sim/lib/parity_compare.py mc <family> <family>-reduced.json \
  --request <request.json> --report <report.json> --unit-dir <out>/<member> \
  [--sweep-dir <out>/<member> --pre213 <pre-#213-snm_extract.py>]
```

`--request` pins the reducer's expected coverage to the corners the request
actually asked for, and checks the executed `deck_sha256` against the composed
deck; without it the reducer expects all 27 corners and a bounded run grades
`OPEN`. A single corner may also be probed with `--backend local` as a debug
probe before spending fleet capacity -- on a host with the pinned PDK; a host
without one probes through the same batch path instead. `parity_compare.py`
makes the record comparison mechanical (exact match for the `RESULT:` families,
pre-#213 crosscheck with the 30 uV gate for the SNM families, plus the
`deck_sha256` present-and-equal assertion), and exits non-zero on any
mismatch, coverage gap or `OPEN` corner.
