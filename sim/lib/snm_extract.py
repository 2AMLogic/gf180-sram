#!/usr/bin/env python3
"""Static noise margin (SNM) extraction from a single half-cell VTC sweep.

Why one sweep is enough: `bitcell_6t`'s two storage inverters
(MPL/MNL and MPR/MNR in design/netlist/bitcell_6t.spice) are identical
devices under a cross-coupled connection. For a cell built from two
identical inverters, the classic "butterfly curve" (the two inverters'
voltage-transfer curves plotted against each other, one mirrored across the
line Vout=Vin) can be constructed from a *single* inverter's VTC sweep: the
first branch is the sweep itself, y = f(x); the second branch is that same
inverter's curve reflected across the diagonal, i.e. the *inverse* relation
x = f(y), which -- because the two inverters are identical devices -- is
exactly the transfer curve the other half-cell would produce. This is a
standard simplification for symmetric 6T SRAM SNM extraction (see e.g. E.
Seevinck et al., "Static-Noise Margin Analysis of MOS SRAM Cells," IEEE
JSSC 1987, for the general two-curve method this specializes).

SNM is then the side length of the largest axis-aligned square that fits
between the two curves within one lobe of the butterfly plot. Because the
second curve is the exact mirror image of the first about y=x, the maximum
vertical gap between the sweep curve and its own inverse -- found for x in
one lobe -- equals that maximum square's side length.

Finding the two curves' intersections (f(x) = f^-1(x)) is equivalent to
finding the fixed points of f composed with itself: f(f(x)) = x. This
script uses that composition directly, evaluated with forward
interpolation only (never constructing an explicit inverse-of-f table).
That matters in practice: a naive "swap the (x, y) pairs and sort" way of
building f^-1 is numerically fragile wherever f's sampled *output* changes
extremely slowly (its slope near either rail can under/overflow float
resolution over a wide span of x), which biases a sorted-table inverse and
silently drops a real crossing. Forward interpolation of the original,
evenly-sampled-in-x sweep has no such flat-tail pathology, so composing it
with itself is the robust way to find the same roots.

Input: a two-column whitespace-separated ASCII data file (Vin, Vout), as
written by ngspice's `wrdata` from a DC sweep, monotonically increasing in
Vin. Output: prints `RESULT: <label> = <value>` (volts) to stdout, and
exits 1 with a diagnostic on stderr if the curve is degenerate (e.g. it
never regenerates into a bistable pair at this corner -- a reportable open
result, never silently coerced to a positive number).
"""
from __future__ import annotations

import sys


def read_xy(path: str) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("*", "#")):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                x, y = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            pts.append((x, y))
    return pts


def interp(pts: list[tuple[float, float]], x: float) -> float:
    """Linear interpolation of y at x over a curve sorted ascending by x.

    Queries outside [pts[0].x, pts[-1].x] clamp to the nearest endpoint.
    """
    xs_lo, xs_hi = pts[0][0], pts[-1][0]
    if x <= xs_lo:
        return pts[0][1]
    if x >= xs_hi:
        return pts[-1][1]
    lo, hi = 0, len(pts) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pts[mid][0] <= x:
            lo = mid
        else:
            hi = mid
    x0, y0 = pts[lo]
    x1, y1 = pts[hi]
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def solve_inverse(pts: list[tuple[float, float]], target_y: float) -> float:
    """Find x such that interp(pts, x) == target_y, via bisection.

    Assumes `pts` (sorted ascending by x) is monotonic in y -- true for any
    single-stage CMOS inverter's VTC. Bisection only ever evaluates the
    well-behaved forward `interp`, so it is immune to the flat-tail
    pathology a sorted-and-swapped inverse table hits (see module
    docstring).
    """
    lo, hi = pts[0][0], pts[-1][0]
    y_lo, y_hi = pts[0][1], pts[-1][1]
    decreasing = y_lo >= y_hi
    for _ in range(80):
        mid = (lo + hi) / 2
        y_mid = interp(pts, mid)
        above = y_mid >= target_y
        if above == decreasing:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def find_crossings(pts: list[tuple[float, float]]) -> list[float]:
    """x-values where f(x) = f^-1(x), found as the fixed points of f o f.

    This is *not* the same as f(x) = x: for two identical cross-coupled
    inverters with output-vs-input curve f, the two stable states
    (Q, QB) = (a, b) and (b, a) satisfy f(a) = b and f(b) = a, so
    f(f(a)) = f(b) = a -- i.e. a is a fixed point of f o f, generally
    *not* of f alone (unless a = b, the metastable point, which trivially
    satisfies both). Scanning h(x) = f(f(x)) - x for sign changes recovers
    all 3 fixed points (low stable, metastable, high stable) for a
    bistable pair, using only forward interpolation of the original sweep.
    """
    def h(x: float, y_at_x: float) -> float:
        return interp(pts, y_at_x) - x

    raw_crossings = []
    h_values = [h(x, y) for x, y in pts]
    for i in range(len(pts) - 1):
        prev_x, prev_h = pts[i][0], h_values[i]
        cur_x, cur_h = pts[i + 1][0], h_values[i + 1]
        if prev_h == 0:
            raw_crossings.append(prev_x)
        elif (prev_h > 0) != (cur_h > 0):
            denom = cur_h - prev_h
            frac = -prev_h / denom if denom != 0 else 0.0
            raw_crossings.append(prev_x + frac * (cur_x - prev_x))
    if h_values[-1] == 0:
        raw_crossings.append(pts[-1][0])

    # A fixed point that sits exactly at (or a hair past, by solver
    # tolerance) the sweep's own boundary never produces a sign flip --
    # there is no sample beyond the boundary to flip against -- so it
    # would otherwise go undetected even though h is essentially zero
    # there. This is the common case for an inverter whose VTC saturates
    # very close to (but not exactly at) a rail: treat "close enough to
    # zero" at the two sweep endpoints as a boundary crossing too, using a
    # tolerance tied to the sweep's own y-span (SPICE convergence is
    # typically far coarser than float precision, so 0.1% of the swept
    # output range is a conservative, still-tight, band).
    y_span = max(y for _, y in pts) - min(y for _, y in pts)
    boundary_tol = max(y_span * 1e-3, 1e-6)
    if abs(h_values[0]) <= boundary_tol and (not raw_crossings or abs(raw_crossings[0] - pts[0][0]) > 1e-12):
        raw_crossings.insert(0, pts[0][0])
    if abs(h_values[-1]) <= boundary_tol and (not raw_crossings or abs(raw_crossings[-1] - pts[-1][0]) > 1e-12):
        raw_crossings.append(pts[-1][0])

    if not raw_crossings:
        return []
    # Dedupe crossings closer together than 0.5% of the swept x-span --
    # numerical noise near a near-tangent crossing can otherwise register
    # as two adjacent detections instead of one.
    span = pts[-1][0] - pts[0][0]
    eps = max(span * 0.005, 1e-9)
    deduped = [raw_crossings[0]]
    for c in raw_crossings[1:]:
        if c - deduped[-1] > eps:
            deduped.append(c)
    return deduped


