"""Shared layout engine for the periphery generators (issue #505).

Everything the column path (#205), the row decoder strip (#204) and the
control block / column decoder (#246) draw with used to live inside
``layout/periphery/column/generate.py`` and be reached from the other two by
monkey-patching that module's globals (``NCOLS``, ``SLICE_W``) before each
build -- an order-dependent hazard the moment two generators share one
process. It lives here once now, unchanged in behaviour:

* the layer / geometry constants of the 0.65 um routing grid,
* the SPICE subckt parser and flattener (``parse_spice`` / ``flatten``),
* the 3-layer grid A* ``Router`` -- whose A* bound is the per-column
  ``bisect`` Manhattan minimum (the fast bound #299 introduced as
  ``FastRouter``; the naive min-scan version computed the same value and is
  gone),
* ``Ctx`` (shapes + labels + router) and the strip placer
  (``Strip`` / ``layout_strip``: chains of single-finger devices between two
  supply rails),
* the route / emit / GDS helpers (``add_bottom_pin``, ``route``,
  ``emit_routes``, ``to_cell``) and the ``dff`` chain table
  (``dff_chains``),
* the per-strip rail / implant / strap helpers the row generator
  contributed (``Plan`` / ``layout_cells`` / ``draw_plan`` / ``add_strap``).

What each generator passes in instead of mutating globals: the grid width
``ncols`` (``Router`` / ``Ctx`` take it explicitly; ``layout_strip`` reads it
from the ``Ctx``). The column defaults (``SLICE_W``, ``NCOLS``, ``X0``)
remain module constants here because ``X0`` -- the x of grid column 0 --
is shared by every generator's grid, whatever its width.

No geometry, routing order, tie-breaking or A* heuristic value differs from
the pre-extraction engine: the committed GDS files regenerate byte-for-byte
(``layout/verify.sh`` step 1). See ``layout/periphery/column/generate.py``'s
docstring ("Grid") for the spacing argument behind ``G = 0.65 um``.
"""

from __future__ import annotations

import bisect
import heapq
import itertools
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field

import klayout.db as kdb

from layout.common import (
    ARRAY_LAYER_NAMES,
    L_METAL3,
    L_METAL3_LBL,
    L_VIA2,
    ROOT,
    load_module,
    nm,
    register_layer,
)

bitcell = load_module("_sram_bitcell_generate", "layout/bitcell/generate.py")
NETLIST_DIR = os.path.join(ROOT, "design", "netlist")

# ---------------------------------------------------------------------------
# Layers (GDS layer/datatype) -- the bitcell's, plus Via2/Metal3 (as the
# array). The Via2/Metal3 numbers and names are shared with the array
# generator through layout.common (issue #475); the name table below covers
# every layer this periphery draws on.
# ---------------------------------------------------------------------------
L_NWELL, L_COMP, L_POLY2 = bitcell.L_NWELL, bitcell.L_COMP, bitcell.L_POLY2
L_PPLUS, L_NPLUS, L_CONTACT = bitcell.L_PPLUS, bitcell.L_NPLUS, bitcell.L_CONTACT
L_METAL1, L_VIA1, L_METAL2 = bitcell.L_METAL1, bitcell.L_VIA1, bitcell.L_METAL2
L_METAL1_LBL, L_METAL2_LBL = bitcell.L_METAL1_LBL, bitcell.L_METAL2_LBL
_LAYER_NAMES = {**bitcell._LAYER_NAMES, **ARRAY_LAYER_NAMES}
METAL = (L_METAL1, L_METAL2, L_METAL3)

# ---------------------------------------------------------------------------
# Geometry constants (um). Rule ids are gf180mcu DRM ids; "curated" = klt's
# bundled deck, "native" = the PDK's own deck under libs.tech/klayout.
# ---------------------------------------------------------------------------
SLICE_W = round(4 * bitcell.W_CELL, 3)  # 17.84: one I/O = four bitcell columns
G = 0.65  # routing grid pitch (see the column generator's docstring, "Grid")
NCOLS = 26
X0 = round(0.5 * (SLICE_W - (NCOLS - 1) * G), 3)  # x of column 0 (0.795)

CO = bitcell.CO_SIZE  # 0.22   CO.1
HCO = 0.5 * CO
PAD = 0.38  # Poly2 / Metal1 pad around one contact (CO.3 + margin, CO.6a)
HPAD = 0.5 * PAD
COMP_HALF = 0.18  # half-width of COMP around a contact column: CO.4 = 0.07 exactly

