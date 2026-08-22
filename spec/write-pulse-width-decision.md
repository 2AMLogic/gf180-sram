# Decision record: no independent write timing target — write margin is measured against a fixed, stated 2 ns pulse width

**Status**: Proposed for ratification via PR approval (2AMLogic/2am#357 standing
policy — the operator's PR approval is the ratification act; see
"Ratification mechanism" below)
**Resolves**: #7 ("Spec gap: the write-margin criterion cites a timing target
that does not exist, and signoff as ratified cannot reach T1")
**Amends**: `spec/sram.md` § "Characterization" → "What must be measured, not
just asserted" (write-margin row only — see "What this record changes")

## Question

`spec/sram.md`'s write-margin row defines write margin as:

> the minimum bit-line / write-driver drive ... that successfully flips the
> cell's stored value within the write pulse width **the macro's timing
> target assumes**.

No ratified document anywhere in `spec/` defines what "the macro's timing
target" is — there is no numeric write-pulse-width, cycle-time, or
clock-period target anywhere in `spec/sram.md` or any of the seven decision
records that predate this one. `sim/write-margin/testbench/tb_write_margin.spice`
already presets and trials the cell over a fixed 2 ns window (`VWL`/`VBL`/`VBLB`
all pivot at `4n`/`6n` for the trial phase) with no citation back to a
ratified number. This record resolves what that phrase means: either (a)
ratify a numeric write-pulse-width/timing target, grounded in a stated basis,
or (b) ratify that write margin is measured against a fixed, stated pulse
width with no independent timing target.

## Answer

**(b) — no independent write timing target is ratified.** Write margin is
measured against a fixed, stated **2 ns** write-pulse width. `spec/sram.md`'s
write-margin row is amended to describe that fixed window directly instead of
referencing an undefined "macro's timing target."

This mirrors the precedent `spec/target-yield-decision.md` already set for
this repo (formalizing an evidence-grounded status quo as "no number," not a
placeholder) — the "no numeric target" option #7 itself names as branch (b).

### Evidence

1. **This macro has no ratified clock period, cycle time, or frequency
   target to derive a write-pulse width from.** `spec/sram.md`'s own
   "Ports" section ratifies a 1RW synchronous interface (one clock, one
   address bus) but states no target frequency or cycle time; its
   "Deliverables" section commits this repo to *generating* Liberty timing
   tables from *measured* access time, not to hitting a target period. A
   repo-wide search of every ratified `spec/*.md` document (`sram.md`,
   `bitcell-decision.md`, `block-kind-decision.md`, `corner-count-
   correction.md`, `kb-scale-integration.md`, `pdk-variant-decision.md`,
   `statistical-treatment-decision.md`, `target-yield-decision.md`) for
   "cycle", "frequency", "MHz", or "clock period" returns zero matches. The
   phrase "the macro's timing target" in the write-margin row is therefore
   not an under-cited reference to something ratified elsewhere — nothing
   exists for it to point to. Inventing a clock-period target now, solely to
   backfill this one row, would be exactly the "invent one here without that
   backing" move `spec/target-yield-decision.md` already flagged as out of
   bounds for a different row's un-ratified number, and CLAUDE.md's "agents
   do not relax the ratified spec to make results pass" cuts the same way
   against inventing a number to make the phrase resolve to something.

2. **The write-margin testbench's 2 ns window is already generously wider
   than every measured write access time at every corner, so it is not an
   arbitrary or unmeasured value — it has margin against the one number this
   repo has actually measured.** `sim/access-time/records/20260817-012005-4448966.md`
   reports write access time (WL assertion to internal storage node `Q`
   crossing VDD/2) at all 27 corners; the slowest corner (`ss_125c_2.97v`,
   the worst process/temperature/voltage combination for switching speed) is
   `8.49307E-11 s` ≈ 85 ps. The write-margin testbench's trial window
   (`4n` to `6n`, i.e. 2 ns / 2000 ps) is ~23x that worst-case measured
   access time — comfortably wide enough that the write-margin trial is not
   silently truncating a real write attempt at any ratified corner. This is
   cited as corroborating evidence that the existing 2 ns choice is
   reasonable, not as a derivation of 2 ns itself — the two numbers were
   produced independently (the testbench predates and was not tuned against
   the access-time record), and this record does not claim 2 ns was
   *derived* from the 85 ps figure.

3. **A numeric target picked now would carry the same defect
   `spec/target-yield-decision.md` already diagnosed for a different row: no
   principled way to pick one value from the evidence in hand.** The write
   margin testbench's own header states its bisection search resolves the
   write-trip voltage to ~0.2 mV precision specifically because a coarser
   grid (the original 41-point linear scan) swamped the mismatch effect the
   Monte Carlo campaign needed to measure — i.e., this repo has already
   learned, in this same experiment, that an unmotivated round number
   quietly degrades a downstream measurement. Picking a clock-period target
   now — with no target application, no ratified interface timing beyond
   "one clock, one address bus," and no downstream consumer that needs one
   yet — would carry exactly that risk with no offsetting benefit: nothing
   in the ratified spec depends on write margin being measured against any
   particular pulse width other than "a stated, fixed one, wide enough to
   observe a completed write."

