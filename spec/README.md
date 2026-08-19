# spec

Ratified spec and decision records for this block.

- [`bitcell-decision.md`](bitcell-decision.md) — resolves #1: gf180mcu ships
  a foundry 6T bitcell (`018SRAM_cell1`), but only embedded in four
  fixed-depth `gf180mcu_fd_ip_sram` hardened macros, not as a standalone
  primitive. Decides this repo draws a custom bitcell/array rather than
  integrating the hardened macro, with rationale.
- [`sram.md`](sram.md) — resolves #2: ratifies the target macro spec
  (organization, ports, deliverables, characterization) that was left as a
  DRAFT table in `README.md`, building on the bitcell decision above.
- [`corner-count-correction.md`](corner-count-correction.md) — resolves #53:
  corrects `sram.md`'s "Corner set" arithmetic (`3 × 3 × 3` is 27, not 9).
  A label-only correction — the ratified corner set, the Signoff definition,
  and every committed record are unchanged.
- [`kb-scale-integration.md`](kb-scale-integration.md) — resolves #73:
  informational (not a change to the ratified spec). States the PDK's
  fixed-macro ceiling (`512×8` = 0.5 KB, measured from the shipped LEF),
  what this repo's own custom macro does and does not offer above it, and a
  KB-scale integrator's path (tiled foundry macros vs. DFFRAM vs. OpenRAM,
  with area/timing evidence tiers labelled and the mux/bank-select cost
  flagged as unmeasured). Also notes the open kit's lack of dense NVM.
- [`block-kind-decision.md`](block-kind-decision.md) — resolves #19:
  ratifies this block's T1 evidence-tier kind (per
  `klayout-tools/docs/design-evidence-tiers.md`'s "Block kind" requirement)
  as `analog`, scoped to everything currently ratified (the custom
  bitcell/array and the xschem + ngspice PVT characterization approach); does
  not pre-commit any future periphery to a kind. `sram.md` gains a pointer
  to this record; no existing ratified value changes.
- [`statistical-treatment-decision.md`](statistical-treatment-decision.md) —
  resolves #20: ratifies read SNM, hold SNM, and write margin as statistical
  (mismatch-driven) spec rows requiring Monte Carlo evidence per
  klayout-tools' `docs/design-evidence-tiers.md` item 6, combined with —
  never replacing — the ratified 27-corner deterministic matrix. Additive
  only to `sram.md`'s Characterization section. Cites the three Monte Carlo
  / `klt yield` records PR #58 already committed (`sim/read-snm/mc/`,
  `sim/hold-snm/mc/`, `sim/write-margin/mc/`) as satisfying evidence, and
  explicitly defers ratifying a numeric `target_yield` bar as a named
  follow-up.
