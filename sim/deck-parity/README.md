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
                                 # deterministic receipts: each corner carries
                                 # the raw RESULT: lines its reducer matched
                                 # (corners[].result_lines); MC receipts
                                 # carry theirs as per-corner
                                 # result-lines.txt -- see the
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
graded anything other than `recorded`; and the deterministic `reduce`
output must carry, per corner, the raw `RESULT:` lines its reducer matched
(`corners[].result_lines`) so the graded numbers are re-derivable from
committed bytes. That requirement is keyed to the `corners[]` shape
`deck_adapter.py reduce` emits; `reduce_mc_report()` has no `corners[]`,
and the MC rule below supplies the equivalent for its one `RESULT:`-emitting
family -- the raw lines as a per-corner `result-lines.txt` -- so that
family's MC grading is re-derivable from committed bytes through that file.
That preserved
grading input is cheap -- the matched lines are ~9.6 KB of raw text across
the five families of the full-grid receipt (~3.9 KB of it for the three
`RESULT:`-emitting ones); as committed bytes the rule's cost is measured at
9,504 B for the two SNM families, re-reducing both from the receipt's
committed inputs under this rule (5,778 B of raw text plus ~23 B per
preserved line of JSON array formatting), with the three
`RESULT:`-emitting families adding at least their measured 3,996 B of raw
text (their clean-run `stdout.bin` was discarded, so their serialized
growth is not directly measurable on this receipt) -- all of it well under
1% of the ~2 MB full stdout would add -- while omitting it leaves the three
`RESULT:`-emitting families' numbers unverifiable: their raw lines lived in
the per-unit `stdout.bin` this rule discards for clean runs, and only the two
SNM families stay re-derivable, via their committed sweeps. The two
one-corner receipts (both 2026-11-14 -- the transport run and the
spiceinit-pin run) predate this rule and committed each family's single
`stdout.log`/`corner.inc`/sweep flat at the family level; the full-grid
receipt (2026-11-15, 135 units) introduced the per-corner subdirectories and
the rule, because committing all 135 engine stdout streams would add ~2 MB of
raw stream that the graded `reduced.json` already summarises. The full-grid
receipt predates the `corners[].result_lines` clause specifically (#374
added that clause after the receipt was committed) and is exempt from it
only: its committed `reduced.json` files carry no `result_lines`, so the
three `RESULT:`-emitting families' graded numbers are not re-derivable from
committed bytes (the two SNM families stay re-derivable via their committed
sweeps, as above) -- the rule's other clauses (the five core files, the
per-corner `corner.inc`, the committed SNM sweeps, the conditional
`stdout.log`) it satisfies.

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

A receipt's `## Files in` table -- whose heading names the receipt directory
the table's paths live under -- is gated by CI
(`scripts/ci/check-evidence-format.sh`): every backticked path in the table's
File column must resolve to at least one committed file under the receipt
directory, with `<...>` placeholders matched as per-segment globs (so
`<family>/<corner-id>/stdout.log` demands a committed `stdout.log` under some
family/corner pair). A row that documents artifacts deliberately **not**
committed -- today, the full-grid `stdout.log` row above -- must carry the
literal token `(none committed)` in its What cell; the gate skips such a row.
This keeps a receipt from citing evidence it does not commit (issue #356).

**Prose committed-bytes sections are deliberately out of scope for that
gate** (issue #372). A receipt may additionally -- or instead -- document
its artifacts in prose (both MC receipts do, under `## What is re-derivable
from committed bytes`); CI does not resolve prose-cited paths. Prose claims
are not machine-checkable: the receipt's machine-checkable inventory is its
`## Files in` table, and a receipt that documents committed artifacts in
prose only sits outside the gate. Two pieces of visibility keep that from
being silent: the check's success line reports its coverage -- receipt
`Files in` tables gated, rows resolved -- so a zero-coverage receipt shows
up as a dropped count rather than the same green line as a fully-gated one;
and a deck-parity receipt whose `| File | What |` table sits under a heading
the gate cannot see (a one-character heading deviation) draws a warning,
never a CI failure, naming the doc and the unmatched heading. Tables in the
other experiments' READMEs are directory listings, not receipts, and are
outside the warning.

## Receipts

The first three receipts answer the deck-transport question (the #230
migration this directory scopes itself to); the `spiceinit-pin` receipt
answers a different one -- generator **environment**: whether the staged,
pinned `.spiceinit` (#338) reaches the fleet worker and reproduces the
committed values. The `mc-9corner` receipt completes the MC half of the
transport question and records a new finding about that environment: the
committed *MC* records were taken unpinned, so the pin moves the SNM
negative-control values off them (fully attributed in the receipt).

| Receipt | Corner(s) | Families | Result |
|---|---|---|---|
| [`20261114-tt_25c_3.30v.md`](20261114-tt_25c_3.30v.md) | `tt_25c_3.30v` | all 5 characterization families | parity holds; the 3 `RESULT:`-emitting families match the committed value exactly, the 2 SNM families match to <= 3 uV once the documented #213 extractor change is held fixed |
| [`20261115-full-grid.md`](20261115-full-grid.md) | all 27 | all 5 characterization families | parity holds at every corner: 108/108 record metrics exact across the 3 `RESULT:`-emitting families, the 2 SNM families within 1 uV / 7 uV of the committed value (gate 30 uV) under the pre-#213 crosscheck, 0 `OPEN` units |
| [`20261115-mc-2corner.md`](20261115-mc-2corner.md) | `tt_25c_3.30v`, `ff_125c_2.97v` | the 3 MC families (`read-snm`, `hold-snm`, `write-margin`) | first live Monte Carlo run (3,040 units, one batch-set): every mm sample of the committed arrays reproduced -- `write-margin` exact, the SNM families exact under the pre-#213 `--pair` extractor (max delta 0.0 V) -- every ctrl anchor pinned, every nc errored count and surviving value matched; 5 `OPEN` nc units reported (committed record excluded the same draws) |
| [`20261116-mc-9corner.md`](20261116-mc-9corner.md) | all 9 (full committed MC matrix) | the 3 MC families | 13,680 units in two phases (first submit crashed mid-upload at `klayout-tools#5880`; its 16 collected shards were reused after a byte-identical re-staging provenance check, 5 missing shards re-submitted): all 5,400 mm samples within gate (`write-margin` exact, worst SNM delta 6 uV), 108/108 ctrl anchors exact under the #346 pin, nc errored sets exact everywhere; nc surviving values diverge only for the known-bad draws and are attributed by a committed local A/B to the pin (the committed MC campaign ran unpinned) |
| [`20261114-tt_25c_3.30v-spiceinit-pin.md`](20261114-tt_25c_3.30v-spiceinit-pin.md) | `tt_25c_3.30v` | all 5 characterization families | parity holds with the `.spiceinit` pin staged (#338): all 7 committed record metrics across the 5 families reproduce exactly -- the 3 `RESULT:`-emitting families exact, the 2 SNM families exact under the pre-#213 extractor crosscheck |

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
