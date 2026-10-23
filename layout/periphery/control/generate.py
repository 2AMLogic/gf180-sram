#!/usr/bin/env python3
"""Generate the control block ``sram_ctrl`` and the column decoder ``col_decode``.

Issue #246 (child of #206). Draws ``design/netlist/sram_ctrl.spice`` (address /
enable flops, the self-timed pulse and enable generators and their long-channel
delay chains) and ``design/netlist/col_decode.spice`` (the 2->4 column decoder
with its true / complement drivers) as **two separate flat cells**, because the
macro top instantiates them separately (``XXctrl`` / ``XXcol``) and the
assembly (#247) places them separately.

## How they are drawn

This reuses ``layout/periphery/column/generate.py`` unchanged apart from one
generalisation (poly width follows the device's own ``L``, so the ``L = 0.6 um``
delay inverter can be drawn) -- its netlist reader, strip placer
(``layout_strip``) and maze router -- the way ``layout/periphery/row/generate.py``
does, and borrows that file's per-strip rail / implant / strap helpers. Device
sizes and connectivity come from the netlists; the only hand-made placement
input is :func:`cell_chains` (which devices share diffusion, in what order) and
the strip tables in :data:`SRAM_CTRL_STRIPS` / :data:`COL_DECODE_STRIPS`.

New cell kinds relative to the row / column paths:

* ``dff`` -- ``tg_s`` + ``inv`` based master/slave flop. Its devices flatten to
  the primitive transistors the placer already handles; the chain table is the
  column path's :func:`dff_chains`, shifted to the cell's first column.
* ``inv_dly`` -- ``L = 0.6 um`` inverter. Two consecutive delay stages share
  their supply diffusion (``y1 | g | VDD | g | y2``), so a chain of ``n`` stages
  is ``ceil(n / 2)`` five-column cells.
* ``inv_x4`` / ``inv_x8`` / ``inv_x16`` -- single-finger inverters with
  ``W = 4 / 8 / 16 um`` (P) drawn as one tall transistor, as in the netlist.

## Pin edges (provisional until the macro assembly, #247)

Pins are ``Metal2`` stubs reaching the cell edge, each labelled on ``Metal2``.
``VDD`` / ``VSS`` are the labelled ``Metal2`` straps at the left of the cell.

``sram_ctrl``
  * bottom edge: ``A0..A7``, ``CEN``, ``GWEN``, ``CLK`` (macro inputs) and the
    column-band outputs ``clk_buf``, ``wl_en_n``, ``s_en``, ``q_clk``, ``wpn``
    (the io-band buses sit below the array);
  * top edge: ``aq0..aq7``, ``aqb0..aqb7``, ``wl_en`` (row path / ``col_decode``).

``col_decode``
  * bottom edge: ``aq0``, ``aqb0``, ``aq1``, ``aqb1``, ``wl_en``;
  * top edge: ``csel0..3``, ``cseln0..3``.

## What is NOT claimed

Not area-optimised and nothing about timing: the delay chains are drawn to the
netlist's device sizes only; delay calibration, wire RC and parasitics are not
modelled or measured. The pin edges above are a provisional choice that #247
may revisit (it routes to them), not a floorplan.

Run from the repo root::

    uv run --with klayout python3 layout/periphery/control/generate.py

No timestamps, no randomness, so a re-run reproduces the committed GDS
byte-for-byte.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

import klayout.db as kdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _load(name: str, rel: str):
    path = os.path.join(ROOT, rel)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


row = _load("_sram_row_generate", "layout/periphery/row/generate.py")
col = row.col  # the row generator's instance: module globals (NCOLS) must be shared

G = col.G
C0 = 3  # first chain column (columns 0 / 1 carry the VSS / VDD straps)
GAP = 1  # empty columns between cells of one strip
STRIP_SEP = 5  # rows between one strip's top rail and the next strip's bottom rail
INV_KINDS = {"inv": 1, "inv_x4": 1, "inv_x8": 1, "inv_x16": 1, "inv_dly": 1}
PIN_C0 = 4  # first pin column
EDGE_ROWS = 3  # rows of clear space between the outermost rail and a pin edge


def netlist(block: str) -> str:
    return os.path.join(col.NETLIST_DIR, f"{block}.spice")


# ---------------------------------------------------------------------------
# Floorplans: strips bottom to top; an item is (kind, [instances]) -- an
# inverter-like kind takes one or two instances (two share supply diffusion).
# ---------------------------------------------------------------------------
def _pairs(prefix: str, lo: int, hi: int) -> list:
    names = [f"X{prefix}{i}" for i in range(lo, hi)]
    return [("inv_dly", names[i:i + 2]) for i in range(0, len(names), 2)]


SRAM_CTRL_STRIPS = [
    ("dly_ctl", _pairs("dd", 0, 6) + _pairs("db", 0, 6) + _pairs("dq", 0, 4)),
    ("dly_pulse_a", _pairs("dp", 0, 18)),
    ("dly_pulse_b", _pairs("dp", 18, 35)),
    ("drv_x16", [("inv_x16", ["Xcb2", "Xw2"])]),
    ("drv_x8", [("inv_x8", ["Xwe1", "Xwe2"]), ("inv_x8", ["Xs1", "Xq1"]), ("inv_x4", ["Xw1"])]),
    ("logic_a", [("inv", ["Xcb1"]), ("inv", ["Xp"]), ("nand2", ["Xpn"]), ("nand2", ["Xqn"]),
                 ("nand2", ["Xwn"]), ("nand3", ["Xwen"])]),
    ("logic_b", [("nand3", ["Xsn"]), ("and2", ["Xrd"]), ("and2", ["Xwr"])]),
    ("flops_a", [("dff", ["Xfa0"]), ("dff", ["Xfa1"])]),
    ("flops_b", [("dff", ["Xfa2"]), ("dff", ["Xfa3"])]),
    ("flops_c", [("dff", ["Xfa4"]), ("dff", ["Xfa5"])]),
    ("flops_d", [("dff", ["Xfa6"]), ("dff", ["Xfa7"])]),
    ("flops_e", [("dff", ["Xfcen"]), ("dff", ["Xfgw"])]),
]
COL_DECODE_STRIPS = [
    ("nands", [("nand3", [f"Xn{k}"]) for k in range(4)]),
    ("drivers", [("inv_x16", [f"Xc{k}", f"Xcn{k}"]) for k in range(4)]),
]

SRAM_CTRL_PINS = {
    "bottom": ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "CEN", "GWEN", "CLK",
               "clk_buf", "wl_en_n", "s_en", "q_clk", "wpn"],
    "top": [f"aq{i}" for i in range(8)] + [f"aqb{i}" for i in range(8)] + ["wl_en"],
}
COL_DECODE_PINS = {
    "bottom": ["aq0", "aqb0", "aq1", "aqb1", "wl_en"],
    "top": [f"csel{k}" for k in range(4)] + [f"cseln{k}" for k in range(4)],
}

BLOCKS = {
    "sram_ctrl": dict(strips=SRAM_CTRL_STRIPS, pins=SRAM_CTRL_PINS, ncols=58, bottom_stride=3, top_stride=2,
                      chan={"dly": 2, "drv": 3, "logic": 4, "flops": 5}),
    "col_decode": dict(strips=COL_DECODE_STRIPS, pins=COL_DECODE_PINS, ncols=38, bottom_stride=3, top_stride=3,
                       chan={"nands": 3, "drivers": 4}),
}


def chan_for(block: str, strip: str, bump: int) -> int:
    table = BLOCKS[block]["chan"]
    for key, val in table.items():
        if strip.startswith(key):
            return val + bump
    raise KeyError(strip)


# ---------------------------------------------------------------------------
# Cells -> chains
# ---------------------------------------------------------------------------
def cell_chains(kind: str, insts: list) -> tuple:
    """``(width in columns, {"N": [(offset, names)], "P": [...]})`` for one cell."""
    if kind in INV_KINDS:
        p = [f"{i}.MP" for i in insts]
        n = [f"{i}.MN" for i in insts]
        return 2 * len(insts) + 1, {"N": [(0, n)], "P": [(0, p)]}
    (i,) = insts
    if kind == "nand2":
        return 5, {"P": [(0, [f"{i}.MP0@VDD", f"{i}.MP1"])], "N": [(0, [f"{i}.MN0", f"{i}.MN1"])]}
    if kind == "nand3":
        return 7, {"P": [(0, [f"{i}.MP0@VDD", f"{i}.MP1", f"{i}.MP2"])],
                   "N": [(0, [f"{i}.MN0", f"{i}.MN1", f"{i}.MN2"])]}
    if kind == "and2":
        return 7, {"P": [(0, [f"{i}.MP0@VDD", f"{i}.MP1", f"{i}.MPO"])],
                   "N": [(0, [f"{i}.MN0", f"{i}.MN1", f"{i}.MNO"])]}
    if kind == "dff":
        return 26, col.dff_chains(i)
    raise KeyError(kind)


def make_strip(name: str, items: list, chan: int, ncols: int):
    chains = {"N": [], "P": []}
    c0 = C0
    for kind, insts in items:
        width, spec = cell_chains(kind, insts)
        for k in ("N", "P"):
            for off, names in spec[k]:
                chains[k].append((c0 + off, names))
        c0 += width + GAP
    c_end = c0 - GAP - 1
    assert c_end <= ncols - 2, f"strip {name} is {c_end + 1} columns wide (cell has {ncols})"
    return col.Strip(name, "N", chains, chan=chan), c_end


def add_top_pin(ctx, net: str, c: int, j: int, y_top: float) -> None:
    x = col.X(c)
    rect = (x - col.HWIRE, col.Y(j) - col.HWIRE, x + col.HWIRE, y_top)
    ctx.box(col.L_METAL2, *rect)
    ctx.router.add_obstacle(col.M2, rect, net, col.M1_WIDE_SPACE)
    ctx.term(net, [(col.M2, c, j)])
    ctx.labels.append((col.L_METAL2_LBL, net, x, 0.5 * (col.Y(j) + y_top)))


def build(block: str, bump: int = 0):
    cfg = BLOCKS[block]
    ncols = cfg["ncols"]
    subs = col.parse_spice(netlist(block))
    devmap = {d.name: d for d in col.flatten(subs, block)}

    col.NCOLS = ncols
    col.SLICE_W = round(col.X(ncols - 1) + col.X0, 3)
    ctx = col.Ctx(row_lo=1, row_hi=10_000)
    ctx.router = row.FastRouter(1, 10_000)
    plan = row.Plan()

    jrb = 6  # rows 0..5 under the first rail carry the bottom pin stubs
    for name, items in cfg["strips"]:
        strip, c_end = make_strip(name, items, chan_for(block, name, bump), ncols)
        jrt, _ = row.layout_cells(ctx, plan, devmap, strip, jrb, c_vss=0, c_vdd=1, c_end=c_end)
        jrb = jrt + STRIP_SEP
    top_row = jrt + EDGE_ROWS + 3
    ctx.router.rhi = top_row
    row.draw_plan(ctx, plan)

    vss = [j for (j, net, c0, c1) in plan.rails if net == "VSS"]
    vdd = [j for (j, net, c0, c1) in plan.rails if net == "VDD"]
    row.add_strap(ctx, "VSS", 0, vss, min(vss), max(vss))
    row.add_strap(ctx, "VDD", 1, vdd, min(vdd), max(vdd))

    for i, net in enumerate(cfg["pins"]["bottom"]):
        col.add_bottom_pin(ctx, net, PIN_C0 + cfg["bottom_stride"] * i, jend=2)
    y_top = col.Y(top_row) + col.HWIRE
    for i, net in enumerate(cfg["pins"]["top"]):
        add_top_pin(ctx, net, PIN_C0 + cfg["top_stride"] * i, top_row - 1, y_top)
    return ctx


def build_cell(layout: kdb.Layout, block: str, max_bump: int = 4):
    last = None
    for bump in range(max_bump + 1):
        ctx = build(block, bump)
        try:
            col.route(ctx, block)
        except RuntimeError as exc:
            last = exc
            print(f"  {block}: chan_bump={bump}: {exc}", file=sys.stderr)
            continue
        col.emit_routes(ctx)
        return col.to_cell(layout, block, ctx), bump
    raise last


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", default=HERE)
    ap.add_argument("--block", choices=sorted(BLOCKS), action="append",
                    help="draw only this block (default: both)")
    args = ap.parse_args()
    for block in args.block or sorted(BLOCKS):
        layout = kdb.Layout()
        layout.dbu = 0.001
        cell, bump = build_cell(layout, block)
        bb = cell.dbbox()
        print(f"{block}: {bb.width():.3f} x {bb.height():.3f} um (channel bump {bump})")
        path = os.path.join(args.out_dir, f"{block}.gds")
        layout.write(path, col.save_options())
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
