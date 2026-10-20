#!/usr/bin/env python3
"""Offline contract tests for sim/lib/deck_adapter.py (#230).

No ngspice, no PDK, no fleet. Reports below are hand-built STUBS that exercise
the reducer's contract (coverage, shapes, failure handling); nothing here is
physical evidence and no stub result may be quoted as a measurement.

Run: python3 sim/lib/test_deck_adapter.py   (or via `npm run test`)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deck_adapter as da  # noqa: E402

REPO = da.REPO_ROOT
FAILURES = []


def check(name, cond, detail=""):
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def test_corner_matrix():
    ids = da.corner_ids()
    check("27 corners", len(ids) == 27 and len(set(ids)) == 27, str(len(ids)))
    check("first/last", ids[0] == "ff_-40c_2.97v" and ids[-1] == "ss_125c_3.63v", f"{ids[0]} {ids[-1]}")


def test_corner_inc_matches_launcher():
    """The generated corner.inc must stay byte-equal to run_corner_sweep.sh's heredoc."""
    sh = (REPO / "sim/lib/run_corner_sweep.sh").read_text()
    m = re.search(r"<<EOF\n(.*?)\nEOF\n", sh, re.S)
    check("heredoc found", m is not None)
    if not m:
        return
    template = m.group(1) + "\n"
    for process, temp, vdd in da.corners():
        expect = (
            template.replace("${LIB_SECTION[$process]}", da.LIB_SECTION[process])
            .replace("$GF180_DESIGN_INC", "/pdk/design.ngspice")
            .replace("$GF180_MODEL_FILE", "/pdk/model.ngspice")
            .replace("${temp}", str(temp))
            .replace("$temp", str(temp))
            .replace("${vdd}", vdd)
            .replace("$vdd", vdd)
            .replace("$process", process)
        )
        got = da.compose_corner_inc(process, temp, vdd, "/pdk/design.ngspice", "/pdk/model.ngspice")
        check(f"corner.inc {process} {temp} {vdd}", got == expect, f"\n{got}\n!=\n{expect}")


def test_launcher_loop_axes_match():
    sh = (REPO / "sim/lib/run_corner_sweep.sh").read_text()
    for var, axis in (("PROCESSES", da.PROCESSES), ("TEMPS", da.TEMPS), ("VDDS", da.VDDS)):
        m = re.search(rf"^{var}=\((.*?)\)", sh, re.M)
        check(f"axis {var}", m and m.group(1).split() == [str(a) for a in axis], str(m and m.group(1)))


def test_build_all_families():
    for family, (exp_dir, tb, mode) in da.FAMILIES.items():
        with tempfile.TemporaryDirectory() as td:
            req = da.build_request(family, td)
            check(f"{family} unit count", len(req["decks"]) == 27)
            check(f"{family} ids", [d["id"] for d in req["decks"]] == da.corner_ids())
            for bad in ("corners", "monte_carlo", "analysis", "measurements", "netlist"):
                check(f"{family} no corner field {bad}", bad not in req)
            src = (REPO / exp_dir / "testbench" / tb).read_bytes()
            meta = req["x_gf180_sram_adapter"]
            check(f"{family} source sha", meta["testbench_sha256"] == hashlib.sha256(src).hexdigest())
            for d in req["decks"]:
                unit = Path(td) / "units" / d["id"]
                deck = (unit / tb).read_bytes()
                check(f"{family} {d['id']} deck", deck == src.replace(b"@@REPO_ROOT@@", b"."),
                      "deck differs from source beyond the REPO_ROOT token")
                check(f"{family} corner.inc", (unit / "corner.inc").is_file())
                if b"@@REPO_ROOT@@" in src:
                    check(f"{family} DUT staged", (unit / da.DUT_NETLIST).is_file())
            first = Path(td) / "units" / da.corner_ids()[0] / tb
            check(f"{family} deck hash", meta["composed_deck_sha256"] == hashlib.sha256(first.read_bytes()).hexdigest())
            kind, datafile, _ = da.parse_mode(mode)
            has_outputs = all(d.get("outputs") == [datafile] for d in req["decks"]) if datafile else all("outputs" not in d for d in req["decks"])
            check(f"{family} outputs", has_outputs)


def test_klt_accepts_requests():
    """If klayout_tools is importable, its own deck planner must accept every request."""
    try:
        from klayout_tools import sim_decks
    except ImportError:
        print("SKIP klt planner check (klayout_tools not importable here)")
        return
    for family in da.FAMILIES:
        with tempfile.TemporaryDirectory() as td:
            req = da.build_request(family, td)
            units = sim_decks.plan_deck_units(req, request_dir=td)
            check(f"{family} planner", len(units) == 27)


