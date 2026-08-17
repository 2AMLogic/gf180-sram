#!/usr/bin/env python3
"""Generate ``sram_bitcell_6t.gds`` — the device-level 6T SRAM bitcell layout.

This is the real, transistor-level layout of ``design/bitcell_6t.sch`` (issue
#21), drawn on gf180mcu drawing layers. It replaces the explicitly-labeled
placeholder box that PR #36 committed here while ``design/`` was still empty.

## Where the sizing comes from

Every device dimension below is taken from the committed, xschem-derived
netlist ``design/netlist/bitcell_6t.spice`` — not invented here:

===========  ==================  ========  ========
Netlist ref  Role                W (um)    L (um)
===========  ==================  ========  ========
``XMPL``     pull-up  (pfet)     0.22      0.28
``XMPR``     pull-up  (pfet)     0.22      0.28
``XMNL``     pull-down (nfet)    0.36      0.28
``XMNR``     pull-down (nfet)    0.36      0.28
``XMAL``     access   (nfet)     0.24      0.28
``XMAR``     access   (nfet)     0.24      0.28
===========  ==================  ========  ========

`W` is drawn as the poly/COMP overlap length of each device's channel, so
``klt extract`` reads back exactly these numbers (see ``layout/README.md``,
"Extraction / connectivity check").

## Topology

One horizontal NMOS COMP strip carries all four NMOS devices with shared
source/drain diffusions, in schematic order::

    BL | MAL | Q | MNL | VSS | MNR | QB | MAR | BLB

A second COMP strip inside ``Nwell`` carries the two pull-ups, sharing the
middle ``VDD`` diffusion::

    Q | MPL | VDD | MPR | QB

The two inverter gates (`MNL`+`MPL` = net ``QB``; `MNR`+`MPR` = net ``Q``)
are single vertical Poly2 stripes running from the NMOS row up through the
PMOS row, so each inverter's n/p gates are one drawn shape. The wordline is
a horizontal Poly2 stripe spanning the full cell width, merged with both
access-device gates — so tiling the cell left-to-right forms one continuous
wordline per row without any array-level routing.

Cross-coupling uses two horizontal Poly2 jogs at *different heights* in the
band between the NMOS and PMOS rows: the ``Q`` gate stripe jogs left to a
contacted landing pad, the ``QB`` gate stripe jogs right to a second landing
pad above it. Each landing pad is then tied to the opposite storage node's
diffusions by one L-shaped Metal1 strap. The two straps never cross (they
occupy disjoint x/y bands), which is what makes a single-Metal1 cross-couple
possible.

## Boundary contract (what makes the cell tile by abutment)

* ``BL`` / ``BLB``  — Metal1 stripes spanning the full cell height, so a
  vertical stack of instances forms one bitline pair per column.
* ``VDD`` / ``VSS`` — Metal2 stripes spanning the full cell height (the rails
  run vertically so they never cross the horizontal wordline).
* ``WL``           — Poly2 stripe spanning the full cell width.
* ``Nwell``        — spans the full cell width, so wells merge along a row;
  the cell is tall enough that vertically adjacent wells stay > NW.2a apart.
* Everything else is inset from the cell boundary by at least the relevant
  minimum spacing, so abutment cannot create a violation.

Well/substrate ties are drawn inside the cell (an ``Nplus`` tie strip inside
the well for ``VDD``, a ``Pplus`` tie strip on substrate for ``VSS``), rather
than relying on periphery tap rows.

## What is NOT claimed here

* The cell is **not** area-optimized. It is drawn to conservative, generic
  rule margins (see the constants below), not to gf180mcu's ``SramCore``
  (108/5) marker-scoped SRAM rules, which is how a foundry-grade bitcell
  reaches its published density. ``layout/README.md`` records the measured
  area penalty against the foundry reference.
* DRC evidence is limited to the deck ``klt drc --deck gf180mcu`` actually
  implements (a curated subset of the DRM). See ``layout/README.md``.

## Determinism

Run from the repo root::

    uv run --with klayout python3 layout/bitcell/generate.py

GDSII header timestamps are disabled (see :func:`save_options`), so re-running
produces a byte-identical file and ``git diff`` stays empty.
"""