4. **The write-margin testbench's own header already documents the fixed
   window explicitly**, and describes it as this testbench's own choice
   (`"the write pulse width"` in the comment block matches the phrasing this
   record ratifies) rather than as a value derived from a spec-level target.
   Ratifying (b) makes the spec's prose match what the testbench, and every
   committed write-margin record produced against it, has always actually
   measured.

### Why no independent timing target is ratified

The honest failure mode this record avoids is inventing a clock-period or
cycle-time number with no ratified interface timing to hang it on, purely to
give the write-margin row's "timing target" phrase something to resolve to.
That would not be a measurement — it would be a number selected after the
fact to make an existing phrase parse, which is the same anti-pattern
`spec/target-yield-decision.md` rejected for `target_yield` (picking a number
with "no principled way ... from this evidence alone"). The fixed 2 ns
pulse width is not that: it is the value every committed write-margin record
already measures against, it already has ~23x margin over the worst measured
write access time, and stating it plainly removes the dangling reference
without asserting a timing commitment this repo has not made anywhere else.

## What this record changes

`spec/sram.md`'s Characterization section, "What must be measured, not just
asserted" subsection, the write-margin bullet currently reads:

> - **Write margin** — the minimum bit-line / write-driver drive (e.g. write
>   trip voltage, or the N-curve-based write margin) that successfully flips
>   the cell's stored value within the write pulse width the macro's timing
>   target assumes. Must show successful flip with positive margin at every
>   corner.

That bullet is replaced with:

> - **Write margin** — the minimum bit-line / write-driver drive (e.g. write
>   trip voltage, or the N-curve-based write margin) that successfully flips
>   the cell's stored value within a fixed **2 ns** write-pulse width (no
>   independent macro timing target is ratified; see
>   `spec/write-pulse-width-decision.md`). Must show successful flip with
>   positive margin at every corner.

No other row, corner, axis, or Signoff threshold in `spec/sram.md` changes.

## What this record does not change

- **The write-margin testbench, or any committed write-margin evidence.**
  `sim/write-margin/testbench/tb_write_margin.spice`'s 2 ns trial window is
  unchanged — it is exactly the value this record ratifies as the fixed
  pulse width, so **no re-run is required**. All three existing
  `sim/write-margin/records/*.md` entries (`20260817-011733-4448966.md`,
  `20260817-030501-7cdc2da.md`, `20260817-105029-ce56f59.md`) and the
  committed Monte Carlo campaign
  (`sim/write-margin/mc/records/20260817-104116-ce56f59.md`) remain valid
  evidence exactly as recorded — none of them measured against an
  undefined target; all of them measured against the same fixed 2 ns window
  this record now states explicitly.
- **The Signoff `> 0` threshold**, the 27-corner matrix, or the statistical-
  treatment classification for write margin — all untouched, per
  `spec/corner-count-correction.md` and `spec/statistical-treatment-
  decision.md`.
- **Read SNM, hold SNM, or read/write access time.** None of those rows'
  text changes; access time stays a *measured* quantity with no target, per
  `spec/sram.md`'s existing Deliverables framing.
- **The door to a future numeric timing target.** This record does not
  forbid a later decision record from ratifying a clock-period/cycle-time
  target once this repo actually needs one (e.g. once a sense amp, write
  driver, or full synchronous interface is designed and Liberty timing needs
  a target to be checked against, not merely reported). This record only
  declines to invent one today, on today's evidence, to answer a dangling
  phrase.

## Ratification mechanism

Per 2AMLogic/2am#357 (2026-08-19 operator ruling), canary spec/DR
ratification-via-PR is standing policy for this repository: a builder drafts
the ratification/decision record as a PR on the evidence already collected,
and the operator's approval of that PR is the ratification act itself — not
a separate, later sign-off. This record is drafted under that policy; it
reflects the evidence above for the operator to approve or reject, not a
ruling this agent is making unilaterally.

## References

- `spec/sram.md` § "Characterization" — the write-margin row this record
  amends.
- `spec/target-yield-decision.md` — the precedent this record follows for
  ratifying "no number" as a considered, evidence-backed answer rather than
  a default.
- `sim/write-margin/testbench/tb_write_margin.spice` — the testbench whose
  existing 2 ns trial window (`4n`–`6n`) this record ratifies as the ratified
  fixed pulse width; unchanged by this record.
- `sim/write-margin/records/20260817-011733-4448966.md`,
  `sim/write-margin/records/20260817-030501-7cdc2da.md`,
  `sim/write-margin/records/20260817-105029-ce56f59.md`,
  `sim/write-margin/mc/records/20260817-104116-ce56f59.md` — the four
  committed write-margin evidence records (three deterministic corner
  sweeps plus the Monte Carlo/yield campaign) this record confirms remain
  valid without a re-run.
- `sim/access-time/records/20260817-012005-4448966.md` — the committed
  write-access-time corner sweep cited above (worst case 85 ps at
  `ss_125c_2.97v`) as corroborating evidence that the existing 2 ns window
  has ample margin over the one write-speed quantity this repo has actually
  measured.
- Issue #7 — the operator-decision issue this record resolves.
- `CLAUDE.md` — "Spec changes go through `spec/` with a decision record;
  agents do not relax the ratified spec to make results pass" (this record
  declines to *invent* a number to make a phrase resolve, for the same
  reason agents must not invent a number to make a failing result pass).