WIRE = 0.35  # Metal1/2/3 wire width: >= 0.341, so the "narrow line" EOL rules
HWIRE = 0.5 * WIRE  # (V1.3c/V1.4b/CO.6a, < 0.34 um) never apply
VIA_SZ = bitcell.V1_SIZE  # 0.26   V1.1 / V2.1
HVIA = 0.5 * VIA_SZ
L_GATE = bitcell.L_GATE  # 0.28
HGATE = 0.5 * L_GATE
L_LONG = 0.6  # the long-channel delay inverter (``inv_dly``, issue #246)


def hgate(dev) -> float:
    """Half the drawn poly width of ``dev``: its channel length."""
    return 0.5 * dev.l
POLY_EXT = 0.24  # PL.4 (0.22) + 0.02: poly past COMP
POLY_PAD_COMP = 0.10  # PL.5a_LV: field poly pad to COMP
IMP_ENC_GATE = bitcell.IMP_ENC_GATE  # 0.23 NP.5a / PP.5a
IMP_ENC_COMP = bitcell.IMP_ENC_COMP  # 0.16 NP.5b / PP.5b
IMP_SPACE = bitcell.IMP_SPACE  # 0.25 between Nplus and Pplus
NW_ENC_PCOMP = bitcell.NW_ENC_PCOMP  # 0.45, DF.4c_LV (0.43) + 0.02
NW_ENC_NCOMP = bitcell.NW_ENC_NCOMP  # 0.20, DF.4d_LV (0.12) + 0.08
RAIL_H = 0.40  # Metal1 supply rail (>= 0.34, contact enclosure 0.09)
M1_SPACE = 0.23  # M1.2a
M1_WIDE_SPACE = 0.30  # M1.2b / M2.2b / M3.2b: shape with an edge >= 10 um
STUB_W = bitcell.M1_STRIPE_W  # 0.30: bit-line stub == array stripe width
SUPPLY = {"N": "VSS", "P": "VDD"}


def X(c: float) -> float:
    return round(X0 + G * c, 3)


def Y(j: float) -> float:
    return round(G * j, 3)


# ---------------------------------------------------------------------------
# Netlist reader (SPICE subckts -> flat transistor list)
# ---------------------------------------------------------------------------
@dataclass
class Dev:
    name: str
    kind: str  # 'N' | 'P'
    w: float
    l: float
    d: str
    g: str
    s: str


@dataclass
class Subckt:
    ports: list
    mos: list = field(default_factory=list)  # (name, d, g, s, b, model, w, l)
    insts: list = field(default_factory=list)  # (name, nets, subckt)


def _logical_lines(path: str):
    out: list[str] = []
    with open(path) as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("*"):
                continue
            if line.startswith("+") and out:
                out[-1] += " " + line[1:].strip()
            else:
                out.append(line.strip())
    return out


def parse_spice(path: str) -> dict[str, Subckt]:
    subs: dict[str, Subckt] = {}
    cur: Subckt | None = None
    for line in _logical_lines(path):
        low = line.lower()
        if low.startswith(".subckt"):
            tok = line.split()
            cur = Subckt(ports=tok[2:])
            subs[tok[1]] = cur
        elif low.startswith(".ends"):
            cur = None
        elif cur is not None and line[0] in "Xx":
            m = re.match(
                r"X(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(nfet_03v3|pfet_03v3)\s+(.*)$",
                line,
            )
            if m:
                w = float(re.search(r"\bW=([0-9.]+)u", m.group(7)).group(1))
                l = float(re.search(r"\bL=([0-9.]+)u", m.group(7)).group(1))
                cur.mos.append((m.group(1), *m.group(2, 3, 4, 5, 6), w, l))
            else:
                tok = line.split()
                cur.insts.append((tok[0][1:], tok[1:-1], tok[-1]))
    return subs


def flatten(subs: dict[str, Subckt], top: str) -> list[Dev]:
    devs: list[Dev] = []

    def walk(name: str, path: str, netmap: dict[str, str]) -> None:
        sub = subs[name]

        def net(n: str) -> str:
            if n in netmap:
                return netmap[n]
            return f"{path}{n}" if path else n

        for (dn, d, g, s, b, model, w, l) in sub.mos:
            devs.append(
                Dev(
                    name=f"{path}{dn}",
                    kind="N" if model.startswith("nfet") else "P",
                    w=w, l=l, d=net(d), g=net(g), s=net(s),
                )
            )
        for (iname, nets, sname) in sub.insts:
            child = subs[sname]
            assert len(nets) == len(child.ports), (iname, sname)
            walk(sname, f"{path}{iname}.", {p: net(n) for p, n in zip(child.ports, nets)})

    top_map = {p: p for p in subs[top].ports}
    walk(top, "", top_map)
    return devs


