#!/usr/bin/env python3
"""Generate ``sram_bitcell_6t_PLACEHOLDER.gds`` — NOT a real bitcell layout.

## Why this exists, and why it is a placeholder

`spec/bitcell-decision.md` ratified drawing a custom 6T bitcell (Option 2)
rather than integrating gf180mcu's hardened `gf180mcu_fd_ip_sram` macro.
Drawing that bitcell for real means placing and sizing six transistors from
a schematic/netlist — but T1 checklist item 1 (committed schematic sources
and derived netlist under `design/`, tracked as issue #21) has **not landed
yet** as of this script's authoring. There is no device sizing anywhere in
this repo to lay out.

Rather than block issue #22 entirely on #21, or fabricate transistor-level
geometry with invented sizing (which would misrepresent a real bitcell),
this script draws an explicitly-labeled **placeholder footprint**: a single
outline rectangle plus a text label, on `Metal1` only — no `Poly2`, no
diffusion, no well, no contacts. It contains no device geometry of any kind,
so no downstream tool (`klt drc`, `klt extract`, `klt lvs`) could ever read
it as a real transistor even by accident. Its only purpose is to prove the
**array-tiling/hierarchy machinery** in `layout/sram_256x32/generate.py` end
to end (instance arraying, port-label placement) ahead of the real device
geometry landing — see `layout/README.md` for the full status and the
tool-capability gap this stands in for (no `klt gen` generator exists for a
cross-coupled 6T SRAM bitcell; filed generically upstream).

**Do not treat this GDS as evidence of anything DRC/LVS/electrical.** It is
scaffolding for the array-generation flow, not a candidate bitcell.

## Dimensions

`BITCELL_WIDTH_UM` / `BITCELL_HEIGHT_UM` below are illustrative only — a
round number in the range of published 180 nm-class 6T bitcell footprints,
*not* derived from any gf180mcu design rule, foundry reference bitcell
measurement, or device sizing (none of which exist yet for this repo's own
cell). Once #21 lands, this script is where the real bitcell polygons (or a
generator call) replace the placeholder box, and these constants are
replaced by the real footprint the sized devices actually require.

## Determinism

Run from the repo root::

    uv run --with klayout python3 layout/bitcell/generate.py

GDSII header timestamps are disabled (see `save_options()`), so re-running
produces a byte-identical file and `git diff` stays empty.
"""

from __future__ import annotations

import os

import klayout.db as kdb

# gf180mcu GDS layer/datatype pairs (from the PDK's own
# libs.tech/klayout/tech/gf180mcu.lyp / .map), reused from the convention
# `layout/README.md` documents and the sibling gf180-bandgap repo's
# `layout/bandgap_top/generate.py` establishes for this same PDK.
L_METAL1 = (34, 0)
L_METAL1_LBL = (34, 10)

# Illustrative placeholder footprint only -- see module docstring "Dimensions".
BITCELL_WIDTH_UM = 1.2
BITCELL_HEIGHT_UM = 2.4

TOP_CELL = "sram_bitcell_6t_PLACEHOLDER"


def draw(layout: kdb.Layout, top: kdb.Cell) -> None:
    """Draw the placeholder footprint into ``top``, an already-created cell
    in ``layout``.

    Factored out of :func:`build` so ``layout/sram_256x32/generate.py`` can
    draw this exact same cell directly into *its own* ``kdb.Layout``
    (KLayout's array-instance primitive needs the instanced cell and the
    array's top cell to live in one `Layout`) instead of merging two
    separately-built layouts together.
    """
    metal1 = layout.layer(*L_METAL1)
    layout.set_info(metal1, kdb.LayerInfo(*L_METAL1, "Metal1"))
    metal1_lbl = layout.layer(*L_METAL1_LBL)
    layout.set_info(metal1_lbl, kdb.LayerInfo(*L_METAL1_LBL, "Metal1_Label"))

    w = int(round(BITCELL_WIDTH_UM / layout.dbu))
    h = int(round(BITCELL_HEIGHT_UM / layout.dbu))

    # A single outline box -- no device layers of any kind. This is
    # deliberate: it must never be mistaken for a real transistor.
    top.shapes(metal1).insert(kdb.Box(0, 0, w, h))

    label = kdb.Text("PLACEHOLDER_NOT_A_REAL_BITCELL_SEE_ISSUE_21", kdb.Trans(0, 0))
    top.shapes(metal1_lbl).insert(label)


def build() -> kdb.Layout:
    layout = kdb.Layout()
    layout.dbu = 0.001  # 1 dbu = 1 nm
    top = layout.create_cell(TOP_CELL)
    draw(layout, top)
    return layout


def save_options() -> kdb.SaveLayoutOptions:
    """Writer options that make the emitted GDS byte-stable (see module
    docstring "Determinism")."""
    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "sram_bitcell_6t_PLACEHOLDER.gds")
    build().write(out_path, save_options())
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
