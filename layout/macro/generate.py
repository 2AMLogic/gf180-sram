#!/usr/bin/env python3
"""Assemble the committed blocks into the macro: ``sram_256x32``.

Issue #247 (child of #206). Places the blocks drawn by #204/#205/#246 around the
centre-fed 4:1 floorplan ratified in ``spec/wordline-rc-decision.md`` and wires
them with Metal2/Metal3 (plus short Metal1/Via1 joins), so the top cell
``sram_256x32`` exposes exactly the 107 signal pins and ``VDD``/``VSS`` of
``spec/macro-interface-decision.md``. Nothing is re-drawn: every block is the
committed GDS (copied in as a child cell, hierarchy kept).

## Floorplan (x to the right, y up; origin = array row 0, left cell edge)

::

     VDD / VSS straps (Metal3, top edge)
     +--------------+ ch +---------+ ch +--------------+
     | precharge x16|    |         |    | precharge x16|   y = 345.6 .. 353.1
     | array half   |    |  row    |    | array half   |   64 rows x 64 cols
     | (mirrored)   | CL | decoder | CR |              |   each
     | io x16       |    |  strip  |    | io x16       |   y = -58.5 .. 0
     +--------------+    +---------+    +--------------+
                         | sram_ctrl | col_decode |       below the strip
     bottom edge: A CEN GWEN CLK (ctrl), D WEN Q (slice i), Metal2

* Two 64-column halves of the array (``layout/sram_256x32/generate.py``, the
  generator that drew ``layout/sram_64x128/sram_64x128_array.gds``) around the
  row strip: the left half is mirrored so its landing-pad strip faces the strip,
  the right half is not. :func:`check_half_against_committed` asserts the half is
  geometrically the committed 64 x 128 file's columns 0..63, so the committed file
  is the reference, not a stand-in.
* The column slices are 16 + 16 (``io_slice`` below, ``precharge_slice`` above),
  mirrored together with the half they sit under, so every bit-line stub stays on
  its array stripe.
* ``WL<k>``: each strip pin (Metal3, both strip edges) is joined to that row's
  Metal1 landing pad by a Metal3 bar, Via2, a Metal2 pad and Via1.
* Channels CL / CR carry Metal2 risers for the thirteen band control nets
  (``csel0..3``, ``cseln0..3``, ``clk_buf``, ``wl_en_n``, ``s_en``, ``q_clk``,
  ``wpn``) up to the Metal3 buses the slices already draw, and the supply trunks.
* The control block and the column decoder (rotated 180 degrees, so its inputs
  face up) sit below the strip. Their wiring is a top channel (Metal3 tracks, one
  per net, Metal2 risers) and a bottom channel.
* Pins: ``A``/``CEN``/``GWEN``/``CLK`` are the control block's Metal2 pins;
  ``D``/``WEN``/``Q`` are the slices' Metal2 pins prolonged straight down to the
  same bottom edge. ``VDD``/``VSS`` are two Metal3 straps along the top edge.

## What this is not

Routing is generated for connectivity and DRC, not optimised: no parasitic, timing
or wordline-RC statement, no area claim. The pin stubs are far longer than the
foundry's 5 um because the control block (171 um tall) sits below the array bands.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

import klayout.db as kdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOP_CELL = "sram_256x32"
OUT_GDS = os.path.join(HERE, f"{TOP_CELL}.gds")
ARRAY64_GDS = os.path.join(ROOT, "layout", "sram_64x128", "sram_64x128_array.gds")


def _load(name: str, rel: str):
    path = os.path.join(ROOT, rel)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


array = _load("_sram_array_generate", "layout/sram_256x32/generate.py")
bitcell = array.bitcell
col = _load("_sram_column_generate", "layout/periphery/column/generate.py")

BLOCKS = {
    "io_slice": "layout/periphery/column/io_slice.gds",
    "precharge_slice": "layout/periphery/column/precharge_slice.gds",
    "row_path": "layout/periphery/row/row_path.gds",
    "sram_ctrl": "layout/periphery/control/sram_ctrl.gds",
    "col_decode": "layout/periphery/control/col_decode.gds",
}

# Layers ----------------------------------------------------------------------
L_M1, L_V1, L_M2 = bitcell.L_METAL1, bitcell.L_VIA1, bitcell.L_METAL2
L_V2, L_M3 = col.L_VIA2, col.L_METAL3
L_M2_LBL, L_M3_LBL = bitcell.L_METAL2_LBL, col.L_METAL3_LBL
LBL_OF = {L_M1: bitcell.L_METAL1_LBL, L_M2: L_M2_LBL, L_M3: L_M3_LBL}

# Geometry --------------------------------------------------------------------
W_CELL = bitcell.W_CELL                       # 4.46
H_CELL = bitcell.H_CELL                       # 5.40
SLICE_W = col.SLICE_W                         # 17.84
HALF_COLS = 64
ROWS = 64
PB = array.WL_PAD_BAND                        # 0.43 landing-pad strip
AW = round(HALF_COLS * W_CELL, 3)             # 285.44 tiled cells per half
H_ARR = round(ROWS * H_CELL, 3)               # 345.6
HW = 0.175                                    # half of a 0.35 wire
VIA = col.VIA_SZ                              # 0.26
HV = 0.5 * VIA
TRK = 0.65                                    # track pitch of the channel risers/tracks

CHL = 14.0                                    # left channel (risers, trunks)
CHR = 30.0                                    # right channel (+ column decoder)
TOP_CH = 16.0                                 # control top channel
BOT_CH = 16.0                                 # control bottom channel

# Band control nets (macro net -> io_slice bus label); precharge buses carry csel only
BAND_NETS = ["csel0", "csel1", "csel2", "csel3", "cseln0", "cseln1", "cseln2", "cseln3",
             "clk_buf", "wl_en_n", "s_en", "q_clk", "wpn"]
IO_BUS = {n: n for n in BAND_NETS}
IO_BUS["clk_buf"] = "clk"


def nm(v: float) -> int:
    return int(round(v * 1000))


def snap(v: float) -> float:
    return round(round(v / 0.005) * 0.005, 3)


# ---------------------------------------------------------------------------
# Source blocks
# ---------------------------------------------------------------------------
def source_labels(path: str) -> list[tuple[tuple[int, int], str, float, float]]:
    ly = kdb.Layout()
    ly.read(path)
    top = ly.top_cells()[0]
    out = []
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        for s in top.shapes(li).each():
            if s.is_text():
                out.append(((info.layer, info.datatype), s.text.string,
                            s.text.x * ly.dbu, s.text.y * ly.dbu))
    return out


def strip_texts(layout: kdb.Layout, cell: kdb.Cell) -> None:
    """Remove every text from ``cell`` and its subtree: a child's local labels
    would otherwise name 32 physically distinct nets alike."""
    todo = [cell.cell_index()] + list(cell.called_cells())
    for ci in todo:
        c = layout.cell(ci)
        for li in layout.layer_indexes():
            sh = c.shapes(li)
            for s in [s for s in sh.each() if s.is_text()]:
                sh.erase(s)


def import_block(layout: kdb.Layout, name: str, path: str) -> kdb.Cell:
    src = kdb.Layout()
    src.read(path)
    top = src.top_cells()[0]
    dst = layout.create_cell(name)
    dst.copy_tree(top)
    strip_texts(layout, dst)
    return dst


def import_half(layout: kdb.Layout) -> kdb.Cell:
    src = array.build(ROWS, HALF_COLS, "sram_64x64_half")
    dst = layout.create_cell("sram_64x64_half")
    dst.copy_tree(src.cell("sram_64x64_half"))
    strip_texts(layout, dst)
    return dst


def check_half_against_committed(layout: kdb.Layout, half: kdb.Cell) -> None:
    """The half must be columns 0..63 of the committed 64 x 128 array, layer by
    layer (the committed file's wider Metal3 straps clipped to the half)."""
    ref = kdb.Layout()
    ref.read(ARRAY64_GDS)
    rtop = ref.cell("sram_64x128_array")
    win = kdb.Box(0, -10000, nm(PB + AW), nm(H_ARR) + 10000)
    n = 0
    for lp in sorted({(i.layer, i.datatype) for i in ref.layer_infos()}):
        if lp[1] == 10:
            continue
        ri = ref.find_layer(*lp)
        hi = layout.find_layer(*lp)
        r = kdb.Region(rtop.begin_shapes_rec_touching(ri, win)) & kdb.Region(win)
        h = kdb.Region(half.begin_shapes_rec(hi)) if hi is not None else kdb.Region()
        r.merge()
        h.merge()
        if not (r ^ h).is_empty():
            raise SystemExit(f"half array differs from the committed 64x128 array on {lp}")
        n += 1
    print(f"half array == committed 64x128 columns 0..63 on {n} layers")


# ---------------------------------------------------------------------------
# Wiring helper
# ---------------------------------------------------------------------------
class Macro:
    def __init__(self) -> None:
        self.ly = kdb.Layout()
        self.ly.dbu = 0.001
        self.top: kdb.Cell | None = None
        self.nets: dict[str, int] = {}
        self.pins: list[tuple[str, tuple[int, int], float, float]] = []

    def li(self, lp: tuple[int, int]) -> int:
        i = self.ly.layer(*lp)
        self.ly.set_info(i, kdb.LayerInfo(lp[0], lp[1], col._LAYER_NAMES.get(lp, "")))
        return i

    def box(self, lp, x0, y0, x1, y1) -> None:
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        self.top.shapes(self.li(lp)).insert(kdb.Box(nm(x0), nm(y0), nm(x1), nm(y1)))

    def wire(self, lp, x0, y0, x1, y1, hw=HW) -> None:
        """Rectangle between two points, ``hw`` half-width around the segment."""
        self.box(lp, min(x0, x1) - (hw if y0 == y1 else hw), min(y0, y1) - hw,
                 max(x0, x1) + hw, max(y0, y1) + hw) if False else None
        self.box(lp, min(x0, x1) - hw, min(y0, y1) - hw, max(x0, x1) + hw, max(y0, y1) + hw)

    def via(self, lp, x, y) -> None:
        self.box(lp, x - HV, y - HV, x + HV, y + HV)

    def text(self, lp, name, x, y) -> None:
        self.top.shapes(self.li(lp)).insert(kdb.Text(name, kdb.Trans(nm(x), nm(y))))

    def inst(self, cell: kdb.Cell, trans: kdb.Trans) -> None:
        self.top.insert(kdb.CellInstArray(cell.cell_index(), trans))

    def inst_row(self, cell: kdb.Cell, trans: kdb.Trans, n: int, pitch: float) -> None:
        self.top.insert(kdb.CellInstArray(cell.cell_index(), trans,
                                          kdb.Vector(nm(pitch), 0), kdb.Vector(0, 0), n, 1))

    def route_m3_m2(self, x, y) -> None:
        """Via2 between a Metal2 riser and a Metal3 bar crossing at (x, y)."""
        self.via(L_V2, x, y)


def build() -> kdb.Layout:
    m = Macro()
    ly = m.ly
    m.top = ly.create_cell(TOP_CELL)

    cells = {n: import_block(ly, n, os.path.join(ROOT, p)) for n, p in BLOCKS.items()}
    half = import_half(ly)
    check_half_against_committed(ly, half)

    # -- source geometry read back from the committed blocks ---------------------
    lab = {n: source_labels(os.path.join(ROOT, p)) for n, p in BLOCKS.items()}
    bb = {n: cells[n].dbbox() for n in cells}
    io_h, pre_h = bb["io_slice"].height(), bb["precharge_slice"].height()
    assert abs(bb["io_slice"].width() - SLICE_W) < 1e-6
    strip_w, strip_h = bb["row_path"].width(), bb["row_path"].height()

    def lbl(block, name, lp=None):
        hits = [(x, y) for (l, n, x, y) in lab[block] if n == name and (lp is None or l == lp)]
        return hits

    wl_y = 0.5 * (bitcell.Y_WL_BOT + bitcell.Y_WL_TOP)
    y_arr0 = round(lbl("row_path", "wl0", L_M3_LBL)[0][1] - wl_y, 3)   # strip frame y of array row 0

    # -- x / y frame ------------------------------------------------------------
    XLP = round(AW + PB, 3)                  # left half: mirror axis (x -> XLP - x)
    SX = round(XLP + CHL, 3)                 # strip left edge
    SR = round(SX + strip_w, 3)              # strip right edge
    XRA = round(SR + CHR, 3)                 # right half origin (its pad band starts here)
    XRC = round(XRA + PB, 3)                 # right cells start
    X_END = round(XRC + AW, 3)
    Y_IO = -io_h                             # io band bottom
    Y_PRE = H_ARR                            # precharge band bottom
    Y_PRE_TOP = round(Y_PRE + pre_h, 3)
    SY = round(-y_arr0, 3)                   # strip frame origin y
    Y_STRIP_BOT = SY
    Y_STRIP_TOP = round(SY + strip_h, 3)

    # -- arrays and bands --------------------------------------------------------
    m.inst(half, kdb.Trans(kdb.Trans.M90, nm(XLP), 0))          # mirrored: pads face the strip
    m.inst(half, kdb.Trans(kdb.Trans.R0, nm(XRA), 0))
    io, pre = cells["io_slice"], cells["precharge_slice"]
    m.inst_row(io, kdb.Trans(kdb.Trans.M90, nm(SLICE_W), nm(Y_IO)), 16, SLICE_W)
    m.inst_row(pre, kdb.Trans(kdb.Trans.M90, nm(SLICE_W), nm(Y_PRE)), 16, SLICE_W)
    m.inst_row(io, kdb.Trans(kdb.Trans.R0, nm(XRC), nm(Y_IO)), 16, SLICE_W)
    m.inst_row(pre, kdb.Trans(kdb.Trans.R0, nm(XRC), nm(Y_PRE)), 16, SLICE_W)
    m.inst(cells["row_path"], kdb.Trans(kdb.Trans.R0, nm(SX), nm(SY)))

    # -- control block (under the strip) and column decoder ----------------------
    ctrl_w, ctrl_h = bb["sram_ctrl"].right, bb["sram_ctrl"].top
    cd_w, cd_h = bb["col_decode"].right, bb["col_decode"].top
    Y_CTRL_TOP = round(Y_STRIP_BOT - TOP_CH, 3)
    YA = round(Y_CTRL_TOP - ctrl_h, 3)            # ctrl origin y = its bottom edge
    Y_B = round(YA - BOT_CH, 3)                   # macro bottom edge

    wire_macro(m, cells, lab, dict(
        XLP=XLP, SX=SX, SR=SR, XRA=XRA, XRC=XRC, X_END=X_END, Y_IO=Y_IO, Y_PRE=Y_PRE,
        Y_PRE_TOP=Y_PRE_TOP, SY=SY, Y_STRIP_BOT=Y_STRIP_BOT, Y_CTRL_TOP=Y_CTRL_TOP, YA=YA,
        Y_B=Y_B, ctrl_w=ctrl_w, cd_w=cd_w, cd_h=cd_h, wl_y=wl_y))
    return m.ly


def spacing_of(lp) -> float:
    return 0.30


def near_region(m: Macro, lp, x0, y0, x1, y1, pad) -> kdb.Region:
    li = m.ly.find_layer(*lp)
    if li is None:
        return kdb.Region()
    box = kdb.Box(nm(min(x0, x1) - pad), nm(min(y0, y1) - pad), nm(max(x0, x1) + pad), nm(max(y0, y1) + pad))
    r = kdb.Region(m.top.begin_shapes_rec_touching(li, box))
    r.merge()
    return r


def clear(m: Macro, lp, rect, anchors=(), spacing=0.30) -> bool:
    """True when a new ``rect`` on ``lp`` keeps ``spacing`` to everything already placed,
    except the polygons touching an anchor point (the net it is meant to join)."""
    x0, y0, x1, y1 = rect
    near = near_region(m, lp, x0, y0, x1, y1, spacing + 0.1)
    if anchors:
        pts = kdb.Region()
        for (ax, ay) in anchors:
            pts.insert(kdb.Box(nm(ax) - 2, nm(ay) - 2, nm(ax) + 2, nm(ay) + 2))
        near = near - near.interacting(pts)
    new = kdb.Region(kdb.Box(nm(x0), nm(y0), nm(x1), nm(y1))).sized(nm(spacing) - 1)
    return (new & near).is_empty()


def covered(m: Macro, lp, rect) -> bool:
    """True when ``rect`` lies wholly inside shapes of ``lp`` already placed."""
    x0, y0, x1, y1 = rect
    near = near_region(m, lp, x0, y0, x1, y1, 0.2)
    new = kdb.Region(kdb.Box(nm(x0), nm(y0), nm(x1), nm(y1)))
    return (new - near).is_empty()


def wire_macro(m: Macro, cells, lab, g: dict) -> None:
    XLP, SX, SR, XRA, XRC, X_END = (g[k] for k in ("XLP", "SX", "SR", "XRA", "XRC", "X_END"))
    Y_IO, Y_PRE, Y_PRE_TOP, SY = g["Y_IO"], g["Y_PRE"], g["Y_PRE_TOP"], g["SY"]
    Y_STRIP_BOT, Y_CTRL_TOP, YA, Y_B = g["Y_STRIP_BOT"], g["Y_CTRL_TOP"], g["YA"], g["Y_B"]
    ctrl_w, cd_w, cd_h, wl_y = g["ctrl_w"], g["cd_w"], g["cd_h"], g["wl_y"]
    AL_END = AW                                     # left cells end (= left band end)
    L2 = L_M2_LBL

    def pin_of(block, name, lp=L2):
        hits = [(x, y) for (l, n, x, y) in lab[block] if n == name and l == lp]
        assert len(hits) == 1, (block, name, hits)
        return hits[0]

    # ---- wordline joins: strip pin (Metal3) -> Metal3 bar -> Via2 -> Metal2 -> Via1 -> pad ----
    for k in range(ROWS):
        yk = round(k * H_CELL + wl_y, 3)
        for side in ("L", "R"):
            # A short Metal2 jog carries the join 0.9 um out of the pad band, so the
            # Metal3 bar clears the array's own Metal3 supply straps (row 63's wordline
            # sits within a spacing of them).
            if side == "L":
                xc = round(XLP - 0.5 * array.WL_PAD_M1_W, 3)
                xj = round(xc + 0.9, 3)
                bar = (xj - 0.19, yk, SX + 0.35, yk)
            else:
                xc = round(XRA + 0.5 * array.WL_PAD_M1_W, 3)
                xj = round(xc - 0.9, 3)
                bar = (SR - 0.35, yk, xj + 0.19, yk)
            m.wire(L_M3, *bar, hw=HW)
            m.via(L_V2, xj, yk)
            m.box(L_M2, min(xc, xj) - 0.19, yk - 0.20, max(xc, xj) + 0.19, yk + 0.20)
            m.via(L_V1, xc, yk)

    # ---- pin lists of the blocks, in world coordinates ---------------------------
    io_stub = {n: pin_of("io_slice", n)[0] for n in ("d_in", "wen_in", "q_out")}
    bus_y_io = {n: y for (l, n, x, y) in lab["io_slice"] if l == L_M3_LBL}
    bus_y_pre = {n: y for (l, n, x, y) in lab["precharge_slice"] if l == L_M3_LBL}

    # ---- slice pins: Metal2 stubs prolonged down to the macro bottom edge -------------
    for j in range(32):
        for bus, stub in (("D", "d_in"), ("WEN", "wen_in"), ("Q", "q_out")):
            fx = io_stub[stub]
            x = round((j + 1) * SLICE_W - fx, 3) if j < 16 else round(XRC + (j - 16) * SLICE_W + fx, 3)
            m.box(L_M2, x - HW, Y_B, x + HW, Y_IO + 1.0)
            m.pins.append((f"{bus}[{j}]", L_M2_LBL, x, Y_B + 0.65))

    # ---- choose the control block's x offset so top-channel risers keep apart ----------
    cd_in = {n: pin_of("col_decode", n)[0] for n in ("aq0", "aqb0", "aq1", "aqb1", "wl_en")}
    ctrl_top_x = {n: pin_of("sram_ctrl", n)[0] for n in
                  [f"aq{i}" for i in range(8)] + [f"aqb{i}" for i in range(8)] + ["wl_en"]}
    strip_x = {n: pin_of("row_path", n)[0] for n in
               [f"aq{i}" for i in range(2, 8)] + [f"aqb{i}" for i in range(2, 8)] + ["wl_en"]}
    cd_nets = ("aq0", "aqb0", "aq1", "aqb1", "wl_en")
    top_nets = [f"aq{i}" for i in range(8)] + [f"aqb{i}" for i in range(8)] + ["wl_en"]

    def top_xs(dx):
        xc = SX + dx
        xcd1 = xc + ctrl_w + 4.0 + cd_w
        pts = {}
        for n in top_nets:
            pts.setdefault(n, []).append(round(xc + ctrl_top_x[n], 3))
            if n in strip_x:
                pts[n].append(round(SX + strip_x[n], 3))
            if n in cd_nets:
                pts[n].append(round(xcd1 - cd_in[n], 3))
        return pts, xc, xcd1

    best = None
    for step in range(0, 800):
        dx = step * 0.005
        pts, _, _ = top_xs(dx)
        flat = [(x, n) for n, xs in pts.items() for x in xs]
        gap = min(abs(a[0] - b[0]) for i, a in enumerate(flat) for b in flat[i + 1:] if a[1] != b[1])
        if best is None or gap > best[0] + 1e-9:
            best = (gap, dx)
    gap, dx_c = best
    dx_c = snap(dx_c)
    pts, XC, XCD1 = top_xs(dx_c)
    assert gap >= 0.55, f"top-channel risers only {gap:.3f} um apart"
    print(f"control block at x={XC:.3f}; top-channel riser gap {gap:.3f} um")
    m.inst(cells["sram_ctrl"], kdb.Trans(kdb.Trans.R0, nm(XC), nm(YA)))
    m.inst(cells["col_decode"], kdb.Trans(kdb.Trans.R180, nm(XCD1), nm(Y_CTRL_TOP)))
    Y_CD_BOT = round(Y_CTRL_TOP - cd_h, 3)

    # ---- top channel: one Metal3 track per net, Metal2 risers ----------------------------
    for i, n in enumerate(top_nets):
        yt = round(Y_CTRL_TOP + 2.0 + TRK * i, 3)
        xs = pts[n]
        m.wire(L_M3, min(xs), yt, max(xs), yt)
        xcn = round(XC + ctrl_top_x[n], 3)
        m.box(L_M2, xcn - HW, Y_CTRL_TOP - 0.3, xcn + HW, yt + HW)
        m.via(L_V2, xcn, yt)
        if n in strip_x:
            xs_ = round(SX + strip_x[n], 3)
            m.box(L_M2, xs_ - HW, yt - HW, xs_ + HW, Y_STRIP_BOT + 0.3)
            m.via(L_V2, xs_, yt)
        if n in cd_nets:
            xd = round(XCD1 - cd_in[n], 3)
            m.box(L_M2, xd - HW, Y_CTRL_TOP - 0.3, xd + HW, yt + HW)
            m.via(L_V2, xd, yt)

    # ---- control block pins (bottom): external, and band outputs --------------------------
    ctrl_bot = {n: pin_of("sram_ctrl", n)[0] for n in
                [f"A{i}" for i in range(8)] + ["CEN", "GWEN", "CLK"] + ["clk_buf", "wl_en_n", "s_en", "q_clk", "wpn"]}
    for i in range(8):
        pass
    ext = {f"A{i}": f"A[{i}]" for i in range(8)}
    ext.update({"CEN": "CEN", "GWEN": "GWEN", "CLK": "CLK"})
    for n, pname in ext.items():
        x = round(XC + ctrl_bot[n], 3)
        m.box(L_M2, x - HW, Y_B, x + HW, YA + 0.3)
        m.pins.append((pname, L_M2_LBL, x, Y_B + 0.65))

    # ---- band control nets: bottom-channel tracks and the left/right risers -------------------
    x_L = {n: round(XLP + 1.5 + TRK * i, 3) for i, n in enumerate(BAND_NETS)}
    x_R = {n: round(SR + 13.5 + TRK * i, 3) for i, n in enumerate(BAND_NETS)}
    cd_out = {n: pin_of("col_decode", n)[0] for n in BAND_NETS[:8]}
    src_x = {}
    for n in BAND_NETS[:8]:
        src_x[n] = (round(XCD1 - cd_out[n], 3), Y_CD_BOT)
    for n in BAND_NETS[8:]:
        src_x[n] = (round(XC + ctrl_bot[n], 3), YA)
    for i, n in enumerate(BAND_NETS):
        yt = round(YA - 2.0 - TRK * i, 3)
        sx, sy = src_x[n]
        assert x_L[n] < sx < x_R[n]
        m.wire(L_M3, x_L[n], yt, x_R[n], yt)
        m.box(L_M2, sx - HW, yt - HW, sx + HW, sy + 0.3)
        m.via(L_V2, sx, yt)
        io_y = Y_IO + bus_y_io[IO_BUS[n]]
        taps = [io_y]
        if n in bus_y_pre:
            taps.append(Y_PRE + bus_y_pre[n])
        for side, xr in (("L", x_L[n]), ("R", x_R[n])):
            m.via(L_V2, xr, yt)
            m.box(L_M2, xr - HW, yt - HW, xr + HW, max(taps) + HW)
            for ty in taps:
                m.via(L_V2, xr, ty)
                if side == "L":
                    m.wire(L_M3, AL_END - 0.2, ty, xr, ty)
                else:
                    m.wire(L_M3, xr, ty, XRC + 0.2, ty)

    # ================= supply =================================================================
    TRUNK = {"L": {"VDD": round(SX - 3.0, 3), "VSS": round(SX - 1.8, 3)},
             "R": {"VSS": round(SR + 23.4, 3), "VDD": round(SR + 24.6, 3)}}
    taps_y = {(s, n): [] for s in "LR" for n in ("VDD", "VSS")}

    def label_pts(block, net, lp):
        return [(x, y) for (l, n, x, y) in lab[block] if n == net and l == lp]

    def poly_bbox(cell, lp, x, y):
        li = m.ly.find_layer(*lp)
        r = kdb.Region(cell.begin_shapes_rec(li))
        r.merge()
        hit = r.interacting(kdb.Region(kdb.Box(nm(x) - 2, nm(y) - 2, nm(x) + 2, nm(y) + 2)))
        assert not hit.is_empty(), (cell.name, lp, x, y)
        b = hit.bbox()
        return b.left * 0.001, b.bottom * 0.001, b.right * 0.001, b.top * 0.001

    def rail_at_edge(block, net, wy0):
        """(y_lo, y_hi) of a ``net`` Metal1 rail of the slice where it meets frame x = 0."""
        li = m.ly.find_layer(*L_M1)
        r = kdb.Region(cells[block].begin_shapes_rec(li))
        r.merge()
        edge = r & kdb.Region(kdb.Box(0, -1000, 60, nm(60.0)))
        for (px, py) in label_pts(block, net, bitcell.L_METAL1_LBL):
            poly = r.interacting(kdb.Region(kdb.Box(nm(px) - 2, nm(py) - 2, nm(px) + 2, nm(py) + 2)))
            e = edge & poly
            if not e.is_empty():
                b = e.bbox()
                return wy0 + b.bottom * 0.001, wy0 + b.top * 0.001
        raise SystemExit(f"no {net} rail reaches the {block} band edge")

    # -- band rails -> trunks (Metal1 bar, Via1 onto the Metal2 trunk) ------------------------
    for block, wy0 in (("io_slice", Y_IO), ("precharge_slice", Y_PRE)):
        for net in ("VDD", "VSS"):
            ylo, yhi = rail_at_edge(block, net, wy0)
            yc = round(0.5 * (ylo + yhi), 3)
            for side in "LR":
                xt = TRUNK[side][net]
                if side == "L":
                    m.box(L_M1, AL_END - 0.2, yc - 0.2, xt + 0.19, yc + 0.2)
                else:
                    m.box(L_M1, xt - 0.19, yc - 0.2, XRC + 0.2, yc + 0.2)
                m.via(L_V1, xt, yc)
                taps_y[(side, net)].append(yc)

    # -- strip / control / column decoder straps -> trunks (Metal3 bar, Via2) ------------------
    def strap_bar(net, side, x_strap, ylo, yhi):
        xt = TRUNK[side][net]
        y = ylo + 1.0
        while y < yhi - 1.0:
            y = snap(y)
            rect = (min(x_strap, xt) - 0.19, y - 0.19, max(x_strap, xt) + 0.19, y + 0.19)
            v2 = (x_strap - HV, y - HV, x_strap + HV, y + HV)
            if clear(m, L_M3, rect) and clear(m, L_V2, v2, spacing=0.28):
                m.wire(L_M3, x_strap, y, xt, y, hw=0.19)
                m.via(L_V2, x_strap, y)
                m.via(L_V2, xt, y)
                taps_y[(side, net)].append(y)
                return
            y += TRK
        raise SystemExit(f"no clear spot for a {net} strap bar at x={x_strap:.3f}")

    for net in ("VSS", "VDD"):
        # strip (left channel)
        sx, sy = label_pts("row_path", net, L_M2_LBL)[0]
        b = poly_bbox(cells["row_path"], L_M2, sx, sy)
        strap_bar(net, "L", round(SX + sx, 3), SY + b[1], SY + b[3])
        # control block (left channel)
        cx, cy = label_pts("sram_ctrl", net, L_M2_LBL)[0]
        b = poly_bbox(cells["sram_ctrl"], L_M2, cx, cy)
        strap_bar(net, "L", round(XC + cx, 3), YA + b[1], YA + b[3])
        # column decoder, rotated 180 degrees (right channel)
        dx_, dy_ = label_pts("col_decode", net, L_M2_LBL)[0]
        b = poly_bbox(cells["col_decode"], L_M2, dx_, dy_)
        strap_bar(net, "R", round(XCD1 - dx_, 3), Y_CTRL_TOP - b[3], Y_CTRL_TOP - b[1])

    # -- array <-> precharge band seam (top): Metal2 bridge from the array's stripe to the rail --
    stripe = {"VDD": bitcell.X_VDD_M2_C, "VSS": bitcell.X_VSS_M2_C}
    for side in "LR":
        for net in ("VDD", "VSS"):
            ylo, yhi = rail_at_edge("precharge_slice", net, Y_PRE)
            done = False
            for c in range(HALF_COLS):
                fx = PB + c * W_CELL + stripe[net]
                cx = round(XLP - fx, 3) if side == "L" else round(XRA + fx, 3)
                for yv in [round(0.5 * (ylo + yhi) + d, 3) for d in (0, 0.2, -0.2, 0.4, -0.4)]:
                    if not (ylo + 0.1 <= yv <= yhi - 0.1) and (yhi - ylo) > 0.5:
                        continue
                    via_box = (cx - HV - 0.06, yv - HV - 0.06, cx + HV + 0.06, yv + HV + 0.06)
                    if not covered(m, L_M1, via_box):
                        continue
                    bridge = (cx - 0.19, H_ARR - 0.5, cx + 0.19, yv + 0.2)
                    if not clear(m, L_M2, bridge, anchors=[(cx, H_ARR - 0.3)]):
                        continue
                    if not clear(m, L_V1, (cx - HV, yv - HV, cx + HV, yv + HV), spacing=0.28):
                        continue
                    m.box(L_M2, *bridge)
                    m.via(L_V1, cx, yv)
                    done = True
                    break
                if done:
                    break
            if not done:
                raise SystemExit(f"no seam bridge for {net} on side {side}")

    # -- trunks and the top-edge Metal3 straps ----------------------------------------------------
    Y0 = round(Y_PRE_TOP + 2.0, 3)
    strap_y = {"VSS": (Y0, Y0 + 1.5), "VDD": (round(Y0 + 2.5, 3), round(Y0 + 4.0, 3))}
    for side in "LR":
        for net in ("VDD", "VSS"):
            xt = TRUNK[side][net]
            lo = min(taps_y[(side, net)]) - 0.3
            sy0, sy1 = strap_y[net]
            yc = 0.5 * (sy0 + sy1)
            m.box(L_M2, xt - 0.3, lo, xt + 0.3, yc + 0.7)
            for dy in (-0.3, 0.3):
                m.via(L_V2, xt, yc + dy)
    for net in ("VDD", "VSS"):
        sy0, sy1 = strap_y[net]
        m.box(L_M3, 0.0, sy0, X_END, sy1)
        m.pins.append((net, L_M3_LBL, round(0.5 * X_END, 3), round(0.5 * (sy0 + sy1), 3)))

    for name, lp, x, y in m.pins:
        m.text(lp, name, x, y)


def save_options() -> kdb.SaveLayoutOptions:
    return array.save_options()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default=OUT_GDS)
    args = ap.parse_args()
    ly = build()
    ly.write(args.out, save_options())
    bb = ly.cell(TOP_CELL).dbbox()
    print(f"wrote {args.out}: {bb.width():.3f} x {bb.height():.3f} um "
          f"({bb.width() * bb.height() / 1e6:.4f} mm^2), origin of the array at (0, 0)")


if __name__ == "__main__":
    main()