# ---------------------------------------------------------------------------
# Maze router
# ---------------------------------------------------------------------------
M1, M2, M3 = 0, 1, 2
_STEP = {  # (layer, horizontal?) -> cost
    (M1, True): 1.0, (M1, False): 1.7,
    (M2, True): 2.4, (M2, False): 1.0,
    (M3, True): 1.0, (M3, False): 2.4,
}
VIA_COST = 5.0
LAYER_HALF = (HPAD, HWIRE, HWIRE)  # conservative node half-extent per layer


def _gap(a, b) -> float:
    dx = max(0.0, max(a[0] - b[2], b[0] - a[2]))
    dy = max(0.0, max(a[1] - b[3], b[1] - a[3]))
    return math.hypot(dx, dy)


class Router:
    def __init__(self, row_lo: int, row_hi: int, ncols: int):
        self.rlo, self.rhi = row_lo, row_hi
        self.ncols = ncols
        self.near: dict[tuple, set] = defaultdict(set)  # node -> nets of nearby statics
        self.enear: dict[tuple, set] = defaultdict(set)  # edge -> nets
        self.noviablock: set[tuple] = set()  # (c, r) where Via1 is forbidden
        self.owner: dict[tuple, str] = {}
        self.terms: dict[str, list[frozenset]] = defaultdict(list)
        self.routes: dict[str, tuple[set, set]] = {}
        self.via1: set[tuple] = set()
        self.via2: set[tuple] = set()

    # -- obstacles -----------------------------------------------------
    def add_obstacle(self, layer: int, rect, net: str, spacing: float) -> None:
        hp = LAYER_HALF[layer]
        x0, y0, x1, y1 = rect
        c_lo = int(math.floor((x0 - spacing - hp - 1.0 - X0) / G))
        c_hi = int(math.ceil((x1 + spacing + hp + 1.0 - X0) / G))
        r_lo = int(math.floor((y0 - spacing - hp - 1.0) / G))
        r_hi = int(math.ceil((y1 + spacing + hp + 1.0) / G))
        for c in range(max(0, c_lo), min(self.ncols - 1, c_hi) + 1):
            for r in range(max(self.rlo, r_lo), min(self.rhi, r_hi) + 1):
                node = (layer, c, r)
                cx, cy = X(c), Y(r)
                if _gap((cx - hp, cy - hp, cx + hp, cy + hp), rect) < spacing - 1e-9:
                    self.near[node].add(net)
                for key, box in (
                    ((layer, c, r, "h"), (cx - HWIRE, cy - HWIRE, X(c + 1) + HWIRE, cy + HWIRE)),
                    ((layer, c, r, "v"), (cx - HWIRE, cy - HWIRE, cx + HWIRE, Y(r + 1) + HWIRE)),
                ):
                    if _gap(box, rect) < spacing - 1e-9:
                        self.enear[key].add(net)

    # -- node / edge legality ------------------------------------------
    def node_ok(self, node, net) -> bool:
        _, c, r = node
        if c < 0 or c >= self.ncols or r < self.rlo or r > self.rhi:
            return False
        near = self.near.get(node)
        if near and (near - {net}):
            return False
        o = self.owner.get(node)
        return o is None or o == net

    def edge_ok(self, a, b, net) -> bool:
        (l, c, r), (_, c2, r2) = a, b
        key = (l, min(c, c2), min(r, r2), "h" if r == r2 else "v")
        near = self.enear.get(key)
        return not (near and (near - {net}))

    # -- search --------------------------------------------------------
    def _heuristic(self, targets):
        """A* bound: ``h(node)`` = minimum Manhattan distance to any target.

        Targets are bucketed per column with their rows sorted, so the bound
        is one ``bisect`` per column instead of a scan over every target node
        -- the scan is quadratic once a net owns a 500-node trunk (#299). The
        value is the same minimum the scan computed.
        """
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

    def _search(self, net, sources, targets):
        heap: list = []
        counter = itertools.count()
        dist: dict[tuple, float] = {}
        prev: dict[tuple, tuple] = {}
        h = self._heuristic(targets)

        for s in sorted(sources):
            st = (s, 0)
            dist[st] = 0.0
            heapq.heappush(heap, (h(s), next(counter), 0.0, st))
        while heap:
            _, _, g, st = heapq.heappop(heap)
            if g > dist.get(st, 1e18) + 1e-12:
                continue
            node, vflag = st
            if node in targets:
                path = [node]
                cur = st
                while cur in prev:
                    cur = prev[cur]
                    path.append(cur[0])
                path.reverse()
                return path
            l, c, r = node
            moves = []
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (l, c + dc, r + dr)
                if self.node_ok(nb, net) and self.edge_ok(node, nb, net):
                    moves.append((nb, _STEP[(l, dr == 0)], 0))
            if not vflag:
                for dl in (1, -1):
                    nl = l + dl
                    if nl < 0 or nl > 2:
                        continue
                    lo = min(l, nl)
                    if lo == M1 and (c, r) in self.noviablock:
                        continue
                    if lo == M1 and (c, r) in self.via2:
                        continue
                    if lo == M2 and (c, r) in self.via1:
                        continue
                    nb = (nl, c, r)
                    if self.node_ok(nb, net):
                        moves.append((nb, VIA_COST, 1))
            for nb, cost, nf in moves:
                ns = (nb, nf)
                ng = g + cost
                if ng < dist.get(ns, 1e18) - 1e-12:
                    dist[ns] = ng
                    prev[ns] = st
                    heapq.heappush(heap, (ng + h(nb), next(counter), ng, ns))
        return None

    def _commit(self, net, path, nodes, edges):
        for a, b in itertools.pairwise(path):
            if a[0] != b[0]:
                (self.via1 if min(a[0], b[0]) == M1 else self.via2).add((a[1], a[2]))
            edges.add((a, b) if a <= b else (b, a))
        for n in path:
            nodes.add(n)
            self.owner[n] = net

    def route_net(self, net) -> bool:
        terms = [set(t) for t in self.terms[net]]
        nodes: set = set()
        edges: set = set()
        tree = set(terms[0])
        for n in tree:
            self.owner[n] = net
        nodes |= tree
        remaining = terms[1:]
        while remaining:
            targets = set().union(*remaining)
            path = self._search(net, tree, targets)
            if path is None:
                return False
            self._commit(net, path, nodes, edges)
            tree |= set(path)
            hit = path[-1]
            keep = []
            for t in remaining:
                if hit in t:
                    for n in t:
                        self.owner[n] = net
                    tree |= t
                    nodes |= t
                else:
                    keep.append(t)
            remaining = keep
        self.routes[net] = (nodes, edges)
        return True

    def reset_routes(self) -> None:
        self.owner.clear()
        self.routes.clear()
        self.via1.clear()
        self.via2.clear()
        for net, ts in self.terms.items():
            if len(ts) >= 1:
                for t in ts:
                    for n in t:
                        self.owner[n] = net

    def route_all(self, nets: list[str], tries: int = 40) -> list[str]:
        """Route ``nets``; on failure re-order (failed first) and retry."""
        order = list(nets)
        failed: list[str] = []
        for _ in range(tries):
            self.reset_routes()
            failed = []
            for net in order:
                if not self.route_net(net):
                    failed.append(net)
                    # a failed net leaves partial ownership: drop it
                    for n, o in list(self.owner.items()):
                        if o == net and not any(n in t for t in self.terms[net]):
                            del self.owner[n]
            if not failed:
                return []
            order = failed + [n for n in order if n not in failed]
        return failed


