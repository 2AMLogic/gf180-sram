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
| Bitcell | `bitcell/sram_bitcell_6t.gds` — 6 transistors, 4.46 x 5.39 um |
| Array | `sram_256x32/sram_256x32_array.gds` — 8,192 cells, 142.72 x 1379.84 um (0.1969 mm²) |
| DRC | `klt drc --deck gf180mcu`: **clean, 0 violations** — bitcell, 3x3 abutment tile, and the full 256 x 32 array |
| Devices | `klt extract --deck gf180mcu`: 6 devices in the bitcell, 49,152 (32,768 nfet + 16,384 pfet) in the array — exactly 6 x 8,192 |
| LVS | `klt lvs` vs. `design/netlist/bitcell_6t.spice`: **`status: match`** — 6/6 devices, 7/7 nets (see "Known tool gaps" #1 for how `layout/lvs_reference.py` keeps this reproducible across `klt` extraction-deck behavior) |

Everything above is reproduced end-to-end by `./layout/verify.sh` (see
"Reproducing and re-checking"). What is *not* claimed is in "What this does
and does not prove".

## What's in this directory

```
layout/
  README.md                             this file
  verify.sh                             regenerate + re-run every check quoted here
  lvs_reference.py                      bulk-terminal rewrite for the LVS reference,
                                        derived from an actual extracted netlist
                                        (see "Known tool gaps")
  bitcell/
    generate.py                         draws the 6T bitcell (klayout.db API)
    sram_bitcell_6t.gds                 committed, deterministic GDS
  sram_256x32/
    generate.py                         tiles the bitcell into the 256 x 32 array
    sram_256x32_array.gds               committed, deterministic GDS
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

The only array-level geometry is two `Metal3` straps (one `VDD`, one `VSS`)
that drop a `Via2` onto each column's corresponding `Metal2` stripe — that is
what makes `VDD`/`VSS` *single* nets across the array instead of 32 isolated
column rails. Extraction confirms it: the full array extracts to 16,706 nets
= 256 wordlines + 64 bitlines + 2 supplies + 16,384 storage nodes (every
cell's well/substrate tie is folded directly into those 2 supply nets — see
"Known tool gaps" #1).

### Scope: the storage-array core, matching `design/`

Like the schematic side (see `design/README.md`), this is the bitcell-array
**core**. Address decode, column mux, sense amps and write drivers — the rest
of `spec/sram.md`'s 1RW pin list (`A`, `CEN`, `CLK`, `D`, `Q`, `GWEN`, `WEN`)
— are periphery and are not drawn. The array's ports are the raw
per-row/per-column pins the ratified organization implies and the committed
netlist declares: `WL0..WL255`, `BL0..BL31`, `BLB0..BLB31`, `VDD`, `VSS`.
Port-for-port, cell-for-cell, this layout is the same 256 x 32 / 1RW
organization `spec/sram.md` ratifies and `design/sram_256x32_array.sch`
captures.

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
* Geometry is on a 5 nm grid and passes `klt precheck`'s hygiene battery.

**Does not prove**:

* **Sign-off DRC.** `klt`'s gf180mcu deck is explicitly a curated subset. It
  does not model implant (`Nplus`/`Pplus`) rules, poly-to-COMP and
  contact-to-poly spacing, density, antenna, latch-up, or the DRM's
  `SramCore` (108/5) marker-scoped SRAM rules. Those rules are satisfied
  *by construction* here (every constant in `bitcell/generate.py` cites the
  DRM rule it targets, with margin), which is **not** the same as being
  checked. Running the PDK's own KLayout DRC deck (`klt drc --engine
  klayout`, which needs a standalone `klayout` binary this host does not
  have) is part of issue #23.
* **Electrical behaviour.** No post-layout simulation, no parasitics. The
  `sim/` PVT results characterize the *schematic*; PEX and post-layout
  re-simulation are issue #23.
* **A routed macro.** There is no periphery, no pin/obstruction abstract, no
  LEF/Liberty view (issue #24's scope).
* **Array-level LVS.** See "Known tool gaps" — `klt extract` is flat-only, so
  the hierarchical array netlist cannot be compared as-is today.

## Area: measured against the foundry's own bitcell

`spec/bitcell-decision.md` cites gf180mcu's hardened `gf180mcu_fd_ip_sram` as
the topology reference. Its **layout** ships in the PDK, so its bitcell is
directly measurable — done here with `klt cells` on
`libs.ref/gf180mcu_fd_ip_sram/gds/gf180mcu_fd_ip_sram__sram64x8m8wm1.gds`:

| | Column pitch | Row pitch | Area/bit |
|---|---|---|---|
| Foundry `018SRAM_cell1` | <= 3.68 um | 4.84 um | <= 17.8 um² |
| This repo's `sram_bitcell_6t` | 4.46 um | 5.39 um | 24.0 um² |

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

Filed generically against `2AMLogic/klayout-tools` per `CLAUDE.md`:

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
   installed it relative to #1113 — this is exactly what happened in
   [gf180-sram#75](https://github.com/2AMLogic/gf180-sram/issues/75): a host
   that had already picked up #1113's fix (bulk tied straight to `VDD`/`VSS`)
   ran against `layout/lvs_reference.py`'s then-hardcoded `vsubs`/`vnw`
   rewrite, which assumed the pre-#1113 anonymous-net behavior and actively
   *broke* what would otherwise have been a clean match. `layout/lvs_reference.py`
   no longer hardcodes body-net
   names: it takes `--layout-netlist <klt extract output>` and derives each
   device type's actual bulk net from that run's real extraction, then
   rewrites *only* the four bulk terminals of the reference netlist to
   match — a no-op today, and still correct if a future extraction deck (or
   a bitcell without ties drawn inside it) reintroduces a synthesized net.
2. **`klt extract` is flat-only**, by design ("Flat (not hierarchical)
   extraction, deliberately"). The committed array GDS *is* hierarchical (one
   bitcell cell, one `CellInstArray`) and the committed reference netlist is
   too (one `.subckt bitcell_6t` + 8,192 calls), but extraction flattens to
   49,152 top-level devices, so `klt lvs` cannot pair the two sides at all
   (`topology: circuit could not be matched to a counterpart`). Array/macro
   LVS therefore needs either hierarchy-preserving extraction or a reference
   flattening path. Filed as
   [klayout-tools#1085](https://github.com/2AMLogic/klayout-tools/issues/1085).
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
./layout/verify.sh            # ~3 min: adds the full-array DRC + extraction
./layout/verify.sh --quick    # ~20 s: bitcell + 3x3 tile only
```

It regenerates both GDS files, fails if either differs from the committed
bytes, then runs `klt precheck`, `klt drc`, `klt extract` and `klt lvs` and
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
python3 layout/lvs_reference.py design/netlist/bitcell_6t.spice \
    --layout-netlist /tmp/bc.spice -o /tmp/bc_ref.spice
klt lvs '{"layout":{"netlist":"/tmp/bc.spice","top":"sram_bitcell_6t"},
          "reference":{"netlist":"/tmp/bc_ref.spice","form":"subckt-call"}}'

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
| `klt stats` (bitcell) | `bbox_um: (0.0, 0.0) - (4.46, 5.39)`, 38 polygons |
| `klt stats` (array) | `bbox_um: (0.0, 0.0) - (142.72, 1379.84)` |

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
- Issue #23 — DRC/LVS/PEX sign-off, which consumes this layout: the PDK-native
  DRC deck, post-layout extraction with parasitics, and the append-only
  evidence trail.
- `2AMLogic/gf180-bandgap`, `layout/bandgap_top/generate.py` — the sibling
  canary whose construction pattern (bespoke `klayout.db` generator,
  deterministic GDSII writer options, `uv run --with klayout` invocation)
  this directory follows.
