#!/usr/bin/env python3
"""Generate ``sram_256x32_array.gds`` — the 256 x 32 bitcell-array layout.

Tiles ``layout/bitcell/generate.py``'s device-level 6T bitcell into the
``spec/sram.md``-ratified 256-word x 32-bit organization, matching
``design/sram_256x32_array.sch`` / ``design/netlist/sram_256x32_array.spice``
(issue #21) cell-for-cell and port-for-port.

## Scope: the storage array core, matching design/

Like the schematic side, this is the bitcell-array **core** — 8,192 storage
cells plus their wordline / bitline / supply connections. Address decode,
column mux, sense amps and write drivers (the rest of ``spec/sram.md``'s 1RW
pin list: ``A``, ``CEN``, ``CLK``, ``D``, ``Q``, ``GWEN``, ``WEN``) are
periphery and are not drawn here, exactly as ``design/README.md`` scopes the
schematic. The array's own ports are therefore the raw per-row/per-column
pins the netlist declares::

    WL0..WL255, BL0..BL31, BLB0..BLB31, VDD, VSS

## How the array is built

The bitcell tiles by **abutment**: it spans its own pitch with the wires that
have to run through it (Poly2 wordline across the full cell width, Metal1
bitlines and Metal2 supply rails across the full cell height, Nwell across the
full cell width), so a plain 256 x 32 instance array wires itself:

* each row's 32 cells share one continuous Poly2 wordline -> ``WL<row>``
* each column's 256 cells share one continuous Metal1 bitline pair ->
  ``BL<col>`` / ``BLB<col>``
* each column's supply rails are continuous Metal2 stripes

The placements are one ``kdb.CellInstArray`` — a single hierarchical instance
covering all 8,192 sites, not 8,192 individually placed cells.

The one thing abutment alone does *not* finish is joining the 32 per-column
supply stripes to each other. Two Metal3 straps (one ``VDD``, one ``VSS``)
run across the array and drop a Via2 onto every column's corresponding Metal2
stripe, which is what makes ``VDD``/``VSS`` single nets across the whole array
rather than 32 isolated column rails. They are the array's only non-bitcell
geometry.

## Determinism

Run from the repo root::

    uv run --with klayout python3 layout/sram_256x32/generate.py

GDSII header timestamps are disabled, so re-running produces a byte-identical
file and ``git diff`` stays empty. ``--rows``/``--cols`` build a smaller tile
(e.g. ``--rows 3 --cols 3`` for the abutment DRC check in
``layout/verify.sh``) without touching the committed full-size array.
"""

from __future__ import annotations

import argparse
import os
import sys

import klayout.db as kdb

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bitcell")
)
import generate as bitcell  # noqa: E402  (local sibling module, see sys.path above)

ROWS = 256
COLS = 32

TOP_CELL = "sram_256x32_array"

# Array-level layers (the bitcell itself draws nothing above Metal2).
L_VIA2 = (38, 0)
L_METAL3 = (42, 0)
L_METAL3_LBL = (42, 10)

_LAYER_NAMES = {
    L_VIA2: "Via2",
    L_METAL3: "Metal3",
    L_METAL3_LBL: "Metal3_Label",
}

# Metal3 supply straps (see the module docstring). Drawn inside the top row's
# band so they overlap the Metal2 column stripes they via down onto.
V2_SIZE = 0.26  # V2.1
V2_ENC_M3 = 0.06  # V2.4 (0.01) + margin
M3_STRAP_W = V2_SIZE + 2 * V2_ENC_M3  # 0.38, >= M3.1 (0.28)
M3_SPACE = 0.30  # M3.2a (0.28) + 0.02
STRAP_VSS_OFFSET = 0.20  # from the top row's own origin
STRAP_VDD_OFFSET = STRAP_VSS_OFFSET + M3_STRAP_W + M3_SPACE


def _layer(layout: kdb.Layout, lp: tuple[int, int]) -> int:
    index = layout.layer(*lp)
    name = _LAYER_NAMES.get(lp)
    if name is not None:
        layout.set_info(index, kdb.LayerInfo(*lp, name))
    return index


def _insert_box(layout: kdb.Layout, cell: kdb.Cell, lp: tuple[int, int],
                x0: float, y0: float, x1: float, y1: float) -> None:
    cell.shapes(_layer(layout, lp)).insert(
        kdb.Box.from_dbox(kdb.DBox(x0, y0, x1, y1) * (1.0 / layout.dbu))
    )


