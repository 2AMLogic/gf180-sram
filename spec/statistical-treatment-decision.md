# Decision record: read/hold SNM and write margin are statistical rows

**Status**: Proposed for ratification via PR approval (2AMLogic/2am#357 standing
policy — the operator's PR approval is the ratification act; see
"Ratification mechanism" below)
**Resolves**: #20 ("Operator decision: ratify whether read/hold SNM and write
margin are statistical (Monte-Carlo-requiring) spec rows")
**Amends**: `spec/sram.md` § "Characterization" (additive only — see "What
this record does not change")

## Question

`spec/sram.md`'s Characterization section defines read SNM, hold SNM, and
write margin as per-corner recorded margins across the ratified 27-corner PVT
matrix (`spec/corner-count-correction.md`), but never states whether these
rows are **statistical** (mismatch-driven, requiring Monte Carlo evidence per
klayout-tools' `docs/design-evidence-tiers.md` item 6) or **deterministic**
corner-only quantities. Item 6 requires a spec whose statistical rows are
ambiguous to "say so explicitly rather than omit the item" — an omission
first flagged by #13's T1 re-read and decomposed into this issue by #18.

## Answer

**Read SNM, hold SNM, and write margin are statistical (mismatch-driven) spec
rows.** Each requires Monte Carlo (device-mismatch) evidence, combined with —
never substituting for — the ratified 27-corner deterministic matrix, per
`docs/design-evidence-tiers.md` item 6.

This record ratifies that reading and amends `spec/sram.md`'s Characterization
section to state it explicitly (see the amendment text under "What this
record changes" below).

A numeric yield/confidence bar (`target_yield`) for grading the campaigns
against is **explicitly deferred**, not ratified here — see "Deferred:
`target_yield`" below.

### Evidence

Three independent lines of evidence, all pointing the same way:

1. **Device physics, cited in the issue itself.** SNM and write margin in a
   6T bitcell are textbook mismatch-sensitive quantities: the cross-coupled
   inverter pair and the two access transistors each draw independent
   Vt/beta offsets on real silicon, and inter-device mismatch is the dominant
   real-failure mechanism for both stability margins. A corner matrix moves
   every device on the same die together and cannot exercise this
   independent-offset failure mode at all — only a Monte Carlo mismatch
   campaign can. This is the "strong prior" the issue's own "Context for the
   ruling" section documents, and the Curator's routing comment
   (2026-08-16) confirmed it is "close to settled" as a technical matter,
   with only sequencing/wording left open — exactly what this record
   resolves.

2. **klayout-tools' evidence-tier definition matches this row shape exactly.**
   `docs/design-evidence-tiers.md` item 6: "any accuracy, offset, or
   matching spec row is statistical; a corner matrix... cannot validate it."
   Read SNM, hold SNM, and write margin are offset/matching-sensitive
   margins by construction (see 1), so they fall squarely inside item 6's
   scope, not at its edge.

3. **The evidence-collection side is already built and already runs under
   this reading.** PR #58 (merged 2026-08-17, closing companion issue #26)
   added a Monte Carlo mismatch harness (`sim/lib/run_mc_campaign.py`) and
   committed one campaign per margin, each combined with — not replacing —
   the deterministic 27-corner records:

   | Claim | Record | Corners | N/corner | Cpk range | sigma-to-spec range | Determinism control | Negative control |
   |---|---|---|---|---|---|---|---|
   | Read SNM | [`sim/read-snm/mc/records/20260817-102455-ce56f59.md`](../sim/read-snm/mc/records/20260817-102455-ce56f59.md) | 9-point MC subset of the 27-corner set | 200 | 2.55 – 8.18 | 7.65 – 24.5 | PINNED (9/9) | detected (9/9) |
   | Hold SNM | [`sim/hold-snm/mc/records/20260817-103316-ce56f59.md`](../sim/hold-snm/mc/records/20260817-103316-ce56f59.md) | 9-point MC subset of the 27-corner set | 200 | 18.3 – 22.9 | 54.9 – 68.6 | PINNED (9/9) | detected (9/9) |
   | Write margin | [`sim/write-margin/mc/records/20260817-104116-ce56f59.md`](../sim/write-margin/mc/records/20260817-104116-ce56f59.md) | 9-point MC subset of the 27-corner set | 200 | 74.2 – 133.2 | 222.6 – 399.6 | PINNED (9/9) | detected (9/9) |

   Each record: per-instance device mismatch only (`sw_stat_mismatch=1`,
   process/global variation still carried by the corner axis so no estimate
   pools across corners), an exact Clopper-Pearson empirical yield lower
   bound, Cpk/sigma-to-spec computed against the spec's own `> 0` limit, a
   determinism control (`sw_stat_mismatch=0` exactly reproduces the
   deterministic corner record for the same corner — ties the MC evidence to
   the existing 27-corner evidence rather than leaving it unanchored), and a
   negative control (an independently-seeded known-bad variant — 20x/12x/6x
   mismatch or a collapsed supply, per measurement — correctly detected as
   degraded at every one of the 27 measurement/corner pairs across the three
   campaigns). All three campaigns were built and run under issue #26's own
   Dependencies section, which explicitly proceeded on the conservative
   "yes, statistical" reading while this ruling was pending — this record
   ratifies that reading rather than overturning it, so no evidence already
   committed needs to be redone or invalidated by this decision either way.

   Each of the three records also states explicitly, in its own words: *"No
   `target_yield` is declared: `spec/sram.md` ratifies no yield target for
   these rows (that is exactly the open operator decision tracked as issue
   #20)."* That is the gap this record closes on the "statistical vs.
   deterministic" axis, while leaving the numeric-bar sub-question open (see
   below).

### Why the correction is safe

Nothing about the ratified 27-corner deterministic matrix, the Signoff
definition's `> 0` threshold, or any committed evidence changes. This record
only makes explicit — for the first time — a classification the spec's
Characterization section previously left unstated, matching the evidence
that already exists (PR #58) and the design-practice prior the issue itself
documented before any evidence was collected. This is not a case of relaxing
the ratified spec to make a result pass (`CLAUDE.md`): the amendment adds a
disclosure and an evidence-tier requirement, and every existing statistical
record already meets it.

## What this record changes

`spec/sram.md`'s Characterization section, "What must be measured, not just
asserted" subsection, gains one new paragraph (placed after the existing
bulleted list of the four measured quantities, before "### Corner set"):

> **Statistical treatment**: read SNM, hold SNM, and write margin are
> **statistical (mismatch-driven) rows** — device Vt/beta mismatch between
> the cross-coupled inverters and access transistors is the dominant
> real-silicon failure mode for both stability margins, and a corner matrix
> alone cannot exercise it (every device on a corner-matrix run moves
> together; real mismatch does not). Per klayout-tools'
> `docs/design-evidence-tiers.md` item 6, each of these three rows requires
> Monte Carlo (device-mismatch) evidence — a recorded seed, a sample count, a
> deterministic negative control, and a `klt yield` report — **combined
> with, never substituting for,** the deterministic corner-matrix evidence
> below. Read/write access time is not a matching/offset quantity in this
> macro's target spec and is not classified as statistical by this record.
> See `spec/statistical-treatment-decision.md` for the ratification record
> and `sim/README.md` § "Monte Carlo / yield evidence records" for the
> harness and record-tree convention this requirement is checked against.

## Deferred: `target_yield`

The three committed MC campaigns (PR #58) report Cpk, sigma-to-spec, and an
exact Clopper-Pearson empirical-yield lower bound at every corner, but none
declares a `target_yield` — because, before this record, `spec/sram.md`
ratified no numeric yield/confidence bar for a statistical row to be graded
against, and the harness correctly declines to invent one silently.

This record does **not** pick that number. The 200-sample campaigns already
in the repo report Cpk values from roughly 2.5 (read SNM's worst corner) to
over 130 (write margin's best corner) — several orders of magnitude apart —
and choosing a single `target_yield` (or a per-measurement set of them) that
this repo's sizing is actually held to requires either external
precedent (e.g. an industry PPM/DPM target for a canary macro of this scale)
or a deliberate risk-tolerance call this record has no evidence basis to
make unilaterally. Inventing a number here without that backing would be
exactly the kind of unilateral spec relaxation-or-tightening `CLAUDE.md`
reserves to a decision record built on evidence, not a placeholder.

**Follow-up**: #90 ratifies a `target_yield` (or explicit "no numeric target,
Cpk/sigma-to-spec only" decision) for the three statistical rows, informed by
the Cpk/sigma-to-spec ranges the existing 200-sample campaigns already
report. Until #90 lands, this record's requirement is satisfied by a
`klt yield` report with a recorded seed, sample count, determinism control,
and negative control per statistical row — exactly what PR #58 already
produced — graded on Cpk/sigma-to-spec/empirical-yield-lower-bound, not
against a numeric target.

## What this record does not change

- **The corner set, corner count, or Signoff definition.** The ratified
  27-corner process x temperature x voltage matrix
  (`spec/corner-count-correction.md`) and the `> 0` Signoff threshold for
  read SNM, hold SNM, and write margin are untouched.
- **Read/write access time's classification.** Access time is a delay
  measurement, not an offset/matching quantity; this record does not
  reclassify it as statistical, and does not rule on whether it should be
  addressed separately (out of scope here).
- **Any committed evidence.** Nothing under `sim/*/records/`,
  `sim/*/corners/`, or the Monte Carlo trees (`sim/*/mc/**`) is edited. PR
  #58's three MC records already satisfy the amendment's evidence
  requirement as stated; this record does not require them to be re-run.
- **A numeric `target_yield`.** Deliberately and visibly deferred above, not
  silently omitted.
- **The "Block kind" subsection.** Companion issue #19 (block-kind:
  analog/digital/mixed-signal classification) already landed independently as
  `spec/block-kind-decision.md`, ratifying this block's T1 kind as `analog`.
  It touches the same Characterization section but is an independent
  classification question; this record does not revisit or depend on it.

## Ratification mechanism

Per 2AMLogic/2am#357 (2026-08-19 operator ruling), canary spec/DR
ratification-via-PR is standing policy for this repository: a builder drafts
the ratification/decision record as a PR on the evidence already collected,
and the operator's approval of that PR is the ratification act itself — not
a separate, later sign-off. This record is drafted under that policy; it
reflects the evidence above for the operator to approve or reject, not a
ruling this agent is making unilaterally.

## Note on companion issue #19

At the time this record was drafted, companion issue #19 (block-kind ruling:
analog vs. digital vs. mixed-signal) was independently in flight; the
Curator's 2026-08-19 guidance on issue #20 asked this PR to stay scoped to
the statistical-treatment question only and let the operator decide whether
to combine the two rulings. #19 landed first, as `spec/block-kind-decision.md`
(merged via PR #89) — this record proceeds on the current `spec/sram.md`,
rebased on top of that merge, and does not revisit its "Block kind"
subsection.

## References

- `spec/sram.md` § "Characterization" — the section this record amends.
- `spec/corner-count-correction.md` — the prior decision record this one
  follows as a structural model (Status/Resolves/Amends/Question/Answer +
  Evidence/References) and whose corner-count/Signoff conclusions this
  record leaves untouched.
- `sim/read-snm/mc/records/20260817-102455-ce56f59.md`,
  `sim/hold-snm/mc/records/20260817-103316-ce56f59.md`,
  `sim/write-margin/mc/records/20260817-104116-ce56f59.md` — the three
  committed Monte Carlo / `klt yield` evidence records cited above (PR #58,
  merged 2026-08-17, closing #26).
- `sim/README.md` § "Monte Carlo / yield evidence records" — the harness and
  record-tree convention (`sim/lib/run_mc_campaign.py`, `sim/<experiment>/mc/`
  tree layout) this record's requirement is checked against.
- klayout-tools `docs/design-evidence-tiers.md` item 6 — the evidence-tier
  requirement this record's classification triggers.
- Issue #20 — the operator-decision issue this record resolves; #18
  (decomposition of #13's T1 re-read that filed #20); #26 (the MC/yield
  build-tracking issue PR #58 closed, cited as evidence above); #90 (the
  deferred `target_yield` follow-up filed by this record).
- `spec/block-kind-decision.md` — the companion #19 ruling (block kind:
  `analog`), merged via PR #89 ahead of this record. Independent
  classification question; this record's Characterization amendment sits
  alongside its "Block kind" subsection without depending on or revisiting
  it.
- `CLAUDE.md` — "Spec changes go through `spec/` with a decision record;
  agents do not relax the ratified spec to make results pass," and
  "Verification is the product: no claim without a testbench," both of
  which this record's amendment and evidence citation satisfy.