# ---------------------------------------------------------------------------
# Layout context
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, row_lo: int, row_hi: int, ncols: int):
        self.shapes: dict[tuple, list] = defaultdict(list)
        self.labels: list = []
        self.ncols = ncols
        self.router = Router(row_lo, row_hi, ncols)
        self.rails: dict[int, str] = {}
        self.rows: list = []  # (kind, side, ymin, ymax, rail_y) COMP extents of device rows

    def box(self, layer, x0, y0, x1, y1) -> None:
        self.shapes[layer].append((round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)))

    def metal1(self, rect, net, spacing=M1_SPACE) -> None:
        self.box(L_METAL1, *rect)
        self.router.add_obstacle(M1, rect, net, spacing)

    def term(self, net: str, nodes) -> None:
        self.router.terms[net].append(frozenset(nodes))


# ---------------------------------------------------------------------------
# Strips
# ---------------------------------------------------------------------------
@dataclass
class Strip:
    name: str
    a_kind: str  # kind of the bottom row: 'N' (VSS below) or 'P' (VDD below)
    chains: dict  # kind -> list[(start_col, [device names])]
    chan: int = 3  # free rows between the rows' gate pads
    bottom_rail: bool = True
    strap: bool = False  # join consecutive same-net gates of a chain with poly


@dataclass
class Placed:
    dev: Dev
    cl: int
    cg: int
    cr: int
    nl: str
    nr: str


