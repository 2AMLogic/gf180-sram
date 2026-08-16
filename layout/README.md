# layout

Layout work for this repo is driven by
[klayout-tools](https://github.com/2AMLogic/klayout-tools) (`klt`), per
`CLAUDE.md`. This directory is T1 checklist item 2 ("Layout" —
`klayout-tools/docs/design-evidence-tiers.md`'s *Analog* column: "committed
GDS/OASIS, reproducibly generated or with documented provenance").

## Status, stated plainly: infrastructure only, not a real bitcell (2026-08-16)

**What is committed here is array-tiling/hierarchy generation infrastructure
plus an explicitly-labeled placeholder bitcell and array — not a real,
device-level SRAM layout.** T1 checklist item 1 (committed schematic sources
and derived netlist under `design/`, tracked as issue #21) had **not landed**
as of this writing — `design/` still holds only its placeholder README, so
there is no device sizing anywhere in this repo to lay out a real 6T bitcell
from. `spec/bitcell-decision.md` already flags that the custom bitcell's own
DRC waiver/special-rule status "is not yet established... in scope for
whichever issue does the actual bitcell layout" — that full-custom,
device-level design work is real, substantial, and belongs to a follow-up
once #21 lands, not to a placeholder built without a schematic.

Rather than leave `layout/` at its prior single-line placeholder README with
nothing committed, or block this issue entirely on #21, this directory
commits the part that does **not** depend on device sizing: a reproducible
generator that tiles one repeated cell into the ratified 256×32 array using
KLayout's native hierarchical array-instance primitive, plus a placeholder
bitcell cell (an outline box with no device geometry of any kind — see
`bitcell/generate.py`'s docstring) that exercises that tiling machinery end
to end. **Do not read the committed GDS files as evidence of a working
bitcell or macro.** No DRC, LVS, or electrical claim is made about either
file; `klt precheck` was run only as a layout-hygiene sanity check (see
below), not a design-rule or connectivity check.

Per `design-evidence-tiers.md`'s freshness/staleness rule, this directory
cannot pass T1 item 2 until a real bitcell (derived from #21's schematic) is
substituted for the placeholder and the array is regenerated from it — that
is the concrete follow-up this PR leaves open, not a silent claim of
completion.

## What's in this directory

```
layout/
  README.md                                   this file
  bitcell/
    generate.py                                draws the placeholder bitcell (klayout.db API)
    sram_bitcell_6t_PLACEHOLDER.gds             committed, deterministic placeholder GDS
  sram_256x32/
    generate.py                                 tiles the placeholder bitcell into a 256x32 array
    sram_256x32_PLACEHOLDER.gds                 committed, deterministic placeholder GDS
```

- `bitcell/sram_bitcell_6t_PLACEHOLDER.gds` — a single outline rectangle on
  `Metal1` (1.2 x 2.4 um, an illustrative round number *not* derived from any
  gf180mcu design rule or device sizing — see the script's "Dimensions"
  section) plus a text label. No `Poly2`, diffusion, well, or contact layer
  is drawn, so no downstream tool (`klt drc`, `klt extract`, `klt lvs`) could
  ever mistake it for a real transistor.
- `sram_256x32/sram_256x32_PLACEHOLDER.gds` — that placeholder cell
  instanced 256 rows x 32 columns (8,192 placements) as a **single**
  `klayout.db.CellInstArray` hierarchical instance (not 8,192 individually
  placed cells), plus illustrative perimeter text labels naming the ratified
  1RW port list from `spec/sram.md` (`A[7:0]`, `CEN`, `CLK`, `D[31:0]`,
  `Q[31:0]`, `GWEN`, `WEN`, `VDD`, `VSS`) at evenly-spaced, non-routed
  positions.

## What this proves and what it does not

**Proves**: the array-tiling and two-level hierarchy machinery (instancing
one cell many times as a single efficient array reference, building a
`bitcell -> array` GDS hierarchy, placing port labels at a macro boundary) —
exactly the tool surface `CLAUDE.md` calls out as untested here ("array
generation ... hierarchy handling ... are all tool surface nothing here has
touched"). Once a real bitcell lands, only `bitcell/generate.py`'s placeholder
box needs replacing with real device geometry — the array generator's tiling
call does not change.

**Does not prove**: anything about the bitcell's electrical function,
stability, or DRC/LVS cleanliness (there is no device geometry to check), the
macro's real physical size (the 1.2 x 2.4 um pitch is illustrative, not a
real bitcell footprint), or a real, routed pinout (the port labels mark
illustrative positions only).

## Tool investigation: why this isn't `klt gen` output

Checked directly against the installed tool (`klt 0.2.0`, gf180mcuC PDK,
`open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, per
`spec/bitcell-decision.md`), 2026-08-16:

- **`klt gen --list --pdk gf180mcuC`** enumerates eight named PCell
  generators: `bjt_array`, `bond_pad`, `diff_pair`, `esd_device`,
  `guard_ring`, `mos_array`, `res_array`, `resistor_strip`. All are generic
  matched-device analog primitives (arrays of identical unit devices,
  differential pairs, guard rings). None is a memory bitcell, a
  cross-coupled latch, or any block-specific generator — `klt gen` is
  primitive-first by design (per klayout-tools#346, closed as completed:
  arbitrary block layout is expected to compose these primitives, or go
  bespoke against `klayout.db` directly, not to gain a single "build my
  block" verb).
- **`klt gen-compose`** places already-generated `klt gen` blocks via a
  `placement.strategy` of `"row"` (single left-to-right strip) or
  `"explicit"` (each block at its own declared X/Y). Neither expresses a
  large regular 2-D tiling of one repeated block — composing a 256x32 array
  through `gen-compose` today would mean an `"explicit"` placement entry per
  one of 8,192 instances, an unreviewable request document. This is a real,
  generic tool gap, filed upstream:
  [klayout-tools#1053](https://github.com/2AMLogic/klayout-tools/issues/1053)
  ("gen-compose has no grid/repeat placement strategy"). Raw
  `klayout.db.CellInstArray` (used directly by `sram_256x32/generate.py`
  below) is the workaround, and is exactly the primitive `gen-compose`'s
  request schema is missing.
- **`klt` has no layout-*write* verb for arbitrary geometry** other than
  `klt draw` (deliberately dumb, no PDK awareness, no rule checking, built
  for known-bad DRC fixtures — not appropriate for a real macro). The
  established pattern for a real block on this toolkit, per the sibling
  gf180-bandgap canary's `layout/bandgap_top/generate.py`, is a bespoke
  script against the `klayout.db` (`pya`-compatible) Python API. This
  directory's two `generate.py` scripts follow that same pattern.

This reproduces and extends the gap `spec/bitcell-decision.md` already
predicted ("Expect the tools to be weakest at the array and abstract
stages") — there is no `klt gen` generator family for the class of device
this repo's bitcell actually is (a differential cross-coupled 6T latch), and
no efficient large-array composition path through `gen-compose` either.

## Install `klt`

```bash
uv tool install git+https://github.com/2AMLogic/klayout-tools
# or: pip install git+https://github.com/2AMLogic/klayout-tools
klt --version   # 0.2.0 as of this writing
```

`klt` runs fully headless via the pip `klayout` package's native
`klayout.db` primitives — no KLayout GUI/application binary, no `DISPLAY`,
no Qt.

## Reproducing the committed GDS

From the repo root:

```bash
# 1. Placeholder bitcell (byte-for-byte deterministic -- git diff stays empty)
uv run --with klayout python3 layout/bitcell/generate.py

# 2. Placeholder 256x32 array, tiling the same bitcell cell
uv run --with klayout python3 layout/sram_256x32/generate.py

# Layout-hygiene sanity check (not a DRC/LVS claim -- see "What this proves
# and what it does not" above)
klt precheck --deck gf180mcu layout/bitcell/sram_bitcell_6t_PLACEHOLDER.gds
klt precheck --deck gf180mcu layout/sram_256x32/sram_256x32_PLACEHOLDER.gds

# Basic geometry/hierarchy inspection
klt stats layout/sram_256x32/sram_256x32_PLACEHOLDER.gds
klt cells layout/sram_256x32/sram_256x32_PLACEHOLDER.gds
```

`uv run --with klayout` pulls the pip `klayout` package into an ephemeral
venv on first run — no repo-local Python environment to set up.

Both generators write GDS with GDSII header timestamps disabled, so
re-running leaves `git diff` empty (verified at commit time by diffing a
fresh run against the committed files).

Expected results (as committed, 2026-08-16):

| Check | Result |
|---|---|
| `bitcell/generate.py` re-run | byte-identical to the committed GDS |
| `sram_256x32/generate.py` re-run | byte-identical to the committed GDS |
| `klt precheck --deck gf180mcu` (bitcell) | `status: pass` (zero_area, cell_names, pin_labels_over_drawing all pass; offgrid/layer_whitelist skipped, no `--grid-um`/`--allowed-layers` given) |
| `klt precheck --deck gf180mcu` (array) | `status: pass`, same checks |
| `klt stats` (array) | `bbox_um: (0.0, -6.0) - (38.4, 614.4)`, 2 polygons, one `CellInstArray` child instance |

## Tool/PDK versions

- `klt` 0.2.0
- `klayout` pip package (via `uv run --with klayout`, no version pinned
  beyond what `uv` resolves at run time — see the "known gap" note below)
- gf180mcu PDK: `gf180mcuC` variant, `open_pdks` commit
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (per
  `spec/bitcell-decision.md`, cached under `~/.volare/gf180mcuC`)

**Known gap, noted rather than fixed in this PR**: neither `generate.py`
script pins an exact `klayout` package version, so a future run could pick up
a newer release with different default behavior. `layout/bandgap_top`'s own
established pattern in the sibling gf180-bandgap repo has the same property
(`uv run --with klayout`, unpinned) — this repo follows that existing
convention rather than diverging from it unilaterally; pinning is a
reasonable follow-up but is not this issue's scope.

## Freshness / staleness (per `design-evidence-tiers.md`)

This layout is **not** derived from any schematic or netlist — none exists
yet. It therefore cannot be graded "fresh" against design sources the way
`design-evidence-tiers.md`'s staleness rule expects; it is explicitly
pre-design scaffolding, not a T1 item-2 pass. Once #21 lands:

1. Replace `bitcell/generate.py`'s placeholder outline with a real
   transistor-level 6T bitcell layout derived from the committed schematic
   (its own DRC waiver/special-rule survey per `spec/bitcell-decision.md`)
   — separate, substantial full-custom design work, not a mechanical swap.
2. Re-run `sram_256x32/generate.py` unchanged (the tiling call is already
   parameterized on the bitcell's committed footprint) to produce the real
   256x32 array.
3. Run `klt drc` / `klt extract` / `klt lvs` against the real array
   (tracked under issue #23) to establish T1 items 3/4.

Until step 1 lands, this directory's own freshness state is "blocked on
#21," not "stale" — there is no prior real layout to go stale relative to.

## References

- `spec/sram.md` — ratified organization (256x32, 1RW) and port list this
  directory's illustrative labels reflect.
- `spec/bitcell-decision.md` — the decision to draw a custom bitcell/array
  rather than integrate `gf180mcu_fd_ip_sram`, and its note that the custom
  bitcell's DRC waiver status is not yet established.
- Issue #21 — commits the schematic/netlist this directory's real bitcell
  will be derived from (soft dependency, not yet landed as of this PR).
- Issue #23 — DRC/LVS/PEX verification, which consumes a real (non-placeholder)
  layout from this directory.
- [klayout-tools#1053](https://github.com/2AMLogic/klayout-tools/issues/1053)
  — the `gen-compose` grid/repeat placement gap filed from this
  investigation.
- [klayout-tools#346](https://github.com/2AMLogic/klayout-tools/issues/346)
  (closed, completed) — the prior friction record establishing that `klt
  gen`/`gen-compose` are primitive-first by design and a bespoke
  `klayout.db` generator is the sanctioned pattern for a real block, which
  this directory's two `generate.py` scripts follow.
- `2AMLogic/gf180-bandgap`, `layout/bandgap_top/generate.py` — the sibling
  canary this directory's construction pattern (bespoke `klayout.db`
  generator, deterministic GDSII writer options, `uv run --with klayout`
  invocation) is drawn from.
