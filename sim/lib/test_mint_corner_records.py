#!/usr/bin/env python3
"""Offline contract tests for sim/lib/mint_corner_records.py (#437).

No ngspice, no PDK, no fleet. The graded reports below are hand-built STUBS
fed through the real `deck_adapter.py reduce` grading; nothing here is
physical evidence and no stub value may be quoted as a measurement. What is
under test is the minting CONTRACT: record format, append-only refusals,
fail-closed coverage rules, report-declared stream-path resolution (#444),
and that `compare_records.py` consumes the minted output unchanged.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deck_adapter as da  # noqa: E402
import mint_corner_records as mcr  # noqa: E402

REPO = da.REPO_ROOT
FAILURES = []


def check(name, cond, detail=""):
    if not cond:
        FAILURES.append(f"{name}: {detail}")


SCH_KEY = "pex-write-margin-schematic"
EXT_KEY = "pex-write-margin-extracted"


def _graded(family, request, values, *, drop=(), open_corners=(), stream_decl="declared"):
    """Stub deck report -> real reduce grading. NOT a measurement.

    `values` maps corner id -> the write_trip_voltage_v stub; corners in
    `drop` are missing from the report entirely (a coverage error); corners
    in `open_corners` produce no RESULT line (grade OPEN). `stream_decl`
    picks the unit stream layout (#444): "declared" (default) declares
    `<cid>/stdout.bin`-shaped paths, "units" declares a non-default
    `units/<cid>/out.bin` layout, "omitted" writes the default layout with
    no `stdout`/`stderr` fields (exercising the fallback). The returned
    dict carries `_stub_report_outdir` (the unit dir to pass as `unit_dir`)
    and `_stub_report` (the report to pass as `report`) -- which no real
    reduce output ever has."""
    ids = [c for c in request["x_gf180_sram_adapter"]["corners"] if c not in drop]
    outdir = Path(tempfile.mkdtemp(prefix="mint-units-"))
    units = []
    for cid in ids:
        if stream_decl == "units":
            stdout_rel, stderr_rel = f"units/{cid}/out.bin", f"units/{cid}/err.bin"
        else:
            stdout_rel, stderr_rel = f"{cid}/stdout.bin", f"{cid}/stderr.bin"
        text = "" if cid in open_corners else (
            f"RESULT: write_trip_voltage_v = {values[cid]}\nRESULT: write_vdd_v = 3.3\n"
        )
        (outdir / stdout_rel).parent.mkdir(parents=True, exist_ok=True)
        (outdir / stdout_rel).write_bytes(text.encode())
        (outdir / stderr_rel).write_bytes(b"")
        unit = {"id": cid, "status": "pass", "exit_code": 0, "timed_out": False,
                "missing_outputs": [],
                "deck_sha256": request["x_gf180_sram_adapter"]["composed_deck_sha256"]}
        if stream_decl != "omitted":
            unit["stdout"], unit["stderr"] = stdout_rel, stderr_rel
        units.append(unit)
    report = {"mode": "decks", "status": "pass", "unit_count": len(units), "units": units,
              "outdir": str(outdir)}
    exp_ids, exp_sha = da.expected_from_request(family, request)
    reduced = da.reduce_report(family, report, outdir=outdir,
                               expected_ids=exp_ids, expected_deck_sha256=exp_sha)
    reduced["_stub_report_outdir"] = str(outdir)
    reduced["_stub_report"] = report
    return reduced


def _seed_exp_dir(td, family):
    """A minimal experiment dir carrying the family's real testbench."""
    exp_dir, tb, _mode, _staged = da.FAMILIES[family]
    (Path(td) / "testbench").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / exp_dir / "testbench" / tb, Path(td) / "testbench" / tb)


def _tb_bytes(family):
    exp_dir, tb, _m, _s = da.FAMILIES[family]
    return (REPO / exp_dir / "testbench" / tb).read_bytes()


