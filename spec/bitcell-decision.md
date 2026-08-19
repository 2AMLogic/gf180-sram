# Decision record: the bitcell question

**Status**: Decided, 2026-08-05
**Resolves**: #1 ("Answer the bitcell question before ratifying anything")
**Blocks unblocked by this record**: #2 ("Ratify the target spec")

> **Note (2026-08-19)**: this record's `gf180mcuC` citations below are
> verbatim, dated terminal transcripts of what was actually run on
> 2026-08-05 (`gf180mcuC` was used incidentally, as "any of the four"
> process variants, not as a deliberate pin) and are left unedited per this
> repo's evidence conventions. The variant this repo actually builds and
> cites against is now ratified as `gf180mcuD` —
> see [`pdk-variant-decision.md`](pdk-variant-decision.md), which also shows
> every artifact this record cites (`gf180mcu_fd_ip_sram`'s SPICE/GDS/LEF,
> `open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`) is
> byte-identical between the two variants, so nothing below is stale as a
> result.

## Question

Does gf180mcu ship a usable 6T SRAM bitcell, or must one be drawn? Per
`CLAUDE.md` § "First question, before the spec," this decides the entire
scope of this repo before anything in `spec/` can be ratified.

## Answer

**Yes, but only embedded inside four fixed-depth foundry-hardened macros —
not as a standalone, tileable primitive.**

### Evidence: the foundry bitcell exists, inside `gf180mcu_fd_ip_sram`

Verified 2026-08-05 against the PDK installed in this environment
(`klt pdk list`; `open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`,
cached under `~/.volare/gf180mcu{A,B,C,D}` — all four process variants carry
the same library):

```
$ klt pdk list
root: /Users/rwalters/.volare  (search root: ~/.volare)
  gf180mcuA  open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b
  gf180mcuB  open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b
  gf180mcuC  open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b
  gf180mcuD  open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b
  sky130A    open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b
  sky130B    open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b
```

gf180mcu ships a complete, Apache-2.0-licensed, foundry-hardened SRAM IP
library at `libs.ref/gf180mcu_fd_ip_sram/` (present under every
`~/.volare/gf180mcu{A,B,C,D}` root) with `gds/`, `lef/`, `lib/`, `cdl/`,
`spice/`, `verilog/`, `mag/`, and `maglef/` views, for **four fixed depths**,
all ×8-bit, single metal-stack option `m8wm1`:

- `gf180mcu_fd_ip_sram__sram64x8m8wm1`
- `gf180mcu_fd_ip_sram__sram128x8m8wm1`
- `gf180mcu_fd_ip_sram__sram256x8m8wm1`
- `gf180mcu_fd_ip_sram__sram512x8m8wm1`

The SPICE license header confirms provenance and license:

```
$ head -13 ~/.volare/gf180mcuC/libs.ref/gf180mcu_fd_ip_sram/spice/gf180mcu_fd_ip_sram__sram64x8m8wm1.spice
* Copyright 2022 GlobalFoundries PDK Authors
* Licensed under the Apache License, Version 2.0 (the "License");
...
```

**Pin list** (from the LEF, `sram64x8m8wm1`; direction from `PIN ... DIRECTION`
records): `A[5:0]` (address, `INPUT`), `CEN` (`INPUT`), `CLK` (`INPUT`),
`D[7:0]` (`INPUT`), `Q[7:0]` (`OUTPUT`), `GWEN` (`INPUT`), `WEN[7:0]`
(per-byte-lane write enable, `INPUT`), `VDD`/`VSS` (`INOUT`). This is a
single-port synchronous 1RW interface — one clock, one address, one
read/write data path.

**The bitcell itself**: inside the raw SPICE for every depth (e.g.
`gf180mcu_fd_ip_sram__sram64x8m8wm1.spice`), the array is built from an
internal 6T bitcell subcircuit `018SRAM_cell1` (8 devices per the netlist
comment `** N=8 EP=0 IP=0 FDC=0`), instantiated as a differential pair
`018SRAM_cell1_2x` and tiled across the array (`X0`/`X1` instances of
`018SRAM_cell1_2x` recur throughout the `.spice` netlist). The Magic layout
library ships **separate, per-macro copies of the standalone bitcell cell**
— `018SRAM_cell1_64x8m81.mag`, `018SRAM_cell1_128x8m81.mag`,
`018SRAM_cell1_256x8m81.mag`, `018SRAM_cell1_512x8m81.mag` (plus matching
`_2x`, `_dummy`, `_dummy_R`, and `_cutPC` variants per depth) under
`libs.ref/gf180mcu_fd_ip_sram/mag/` — confirming the bitcell is a real,
inspectable physical layout, not just a SPICE abstraction, but one that
exists as four depth-specific copies baked into each hardened macro's cell
library rather than a single reusable, independently-instantiable primitive
comparable to (e.g.) sky130's `sky130_fd_bd_sram__sram_sp_cell`.

