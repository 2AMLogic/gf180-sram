#!/usr/bin/env python3
"""Generate the column-path layout: ``precharge_slice`` and ``io_slice``.

Issue #205 (child of #201). Draws the two per-I/O column-path cells that
``spec/periphery-architecture.md`` (#202) fixed and ``design/netlist/``
(#203) captured:

* ``precharge_slice`` -- 12 PMOS (``design/netlist/precharge_slice.spice``):
  bit-line precharge/equalize for the four columns of one I/O. Sits above the
  array.
* ``io_slice`` -- 99 devices (``design/netlist/io_slice.spice``): the 4:1
  column mux, the latch sense amp ``sa_latch``, the write driver ``wdrv`` and
  the three flops (``D``, ``WEN`` input capture and the ``Q`` register). Sits
  below the array.

Both are exactly **4 x W_CELL = 17.84 um** wide (one I/O = 4 bitcell columns,
#202 row 3), so 32 of them tile into the bottom and top bands of the 4:1
array. ``BL``/``BLB`` enter on ``Metal1`` stubs at the *same x* as the array's
continuous bit-line stripes (``layout/bitcell/generate.py``), so the seam adds
no new geometry for the bit lines.

## How the cells are drawn

Nothing here is hand-placed polygon art: device sizes (``W``/``L``) are read
from the netlists, and every wire is produced by the same small flow.

1. **Netlist -> devices.** ``design/netlist/*.spice`` is parsed and flattened
   (``dff`` -> ``inv``/``tg_s`` -> transistors). Sizes and connectivity come
   from the file, not from this script.
2. **Chains.** A *chain* is a row of single-finger transistors that share
   source/drain diffusion (``VSS -[g]- y -[g]- VSS ...``). Which devices form a
   chain, and in what order, is the only hand-made placement input (the chain
   tables in :func:`build_precharge` / :func:`build_io`). Orientation of each
   device is derived so that facing terminals share a net; a mismatch is a
   hard error.
3. **Strips.** An N row and a P row (gates run vertically, so a common n/p
   gate is one poly stripe) with a routing channel between them, between two
   horizontal ``Metal1`` supply rails. Adjacent strips are mirrored so they
   share a rail (and its well/substrate tie strip).
4. **Router.** Every signal net is routed by a small deterministic maze
   router on a fixed grid (:data:`G`), three layers (Metal1/2/3). The grid
   pitch is chosen so that *any* two different-net objects on distinct grid
   nodes already satisfy the spacing rules (see "Grid" below); the router
   therefore only has to keep nets on distinct nodes. Static geometry (contact
   bars, rails, bit-line stubs, bus tracks) is entered as obstacles whose
   clearance is computed, not assumed.
5. **Supply** goes straight from each source contact to the rail with a
   ``Metal1`` bar; rails carry continuous substrate/well tie strips, and one
   vertical ``Metal2`` strap per supply joins a slice's rails (they are
   separate wells otherwise).

The flow behind these steps -- netlist reader, strip placer, router, route /
emit helpers and the ``dff`` chain table -- lives in the shared periphery
engine, ``layout/periphery/engine.py`` (#505 extracted it from this file);
this file holds only what is specific to the two column-path cells
(full-width rails and implants, the ``Metal3`` bus tracks, the bit-line stubs
and the band tiling).

## Grid

``G = 0.65 um``. With ``Metal1``/``2``/``3`` wires 0.35 um wide (not "narrow"
under the DRM's < 0.34 um end-of-line rules), a pad 0.38 um square and a rule
set of 0.28 um (Metal2/3) / 0.23 um (Metal1) spacing -- both rising to 0.30 um
for any shape with an edge >= 10 um (M1.2b/M2.2b), which rails, bus tracks and
long vertical runs are -- two shapes on different nodes are never closer than
0.30 um. That is the whole reason for 0.65.

## Slice interface

* ``BL``/``BLB``: ``Metal1`` stubs, 0.30 um wide, at the array's own column x
  (``bitcell.X_BL_C``/``X_BLB_C`` + k * ``W_CELL``), running to the slice's
  array-facing edge.
* ``VDD``/``VSS``: full-width ``Metal1`` rails with continuous tie strips; a
  rail at the same y in every slice forms one net across a band.
* Shared control inputs (``csel*``, ``cseln*``, ``clk``, ``q_clk``, ``s_en``,
  ``wl_en_n``, ``wpn``): full-width ``Metal3`` bus tracks at the same y in every
  slice, so a band forms one net per control line. The macro (#206) taps them
  at the band ends.
* ``D``/``WEN``/``Q`` (``d_in``, ``wen_in``, ``q_out``): ``Metal2`` stubs on
  the bottom edge (#202 "Pin placement").

Everything is drawn inside ``0 <= x <= 17.84``. Diffusion stays >= 0.6 um from
the slice's left/right edge, so a slice keeps the DF.4c_LV Nwell overlap of
PCOMP on its own (the first and last slice of a band need no end cap) while the
wells of neighbouring slices still merge at the shared edge.

## Outputs (``layout/periphery/column/``)

* ``precharge_slice.gds`` / ``io_slice.gds`` -- one top cell each, for per-cell
  DRC/extract/LVS against ``design/netlist/<cell>.spice``.
* ``column_band.gds`` -- ``precharge_band`` and ``io_band``: 32 slices each as
  one hierarchical ``CellInstArray`` (pitch 17.84 um).
* ``--abut ARRAY.gds -o OUT.gds`` writes a *scratch* composite -- the array,
  ``io_band`` below it and ``precharge_band`` above it -- for the bit-line seam
  DRC in ``layout/verify.sh``. It is not committed.

## What is NOT claimed

Not area-optimized (single-finger devices, ``G``-pitch diffusion); pitch and
spacing are chosen for correctness of an automatically generated layout. No
timing or parasitic claim is made here (#206/PEX are separate).

## Determinism

Run from the repo root::

    uv run --with klayout python3 layout/periphery/column/generate.py

No timestamps, no randomness (the router breaks ties on insertion order), so a
re-run reproduces the committed GDS byte-for-byte.
"""

