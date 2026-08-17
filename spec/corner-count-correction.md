# Decision record: the "Corner set" corner count is 27, not 9

**Status**: Decided, 2026-08-17
**Resolves**: #53 ("spec/sram.md 'Corner set' arithmetic error: 3x3x3 labeled
'9 corners' but the actual matrix (and every committed sim/ record) has 27
points")
**Amends**: `spec/sram.md` § "Characterization" → "Corner set" and
§ "Characterization" → "Signoff definition" (prose only — see "What this
record does not change")

## Question

`spec/sram.md`'s ratified "Corner set" section defines three fully-crossed
axes ("**Process** × **temperature** × **voltage**, all combinations") of
three points each, then labels their product:

> 3 × 3 × 3 = **9 corners**

3 × 3 × 3 = 27. Was the ratified intent (a) the full 27-point cross product,
mislabeled as "9" by an arithmetic slip in the prose, or (b) a 9-point corner
set, with voltage meant as something other than a fully-crossed third axis?

That distinction matters because it decides whether this is a text fix or a
scope change: under (a) nothing about the ratified corner set moves and the
fix is a label correction; under (b) the executed sweeps have been running a
27-point superset of the ratified set and the spec's own axis description
would need rewriting.

## Answer

**(a) — the intent is the full 27-point cross product; "9" was an arithmetic
slip in the prose, and is corrected to 27.**

This record ratifies that reading. `spec/sram.md` now reads
`3 × 3 × 3 = **27 corners**`, and the Signoff definition's "every one of the
9 corners above" reads "every one of the 27 corners above."

### Evidence

Three independent lines of evidence, all pointing the same way:

1. **The spec's own axis description.** The section header sentence is
   "**Process** × **temperature** × **voltage**, all combinations," and the
   table lists three points on each axis. A fully-crossed set of three
   3-point axes has 27 members; there is no reading of "all combinations"
   under which it has 9. Reading (b) would require the voltage row to be
   something other than a crossed axis, which the section does not say.

2. **Every committed record already contains 27 corner points.** Each
   `sim/*/records/*.md` produced by `sim/lib/run_corner_sweep.sh` carries
   exactly 27 `- **<corner-id>**:` result rows (9 `ff_*` + 9 `tt_*` +
   9 `ss_*`), spanning `{ff,tt,ss} × {-40,25,125}C × {2.97,3.30,3.63}V`.
   The harness has never run a 9-point subset.

3. **The harness itself is a triple-nested loop over the three axes.**
   `sim/lib/run_corner_sweep.sh` iterates `PROCESSES × TEMPS × VDDS` with no
   subsetting; the "9" it printed was a hardcoded string literal in its
   record text and terminal output, not a count of anything it did.

`sim/signoff-summary.md` — the derived per-corner PASS/FAIL rollup — already
reported the real 27-row count and flagged the spec's "9" as an
inconsistency, deferring the spec edit to this record.

### Why the correction is safe

The 27-point matrix is a superset of any 9-point reading of the ratified
axes, and every one of those 27 points already passes the Signoff
definition's strictly-`> 0` requirement for read SNM, hold SNM, and write
margin, with access time recorded (see `sim/signoff-summary.md`). So
correcting the count neither invalidates a recorded result nor weakens a
requirement: it makes the spec's prose agree with the evidence that was
always there.

This is explicitly **not** a case of relaxing the ratified spec to make a
result pass (`CLAUDE.md`: "agents do not relax the ratified spec to make
results pass"). The correction *raises* the stated number of corners a
signoff must cover, from 9 to 27, and every corner in the larger set already
has committed evidence.

## What this record does not change

- **The corner set itself.** The three axes and their points are untouched:
  process `{ff, tt, ss}`, temperature `{-40, 25, 125} C`, supply
  `{2.97, 3.30, 3.63} V`.
- **The Signoff definition.** Still "read SNM, hold SNM, and write margin
  strictly positive, plus a recorded access time, at every corner" — only the
  numeral naming how many corners "every corner" is has changed.
- **Any committed evidence.** Nothing under `sim/*/records/`,
  `sim/*/corners/`, `sim/*/netlist-snapshots/`, `sim/*/raw-logs/`, or the
  Monte Carlo trees (`sim/*/mc/**`) is edited. Those records' generated text
  says "9 corner points total" while listing 27 rows, because that is what
  the harness printed at generation time; the append-only rule
  (`sim/README.md` § "Append-only rule") means that stays exactly as
  recorded. The mislabel is fixed at the *source* — the script — so every
  future record states the correct, computed count.
- **Any measured value, verdict, or aggregate** in `sim/signoff-summary.md`.
  The rollup is regenerated from the same unchanged records; only its
  explanatory "Note on corner count" prose changes, because the spec
  inconsistency it described no longer exists.

## Consequence for tooling and docs

The wrong count had been copied out of the spec into the harness and every
doc that cited it. All of those are corrected alongside this record:

- `sim/lib/run_corner_sweep.sh` — the three places that printed "9" (the
  generated record's corner-matrix line, its `Overall: recorded` line, and
  the terminal summary) now **compute** the count as
  `${#PROCESSES[@]} * ${#TEMPS[@]} * ${#VDDS[@]}`, so the number can no
  longer drift from the loop that produces it if an axis is ever changed.
- `sim/README.md`, root `README.md`, `sim/lib/render_signoff_table.py`,
  `sim/lib/run_mc_campaign.py`, `sim/lib/snm_extract.py`, and the
  `sim/*/testbench/*.spice` header comments — all corrected to 27. The
  testbench edits are comment-only (SPICE `*` lines), change no netlist
  semantics, and therefore do not trigger the append-only rule's
  "a fix to the testbench gets verified by a new record" clause: there is no
  measurement for a new record to re-verify.
- `WORK_LOG.md` and `WORK_PLAN.md` still contain "9-corner" strings, and are
  deliberately left alone: those are verbatim quotations of forge artifact
  titles (issue #24's title, PR #46's title) that exist on GitHub with that
  wording and cannot be retroactively edited. Rewriting the quotations would
  make the log a less accurate record, not a more accurate one, and the
  Guide role regenerates both files from the forge anyway.

## References

- `spec/sram.md` § "Characterization" → "Corner set" / "Signoff definition"
  — the corrected text, with an inline note pointing here.
- `sim/signoff-summary.md` — the derived 27-row per-corner PASS/FAIL rollup
  that first surfaced the discrepancy.
- `sim/README.md` § "The ratified 27-corner PVT matrix" — the harness-side
  description of the same matrix.
- `CLAUDE.md` — "Spec changes go through `spec/` with a decision record;
  agents do not relax the ratified spec to make results pass," the rule this
  record exists to satisfy.
