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
import heapq
import importlib.util
import itertools
import math
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

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


bitcell = _load("_sram_bitcell_generate", "layout/bitcell/generate.py")
NETLIST_DIR = os.path.join(ROOT, "design", "netlist")

# ---------------------------------------------------------------------------
# Layers (GDS layer/datatype) -- the bitcell's, plus Via2/Metal3 (as the array).
# ---------------------------------------------------------------------------
L_NWELL, L_COMP, L_POLY2 = bitcell.L_NWELL, bitcell.L_COMP, bitcell.L_POLY2
L_PPLUS, L_NPLUS, L_CONTACT = bitcell.L_PPLUS, bitcell.L_NPLUS, bitcell.L_CONTACT
L_METAL1, L_VIA1, L_METAL2 = bitcell.L_METAL1, bitcell.L_VIA1, bitcell.L_METAL2
L_METAL1_LBL, L_METAL2_LBL = bitcell.L_METAL1_LBL, bitcell.L_METAL2_LBL
L_VIA2 = (38, 0)
L_METAL3 = (42, 0)
L_METAL3_LBL = (42, 10)
_LAYER_NAMES = dict(bitcell._LAYER_NAMES)
_LAYER_NAMES.update({L_VIA2: "Via2", L_METAL3: "Metal3", L_METAL3_LBL: "Metal3_Label"})
METAL = (L_METAL1, L_METAL2, L_METAL3)

# ---------------------------------------------------------------------------
# Geometry constants (um). Rule ids are gf180mcu DRM ids; "curated" = klt's
# bundled deck, "native" = the PDK's own deck under libs.tech/klayout.
# ---------------------------------------------------------------------------
SLICE_W = round(4 * bitcell.W_CELL, 3)  # 17.84: one I/O = four bitcell columns
G = 0.65  # routing grid pitch (see module docstring, "Grid")
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
NW_ENC_PCOMP = 0.45  # DF.4c_LV (0.43) + 0.02
NW_ENC_NCOMP = 0.20  # DF.4d_LV (0.12) + 0.08
NW_TO_NCOMP = 0.43  # DF.16_LV
RAIL_H = 0.40  # Metal1 supply rail (>= 0.34, contact enclosure 0.09)
M1_SPACE = 0.23  # M1.2a
M1_WIDE_SPACE = 0.30  # M1.2b / M2.2b / M3.2b: shape with an edge >= 10 um
STUB_W = bitcell.M1_STRIPE_W  # 0.30: bit-line stub == array stripe width
SUPPLY = {"N": "VSS", "P": "VDD"}


def X(c: float) -> float:
    return round(X0 + G * c, 3)


def Y(j: float) -> float:
    return round(G * j, 3)


def nm(v: float) -> int:
    return int(round(v * 1000))


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
    def __init__(self, row_lo: int, row_hi: int):
        self.rlo, self.rhi = row_lo, row_hi
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
        for c in range(max(0, c_lo), min(NCOLS - 1, c_hi) + 1):
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
        if c < 0 or c >= NCOLS or r < self.rlo or r > self.rhi:
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
        """A* bound: ``h(node)`` = minimum Manhattan distance to any target."""
        tl = list(targets)

        def h(node):
            _, c, r = node
            return min(abs(c - tc) + abs(r - tr) for (_, tc, tr) in tl)

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
    def __init__(self, row_lo: int, row_hi: int):
        self.shapes: dict[tuple, list] = defaultdict(list)
        self.labels: list = []
        self.router = Router(row_lo, row_hi)
        self.rails: dict[int, str] = {}
        self.rows: list = []  # (kind, ymin, ymax) COMP extents of device rows
        self.wells: list = []  # extra n-well boxes
        self.bus: dict[str, int] = {}

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
            assert ch[-1].cr < NCOLS, f"{strip.name}: chain runs past column {NCOLS - 1}"
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
                    bar_net = net
                else:
                    bar_net = net
                rect = (X(col) - HPAD, Y(lo) - HPAD, X(col) + HPAD, Y(hi) + HPAD)
                ctx.metal1(rect, bar_net, M1_SPACE)
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
# Rails, ties, wells, implants
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
# Ports: bus tracks, bottom pins, bit-line stubs
# ---------------------------------------------------------------------------
def add_bus(ctx: Ctx, net: str, row: int) -> None:
    y = Y(row)
    rect = (0.0, y - HWIRE, SLICE_W, y + HWIRE)
    ctx.box(L_METAL3, *rect)
    ctx.router.add_obstacle(M3, rect, net, M1_WIDE_SPACE)
    ctx.term(net, [(M3, c, row) for c in range(NCOLS)])
    ctx.labels.append((L_METAL3_LBL, net, 0.5 * SLICE_W, y))
    ctx.bus[net] = row