def snm(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Return (snm_lobe_low, snm_lobe_high) -- the two stable-lobe margins.

    A bistable inverter pair has 3 fixed points of f o f: low stable
    point, metastable midpoint, high stable point. The low lobe spans
    [x_low, x_mid]; the high lobe spans [x_mid, x_high]. SNM per spec is
    "the minimum butterfly-curve square side length" -- report both
    lobes; the macro-level claim is the minimum of the two (spec/sram.md's
    "must be > 0 at every corner" applies to both).
    """
    crossings = find_crossings(pts)
    if len(crossings) < 3:
        raise ValueError(
            f"f(f(x))-x has {len(crossings)} root(s), not the 3 required "
            "for a bistable cell (low/meta/high) -- not a valid butterfly "
            "curve at this corner"
        )
    # Exactly 3 is the common case. If more survive dedup (a noisy or
    # near-tangent corner), take the outermost pair as the stable states
    # and the crossing nearest their midpoint as the metastable point --
    # the two lobes of interest are still bounded by the true extremes.
    x_lo, x_hi = crossings[0], crossings[-1]
    interior = crossings[1:-1]
    x_mid = (
        min(interior, key=lambda c: abs(c - (x_lo + x_hi) / 2))
        if interior
        else (x_lo + x_hi) / 2
    )

    def max_gap(x_start: float, x_end: float) -> float:
        # Sample within [x_start, x_end], evaluating the vertical distance
        # between the sweep curve f(x) and its mirror image about y=x,
        # f^-1(x) -- found by bisection (solve_inverse), not a sorted
        # inverse table. This vertical gap (a constant-x cross-section
        # between the curve and its point reflection about the diagonal)
        # is directly the side length of the largest axis-aligned square
        # inscribed between the two curves, per Seevinck et al. 1987's
        # construction -- no additional geometric factor is needed.
        best = 0.0
        for x, y in pts:
            if x_start <= x <= x_end:
                y_inv = solve_inverse(pts, x)
                best = max(best, abs(y_inv - y))
        return best

    lo_gap = max_gap(x_lo, x_mid)
    hi_gap = max_gap(x_mid, x_hi)
    return lo_gap, hi_gap


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: snm_extract.py <data-file> <label>", file=sys.stderr)
        return 2
    data_path, label = sys.argv[1], sys.argv[2]
    pts = read_xy(data_path)
    if len(pts) < 5:
        print(f"RESULT-ERROR: {label} -- fewer than 5 data points in {data_path}", file=sys.stderr)
        return 1
    pts.sort(key=lambda p: p[0])
    try:
        lo, hi = snm(pts)
    except ValueError as exc:
        print(f"RESULT-ERROR: {label} -- {exc}", file=sys.stderr)
        return 1
    margin = min(lo, hi)
    print(f"RESULT: {label}_lobe_low_v = {lo:.6f}")
    print(f"RESULT: {label}_lobe_high_v = {hi:.6f}")
    print(f"RESULT: {label}_v = {margin:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