def _insert_text(layout: kdb.Layout, cell: kdb.Cell, lp: tuple[int, int],
                 text: str, x: float, y: float) -> None:
    cell.shapes(_layer(layout, lp)).insert(
        kdb.Text(
            text,
            kdb.Trans(int(round(x / layout.dbu)), int(round(y / layout.dbu))),
        )
    )


def build(rows: int = ROWS, cols: int = COLS) -> kdb.Layout:
    layout = kdb.Layout()
    layout.dbu = 0.001  # 1 dbu = 1 nm

    # Draw the bitcell into *this* layout (KLayout's array-instance primitive
    # needs the instanced cell and the array's top cell in one `Layout`), with
    # labels suppressed: the array names its own per-row/per-column nets below,
    # so 8,192 copies of the cell-level pin labels would be 8,192 same-named
    # texts on 32 (or 256) physically distinct nets.
    cell = layout.create_cell(bitcell.TOP_CELL)
    bitcell.draw(layout, cell, with_labels=False)

    top = layout.create_cell(TOP_CELL)

    pitch_x = int(round(bitcell.W_CELL / layout.dbu))
    pitch_y = int(round(bitcell.H_CELL / layout.dbu))
    top.insert(
        kdb.CellInstArray(
            cell.cell_index(),
            kdb.Trans(0, 0),
            kdb.Vector(pitch_x, 0),  # column step
            kdb.Vector(0, pitch_y),  # row step
            cols,
            rows,
        )
    )

    array_w = bitcell.W_CELL * cols

    # -- Metal3 supply straps + Via2 down to every column's Metal2 stripe --
    strap_y0 = (rows - 1) * bitcell.H_CELL
    straps = (
        ("VSS", strap_y0 + STRAP_VSS_OFFSET, bitcell.X_VSS_M2_C),
        ("VDD", strap_y0 + STRAP_VDD_OFFSET, bitcell.X_VDD_M2_C),
    )
    for name, y0, stripe_cx in straps:
        y1 = y0 + M3_STRAP_W
        _insert_box(layout, top, L_METAL3, 0.0, y0, array_w, y1)
        cy = 0.5 * (y0 + y1)
        for col in range(cols):
            cx = col * bitcell.W_CELL + stripe_cx
            _insert_box(
                layout, top, L_VIA2,
                cx - 0.5 * V2_SIZE, cy - 0.5 * V2_SIZE,
                cx + 0.5 * V2_SIZE, cy + 0.5 * V2_SIZE,
            )
        _insert_text(layout, top, L_METAL3_LBL, name, 0.5 * array_w, cy)

    # -- Port labels: one per physical net, on the net's own drawn shape --
    for col in range(cols):
        x0 = col * bitcell.W_CELL
        y = 0.5 * bitcell.H_CELL
        _insert_text(layout, top, bitcell.L_METAL1_LBL, f"BL{col}",
                     x0 + bitcell.X_BL_C, y)
        _insert_text(layout, top, bitcell.L_METAL1_LBL, f"BLB{col}",
                     x0 + bitcell.X_BLB_C, y)
    wl_y = 0.5 * (bitcell.Y_WL_BOT + bitcell.Y_WL_TOP)
    wl_x = 0.5 * bitcell.MARGIN_X
    for row in range(rows):
        _insert_text(layout, top, bitcell.L_POLY2_LBL, f"WL{row}",
                     wl_x, row * bitcell.H_CELL + wl_y)

    return layout


def save_options() -> kdb.SaveLayoutOptions:
    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=ROWS)
    parser.add_argument("--cols", type=int, default=COLS)
    parser.add_argument("-o", "--out", default=None)
    args = parser.parse_args()

    out_path = args.out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), f"{TOP_CELL}.gds"
    )
    build(args.rows, args.cols).write(out_path, save_options())
    print(f"wrote {out_path}")
    print(
        f"{args.rows} rows x {args.cols} cols = {args.rows * args.cols} cells, "
        f"{bitcell.W_CELL * args.cols:.3f} x {bitcell.H_CELL * args.rows:.3f} um "
        f"({bitcell.W_CELL * args.cols * bitcell.H_CELL * args.rows / 1e6:.6f} mm^2)"
    )


if __name__ == "__main__":
    main()
