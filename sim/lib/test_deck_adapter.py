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


# --------------------------------------------------------------------------
# Monte Carlo adapter (offline contract tests; stub reports are not evidence)
# --------------------------------------------------------------------------

import run_mc_campaign as mc  # noqa: E402

MC_CORNERS = ["tt:25:3.30", "ff:125:2.97"]


def _mc_build(family, td, **kw):
    args = dict(n=3, n_control=2, n_nc=2, seed=20260817, nc_mismatch_scale=4.0, nc_vdd="2.50")
    args.update(kw)
    return da.build_mc_request(family, td, MC_CORNERS, **args)


def test_mc_seed_pins():
    """Values captured from run_mc_campaign.derive_seed; a derivation change must be loud."""
    pins = {
        (20260817, 'tt_25c_3.30v', 'mm', 0): 1945852594,
        (20260817, 'tt_25c_3.30v', 'mm-L', 1): 492608256,
        (20260817, 'tt_25c_3.30v', 'mm-R', 1): 1075919187,
        (20260817, 'ff_125c_2.97v', 'ctrl', 0): 1649341764,
        (1, 'ss_-40c_3.63v', 'nc', 7): 1104457169,
    }
    for args, v in pins.items():
        check(f"seed pin {args}", mc.derive_seed(*args) == v, str(mc.derive_seed(*args)))


def test_mc_build_identity():
    for family in da.MC_FAMILIES:
        with tempfile.TemporaryDirectory() as td:
            req = _mc_build(family, td)
            meta = req["x_gf180_sram_adapter"]
            _mode, _k = da.MC_FAMILIES[family]
            pair = _mode.startswith("snm-pair")
            per_sample = 2 if pair else 1
            per_corner = (3 + 2 + 2) * per_sample
            check(f"{family} mc unit count", len(req["decks"]) == per_corner * 2, str(len(req["decks"])))
            ids = [d["id"] for d in req["decks"]]
            check(f"{family} mc ids unique, single segment", len(set(ids)) == len(ids) and all("/" not in i for i in ids))
            for bad in ("corners", "monte_carlo", "analysis", "measurements", "netlist"):
                check(f"{family} mc no field {bad}", bad not in req)
            check(f"{family} mc timeouts", all(d["timeout_s"] == da.DECK_TIMEOUT_S for d in req["decks"]))
            for m in meta["units"]:
                k = f"{m['kind']}-{m['side']}" if m["side"] else m["kind"]
                check(f"{family} seed {m['id']}", m["seed"] == mc.derive_seed(20260817, m["corner_id"], k, m["index"]))
                inc = (Path(td) / "units" / m["id"] / "corner.inc").read_text()
                expect = mc.build_corner_inc({"GF180_MODEL_FILE": f"$PDK_ROOT/{da.MODEL_REL}"}, m["process"], m["temp"],
                                             m["vdd"], m["seed"], m["sw_stat_mismatch"])
                check(f"{family} corner.inc bytes {m['id']}", inc == expect)
                check(f"{family} seed in inc {m['id']}", f".options seed={m['seed']}\n" in inc)
            if pair:
                tt = [m for m in meta["units"] if m["corner_id"] == "tt_25c_3.30v" and m["kind"] == "mm" and m["index"] == 0]
                check(f"{family} pair two seeds", len(tt) == 2 and tt[0]["seed"] != tt[1]["seed"] and {t["side"] for t in tt} == {"L", "R"})
            nc = [m for m in meta["units"] if m["kind"] == "nc"]
            check(f"{family} nc params", all(m["sw_stat_mismatch"] == 4.0 and m["vdd"] == "2.50" for m in nc) and len(nc) == 2 * 2 * per_sample)
            ctrl = [m for m in meta["units"] if m["kind"] == "ctrl"]
            check(f"{family} ctrl mismatch off", all(m["sw_stat_mismatch"] == 0 for m in ctrl))
            # nc seeds still derive from the corner's own id, not the nc supply
            check(f"{family} nc seed corner id", all(m["corner_id"] in ("tt_25c_3.30v", "ff_125c_2.97v") for m in nc))
            src = (REPO / da.FAMILIES[family][0] / "testbench" / da.FAMILIES[family][1]).read_bytes()
            u0 = Path(td) / "units" / ids[0] / da.FAMILIES[family][1]
            check(f"{family} mc deck bytes", u0.read_bytes() == src.replace(b"@@REPO_ROOT@@", b"."))


def test_mc_n1_and_guard():
    with tempfile.TemporaryDirectory() as td:
        req = _mc_build("write-margin", td, n=1, n_control=0, n_nc=0)
        check("n=1 count", len(req["decks"]) == 2)
    with tempfile.TemporaryDirectory() as td:
        try:
            da.build_mc_request("write-margin", td, ["tt:25:3.30"], n=1, n_control=0, n_nc=0, seed=1)
            check("single corner refused", False)
        except ValueError:
            pass


def _mc_stub(family, request, outdir, *, drop=(), dup=None, timeouts=(), nostdout=(), nodata=()):
    """Hand-built stub deck report. NOT a measurement."""
    kind, datafile, label = da.parse_mc_mode(da.MC_FAMILIES[family][0])
    key = da.MC_FAMILIES[family][1]
    units = []
    for m in request["x_gf180_sram_adapter"]["units"]:
        uid = m["id"]
        if uid in drop:
            continue
        ud = Path(outdir) / uid
        ud.mkdir(parents=True, exist_ok=True)
        text = "" if (kind != "direct" or uid in nostdout) else f"RESULT: {key} = {0.1 + m['seed'] % 1000 / 10000.0}\n"
        (ud / "stdout.bin").write_bytes(text.encode())
        (ud / "stderr.bin").write_bytes(b"")
        missing = []
        if kind != "direct":
            if uid in nodata:
                missing = [datafile]
            else:
                rows = [f"{x:.4f} {3.3 * (1 - x / 3.3) ** 3:.6f}" for x in [i * 3.3 / 40 for i in range(41)]]
                (ud / datafile).write_text("\n".join(rows) + "\n")
        timed = uid in timeouts
        units.append({"id": uid, "status": "timeout" if timed else "pass", "exit_code": None if timed else 0,
                      "timed_out": timed, "stdout": f"{uid}/stdout.bin", "stderr": f"{uid}/stderr.bin",
                      "missing_outputs": missing, "deck_sha256": "0" * 64})
    if dup:
        units.append(dict(units[0], id=dup))
    return {"mode": "decks", "status": "pass", "unit_count": len(units), "units": units, "outdir": str(outdir)}