**Characterization already exists**: each depth ships 15 `.lib` Liberty
corners (`sram64x8m8wm1` example: `{ff,ss,tt} x {n40C,025C,125C} x` matched
VDD points, e.g. `tt_025C_1v80`/`tt_025C_3v30`/`tt_025C_5v00`,
`ss_n40C_1v62`/`3v00`/`4v50`, `ff_125C_1v98`/`3v60`/`5v50`) — i.e. this IP
already carries PVT-corner timing/power characterization for its bitcell
array, which this repo's CLAUDE.md-mandated PVT-corner verification posture
can use as a comparison point.

**This answers the literal question**: yes, gf180mcu has a 6T-family
bitcell — but it is not exposed as a standalone, tileable standard cell or
PDK primitive. It exists only baked into these four pre-hardened,
fixed-depth compiler outputs. There is no separate bitcell GDS/LEF/SPICE
file outside those four macros that a from-scratch array build could
instantiate and tile the way OpenRAM tiles a standalone bitcell cell for
other PDKs.

### OpenRAM's actual gf180mcu support (corrects the original issue's premise)

The original issue's "What to establish" section asked to read OpenRAM's
gf180mcu approach "since it already generates macros for this PDK." That
premise is **false** as of this date. Verified directly against OpenRAM's
own documentation (`VLSIDA/OpenRAM`, `stable` branch,
`docs/source/basic_setup.md`, fetched live 2026-08-05):

```
## GF180 Setup

OpenRAM currently **does not** support gf180mcu for SRAM generation. However
ROM generation for gf180mcu is supported as an experimental feature.

To install gf180mcuD, you can run:

    cd $HOME/OpenRAM
    make gf180mcu-pdk
```

OpenRAM has no gf180mcu bitcell or SRAM array design to read as a reference
for this repo. Its gf180mcu support is limited to experimental ROM
generation, which is not a comparable memory-array design (no read/write
port design, no bitcell stability characterization). CLAUDE.md's adjacent
claim — "Free gf180mcu and sky130 SRAM macros already exist" — still holds,
just not via OpenRAM: the free gf180mcu macro is the foundry-hardened
`gf180mcu_fd_ip_sram` IP documented above (Apache-2.0 licensed), not an
OpenRAM output.

### Tool gap: `klt pdk cells` does not surface the SRAM IP library

Verified live in this environment, re-checked at implementation time
(`klt 0.2.0`, 2026-08-05):

```
$ klt pdk cells --pdk gf180mcuC
pdk: gf180mcuC

library                  devices  lib corners
-----------------------  -------  --------------------------------------------
gf180mcu_fd_sc_mcu7t5v0  -        1.8V @ gf180mcu_fd_sc_mcu7t5v0__tt_025C_1v80
gf180mcu_fd_sc_mcu9t5v0  -        1.8V @ gf180mcu_fd_sc_mcu9t5v0__tt_025C_1v80
```

