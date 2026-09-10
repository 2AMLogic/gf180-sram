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
rather than 32 isolated column rails.

## The wordline landing-pad strip (issue #121)

Abutment leaves each ``WL<row>`` as bare Poly2. Poly2 is not a ``TYPE
ROUTING`` layer in gf180mcu's tech LEF, so a wordline that carries nothing but
Poly2 has no pin geometry a router — or ``klt lef-abstract``, or a physical
row decoder — could ever land on: the array's first LEF abstract (issue #120,
``views/README.md``) reported all 256 ``WL<row>`` pins as
``geometry_source: "none"``, in ``unroutable_pins[]``.

So the array reserves a narrow strip of periphery, :data:`WL_PAD_BAND` wide,
to the **left** of the tiled cells (where a row decoder would sit) and draws,
per row, a Poly2 landing pad that abuts that row's wordline stripe, one
Poly2-to-Metal1 contact on it, and a Metal1 pad — and labels ``WL<row>`` on
the *Metal1* pad rather than on the Poly2 stripe. The tiled cells are placed
at ``x = WL_PAD_BAND`` so the strip, not negative space, holds the array's
left boundary.

The strip and the two Metal3 straps are the array's only non-bitcell geometry.

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

# ---------------------------------------------------------------------------
# Wordline landing pads (see the module docstring's own section).
#
# Every dimension here is derived from layout/bitcell/generate.py's own
# DRM-cited contact/enclosure constants — the same ones the bitcell's *own*
# Poly2 landing pads (``Y_CO_JOG_Q`` / ``Y_CO_JOG_QB``) are built from — so
# this periphery is drawn to exactly the rule margins of the cell it abuts,
# with no new hand-picked numbers.
# ---------------------------------------------------------------------------
# Poly2 pad: a wordline stripe is only POLY_WIDTH (0.26) tall, which cannot
# hold a 0.22 contact with CO.3 enclosure on both edges, so the pad is the
# locally-widened Poly2 the contact needs (0.38), exactly like the bitcell's
# cross-couple jogs.
WL_PAD_POLY_H = bitcell.CO_SIZE + 2 * bitcell.CO_ENC_POLY  # 0.38 (CO.3)
# Contact column. Poly2's enclosure (CO.3, 0.08 here) is the wider of the two
# enclosures, so it — not Metal1's (CO.6a/CO.6b, 0.07) — sets how far in from
# the array's left boundary the cut sits.
WL_PAD_CO_CX = round(bitcell.CO_ENC_POLY + 0.5 * bitcell.CO_SIZE, 3)  # 0.19
# Metal1 pad: starts flush with the array's left boundary (so the pin is
# reachable from outside the macro) and ends one CO.6a/CO.6b enclosure past
# the cut.
WL_PAD_M1_W = round(WL_PAD_CO_CX + 0.5 * bitcell.CO_SIZE + bitcell.CO_ENC_M1, 3)
# M1.3 (minimum Metal1 area, 0.1444 um^2) and CO.6a (the 0.34 um narrow-metal
# end-of-line overlap it would otherwise take) are both *outside* klt's
# curated gf180mcu deck, so — like the bitcell's own margins — they are
# satisfied by construction rather than by a check: the pad is made tall
# enough that neither can bind, and :data:`_WL_PAD_M1_AREA_OK` asserts it.
M1_MIN_AREA = 0.1444  # M1.3
M1_NARROW = 0.34  # CO.6a applies only to Metal1 narrower than this
WL_PAD_M1_H = 0.42
# Band width: the pad's Metal1 has to clear column 0's BL stripe by M1.2a.
WL_PAD_BAND = round(
    WL_PAD_M1_W
    + bitcell.M1_SPACE
    - (bitcell.X_BL_C - 0.5 * bitcell.M1_STRIPE_W),
    3,
)