from __future__ import annotations

import os

import klayout.db as kdb

# ---------------------------------------------------------------------------
# gf180mcu drawing layers (GDS layer/datatype), read from the PDK's own
# libs.tech/klayout/tech/gf180mcu.lyp. These are the same pairs klt's curated
# gf180mcu DRC deck and extraction deck key off.
# ---------------------------------------------------------------------------
L_NWELL = (21, 0)
L_COMP = (22, 0)
L_POLY2 = (30, 0)
L_POLY2_LBL = (30, 10)
L_PPLUS = (31, 0)
L_NPLUS = (32, 0)
L_CONTACT = (33, 0)
L_METAL1 = (34, 0)
L_METAL1_LBL = (34, 10)
L_VIA1 = (35, 0)
L_METAL2 = (36, 0)
L_METAL2_LBL = (36, 10)

_LAYER_NAMES = {
    L_NWELL: "Nwell",
    L_COMP: "COMP",
    L_POLY2: "Poly2",
    L_POLY2_LBL: "Poly2_Label",
    L_PPLUS: "Pplus",
    L_NPLUS: "Nplus",
    L_CONTACT: "Contact",
    L_METAL1: "Metal1",
    L_METAL1_LBL: "Metal1_Label",
    L_VIA1: "Via1",
    L_METAL2: "Metal2",
    L_METAL2_LBL: "Metal2_Label",
}

# ---------------------------------------------------------------------------
# Design-rule constants (um).
#
# Each value cites the gf180mcu DRM rule it derives from. Where a margin is
# added over the DRM minimum it is stated explicitly: this cell is drawn with
# deliberate slack rather than at the rule limit, because (a) klt's curated
# gf180mcu deck implements a *subset* of the DRM, so rules it does not check
# must be satisfied by construction, and (b) a first-cut bitcell that fails
# sign-off DRC later is worth less than one that is a little larger.
# ---------------------------------------------------------------------------
CO_SIZE = 0.22  # CO.1: contacts are a fixed 0.22 x 0.22 square
CO_ENC_COMP = 0.08  # CO.4 (0.07) + 0.01
CO_ENC_POLY = 0.08  # CO.3 (0.07) + 0.01
CO_ENC_M1 = 0.03  # CO.6 (0.005), widened so the M1 pad still meets M1.1
CO_TO_POLY = 0.18  # gate-to-contact clearance (CO.5 class; not in klt's subset)
COMP_SPACE = 0.30  # DF.3a (0.28) + 0.02
POLY_SPACE = 0.26  # PL.3a (0.24) + 0.02
POLY_WIDTH = 0.26  # PL.1 min 0.18; wordline stripe drawn wider for R
POLY_EXT_COMP = 0.24  # PL.4 (0.22) + 0.02
POLY_TO_COMP = 0.12  # PL.5 class field clearance (0.10) + 0.02
M1_SPACE = 0.26  # M1.2a (0.23) + 0.03
M1_STRIPE_W = 0.30  # >= M1.1 (0.23); bitline stripes
M1_BAR_W = CO_SIZE + 2 * CO_ENC_M1  # 0.28, >= M1.1
V1_SIZE = 0.26  # V1.1
V1_ENC_M1 = 0.06  # V1.2a is 0.00 in the curated deck; real decks want margin
V1_ENC_M2 = 0.06  # V1.3a (0.01) + 0.05
M2_STRIPE_W = V1_SIZE + 2 * V1_ENC_M2  # 0.38, >= M2.1 (0.28)
NW_ENC_COMP = 0.20  # NW.5 (0.12) + 0.08
NW_SPACE = 0.60  # NW.2a
NW_TO_COMP = 0.43  # NW.3 class: COMP outside the well to Nwell
IMP_ENC_COMP = 0.16  # NP.5a / PP.5a class: implant overlap of COMP
IMP_SPACE = 0.25  # Nplus-to-Pplus separation (not in klt's curated subset)

