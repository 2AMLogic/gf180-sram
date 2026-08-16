#!/usr/bin/env python3
"""Generate ``sram_256x32_PLACEHOLDER.gds`` — NOT a real macro layout.

## What this proves, and what it does not

`spec/sram.md` ratifies a 256-word x 32-bit (1 kB), single fixed-instance,
1RW macro. This script tiles `layout/bitcell/generate.py`'s placeholder
bitcell into a 256-row x 32-column grid using KLayout's native array-instance
primitive (`kdb.CellInstArray`) — the same array-tiling and hierarchy
mechanism a real bitcell-to-array build would use — and adds perimeter text
labels naming the ratified port list at illustrative positions.

This exercises exactly the tool surface `CLAUDE.md` flags as untested
("array generation, macro-level LVS, hierarchy handling ... are all tool
surface nothing here has touched"): instancing one cell ~8,192 times as a
single efficient array reference (not 8,192 individually-placed cells),
building a two-level GDS hierarchy (array -> bitcell), and placing pin
labels at a macro boundary. All of that machinery is real and reusable.

**What is not real**: the underlying bitcell (see
`layout/bitcell/generate.py`'s docstring — an outline box with no device
geometry) and therefore this array. No claim of DRC/LVS cleanliness,
electrical correctness, or the actual macro footprint is made by this file.
Port label positions are illustrative placement, not a routed pinout.

## Port list

Per `spec/sram.md` ("Ports: 1RW first"), matching `gf180mcu_fd_ip_sram`'s
1RW pin interface shape, scaled to this macro's own organization:

- `A[7:0]`   — address (256 words needs 8 bits)
- `CEN`      — chip enable
- `CLK`      — clock
- `D[31:0]`  — write data (32 bits)
- `Q[31:0]`  — read data (32 bits)
- `GWEN`     — global write enable
- `WEN`      — write enable
- `VDD`, `VSS` — supplies

`spec/sram.md` does not (yet) ratify `WEN`'s per-bit granularity (a single
bit vs. per-byte lanes, the way the foundry macro's `WEN[7:0]` covers its
8-bit data path) — that is schematic-level detail deferred to whichever
design lands #21. This placeholder labels a single `WEN`, the simplest
reading, and is not itself a granularity ratification.

## Determinism

Run from the repo root::

    uv run --with klayout python3 layout/sram_256x32/generate.py

GDSII header timestamps are disabled, so re-running produces a
byte-identical file and `git diff` stays empty.
"""

from __future__ import annotations

import os
import sys

import klayout.db as kdb

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bitcell"))
import generate as bitcell_gen  # noqa: E402  (local sibling module, see sys.path above)

ROWS = 256
COLS = 32

TOP_CELL = "sram_256x32_PLACEHOLDER"

L_METAL1 = bitcell_gen.L_METAL1
L_METAL1_LBL = bitcell_gen.L_METAL1_LBL

# Ratified 1RW port list (see module docstring "Port list"), labeled along
# the macro's bottom edge at illustrative, evenly-spaced positions -- not a
# routed pinout.
PORT_LABELS = [
    "A[7:0]",
    "CEN",
    "CLK",
    "D[31:0]",
    "Q[31:0]",
    "GWEN",
    "WEN",
    "VDD",
    "VSS",
]


def build() -> kdb.Layout:
    layout = kdb.Layout()
    layout.dbu = 0.001  # 1 dbu = 1 nm

    # Draw the bitcell cell directly into *this* layout (not the separate
    # `kdb.Layout` the standalone `layout/bitcell/generate.py` invocation
    # creates) -- KLayout's array-instance primitive needs the instanced
    # cell and the array's top cell to live in the same `Layout`. Same
    # `draw()` call, same geometry, so this array's bitcell instance is
    # byte-for-byte identical to the standalone
    # `sram_bitcell_6t_PLACEHOLDER.gds`.
    bitcell_cell = layout.create_cell(bitcell_gen.TOP_CELL)
    bitcell_gen.draw(layout, bitcell_cell)

    top = layout.create_cell(TOP_CELL)

    metal1 = layout.layer(*L_METAL1)
    layout.set_info(metal1, kdb.LayerInfo(*L_METAL1, "Metal1"))
    metal1_lbl = layout.layer(*L_METAL1_LBL)
    layout.set_info(metal1_lbl, kdb.LayerInfo(*L_METAL1_LBL, "Metal1_Label"))

    w = int(round(bitcell_gen.BITCELL_WIDTH_UM / layout.dbu))
    h = int(round(bitcell_gen.BITCELL_HEIGHT_UM / layout.dbu))

    # One CellInstArray -- a single hierarchical instance covering all
    # ROWS x COLS placements, not ROWS*COLS individually-placed cells.
    array = kdb.CellInstArray(
        bitcell_cell.cell_index(),
        kdb.Trans(0, 0),
        kdb.Vector(w, 0),  # column step
        kdb.Vector(0, h),  # row step
        COLS,
        ROWS,
    )
    top.insert(array)

    array_w = w * COLS
    array_h = h * ROWS

    # Macro boundary outline, offset below the bitcell array, so the array
    # and the macro frame are visibly distinct in a viewer.
    frame_margin = int(round(2.0 / layout.dbu))
    frame_h = int(round(4.0 / layout.dbu))
    top.shapes(metal1).insert(
        kdb.Box(0, -frame_h - frame_margin, array_w, -frame_margin)
    )

    # Evenly-spaced, illustrative port labels along the macro frame.
    step = array_w // (len(PORT_LABELS) + 1)
    label_y = -frame_h // 2 - frame_margin
    for i, name in enumerate(PORT_LABELS, start=1):
        top.shapes(metal1_lbl).insert(kdb.Text(name, kdb.Trans(step * i, label_y)))

    # Placed inside the frame box (not below it) so `klt precheck`'s
    # pin_labels_over_drawing check -- which flags any Metal1_Label text not
    # landing on drawn Metal1 -- passes cleanly; this text is an annotation,
    # not a routed pin, but sitting over drawn geometry is good label
    # hygiene regardless.
    top.shapes(metal1_lbl).insert(
        kdb.Text(
            "PLACEHOLDER_NOT_A_REAL_ARRAY_SEE_ISSUE_21_AND_22",
            kdb.Trans(array_w // 2, label_y),
        )
    )

    return layout


def save_options() -> kdb.SaveLayoutOptions:
    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "sram_256x32_PLACEHOLDER.gds")
    build().write(out_path, save_options())
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
