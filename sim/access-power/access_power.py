#!/usr/bin/env python3
"""Dynamic energy per read/write access on the macro-smoke netlist (#329).

    access_power.py gen-klt [--out ...] [--request-out ...]   # klt sim body + request
    access_power.py check-klt <klt-sim-report.json>

`gen-klt` emits the *same* circuit and the *same* stimulus as
`sim/macro-smoke/smoke.py gen-klt` -- it imports that generator rather than
forking its 800-odd generated lines -- and differs from it only in the
measurement set of the request it writes beside it: two `.meas tran ... INTEG
i(vvdd)` windows, one per full clock cycle of one write and one read, plus the
read cycle's functional `FIND v(Q[*])` probes.

`check-klt` converts each corner's integrated supply charge to energy per
access at that corner's own supply (`E = Q x VDD`), checks that the read cycle
actually returned the expected word, and fails closed: a corner missing from
the report, a duplicated corner, a null measurement, a repeated measurement
name, or a read that did not return `0xDEADBEEF` is
reported `OPEN`, never dropped; a non-physical charge is `FAIL`.

Recorded quantity, no threshold: see `sim/access-power/README.md` and the
records' "Limits" for what the number does and does not include.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "sim" / "macro-smoke"))
sys.path.insert(0, str(REPO_ROOT / "sim" / "lib"))
import smoke  # noqa: E402  (path-injected import, as measurements/generate_report.py does)

# The ratified corner matrix has a single owner, sim/lib/corner_matrix.py
# (#331) -- imported here rather than re-listed, so the request this module
# builds and the completeness this grader asserts cannot drift from the
# ratified matrix. `klt sim` wants the two numeric axes as JSON numbers, so
# they are converted at this consumer's own boundary: the owner holds every
# axis point as the spec's literal label (see that module's "Axis element
# type").
from corner_matrix import (  # noqa: E402
    LIB_SECTION,
    PROCESSES,
    TEMPS,
    VDDS,
    corners as ratified_corners,
)

# The DUT include as `smoke.gen_klt()` writes it (resolved beside *its* body)
# and as this body needs it (one checked-in copy, not a second one here).
SMOKE_INCLUDE = ".include './sram_256x32.noarray.spice'"
OUR_INCLUDE = ".include '../../macro-smoke/testbench/sram_256x32.noarray.spice'"

# The two operations whose cycles are integrated, by their `smoke.OPS` label:
# an edge-to-edge window, so the control-pulse chain, bit-line restore and
# output charging that follow the edge are all inside the number.
WRITE_LABEL = "write A7"
READ_LABEL = "read A7"

# ngspice reports the current *through* a voltage source as flowing from its
# `+` node into the source, so `i(vvdd)` is negative while VVDD supplies the
# circuit. The raw `.meas ... INTEG` is kept unsigned in SPICE and negated
# here, so the committed report holds the simulator's own number and the
# convention lives in exactly one place.
CHARGE_SIGN = -1.0


def op_index(label):
    """Index of `label` in `smoke.OPS`, or a loud failure if it moved."""
    for i, o in enumerate(smoke.OPS):
        if o[0] == label:
            return i
    raise SystemExit(
        f"access_power: no operation labelled {label!r} in smoke.OPS -- the "
        "macro-smoke stimulus changed; re-derive the integration windows "
        "before regenerating this testbench."
    )


def window(i):
    """The full clock cycle of `smoke.OPS[i]`, in ns: edge to the next edge."""
    return smoke.edge(i), smoke.edge(i) + smoke.PERIOD


def corner_id(process, vdd, temp):
    """`klt sim`'s own corner label, as it appears in a report's `corner_id`."""
    return f"{process}/{vdd:.3f}V/{temp:g}C"


def expected_corners():
    """The 27 (process, supply, temperature) points the request declares: the
    owner's loop order, converted to this grader's numeric boundary types."""
    return [(p, float(v), int(t)) for p, t, v in ratified_corners()]


def gen_klt():
    """The macro-smoke circuit body, re-banner-ed and re-pointed at the one
    checked-in `sram_256x32.noarray.spice`. Identical cards otherwise: the
    energy is attributable to the same operating point the functional smoke
    already grades."""
    body = smoke.gen_klt()
    head, sep, tail = body.partition(SMOKE_INCLUDE)
    if not sep:
        raise SystemExit(
            "access_power: smoke.gen_klt() no longer emits "
            f"{SMOKE_INCLUDE!r} -- re-check the DUT include before "
            "regenerating this testbench."
        )
    stray = [ln for ln in head.splitlines() if ln.strip() and not ln.startswith("*")]
    if stray:
        raise SystemExit(
            "access_power: smoke.gen_klt() now emits circuit cards before its "
            f"DUT include ({stray[0]!r}); this generator would drop them. "
            "Re-check the body assembly."
        )
    out = [
        "* Macro dynamic access energy -- klt sim circuit BODY (issue #329).",
        "* GENERATED by sim/access-power/access_power.py gen-klt -- do not hand-edit.",
        "*",
        "* The circuit and the stimulus are sim/macro-smoke/smoke.py's gen_klt()",
        "* verbatim (imported, not copied): the same reduced two-row array, the same",
        "* 20 fF bit-line stand-ins, the same 32 x 20 fF Q[*] output load, the same",
        "* ten-cycle PWL stimulus. Only the request's measurement set differs --",
        "* requests/access_power.json integrates i(vvdd) over one write cycle and",
        "* one read cycle instead of sampling Q. The DUT include points at the one",
        "* checked-in copy under sim/macro-smoke/testbench/ rather than a second one.",
        "* Recorded quantity, no threshold; see the records' Limits.",
    ]
    return "\n".join(out) + "\n" + OUR_INCLUDE + tail


def klt_request():
    """The `klt sim` request for gen_klt(): 27 corners, two cycle-charge
    integrals, and the read cycle's 32 functional `Q` probes."""
    meas = []
    for name, label in (("q_write", WRITE_LABEL), ("q_read", READ_LABEL)):
        t0, t1 = window(op_index(label))
        meas.append(
            {
                "name": name,
                "spice": f".meas tran {name} INTEG i(vvdd) FROM={t0:g}n TO={t1:g}n",
                "unit": "C",
            }
        )
    ts = smoke.edge(op_index(READ_LABEL)) + smoke.SAMPLE
    for b in range(32):
        meas.append(
            {
                "name": f"q{b}_rd",
                "spice": f".meas tran q{b}_rd FIND v(Q[{b}]) AT={ts:g}n",
                "unit": "V",
            }
        )
    return {
        "netlist": "../testbench/tb_access_power.klt.spice",
        "engine": "ngspice",
        "models": {"lib": "$PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": [{"name": p, "sections": [LIB_SECTION[p]]} for p in PROCESSES],
            "supply_v": {"vvdd": [float(v) for v in VDDS]},
            "temperature_c": [int(t) for t in TEMPS],
        },
        "analysis": {
            "kind": "tran",
            "args": f"0.02n {smoke.edge(len(smoke.OPS) - 1) + smoke.PERIOD:g}n",
        },
        "measurements": meas,
        "netlist_source": "schematic",
        "options": {"timeout_s": 1500},
        # Each corner of this deck takes ~5-7 minutes, so 27 of them serially
        # in one batch job (~2.6 h) is killed at the fleet's whole-job ceiling
        # with every unit reported `batch_job_timeout`. Shard it: 14 hosts is
        # at most 2 units per shard, each comfortably inside the ceiling. The
        # same reason `sim/macro-smoke`'s 27-corner run of this deck went out
        # as 9 shards (its record's fleet array).
        "remote": {"hosts": 14},
    }