def test_mc_reduce_shapes():
    for family in ("write-margin", "read-snm"):
        with tempfile.TemporaryDirectory() as bd, tempfile.TemporaryDirectory() as rd:
            req = _mc_build(family, bd)
            r = da.reduce_mc_report(family, req, _mc_stub(family, req, rd), outdir=rd)
            check(f"{family} mc recorded", r["overall"] == "recorded", json.dumps(r["coverage_errors"] + r["infra_failures"])[:300])
            b = r["batches"]["tt_25c_3.30v"]
            check(f"{family} kinds", set(b) == {"mm", "ctrl", "nc"})
            check(f"{family} sample counts", [len(b[k]["samples"]) for k in ("mm", "ctrl", "nc")] == [3, 2, 2])
            check(f"{family} seed order", [s[0] for s in b["mm"]["samples"]] == [0, 1, 2])
            m0 = [m for m in req["x_gf180_sram_adapter"]["units"] if m["id"] == da.mc_unit_id("tt_25c_3.30v", "mm", 0, "L" if family == "read-snm" else None)][0]
            want = f"L={m0['seed']}" if family == "read-snm" else str(m0["seed"])
            check(f"{family} seed label", b["mm"]["seed_labels"][0].startswith(want), b["mm"]["seed_labels"][0])
            meas = {m["name"]: m for m in r["measurements"]}
            key = da.MC_FAMILIES[family][1]
            mm = meas[f"{key}@tt_25c_3.30v"]
            check(f"{family} measurement shape", set(mm) >= {"name", "unit", "samples", "errored", "limits", "source_corners", "negative_control"})
            check(f"{family} measurement counts", len(mm["samples"]) + mm["errored"] == 3)
            check(f"{family} nc block", set(mm["negative_control"]) == {"samples", "errored", "description"})
    with tempfile.TemporaryDirectory() as bd, tempfile.TemporaryDirectory() as rd:
        req = _mc_build("write-margin", bd)
        r = da.reduce_mc_report("write-margin", req, _mc_stub("write-margin", req, rd), outdir=rd)
        vals = r["batches"]["tt_25c_3.30v"]["mm"]["samples"][0][1]
        check("direct results shape", set(vals) == {"write_trip_voltage_v"} and isinstance(vals["write_trip_voltage_v"], float))


def test_mc_reduce_fails_closed():
    fam = "write-margin"
    with tempfile.TemporaryDirectory() as bd:
        req = _mc_build(fam, bd)
    first = req["x_gf180_sram_adapter"]["units"][0]["id"]
    cases = {
        "missing unit": dict(drop=(first,)),
        "duplicate id": dict(dup=first),
        "timeout": dict(timeouts=(first,)),
        "exit 0 without RESULT": dict(nostdout=(first,)),
    }
    for name, kw in cases.items():
        with tempfile.TemporaryDirectory() as rd:
            r = da.reduce_mc_report(fam, req, _mc_stub(fam, req, rd, **kw), outdir=rd)
            check(f"mc {name} => OPEN", r["overall"] == "OPEN", name)
    with tempfile.TemporaryDirectory() as rd:
        rep = _mc_stub(fam, req, rd)
        rep["units"].append(dict(rep["units"][0], id="mc.bogus"))
        r = da.reduce_mc_report(fam, req, rep, outdir=rd)
        check("mc unexpected id => OPEN", r["overall"] == "OPEN" and any("unexpected" in e for e in r["coverage_errors"]))
    with tempfile.TemporaryDirectory() as rd:
        check("mc non-deck report => OPEN", da.reduce_mc_report(fam, req, {"mode": "corners"})["overall"] == "OPEN")
    with tempfile.TemporaryDirectory() as bd, tempfile.TemporaryDirectory() as rd:
        sreq = _mc_build("read-snm", bd)
        sid = sreq["x_gf180_sram_adapter"]["units"][1]["id"]
        r = da.reduce_mc_report("read-snm", sreq, _mc_stub("read-snm", sreq, rd, nodata=(sid,)), outdir=rd)
        check("mc absent declared output => OPEN", r["overall"] == "OPEN" and r["infra_failures"])
    with tempfile.TemporaryDirectory() as rd:
        tampered = json.loads(json.dumps(req))
        tampered["x_gf180_sram_adapter"]["units"][0]["seed"] += 1
        r = da.reduce_mc_report(fam, tampered, _mc_stub(fam, tampered, rd), outdir=rd)
        check("mc seed drift => OPEN", r["overall"] == "OPEN" and any("seed drift" in e for e in r["coverage_errors"]))


def main():
    for t in (test_corner_matrix, test_corner_inc_matches_launcher, test_launcher_loop_axes_match,
              test_build_all_families, test_klt_accepts_requests, test_reducer_direct, test_reducer_snm,
              test_mc_seed_pins, test_mc_build_identity, test_mc_n1_and_guard,
              test_mc_reduce_shapes, test_mc_reduce_fails_closed):
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
