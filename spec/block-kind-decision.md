# Decision record: this block's T1 evidence-tier kind is `analog`

**Status**: Decided, 2026-08-19
**Resolves**: #19 ("Operator decision: ratify this block's T1 evidence-tier
kind (analog/digital/mixed-signal) in `spec/sram.md`")
**Amends**: `spec/sram.md` § "Characterization" (additive pointer only — see
"What this record does not change")

## Question

`klayout-tools/docs/design-evidence-tiers.md` § "Block kind" requires every
T1 claim to state the block's kind — exactly one of `analog`, `digital`, or
`mixed-signal` — before checklist items 1 (design sources), 2 (layout), 5
(corner verification), 6 (statistical/MC evidence), and 7 (post-layout
verification) can be graded against the correct column (items 3, 4, 9, 10
are kind-independent). `spec/sram.md`, ratified 2026-08-05, never states a
kind. Per `CLAUDE.md`, agents do not add spec content unilaterally, so the
declaration must land as a ratified decision record, not a silent edit.

## Answer

**`analog`.**

This ruling is scoped to **everything currently ratified in this repo** —
the custom bitcell/array (`spec/bitcell-decision.md`) and the PVT
characterization approach (`spec/sram.md` § "Characterization"). It does
**not** pre-commit any future periphery (decoders, control logic, or other
digital support blocks not yet designed) to a kind. If a future periphery
block is built with an RTL/digital-synthesis flow, that block's own kind is
a separate declaration made when that work is scoped — at which point this
repo would become `mixed-signal` overall, with the partition boundary
stated explicitly at that time (per `design-evidence-tiers.md`'s
requirement that a mixed-signal claim name which nets/pins/cells belong to
which side). No such partition exists today because no digital-synthesized
sub-block exists today.

### Evidence

Two independent lines of evidence in what is actually ratified today, both
pointing to `analog`:

1. **`spec/bitcell-decision.md`** (Status: Decided, 2026-08-05) ratifies
   Option 2: this repo draws a **custom bitcell and array** from scratch —
   full-custom transistor-level layout (GDS) with the foundry
   `gf180mcu_fd_ip_sram` macro's Liberty corners and `018SRAM_cell1`
   topology used only as a reference/comparison dataset, not integrated or
   synthesized. Nothing in that decision involves RTL or a digital
   synthesis/place-and-route flow — the deliverable is hand-drawn silicon.

2. **`spec/sram.md`** § "Characterization" (Status: Ratified, 2026-08-05)
   ratifies the verification approach: read/hold static noise margin
   (butterfly-curve measurement), write margin, and access time, all
   measured via `CLAUDE.md`'s xschem + ngspice schematic-capture-and-SPICE
   flow across a 27-point PVT corner matrix
   (`spec/corner-count-correction.md`). This is exactly
   `design-evidence-tiers.md`'s *Analog* column for items 1 (schematic
   sources + derived netlist) and 5 (PVT corner sweeps) — the *Digital*
   column's RTL-plus-synthesized-netlist and standard P&R-corner-STA
   evidence has no counterpart anywhere in the ratified spec. Item 6
   (statistical/Monte Carlo evidence) is likewise the *Analog* column's
   device-mismatch MC treatment, not a digital yield/timing-margin
   treatment — consistent with the SNM/write-margin measurements above.

Both records describe full-custom, transistor-level work with no RTL or
digital-synthesis flow anywhere in scope. Under `design-evidence-tiers.md`'s
"Block kind" definition, that is squarely `analog`: "Analog blocks satisfy
the Analog column only." There is no ratified line in either record that
reads as `digital` or that names a `mixed-signal` partition boundary.

## What this record does not change

- **Every existing ratified value in `spec/sram.md`.** Organization, Ports,
  Deliverables, and the full "Characterization" section (the measurement
  definitions, the 27-corner set, and the Signoff definition) are untouched.
  `git diff` on `spec/sram.md` for this change shows only the new pointer
  line added below, nothing removed or reworded.
- **`spec/bitcell-decision.md`.** Cited as evidence, not amended.
- **Any future periphery's kind.** As stated in "Answer" above, this record
  covers only what is ratified today; it makes no claim about decoders,
  control logic, or any other block not yet designed.

## Consequence for tooling and docs

`spec/sram.md` gains a single additive "Block kind" line under
§ "Characterization" pointing here, so a future T1 evidence claim for this
macro can be graded against `design-evidence-tiers.md`'s Analog column
without re-deriving the kind each time. `spec/README.md`'s index gains one
bullet for this record, matching the existing four-bullet format.

## References

- `spec/sram.md` § "Characterization" → "Block kind" — the new pointer to
  this record.
- `spec/bitcell-decision.md` — resolves #1, ratifies the custom
  bitcell/array decision cited as evidence above.
- `spec/corner-count-correction.md` — resolves #53, the 27-point PVT corner
  set cited as evidence above (label-only correction, unaffected by this
  record).
- `klayout-tools/docs/design-evidence-tiers.md` § "Block kind" — the
  requirement this record satisfies, and the source of the `analog` /
  `digital` / `mixed-signal` definitions quoted in "Answer" above.
- `CLAUDE.md` — "Spec changes go through `spec/` with a decision record;
  agents do not relax the ratified spec to make results pass," the rule
  this record follows; and 2AMLogic/2am#357, the standing policy under
  which a builder drafts this record as a PR and the operator's PR approval
  is the ratification act.