def n_contacts(w: float) -> int:
    return int(math.floor((w - PAD + 1e-9) / G)) + 1


def relpad(w: float) -> int:
    """Rows from a row's rail-side contact row to its gate-pad row.

    The pad centre must clear the COMP edge by POLY_PAD_COMP (PL.5a_LV) plus
    half a pad; with the first contact 0.19 inside the COMP edge that is
    ``(w + POLY_PAD_COMP)`` above the contact row.
    """
    return int(math.ceil((w + POLY_PAD_COMP) / G - 1e-9))


def place_chain(devs: list[Dev], c0: int, hint: str | None = None) -> list[Placed]:
    out: list[Placed] = []
    prev_right = None
    for i, dev in enumerate(devs):
        ends = (dev.d, dev.s)
        if i == 0:
            if hint is not None:
                assert hint in ends, f"{dev.name}: hint {hint!r} not in {ends}"
                left = hint
                right = ends[1] if ends[0] == hint else ends[0]
            elif len(devs) > 1:
                nxt = (devs[1].d, devs[1].s)
                if ends[1] in nxt:
                    left, right = ends[0], ends[1]
                elif ends[0] in nxt:
                    left, right = ends[1], ends[0]
                else:
                    raise ValueError(f"{dev.name}: no net shared with {devs[1].name}")
            else:
                left, right = ends
        else:
            if prev_right not in ends:
                raise ValueError(f"{dev.name}: {prev_right!r} is not one of {ends}")
            left = prev_right
            right = ends[1] if ends[0] == left else ends[0]
        out.append(Placed(dev, c0 + 2 * i, c0 + 2 * i + 1, c0 + 2 * i + 2, left, right))
        prev_right = right
    return out