def test_mint_recorded():
    """A fully-recorded full-grid grading mints the launcher-format record."""
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ud:
        req = da.build_request(SCH_KEY, ud)
        values = {c: 1.0 for c in req["x_gf180_sram_adapter"]["corners"]}
        reduced = _graded(SCH_KEY, req, values)
        exp = Path(td)
        _seed_exp_dir(td, SCH_KEY)
        rid = "20261117-120000-deadbee"
        md = mcr.mint_record(SCH_KEY, reduced, req, report=reduced["_stub_report"],
                             unit_dir=Path(reduced["_stub_report_outdir"]),
                             exp_dir=exp, record_id=rid, claim="test claim",
                             timestamp="2026-11-17T12:00:00Z")
        text = md.read_text()
        for needle in (
            f"# Record {rid}",
            f"- **Record ID**: {rid}",
            "- **Claim**: test claim",
            "- **Timestamp / author**: 2026-11-17T12:00:00Z, agent-builder",
            "- **Supersedes**: (none -- first record for this claim)",
            "  - **Overall: recorded**",
            "- **Netlist provenance**: schematic (`testbench/tb_write_margin_schematic.spice`, "
            "DUT per `sim/pex/access-time/dut/bitcell_6t_subckt.spice` at ",
            f"  - Netlist snapshot: `netlist-snapshots/{rid}.spice`",
            f"  - Raw logs: `corners/{rid}/`",
        ):
            check(f"record contains {needle[:60]}", needle in text, f"missing from:\n{text[:900]}")
        # every corner row carries the launcher's grep|tr RESULT-joined shape
        row = [ln for ln in text.splitlines() if ln.startswith("  - **tt_25c_3.30v**:")]
        check("recorded row shape",
              row and row[0] == "  - **tt_25c_3.30v**: RESULT: write_trip_voltage_v = 1.0;RESULT: write_vdd_v = 3.3;",
              str(row))
        check("27 corner rows",
              sum(1 for ln in text.splitlines()
                  if ln.startswith("  - **") and "Overall" not in ln) == 27)
        # corner log: raw streams + launcher trailer
        log = (exp / "corners" / rid / "tt_25c_3.30v.log").read_text()
        check("log has RESULT", "RESULT: write_trip_voltage_v = 1.0" in log, log[-200:])
        check("log trailer corner",
              "=== corner: tt_25c_3.30v (process=tt temp=25C vdd=3.30V) ===" in log, log[-200:])
        check("log trailer exit", "=== ngspice exit status: 0 ===" in log, log[-200:])
        # snapshot is the raw testbench, @@REPO_ROOT@@ intact
        snap = (exp / "netlist-snapshots" / f"{rid}.spice").read_bytes()
        check("snapshot raw testbench", snap == _tb_bytes(SCH_KEY), "snapshot != source testbench")
        # parseable by the shared record parser (render_signoff_table)
        sys.path.insert(0, str(REPO / "sim" / "lib"))
        import render_signoff_table as signoff
        parsed = signoff.parse_record(md)
        check("parse_record sees 27 corners", len(parsed) == 27, str(len(parsed)))
        check("parse_record value",
              parsed["tt_25c_3.30v"]["write_trip_voltage_v"] == 1.0, str(parsed.get("tt_25c_3.30v")))


