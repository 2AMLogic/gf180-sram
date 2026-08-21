# Decision record: no numeric `target_yield` — Cpk/sigma-to-spec/empirical-yield-lower-bound only

**Status**: Proposed for ratification via PR approval (2AMLogic/2am#357 standing
policy — the operator's PR approval is the ratification act; see
"Ratification mechanism" below)
**Resolves**: #90 ("Ratify a numeric `target_yield` (or explicit 'no target')
for read SNM, hold SNM, and write margin")
**Amends**: `spec/sram.md` § "Characterization" (additive only — see "What
this record changes")

## Question

`spec/statistical-treatment-decision.md` (resolving #20) ratified read SNM,
hold SNM, and write margin as statistical (mismatch-driven) spec rows
requiring Monte Carlo evidence, but explicitly deferred ratifying a numeric
`target_yield` / confidence bar those rows are graded against. The three
committed MC campaigns (PR #58, closing #26) report Cpk, sigma-to-spec, and
an exact Clopper-Pearson empirical-yield lower bound at every corner, but
`spec/sram.md` ratifies no numeric bar for any of it to be measured against.
This record picks one of the three options #90 itself lays out: ratify a
number, ratify "no number," or ratify some other numeric-bar shape.

## Answer

**No numeric `target_yield` is ratified.** The standing requirement for read
SNM, hold SNM, and write margin stays exactly what the three committed
campaigns (PR #58) already report: a `klt yield` document per row with a
recorded seed, sample count, determinism control, and negative control,
graded on Cpk / sigma-to-spec / the exact Clopper-Pearson empirical-yield
lower bound — never against an invented pass/fail number.

This is a decision to formalize the status quo, not a placeholder: the
option to pick a number was seriously considered (see "Why a number was not
picked" below) and rejected on the evidence in this repo already, not for
lack of looking.

### Evidence

1. **The Cpk range the existing campaigns already report spans two orders of
   magnitude, with no principled way to collapse it to one number from this
   evidence alone.** Per `spec/statistical-treatment-decision.md`'s own
   summary table:

   | Measurement | Cpk range (9 corners) | sigma-to-spec range |
   |---|---|---|
   | Read SNM | 2.55 – 8.18 | 7.65 – 24.5 |
   | Hold SNM | 18.3 – 22.9 | 54.9 – 68.6 |
   | Write margin | 74.2 – 133.2 | 222.6 – 399.6 |

   A single `target_yield` graded against the *worst* corner's Cpk (read
   SNM's 2.55, already well above the conventional 1.33 process-capability
   bar) would be trivially met by hold SNM and write margin at every corner
   with no discriminating power left; graded against a *typical* value
   instead, it would silently pass a real read-SNM regression at the
   corners already closest to the limit. Neither choice is informed by
   anything this record has evidence for — it is exactly the "deliberate
   risk-tolerance call... has no evidence basis to make unilaterally" the
   deferring record already named.

2. **A 200-sample-per-corner campaign structurally cannot resolve the
   per-bit yield an 8192-bit array needs, so a numeric bar set against it
   now would not mean what it appears to mean.** `sim/README.md` § "Two
   yield estimates" states this plainly: "a plain-random campaign at N =
   200 per corner bounds the empirical per-cell yield only to roughly 98%
   at 95% confidence — whereas an 8192-bit array needs per-cell yield far
   beyond what a few hundred samples can resolve. Closing that gap needs a
   ratified target and a variance-reduced (importance-sampled) campaign,
   not more of the same draws." Ratifying, say, "Cpk ≥ 1.33" or "empirical
   yield ≥ 99.9%" today would be graded against a campaign that cannot
   distinguish that bar from a materially worse one at array scale — the
   number would look like a real gate while measuring a claim the evidence
   cannot actually support. A target set now would either have to be so
   loose it adds no discriminating power (see point 1) or would overstate
   the confidence a 200-sample campaign can back.

3. **No external precedent this record can honestly cite.** Issue #90
   itself allows ratifying a number "informed by industry PPM/DPM precedent
   for a canary macro at this scale." This repo's own `spec/` and `docs/`
   trees carry no such citation today (checked: no PPM/DPM/industry-yield
   reference exists anywhere in `spec/*.md` or `docs/*.md` other than this
   record and the ones it cites), and CLAUDE.md's canary framing — "this
   block is not competing with OpenRAM... use OpenRAM's output as a
   reference and comparison where it helps, cite it when you do" — commits
   this repo to citing a source, not inventing a bar from first principles.
   Introducing a specific PPM/DPM number without a citable source would be
   exactly the "invent one here without that backing" move the deferring
   record already flagged as out of bounds, and CLAUDE.md's "agents do not
   relax the ratified spec to make results pass" applies equally to
   *tightening* an ungrounded number into the spec as it does to loosening
   one.

4. **The status quo is not "no requirement" — it already has teeth.**
   `sim/lib/run_mc_campaign.py` / `klt yield` already refuses to silently
   invent a target: it emits an explicit, machine-readable warning on every
   report ("No `target_yield` is declared... this harness does not invent
   one") and reports the honest two-sided estimate (empirical
   Clopper-Pearson lower bound *and* the parametric Cpk/sigma-to-spec
   figure with its own confidence interval and Anderson-Darling normality
   check) rather than collapsing to a pass/fail bit. A regression is still
   visible under this regime — Cpk/sigma-to-spec dropping between two
   records for the same corner is exactly as informative as a bare
   pass/fail flip, and more informative than a bare pass/fail flip that
   happens to straddle an arbitrary bar. Ratifying "no number" here
   formalizes a status quo that already does real evidentiary work, not a
   waiver of one.

### Why a number was not picked

The honest failure mode this record is guarding against is not "too lazy to
pick a number" — it is picking one that either does no discriminating work
(set below every corner's worst-case Cpk, per point 1) or implies a
confidence level the underlying N = 200 campaigns cannot back (per point 2).
Both of those are worse than stating the true current bound: this repo has
*some* margin at every ratified corner, quantified precisely (Cpk,
sigma-to-spec, an exact empirical lower bound with its own confidence
interval), with no discriminating pass/fail line drawn across it yet because
no evidence-backed line exists. `sim/README.md` already reaches the same
conclusion independently, in the section documenting why closing the array-
scale yield gap "needs a ratified target and a variance-reduced
(importance-sampled) campaign, not more of the same draws" — i.e., a future
record picking a number should arrive paired with the campaign design that
can actually support it, not detached from one.

### Why this correction is safe

Nothing about the ratified 27-corner deterministic matrix, the Signoff
`> 0` threshold, the statistical-row classification (`spec/statistical-
treatment-decision.md`), or any committed evidence changes. This record
resolves the last open sub-question `spec/statistical-treatment-decision.md`
named ("Deferred: `target_yield`") by making the status quo it already
described the ratified answer, rather than leaving it perpetually deferred.
No evidence under `sim/` is edited or re-run.

## What this record changes

`spec/sram.md`'s Characterization section, "What must be measured, not just
asserted" subsection, "Statistical treatment" paragraph currently ends:

> ...No numeric `target_yield` bar is ratified for these rows; that is an
> explicitly deferred follow-up (see `spec/statistical-treatment-decision.md`
> § "Deferred: `target_yield`").

That sentence is replaced with:

> No numeric `target_yield` bar is ratified for these rows, and none is
> planned absent new evidence: `spec/target-yield-decision.md` ratifies
> Cpk / sigma-to-spec / the exact empirical-yield lower bound, each with its
> own confidence interval, as the standing requirement instead of a
> pass/fail number.

## What this record does not change

- **The corner set, corner count, or Signoff definition.** Untouched — see
  `spec/corner-count-correction.md`.
- **The statistical-row classification.** `spec/statistical-treatment-
  decision.md`'s ratification that read SNM, hold SNM, and write margin are
  statistical (mismatch-driven) rows requiring Monte Carlo evidence is
  unchanged; this record only resolves that record's own deferred
  sub-question.
- **Any committed evidence.** Nothing under `sim/*/records/`,
  `sim/*/corners/`, or `sim/*/mc/**` is edited or re-run. The three existing
  MC campaigns (PR #58) already satisfy this record's requirement exactly as
  committed.
- **The Signoff `> 0` threshold.** Read SNM, hold SNM, and write margin must
  still be strictly positive at every corner; that requirement is
  independent of, and unaffected by, this record's statistical-grading
  question.
- **The door to a future numeric bar.** This record does not forbid a later
  decision record from ratifying a `target_yield` once it is paired with
  evidence that can actually support the confidence level implied — e.g. a
  variance-reduced / importance-sampled campaign sized for array-scale
  per-bit yield, per `sim/README.md`'s own diagnosis of what closing that
  gap needs. This record only declines to ratify one on today's evidence.

## Ratification mechanism

Per 2AMLogic/2am#357 (2026-08-19 operator ruling), canary spec/DR
ratification-via-PR is standing policy for this repository: a builder drafts
the ratification/decision record as a PR on the evidence already collected,
and the operator's approval of that PR is the ratification act itself — not
a separate, later sign-off. This record is drafted under that policy; it
reflects the evidence above for the operator to approve or reject, not a
ruling this agent is making unilaterally.

## References

- `spec/sram.md` § "Characterization" — the section this record amends.
- `spec/statistical-treatment-decision.md` — the prior decision record this
  one resolves the deferred sub-question of, and the structural model
  (Status/Resolves/Amends/Question/Answer + Evidence/References) this
  record follows.
- `sim/read-snm/mc/records/20260817-102455-ce56f59.md`,
  `sim/hold-snm/mc/records/20260817-103316-ce56f59.md`,
  `sim/write-margin/mc/records/20260817-104116-ce56f59.md` — the three
  committed Monte Carlo / `klt yield` evidence records cited above (PR #58,
  merged 2026-08-17, closing #26).
- `sim/README.md` § "Limits, and the one number this repo does not invent"
  and § "Interpreting these results against sign-off" — the harness-side
  reasoning (array-scale yield resolution, the deliberate absence of an
  invented bar) this record's Answer is grounded in.
- klayout-tools `docs/design-evidence-tiers.md` item 6 — the evidence-tier
  requirement the statistical classification triggers (unaffected by this
  record).
- Issue #90 — the operator-decision issue this record resolves; #20 (the
  statistical-treatment ruling this follows); #26 / PR #58 (the MC/yield
  evidence-collection work cited as evidence above).
- `CLAUDE.md` — "Spec changes go through `spec/` with a decision record;
  agents do not relax the ratified spec to make results pass" (this record
  declines to *tighten* the spec with an ungrounded number, for the same
  reason agents must not relax it with an ungrounded waiver), and
  "Verification is the product: no claim without a testbench."
