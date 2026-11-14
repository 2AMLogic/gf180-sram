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
  <date>-<corner-id>.md         # the receipt: what ran, job ids, executor
                                 # identity, the comparison table, the limits
  <date>-<corner-id>/
    batch-set-envelope.json     # klt sim --batch-set aggregate envelope
    set-manifest.json           # per-member request -> job id mapping
    <family>/
      request.json              # the deck-list request as submitted
      report.json               # klt sim's deck report (environment.remote)
      reduced.json              # deck_adapter.py reduce --request output
      stdout.log                # the worker's engine stdout, unmodified
      corner.inc                # the generated corner include
      *_sweep.txt               # declared sweep outputs the fleet returned
```

A request's `units/` scratch tree is deliberately **not** committed: the decks
are already in the repo (`sim/*/testbench/`, `design/netlist/`) and each
request's `x_gf180_sram_adapter` block carries the source-testbench and
composed-deck sha256, which the report's `units[].deck_sha256` is checked
against. So a receipt is auditable without duplicating netlists.

## Receipts

| Receipt | Corner | Families | Result |
|---|---|---|---|
| [`20261114-tt_25c_3.30v.md`](20261114-tt_25c_3.30v.md) | `tt_25c_3.30v` | all 5 characterization families | parity holds; the 3 `RESULT:`-emitting families match the committed value exactly, the 2 SNM families match to <= 3 uV once the documented #213 extractor change is held fixed |

## Reproducing one

Deck-mode runs go to the batch fleet, never a local grid (host policy). The
exact commands for each receipt are in the receipt itself; the shape is:

```bash
python3 sim/lib/deck_adapter.py build <family> --corner tt:25:3.30 \
  --stage-dir <scratch> --request-out <scratch>/<family>.json
klt sim <scratch>/<family>.json --backend batch --wait-for-capacity 600 \
  -o <out> --report-out <out>/report.json
python3 sim/lib/deck_adapter.py reduce <family> <out>/report.json \
  --request <scratch>/<family>.json
```

`--request` pins the reducer's expected coverage to the corners the request
actually asked for, and checks the executed `deck_sha256` against the composed
deck; without it the reducer expects all 27 corners and a bounded run grades
`OPEN`. A single corner may also be run with `--backend local` as a debug
probe before spending fleet capacity.
