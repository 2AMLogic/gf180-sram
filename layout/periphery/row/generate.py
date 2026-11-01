#!/usr/bin/env python3
"""Generate the row-decoder + wordline-driver strip: ``row_path``.

Issue #204 (child of #201). Draws ``design/netlist/row_path.spice`` -- two
3->8 predecoders (``and4`` x 8 for the high address bits and ``wl_en``, ``and3``
x 8 for the low bits) and 64 ``rowdrv`` NAND2+inverter wordline drivers -- as
**one flat cell**, for the ratified center-fed 4:1 organization
(``spec/periphery-architecture.md``, ``spec/wordline-rc-decision.md``: 64
rows, one driver strip *between* the two 64-column halves).

Scope is the strip only. Slice placement, the second landing-pad strip and
re-tiling the array are #206; the 27-corner wordline-RC / write-waveform /
integrated-read validation matrix is a separate, ungranted piece of work. Nothing
here claims the strip fits the array or validates a timing number.

## How it is drawn

This reuses ``layout/periphery/column/generate.py`` unchanged -- its netlist
reader, device/strip placer (``layout_strip``) and maze router -- because the
decoder is the same kind of problem (single-finger devices, ``L = 0.28 um``,
chains of shared diffusion between two supply rails). Only what that file
hard-wires to one 17.84 um slice (grid width, rail extent, wells) is
parameterised here: the module globals it reads (``NCOLS``, ``X0``, ``SLICE_W``)
are set before each build, and rails, implants and wells are drawn per cell
rather than full-width.

* Device sizes and connectivity come from ``row_path.spice``; the chain tables
  below (``rowdrv``: ``VDD-MP0-nb-MP1-VDD-MPO-y``, ...) are the only hand-made
  placement input.
* The router keeps nets on distinct nodes of the same 0.65 um grid as the column
  path (see that file's "Grid"), so spacing rules hold by construction.

## Does ``rowdrv`` fit the 5.40 um row pitch?  No -- and the placement says so

A ``rowdrv`` is a 6 um PMOS and 3 um NMOS output stage plus a 2 um NAND2, drawn
as one N row and one P row between two rails: **13.65 um rail to rail** (``chan
= 1``), 2.5 row pitches. It cannot sit inside one 5.40 um pitch. The drivers are
therefore interleaved in :data:`NSTAG` = 3 columns: driver ``k`` goes in column
``k % 3`` at the height that puts its output on the wordline row ``k``, so
consecutive drivers of one column are 3 pitches (16.2 um) apart. Each ``WL<k>``
leaves its driver on a ``Metal3`` track at row ``k``'s height, crossing the
other columns, and ends at **both** strip edges (the strip sits between the two
halves, so each wordline has to reach each half). The edge pins are ``Metal3``;
the array's landing pads are ``Metal1`` (``WL_PAD_BAND``), joined at assembly
(#206), not here.

## Strip interface

Strip frame: x from 0 to :data:`STRIP_W`; the array's row 0 sits at
y = :data:`Y_ARRAY0` (so ``WL<k>`` leaves at ``Y_ARRAY0 + k * H_CELL + wl_y``,
the same height as that row's landing pad in the array). Inputs ``aq2..aq7``,
``aqb2..aqb7`` and ``wl_en`` are ``Metal2`` stubs on the bottom edge; ``VDD``/
``VSS`` are the ``Metal2`` straps (labelled).

Run from the repo root::

    uv run --with klayout python3 layout/periphery/row/generate.py

No timestamps, no randomness, so a re-run reproduces the committed GDS
byte-for-byte.
"""

from __future__ import annotations

import argparse
import bisect
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


col = _load("_sram_column_generate", "layout/periphery/column/generate.py")
array = _load("_sram_array_generate", "layout/sram_256x32/generate.py")
bitcell = col.bitcell

TOP_CELL = "row_path"
NETLIST = os.path.join(col.NETLIST_DIR, "row_path.spice")

# ---------------------------------------------------------------------------
# Floorplan (grid columns of the column path's G = 0.65 um grid)
# ---------------------------------------------------------------------------
G = col.G
H_CELL = bitcell.H_CELL  # 5.40: row pitch, from the array itself
WL_Y = 0.5 * (bitcell.Y_WL_BOT + bitcell.Y_WL_TOP)  # wordline height inside a row
NROWS = 64
NSTAG = 3  # driver columns: ceil(13.65 um / 5.40 um) -- see the module docstring
CHAN = 1  # free rows between a driver's two gate-pad rows (smallest that routes)