from __future__ import annotations

import argparse
import math
import os
import sys

import klayout.db as kdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))

from layout.common import load_module, nm, save_options  # noqa: E402
from layout.periphery.engine import (  # noqa: E402
    COMP_HALF,
    G,
    HCO,
    HWIRE,
    HPAD,
    HVIA,
    IMP_ENC_COMP,
    IMP_ENC_GATE,
    L_COMP,
    L_CONTACT,
    L_METAL1,
    L_METAL1_LBL,
    L_METAL2,
    L_METAL3,
    L_METAL3_LBL,
    L_NWELL,
    L_NPLUS,
    L_PPLUS,
    L_VIA1,
    L_VIA2,  # re-export: layout/macro/generate.py reads col.L_VIA2
    _LAYER_NAMES,  # re-export: layout/macro/generate.py reads col._LAYER_NAMES
    M1,
    M1_WIDE_SPACE,
    M2,
    M3,
    NCOLS,
    NETLIST_DIR,
    NW_ENC_NCOMP,
    NW_ENC_PCOMP,
    RAIL_H,
    SLICE_W,
    STUB_W,
    VIA_SZ,  # re-export: layout/macro/generate.py reads col.VIA_SZ
    X,
    X0,
    Y,
    Ctx,
    Strip,
    add_bottom_pin,
    bitcell,
    dff_chains,
    emit_routes,
    flatten,
    layout_strip,
    parse_spice,
    route,
    to_cell,
)

# ---------------------------------------------------------------------------
# Rails, ties, wells, implants (full slice width -- the engine's Plan /
# draw_plan draw these per strip for the blocks whose rails do not span the
# whole cell)
# ---------------------------------------------------------------------------
def draw_rails(ctx: Ctx) -> None:
    for j, net in sorted(ctx.rails.items()):
        y = Y(j)
        ctx.metal1((0.0, y - 0.5 * RAIL_H, SLICE_W, y + 0.5 * RAIL_H), net, M1_WIDE_SPACE)
        ctx.box(L_COMP, X(0) - COMP_HALF, y - 0.19, X(NCOLS - 1) + COMP_HALF, y + 0.19)
        for c in range(0, NCOLS, 2):
            ctx.box(L_CONTACT, X(c) - HCO, y - HCO, X(c) + HCO, y + HCO)
        if net == "VSS":
            ctx.box(L_PPLUS, 0.0, y - 0.19 - IMP_ENC_COMP, SLICE_W, y + 0.19 + IMP_ENC_COMP)
        else:
            ctx.box(L_NPLUS, 0.0, y - 0.19 - IMP_ENC_COMP, SLICE_W, y + 0.19 + IMP_ENC_COMP)
            ctx.box(L_NWELL, 0.0, y - 0.19 - NW_ENC_NCOMP, SLICE_W, y + 0.19 + NW_ENC_NCOMP)
        ctx.labels.append((L_METAL1_LBL, net, 0.5 * SLICE_W, y))
    # Rails of one supply at different y are separate Metal1 bars (and, for
    # VDD, separate wells): join them with one vertical Metal2 strap per
    # supply, on a grid column the routers then treat as a static obstacle.
    # Columns 1 / 25 sit between the (even-column) tie contacts and far from
    # the neighbouring slice's strap.
    for net, col in (("VDD", 1), ("VSS", NCOLS - 2)):
        rows = sorted(j for j, n in ctx.rails.items() if n == net)
        if len(rows) < 2:
            continue
        x = X(col)
        rect = (x - HWIRE, Y(rows[0]) - HWIRE, x + HWIRE, Y(rows[-1]) + HWIRE)
        ctx.box(L_METAL2, *rect)
        ctx.router.add_obstacle(M2, rect, net, M1_WIDE_SPACE)
        for j in rows:
            ctx.box(L_VIA1, x - HVIA, Y(j) - HVIA, x + HVIA, Y(j) + HVIA)
            ctx.router.noviablock.add((col, j))


