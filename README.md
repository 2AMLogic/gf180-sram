# gf180-sram

An SRAM macro on the [gf180mcu](https://github.com/google/gf180mcu-pdk) open
PDK, built and verified by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools).

**Status: just opened, specification phase.** Nothing is designed yet.

**Built agent-native.** Every specification, decision record, testbench, and
line of documentation here is produced by AI agents working from a ratified
spec and an append-only evidence trail — not human-authored work that agents
merely assisted with. Verification is the product: every claim traces to a
recorded result. Where the agents hit friction with the open-source tooling —
most often [klayout-tools](https://github.com/2AMLogic/klayout-tools) — that
friction is filed as a public issue against the tool itself, so the fix
benefits everyone using gf180mcu, not just this repo.

## Why this block, stated honestly

This is the first **memory macro** in the program. Every sibling canary is a
flat analog or digital block, so array generation, macro-level LVS, abstract
and Liberty view generation, and the bitcell-to-array hierarchy are all tool
surface that has never been exercised here.

That is the reason it exists, and it is worth being plain that this block is
**not** selected for demand. [OpenRAM](https://openram.org) already generates
free SRAM macros for sky130, and gf180mcu itself ships a free, foundry-
hardened SRAM macro (`gf180mcu_fd_ip_sram`) outside of OpenRAM — see
[`spec/bitcell-decision.md`](spec/bitcell-decision.md) for the evidence.
OpenRAM does not currently generate gf180mcu SRAM macros (its gf180mcu
support is experimental ROM generation only). This repo is not trying to
out-compete either of those; it is trying to find out what breaks when the
tools are pointed at a memory array, and to fix it.

Where OpenRAM's output is a useful reference or a useful comparison, use it
and say so. Do not reimplement it.

## Target specification (DRAFT — engineering to ratify, see issue #2)

| Parameter | Target | Stretch |
|---|---|---|
| Organization | 1 kB (e.g. 256 × 32) | parameterized generator |
| Ports | 1RW | 1RW1R |
| Supply | 3.3 V | — |
| Bitcell | custom 6T (see [`spec/bitcell-decision.md`](spec/bitcell-decision.md)) | — |
| Deliverables | GDS, LEF abstract, Liberty timing | — |
| Signoff | DRC + LVS clean, functional across PVT | — |

The bitcell question is resolved: gf180mcu's 6T bitcell (`018SRAM_cell1`)
exists only embedded inside four fixed-depth foundry-hardened
`gf180mcu_fd_ip_sram` macros, not as a standalone, tileable primitive. This
repo draws a custom bitcell and array rather than integrating that hardened
macro, so the array-generation, hierarchy, and view-generation tooling this
block exists to exercise actually gets exercised. Full evidence and
rationale: [`spec/bitcell-decision.md`](spec/bitcell-decision.md). The
remaining spec parameters (organization, deliverables, characterization) are
tracked for ratification in issue #2.

Maturity ladder: bitcell question answered → spec ratified → bitcell
characterized → array assembled → DRC/LVS-clean → abstract and Liberty views
generated and checked → shuttle seat → measured silicon. **Current position:
bitcell question answered, spec ratification pending (#2).**

## Repo layout

```
spec/          ratified spec + decision records
design/        bitcell and periphery schematics
sim/           testbenches + PVT corner results (ngspice)
layout/        GDS + DRC/LVS reports (klayout-tools driven)
views/         generated LEF / Liberty abstracts
measurements/  silicon characterization (empty until tape-out)
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
