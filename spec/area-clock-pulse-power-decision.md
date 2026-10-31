# Decision record: area, minimum clock pulse and power are recorded rows with no pass threshold

**Status**: Proposed for ratification via PR approval (2AMLogic/2am#357 standing
policy — the operator's PR approval is the ratification act; see
"Ratification mechanism" below)
**Resolves**: #293 ("spec: no area, min-clock-pulse or power rows in spec/sram.md")
**Amends**: `spec/sram.md` § "Characterization" (additive — a new "Recorded
quantities" subsection; no existing row changes)

## Question

`spec/sram.md` ratifies read SNM, hold SNM, write margin and access time across
27 corners, but carries no row for **area** (macro, per bit, bitcell),
**minimum clock pulse**, or **power** (leakage, dynamic per access). Hold SNM
is the only retention statement. Without a stated form, any such figure that
later appears (LEF/Liberty views, comparisons against `gf180mcu_fd_ip_sram` or
OpenRAM) has no agreed status: a reader cannot tell a target from a
measurement from an omission. The sibling port `sg13g2-sram` raised the same
omission (2AMLogic/sg13g2-sram#74, as reported in #293; that tracker was not
read for this record).

## Answer

**All five quantities are carried in `spec/sram.md` as *recorded, no pass
threshold*.** Each is stated with a source, or explicitly as "not yet
measured". None is a Signoff criterion and no numeric target is ratified.

| Quantity | Form | Status as of `68654da` (2026-10-29) |
|---|---|---|
| Bitcell area | recorded, no pass threshold | 4.46 × 5.40 µm = **24.08 µm²** (`klt stats` bbox of `layout/bitcell/sram_bitcell_6t.gds`; `layout/README.md` § "Area" reports 24.1 µm²) |
| Per-bit area | recorded, no pass threshold | **24.16 µm²/bit**, storage-array core only (143.15 × 1382.4 µm = 197,890.6 µm² over 8192 bits) |
| Macro area | recorded, no pass threshold | **not yet measured** for the full 1RW macro. The only LEF, `views/sram_256x32_array.lef` (`SIZE 143.1500 BY 1382.4000`, ≈ 0.198 mm²), is the storage-array core with no periphery (322 pins, not the 37-pin macro interface; `views/README.md` § "Scope"), so it is not the macro's area |
| Minimum clock pulse | recorded, no pass threshold | **not yet measured** — shortest `CLK` high/low width at which the macro still completes a correct read/write, per corner. No testbench exists |
| Power (leakage; dynamic per access) | recorded, no pass threshold | **not yet measured** — per corner. No power testbench exists |

Area figures above are arithmetic on the cited bbox/`SIZE` values (not
re-derived from the GDS by this record). Per-bit area includes no periphery,
so it is a lower bound on any macro-level area/bit.

### Evidence and reasoning

1. **A layout and LEF exist, so array-core area is derivable today; the
   macro's is not.** Quoting the core figure as "the macro area" would
   mislead, since `periphery-architecture.md` places decode, column mux, sense
   amps and write drivers around it. The record therefore separates the three
   area rows and marks macro area unmeasured instead of guessing.
2. **No measured basis exists for a numeric threshold.** There is no
   minimum-pulse or power testbench in `sim/`, and no ratified clock period
   or interface timing (`spec/write-pulse-width-decision.md`). Ratifying a
   number now would invent a target, which CLAUDE.md forbids ("agents do not
   relax the ratified spec" cuts equally against inventing a bar). This is the
   same reasoning as `spec/write-pulse-width-decision.md` and
   `spec/target-yield-decision.md`.
3. **Leaving the omission unrecorded is the defect being fixed.** A stated
   "recorded, no pass threshold" form lets later figures be attached to rows
   with a known status.
4. **Comparison, not targets.** Foundry rows in
   `ratification/market-key/comps/sram.md` (e.g. `sram256x8m8wm1`, 71.9 µm²/bit,
   whole macro incl. periphery) and OpenRAM output (per CLAUDE.md) are
   references to cite. They are not copied in as thresholds, and the
   array-core-only per-bit figure above is not like-for-like with them.

## What this record changes

`spec/sram.md` gains a "Recorded quantities (no pass threshold)" subsection
under "Characterization" listing the five rows above, and a References entry
for this record.

## What this record does not change

- The Signoff definition, the 27-corner set, or any existing row (read SNM,
  hold SNM, write margin, access time) — untouched.
- Any `sim/` evidence; no simulation was run or needed.
- Any numeric area, clock-pulse or power target — none is ratified. A later
  record may ratify one once a measured basis exists.
- The sibling repository.

Out of scope: writing minimum-pulse or power testbenches (to be filed
separately if wanted).

## Ratification mechanism

Per 2AMLogic/2am#357 (2026-08-19 operator ruling), ratification-via-PR is
standing policy for this repository: the operator's approval of the PR is the
ratification act. This record is proposed, and does not claim ratification
itself.

## References

- `spec/sram.md` § "Characterization" — amended additively.
- `spec/write-pulse-width-decision.md`, `spec/target-yield-decision.md` — the
  "recorded, no number" precedent followed here.
- `views/sram_256x32_array.lef`, `layout/bitcell/sram_bitcell_6t.gds`,
  `layout/README.md` § "Area" and § "Tool / PDK versions" — area sources
  (both files last changed at `2408c71`; figures read at `68654da`).
- `spec/periphery-architecture.md` — the periphery absent from the LEF core.
- `ratification/market-key/comps/sram.md` — foundry comparison rows.