def draw_rows(ctx: Ctx) -> None:
    for kind, side, ymin, ymax, rail_y in ctx.rows:
        lp = L_NPLUS if kind == "N" else L_PPLUS
        ctx.box(lp, 0.0, ymin - IMP_ENC_GATE, SLICE_W, ymax + IMP_ENC_GATE)
        if kind == "P":
            y0 = ymin - NW_ENC_PCOMP
            y1 = ymax + NW_ENC_PCOMP
            if side == "A":
                y0 = min(y0, rail_y - 0.19 - NW_ENC_NCOMP)
            else:
                y1 = max(y1, rail_y + 0.19 + NW_ENC_NCOMP)
            ctx.box(L_NWELL, 0.0, y0, SLICE_W, y1)


# ---------------------------------------------------------------------------
# Ports: bus tracks, bit-line stubs
# ---------------------------------------------------------------------------
def add_bus(ctx: Ctx, net: str, row: int) -> None:
    y = Y(row)
    rect = (0.0, y - HWIRE, SLICE_W, y + HWIRE)
    ctx.box(L_METAL3, *rect)
    ctx.router.add_obstacle(M3, rect, net, M1_WIDE_SPACE)
    ctx.term(net, [(M3, c, row) for c in range(NCOLS)])
    ctx.labels.append((L_METAL3_LBL, net, 0.5 * SLICE_W, y))


def add_bl_stub(ctx: Ctx, net: str, x: float, jl: int, edge_y: float, toward: str) -> None:
    """Metal1 stub at the array's own bit-line x, reaching the slice edge
    ``edge_y``, then a jog on row ``jl`` onto a grid column.

    ``toward`` is ``"right"`` for BL (jog to the first column at or right of
    the stub) and ``"left"`` for BLB: each BLB<k> sits only 0.70 um left of
    BL<k+1>, so the pair's jogs must diverge rather than meet.
    """
    f = (x - X0) / G
    c = int(math.ceil(f - 1e-9)) if toward == "right" else int(math.floor(f + 1e-9))
    xc = X(c)
    y = Y(jl)
    lo, hi = sorted((y - HWIRE, edge_y))
    stub = (x - 0.5 * STUB_W, lo, x + 0.5 * STUB_W, hi)
    jog = (min(x - 0.5 * STUB_W, xc - HPAD), y - HPAD, max(x + 0.5 * STUB_W, xc + HPAD), y + HPAD)
    for r in (stub, jog):
        ctx.box(L_METAL1, *r)
        ctx.router.add_obstacle(M1, r, net, M1_WIDE_SPACE)
    ctx.term(net, [(M1, c, jl)])
    ctx.labels.append((L_METAL1_LBL, net, x, 0.5 * (lo + hi) if abs(hi - lo) > 0.4 else y))


# ---------------------------------------------------------------------------
# The two cells
# ---------------------------------------------------------------------------
def _bl_x(s: int) -> float:
    return round(bitcell.X_BL_C + s * bitcell.W_CELL, 3)


def _blb_x(s: int) -> float:
    return round(bitcell.X_BLB_C + s * bitcell.W_CELL, 3)