_WL_PAD_M1_AREA_OK = WL_PAD_M1_W * WL_PAD_M1_H
assert _WL_PAD_M1_AREA_OK >= M1_MIN_AREA, "WL landing pad violates M1.3"
assert min(WL_PAD_M1_W, WL_PAD_M1_H) >= M1_NARROW, "WL landing pad invites CO.6a"
assert WL_PAD_BAND >= WL_PAD_M1_W, "WL landing pad overruns its own band"


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
    # The tiled cells sit one wordline-landing-pad band in from x = 0, so the
    # pad strip — not empty space — holds the array's left boundary.
    x_off = WL_PAD_BAND
    top.insert(
        kdb.CellInstArray(
            cell.cell_index(),
            kdb.Trans(int(round(x_off / layout.dbu)), 0),
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
        _insert_box(layout, top, L_METAL3, x_off, y0, x_off + array_w, y1)
        cy = 0.5 * (y0 + y1)
        for col in range(cols):
            cx = x_off + col * bitcell.W_CELL + stripe_cx
            _insert_box(
                layout, top, L_VIA2,
                cx - 0.5 * V2_SIZE, cy - 0.5 * V2_SIZE,
                cx + 0.5 * V2_SIZE, cy + 0.5 * V2_SIZE,
            )
        _insert_text(layout, top, L_METAL3_LBL, name, x_off + 0.5 * array_w, cy)

    # -- Wordline landing pads: one Poly2 pad + contact + Metal1 pad per row --
    #
    # The Poly2 pad abuts (does not overlap) the row's own wordline stripe at
    # x = x_off, the same edge-to-edge contract every other connection in this
    # array already relies on — bitline stripes join cell-to-cell the same way.
    wl_y = 0.5 * (bitcell.Y_WL_BOT + bitcell.Y_WL_TOP)
    for row in range(rows):
        cy = row * bitcell.H_CELL + wl_y
        _insert_box(
            layout, top, bitcell.L_POLY2,
            0.0, cy - 0.5 * WL_PAD_POLY_H, x_off, cy + 0.5 * WL_PAD_POLY_H,
        )
        _insert_box(
            layout, top, bitcell.L_CONTACT,
            WL_PAD_CO_CX - 0.5 * bitcell.CO_SIZE, cy - 0.5 * bitcell.CO_SIZE,
            WL_PAD_CO_CX + 0.5 * bitcell.CO_SIZE, cy + 0.5 * bitcell.CO_SIZE,
        )
        _insert_box(
            layout, top, bitcell.L_METAL1,
            0.0, cy - 0.5 * WL_PAD_M1_H, WL_PAD_M1_W, cy + 0.5 * WL_PAD_M1_H,
        )

    # -- Port labels: one per physical net, on the net's own drawn shape --
    for col in range(cols):
        x0 = x_off + col * bitcell.W_CELL
        y = 0.5 * bitcell.H_CELL
        _insert_text(layout, top, bitcell.L_METAL1_LBL, f"BL{col}",
                     x0 + bitcell.X_BL_C, y)
        _insert_text(layout, top, bitcell.L_METAL1_LBL, f"BLB{col}",
                     x0 + bitcell.X_BLB_C, y)
    # WL<row> is labelled on its Metal1 landing pad, not on the Poly2 stripe:
    # Poly2 is not a routing-type layer, so a Poly2-labelled wordline has no
    # pin geometry any abstract or router can use (issue #121).
    for row in range(rows):
        _insert_text(layout, top, bitcell.L_METAL1_LBL, f"WL{row}",
                     0.5 * WL_PAD_M1_W, row * bitcell.H_CELL + wl_y)

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
    layout = build(args.rows, args.cols)
    layout.write(out_path, save_options())
    bbox = layout.cell(TOP_CELL).bbox()
    dbu = layout.dbu
    width = bbox.width() * dbu
    height = bbox.height() * dbu
    print(f"wrote {out_path}")
    print(
        f"{args.rows} rows x {args.cols} cols = {args.rows * args.cols} cells, "
        f"{width:.3f} x {height:.3f} um ({width * height / 1e6:.6f} mm^2) "
        f"-- {bitcell.W_CELL * args.cols:.3f} um of tiled cells plus a "
        f"{WL_PAD_BAND:.3f} um wordline landing-pad band"
    )


if __name__ == "__main__":
    main()