# ---------------------------------------------------------------------------
# Device sizing — transcribed from design/netlist/bitcell_6t.spice.
# ---------------------------------------------------------------------------
L_GATE = 0.28  # all six devices
W_PU = 0.22  # XMPL / XMPR (pfet_03v3)
W_PD = 0.36  # XMNL / XMNR (nfet_03v3)
W_PG = 0.24  # XMAL / XMAR (nfet_03v3)

TOP_CELL = "sram_bitcell_6t"

# ---------------------------------------------------------------------------
# X plan: one accumulation pass across the NMOS row. Every x coordinate in the
# cell derives from this, including the PMOS row (its pads and gates sit on the
# same x columns as the NMOS row's) and the metal stripes.
# ---------------------------------------------------------------------------
MARGIN_X = IMP_ENC_COMP  # implant overlap sets the left/right inset
PAD_W = CO_SIZE + 2 * CO_ENC_COMP  # 0.38: a diffusion pad holding one contact
NECK_MARGIN = CO_TO_POLY - CO_ENC_COMP  # 0.10: pad edge to gate edge
# The center (VSS/VDD) diffusion pad is widened so the two cross-couple poly
# landing pads fit between the inverter gate stripes with POLY_SPACE on both
# sides.
CENTER_PAD_W = PAD_W + 2 * POLY_SPACE - 2 * NECK_MARGIN  # 0.70


def _x_plan() -> dict[str, tuple[float, float]]:
    cursor = MARGIN_X
    plan: dict[str, tuple[float, float]] = {}

    def place(name: str, width: float) -> None:
        nonlocal cursor
        plan[name] = (cursor, cursor + width)
        cursor += width

    place("pad_bl", PAD_W)
    cursor += NECK_MARGIN
    place("gate_wl_l", L_GATE)
    cursor += NECK_MARGIN
    place("pad_q", PAD_W)
    cursor += NECK_MARGIN
    place("gate_qb", L_GATE)
    cursor += NECK_MARGIN
    place("pad_vss", CENTER_PAD_W)
    cursor += NECK_MARGIN
    place("gate_q", L_GATE)
    cursor += NECK_MARGIN
    place("pad_qb", PAD_W)
    cursor += NECK_MARGIN
    place("gate_wl_r", L_GATE)
    cursor += NECK_MARGIN
    place("pad_blb", PAD_W)
    plan["_end"] = (cursor, cursor + MARGIN_X)
    return plan


X = _x_plan()
W_CELL = X["_end"][1]
X_CENTER = 0.5 * (X["pad_vss"][0] + X["pad_vss"][1])

# PMOS row / tie strips span the same x extent as the storage-node pads.
X_PMOS = (X["pad_q"][0], X["pad_qb"][1])

# ---------------------------------------------------------------------------
# Y plan: bottom-up, each band derived from the band below it.
# ---------------------------------------------------------------------------
TIE_H = PAD_W  # tie strips hold one contact row

# 1. p-substrate tie strip (VSS)
Y_PTIE_BOT = 0.20
Y_PTIE_TOP = Y_PTIE_BOT + TIE_H

# 2. wordline poly stripe
Y_WL_BOT = Y_PTIE_TOP + POLY_TO_COMP + 0.18
Y_WL_TOP = Y_WL_BOT + POLY_WIDTH

# 3. NMOS row (COMP bottom edge is straight; necks/pads grow upward)
Y_N = round(Y_WL_TOP + POLY_SPACE + POLY_EXT_COMP + 0.01, 3)
Y_N_TOP = Y_N + PAD_W
Y_POLY_N_BOT = Y_N - POLY_EXT_COMP
Y_POLY_N_TOP = Y_N_TOP + POLY_EXT_COMP

# 4. cross-couple band: two poly landing-pad jogs at different heights
JOG_H = PAD_W
Y_JOG_Q_BOT = round(Y_N_TOP + POLY_TO_COMP + 0.20, 3)
Y_JOG_Q_TOP = Y_JOG_Q_BOT + JOG_H
Y_JOG_QB_BOT = round(Y_JOG_Q_TOP + POLY_SPACE, 3)
Y_JOG_QB_TOP = Y_JOG_QB_BOT + JOG_H