def layout_strip(ctx: Ctx, strip: Strip, devmap: dict[str, Dev], jrb: int, jfloor: int = 1):
    """Draw one strip whose bottom rail row is ``jrb``; return its top rail row."""
    kind_a = strip.a_kind
    kind_b = "P" if kind_a == "N" else "N"
    def _chain(c0, names):
        hint = None
        if "@" in names[0]:
            names = list(names)
            names[0], hint = names[0].split("@")
        return place_chain([devmap[n] for n in names], c0, hint)

    placed = {k: [_chain(c0, names) for (c0, names) in strip.chains.get(k, [])] for k in ("N", "P")}
    # chain overlap check
    for k, chs in placed.items():
        used: set[int] = set()
        for ch in chs:
            cols = set(range(ch[0].cl, ch[-1].cr + 1))
            assert not (cols & used), f"{strip.name}: overlapping {k} chains"
            used |= cols
            assert ch[-1].cr < ctx.ncols, f"{strip.name}: chain runs past column {ctx.ncols - 1}"
    a_devs = [p for ch in placed[kind_a] for p in ch]
    b_devs = [p for ch in placed[kind_b] for p in ch]

    ja0 = jrb + 2 if strip.bottom_rail else jfloor + 1
    if strip.bottom_rail:
        ctx.rails[jrb] = SUPPLY[kind_a]
    max_a_pad = max([ja0 + relpad(p.dev.w) for p in a_devs], default=jfloor)
    max_rel_b = max([relpad(p.dev.w) for p in b_devs], default=0)
    jb0 = max_a_pad + 1 + strip.chan + max_rel_b
    if a_devs and b_devs:
        wa = max(p.dev.w for p in a_devs)
        wb = max(p.dev.w for p in b_devs)
        jb0 = max(jb0, ja0 + int(math.ceil((0.9 + wa + wb - 0.38) / G - 1e-9)))
    elif b_devs and strip.bottom_rail:
        wb = max(p.dev.w for p in b_devs)
        jb0 = max(jb0, jrb + int(math.ceil((0.88 + wb) / G - 1e-9)))
    jrt = jb0 + 2
    ctx.rails[jrt] = SUPPLY[kind_b]

    gates = []  # (side, Placed, chain index, comp ybot, ytop, pad row)
    for side, kind, j0, chains in (("A", kind_a, ja0, placed[kind_a]), ("B", kind_b, jb0, placed[kind_b])):
        sup = SUPPLY[kind]
        rail_row = jrb if side == "A" else jrt
        for ci, ch in enumerate(chains):
            # contact columns
            cols: dict[int, dict] = {}
            for p in ch:
                for col, net in ((p.cl, p.nl), (p.cr, p.nr)):
                    e = cols.setdefault(col, {"net": net, "n": 0})
                    assert e["net"] == net
                    e["n"] = max(e["n"], n_contacts(p.dev.w))
            for p in ch:
                w = p.dev.w
                assert min(abs(p.dev.l - L_GATE), abs(p.dev.l - L_LONG)) < 1e-9, \
                    f"{p.dev.name}: L != {L_GATE} / {L_LONG}"
                if side == "A":
                    yb = Y(j0) - 0.19
                    yt = yb + w
                else:
                    yt = Y(j0) + 0.19
                    yb = yt - w
                ctx.box(L_COMP, X(p.cl) - COMP_HALF, yb, X(p.cr) + COMP_HALF, yt)
                pr = relpad(w)
                pad = j0 + pr if side == "A" else j0 - pr
                gates.append((side, p, ci, round(yb, 3), round(yt, 3), pad))
            for col, e in cols.items():
                net, nrows = e["net"], e["n"]
                rows = [j0 + i for i in range(nrows)] if side == "A" else [j0 - i for i in range(nrows)]
                for r in rows:
                    ctx.box(L_CONTACT, X(col) - HCO, Y(r) - HCO, X(col) + HCO, Y(r) + HCO)
                    ctx.router.noviablock.add((col, r))
                lo, hi = min(rows), max(rows)
                if net in ("VDD", "VSS"):
                    assert net == sup, f"{net} contact in a {kind} row (strip {strip.name})"
                    if side == "A":
                        lo = rail_row
                    else:
                        hi = rail_row
                rect = (X(col) - HPAD, Y(lo) - HPAD, X(col) + HPAD, Y(hi) + HPAD)
                ctx.metal1(rect, net, M1_SPACE)
                if net not in ("VDD", "VSS"):
                    ctx.term(net, [(M1, col, r) for r in range(lo, hi + 1)])
    for side, kind in (("A", kind_a), ("B", kind_b)):
        ext = [(g[3], g[4]) for g in gates if g[0] == side]
        if ext:
            rail_y = Y(jrb) if side == "A" else Y(jrt)
            ctx.rows.append((kind, side, min(e[0] for e in ext), max(e[1] for e in ext), rail_y))

    # ---- gates -----------------------------------------------------
    by_col: dict[int, dict] = defaultdict(dict)
    for (side, p, ci, yb, yt, pad) in gates:
        by_col[p.cg][side] = (p, ci, yb, yt, pad)

    def gate_pad(xg, jg, net):
        ctx.box(L_POLY2, xg - HPAD, Y(jg) - HPAD, xg + HPAD, Y(jg) + HPAD)
        ctx.box(L_CONTACT, xg - HCO, Y(jg) - HCO, xg + HCO, Y(jg) + HCO)
        ctx.metal1((xg - HPAD, Y(jg) - HPAD, xg + HPAD, Y(jg) + HPAD), net)
        c = int(round((xg - X0) / G))
        ctx.router.noviablock.add((c, jg))
        ctx.term(net, [(M1, c, jg)])

    if strip.strap:
        for kind in ("N", "P"):
            for ch in placed[kind]:
                i = 0
                while i < len(ch):
                    j = i
                    while j + 1 < len(ch) and ch[j + 1].dev.g == ch[i].dev.g:
                        j += 1
                    grp = ch[i:j + 1]
                    side = "A" if kind == kind_a else "B"
                    infos = [by_col[p.cg][side] for p in grp]
                    pad = max(i_[4] for i_ in infos) if side == "A" else min(i_[4] for i_ in infos)
                    xs = [X(p.cg) for p in grp]
                    for (p, (_, _, yb, yt, _)) in zip(grp, infos):
                        hg = hgate(p.dev)
                        if side == "A":
                            ctx.box(L_POLY2, X(p.cg) - hg, yb - POLY_EXT, X(p.cg) + hg, Y(pad) + HGATE)
                        else:
                            ctx.box(L_POLY2, X(p.cg) - hg, Y(pad) - HGATE, X(p.cg) + hg, yt + POLY_EXT)
                    ctx.box(L_POLY2, xs[0] - HGATE, Y(pad) - HGATE, xs[-1] + HGATE, Y(pad) + HGATE)
                    gate_pad(xs[len(xs) // 2], pad, grp[0].dev.g)
                    for p in grp:
                        by_col[p.cg].pop(side, None)
                    i = j + 1
    pads_a = [g[5] for g in gates if g[0] == "A"]
    pads_b = [g[5] for g in gates if g[0] == "B"]
    for col, sides in sorted(by_col.items()):
        a = sides.get("A")
        b = sides.get("B")
        if a and b and a[0].dev.g == b[0].dev.g:
            pa, pb = a[4], b[4]
            jc = (max(pads_a) + min(pads_b)) // 2
            assert pa <= jc <= pb, f"{strip.name}: no common-gate pad row for col {col}"
            xg = X(col)
            hg = hgate(a[0].dev)
            ctx.box(L_POLY2, xg - hg, a[2] - POLY_EXT, xg + hg, b[3] + POLY_EXT)
            gate_pad(xg, jc, a[0].dev.g)
            continue
        if a:
            p, _, yb, yt, pad = a
            xg = X(col)
            hg = hgate(p.dev)
            ctx.box(L_POLY2, xg - hg, yb - POLY_EXT, xg + hg, Y(pad) + HGATE)
            gate_pad(xg, pad, p.dev.g)
        if b:
            p, _, yb, yt, pad = b
            xg = X(col)
            hg = hgate(p.dev)
            ctx.box(L_POLY2, xg - hg, Y(pad) - HGATE, xg + hg, yt + POLY_EXT)
            gate_pad(xg, pad, p.dev.g)
    return jrt, {"ja0": ja0, "jb0": jb0, "jrb": jrb, "jrt": jrt}


# ---------------------------------------------------------------------------
# Ports: bottom pins
# ---------------------------------------------------------------------------
def add_bottom_pin(ctx: Ctx, net: str, col: int, jend: int = 2) -> None:
    x = X(col)
    rect = (x - HWIRE, 0.0, x + HWIRE, Y(jend) + HWIRE)
    ctx.box(L_METAL2, *rect)
    ctx.router.add_obstacle(M2, rect, net, M1_WIDE_SPACE)
    ctx.term(net, [(M2, col, jend)])
    ctx.labels.append((L_METAL2_LBL, net, x, 0.5 * Y(jend)))


# ---------------------------------------------------------------------------
# Route + emit
# ---------------------------------------------------------------------------
def route(ctx: Ctx, label: str) -> None:
    r = ctx.router
    nets = [n for n, ts in r.terms.items() if len(ts) >= 2 and n not in ("VDD", "VSS")]

    def bbox_key(n):
        pts = [(c, rr) for t in r.terms[n] for (_, c, rr) in t]
        cs = [p[0] for p in pts]
        rs = [p[1] for p in pts]
        has_bus = any(l == M3 for t in r.terms[n] for (l, _, _) in t)
        return (1 if has_bus else 0, (max(cs) - min(cs)) + (max(rs) - min(rs)), n)

    nets.sort(key=bbox_key)
    failed = r.route_all(nets)
    if failed:
        raise RuntimeError(f"{label}: unrouted nets: {failed}")


def emit_routes(ctx: Ctx) -> None:
    r = ctx.router
    for net in sorted(r.routes):
        nodes, edges = r.routes[net]
        via1_nodes = set()
        via2_nodes = set()
        for a, b in edges:
            if a[0] != b[0]:
                (via1_nodes if min(a[0], b[0]) == M1 else via2_nodes).add((a[1], a[2]))
        for (l, c, rr) in nodes:
            x, y = X(c), Y(rr)
            if l == M1:
                half = HPAD if (c, rr) in via1_nodes else HWIRE
            else:
                half = HWIRE
            ctx.box(METAL[l], x - half, y - half, x + half, y + half)
        for a, b in edges:
            if a[0] != b[0]:
                continue
            (l, c, rr), (_, c2, r2) = a, b
            x0, x1 = sorted((X(c), X(c2)))
            y0, y1 = sorted((Y(rr), Y(r2)))
            ctx.box(METAL[l], x0 - HWIRE, y0 - HWIRE, x1 + HWIRE, y1 + HWIRE)
        for (c, rr) in via1_nodes:
            ctx.box(L_VIA1, X(c) - HVIA, Y(rr) - HVIA, X(c) + HVIA, Y(rr) + HVIA)
        for (c, rr) in via2_nodes:
            ctx.box(L_VIA2, X(c) - HVIA, Y(rr) - HVIA, X(c) + HVIA, Y(rr) + HVIA)


def to_cell(layout: kdb.Layout, name: str, ctx: Ctx) -> kdb.Cell:
    cell = layout.create_cell(name)
    for lp in sorted(ctx.shapes):
        reg = kdb.Region()
        for (x0, y0, x1, y1) in ctx.shapes[lp]:
            reg.insert(kdb.Box(nm(x0), nm(y0), nm(x1), nm(y1)))
        reg.merge()
        cell.shapes(register_layer(layout, lp, _LAYER_NAMES)).insert(reg)
    for lp, text, x, y in ctx.labels:
        cell.shapes(register_layer(layout, lp, _LAYER_NAMES)).insert(kdb.Text(text, kdb.Trans(nm(x), nm(y))))
    return cell


# ---------------------------------------------------------------------------
# Shared chain table: the ``dff`` of the io slices and the control flops
# ---------------------------------------------------------------------------
def dff_chains(p: str) -> dict:
    def row(m):
        def n(inst, dev):
            return f"{p}.{inst}.{dev}"

        return [
            (0, [n("Xckb", m), n("Xckp", m)]),
            (5, [n("Xtm", m), n("Xtmf", m)]),
            (11, [n("Xmf", m), n("Xnm", m), n("Xts", m)]),
            (19, [n("Xns", m), n("Xsf", m), n("Xtsf", m)]),
        ]

    return {"N": row("MN"), "P": row("MP")}


# ---------------------------------------------------------------------------
# Per-strip rails, implants, wells (strips whose rails do not span the whole
# cell -- the row decoder strip and the control blocks)
# ---------------------------------------------------------------------------
EDGE = 0.4  # rail / implant overhang past the outermost column
WELL_EDGE = 0.55


class Plan:
    """Everything drawn per strip that is not a device: rails, implants, wells."""

    def __init__(self):
        self.rails: list = []  # (row, net, c_from, c_to)
        self.rows: list = []  # (kind, side, ymin, ymax, rail_y, xl, xr)
        self.vss_rows: dict[int, list[int]] = {}  # strap column -> rail rows
        self.vdd_rows: dict[int, list[int]] = {}


def layout_cells(ctx, plan: Plan, devmap, strip, jrb, c_vss, c_vdd, c_end):
    """Run ``layout_strip`` for one strip and record the per-strip rails /
    implant extents (its own ``ctx.rails`` / ``ctx.rows`` are keyed by row
    alone, so they are taken out after each strip)."""
    ctx.rails, ctx.rows = {}, []
    jrt, info = layout_strip(ctx, strip, devmap, jrb)
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
        ctx.metal1((x0, y - 0.5 * RAIL_H, x1, y + 0.5 * RAIL_H), net, M1_WIDE_SPACE)
        ctx.box(L_COMP, X(c0) - COMP_HALF, y - 0.19, X(c1) + COMP_HALF, y + 0.19)
        for c in range(c0 + 1, c1 + 1, 2):
            ctx.box(L_CONTACT, X(c) - HCO, y - HCO, X(c) + HCO, y + HCO)
            ctx.router.noviablock.add((c, j))
        ctx.router.noviablock.add((c0, j))
        if net == "VSS":
            ctx.box(L_PPLUS, x0, y - 0.19 - IMP_ENC_COMP, x1, y + 0.19 + IMP_ENC_COMP)
        else:
            ctx.box(L_NPLUS, x0, y - 0.19 - IMP_ENC_COMP, x1, y + 0.19 + IMP_ENC_COMP)
            ctx.box(L_NWELL, x0 - 0.05, y - 0.19 - NW_ENC_NCOMP, x1 + 0.05,
                    y + 0.19 + NW_ENC_NCOMP)
    for (kind, side, ymin, ymax, rail_y, xl, xr) in plan.rows:
        lp = L_NPLUS if kind == "N" else L_PPLUS
        ctx.box(lp, xl, ymin - IMP_ENC_GATE, xr, ymax + IMP_ENC_GATE)
        if kind == "P":
            y0 = ymin - NW_ENC_PCOMP
            y1 = ymax + NW_ENC_PCOMP
            if side == "A":
                y0 = min(y0, rail_y - 0.19 - NW_ENC_NCOMP)
            else:
                y1 = max(y1, rail_y + 0.19 + NW_ENC_NCOMP)
            ctx.box(L_NWELL, xl, y0, xr, y1)


def add_strap(ctx, net: str, c: int, rows: list[int], j_lo: int, j_hi: int) -> None:
    """Vertical Metal2 strap on grid column ``c`` from row ``j_lo`` to ``j_hi``
    with a Via1 on every rail row in ``rows``."""
    x = X(c)
    rect = (x - HWIRE, Y(j_lo) - HWIRE, x + HWIRE, Y(j_hi) + HWIRE)
    ctx.box(L_METAL2, *rect)
    ctx.router.add_obstacle(M2, rect, net, M1_WIDE_SPACE)
    for j in rows:
        ctx.box(L_VIA1, x - HVIA, Y(j) - HVIA, x + HVIA, Y(j) + HVIA)
        ctx.router.noviablock.add((c, j))
    ctx.labels.append((L_METAL2_LBL, net, x, Y(j_lo) + 0.5 * RAIL_H))