def _middle_rows(info: dict, count: int) -> list[int]:
    lo, hi = info["jrb"] + 1, info["jrt"] - 1
    start = lo + max(0, (hi - lo + 1 - count) // 2)
    return list(range(start, start + count))


def build_precharge(chan_bump: int = 0) -> tuple[Ctx, float]:
    subs = parse_spice(os.path.join(NETLIST_DIR, "precharge_slice.spice"))
    devmap = {d.name: d for d in flatten(subs, "precharge_slice")}
    names = []
    for k in range(4):
        names += [f"MPB{k}", f"MPE{k}", f"MPN{k}"]
    strip = Strip("precharge", "N", {"P": [(0, names)]}, chan=3 + chan_bump, bottom_rail=False, strap=True)
    jl = 1
    ctx = Ctx(row_lo=1, row_hi=10_000, ncols=NCOLS)  # rhi is lowered once the cell height is known
    jrt, _ = layout_strip(ctx, strip, devmap, jrb=0, jfloor=jl)
    j_vss = jrt + 2
    ctx.rails[j_vss] = "VSS"
    top_row = j_vss + 1
    ctx.router.rhi = top_row
    height = Y(top_row + 1)
    draw_rails(ctx)
    draw_rows(ctx)
    for s in range(4):
        add_bl_stub(ctx, f"bl{s}", _bl_x(s), jl, 0.0, "right")
        add_bl_stub(ctx, f"blb{s}", _blb_x(s), jl, 0.0, "left")
    rows = [3, 4, 6, 8]
    for k in range(4):
        add_bus(ctx, f"csel{k}", rows[k])
    return ctx, height


def build_io(chan_bump: int = 0) -> tuple[Ctx, float]:
    subs = parse_spice(os.path.join(NETLIST_DIR, "io_slice.spice"))
    devmap = {d.name: d for d in flatten(subs, "io_slice")}

    def sa_chains():
        return {
            "N": [
                (0, ["Xsa.MNA", "Xsa.MNB"]),
                (6, ["Xsa.MNT"]),
                (10, ["Xwd.MNWL", "Xwd.MNWR"]),
            ],
            "P": [(0, ["Xsa.MPA@VDD", "Xsa.MPE1", "Xsa.MPE2", "Xsa.MPB"])],
        }

    def wl_chains():
        def nor(inst, m):
            return [f"Xwd.{inst}.{m}{i}" for i in range(3)]

        return {
            "N": [(0, nor("Xpl", "MN")), (8, nor("Xpr", "MN")), (16, ["Xwd.Xdn.MN"])],
            "P": [(0, nor("Xpl", "MP")), (8, nor("Xpr", "MP")), (16, ["Xwd.Xdn.MP"])],
        }

    def mux_chains(m):
        return [
            (0, [f"Xmb0.{m}", f"Xmb1.{m}"]),
            (6, [f"Xmb2.{m}", f"Xmb3.{m}"]),
            (12, [f"Xmn0.{m}", f"Xmn1.{m}"]),
            (18, [f"Xmn2.{m}", f"Xmn3.{m}"]),
        ]

    b = chan_bump
    strips = [
        (Strip("fd", "N", dff_chains("Xfd"), chan=5 + b), ["clk"]),
        (Strip("fw", "P", dff_chains("Xfw"), chan=5 + b), []),
        (Strip("wlogic", "N", wl_chains(), chan=4 + b), ["wpn"]),
        (Strip("fq", "P", dff_chains("Xfq"), chan=5 + b), ["q_clk"]),
        (Strip("sa", "N", sa_chains(), chan=4 + b), ["s_en", "wl_en_n"]),
        (Strip("mux", "P", {"N": mux_chains("MN"), "P": mux_chains("MP")}, chan=4 + b),
         [f"csel{k}" for k in range(4)] + [f"cseln{k}" for k in range(4)]),
    ]
    ctx = Ctx(row_lo=1, row_hi=10_000, ncols=NCOLS)  # rhi is lowered once the cell height is known
    jrb = 1
    bus_plan: list[tuple[str, int]] = []
    for strip, bus in strips:
        jrt, info = layout_strip(ctx, strip, devmap, jrb)
        for net, row in zip(bus, _middle_rows(info, len(bus))):
            bus_plan.append((net, row))
        jrb = jrt
    jl = jrb + 2
    top_row = jl
    ctx.router.rhi = top_row
    height = Y(jl + 1)
    draw_rails(ctx)
    draw_rows(ctx)
    for s in range(4):
        add_bl_stub(ctx, f"bl{s}", _bl_x(s), jl, height, "right")
        add_bl_stub(ctx, f"blb{s}", _blb_x(s), jl, height, "left")
    for net, row in bus_plan:
        add_bus(ctx, net, row)
    add_bottom_pin(ctx, "d_in", 3)
    add_bottom_pin(ctx, "wen_in", 9)
    add_bottom_pin(ctx, "q_out", 21)
    return ctx, height


def build_cell(kind: str, max_bump: int = 6):
    builder = build_precharge if kind == "precharge_slice" else build_io
    last = None
    for bump in range(max_bump + 1):
        ctx, height = builder(bump)
        try:
            route(ctx, kind)
        except RuntimeError as exc:
            last = exc
            print(f"  {kind}: chan_bump={bump}: {exc}", file=sys.stderr)
            continue
        emit_routes(ctx)
        return ctx, height, bump
    raise last


def make_band(layout: kdb.Layout, slice_cell: kdb.Cell, name: str, n: int = 32) -> kdb.Cell:
    top = layout.create_cell(name)
    top.insert(
        kdb.CellInstArray(
            slice_cell.cell_index(), kdb.Trans(0, 0), kdb.Vector(nm(SLICE_W), 0), kdb.Vector(0, 0), n, 1
        )
    )
    return top


def check_bitline_seams(layout: kdb.Layout, top: kdb.Cell, x_off: int, arr_h: int) -> int:
    """Assert every bit line of every slice is one Metal1 polygon across the
    array/band seam (stub and array stripe share x and width, so they merge).

    Returns the number of bit lines checked (2 seams x 32 slices x 8 lines).
    """
    li = layout.layer(*L_METAL1)
    checked = 0
    for seam_y, label in ((0, "io_band/array"), (arr_h, "array/precharge_band")):
        for i in range(32):
            for s in range(4):
                for x_um in (_bl_x(s), _blb_x(s)):
                    x = x_off + i * nm(SLICE_W) + nm(x_um)
                    win = kdb.Box(x - 500, seam_y - 1000, x + 500, seam_y + 1000)
                    reg = kdb.Region(top.begin_shapes_rec_touching(li, win))
                    reg.merge()
                    below = kdb.Region(kdb.Box(x - 10, seam_y - 200, x + 10, seam_y - 100))
                    above = kdb.Region(kdb.Box(x - 10, seam_y + 100, x + 10, seam_y + 200))
                    joined = [p for p in reg.each() if
                              not (kdb.Region(p) & below).is_empty() and not (kdb.Region(p) & above).is_empty()]
                    if not joined:
                        raise RuntimeError(f"bit line at x={x * 0.001:.3f} (slice {i}) does not cross the {label} seam")
                    checked += 1
    return checked


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", default=HERE)
    ap.add_argument("--abut", metavar="ARRAY_GDS",
                    help="write a scratch GDS with the 32-slice bands abutted to this array "
                         "(see layout/verify.sh); needs -o")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    built = {}
    for kind in ("precharge_slice", "io_slice"):
        ctx, height, bump = build_cell(kind)
        built[kind] = (ctx, height)
        tmp = kdb.Layout()
        tmp.dbu = 0.001
        bb = to_cell(tmp, kind, ctx).dbbox()
        print(f"{kind}: {bb.width():.3f} x {bb.height():.3f} um (channel bump {bump})")

    if args.abut:
        assert args.out, "--abut needs -o"
        layout = kdb.Layout()
        layout.read(args.abut)
        array = next(c for c in layout.top_cells() if c.name.startswith("sram_"))
        pre = to_cell(layout, "precharge_slice", built["precharge_slice"][0])
        io = to_cell(layout, "io_slice", built["io_slice"][0])
        pre_band = make_band(layout, pre, "precharge_band")
        io_band = make_band(layout, io, "io_band")
        # the array's own wordline landing-pad strip sits left of its first cell
        arr_gen = load_module("_sram_array_generate", "layout/sram_256x32/generate.py")
        x_off = nm(arr_gen.WL_PAD_BAND)
        arr_h = array.bbox().top
        top = layout.create_cell("column_abut_check")
        top.insert(kdb.CellInstArray(array.cell_index(), kdb.Trans(0, 0)))
        top.insert(kdb.CellInstArray(io_band.cell_index(), kdb.Trans(x_off, -nm(built["io_slice"][1]))))
        top.insert(kdb.CellInstArray(pre_band.cell_index(), kdb.Trans(x_off, arr_h)))
        n = check_bitline_seams(layout, top, x_off, arr_h)
        print(f"seam: {n} bit-line crossings, each one Metal1 polygon from the array into the band")
        layout.write(args.out, save_options())
        print(f"wrote {args.out}")
        return

    for kind in ("precharge_slice", "io_slice"):
        layout = kdb.Layout()
        layout.dbu = 0.001
        to_cell(layout, kind, built[kind][0])
        path = os.path.join(args.out_dir, f"{kind}.gds")
        layout.write(path, save_options())
        print(f"wrote {path}")
    layout = kdb.Layout()
    layout.dbu = 0.001
    pre = to_cell(layout, "precharge_slice", built["precharge_slice"][0])
    io = to_cell(layout, "io_slice", built["io_slice"][0])
    make_band(layout, pre, "precharge_band")
    make_band(layout, io, "io_band")
    path = os.path.join(args.out_dir, "column_band.gds")
    layout.write(path, save_options())
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