def test_mint_refusals():
    """Every fail-closed rule refuses with an error, writing nothing."""
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ud:
        req = da.build_request(SCH_KEY, ud)
        values = {c: 1.0 for c in req["x_gf180_sram_adapter"]["corners"]}
        good = _graded(SCH_KEY, req, values)
        exp = Path(td)
        _seed_exp_dir(td, SCH_KEY)
        rid = "20261117-120000-deadbee"

        def mint(**kw):
            args = dict(family=SCH_KEY, request=req, report=good["_stub_report"],
                        exp_dir=exp, record_id=rid, claim="c")
            args.update(kw)
            return mcr.mint_record(**args)

        # bounded request (a parity run) never mints
        with tempfile.TemporaryDirectory() as ud2:
            bounded = da.build_request(SCH_KEY, ud2, corner_specs=["tt:25:3.30"])
            try:
                mint(request=bounded, reduced={}, unit_dir=Path("/x"))
                check("bounded refused", False, "minted from a bounded request")
            except ValueError as ve:
                check("bounded refused", "full-grid" in str(ve), str(ve))
        # coverage errors
        broken = _graded(SCH_KEY, req, values, drop=("tt_25c_3.30v",))
        try:
            mint(reduced=broken, unit_dir=Path("/x"))
            check("coverage errors refused", False)
        except ValueError as ve:
            check("coverage errors refused", "coverage errors" in str(ve), str(ve))
        # a grading that is not the full grid: real bounded gradings carry a
        # subset `expected` (reduce --request pins coverage to the corners
        # the request asked for), and a subset never mints a record that
        # claims the full ratified matrix
        one_corner = dict(good, expected=good["expected"][:1])
        try:
            mint(reduced=one_corner, unit_dir=Path("/x"))
            check("partial grid refused", False)
        except ValueError as ve:
            check("partial grid refused", "full ratified corner grid" in str(ve), str(ve))
        # missing raw log for a recorded corner
        try:
            mint(reduced=good, unit_dir=Path("/nonexistent"))
            check("missing raw log refused", False)
        except ValueError as ve:
            check("missing raw log refused", "stdout.bin missing" in str(ve), str(ve))
        # request for another family
        with tempfile.TemporaryDirectory() as ud3:
            other = da.build_request(EXT_KEY, ud3)
            try:
                mint(reduced=good, request=other, unit_dir=Path("/x"))
                check("family mismatch refused", False)
            except ValueError as ve:
                check("family mismatch refused", "family" in str(ve), str(ve))
        # MC request
        with tempfile.TemporaryDirectory() as ud4:
            mc = da.build_mc_request("write-margin", ud4, ["tt:25:3.30", "ff:125:2.97"],
                                     n=2, n_control=1, n_nc=1, seed=1)
            try:
                mint(reduced=good, request=mc, unit_dir=Path("/x"))
                check("MC request refused", False)
            except ValueError as ve:
                check("MC request refused", "Monte Carlo" in str(ve), str(ve))
        # reduced report for another family
        try:
            mint(reduced=dict(good, family=EXT_KEY), unit_dir=Path("/x"))
            check("reduced family mismatch refused", False)
        except ValueError as ve:
            check("reduced family mismatch refused", "family" in str(ve), str(ve))
        # snm family (non-direct mode)
        try:
            mint(family="read-snm", reduced=good, unit_dir=Path("/x"))
            check("snm family refused", False)
        except ValueError as ve:
            check("snm family refused", "direct-mode" in str(ve), str(ve))
        # missing testbench under the exp dir
        empty = Path(str(td) + "-empty")
        empty.mkdir()
        try:
            mint(reduced=good, exp_dir=empty, unit_dir=Path("/x"))
            check("missing testbench refused", False)
        except FileNotFoundError as fe:
            check("missing testbench refused", "testbench" in str(fe), str(fe))
        # wrong testbench bytes under the exp dir
        wrong = Path(str(td) + "-wrong")
        (wrong / "testbench").mkdir(parents=True)
        (wrong / "testbench" / da.FAMILIES[SCH_KEY][1]).write_bytes(b"* different\n.end\n")
        try:
            mint(reduced=good, exp_dir=wrong, unit_dir=Path("/x"))
            check("wrong testbench refused", False)
        except ValueError as ve:
            check("wrong testbench refused", "differs" in str(ve), str(ve))
        # report that is not a deck-list report
        try:
            mint(reduced=good, report={"mode": "engines", "units": []}, unit_dir=Path("/x"))
            check("non-decks report refused", False)
        except ValueError as ve:
            check("non-decks report refused", "deck-list report" in str(ve), str(ve))
        # a recorded corner with no unit in the report (grading/report mismatch)
        first_cid = good["corners"][0]["id"]
        stripped = dict(good["_stub_report"],
                        units=[u for u in good["_stub_report"]["units"] if u["id"] != first_cid])
        try:
            mint(reduced=good, report=stripped, unit_dir=Path(good["_stub_report_outdir"]))
            check("report missing recorded unit refused", False)
        except ValueError as ve:
            check("report missing recorded unit refused", "no unit in the report" in str(ve), str(ve))
        # nothing was written under the seeded exp dir
        check("refusals wrote nothing",
              sorted(p.name for p in exp.iterdir()) == ["testbench"],
              str(sorted(p.name for p in exp.iterdir())))


