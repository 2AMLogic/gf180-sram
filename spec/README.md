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
