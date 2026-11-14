#!/usr/bin/env python3
"""Minimum clock pulse width sweep: klt sim body generator and grader (issue #328).

    pulse.py gen-klt                                  # 9 bodies + 9 requests + DUT copy
    pulse.py check-klt <klt-sim-report.json>          # grade ONE variant's report
    pulse.py grade-set <report.json> [...]            # fold variants -> per-corner minimum

`spec/area-clock-pulse-power-decision.md` records "Minimum clock pulse" as
"shortest `CLK` high/low width at which the macro still completes a correct
read/write, per corner", status *not yet measured*. The only demonstrated
operating point is `CLK` 10 ns high / 10 ns low (`sim/macro-smoke/records/
20261018-082302-37ba562.md`), which is one passing point, not a minimum.

`klt sim`'s corner axes are PVT only, so the swept axis lives outside the
request: one generated body + request per grid point, the `sim/wordline-rc/`
shape. The grid is two 1-D sweeps sharing the 10/10 ns baseline (2 ns
resolution, deliberate):

    high: clk_high in {4, 6, 8, 10, 12, 14} ns at clk_low = 10 ns
    low:  clk_low  in {4, 6, 8, 10}         ns at clk_high = 10 ns

The grid brackets ABOVE 10 ns on purpose: the internal control chain at
`ss_125c_2.97v` already consumes 7.78 ns (write) / 8.68 ns (read) of the high
phase (`sim/macro-smoke/records/20261018-082301-37ba562.md`), so a grid
stopping at 10 ns would report "no passing width" at the slow corners without
having bracketed them.

The macro-smoke timing constants are NOT parameterised on pulse width, and
three of them couple the stimulus schedule to `CLK_HIGH` in ways that would
fabricate a false minimum if swept naively. This generator derives all of them
from the swept pair instead (see `derived()`), and the record states the
derived values per variant so a reader can tell a macro limit from a stimulus
artifact:

    PERIOD = clk_high + clk_low
    SAMPLE = clk_high - 1.0   (Q is probed before CLK falls, as in smoke.py,
                              where the fixed 9.0 ns is only valid while
                              CLK_HIGH > 9.0)
    SETUP  = min(6.0, clk_low - 1.0)  (input transitions happen in the low
                              phase; smoke.py's fixed 6.0 ns violates its own
                              setup discipline once clk_low < 6.0)

Everything else is copied verbatim from `sim/macro-smoke/smoke.py` (its `OPS`
table, `reduced_array()`, `pwl()` and grading rule): same reduced two-row
array, same 20 fF bit-line stand-in, same 7 sampled words, so results stay
comparable with the 10/10 ns baseline. At (10, 10) the derived constants
reproduce smoke.py's exactly (PERIOD 20, SAMPLE 9, SETUP 6), and the generated
body is line-for-line its `tb_macro_write_read.klt.spice` -- pinned by
`sim/lib/test_min_clock_pulse.py`.

`check-klt` grades one variant's report per corner against that corner's own
VDD (a bit is defined if within 20% of a rail); a variant passes a corner only
if every sampled word matches and no bit is undefined. A corner `klt sim` did
not measure (errored/failed run, missing values) is OPEN, never FAIL: an
unmeasured corner is bench evidence, not a macro failure. `grade-set` folds
the per-variant verdicts into the per-corner minimum on each axis: the
smallest grid width that passes AND has no failing or unmeasured point above
it. `>= <max grid>` / `OPEN` are reported as sentinels, never dropped, per
AC2 and the `sim/README.md` append-only rule; a passing width below the
reported minimum (a non-monotonic pass island) is recorded in the note, not
smoothed away.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
# The ratified corner matrix has a single owner, sim/lib/corner_matrix.py
# (#331); the request's `corners` block is derived from it, exactly as
# sim/macro-smoke/smoke.py does. Numbers are converted at this consumer's own
# boundary (see corner_matrix's "Axis element type").
from corner_matrix import LIB_SECTION, PROCESSES, TEMPS, VDDS  # noqa: E402

HERE = Path(__file__).resolve().parent
TB_DIR = HERE / "testbench"
REQ_DIR = HERE / "requests"

FIRST_EDGE = 5.0  # ns; edge 0 is an idle (CEN=1) initialisation cycle
TRISE = 0.1
BL_STANDIN_FF = 20  # lumped bit-line capacitance for the unpopulated rows
DUT_COPY = "sram_256x32.noarray.spice"  # copied from sim/macro-smoke/testbench/

# The swept grid: two 1-D sweeps sharing the 10/10 ns baseline (counted once,
# so 9 distinct variants, not 10). 2 ns resolution is deliberate and is stated
# in the record. Extending to 14 ns on the high axis is what brackets the
# slow corners (see the module docstring).
CLK_LOW_HELD = 10.0
CLK_HIGH_HELD = 10.0
CLK_HIGH_GRID = (4.0, 6.0, 8.0, 10.0, 12.0, 14.0)
CLK_LOW_GRID = (4.0, 6.0, 8.0, 10.0)

# (label, CEN, GWEN, A, D, WEN, expected Q after this cycle's edge or None)
# WEN[i] = 0 writes bit i. Q is only loaded by reads (CEN=0, GWEN=1).
# Copied verbatim from sim/macro-smoke/smoke.py -- do not diverge.
M32 = 0xFFFFFFFF
OPS = [
    ("idle-init", 1, 1, 0x00, 0x00000000, M32, None),
    ("write A7", 0, 0, 0xA7, 0xDEADBEEF, 0x00000000, None),
    ("write 3C", 0, 0, 0x3C, 0x12345678, 0x00000000, None),
    ("read A7", 0, 1, 0xA7, 0x00000000, M32, 0xDEADBEEF),
    ("read 3C", 0, 1, 0x3C, 0x00000000, M32, 0x12345678),
    # per-bit mask: bits 15:0 masked (WEN=1), bits 31:16 written with ones
    ("masked write A7", 0, 0, 0xA7, 0xFFFFFFFF, 0x0000FFFF, 0x12345678),
    ("read A7 after mask", 0, 1, 0xA7, 0x00000000, M32, 0xFFFFBEEF),
    ("read 3C neighbour", 0, 1, 0x3C, 0x00000000, M32, 0x12345678),
    # CEN=1 with GWEN=0 and fresh data: no write, Q holds
    ("idle (CEN=1) no write", 1, 0, 0xA7, 0x00000000, 0x00000000, 0x12345678),
    ("read A7 after idle", 0, 1, 0xA7, 0x00000000, M32, 0xFFFFBEEF),
]


def variant_tag(clk_high: float, clk_low: float) -> str:
    """Grid-point file tag, e.g. (8.0, 10.0) -> `h08_l10`."""
    return f"h{int(clk_high):02d}_l{int(clk_low):02d}"


def parse_variant(tag: str) -> tuple[float, float]:
    m = re.fullmatch(r"h(\d+)_l(\d+)", tag)
    if not m:
        raise ValueError(f"not a variant tag: {tag!r}")
    return (float(m.group(1)), float(m.group(2)))


def grid_points() -> list[tuple[float, float]]:
    """Every swept (clk_high, clk_low); the 10/10 ns baseline appears once."""
    pts = [(h, CLK_LOW_HELD) for h in CLK_HIGH_GRID]
    pts += [(CLK_HIGH_HELD, l) for l in CLK_LOW_GRID if l != CLK_LOW_HELD]
    return pts


def derived(clk_high: float, clk_low: float) -> dict[str, float]:
    """The stimulus constants smoke.py holds fixed, derived from the swept pair.

    A sweep that left these fixed would measure the testbench schedule, not
    the macro: SAMPLE must sit inside the high phase (smoke.py's 9.0 ns probe
    is only valid while CLK_HIGH > 9.0), and SETUP must sit inside the low
    phase (its 6.0 ns transitions precede the edge). PERIOD is the edge
    spacing every `.meas ... AT=` time is derived from.
    """
    return {
        "PERIOD": clk_high + clk_low,
        "SAMPLE": clk_high - 1.0,
        "SETUP": min(6.0, clk_low - 1.0),
    }


def edge(i: int, period: float) -> float:
    return FIRST_EDGE + period * i


def pwl(values, period: float, setup: float, vdd="VDDC"):
    """values: list of 0/1 per op -> PWL string, change at edge(i)-setup."""
    pts = [f"0 {vdd if values[0] else 0}"]
    prev = values[0]
    for i, v in enumerate(values[1:], 1):
        if v != prev:
            t = edge(i, period) - setup
            pts.append(f"{t:g}n {vdd if prev else 0}")
            pts.append(f"{t + TRISE:g}n {vdd if v else 0}")
            prev = v
    return "PWL(" + " ".join(pts) + ")"


def reduced_array(w):
    """The reduced `sram_64x128_array`: only the rows OPS addresses, 20 fF stand-ins.

    Copied verbatim from sim/macro-smoke/smoke.py so the array (and therefore
    the result) stays comparable with the 10/10 ns baseline record.
    """
    rows = sorted({o[3] >> 2 for o in OPS})
    pins = [f"WL{r}" for r in range(64)]
    for p in range(128):
        pins += [f"BL{p}", f"BLB{p}"]
    w(".subckt sram_64x128_array " + " ".join(pins) + " VDD VSS")
    for r in rows:
        for p in range(128):
            w(f"Xr{r}c{p} BL{p} BLB{p} WL{r} VDD VSS bitcell_6t")
    for p in range(128):
        w(f"Cbl{p} BL{p} VSS {BL_STANDIN_FF}f")
        w(f"Cblb{p} BLB{p} VSS {BL_STANDIN_FF}f")
    w(".ends")


def gen_klt(clk_high: float, clk_low: float) -> str:
    """klt sim circuit BODY for one grid point: same structure as smoke.py's.

    No corner.inc, .tran, .meas or .end. The supply is `VVDD` (altered by the
    request's `corners.supply_v.vvdd` axis); every stimulus is a 0..1 PWL
    scaled by V(VDD) through a B-source, since a body cannot use `.param
    VDDC`. At (10, 10) every non-comment line equals smoke.py's committed
    `tb_macro_write_read.klt.spice` (pinned by test_min_clock_pulse.py).
    """
    d = derived(clk_high, clk_low)
    period, clk_high_ns, setup = d["PERIOD"], clk_high, d["SETUP"]
    out = []
    w = out.append
    w(f"* Minimum clock pulse width, variant {variant_tag(clk_high, clk_low)}")
    w(f"* (CLK high {clk_high:g} ns / low {clk_low:g} ns) -- klt sim circuit BODY (issue #328).")
    w("* GENERATED by sim/min-clock-pulse/pulse.py gen-klt -- do not hand-edit.")
    w("*")
    w(f"* Derived stimulus constants for this variant: PERIOD={period:g},"
      f" SETUP={setup:g}, SAMPLE={d['SAMPLE']:g} (ns).")
    w("* Same reduced two-row array and 20 fF bit-line stand-in as")
    w("* sim/macro-smoke (records stay comparable with the 10/10 ns baseline).")
    w(".include './sram_256x32.noarray.spice'")
    w("* PDK default params normally supplied by design.ngspice (via corner.inc)")
    for p in ("sw_stat_global=0", "sw_stat_mismatch=0", "mc_skew=3", "res_mc_skew=3", "cap_mc_skew=3", "fnoicor=0"):
        w(f".param {p}")
    w("VVDD VDD 0 DC 3.3")
    w("VVSS VSS 0 DC 0")
    reduced_array(w)
    w("")
    n = len(OPS)
    clk = ["0 0"]
    for i in range(n):
        e = edge(i, period)
        clk += [
            f"{e:g}n 0",
            f"{e + TRISE:g}n 1",
            f"{e + clk_high_ns:g}n 1",
            f"{e + clk_high_ns + TRISE:g}n 0",
        ]
    w("V1CLK CLK_s 0 PWL(" + " ".join(clk) + ")")
    w("V1CEN CEN_s 0 " + pwl([o[1] for o in OPS], period, setup, "1"))
    w("V1GWEN GWEN_s 0 " + pwl([o[2] for o in OPS], period, setup, "1"))
    w("BCLK CLK 0 V='v(VDD)*v(CLK_s)'")
    w("BCEN CEN 0 V='v(VDD)*v(CEN_s)'")
    w("BGWEN GWEN 0 V='v(VDD)*v(GWEN_s)'")
    for b in range(8):
        w(f"V1A{b} A{b}_s 0 " + pwl([o[3] >> b & 1 for o in OPS], period, setup, "1"))
        w(f"BA{b} A[{b}] 0 V='v(VDD)*v(A{b}_s)'")
    for b in range(32):
        w(f"V1D{b} D{b}_s 0 " + pwl([o[4] >> b & 1 for o in OPS], period, setup, "1"))
        w(f"BD{b} D[{b}] 0 V='v(VDD)*v(D{b}_s)'")
        w(f"V1W{b} WEN{b}_s 0 " + pwl([o[5] >> b & 1 for o in OPS], period, setup, "1"))
        w(f"BW{b} WEN[{b}] 0 V='v(VDD)*v(WEN{b}_s)'")
    pins = " ".join(
        [f"A[{b}]" for b in range(7, -1, -1)]
        + ["CEN", "GWEN", "CLK"]
        + [f"D[{b}]" for b in range(31, -1, -1)]
        + [f"WEN[{b}]" for b in range(31, -1, -1)]
        + [f"Q[{b}]" for b in range(31, -1, -1)]
    )
    w(f"XDUT {pins} VDD VSS sram_256x32")
    for b in range(32):
        w(f"CQ{b} Q[{b}] 0 20f")
    w(".option method=gear reltol=2e-3 abstol=1e-12 itl4=100")
    return "\n".join(out) + "\n"


def klt_request(clk_high: float, clk_low: float) -> dict:
    """The klt sim request for one grid point: the ratified 27-corner matrix
    (derived from sim/lib/corner_matrix.py), one FIND per sampled Q bit, every
    `.meas ... AT=` time derived from this variant's PERIOD."""
    d = derived(clk_high, clk_low)
    meas = []
    for i, o in enumerate(OPS):
        if o[6] is None:
            continue
        ts = edge(i, d["PERIOD"]) + d["SAMPLE"]
        for b in range(32):
            meas.append({
                "name": f"q{b}_op{i}",
                "spice": f".meas tran q{b}_op{i} FIND v(Q[{b}]) AT={ts:g}n",
                "unit": "V",
            })
    return {
        "netlist": f"../testbench/tb_min_clk_{variant_tag(clk_high, clk_low)}.klt.spice",
        "engine": "ngspice",
        "models": {"lib": "$PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": [{"name": p, "sections": [LIB_SECTION[p]]} for p in PROCESSES],
            "supply_v": {"vvdd": [float(v) for v in VDDS]},
            "temperature_c": [int(t) for t in TEMPS],
        },
        "analysis": {"kind": "tran", "args": f"0.02n {edge(len(OPS) - 1, d['PERIOD']) + d['PERIOD']:g}n"},
        "measurements": meas,
        "netlist_source": "schematic",
        "options": {"timeout_s": 1500},
    }


# --- grading -----------------------------------------------------------------

PASS, FAIL, OPEN = "PASS", "FAIL", "OPEN"


def grade_corner(corner) -> dict:
    """Grade one corner of a report: rebuild every sampled Q word against that
    corner's own VDD (a bit is defined if within 20% of a rail, the smoke.py
    rule). A corner klt sim did not measure is OPEN with its klt status named,
    never FAIL: an unmeasured corner is bench evidence, not a macro failure."""
    vdd = corner["supply_v"]["vvdd"]
    klt_status = corner.get("status", "?")
    vals = {}
    for m in corner.get("measurements") or []:
        r = re.fullmatch(r"q(\d+)_op(\d+)", m["name"])
        if r and m.get("value") is not None:
            vals[(int(r.group(2)), int(r.group(1)))] = float(m["value"])
    bad = missing = und_total = 0
    for i, o in enumerate(OPS):
        if o[6] is None:
            continue
        got = 0
        und = 0
        for b in range(32):
            v = vals.get((i, b))
            if v is None:
                missing += 1
                continue
            if not (v < 0.2 * vdd or v > 0.8 * vdd):
                und += 1
            got |= (1 if v > vdd / 2 else 0) << b
        und_total += und
        if und or (not missing and got != o[6]):
            bad += 1
    if missing:
        status = OPEN
    elif bad:
        status = FAIL
    else:
        status = PASS
    return {
        "status": status,
        "words_bad": bad,
        "unmeasured_bits": missing,
        "undefined_bits": und_total,
        "klt_status": klt_status,
    }


def grade_report(report) -> tuple[str, dict]:
    """Grade a whole report; return (variant_tag, {corner_id: verdict})."""
    rep = report if isinstance(report, dict) else json.loads(Path(report).read_text())
    m = re.search(r"tb_min_clk_(h\d+_l\d+)\.klt\.spice", rep.get("netlist", {}).get("path", ""))
    if not m:
        raise ValueError(f"report is not a min-clock-pulse variant: {rep.get('netlist')}")
    return m.group(1), {c["corner_id"]: grade_corner(c) for c in rep["corners"]}


def check_klt(report) -> int:
    """Grade one variant's report; print RESULT lines in the repo convention.
    Exit 1 on any FAIL, 2 if only OPEN rows remain, 0 if every corner passed."""
    tag, verdicts = grade_report(report)
    fail = open_ = 0
    for cid, v in verdicts.items():
        fail += v["status"] == FAIL
        open_ += v["status"] == OPEN
        extra = f" words_bad={v['words_bad']} unmeasured_bits={v['unmeasured_bits']}"
        if v["status"] == OPEN:
            extra += f" klt_status={v['klt_status']}"
        elif v["status"] == PASS:
            extra += f" undefined_bits={v['undefined_bits']}"
        print(f"RESULT: {cid} {tag} {v['status']} ({extra.strip()})")
    print(
        f"RESULT: {tag} = {'FAIL' if fail else 'OPEN' if open_ else 'PASS'}"
        f" over {len(verdicts)} corners"
    )
    return 1 if fail else 2 if open_ else 0


def fold_axis(statuses: dict, grid: tuple) -> tuple:
    """Reduce one corner's one axis ({width: PASS/FAIL/OPEN}) to its report
    value. Returns (display, note). The reported minimum is the smallest grid
    width that passes AND has no failing or unmeasured point above it; a pass
    island below it is recorded in the note, not smoothed. Sentinels per AC2:
    any unmeasured width -> OPEN (the sweep is incomplete at this corner); no
    passing width -> OPEN; smallest passing width == largest grid point ->
    `>= <max grid>` (the grid does not bracket the minimum from above)."""
    measured = {w: s for w, s in statuses.items() if s != OPEN}
    if len(measured) != len(statuses):
        unmeas = sorted(w for w, s in statuses.items() if s == OPEN)
        return OPEN, f"unmeasured at {[f'{w:g} ns' for w in unmeas]}"
    if not measured:
        return OPEN, "no passing width in the swept grid"
    passing = sorted(w for w, s in measured.items() if s == PASS)
    if not passing:
        return OPEN, "no passing width in the swept grid"
    w_star = None
    for w in passing:
        if all(measured[u] == PASS for u in grid if u > w):
            w_star = w
            break
    if w_star is None:
        return f">= {max(grid):g} ns", (
            "every passing width has a failing width above it (pass islands);"
            " no bracketed minimum"
        )
    islands = [w for w in passing if w < w_star]
    note = ""
    if islands:
        note = "pass island at " + ", ".join(f"{w:g} ns" for w in islands)
    if w_star == max(grid):
        return f">= {max(grid):g} ns", (
            (note + "; " if note else "")
            + "smallest passing width is the largest grid point; the grid does not bracket the minimum"
        )
    return f"{w_star:g} ns", note


def grade_set(reports) -> int:
    """Fold per-variant verdicts into the per-corner minimum on each axis.
    Exit 0 if every corner is bracketed on both axes; 2 if any corner carries
    a sentinel (OPEN / >= max) -- recorded evidence, not a crash; 1 on a
    structural problem (unreadable report, variant off the grid, an axis
    missing a variant)."""
    by_axis = {}  # corner_id -> {"high": {width: status}, "low": {...}}
    seen_axes = {}  # corner_id -> {"high": set(tags), "low": set(tags)}
    sentinels = 0
    for path in reports:
        tag, verdicts = grade_report(path)
        high, low = parse_variant(tag)
        if low == CLK_LOW_HELD:
            axes = [("high", high)]  # a high-axis variant (incl. the 10/10 baseline)
        else:
            axes = [("low", low)]
        if high == CLK_HIGH_HELD and low == CLK_LOW_HELD:
            axes.append(("low", low))  # the shared baseline is the low axis's 10 ns point
        for axis, width in axes:
            for cid, v in verdicts.items():
                by_axis.setdefault(cid, {"high": {}, "low": {}})[axis][width] = v["status"]
                seen_axes.setdefault(cid, {"high": [], "low": []})[axis].append(tag)
    for cid in sorted(by_axis):
        cells = {}
        for axis, grid in (("high", CLK_HIGH_GRID), ("low", CLK_LOW_GRID)):
            expected = len(grid)
            got = len(seen_axes[cid][axis])
            if got != expected:
                missing = sorted(set(grid_tags(axis)) - set(seen_axes[cid][axis]))
                print(
                    f"ERROR: {cid}: {axis} axis has {got} of {expected} variants"
                    f" (missing: {missing})",
                    file=sys.stderr,
                )
                return 1
            display, note = fold_axis(by_axis[cid][axis], grid)
            cells[axis] = (display, note, by_axis[cid][axis])
            if display == OPEN or display.startswith(">="):
                sentinels += 1

        def status_str(m):
            return " ".join(f"{w:g}:{s[0]}" for w, s in sorted(m.items()))

        print(
            f"MIN: {cid} high={cells['high'][0]} low={cells['low'][0]}"
            f"  [high {status_str(cells['high'][2])} | low {status_str(cells['low'][2])}]"
        )
        for axis in ("high", "low"):
            if cells[axis][1]:
                print(f"NOTE: {cid} {axis}: {cells[axis][1]}")
    print(
        f"RESULT: grade-set over {len(by_axis)} corners x {len(reports)} variants"
        f" ({sentinels} sentinel axes: OPEN or >= max grid)"
    )
    return 2 if sentinels else 0


def grid_tags(axis: str) -> list[str]:
    """variant_tag for every grid point on one axis."""
    if axis == "high":
        return [variant_tag(h, CLK_LOW_HELD) for h in CLK_HIGH_GRID]
    return [variant_tag(CLK_HIGH_HELD, l) for l in CLK_LOW_GRID]


def gen_all(out_tb: Path = TB_DIR, out_req: Path = REQ_DIR) -> list[Path]:
    """Write every grid point's body + request, plus the DUT copy. A pure
    function of this module and the committed DUT copy source, so re-running
    leaves `git status` clean (idempotency is pinned by the offline test)."""
    out_tb.mkdir(parents=True, exist_ok=True)
    out_req.mkdir(parents=True, exist_ok=True)
    written = []
    src = HERE.parent / "macro-smoke" / "testbench" / DUT_COPY
    (out_tb / DUT_COPY).write_bytes(src.read_bytes())
    written.append(out_tb / DUT_COPY)
    for high, low in grid_points():
        tag = variant_tag(high, low)
        body = out_tb / f"tb_min_clk_{tag}.klt.spice"
        body.write_text(gen_klt(high, low))
        req = out_req / f"min_clk_{tag}.json"
        req.write_text(json.dumps(klt_request(high, low), indent=2) + "\n")
        written += [body, req]
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gen-klt", help="write all bodies + requests + the DUT copy")
    ck = sub.add_parser("check-klt", help="grade one variant's klt sim report")
    ck.add_argument("report")
    gs = sub.add_parser("grade-set", help="fold variant reports into per-corner minimums")
    gs.add_argument("reports", nargs="+")
    a = ap.parse_args()
    if a.cmd == "gen-klt":
        for p in gen_all():
            print(f"wrote {p}")
    elif a.cmd == "check-klt":
        sys.exit(check_klt(a.report))
    else:
        sys.exit(grade_set(a.reports))