def read_word(meas, vdd):
    """Rebuild the read cycle's 32-bit word against this corner's own VDD.
    Returns (word, undefined_bits, unmeasured_bits)."""
    word = undefined = unmeasured = 0
    for b in range(32):
        v = meas.get(f"q{b}_rd")
        if v is None:
            unmeasured += 1
            continue
        if not (v < 0.2 * vdd or v > 0.8 * vdd):
            undefined += 1
        word |= (1 if v > vdd / 2 else 0) << b
    return word, undefined, unmeasured


def grade_corner(c, expected_word):
    """One corner -> (status, note). `energies` in J, `charges` in C."""
    vdd = c["supply_v"]["vvdd"]
    meas = {}
    for m in c.get("measurements") or []:
        v = m.get("value")
        name = m["name"]
        if name in meas:
            # A repeated measurement name is ambiguous -- two claims about
            # one quantity. Grade it unmeasured (OPEN) rather than letting
            # last-wins silently pick a copy.
            meas[name] = None
            continue
        meas[name] = None if v is None else float(v)

    charges, bad = {}, []
    for name in ("q_write", "q_read"):
        q = meas.get(name)
        if q is None:
            bad.append(f"{name}=unmeasured")
            continue
        q *= CHARGE_SIGN
        if not math.isfinite(q) or q <= 0.0:
            bad.append(f"{name}={q:.4g}C non-physical")
        charges[name] = q

    word, undefined, unmeasured = read_word(meas, vdd)
    if unmeasured:
        return "OPEN", f"unmeasured_q_bits={unmeasured}"
    if undefined:
        return "OPEN", f"undefined_q_bits={undefined}"
    if word != expected_word:
        return "OPEN", f"read_word=0x{word:08X} expected=0x{expected_word:08X}"
    if any("unmeasured" in b for b in bad):
        return "OPEN", " ".join(bad)
    if bad:
        return "FAIL", " ".join(bad)

    parts = []
    for name, op in (("q_write", "write"), ("q_read", "read")):
        q = charges[name]
        parts.append(f"e_{op}={q * vdd / 1e-12:.4g} pJ (q={q / 1e-12:.4g} pC)")
    return "PASS", " ".join(parts) + f" vdd={vdd:g} V"