def test_mint_open_and_append_only():
    """An OPEN corner mints honestly (Overall: OPEN, row says OPEN); a
    second mint for the same record id refuses -- append-only."""
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ud:
        req = da.build_request(EXT_KEY, ud)
        values = {c: 2.0 for c in req["x_gf180_sram_adapter"]["corners"]}
        reduced = _graded(EXT_KEY, req, values, open_corners=("tt_25c_3.30v",))
        exp = Path(td)
        _seed_exp_dir(td, EXT_KEY)
        rid = "20261117-120001-deadbee"
        md = mcr.mint_record(EXT_KEY, reduced, req, report=reduced["_stub_report"],
                             unit_dir=Path(reduced["_stub_report_outdir"]),
                             exp_dir=exp, record_id=rid, claim="c",
                             supersedes="20260822-093435-fc6ce30 (testbench changed)",
                             timestamp="2026-11-17T12:00:01Z")
        text = md.read_text()
        check("open overall", "  - **Overall: OPEN**" in text, text[-400:])
        row = [ln for ln in text.splitlines() if ln.startswith("  - **tt_25c_3.30v**:")]
        check("open row shape", row and row[0].startswith("  - **tt_25c_3.30v**: OPEN -- no RESULT line captured"),
              str(row))
        check("extracted provenance word",
              "- **Netlist provenance**: extracted (`testbench/tb_write_margin_extracted.spice`, "
              "DUT per `sim/pex/write-margin/dut/extracted-netlist.spice` at " in text, text[:700])
        check("supersedes recorded",
              "- **Supersedes**: 20260822-093435-fc6ce30 (testbench changed)" in text)
        # parse_record treats the open corner as OPEN
        sys.path.insert(0, str(REPO / "sim" / "lib"))
        import render_signoff_table as signoff
        parsed = signoff.parse_record(md)
        check("parse_record OPEN", parsed["tt_25c_3.30v"] == "OPEN", str(parsed.get("tt_25c_3.30v")))
        # append-only: same id again refuses, and the first artifacts survive
        before = {p: p.read_bytes() for p in exp.rglob("*") if p.is_file()}
        try:
            mcr.mint_record(EXT_KEY, reduced, req, report=reduced["_stub_report"],
                            unit_dir=Path(reduced["_stub_report_outdir"]),
                            exp_dir=exp, record_id=rid, claim="c")
            check("append-only refused", False)
        except ValueError as ve:
            check("append-only refused", "already exists" in str(ve), str(ve))
        after = {p: p.read_bytes() for p in exp.rglob("*") if p.is_file()}
        check("append-only artifacts intact", before == after)