N_TRUNK = 16  # ph0..7, pl0..7 -- one copy per driver column
BLOCK_W = N_TRUNK + 2 + 1 + 7 + 1  # trunks, VSS+VDD straps, gap, rowdrv, gap
NCOLS = NSTAG * BLOCK_W
CELL_W = 7  # rowdrv: columns c0 .. c0+6
X0 = col.X0
STRIP_W = round(col.X(NCOLS - 1) + X0, 3)
EDGE = 0.4  # rail / implant overhang past the outermost column
WELL_EDGE = 0.55

# Predecoder strips: (cell kind, output net) per cell, left to right.
PRED_STRIPS = [
    [("and4", f"ph{i}") for i in range(5)],
    [("and4", f"ph{i}") for i in range(5, 8)] + [("and3", f"pl{i}") for i in range(4)],
    [("and3", f"pl{i}") for i in range(4, 8)],
]
PRED_C0 = 3  # first chain column (cols 0 / 1 carry the predecoder straps)
WIDTH = {"and4": 11, "and3": 9}

ADDR_PINS = ["aq2", "aq3", "aq4", "aq5", "aq6", "aq7",
             "aqb2", "aqb3", "aqb4", "aqb5", "aqb6", "aqb7", "wl_en"]


def Y(j):
    return col.Y(j)


def X(c):
    return col.X(c)


# ---------------------------------------------------------------------------
# Router with a cheap A* bound (the column router's bound scans every target
# node, which is quadratic once a net owns a 500-node trunk)
# ---------------------------------------------------------------------------
class FastRouter(col.Router):
    def _heuristic(self, targets):
        bycol: dict[int, list[int]] = {}
        for (_, c, r) in targets:
            bycol.setdefault(c, []).append(r)
        for rows in bycol.values():
            rows.sort()
        cols = sorted(bycol)

        def h(node):
            _, c, r = node
            best = 1 << 30
            for tc in cols:
                dc = abs(c - tc)
                if dc >= best:
                    continue
                rows = bycol[tc]
                i = bisect.bisect_left(rows, r)
                dr = 1 << 30
                if i < len(rows):
                    dr = rows[i] - r
                if i > 0:
                    dr = min(dr, r - rows[i - 1])
                best = min(best, dc + dr)
            return best

        return h


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------
def chains_for(kind: str, inst: str, out: str):
    """``(P chain, N chain)`` device names, in diffusion order, for one cell.

    ``and4`` (4 series inputs) ends its chains on the output stage; ``and3``
    has an odd number of input devices, so its chains start on the output
    stage instead (``out`` is that cell's output net, the first device's hint).
    P and N are ordered so each gate's P and N device share a column.
    """
    if kind == "rowdrv":
        return ([f"{inst}.MP0@VDD", f"{inst}.MP1", f"{inst}.MPO"],
                [f"{inst}.MN0", f"{inst}.MN1", f"{inst}.MNO"])
    if kind == "and4":
        return ([f"{inst}.MP0@VDD"] + [f"{inst}.MP{i}" for i in range(1, 4)] + [f"{inst}.MPO"],
                [f"{inst}.MN{i}" for i in range(4)] + [f"{inst}.MNO"])
    return ([f"{inst}.MPO@{out}"] + [f"{inst}.MP{i}" for i in (2, 1, 0)],
            [f"{inst}.MNO@{out}"] + [f"{inst}.MN{i}" for i in (2, 1, 0)])


class Plan:
    """Everything drawn per strip that is not a device: rails, implants, wells."""

    def __init__(self):
        self.rails: list = []  # (row, net, c_from, c_to)
        self.rows: list = []  # (kind, side, ymin, ymax, rail_y, xl, xr)
        self.vss_rows: dict[int, list[int]] = {}  # strap column -> rail rows
        self.vdd_rows: dict[int, list[int]] = {}