# 5. PMOS row
Y_P = round(Y_JOG_QB_TOP + POLY_TO_COMP + 0.11, 3)
Y_P_TOP = Y_P + PAD_W
Y_POLY_P_TOP = Y_P_TOP + POLY_EXT_COMP

# 6. n-well tie strip (VDD) — placed so its Nplus stays IMP_SPACE clear of the
#    PMOS row's Pplus.
Y_NTIE_BOT = round(
    max(
        Y_P_TOP + COMP_SPACE,
        Y_POLY_P_TOP + POLY_TO_COMP,
        (Y_P_TOP + IMP_ENC_COMP) + IMP_SPACE + IMP_ENC_COMP,
    ),
    3,
)
Y_NTIE_TOP = Y_NTIE_BOT + TIE_H

# 7. Nwell
Y_NW_BOT = round(Y_P - NW_ENC_COMP, 3)
Y_NW_TOP = round(Y_NTIE_TOP + NW_ENC_COMP, 3)

# 8. cell height: the tightest of the vertical abutment constraints, rounded up
H_CELL = round(
    max(
        Y_NTIE_TOP + COMP_SPACE - Y_PTIE_BOT,  # tie COMP to tie COMP
        Y_NTIE_TOP + IMP_ENC_COMP + IMP_SPACE - (Y_PTIE_BOT - IMP_ENC_COMP),
        Y_NW_TOP + NW_TO_COMP - Y_PTIE_BOT,  # well to COMP outside the well
        Y_NW_TOP - Y_NW_BOT + NW_SPACE,  # well to well
    )
    + 0.035,
    2,
)

# Metal geometry that depends on the plan above.
X_BL_C = 0.5 * (X["pad_bl"][0] + X["pad_bl"][1])
X_BLB_C = 0.5 * (X["pad_blb"][0] + X["pad_blb"][1])
X_Q_C = 0.5 * (X["pad_q"][0] + X["pad_q"][1])
X_QB_C = 0.5 * (X["pad_qb"][0] + X["pad_qb"][1])

# VDD Metal1 must clear the BL stripe; the VDD Metal2 rail then sits over it.
X_VDD_M1_L = round(X_BL_C + 0.5 * M1_STRIPE_W + M1_SPACE, 3)
X_VDD_M2_C = round(X_VDD_M1_L + 0.5 * V1_SIZE + V1_ENC_M1 + 0.01, 3)
X_VSS_M2_C = X_CENTER

# Contact rows.
Y_CO_N = (Y_N + CO_ENC_COMP, Y_N + CO_ENC_COMP + CO_SIZE)
Y_CO_P = (Y_P + CO_ENC_COMP, Y_P + CO_ENC_COMP + CO_SIZE)
Y_CO_PTIE = (Y_PTIE_BOT + CO_ENC_COMP, Y_PTIE_BOT + CO_ENC_COMP + CO_SIZE)
Y_CO_NTIE = (Y_NTIE_BOT + CO_ENC_COMP, Y_NTIE_BOT + CO_ENC_COMP + CO_SIZE)

X_POLY_PAD = (X_CENTER - 0.5 * PAD_W, X_CENTER + 0.5 * PAD_W)
Y_CO_JOG_Q = (Y_JOG_Q_BOT + CO_ENC_POLY, Y_JOG_Q_BOT + CO_ENC_POLY + CO_SIZE)
Y_CO_JOG_QB = (Y_JOG_QB_BOT + CO_ENC_POLY, Y_JOG_QB_BOT + CO_ENC_POLY + CO_SIZE)

# Tie-strip contact columns (three per strip, on the storage-node and centre
# diffusion columns).
X_TIE_CONTACTS = (X_Q_C, X_CENTER, X_QB_C)
X_TIE = (
    round(min(X_TIE_CONTACTS) - 0.5 * CO_SIZE - CO_ENC_COMP, 3),
    round(max(X_TIE_CONTACTS) + 0.5 * CO_SIZE + CO_ENC_COMP, 3),
)


def _b(x0: float, y0: float, x1: float, y1: float) -> kdb.DBox:
    return kdb.DBox(x0, y0, x1, y1)


def _co(cx: float, y: tuple[float, float]) -> kdb.DBox:
    return _b(cx - 0.5 * CO_SIZE, y[0], cx + 0.5 * CO_SIZE, y[1])