def check_klt(report):
    """Grade a `klt sim` report of klt_request(). Prints one `RESULT:` line per
    expected corner -- a corner absent from the report, or a corner the report
    carries more than once, is `OPEN`, not dropped -- then the rollup. Exit 1
    on any FAIL, 2 if only OPEN rows remain, else 0."""
    rep = json.loads(Path(report).read_text())
    expected_word = smoke.OPS[op_index(READ_LABEL)][6]
    if expected_word is None:
        raise SystemExit(
            f"access_power: smoke.OPS[{READ_LABEL!r}] declares no expected word; "
            "the functional read check cannot be graded."
        )

    seen = {}
    dups = set()
    for c in rep.get("corners") or []:
        key = (c["process"], round(float(c["supply_v"]["vvdd"]), 3), int(c["temperature_c"]))
        if key in seen:
            # The report carries two corners under one identity: whichever
            # copy graded better, the report is ambiguous. Fail closed.
            dups.add(key)
        seen[key] = c

    fail = open_ = 0
    for process, vdd, temp in expected_corners():
        key = (process, round(vdd, 3), temp)
        c = seen.pop(key, None)
        label = corner_id(process, vdd, temp)
        if key in dups:
            status, note = "OPEN", "duplicate corner in report"
        elif c is None:
            status, note = "OPEN", "corner absent from report"
        else:
            label = c.get("corner_id") or label
            status, note = grade_corner(c, expected_word)
        fail += status == "FAIL"
        open_ += status == "OPEN"
        print(f"RESULT: {label} {status} ({note})")
    for key, c in sorted(seen.items()):
        open_ += 1
        note = "corner not in the ratified 27-point matrix"
        if key in dups:
            note = f"duplicate corner in report; {note}"
        print(f"RESULT: {c.get('corner_id') or key} OPEN ({note})")

    total = len(expected_corners()) + len(seen)
    roll = "FAIL" if fail else "OPEN" if open_ else "PASS"
    print(f"RESULT: access_power = {roll} over {total} corners ({open_} open, {fail} fail)")
    return 1 if fail else 2 if open_ else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    gk = sub.add_parser("gen-klt")
    gk.add_argument("--out", default="sim/access-power/testbench/tb_access_power.klt.spice")
    gk.add_argument("--request-out", default="sim/access-power/requests/access_power.json")
    ck = sub.add_parser("check-klt")
    ck.add_argument("report")
    a = ap.parse_args()
    if a.cmd == "gen-klt":
        Path(a.out).write_text(gen_klt())
        Path(a.request_out).write_text(json.dumps(klt_request(), indent=2) + "\n")
    else:
        sys.exit(check_klt(a.report))