def layout_cells(ctx, plan: Plan, devmap, strip, jrb, c_vss, c_vdd, c_end):
    """Run the column path's ``layout_strip`` for one strip and record the
    per-strip rails / implant extents (its own ``ctx.rails`` / ``ctx.rows`` are
    keyed by row alone, so they are taken out after each strip)."""
    ctx.rails, ctx.rows = {}, []
    jrt, info = col.layout_strip(ctx, strip, devmap, jrb)
    xl = X(min(c_vss, c_vdd)) - WELL_EDGE
    xr = X(c_end) + X0
    for j, net in ctx.rails.items():
        plan.rails.append((j, net, c_vss if net == "VSS" else c_vdd, c_end))
        (plan.vss_rows if net == "VSS" else plan.vdd_rows).setdefault(
            c_vss if net == "VSS" else c_vdd, []).append(j)
    for (kind, side, ymin, ymax, rail_y) in ctx.rows:
        plan.rows.append((kind, side, ymin, ymax, rail_y, xl, xr))
    return jrt, info


def draw_plan(ctx, plan: Plan) -> None:
    for (j, net, c0, c1) in plan.rails:
        y = Y(j)
        x0, x1 = X(c0) - EDGE, X(c1) + EDGE
        ctx.metal1((x0, y - 0.5 * col.RAIL_H, x1, y + 0.5 * col.RAIL_H), net, col.M1_WIDE_SPACE)
        ctx.box(col.L_COMP, X(c0) - col.COMP_HALF, y - 0.19, X(c1) + col.COMP_HALF, y + 0.19)
        for c in range(c0 + 1, c1 + 1, 2):
            ctx.box(col.L_CONTACT, X(c) - col.HCO, y - col.HCO, X(c) + col.HCO, y + col.HCO)
            ctx.router.noviablock.add((c, j))
        ctx.router.noviablock.add((c0, j))
        if net == "VSS":
            ctx.box(col.L_PPLUS, x0, y - 0.19 - col.IMP_ENC_COMP, x1, y + 0.19 + col.IMP_ENC_COMP)
        else:
            ctx.box(col.L_NPLUS, x0, y - 0.19 - col.IMP_ENC_COMP, x1, y + 0.19 + col.IMP_ENC_COMP)
            ctx.box(col.L_NWELL, x0 - 0.05, y - 0.19 - col.NW_ENC_NCOMP, x1 + 0.05,
                    y + 0.19 + col.NW_ENC_NCOMP)
    for (kind, side, ymin, ymax, rail_y, xl, xr) in plan.rows:
        lp = col.L_NPLUS if kind == "N" else col.L_PPLUS
        ctx.box(lp, xl, ymin - col.IMP_ENC_GATE, xr, ymax + col.IMP_ENC_GATE)
        if kind == "P":
            y0 = ymin - col.NW_ENC_PCOMP
            y1 = ymax + col.NW_ENC_PCOMP
            if side == "A":
                y0 = min(y0, rail_y - 0.19 - col.NW_ENC_NCOMP)
            else:
                y1 = max(y1, rail_y + 0.19 + col.NW_ENC_NCOMP)
            ctx.box(col.L_NWELL, xl, y0, xr, y1)


def add_strap(ctx, net: str, c: int, rows: list[int], j_lo: int, j_hi: int) -> None:
    """Vertical Metal2 strap on grid column ``c`` from row ``j_lo`` to ``j_hi``
    with a Via1 on every rail row in ``rows``."""
    x = X(c)
    rect = (x - col.HWIRE, Y(j_lo) - col.HWIRE, x + col.HWIRE, Y(j_hi) + col.HWIRE)
    ctx.box(col.L_METAL2, *rect)
    ctx.router.add_obstacle(col.M2, rect, net, col.M1_WIDE_SPACE)
    for j in rows:
        ctx.box(col.L_VIA1, x - col.HVIA, Y(j) - col.HVIA, x + col.HVIA, Y(j) + col.HVIA)
        ctx.router.noviablock.add((c, j))
    ctx.labels.append((col.L_METAL2_LBL, net, x, Y(j_lo) + 0.5 * col.RAIL_H))