def _via1(cx: float, cy: float) -> kdb.DBox:
    return _b(
        cx - 0.5 * V1_SIZE, cy - 0.5 * V1_SIZE, cx + 0.5 * V1_SIZE, cy + 0.5 * V1_SIZE
    )


def shapes() -> dict[tuple[int, int], list[kdb.DBox]]:
    """All drawn geometry of the bitcell, as micrometre boxes per layer.

    Returned as plain boxes (rather than pre-merged regions) so callers can
    inspect/re-use the plan; :func:`draw` merges them per layer before writing,
    which is what turns the pad/neck box sets into the stepped diffusion
    polygons the devices actually need.
    """
    out: dict[tuple[int, int], list[kdb.DBox]] = {k: [] for k in _LAYER_NAMES}

    # -- NMOS row: pads at full height, channel necks at each device's own W --
    for pad in ("pad_bl", "pad_q", "pad_vss", "pad_qb", "pad_blb"):
        out[L_COMP].append(_b(X[pad][0], Y_N, X[pad][1], Y_N + PAD_W))
    for gate, w in (
        ("gate_wl_l", W_PG),
        ("gate_qb", W_PD),
        ("gate_q", W_PD),
        ("gate_wl_r", W_PG),
    ):
        out[L_COMP].append(
            _b(X[gate][0] - NECK_MARGIN, Y_N, X[gate][1] + NECK_MARGIN, Y_N + w)
        )

    # -- PMOS row (inside the well): same x columns, W_PU necks --
    for pad in ("pad_q", "pad_vss", "pad_qb"):
        out[L_COMP].append(_b(X[pad][0], Y_P, X[pad][1], Y_P + PAD_W))
    for gate in ("gate_qb", "gate_q"):
        out[L_COMP].append(
            _b(X[gate][0] - NECK_MARGIN, Y_P, X[gate][1] + NECK_MARGIN, Y_P + W_PU)
        )

    # -- tie strips --
    out[L_COMP].append(_b(X_TIE[0], Y_PTIE_BOT, X_TIE[1], Y_PTIE_TOP))
    out[L_COMP].append(_b(X_TIE[0], Y_NTIE_BOT, X_TIE[1], Y_NTIE_TOP))

    # -- implants --
    out[L_NPLUS].append(_b(0.0, Y_N - IMP_ENC_COMP, W_CELL, Y_N_TOP + IMP_ENC_COMP))
    out[L_NPLUS].append(
        _b(
            X_TIE[0] - IMP_ENC_COMP,
            Y_NTIE_BOT - IMP_ENC_COMP,
            X_TIE[1] + IMP_ENC_COMP,
            Y_NTIE_TOP + IMP_ENC_COMP,
        )
    )
    out[L_PPLUS].append(
        _b(
            X_PMOS[0] - IMP_ENC_COMP,
            Y_P - IMP_ENC_COMP,
            X_PMOS[1] + IMP_ENC_COMP,
            Y_P_TOP + IMP_ENC_COMP,
        )
    )
    out[L_PPLUS].append(
        _b(
            X_TIE[0] - IMP_ENC_COMP,
            Y_PTIE_BOT - IMP_ENC_COMP,
            X_TIE[1] + IMP_ENC_COMP,
            Y_PTIE_TOP + IMP_ENC_COMP,
        )
    )

    # -- well: full cell width so wells merge along a row --
    out[L_NWELL].append(_b(0.0, Y_NW_BOT, W_CELL, Y_NW_TOP))

    # -- poly: wordline stripe + four gate stripes + two cross-couple jogs --
    out[L_POLY2].append(_b(0.0, Y_WL_BOT, W_CELL, Y_WL_TOP))
    for gate in ("gate_wl_l", "gate_wl_r"):
        out[L_POLY2].append(_b(X[gate][0], Y_WL_BOT, X[gate][1], Y_POLY_N_TOP))
    for gate in ("gate_qb", "gate_q"):
        out[L_POLY2].append(_b(X[gate][0], Y_POLY_N_BOT, X[gate][1], Y_POLY_P_TOP))
    # Q gate stripe jogs left to its landing pad; QB gate stripe jogs right to
    # its own, one POLY_SPACE higher, so the two never touch.
    out[L_POLY2].append(
        _b(X_POLY_PAD[0], Y_JOG_Q_BOT, X["gate_q"][1], Y_JOG_Q_TOP)
    )
    out[L_POLY2].append(
        _b(X["gate_qb"][0], Y_JOG_QB_BOT, X_POLY_PAD[1], Y_JOG_QB_TOP)
    )

    # -- contacts --
    for cx in (X_BL_C, X_Q_C, X_CENTER, X_QB_C, X_BLB_C):
        out[L_CONTACT].append(_co(cx, Y_CO_N))
    for cx in (X_Q_C, X_CENTER, X_QB_C):
        out[L_CONTACT].append(_co(cx, Y_CO_P))
    for cx in X_TIE_CONTACTS:
        out[L_CONTACT].append(_co(cx, Y_CO_PTIE))
        out[L_CONTACT].append(_co(cx, Y_CO_NTIE))
    out[L_CONTACT].append(_co(X_CENTER, Y_CO_JOG_Q))
    out[L_CONTACT].append(_co(X_CENTER, Y_CO_JOG_QB))

    # -- Metal1 --
    # bitline stripes, full height, abutting vertically
    out[L_METAL1].append(
        _b(X_BL_C - 0.5 * M1_STRIPE_W, 0.0, X_BL_C + 0.5 * M1_STRIPE_W, H_CELL)
    )
    out[L_METAL1].append(
        _b(X_BLB_C - 0.5 * M1_STRIPE_W, 0.0, X_BLB_C + 0.5 * M1_STRIPE_W, H_CELL)
    )
    # VSS: substrate tie bar + riser to the NMOS centre (source) diffusion
    m1_ptie = (Y_PTIE_BOT + CO_ENC_COMP - CO_ENC_M1, Y_CO_PTIE[1] + CO_ENC_M1)
    out[L_METAL1].append(
        _b(X_TIE[0] - CO_ENC_M1, m1_ptie[0], X_TIE[1] + CO_ENC_M1, m1_ptie[1])
    )
    out[L_METAL1].append(
        _b(X["pad_vss"][0], m1_ptie[0], X["pad_vss"][1], Y_CO_N[1] + CO_ENC_M1)
    )
    # VDD: well tie bar + riser down to the PMOS centre (source) diffusion
    m1_ntie = (Y_NTIE_BOT + CO_ENC_COMP - CO_ENC_M1, Y_CO_NTIE[1] + CO_ENC_M1)
    out[L_METAL1].append(
        _b(X_VDD_M1_L, m1_ntie[0], X_TIE[1] + CO_ENC_M1, m1_ntie[1])
    )
    out[L_METAL1].append(
        _b(X["pad_vss"][0], Y_CO_P[0] - CO_ENC_M1, X["pad_vss"][1], m1_ntie[1])
    )
    # Q strap: NMOS drain -> PMOS drain, plus the branch to the Q landing pad
    out[L_METAL1].append(
        _b(
            X_Q_C - 0.5 * M1_BAR_W,
            Y_CO_N[0] - CO_ENC_M1,
            X_Q_C + 0.5 * M1_BAR_W,
            Y_CO_P[1] + CO_ENC_M1,
        )
    )
    out[L_METAL1].append(
        _b(
            X_Q_C - 0.5 * M1_BAR_W,
            Y_CO_JOG_Q[0] - CO_ENC_M1,
            X_CENTER + 0.5 * M1_BAR_W,
            Y_CO_JOG_Q[1] + CO_ENC_M1,
        )
    )
    # QB strap: mirror image, one band higher
    out[L_METAL1].append(
        _b(
            X_QB_C - 0.5 * M1_BAR_W,
            Y_CO_N[0] - CO_ENC_M1,
            X_QB_C + 0.5 * M1_BAR_W,
            Y_CO_P[1] + CO_ENC_M1,
        )
    )
    out[L_METAL1].append(
        _b(
            X_CENTER - 0.5 * M1_BAR_W,
            Y_CO_JOG_QB[0] - CO_ENC_M1,
            X_QB_C + 0.5 * M1_BAR_W,
            Y_CO_JOG_QB[1] + CO_ENC_M1,
        )
    )

    # -- Via1 + Metal2 rails (vertical, so they never cross the wordline) --
    y_v1_vss = 0.5 * (Y_WL_TOP + Y_N)
    out[L_VIA1].append(_via1(X_VSS_M2_C, y_v1_vss))
    y_v1_vdd = 0.5 * (m1_ntie[0] + m1_ntie[1])
    out[L_VIA1].append(_via1(X_VDD_M2_C, y_v1_vdd))
    out[L_METAL2].append(
        _b(X_VSS_M2_C - 0.5 * M2_STRIPE_W, 0.0, X_VSS_M2_C + 0.5 * M2_STRIPE_W, H_CELL)
    )
    out[L_METAL2].append(
        _b(X_VDD_M2_C - 0.5 * M2_STRIPE_W, 0.0, X_VDD_M2_C + 0.5 * M2_STRIPE_W, H_CELL)
    )

    return out