def add_bottom_pin(ctx: Ctx, net: str, col: int, jend: int = 2) -> None:
    x = X(col)
    rect = (x - HWIRE, 0.0, x + HWIRE, Y(jend) + HWIRE)
    ctx.box(L_METAL2, *rect)
    ctx.router.add_obstacle(M2, rect, net, M1_WIDE_SPACE)
    ctx.term(net, [(M2, col, jend)])
    ctx.labels.append((L_METAL2_LBL, net, x, 0.5 * Y(jend)))


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


def _kdb_layer(layout: kdb.Layout, lp) -> int:
    li = layout.layer(*lp)
    layout.set_info(li, kdb.LayerInfo(lp[0], lp[1], _LAYER_NAMES[lp]))
    return li


def to_cell(layout: kdb.Layout, name: str, ctx: Ctx) -> kdb.Cell:
    cell = layout.create_cell(name)
    for lp in sorted(ctx.shapes):
        reg = kdb.Region()
        for (x0, y0, x1, y1) in ctx.shapes[lp]:
            reg.insert(kdb.Box(nm(x0), nm(y0), nm(x1), nm(y1)))
        reg.merge()
        cell.shapes(_kdb_layer(layout, lp)).insert(reg)
    for lp, text, x, y in ctx.labels:
        cell.shapes(_kdb_layer(layout, lp)).insert(kdb.Text(text, kdb.Trans(nm(x), nm(y))))
    return cell


# ---------------------------------------------------------------------------
# The two cells
# ---------------------------------------------------------------------------
def _bl_x(s: int) -> float:
    return round(bitcell.X_BL_C + s * bitcell.W_CELL, 3)


def _blb_x(s: int) -> float:
    return round(bitcell.X_BLB_C + s * bitcell.W_CELL, 3)


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
    ctx = Ctx(row_lo=1, row_hi=10_000)  # rhi is lowered once the cell height is known
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
    ctx = Ctx(row_lo=1, row_hi=10_000)  # rhi is lowered once the cell height is known
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


def save_options() -> kdb.SaveLayoutOptions:
    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


def make_band(layout: kdb.Layout, slice_cell: kdb.Cell, name: str, n: int = 32) -> kdb.Cell:
    top = layout.create_cell(name)
    top.insert(
        kdb.CellInstArray(
            slice_cell.cell_index(), kdb.Trans(0, 0), kdb.Vector(nm(SLICE_W), 0), kdb.Vector(0, 0), n, 1
        )
    )
    return top


def check_bitline_seams(layout: kdb.Layout, top: kdb.Cell, x_off: int, arr_h: int, io_h: int) -> int:
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
        spec = importlib.util.spec_from_file_location(
            "_sram_array_generate", os.path.join(ROOT, "layout/sram_256x32/generate.py"))
        arr_gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(arr_gen)
        x_off = nm(arr_gen.WL_PAD_BAND)
        arr_h = array.bbox().top
        top = layout.create_cell("column_abut_check")
        top.insert(kdb.CellInstArray(array.cell_index(), kdb.Trans(0, 0)))
        top.insert(kdb.CellInstArray(io_band.cell_index(), kdb.Trans(x_off, -nm(built["io_slice"][1]))))
        top.insert(kdb.CellInstArray(pre_band.cell_index(), kdb.Trans(x_off, arr_h)))
        n = check_bitline_seams(layout, top, x_off, arr_h, nm(built["io_slice"][1]))
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