def test_compare_records_consumes_minted():
    """The real compare_records.py consumes two minted records unchanged and
    produces the same delta shape it always did (#437 criterion)."""
    sys.path.insert(0, str(REPO / "sim" / "pex" / "write-margin"))
    import compare_records as cr

    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ud:
        exp = Path(td)
        _seed_exp_dir(td, SCH_KEY)
        _seed_exp_dir(td, EXT_KEY)
        sch_req = da.build_request(SCH_KEY, ud)
        ext_req = da.build_request(EXT_KEY, str(ud) + "-ext")
        sch_vals = {c: 1.0 + i * 0.001 for i, c in enumerate(sch_req["x_gf180_sram_adapter"]["corners"])}
        ext_vals = {c: v * 1.05 for c, v in sch_vals.items()}
        sch = _graded(SCH_KEY, sch_req, sch_vals)
        ext = _graded(EXT_KEY, ext_req, ext_vals)
        sch_id, ext_id = "20261117-120100-deadbee", "20261117-120101-deadbee"
        mcr.mint_record(SCH_KEY, sch, sch_req, report=sch["_stub_report"],
                        unit_dir=Path(sch["_stub_report_outdir"]),
                        exp_dir=exp, record_id=sch_id, claim="c", timestamp="2026-11-17T12:01:00Z")
        mcr.mint_record(EXT_KEY, ext, ext_req, report=ext["_stub_report"],
                        unit_dir=Path(ext["_stub_report_outdir"]),
                        exp_dir=exp, record_id=ext_id, claim="c", timestamp="2026-11-17T12:01:01Z")
        old_exp = cr.EXPERIMENT_DIR
        cr.EXPERIMENT_DIR = exp
        delta_path = exp / "delta" / f"{sch_id}_vs_{ext_id}.md"
        try:
            try:
                rc = cr.main(["compare_records.py", sch_id, ext_id])
                check("compare exit 0", rc == 0, str(rc))
            except ValueError:
                # compare_records' summary print resolves the delta path
                # against the repo ROOT; an offline exp dir outside the repo
                # cannot be. The delta file itself is already written -- in
                # production EXPERIMENT_DIR always lives under ROOT and the
                # script runs clean (this test redirects it; the script does
                # not change).
                check("compare exit 0", delta_path.is_file(), "delta not written")
        finally:
            cr.EXPERIMENT_DIR = old_exp
        delta = delta_path.read_text()
        check("delta header",
              f"# Write-margin by-hand PEX delta: {sch_id} (schematic) vs {ext_id} (extracted)" in delta)
        check("delta non-vacuous",
              "All 27 corners produced a paired schematic/extracted value" in delta, delta[-400:])
        check("delta all 27 pass, none errored",
              delta.count("| pass |") == 27 and "| error |" not in delta,
              f"{delta.count('| pass |')} pass rows")
        # spot-check one row: the stub ext value is exactly +5%
        cid = "tt_25c_3.30v"
        sch_v, ext_v = sch_vals[cid], ext_vals[cid]
        want_pct = 100.0 * (ext_v - sch_v) / abs(sch_v)
        row = [ln for ln in delta.splitlines() if ln.startswith(f"| {cid}")]
        check("delta row values",
              row and row[0] == f"| {cid} | {sch_v:.5f} | {ext_v:.5f} | {want_pct:.3f} | pass |",
              str(row))