`gf180mcu_fd_ip_sram` is fully present on disk (GDS/LEF/Liberty/CDL/SPICE/
Verilog/Magic, all four depths) but is not listed — `klt`'s PDK indexer only
enumerates the two decomposed standard-cell libraries
(`gf180mcu_fd_sc_mcu7t5v0`, `gf180mcu_fd_sc_mcu9t5v0`), not hard-macro IP
libraries. This reproduces the gap the Curator flagged during issue #1's
curation; it has **not** been fixed as of this date. Filed generically
(without design-specific detail, per CLAUDE.md's Friction Protocol) at
2AMLogic/klayout-tools — see that tracker for the issue link. Until it is
addressed, this repo must inspect `gf180mcu_fd_ip_sram` via direct
filesystem/`.lib`/`.lef`/`.spice` reads rather than `klt pdk cells`.

## Scope decision

Two options were on the table (see issue #1's "Reframed question"):

1. **Integrate the existing hardened macro(s)** — treat
   `gf180mcu_fd_ip_sram` as the deliverable, scoping this repo's work to
   verification/integration (LVS against the provided CDL, functional sim
   against the provided Liberty/Verilog, `klt` friction in *consuming* a
   hard macro).
2. **Draw a custom bitcell and array**, using the hardened IP's
   characterization (Liberty PVT corners, the `018SRAM_cell1` topology) as
   the reference/comparison point — the same posture CLAUDE.md calls for
   with OpenRAM's output, substituting the foundry hard macro as the
   reference since OpenRAM's gf180mcu SRAM output does not exist.

**Decision: Option 2 — draw a custom bitcell and array.**

### Rationale

CLAUDE.md states this repo's reason for existing directly: *"The macro is
the point. This is the program's first memory block, so array generation,
macro-level LVS, hierarchy handling, and LEF/Liberty view generation are all
tool surface nothing here has touched. Expect the tools to be weakest at the
array and abstract stages, and file what you find."* Option 1 (integrating
the pre-hardened macro) would produce a working verification exercise, but
it does not exercise bitcell-to-array hierarchy construction, array
generation, or abstract/Liberty *generation* (as opposed to consumption) —
the exact tool surface this block was chosen to test. `klt` would only ever
see a pre-built, pre-characterized macro, never drive the array assembly or
view-generation flow at all.

Option 2 is the materially larger job the original issue anticipated ("If
not, it additionally becomes a custom bitcell design with its own stability
characterization"), but it is the option consistent with why this block is
in the program: it forces `klt` and the rest of the open-source flow through
bitcell layout, array tiling, macro-level LVS, and LEF/Liberty
*generation*, with `gf180mcu_fd_ip_sram`'s Liberty corners and
`018SRAM_cell1` topology serving as the reference/comparison point CLAUDE.md
prescribes (same role OpenRAM's output would have played, had it existed for
this node).

This also matches CLAUDE.md's explicit stance that this repo "is not
competing with OpenRAM" or the foundry IP — `gf180mcu_fd_ip_sram` remains
the free, production-grade macro for anyone who just needs gf180mcu SRAM;
this repo's custom array is the canary exercising the design/verification
tooling, not a competing deliverable.

### Consequence for spec

- `spec/sram.md` (issue #2, once ratified) specifies a **custom-drawn 6T
  bitcell and array**, not integration of `gf180mcu_fd_ip_sram`.
- `gf180mcu_fd_ip_sram`'s Liberty corners (15 PVT points per depth) and CDL/
  SPICE netlists are the reference/comparison dataset for this repo's own
  characterization — cite it, do not reimplement its exact topology
  verbatim, and record where this repo's results agree or diverge.
- The custom bitcell's own DRC waiver / special-rule status is **not yet
  established** — gf180mcu's general design rules were not surveyed for
  bitcell-specific waivers as part of this decision (that survey is
  bitcell-design work, in scope for whichever issue does the actual
  bitcell layout, not this scoping decision).
- Port target: 1RW first (matching `gf180mcu_fd_ip_sram`'s interface),
  1RW1R as a stretch goal — consistent with the existing draft spec table
  in `README.md`.

## References

- `libs.ref/gf180mcu_fd_ip_sram/` under `~/.volare/gf180mcu{A,B,C,D}`
  (`open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`) — GDS,
  LEF, Liberty, CDL, SPICE, Verilog, Magic views for
  `sram{64,128,256,512}x8m8wm1`.
- OpenRAM, `VLSIDA/OpenRAM`, `stable` branch,
  `docs/source/basic_setup.md`, § "GF180 Setup" (fetched 2026-08-05):
  <https://github.com/VLSIDA/OpenRAM/blob/stable/docs/source/basic_setup.md>
- `klt 0.2.0` (`klayout-tools` @ `39bdbc4` per issue #1 curation; re-verified
  against the currently installed `klt 0.2.0` on 2026-08-05) —
  `klt pdk list`, `klt pdk cells --pdk gf180mcuC`.
- gf180mcu-pdk (Google/GlobalFoundries open PDK), Apache License 2.0 header
  in `gf180mcu_fd_ip_sram__sram64x8m8wm1.spice`.
