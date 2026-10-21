# layout

Layout for this repo is driven by
[klayout-tools](https://github.com/2AMLogic/klayout-tools) (`klt`), per
`CLAUDE.md`. This directory is T1 checklist item 2 ("Layout" —
`klayout-tools/docs/design-evidence-tiers.md`'s *Analog* column: "committed
GDS/OASIS, reproducibly generated or with documented provenance").

## Status (2026-08-16): real, device-level layout of the committed design

What is committed here is the **transistor-level 6T bitcell layout of
`design/bitcell_6t.sch` and the 256 x 32 array built from it** — not a
placeholder. The earlier placeholder box (PR #36, drawn before `design/`
existed) is gone.

| | |
|---|---|
| Bitcell | `bitcell/sram_bitcell_6t.gds` — 6 transistors, 4.46 x 5.40 um |
| Array | `sram_256x32/sram_256x32_array.gds` — 8,192 cells, 143.15 x 1382.40 um (0.1979 mm²): 142.72 um of tiled cells plus a 0.43 um wordline landing-pad strip at the left edge (issue #121) |
| DRC | `klt drc --deck gf180mcu`: **clean, 0 violations** — bitcell, 3x3 abutment tile, and the full 256 x 32 array. The PDK's **own native** deck (all 547 FEOL+BEOL rules, run directly per `reports/sram-rule-survey.md` "B.4") is also **clean, 0 violations** on all three |
| Devices | `klt extract --deck gf180mcu`: 6 devices in the bitcell, 49,152 (32,768 nfet + 16,384 pfet) in the array — exactly 6 x 8,192 |
| LVS | Bitcell: `klt lvs` vs. `design/netlist/bitcell_6t.spice`: **`status: match`** — 6/6 devices, 7/7 nets. Array: `klt lvs` vs. `design/netlist/sram_256x32_array.spice`, using `options.flatten_reference` (klayout-tools#1085, closed 2026-08-17): **`status: match`** — 49,152/49,152 devices, 16,706/16,706 nets, 322/322 pins; the sole `mismatches[]` entry is a `severity: warning` `topology.flattened` disclosure, not a defect (see "Known tool gaps" #2 and `layout/reports/lvs-array.json`, issue #108) |
| Column path (issue #205) | `periphery/column/` — `precharge_slice` (12 PMOS, 17.84 x 7.50 um) and `io_slice` (99 devices: 4:1 mux, sense amp, write driver, three flops; 17.84 x 58.50 um), each exactly four bitcell columns wide, plus a 32-slice band of each (570.88 um). `klt drc --deck gf180mcu`: **clean** on both slices, both bands, and on the bands abutted to the committed 64 x 128 array. The PDK's native deck (640 rule categories, `klt drc --engine klayout`): **clean** on both slices and on the abutted composite. `klt lvs` vs `design/netlist/{precharge,io}_slice.spice`: **`status: match`** — 12/12 and 99/99 devices, 14/14 and 59/59 nets, 14/14 and 26/26 pins (reference flattened, same `topology.flattened` disclosure as the array). See "The column path" |

Everything above is reproduced end-to-end by `./layout/verify.sh` (see
"Reproducing and re-checking"). What is *not* claimed is in "What this does
and does not prove".

## What's in this directory

```
layout/
  README.md                             this file
  verify.sh                             regenerate + re-run every check quoted here
  bitcell/
    generate.py                         draws the 6T bitcell (klayout.db API)
    sram_bitcell_6t.gds                 committed, deterministic GDS
  sram_256x32/
    generate.py                         tiles the bitcell into the 256 x 32 array
    sram_256x32_array.gds               committed, deterministic GDS
  periphery/column/
    generate.py                         draws the column path (netlist-driven, see below)
    precharge_slice.gds                 committed: 12 PMOS, one I/O's four columns
    io_slice.gds                        committed: mux + sense amp + write driver + 3 flops
    column_band.gds                     committed: 32-slice io_band / precharge_band
  periphery/row/
    generate.py                         draws the row decoder + wordline-driver strip (issue #204)
    row_path.gds                        committed: 16 predecoders + 64 rowdrv, one flat cell
  reports/                              machine-readable DRC/LVS/extract evidence (README inside)
  sram_64x128/
    sram_64x128_array.gds               64 x 128 array (4:1 organization), emitted by
                                        sram_256x32/generate.py --rows 64 --cols 128
                                        --top-name sram_64x128_array (issue #204)
```

### The bitcell

Six devices, sized from `design/netlist/bitcell_6t.spice` (not invented in
the layout): pull-ups `W=0.22`/`L=0.28`, pull-downs `W=0.36`/`L=0.28`, access
devices `W=0.24`/`L=0.28` (um). Each `W` is drawn as the poly/COMP overlap of
that device's channel, so `klt extract` reads back exactly those numbers.

* One NMOS COMP strip carries all four NMOS devices with shared source/drain
  diffusions in schematic order (`BL | MAL | Q | MNL | VSS | MNR | QB | MAR |
  BLB`); a second strip inside `Nwell` carries the two pull-ups sharing the
  middle `VDD` diffusion. Because the three device widths differ, the strips
  are stepped (contact-bearing pads wider than the channel necks) rather than
  plain rectangles.
* Each inverter's n- and p-gate is a **single** vertical `Poly2` stripe.
* Cross-coupling is two horizontal `Poly2` jogs at different heights in the
  band between the rows, each ending in a contacted landing pad, tied to the
  opposite storage node by one L-shaped `Metal1` strap. The two straps
  occupy disjoint x/y bands, which is what makes a single-`Metal1`
  cross-couple work here.
* Well and substrate ties are drawn **inside** the cell (`Nplus`-in-`Nwell`
  for `VDD`, `Pplus`-on-substrate for `VSS`), not deferred to periphery tap
  rows.

Full geometric plan, with every rule constant cited to its DRM rule id, is in
`bitcell/generate.py`'s module docstring and constants block.

### The array, and why it needs almost no array-level routing

The bitcell tiles by **abutment**: the wires that must run through it span its
full pitch — `Poly2` wordline across the full width, `Metal1` bitlines and
`Metal2` supply rails across the full height, `Nwell` across the full width —
so a plain 256 x 32 instance array wires itself. Each row's 32 cells share one
continuous wordline (`WL<row>`); each column's 256 cells share one continuous
bitline pair (`BL<col>`/`BLB<col>`). Supplies run **vertically** in `Metal2`
precisely so they never cross the horizontal wordline.

The placements are a single `kdb.CellInstArray` (one hierarchical instance
covering all 8,192 sites), so the committed array GDS is 20 KB, not 8,192
copies of the cell.

There are two pieces of array-level geometry. The first is two `Metal3`
straps (one `VDD`, one `VSS`) that drop a `Via2` onto each column's
corresponding `Metal2` stripe — that is what makes `VDD`/`VSS` *single* nets
across the array instead of 32 isolated column rails. Extraction confirms it:
the full array extracts to 16,706 nets = 256 wordlines + 64 bitlines + 2
supplies + 16,384 storage nodes (every cell's well/substrate tie is folded
directly into those 2 supply nets — see "Known tool gaps" #1).

The second is the **wordline landing-pad strip** (issue #121). Abutment
leaves each `WL<row>` as bare `Poly2`, which is not a `TYPE ROUTING` layer in
gf180mcu's tech LEF — so a wordline carrying nothing but `Poly2` has no pin
geometry a router, an abstract, or a physical row decoder could land on (all
256 `WL<row>` pins came back `geometry_source: "none"` in the array's first
LEF abstract, issue #120). The array therefore reserves a 0.43 um strip of
periphery to the *left* of the tiled cells — where a row decoder would sit —
and draws, per row, a `Poly2` landing pad abutting that row's wordline
stripe, one `Poly2`-to-`Metal1` contact on it, and a `Metal1` pad flush with
the macro's left boundary. `WL<row>` is labelled on that `Metal1` pad rather
than on the `Poly2` stripe. Every dimension is derived from
`layout/bitcell/generate.py`'s own DRM-cited contact/enclosure constants
(`CO_SIZE`, `CO_ENC_POLY`, `CO_ENC_M1`, `M1_SPACE`), the same ones the
bitcell's own `Poly2` cross-couple landing pads use, so the strip is drawn to
the identical rule margins as the cell it abuts. It adds no devices and no
nets — LVS still matches the unchanged
`design/netlist/sram_256x32_array.spice` port-for-port.

### The column path (issue #205)

`periphery/column/generate.py` draws the two per-I/O cells
`spec/periphery-architecture.md` (#202) fixed and `design/netlist/` (#203)
captured, each exactly **4 x `W_CELL` = 17.84 um** wide (one I/O = four
bitcell columns, #202 row 3) so 32 of them tile into a band:

| Cell | Netlist | Devices | Size | Sits |
|---|---|---|---|---|
| `precharge_slice` | `precharge_slice.spice` | 12 PMOS (precharge + equalize, 4 columns) | 17.84 x 7.50 um | above the array |
| `io_slice` | `io_slice.spice` | 99: 8 `tg_mux`, `sa_latch`, `wdrv`, 3 `dff` (`D` and `WEN` capture, `Q` register) | 17.84 x 58.50 um | below the array |

A 32-slice band is 570.88 um wide (`column_band.gds`: `io_band`,
`precharge_band`), 33,396 um² and 4,282 um² respectively — about 19% on top of
the 64 x 128 array's 197,445 um². **That is not an optimised number**: devices
are single-finger and diffusion sits on a 0.65 um grid (below), and the flops
alone are four times the height they would be in a hand-packed standard cell.

**How it is drawn.** No polygon is hand-placed. `generate.py` parses and
flattens the netlist (device `W`/`L` come from the file; the layout must
extract back to them, and `klt lvs` compares them), places devices in
shared-diffusion *chains* whose order is the only hand-made input, builds
N-row/P-row strips between `Metal1` supply rails (mirrored so strips share a
rail and its tie strip), and routes every signal net with a small
deterministic maze router on a 0.65 um grid over `Metal1`/`2`/`3`. The grid
pitch is chosen so any two different-net shapes on different nodes already
meet the width/space/narrow-line/wide-metal rules, so the router only keeps
nets on distinct nodes; static geometry (contact bars, rails, bit-line stubs,
bus tracks) is entered as obstacles with computed clearance. The module
docstring has the full reasoning, including why `Metal1`/`2`/`3` wires are
0.35 um (just clear of the DRM's < 0.34 um narrow-line end-of-line rules) and
why the pitch is not 0.62 or 0.60.

**Interface** (checked by the seam DRC, below):

* `BL`/`BLB`: 0.30 um `Metal1` stubs at the array's own bit-line x
  (`bitcell.X_BL_C`/`X_BLB_C` + k * `W_CELL`), flush with the slice's
  array-facing edge, so the seam adds no new bit-line geometry. 512 bit-line
  crossings (2 seams x 32 slices x 8) are asserted to be one `Metal1` polygon
  across the array/band seam by `generate.py --abut` itself, which has a
  negative control (shifting the band by 1 um fails the check).
* `VDD`/`VSS`: full-width `Metal1` rails at the same y in every slice, with
  continuous tie strips (substrate and n-well). A slice's several rails of one
  supply are joined by one vertical `Metal2` strap per supply — without it each
  `VDD` rail is its own well and the slice does not compare (see "Known tool
  gaps" #5).
* Shared control inputs (`csel*`, `cseln*`, `clk`, `q_clk`, `s_en`,
  `wl_en_n`, `wpn`): full-width `Metal3` bus tracks at the same y in every
  slice, so a band forms one net per control line.
* `d_in`, `wen_in`, `q_out` (#202 "Pin placement"): `Metal2` stubs at the
  bottom edge, at x = 2.745, 6.645 and 14.445 um within the slice (0.35 um
  wide, 1.475 um deep; #202's ~1.12 x 5 um foundry-style macro pins are #206's).
* Everything lies inside `0 <= x <= 17.84`, and diffusion stays >= 0.6 um from
  the slice's left/right edge, so a slice keeps the Nwell overlap of PCOMP on
  its own and the first and last slice of a band need no end cap.

**Findings.**

* The three flops of `io_slice.spice` *do* fit in the 17.84 um width (each is
  one strip of 25 of the 26 grid columns); the netlist and #202 are unchanged.
* The curated deck models none of the implant rules, and this cell is mostly
  implant bands, tie strips and wells — so the same geometry is also checked
  against the **PDK's native deck** (640 rule categories, `klt drc --engine
  klayout`): **0 violations** on both slices and on the abutted composite,
  committed as `reports/drc-native-column-*.json` (each carries
  `coverage_assertion` with 640 expected = 640 observed categories, so a deck
  that silently ran fewer rules would have failed) and regenerated with
  `./layout/reports/generate.sh --column-path --native`.
* The 64 x 128 array this seam is checked against is the committed
  `sram_64x128/sram_64x128_array.gds` (issue #204); its own DRC and LVS are
  `verify.sh` steps 8 and 9. `verify.sh` step 10 and
  `reports/drc-column-abut.json` check the bands abutted to it (the composite
  itself is a scratch file built by `periphery/column/generate.py --abut`).
* Rails: strap columns 1 and 24 of the 26 are reserved for `Metal2`. Other
  columns are free.

### The row path (issue #204)

`periphery/row/generate.py` draws `design/netlist/row_path.spice` as one flat
cell `row_path`: two 3->8 predecoders (8 x `and4` for `wl_en` and the high
address bits, 8 x `and3` for the low bits) and 64 `rowdrv` wordline drivers --
528 devices (264 nfet + 264 pfet), 53.59 x 397.33 um. It reuses the column
path's netlist reader, strip placer and maze router unchanged (it imports
`periphery/column/generate.py`; only the slice-width globals are set per build),
so the 0.65 um grid argument above applies here too.

**Scope.** The decoder strip only, for the center-fed 4:1 organization
(`spec/wordline-rc-decision.md`, ratified by the operator's ruling on #228).
Placing the 16 + 16 column slices, the second landing-pad strip and re-tiling
the array are #206. The existing `sram_64x128/sram_64x128_array.gds` is
**left-fed and unchanged**.

**Does `rowdrv` fit the 5.40 um row pitch? No.** Its 6 um PMOS / 3 um NMOS output
stage plus the 2 um NAND2 make it **13.65 um rail to rail** (smallest channel
that routes, `chan = 1`), 2.5 row pitches. The drivers are interleaved in 3
columns: driver `k` sits in column `k % 3`, so consecutive drivers of a column
are 16.2 um apart, and each `WL<k>` leaves on a `Metal3` track at row `k`'s
height. A predecoder/driver split into one 5.40 um column would need a smaller
output stage or a different cell topology, which is a design change, not
placement.

**Interface.**

* `WL<k>`: a `Metal3` track at `y = 48.750 + k * 5.40 + wl_y` (strip frame; the
  array's row 0 goes at strip y = 48.750 so each track is at its row's landing-pad
  height), spanning the strip's full width and ending in a labelled
  0.70 um-wide `Metal3` pin stub (`max(WL_PAD_BAND, ...)`) at **both** edges (the strip sits between the two
  halves). The array's landing pads are `Metal1`; joining them is assembly's
  job (#206), as is any mirroring of the second half.
* `aq2..aq7`, `aqb2..aqb7`, `wl_en`: `Metal2` stubs on the bottom edge.
* `VDD`/`VSS`: `Metal2` straps (labelled) joined by two `Metal3` jumpers.

**Findings.**

* `klt drc --deck gf180mcu`: 0 violations. `klt lvs` against `row_path.spice`
  (inline extraction, `flatten_reference`): `status: match`, 528/528 devices,
  279/279 nets, 79/79 pins; the only `mismatches[]` entries are the
  `topology.flattened` disclosure and the "no bjt on either side" note. Reports:
  `reports/{drc,extract,lvs}-row-path.json`.
* **Not run: the PDK-native DRC deck.** This host has no `gf180mcuD`
  `run_drc.py` (`~/.ciel/gf180mcuD/libs.tech/klayout/tech/drc` is absent), so
  unlike the column path no native-deck result exists for the strip. The curated
  deck models none of the implant rules, so implant and well spacing on this
  strip is not checked by any deck run here.
* Not claimed: physical fit with the array or the column bands, abutment or
  connectivity of the assembled floorplan, parasitics, timing, or any validation
  result. **Full-array wordline RC / write-margin validation (the 27-corner,
  15 ohm/sq matrix in `spec/wordline-rc-decision.md`) is pending** and needs a
  separate operator grant.
* The strip is area-naive (single-finger devices, 0.65 um grid, three driver
  columns with the gaps between them): it is a correct drawing, not an
  optimized one.

### Scope: the storage-array core, matching `design/`

Like the schematic side (see `design/README.md`), this is the bitcell-array
**core**. Address decode, column mux, sense amps and write drivers — the rest
of `spec/sram.md`'s 1RW pin list (`A`, `CEN`, `CLK`, `D`, `Q`, `GWEN`, `WEN`)
— are periphery. The array's ports are the raw
per-row/per-column pins the ratified organization implies and the committed
netlist declares: `WL0..WL255`, `BL0..BL31`, `BLB0..BLB31`, `VDD`, `VSS`.
Port-for-port, cell-for-cell, this layout is the same 256 x 32 / 1RW
organization `spec/sram.md` ratifies and `design/sram_256x32_array.sch`
captures.

The periphery architecture, macro floorplan and pin placement are fixed in
[`spec/periphery-architecture.md`](../spec/periphery-architecture.md). Note it
proposes a 4:1 column mux, i.e. a 64 x 128 physical array rather than the
256 x 32 drawn here. The 64 x 128 re-tiling (571.31 x 345.60 um, `WL0..WL63`,
same bitcell and landing-pad strip) is `sram_64x128/sram_64x128_array.gds`
(issue #204), emitted by the same generator and checked by `verify.sh` steps 1,
2, 8 and 9 (DRC clean; LVS against `design/netlist/sram_64x128_array.spice`).
The 256 x 32 files are left untouched until macro assembly (#206) retires them.
Of the periphery, the **column path** (precharge, 4:1 mux, sense amp, write
driver, input/`Q` flops) and the **row decode / wordline-driver strip** are
drawn so far -- see "The column path" and "The row path" above; control and
macro assembly and pins (#206) are not.

## What this does and does not prove

**Proves** (all reproducible via `./layout/verify.sh`):

* The layout is DRC-clean **against the deck `klt` implements** — a curated
  subset of the gf180mcu DRM (width/space/enclosure across
  Poly2/COMP/Contact/Metal1-5/Via1-4, plus Nwell) — at the bitcell, at a 3x3
  abutment tile (so tiling itself introduces no violation), and across the
  full 8,192-cell array.
* The layout **is** the committed schematic: `klt lvs` reports
  `status: match`, 6/6 devices and 7/7 nets, against
  `design/netlist/bitcell_6t.spice`, with device `W`/`L` read back from the
  drawn geometry.
* The array tiles into the ratified organization with the right connectivity:
  49,152 devices, wordlines shared per row, bitline pairs shared per column,
  single `VDD`/`VSS` nets.
* Structural power delivery (T1 item 11, issues #124 and #159): `klt erc`'s
  supply read (`layout/sram_256x32/erc-supply-spec.json` →
  `layout/reports/erc-array-supply.json`, klt 0.6.0) proves each declared
  supply (`VDD`, `VSS`) resolves to exactly **one** electrical island on the
  pure metal-connectivity graph — zero `erc.unconnected_net`, zero
  `erc.supply_short` — with a negative control proving the check computes.
  The spec declares both ties in `ties[]`, and `erc.missing_tie` is computed
  for each, with zero findings: `nwell_tie` (Nwell 21/0, tap = Comp AND
  Nplus, net `VDD`) and `substrate_tie` (gf180mcu draws no p-well, so
  `well_layer: null` + one `well_boxes` entry per row, tap = Comp AND Pplus,
  net `VSS`). Both sit in `erc_coverage.checked` with `skipped` empty; the
  substrate tie is graded `checked_by_well_assertion` — its well region is
  the spec's own assertion (non-degenerate and falsifiable, but asserted, not
  drawn). A negative control (issue #159: `nwell_tie` declared on `VSS`)
  fires 256 `erc.missing_tie`, so the tie check can fail on this layout.
  The citation is compound: the ERC report plus item 4's `lvs-array.json`
  (`match`, `VDD`/`VSS` paired in `net_correspondence`), cited alongside it
  rather than in place of a tie check. Full field-by-field reading:
  `layout/reports/README.md` § "Item 11".
* Geometry is on a 5 nm grid and passes `klt precheck`'s hygiene battery.

**Does not prove**:

* **Sign-off DRC as a repeatable, committed check.** `klt`'s gf180mcu deck
  (`klt drc --deck gf180mcu`, run and committed as evidence in
  `layout/reports/` by issue #23) is explicitly a curated subset. It does
  not model implant (`Nplus`/`Pplus`) rules, poly-to-COMP and
  contact-to-poly spacing, density, antenna, latch-up, or the DRM's
  `SramCore` (108/5) marker-scoped SRAM rules. The PDK's *own* native deck
  **has** now been run against this cell (issue #103, `reports/sram-rule-
  survey.md` "B.4": 547 rules, 21 violations found and fixed, now 0 on the
  bitcell, the 3x3 abutment tile and the full 8,192-cell array) — so
  "satisfied by construction"
  is no longer the only claim. What is still missing is a *committed,
  schema-carrying, CI-runnable* form of that run: it is a manual
  `klayout -b -r` invocation because `klt drc --engine klayout` cannot
  drive this PDK's deck ([klayout-tools#1302](https://github.com/2AMLogic/klayout-tools/issues/1302)),
  so nothing in `layout/reports/` re-checks it automatically and a future
  geometry change can silently regress it again. Issue #8's
  [`layout/reports/sram-rule-survey.md`](reports/sram-rule-survey.md)
  surveys exactly which rule families the `SramCore` marker relaxes (poly/
  contact overlap and several Nwell/LVPWELL/COMP spacing rules -- **not**
  implant, density, antenna, or latch-up, contrary to what this bullet's
  wording might suggest), and runs both the curated deck and (directly,
  bypassing a `klt` gap it found and filed --
  [klayout-tools#1302](https://github.com/2AMLogic/klayout-tools/issues/1302))
  the PDK's real native deck against the foundry's own hardened bitcell
  macro for comparison. A standalone `klayout` binary is now present on
  this host (unlike when this bullet was first written for issue #23), but
  `klt drc --engine klayout` still cannot resolve or correctly drive
  gf180mcu's native deck end-to-end -- see the survey's "B.2" for the full
  chain of attempts and why.
* **Electrical behaviour.** The ratified `sim/` PVT results (`sim/<experiment>/records/`)
  still characterize the *schematic* only -- issue #23 produced one
  real PEX-adjacent artifact (a parasitic-annotated bitcell extraction,
  `sim/pex/`) but could not produce a per-corner schematic-vs-extracted
  delta against the ratified testbenches themselves. Issue #95 closed
  that for write/read access time (`klt pex`-native, `sim/pex/access-time/`)
  and write margin (a by-hand extraction workflow, `sim/pex/write-margin/`)
  as new, parallel evidence alongside (not replacing) the ratified
  schematic records, and documented -- with evidence -- that no
  PEX-compatible path exists for read/hold SNM given this layout's
  monolithic (non-partitionable) bitcell geometry. See `sim/pex/README.md`
  for the full per-measurement breakdown. `sim/pex/` was re-extracted
  against the current (post-issue-#103) bitcell geometry by issue #106 —
  `provenance.input.content_hash` now matches this committed GDS's
  sha256, and no PASS/FAIL verdict moved from the pre-#103 records
  (preserved, unedited, under `sim/pex/pre-issue-103/`); see
  `sim/pex/README.md` "Freshness" for the full re-run record.
* **The column path is a drawn, verified layout — not a characterised one.**
  Geometry, DRC and netlist agreement are proven (see "The column path"); no
  parasitic extraction, timing, or `sim/` result exists for it. Nothing here
  shows the sense amp resolves the bit-line differential, that the write
  driver wins against the bitcell, or that the 4:1 mux and flop timing meet
  the cycle — those need `klt pex` of these cells against the ratified
  testbenches, and the `io_slice` reference is compared *flattened* (the layout
  is drawn flat per slice), so no per-subcircuit hierarchy is verified.
* **A routed macro.** There is still no control logic or macro
  assembly (#206), and the row strip is drawn but not placed against the array. The LEF abstract
  (`views/sram_256x32_array.lef`, issues #120/#182) is generated by the
  released klt 0.6.0 and all 322 pins carry real drawn `PORT` geometry
  (klayout-tools#1614 fixed; the wordlines reach Metal1 since issue #121), but
  `klt place-and-route` has not been run against it, so it is not claimed
  routable. No Liberty view exists yet either. See `views/README.md`'s
  "Pin geometry" and "What this does and does not prove".
* **Array-level LVS.** Achieved — see "Known tool gaps" #2. `klt extract`
  itself stays flat-only (the layout side is always a single flat circuit),
  but `klt lvs`'s `options.flatten_reference` (klayout-tools#1085, closed
  2026-08-17) flattens the *hierarchical reference* netlist before comparing,
  so the two sides pair up: `layout/reports/lvs-array.json` reports
  `status: match`, 49,152/49,152 devices, 16,706/16,706 nets, 322/322 pins
  matched. The remaining `mismatch_count: 1` entry is a `severity: warning`
  `topology.flattened` disclosure of that flatten, not a real mismatch
  (issue #108).

## Area: measured against the foundry's own bitcell

`spec/bitcell-decision.md` cites gf180mcu's hardened `gf180mcu_fd_ip_sram` as
the topology reference. Its **layout** ships in the PDK, so its bitcell is
directly measurable — done here with `klt cells` on
`libs.ref/gf180mcu_fd_ip_sram/gds/gf180mcu_fd_ip_sram__sram64x8m8wm1.gds`:

| | Column pitch | Row pitch | Area/bit |
|---|---|---|---|
| Foundry `018SRAM_cell1` | <= 3.68 um | 4.84 um | <= 17.8 um² |
| This repo's `sram_bitcell_6t` | 4.46 um | 5.40 um | 24.1 um² |

(The foundry cell's own drawn extent is 3.68 x 5.18 um; its mirrored-pair
container `018SRAM_cell1_2x` is 3.68 x 9.68 um for two cells, i.e. a 4.84 um
row pitch. 3.68 um is an *upper bound* on its column pitch — mirroring may
let adjacent columns share more than the bbox suggests — so 17.8 um²/bit is
an upper bound too.)

So this cell is roughly **1.35x** the foundry cell's area, from a first-cut
full-custom draw. The gap is understood, not mysterious:

1. **No mirroring.** Cells are tiled by plain translation, so nothing is
   shared between neighbours. Mirroring alternate rows/columns (what the
   foundry cell does — hence its `_2x` container) lets adjacent cells share
   bitline contacts, supply contacts and tie strips.
2. **Generic rules, not SRAM rules.** The DRM's `SramCore`-marker rules exist
   precisely to let a bitcell go tighter than the generic minimums; this cell
   uses generic minimums *plus* margin, because `klt`'s curated deck does not
   model the marker-scoped rules and drawing to unverifiable tighter numbers
   would be a worse trade.
3. **Single-`Metal1` cross-couple**, which costs a wider centre pad.

Macro-level comparison is *not* meaningful here: the foundry 64x8 macro
(431.86 x 232.88 um for 512 bits) is periphery-dominated, and this array has
no periphery at all.

## Known tool gaps (friction protocol)

Filed generically against `2AMLogic/klayout-tools` per `CLAUDE.md` (1–4 predate the column path; 5–7 are from issue #205):

1. **No tap/tie layer in the gf180mcu extraction deck — filed, and since
   fixed upstream, but the fix changed what this repo's compare needs to
   do.** The deck originally declared `tap=None`, so drawn well/substrate
   ties could not be recognised: every extracted NMOS body landed on a
   synthesized global substrate net and every PMOS body on an anonymous
   `Nwell` net, regardless of what the layout drew. Filed as
   [klayout-tools#1084](https://github.com/2AMLogic/klayout-tools/issues/1084)
   (related, already-closed precedent for sky130: klayout-tools#490);
   upstream fixed it in
   [klayout-tools#1113](https://github.com/2AMLogic/klayout-tools/pull/1113)
   ("derive gf180mcu well/substrate tap from Nplus/Pplus implants"), merged
   2026-08-17. Installed `klt` builds after that PR now fold this cell's
   drawn ties straight into the `VDD`/`VSS` nets they physically contact —
   the same nets the schematic reference already uses — so no bulk-terminal
   substitution is needed for a match today (`nets: layout=7 reference=7
   matched=7`). Because `klt` is installed unpinned
   (`uv tool install git+https://github.com/2AMLogic/klayout-tools`, see
   "Tool / PDK versions"), two hosts can report the *same* `klt --version`
   string (`0.2.0`) while running different behavior depending on when each
   installed it relative to #1113 — this is what happened in
   [gf180-sram#75](https://github.com/2AMLogic/gf180-sram/issues/75), where a
   hardcoded bulk-net rewrite of the reference broke a match that was
   already clean. The rewrite script that came out of that
   (`layout/lvs_reference.py`) was a no-op on current builds and was removed
   (gf180-sram#185): the bitcell LVS now compares against
   `design/netlist/bitcell_6t.spice` unmodified, verified on the CI-pinned
   `klayout-tools==0.6.0`. If the bulk-net naming ever regresses, that
   compare fails loudly.
2. **`klt extract` is flat-only**, by design ("Flat (not hierarchical)
   extraction, deliberately") — still true today, and not what closed this
   gap. The committed array GDS *is* hierarchical (one bitcell cell, one
   `CellInstArray`) and the committed reference netlist is too (one
   `.subckt bitcell_6t` + 8,192 calls); extraction alone flattens only the
   layout side to 49,152 top-level devices, leaving the reference
   hierarchical, so `klt lvs` used to be unable to pair the two sides at all
   (`topology: circuit could not be matched to a counterpart`, both sides).
   Filed as
   [klayout-tools#1085](https://github.com/2AMLogic/klayout-tools/issues/1085);
   **closed 2026-08-17**, landing `options.flatten_reference` /
   `options.flatten_layout` on `klt lvs`. The fix is on the *compare* side,
   not the extraction side: `klt extract` still only ever produces a flat
   layout-side netlist, but `options.flatten_reference: true` now flattens
   the *reference*'s hierarchy in-process (collapsing every subcircuit-call
   instance in place) before comparing, so the already-flat layout side gets
   a directly comparable counterpart. Re-run against this repo's committed
   array GDS/netlist (`layout/reports/generate.sh`, issue #108):
   `status: match`, 49,152/49,152 devices, 16,706/16,706 nets, 322/322 pins
   matched — `layout/reports/lvs-array.json`'s only remaining `mismatches[]`
   entry is the expected `severity: warning`, `category: topology.flattened`
   disclosure of that flatten, not a real defect. Array/macro LVS is
   therefore achievable today via `options.flatten_reference`; it was a
   missing compare-side option, not a fundamentally unsolvable
   flat-vs-hierarchical mismatch. (Historical caveat: the original `klt 0.2.0`
   mint of `layout/reports/lvs-array.json` predates klayout-tools#1205's
   `options` echo in the response JSON, so that earlier artifact did not
   literally carry an `options.flatten_reference: true` field — the flatten
   was visible only via the `topology.flattened` disclosure entry described
   above and the fully-matched device/net/pin counts. The currently
   committed report, re-minted with `klt 0.5.0` per its `provenance` block,
   echoes the full `options` object and does literally carry
   `flatten_reference: true`.)
3. **No bitcell/array generator, and no grid placement in `gen-compose`** (the
   finding PR #36 recorded): `klt gen`'s generators are generic matched-device
   analog primitives, and `gen-compose`'s placement strategies are `row` and
   `explicit` only, so a 256 x 32 tiling would need 8,192 explicit entries.
   Filed then as
   [klayout-tools#1053](https://github.com/2AMLogic/klayout-tools/issues/1053)
   — **closed as completed upstream since**, though the `klt 0.2.0` build used
   here still documents `"grid"` as "spike-scoped for a later phase". Worth
   revisiting on the next `klt` upgrade; the bespoke `klayout.db` generator
   here (the pattern the sibling `gf180-bandgap`'s
   `layout/bandgap_top/generate.py` establishes) remains the working approach
   in the meantime.
4. **`klt drc --engine klayout` silently runs zero rules against a PDK-native
   deck that needs `-rd` variables beyond `input`/`report`** (found running
   issue #8's foundry-bitcell native-DRC comparison). gf180mcu's native deck
   is assembled from Ruby fragments that gate every rule behind `$feol`/
   `$beol`/`$metal_top`/`$metal_level`/`$mim_option` globals; `klt`'s
   `--engine klayout` subprocess only ever sets `-rd input=`/`-rd report=`,
   so those globals default to false/unset and the deck completes
   "successfully" having checked nothing -- `status: clean, violation_count:
   0`, indistinguishable from a real clean pass. Filed as
   [klayout-tools#1302](https://github.com/2AMLogic/klayout-tools/issues/1302).
   `layout/reports/sram-rule-survey.md` "B.2" got a real answer by invoking
   `klayout -b -r` directly with the full variable set, bypassing `klt` for
   that one step.

5. **Pre-extracted `klt lvs` never raises `net.supply_fragmented`; a split
   supply is dozens of anonymous errors** (found by the column path, issue
   #205). Three unstrapped `VDD` rails in one cell extract as `VDD VDD$1
   VDD$2` with no warning, and `klt lvs` on that netlist reported 70 errors
   (`device.unmatched`, `net.merged`, `net.split` with layout names `\$13`…)
   and no supply finding; the finding exists (klayout-tools#2078) but only on
   the inline `layout.file` + `deck` form. Filed as
   [klayout-tools#3920](https://github.com/2AMLogic/klayout-tools/issues/3920).
   The column-path checks therefore use the inline form
   (`layout/verify.sh` 5c, `layout/reports/generate.sh` step 0), which also
   turns `body_verification` from `unchecked` to `verified`; the bitcell and
   array LVS above still use the extracted-netlist form.
6. **No netlist → placed/routed layout verb** (third instance of
   klayout-tools#346 / #1116, both closed as spikes). The column path needed a
   bespoke ~1,100-line `klayout.db` generator — shared-diffusion chains,
   rails/ties/wells/implants, a DRC-safe-by-construction multi-terminal grid
   router, port stubs at externally dictated x — because `klt gen`'s
   generators are uniform arrays and `gen-compose` cannot route nets of three
   or more terminals. Filed as
   [klayout-tools#3922](https://github.com/2AMLogic/klayout-tools/issues/3922)
   with the capability list and two pitfalls (the curated deck models neither
   the wide-metal nor the narrow-line end-of-line rules the pitch had to
   respect; see also the open klayout-tools#3796 and #2351).
7. **`klt drc --engine klayout` now works for gf180mcu, but only with the
   deck script built by hand.** Item 4's silent-zero-rules failure is closed
   (klayout-tools#1302): `--deck-file` + repeated `--deck-var` +
   `--expect-rule-categories 640` drives the PDK's native deck and fails if it
   runs fewer rule tables. `--pdk gf180mcuD` alone still answers "no PDK-native
   klayout DRC deck script found", because the deck is produced by the PDK's
   `run_drc.py --macro_gen` (which needs the `docopt` and `klayout` packages
   and a `--path` that exists but is unused). `layout/reports/generate.sh
   --column-path --native` does those steps. Not re-filed: it continues
   klayout-tools#1302 / #3816, not a new gap.

## Install `klt`

```bash
uv tool install git+https://github.com/2AMLogic/klayout-tools
# or: pip install git+https://github.com/2AMLogic/klayout-tools
klt --version   # 0.2.0 as of this writing
```

`klt` runs fully headless via the pip `klayout` package's native `klayout.db`
primitives — no KLayout GUI/application binary, no `DISPLAY`, no Qt.

## Reproducing and re-checking

Everything in one command, from the repo root:

```bash
./layout/verify.sh            # ~5 min: adds the full-array DRC + extraction and the column seam DRC
./layout/verify.sh --quick    # ~1 min: bitcell, 3x3 tile, the column path (slices, bands, LVS) and the row strip
```

It regenerates all GDS files (bitcell, array, column path), fails if any
differs from the committed bytes, then runs `klt precheck`, `klt drc`, `klt extract` and `klt lvs` and
prints each verdict. Individually:

```bash
# 1. bitcell (byte-for-byte deterministic -- git diff stays empty)
uv run --with klayout python3 layout/bitcell/generate.py

# 2. 256 x 32 array, tiling that same bitcell cell
uv run --with klayout python3 layout/sram_256x32/generate.py
#    (--rows/--cols build a smaller tile without touching the committed file)

# 3. checks
klt precheck --deck gf180mcu --grid-um 0.005 layout/bitcell/sram_bitcell_6t.gds
klt drc --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds
klt drc --deck gf180mcu layout/sram_256x32/sram_256x32_array.gds   # ~1 min
klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds -o /tmp/bc.spice
klt lvs '{"layout":{"netlist":"/tmp/bc.spice","top":"sram_bitcell_6t"},
          "reference":{"netlist":"design/netlist/bitcell_6t.spice","form":"subckt-call"}}'

# 3b. column path (issue #205): slices, 32-slice bands, per-slice LVS
uv run --with klayout python3 layout/periphery/column/generate.py
klt drc --deck gf180mcu layout/periphery/column/io_slice.gds
klt drc --deck gf180mcu layout/periphery/column/column_band.gds
klt lvs '{"layout":{"file":"layout/periphery/column/io_slice.gds","deck":"gf180mcu","top":"io_slice"},
          "reference":{"netlist":"design/netlist/io_slice.spice","form":"subckt-call"},
          "options":{"flatten_reference":true}}'
#    bit-line seam against a scratch 64 x 128 array (~1 min):
uv run --with klayout python3 layout/sram_256x32/generate.py --rows 64 --cols 128 -o /tmp/a.gds
uv run --with klayout python3 layout/periphery/column/generate.py --abut /tmp/a.gds -o /tmp/abut.gds
klt drc --deck gf180mcu /tmp/abut.gds
#    the PDK-native deck too (writes layout/reports/drc-native-column-*.json):
./layout/reports/generate.sh --column-path --native

# 4. inspection
klt stats layout/bitcell/sram_bitcell_6t.gds
klt cells layout/sram_256x32/sram_256x32_array.gds
```

`uv run --with klayout` pulls the pip `klayout` package into an ephemeral venv
on first run — no repo-local Python environment to set up. Both generators
write GDS with GDSII header timestamps disabled, so re-running leaves
`git diff` empty (checked by step 1 of `verify.sh`).

Expected results, as committed (2026-08-16):

| Check | Result |
|---|---|
| `bitcell/generate.py` re-run | byte-identical to the committed GDS |
| `sram_256x32/generate.py` re-run | byte-identical to the committed GDS |
| `klt precheck` (both, `--grid-um 0.005`) | `status: pass` (offgrid, zero_area, cell_names, pin_labels_over_drawing) |
| `klt drc --deck gf180mcu` (bitcell) | `status: clean`, 0 violations |
| `klt drc --deck gf180mcu` (3x3 tile) | `status: clean`, 0 violations |
| `klt drc --deck gf180mcu` (full array) | `status: clean`, 0 violations (~66 s) |
| `klt extract` (bitcell) | 6 devices (4 nfet + 2 pfet), 7 nets, W/L per `design/netlist/bitcell_6t.spice` |
| `klt extract` (full array) | 49,152 devices, 16,706 nets, 322 pins (~94 s) |
| `klt lvs` (bitcell vs. rewritten reference) | `status: match`, 0 mismatches |
| `periphery/column/generate.py` re-run | byte-identical to the committed three GDS files (also across `PYTHONHASHSEED`) |
| `klt drc --deck gf180mcu` (precharge_slice, io_slice, column_band) | `status: clean`, 0 violations |
| `klt drc --deck gf180mcu` (bands abutted to a 64 x 128 array, scratch) | `status: clean`, 0 violations (~1 min) |
| `klt drc --engine klayout` native deck (both slices, abutted composite) | `status: clean`, 0 violations, 640/640 rule categories |
| `klt lvs` (precharge_slice / io_slice, reference flattened) | `status: match`; 12/12 and 99/99 devices, 14/14 and 59/59 nets, 14/14 and 26/26 pins; `mismatches[]` holds only warnings |
| `klt stats` (bitcell) | `bbox_um: (0.0, 0.0) - (4.46, 5.4)`, 38 polygons |
| `klt stats` (array) | `bbox_um: (0.0, 0.0) - (143.15, 1382.4)` |

## Tool / PDK versions

- `klt` 0.2.0 (KLayout module 0.30.10, reported by `klt lvs`'s
  `environment.engine_version`)
- `klayout` pip package, via `uv run --with klayout` (unpinned — see the
  note below)
- Python 3.12+ for the generators (stdlib + `klayout` only)
- PDK: `gf180mcuD`, `open_pdks` commit
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (the commit
  `spec/bitcell-decision.md` and `design/README.md` both verify against),
  installed via [volare](https://github.com/efabless/volare) under
  `~/.volare/gf180mcuD` — see `spec/pdk-variant-decision.md` for why
  `gf180mcuD`, not the `gf180mcuC` this section cited before. The PDK is
  read here only for the layer/datatype map and the foundry-bitcell area
  comparison — the generators themselves depend on nothing but
  `klayout.db`, so `verify.sh`'s DRC/LVS steps run without a PDK install,
  and neither the layer/datatype map nor the area comparison (both
  confirmed byte-identical between `gf180mcuC` and `gf180mcuD` in that
  decision record) changed as a result of the re-pin.

**Known gap, noted rather than fixed**: neither generator pins an exact
`klayout` package version, so a future run could pick up a release with
different default behaviour. The sibling `gf180-bandgap`'s
`layout/bandgap_top/generate.py` has the same property; this repo follows that
existing convention rather than diverging unilaterally. Pinning is a
reasonable follow-up, not this issue's scope. `klt` itself is installed the
same unpinned way (`uv tool install git+https://github.com/2AMLogic/klayout-tools`,
"Install `klt`" below) — a real instance of this gap already surfaced as
[gf180-sram#75](https://github.com/2AMLogic/gf180-sram/issues/75) (see "Known
tool gaps" #1), where an upstream extractor behavior change landed between two
installs without changing the reported `klt --version`.

## Freshness / staleness (per `design-evidence-tiers.md`)

This layout is derived from, and verified against, the design sources
committed by issue #21 (PR #37): `design/bitcell_6t.sch` /
`design/netlist/bitcell_6t.spice` for the device sizing and topology, and
`design/sram_256x32_array.sch` for the array organization. The `klt lvs`
`status: match` above **is** the freshness check, and `layout/verify.sh`
re-runs it on demand.

If the schematic or netlist changes — a device resize, a topology change, a
`--rows`/`--cols` change — this layout is **stale** until
`layout/bitcell/generate.py`'s sizing constants are updated to match, both
GDS files are regenerated, and `./layout/verify.sh` reports a clean DRC and
an LVS `match` again. A resize that only changes `W` needs a constant edit
(`W_PU`/`W_PD`/`W_PG`) plus a regenerate; a topology change needs real
re-layout work.

## References

- `spec/sram.md` — ratified organization (256 x 32, 1RW) this layout targets.
- `spec/bitcell-decision.md` — the decision to draw a custom bitcell rather
  than integrate `gf180mcu_fd_ip_sram`, and the note that the custom
  bitcell's DRC waiver/special-rule status (the `SramCore`-marker rules
  discussed under "Area") is not yet established.
- `spec/pdk-variant-decision.md` — pins `gf180mcuD` as the PDK variant cited
  above, with direct evidence that this directory's DRC/LVS/area results
  (Metal1-Metal3 only, via `klt`'s variant-agnostic curated deck) do not
  depend on the C-vs-D Metal5 delta.
- `design/README.md` — the schematic side, including the device sizing table
  this layout draws from and the same core-vs-periphery scope boundary.
- Issue #23 — DRC/LVS/PEX sign-off, which consumes this layout: closed the
  DRC/LVS legs with committed reports in `layout/reports/`; the PEX leg
  produced one real artifact (`sim/pex/`) but not a full signoff. Issue #95
  closed the PEX leg per-measurement (write/read access time via `klt
  pex`, write margin via a by-hand extraction workflow; no PEX-compatible
  path for read/hold SNM) -- see `sim/pex/README.md`.
- `2AMLogic/gf180-bandgap`, `layout/bandgap_top/generate.py` — the sibling
  canary whose construction pattern (bespoke `klayout.db` generator,
  deterministic GDSII writer options, `uv run --with klayout` invocation)
  this directory follows.