def test_mint_declared_stream_paths():
    """The minter takes a unit's raw streams from the report's declared
    `units[].stdout`/`.stderr` paths -- a non-default layout included --
    falls back to `<cid>/stdout.bin` when the fields are omitted, and
    refuses fail-closed when a declared path is missing on disk (#444)."""
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ud:
        req = da.build_request(SCH_KEY, ud)
        values = {c: 1.0 for c in req["x_gf180_sram_adapter"]["corners"]}
        exp = Path(td)
        _seed_exp_dir(td, SCH_KEY)

        # non-default declared layout: units/<cid>/out.bin + err.bin, nothing
        # at the default layout -- the mint can only succeed via the
        # declaration (the old hardcoded minter refused here)
        declared = _graded(SCH_KEY, req, values, stream_decl="units")
        outdir = Path(declared["_stub_report_outdir"])
        check("declared stub has no default-layout files",
              not (outdir / "tt_25c_3.30v").exists())
        rid = "20261117-120200-deadbee"
        mcr.mint_record(SCH_KEY, declared, req, report=declared["_stub_report"],
                        unit_dir=outdir, exp_dir=exp, record_id=rid, claim="c",
                        timestamp="2026-11-17T12:02:00Z")
        log = (exp / "corners" / rid / "tt_25c_3.30v.log").read_text()
        check("declared layout streams minted",
              "RESULT: write_trip_voltage_v = 1.0" in log, log[:300])

        # omitted stream fields: the default <cid>/stdout.bin layout is the
        # fallback, and the mint still finds the streams
        omitted = _graded(SCH_KEY, req, values, stream_decl="omitted")
        check("omitted stub declares no stream fields",
              "stdout" not in omitted["_stub_report"]["units"][0])
        rid2 = "20261117-120201-deadbee"
        mcr.mint_record(SCH_KEY, omitted, req, report=omitted["_stub_report"],
                        unit_dir=Path(omitted["_stub_report_outdir"]), exp_dir=exp,
                        record_id=rid2, claim="c", timestamp="2026-11-17T12:02:01Z")
        log2 = (exp / "corners" / rid2 / "tt_25c_3.30v.log").read_text()
        check("fallback layout streams minted",
              "RESULT: write_trip_voltage_v = 1.0" in log2, log2[:300])

        # a declared path missing on disk refuses, fail-closed, writing nothing
        holed = _graded(SCH_KEY, req, values, stream_decl="units")
        (Path(holed["_stub_report_outdir"]) / "units" / "tt_25c_3.30v" / "out.bin").unlink()
        before = sorted(p.name for p in exp.iterdir())
        try:
            mcr.mint_record(SCH_KEY, holed, req, report=holed["_stub_report"],
                            unit_dir=Path(holed["_stub_report_outdir"]), exp_dir=exp,
                            record_id="20261117-120202-deadbee", claim="c")
            check("declared path missing refused", False)
        except ValueError as ve:
            check("declared path missing refused",
                  "raw units/tt_25c_3.30v/out.bin missing for recorded corner tt_25c_3.30v"
                  in str(ve),
                  str(ve))
        check("refused mint wrote nothing",
              sorted(p.name for p in exp.iterdir()) == before)


def test_mint_refuses_escaping_stream_path():
    """A report-declared stream path that is absolute or traverses out of
    the unit dir never reaches the minted evidence: the minter refuses
    fail-closed, writing nothing (#448)."""
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ud:
        req = da.build_request(SCH_KEY, ud)
        values = {c: 1.0 for c in req["x_gf180_sram_adapter"]["corners"]}
        reduced = _graded(SCH_KEY, req, values)
        exp = Path(td)
        _seed_exp_dir(td, SCH_KEY)
        outside = Path(tempfile.mkdtemp(prefix="outside-outdir-"))
        try:
            (outside / "secret.log").write_bytes(b"RESULT: write_trip_voltage_v = 9.9\n")
            outdir = reduced["_stub_report_outdir"]
            for name, bad in (
                ("absolute (passwd-style)", str(outside / "secret.log")),
                ("upward traversal", os.path.relpath(outside / "secret.log", outdir)),
            ):
                rep = json.loads(json.dumps(reduced["_stub_report"]))
                rep["units"][0]["stdout"] = bad
                cid0 = rep["units"][0]["id"]
                before = sorted(p.name for p in exp.iterdir())
                try:
                    mcr.mint_record(SCH_KEY, reduced, req, report=rep,
                                    unit_dir=Path(outdir), exp_dir=exp,
                                    record_id="20261117-120300-deadbee", claim="c")
                    check(f"{name} refused", False)
                except ValueError as ve:
                    check(f"{name} refused",
                          cid0 in str(ve) and bad in str(ve) and "outdir" in str(ve), str(ve))
                check(f"{name} wrote nothing",
                      sorted(p.name for p in exp.iterdir()) == before)
        finally:
            shutil.rmtree(outside)


def main():
    for t in (test_mint_recorded, test_mint_refusals, test_mint_open_and_append_only,
              test_mint_declared_stream_paths, test_mint_refuses_escaping_stream_path,
              test_compare_records_consumes_minted):
        t()
    if FAILURES:
        for f in FAILURES[:10]:
            print("FAIL", f)
        print(f"{len(FAILURES)} failure(s)")
        return 1
    print("test_mint_corner_records: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
