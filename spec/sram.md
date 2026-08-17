# Target spec: gf180mcu SRAM macro

**Status**: Ratified, 2026-08-05
**Resolves**: #2 ("Ratify the target spec")
**Depends on**: `spec/bitcell-decision.md` (resolves #1 — draw a custom
bitcell/array rather than integrate `gf180mcu_fd_ip_sram`)

This record ratifies the four items `README.md`'s DRAFT spec table left open
(Organization, Ports, Deliverables, Characterization) into a fixed target.
Per `CLAUDE.md`, this is the spec agents build and verify against — it is
not relaxed to make results pass; a change to any row here requires a new
decision record, not an edit against a failing result.

## Organization: 1 kB, 256 × 32, fixed instance (not a generator)

**Target: 1 kB organized as 256 words × 32 bits, a single fixed instance.**
A parameterized generator is an explicit stretch goal, not the initial
target.

This was the one open question `spec/bitcell-decision.md` did not settle —
its "Consequence for spec" section notes Option 2 (custom array) removes the
foundry IP's fixed-depth constraint (64/128/256/512 × 8) but does not itself
pick fixed-instance-first vs. generator-first. Deciding it here:

- The issue that opened this repo's scope ("What needs deciding") already
  frames a fixed instance as "the smaller first step," and `CLAUDE.md`'s
  framing of this block ("array generation, macro-level LVS, hierarchy
  handling, and LEF/Liberty view generation are all tool surface nothing
  here has touched") is best exercised end-to-end once, on one concrete
  array, before generalizing to a parameter sweep.
- A generator adds a second, orthogonal kind of tool surface (parametric
  array assembly across bit widths/depths) on top of the bitcell-to-array
  hierarchy work `spec/bitcell-decision.md` already committed this repo to.
  Stacking both at once risks neither getting finished; sequencing
  fixed-instance-first lets the bitcell/array/LVS/view-generation flow reach
  a signed-off macro before that flow itself needs to be made parametric.
  `OpenRAM` is the reference precedent for what a generator looks like once
  this repo is ready to build one — no need to re-derive that design from
  scratch, per `CLAUDE.md`'s "use OpenRAM's output as a reference... do not
  reimplement it."
- 256 × 32 is not constrained by (and is not required to match) any of
  `gf180mcu_fd_ip_sram`'s four fixed depths (64/128/256/512 × 8) — this
  repo's array is custom-drawn, so its word/bit split is a free choice, kept
  at the round 1 kB `README.md` already proposed.

**Stretch**: generalize the fixed 256 × 32 instance into a parameterized
generator (word count and/or bit width as parameters), once the fixed
instance is DRC/LVS-clean and characterized.

## Ports: 1RW first, 1RW1R as a stretch goal

**Target: single-port synchronous read/write (1RW)** — one clock, one
address bus, one read/write data path, matching `gf180mcu_fd_ip_sram`'s pin
interface (`A[n]`, `CEN`, `CLK`, `D[n]`, `Q[n]`, `GWEN`, `WEN`, documented in
`spec/bitcell-decision.md`) as the comparison point.

**Stretch: 1RW1R** (add an independent read-only port), matching this
repo's original draft table.

This item was already corroborated during `spec/bitcell-decision.md`'s own
scope decision ("Port target: 1RW first ..., 1RW1R as a stretch goal —
consistent with the existing draft spec table in `README.md`") and is
carried forward here unchanged, now as the ratified target rather than a
decision-record aside.

## Deliverables: GDS, LEF abstract, Liberty timing

**Target: all three views, generated (not merely consumed) by this repo's
own flow** — full-custom GDS for the bitcell and array, a LEF abstract for
integration, and Liberty timing characterization across the corners defined
below.

This was already confirmed in scope by #1's curation pass (the foundry IP
ships this exact view set — GDS, LEF, Liberty, plus CDL/Verilog this repo
does not need to reproduce) and is unchanged by the bitcell decision. What
the bitcell decision *does* change is that this repo must **generate** these
views itself rather than consume the foundry IP's — LEF/Liberty generation
for a from-scratch array is exactly the weak tool surface `CLAUDE.md`
flags ("Expect the tools to be weakest at the array and abstract stages,
and file what you find"), so it stays the point of this deliverable, not an
incidental byproduct.

Out of scope for this record (may be added later without re-ratifying this
spec, since they don't change the macro's target parameters): CDL and
Verilog views, which the foundry IP also ships but which are not called out
in the original DRAFT table or this issue's AC.

## Characterization: what "functional across PVT" means for this macro

This is the item `spec/bitcell-decision.md` explicitly left open ("The
custom bitcell's own DRC waiver/special-rule status is not yet
established... in scope for whichever issue does the actual bitcell
layout, not this scoping decision") and that had no prior definition
anywhere in this repo. Ratifying it here for the first time.

### What must be measured, not just asserted

"Functional across PVT" for this macro means all of the following hold, at
every corner in the corner set below, on the fixed 256 × 32 array (or a
representative column/bitcell testbench where full-array simulation is
impractical) — each as a **recorded margin**, not a bare pass/fail:

- **Read static noise margin (read SNM)** — the minimum butterfly-curve
  square side length for the bitcell during a read access (bit lines
  precharged, wordline asserted, cell holding both `0` and `1`). Must be
  `> 0` at every corner; the margin value itself is the recorded result, not
  just whether it cleared zero.
- **Hold static noise margin (hold SNM)** — the same butterfly-curve
  measurement with the cell in standby (wordline deasserted, bit lines
  floating/precharged, no access in progress). This is the retention
  margin; it is measured separately from read SNM because a 6T cell's
  hold and read stability differ (access transistors loading the storage
  nodes during read is exactly what read SNM is testing for).
- **Write margin** — the minimum bit-line / write-driver drive (e.g. write
  trip voltage, or the N-curve-based write margin) that successfully flips
  the cell's stored value within the write pulse width the macro's timing
  target assumes. Must show successful flip with positive margin at every
  corner.
- **Read/write access time** — the delay from clock edge (or address/enable
  valid, for the applicable timing arc) to valid `Q` output or completed
  write, at each corner. This is the data that populates the Liberty timing
  tables under "Deliverables" above — Liberty views are not shippable
  without a corner-by-corner timing dataset behind them.

A corner "passes" only when read SNM, hold SNM, and write margin are all
strictly positive and the measured access time is recorded; a corner where
any of those degrades to zero or is not measured is not a signed-off corner,
regardless of whether a testbench merely completed without an error.

### Corner set

**Process** × **temperature** × **voltage**, all combinations:

| Axis | Points |
|---|---|
| Process | `ff`, `tt`, `ss` |
| Temperature | `-40 C`, `25 C`, `125 C` |
| Voltage | `2.97 V`, `3.30 V`, `3.63 V` (±10% of this macro's single 3.3 V supply target) |

3 × 3 × 3 = **27 corners**, all reported per `sim/`'s append-only evidence
convention (`CLAUDE.md`: "`sim/` results are append-only evidence").

> The three axes above are fully crossed ("all combinations"), so the corner
> count is their product, 27. This sentence read `= **9 corners**` from
> ratification until 2026-08-17; that was an arithmetic slip in the prose,
> corrected per `spec/corner-count-correction.md`. The axes, the corner set
> itself, and the Signoff definition below are unchanged, and every sweep
> this repo has ever run already executed all 27 points.

This is deliberately narrower than `gf180mcu_fd_ip_sram`'s 15-corner-per-depth
Liberty characterization documented in `spec/bitcell-decision.md`
(`{ff,ss,tt} x {n40C,025C,125C}` against **three separate voltage rails**
— 1.8 V, 3.3 V, and 5 V domains — because that IP supports multiple I/O
voltage options). This macro's target spec has a single 3.3 V supply, as
ratified in the corner-set table above, so only one voltage axis applies; a
±10% sweep around that single rail is the comparable corner density for this
repo's narrower voltage scope, not a shortfall against the foundry IP's
count. The foundry IP's per-corner Liberty data remains the
reference/comparison dataset this repo's own results are checked against, per
`spec/bitcell-decision.md`'s "Consequence for spec."

### Signoff definition

Combining with the existing DRAFT table's Signoff row: this macro is
**functional across PVT** once DRC and LVS are clean on the full array, and
every one of the 27 corners above has a recorded, strictly-positive read SNM,
hold SNM, and write margin, plus a recorded access time feeding the Liberty
views. Any corner that cannot be closed is recorded as an open result in
`sim/`, not silently dropped from the corner set — this spec is not relaxed
to make a failing corner disappear.

## References

- `spec/bitcell-decision.md` — resolves #1, decides Option 2 (custom
  bitcell/array), and is the source for the Ports and Deliverables
  conclusions ratified above.
- `spec/corner-count-correction.md` — resolves #53, the decision record for
  the "Corner set" corner-count correction (9 → 27). Label-only: it changes
  no axis, no corner, and no Signoff threshold.
- `README.md`, "Target specification (DRAFT...)" section — the pre-existing
  draft table this record ratifies and supersedes.
- `libs.ref/gf180mcu_fd_ip_sram/` under `~/.volare/gf180mcu{A,B,C,D}`
  (`open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, per
  `spec/bitcell-decision.md`) — the foundry IP's pin list, view set, and
  15-corner Liberty characterization used above as comparison points, not
  copied targets.