def add_jumper(ctx, net: str, j: int, straps: list[int]) -> None:
    """Horizontal Metal3 line on row ``j`` joined by Via2 to the Metal2 straps
    at grid columns ``straps``."""
    y = Y(j)
    rect = (X(min(straps)) - col.HWIRE, y - col.HWIRE, X(max(straps)) + col.HWIRE, y + col.HWIRE)
    ctx.box(col.L_METAL3, *rect)
    ctx.router.add_obstacle(col.M3, rect, net, col.M1_WIDE_SPACE)
    for c in straps:
        ctx.box(col.L_VIA2, X(c) - col.HVIA, y - col.HVIA, X(c) + col.HVIA, y + col.HVIA)


def add_trunk(ctx, net: str, c: int, j_lo: int, j_hi: int) -> None:
    x = X(c)
    rect = (x - col.HWIRE, Y(j_lo) - col.HWIRE, x + col.HWIRE, Y(j_hi) + col.HWIRE)
    ctx.box(col.L_METAL2, *rect)
    ctx.router.add_obstacle(col.M2, rect, net, col.M1_WIDE_SPACE)
    ctx.term(net, [(col.M2, c, j) for j in range(j_lo, j_hi + 1)])


def build():
    subs = col.parse_spice(NETLIST)
    devmap = {d.name: d for d in col.flatten(subs, TOP_CELL)}

    col.NCOLS = NCOLS
    col.SLICE_W = STRIP_W
    ctx = col.Ctx(row_lo=1, row_hi=10_000)
    ctx.router = FastRouter(1, 10_000)
    plan = Plan()

    # ---- predecoders (three stacked strips, each with its own rail pair) ----
    jrb = 6
    pred_rows: list[tuple[int, int]] = []
    for si, cells in enumerate(PRED_STRIPS):
        chains = {"N": [], "P": []}
        c0 = PRED_C0
        for (kind, out) in cells:
            inst = f"X{out}"
            p, n = chains_for(kind, inst, out)
            chains["P"].append((c0, p))
            chains["N"].append((c0, n))
            c0 += WIDTH[kind] + 1
        assert c0 - 1 <= NCOLS - 1, f"predecoder strip {si} is {c0} columns wide"
        jrt, _ = layout_cells(ctx, plan, devmap, col.Strip(f"pred{si}", "N", chains, chan=CHAN),
                              jrb, c_vss=0, c_vdd=1, c_end=c0 - 2)
        pred_rows.append((jrb, jrt))
        jrb = jrt + 5
    pred_top = pred_rows[-1][1]

    # ---- corridor: supply jumpers, then the trunks start ---------------------
    j_vss_jump = pred_top + 3
    j_vdd_jump = pred_top + 5
    j_trunk0 = pred_top + 8

    # ---- drivers -------------------------------------------------------------
    r_arr0 = j_trunk0 + 12  # row of the array's y = 0 (first driver clears the corridor)
    y_arr0 = Y(r_arr0)
    drv_off = None
    drv_height = None
    block_rows: list[list[tuple[int, int]]] = [[] for _ in range(NSTAG)]
    tracks: list[tuple[int, int, int]] = []  # (k, track row, block)
    for k in range(NROWS):
        b = k % NSTAG
        cb = b * BLOCK_W
        c0 = cb + N_TRUNK + 3
        yk = y_arr0 + k * H_CELL + WL_Y
        rk = int(round(yk / G))
        p, n = chains_for("rowdrv", f"Xrow{k}", f"wl{k}")
        if drv_off is None:
            probe = col.Ctx(1, 10_000)
            _jrt, _ = col.layout_strip(probe, col.Strip("p", "N", {"P": [(0, p)], "N": [(0, n)]},
                                                       chan=CHAN), devmap, 1)
            drv_off = (_jrt - 1) // 2 + 1
            drv_height = round(Y(_jrt) - Y(1), 3)
        jb = rk - drv_off
        jrt, _ = layout_cells(
            ctx, plan, devmap,
            col.Strip(f"drv{k}", "N", {"P": [(c0, p)], "N": [(c0, n)]}, chan=CHAN),
            jb, c_vss=cb + N_TRUNK, c_vdd=cb + N_TRUNK + 1, c_end=c0 + CELL_W - 1)
        block_rows[b].append((jb, jrt))
        tracks.append((k, rk, b))
    top_row = max(jrt for rows in block_rows for (_, jrt) in rows) + 2
    ctx.router.rhi = top_row

    draw_plan(ctx, plan)

    # ---- straps / jumpers ----------------------------------------------------
    pred_vss = [j for (j, net, c0, c1) in plan.rails if net == "VSS" and c0 == 0]
    pred_vdd = [j for (j, net, c0, c1) in plan.rails if net == "VDD" and c0 == 1]
    add_strap(ctx, "VSS", 0, pred_vss, min(pred_vss), j_vss_jump)
    add_strap(ctx, "VDD", 1, pred_vdd, min(pred_vdd), j_vdd_jump)
    jump_vss, jump_vdd = [0], [1]
    for b in range(NSTAG):
        cb = b * BLOCK_W
        c_vss, c_vdd = cb + N_TRUNK, cb + N_TRUNK + 1
        add_strap(ctx, "VSS", c_vss, plan.vss_rows[c_vss], j_vss_jump, max(plan.vss_rows[c_vss]))
        add_strap(ctx, "VDD", c_vdd, plan.vdd_rows[c_vdd], j_vdd_jump, max(plan.vdd_rows[c_vdd]))
        jump_vss.append(c_vss)
        jump_vdd.append(c_vdd)
    add_jumper(ctx, "VSS", j_vss_jump, jump_vss)
    add_jumper(ctx, "VDD", j_vdd_jump, jump_vdd)

    # ---- trunks (ph / pl): one copy per driver column -------------------------
    trunk_nets = [f"ph{i}" for i in range(8)] + [f"pl{i}" for i in range(8)]
    for b in range(NSTAG):
        cb = b * BLOCK_W
        for i, net in enumerate(trunk_nets):
            add_trunk(ctx, net, cb + i, j_trunk0, top_row - 1)

    # ---- wordline tracks + edge pins --------------------------------------------
    pin_w = max(array.WL_PAD_BAND, 4 * col.HWIRE)
    for (k, rk, b) in tracks:
        y = Y(rk)
        yk = y_arr0 + k * H_CELL + WL_Y
        assert abs(y - yk) < 2 * col.HWIRE - 0.02, (k, y, yk)
        net = f"wl{k}"
        rect = (0.0, y - col.HWIRE, STRIP_W, y + col.HWIRE)
        ctx.box(col.L_METAL3, *rect)
        ctx.box(col.L_METAL3, 0.0, yk - col.HWIRE, pin_w, yk + col.HWIRE)
        ctx.box(col.L_METAL3, STRIP_W - pin_w, yk - col.HWIRE, STRIP_W, yk + col.HWIRE)
        ctx.router.add_obstacle(col.M3, rect, net, col.M1_WIDE_SPACE)
        c0 = b * BLOCK_W + N_TRUNK + 3
        ctx.term(net, [(col.M3, c, rk) for c in range(c0, c0 + CELL_W)])
        for x in (0.5 * pin_w, STRIP_W - 0.5 * pin_w):
            ctx.labels.append((col.L_METAL3_LBL, net, x, yk))

    # ---- address pins: Metal2 stubs on the bottom edge ----------------------------
    pin_cols = [4 + 6 * i for i in range(len(ADDR_PINS))]
    for net, c in zip(ADDR_PINS, pin_cols):
        col.add_bottom_pin(ctx, net, c, jend=2)
    return ctx, dict(drv_height=drv_height, y_arr0=y_arr0, top_row=top_row, pred_rows=pred_rows, j_trunk0=j_trunk0,
                     block_rows=block_rows)


def build_cell(layout: kdb.Layout):
    ctx, info = build()
    col.route(ctx, TOP_CELL)
    col.emit_routes(ctx)
    return col.to_cell(layout, TOP_CELL, ctx), info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default=os.path.join(HERE, f"{TOP_CELL}.gds"))
    args = ap.parse_args()
    layout = kdb.Layout()
    layout.dbu = 0.001
    cell, info = build_cell(layout)
    bb = cell.dbbox()
    print(f"{TOP_CELL}: {bb.width():.3f} x {bb.height():.3f} um; array y=0 at strip y={info['y_arr0']:.3f}")
    print(f"rowdrv: {info['drv_height']:.2f} um rail to rail vs the {H_CELL:.2f} um row pitch "
          f"-> {NSTAG} interleaved driver columns")
    layout.write(args.out, col.save_options())
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