# Label anchors, used by the standalone bitcell GDS (the array places its own
# per-row/per-column labels instead — see layout/sram_256x32/generate.py).
LABELS: tuple[tuple[tuple[int, int], str, float, float], ...] = (
    (L_METAL1_LBL, "BL", X_BL_C, 0.5 * H_CELL),
    (L_METAL1_LBL, "BLB", X_BLB_C, 0.5 * H_CELL),
    (L_METAL1_LBL, "Q", X_Q_C, 0.5 * (Y_CO_N[1] + Y_CO_P[0])),
    (L_METAL1_LBL, "QB", X_QB_C, 0.5 * (Y_CO_N[1] + Y_CO_P[0])),
    (L_POLY2_LBL, "WL", 0.5 * MARGIN_X + 0.1, 0.5 * (Y_WL_BOT + Y_WL_TOP)),
    (L_METAL2_LBL, "VDD", X_VDD_M2_C, 0.5 * H_CELL),
    (L_METAL2_LBL, "VSS", X_VSS_M2_C, 0.25 * H_CELL),
)


def draw(layout: kdb.Layout, top: kdb.Cell, with_labels: bool = True) -> None:
    """Draw the bitcell into ``top``, an already-created cell of ``layout``.

    Factored out of :func:`build` so ``layout/sram_256x32/generate.py`` can
    draw this exact cell into *its own* ``kdb.Layout`` (KLayout's array-instance
    primitive needs the instanced cell and the array's top cell to live in one
    ``Layout``), with ``with_labels=False`` so the array's 8,192 instances do
    not each carry a duplicate copy of the cell-level pin labels.
    """
    for lp, boxes in shapes().items():
        if not boxes:
            continue
        li = layout.layer(*lp)
        layout.set_info(li, kdb.LayerInfo(*lp, _LAYER_NAMES[lp]))
        region = kdb.Region()
        for box in boxes:
            region.insert(kdb.Box.from_dbox(box * (1.0 / layout.dbu)))
        region.merge()
        top.shapes(li).insert(region)

    if not with_labels:
        return
    for lp, text, x, y in LABELS:
        li = layout.layer(*lp)
        layout.set_info(li, kdb.LayerInfo(*lp, _LAYER_NAMES[lp]))
        top.shapes(li).insert(
            kdb.Text(text, kdb.Trans(int(round(x / layout.dbu)), int(round(y / layout.dbu))))
        )


def build() -> kdb.Layout:
    layout = kdb.Layout()
    layout.dbu = 0.001  # 1 dbu = 1 nm
    top = layout.create_cell(TOP_CELL)
    draw(layout, top)
    return layout


def save_options() -> kdb.SaveLayoutOptions:
    """Writer options that make the emitted GDS byte-stable (see the module
    docstring's "Determinism" section)."""
    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, f"{TOP_CELL}.gds")
    build().write(out_path, save_options())
    print(f"wrote {out_path}")
    print(f"cell pitch: {W_CELL:.3f} x {H_CELL:.3f} um  ({W_CELL * H_CELL:.3f} um^2)")


if __name__ == "__main__":
    main()