def _stub_report(family, outdir, *, drop=(), dup=None, timeouts=(), stdout=None, sweep=True, exit_code=0):
    """Hand-built stub deck report + unit dirs. NOT a measurement."""
    kind, datafile, label = da.parse_mode(da.FAMILIES[family][2])
    units = []
    for cid in da.corner_ids():
        if cid in drop:
            continue
        ud = Path(outdir) / cid
        ud.mkdir(parents=True, exist_ok=True)
        text = stdout if stdout is not None else (f"RESULT: {family}_stub_s = 1.5e-09\n" if kind == "direct" else "")
        (ud / "stdout.bin").write_bytes(text.encode())
        (ud / "stderr.bin").write_bytes(b"")
        missing = []
        if kind == "snm":
            if sweep:
                # analytic symmetric VTC: 0..3.3, y = 3.3 * (1 - x/3.3)**3 (monotone, stub only)
                rows = [f"{x:.4f} {3.3 * (1 - x / 3.3) ** 3:.6f}" for x in [i * 3.3 / 40 for i in range(41)]]
                (ud / datafile).write_text("\n".join(rows) + "\n")
            else:
                missing = [datafile]
        timed = cid in timeouts
        units.append({
            "id": cid, "status": "timeout" if timed else "pass",
            "exit_code": None if timed else exit_code, "timed_out": timed,
            "stdout": f"{cid}/stdout.bin", "stderr": f"{cid}/stderr.bin",
            "outputs": [] if missing else ([datafile] if datafile else []),
            "missing_outputs": missing, "deck_sha256": "0" * 64,
        })
    if dup:
        units.append(dict(units[0], id=dup))
    return {"mode": "decks", "status": "pass", "unit_count": len(units), "units": units, "outdir": str(outdir)}


def test_reducer_direct():
    with tempfile.TemporaryDirectory() as td:
        r = da.reduce_report("write-margin", _stub_report("write-margin", td))
        check("direct recorded", r["overall"] == "recorded", json.dumps(r["coverage_errors"]))
        check("direct shape", all(set(c["results"]) == {"write-margin_stub_s".replace("write-margin", "write-margin")} for c in r["corners"]))
    with tempfile.TemporaryDirectory() as td:
        rep = _stub_report("write-margin", td, drop=("tt_25c_3.30v",))
        r = da.reduce_report("write-margin", rep)
        check("missing corner => OPEN", r["overall"] == "OPEN" and r["coverage_errors"], str(r["coverage_errors"]))
        check("missing corner reported", any(c["id"] == "tt_25c_3.30v" and c["status"] == "OPEN" for c in r["corners"]))
    with tempfile.TemporaryDirectory() as td:
        r = da.reduce_report("write-margin", _stub_report("write-margin", td, dup="ff_-40c_2.97v"))
        check("duplicate => OPEN", r["overall"] == "OPEN" and any("duplicate" in e for e in r["coverage_errors"]))
    with tempfile.TemporaryDirectory() as td:
        r = da.reduce_report("write-margin", _stub_report("write-margin", td, timeouts=("ss_125c_3.63v",)))
        bad = [c for c in r["corners"] if c["id"] == "ss_125c_3.63v"][0]
        check("timeout => OPEN", r["overall"] == "OPEN" and bad["status"] == "OPEN" and "engine timed out" in bad["reasons"])
    with tempfile.TemporaryDirectory() as td:
        # exit 0 with no RESULT line is NOT a pass
        r = da.reduce_report("write-margin", _stub_report("write-margin", td, stdout="all done\n"))
        check("exit 0 without RESULT => OPEN", r["overall"] == "OPEN")
    with tempfile.TemporaryDirectory() as td:
        r = da.reduce_report("write-margin", _stub_report("write-margin", td, stdout="RESULT-ERROR: write_trip_voltage -- x\n"))
        check("RESULT-ERROR => OPEN", r["overall"] == "OPEN")
    check("non-deck report => OPEN", da.reduce_report("write-margin", {"mode": "corners"})["overall"] == "OPEN")


def test_reducer_snm():
    with tempfile.TemporaryDirectory() as td:
        r = da.reduce_report("read-snm", _stub_report("read-snm", td))
        check("snm recorded", r["overall"] == "recorded", json.dumps(r["corners"][0]))
        keys = set(r["corners"][0]["results"]) if r["corners"] else set()
        check("snm result shape", keys == {"read_snm_lobe_low_v", "read_snm_lobe_high_v", "read_snm_v"}, str(keys))
    with tempfile.TemporaryDirectory() as td:
        r = da.reduce_report("read-snm", _stub_report("read-snm", td, sweep=False))
        c = r["corners"][0]
        check("missing sweep file => OPEN", r["overall"] == "OPEN" and c["status"] == "OPEN"
              and any("missing" in x for x in c["reasons"]), str(c["reasons"]))


def main():
    for t in (test_corner_matrix, test_corner_inc_matches_launcher, test_launcher_loop_axes_match,
              test_build_all_families, test_klt_accepts_requests, test_reducer_direct, test_reducer_snm):
        t()
    if FAILURES:
        for f in FAILURES[:10]:
            print("FAIL", f)
        print(f"{len(FAILURES)} failure(s)")
        return 1
    print("test_deck_adapter: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
