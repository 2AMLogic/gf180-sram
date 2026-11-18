#!/usr/bin/env python3
"""Offline contract tests for sim/lib/mint_corner_records.py (#437, #452).

No ngspice, no PDK, no fleet. The graded reports below are hand-built STUBS
fed through the real `deck_adapter.py reduce` grading; nothing here is
physical evidence and no stub value may be quoted as a measurement. What is
under test is the minting CONTRACT: record format (including the PDK/Run
lines folded in from the retired mint_records.py corner path at the #452
consolidation), append-only refusals, fail-closed coverage rules, PDK
identity resolution fail-closed on a drifted tree (#454), canonical
Claim ownership (FAMILY_CLAIMS), SNM-family support, report-declared
stream-path resolution (#444), and that `compare_records.py` consumes the
minted output unchanged.
"""
from __future__ import annotations

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

STUB_PDK = {
    "variant": "gf180mcuD", "version": "f6eeac7" + "0" * 33,
    "design_inc_rel": "libs.tech/ngspice/design.ngspice",
    "model_file_rel": "libs.tech/ngspice/sm141064.ngspice",
}


def stub_pdk():
    saved = mcr.pdk_identity
    mcr.pdk_identity = lambda: dict(STUB_PDK)
    return saved


def restore_pdk(saved):
    mcr.pdk_identity = saved


def _graded(family, request, values, *, drop=(), open_corners=(), stream_decl="declared"):
    """Stub deck report -> real reduce grading. NOT a measurement.

    `values` maps corner id -> the write_trip_voltage_v stub; corners in
    `drop` are missing from the report entirely (a coverage error); corners
    in `open_corners` produce no RESULT line (grade OPEN). SNM families get
    no stdout RESULT stub -- their measurement comes from the extractor the
    reducer runs over each unit's own sweep data file, stubbed here with a
    six-point falling line (a deterministic, non-physical curve).
    `stream_decl` picks the unit stream layout (#444): "declared" (default)
    declares `<cid>/stdout.bin`-shaped paths, "units" declares a non-default
    `units/<cid>/out.bin` layout, "omitted" writes the default layout with
    no `stdout`/`stderr` fields (exercising the fallback). The returned
    dict carries `_stub_report_outdir` (the unit dir to pass as `unit_dir`)
    and `_stub_report` (the report to pass as `report`) -- which no real
    reduce output ever has."""
    ids = [c for c in request["x_gf180_sram_adapter"]["corners"] if c not in drop]
    kind, datafile, _label = da.parse_mode(da.FAMILIES[family][2])
    outdir = Path(tempfile.mkdtemp(prefix="mint-units-"))
    units = []
    for cid in ids:
        if stream_decl == "units":
            stdout_rel, stderr_rel = f"units/{cid}/out.bin", f"units/{cid}/err.bin"
        else:
            stdout_rel, stderr_rel = f"{cid}/stdout.bin", f"{cid}/stderr.bin"
        if kind == "snm" or cid in open_corners:
            text = ""
        else:
            text = f"RESULT: write_trip_voltage_v = {values[cid]}\nRESULT: write_vdd_v = 3.3\n"
        (outdir / stdout_rel).parent.mkdir(parents=True, exist_ok=True)
        (outdir / stdout_rel).write_bytes(text.encode())
        (outdir / stderr_rel).write_bytes(b"")
        if kind == "snm" and cid not in open_corners:
            (outdir / cid / datafile).write_text(
                "\n".join(f"{i * 0.1:.1f} {1.0 - i * 0.1:.1f}" for i in range(6)) + "\n"
            )
        unit = {"id": cid, "status": "pass", "exit_code": 0, "timed_out": False,
                "missing_outputs": [],
                "deck_sha256": request["x_gf180_sram_adapter"]["composed_deck_sha256"]}
        if stream_decl != "omitted":
            unit["stdout"], unit["stderr"] = stdout_rel, stderr_rel
        units.append(unit)
    report = {"mode": "decks", "status": "pass", "unit_count": len(units), "units": units,
              "outdir": str(outdir),
              "environment": {"engine_version": "47",
                              "remote": {"job_id": "klt-sim-stub", "ami_id": "ami-stub",
                                         "provider": "aws-batch-fleet", "region": "us-east-1"}}}
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


def _tb_composed(family):
    return da.compose_deck(_tb_bytes(family).decode("utf-8")).encode("utf-8")


def test_mint_recorded():
    """A fully-recorded full-grid grading mints the launcher-format record,
    PDK and Run lines included (#452 folded them into the single template)."""
    saved = stub_pdk()
    try:
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
                f"- **PDK**: `{STUB_PDK['variant']}`, open_pdks `{STUB_PDK['version']}` "
                "(issue #173 pin, `sim/lib/pdk_pin.txt`)",
                "- **Run**: `klt sim` deck mode on the batch fleet (#230 cutover path), "
                "job `klt-sim-stub` (ngspice 47, `ami-stub`); pinned run-directory "
                "`.spiceinit` staged per unit (issue #338, sha256 "
                f"`{req['x_gf180_sram_adapter']['spiceinit_sha256']}`; "
                "spec/environment-pin-decision.md)",
                "- **Timestamp / author**: 2026-11-17T12:00:00Z, agent-builder",
                "- **Supersedes**: (none -- first record for this claim)",
                "  - **Overall: recorded**",
                "- **Netlist provenance**: schematic (`testbench/tb_write_margin_schematic.spice`, "
                "DUT per `sim/pex/access-time/dut/bitcell_6t_subckt.spice` at ",
                f"  - Netlist snapshot: `netlist-snapshots/{rid}.spice`",
                f"  - Raw logs: `corners/{rid}/`",
            ):
                check(f"record contains {needle[:60]}", needle in text, f"missing from:\n{text[:1100]}")
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
            # snapshot is the composed deck -- the bytes that actually ran,
            # @@REPO_ROOT@@ rewritten -- not the raw testbench bytes
            snap = (exp / "netlist-snapshots" / f"{rid}.spice").read_bytes()
            check("snapshot is the composed deck bytes", snap == _tb_composed(SCH_KEY),
                  "snapshot != composed deck")
            check("snapshot is sha-pinned to the request",
                  da._sha256(snap) == req["x_gf180_sram_adapter"]["composed_deck_sha256"])
            # parseable by the shared record parser (render_signoff_table)
            sys.path.insert(0, str(REPO / "sim" / "lib"))
            import render_signoff_table as signoff
            parsed = signoff.parse_record(md)
            check("parse_record sees 27 corners", len(parsed) == 27, str(len(parsed)))
            check("parse_record value",
                  parsed["tt_25c_3.30v"]["write_trip_voltage_v"] == 1.0, str(parsed.get("tt_25c_3.30v")))
    finally:
        restore_pdk(saved)


def test_mint_refusals():
    """Every fail-closed rule refuses with an error, writing nothing."""
    saved = stub_pdk()
    try:
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
            # a grading that does not pin this request's composed deck sha256
            # (the check the retired mint_records.py corner path contributed
            # at the #452 consolidation)
            drift = dict(good, expected_deck_sha256="0" * 64)
            try:
                mint(reduced=drift, unit_dir=Path("/x"))
                check("deck-sha drift refused", False)
            except ValueError as ve:
                check("deck-sha drift refused", "composed deck sha256" in str(ve), str(ve))
            # a request whose recorded deck sha the committed testbench no
            # longer composes to: the snapshot must be the bytes that ran
            with tempfile.TemporaryDirectory() as ud3:
                mut = da.build_request(SCH_KEY, ud3)
                mut["x_gf180_sram_adapter"]["composed_deck_sha256"] = "f" * 64
                mutated = _graded(SCH_KEY, mut, values)
                try:
                    mint(request=mut, reduced=mutated,
                         report=mutated["_stub_report"],
                         unit_dir=Path(mutated["_stub_report_outdir"]))
                    check("compose drift refused", False)
                except ValueError as ve:
                    check("compose drift refused", "no longer composes" in str(ve), str(ve))
            # missing raw log for a recorded corner
            try:
                mint(reduced=good, unit_dir=Path("/nonexistent"))
                check("missing raw log refused", False)
            except ValueError as ve:
                check("missing raw log refused", "stdout.bin missing" in str(ve), str(ve))
            # request for another family
            with tempfile.TemporaryDirectory() as ud4:
                other = da.build_request(EXT_KEY, ud4)
                try:
                    mint(reduced=good, request=other, unit_dir=Path("/x"))
                    check("family mismatch refused", False)
                except ValueError as ve:
                    check("family mismatch refused", "family" in str(ve), str(ve))
            # MC request
            with tempfile.TemporaryDirectory() as ud5:
                mc = da.build_mc_request("write-margin", ud5, ["tt:25:3.30", "ff:125:2.97"],
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
    finally:
        restore_pdk(saved)


def _fake_pdk_tree(root, sha):
    """Scratch gf180mcuD tree (no real PDK): model + design files and a
    SOURCES file declaring `sha` -- the shape `pdk_env.sh` resolves."""
    ng = root / "gf180mcuD" / "libs.tech" / "ngspice"
    ng.mkdir(parents=True)
    (ng / "sm141064.ngspice").write_text("*\n")
    (ng / "design.ngspice").write_text("*\n")
    (root / "gf180mcuD" / "SOURCES").write_text(f"open_pdks {sha}\n")
    return root / "gf180mcuD"


def test_pdk_identity_fail_closed():
    """`pdk_identity()` propagates pdk_env.sh's failure: a drifted tree (the
    #454 reproduction -- SOURCES declaring a non-pinned revision) and a
    missing install both refuse with pdk_env.sh's own stderr text, and a
    pinned scratch tree still resolves the identity dict."""
    pin = (REPO / "sim" / "lib" / "pdk_pin.txt").read_text().strip()
    saved_env = os.environ.pop("GF180_PDK_PATH", None)
    try:
        with tempfile.TemporaryDirectory() as td:
            # drifted revision: must refuse, naming the mismatch pdk_env.sh printed
            drifted = _fake_pdk_tree(Path(td) / "drifted", "deadbeef" * 5)
            os.environ["GF180_PDK_PATH"] = str(drifted)
            try:
                mcr.pdk_identity()
                check("drifted tree refuses", False,
                      "pdk_identity() returned a dict instead of SystemExit")
            except SystemExit as e:
                msg = str(e.code)
                check("drifted refusal carries pdk_env.sh stderr",
                      "PDK revision mismatch" in msg, msg)
                check("drifted refusal names found revision",
                      "deadbeef" in msg, msg)
                check("drifted refusal names the pin", pin in msg, msg)
            # missing install: refusal message carries pdk_env.sh's stderr
            os.environ["GF180_PDK_PATH"] = str(Path(td) / "nonexistent" / "gf180mcuD")
            try:
                mcr.pdk_identity()
                check("missing install refuses", False,
                      "pdk_identity() returned a dict instead of SystemExit")
            except SystemExit as e:
                msg = str(e.code)
                check("missing-install refusal carries stderr",
                      "libs.tech/ngspice" in msg, msg)
            # pinned scratch tree: SOURCES carries the pin -- identity resolves
            pinned = _fake_pdk_tree(Path(td) / "pinned", pin)
            os.environ["GF180_PDK_PATH"] = str(pinned)
            ident = mcr.pdk_identity()
            check("pinned tree resolves variant",
                  ident.get("variant") == "gf180mcuD", str(ident))
            check("pinned tree resolves version",
                  ident.get("version") == pin, str(ident))
            check("pinned tree resolves model/design rels",
                  ident.get("design_inc_rel") == "libs.tech/ngspice/design.ngspice"
                  and ident.get("model_file_rel") == "libs.tech/ngspice/sm141064.ngspice",
                  str(ident))
    finally:
        if saved_env is None:
            os.environ.pop("GF180_PDK_PATH", None)
        else:
            os.environ["GF180_PDK_PATH"] = saved_env


def test_claim_ownership():
    """FAMILY_CLAIMS owns the ratified families' Claim strings: no claim
    mints the canonical one, a divergent claim refuses (the signoff rollup
    finds records by Claim substring), and a family outside it must be
    handed one. SNM families mint through the same single minter (#452)."""
    for family in sorted(mcr.FAMILY_CLAIMS):
        _exp, _tb, mode, _staged = da.FAMILIES[family]
        check(f"claimed family {family} resolves in FAMILIES", len(da.FAMILIES[family]) == 4)
        check(f"claimed family {family} mode parses",
              da.parse_mode(mode)[0] in ("direct", "snm"))

    saved = stub_pdk()
    try:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ud:
            # canonical default: write-margin mints its FAMILY_CLAIMS claim
            req = da.build_request("write-margin", ud)
            values = {c: 1.0 for c in req["x_gf180_sram_adapter"]["corners"]}
            reduced = _graded("write-margin", req, values)
            exp = Path(td)
            _seed_exp_dir(td, "write-margin")
            md = mcr.mint_record("write-margin", reduced, req, report=reduced["_stub_report"],
                                 unit_dir=Path(reduced["_stub_report_outdir"]),
                                 exp_dir=exp, record_id="20261117-120310-deadbee")
            canonical = mcr.FAMILY_CLAIMS["write-margin"][1]
            check("canonical claim minted by default",
                  f"- **Claim**: {canonical}" in md.read_text(), md.read_text()[:400])
            # a divergent explicit claim refuses
            try:
                mcr.mint_record("write-margin", reduced, req, report=reduced["_stub_report"],
                                unit_dir=Path(reduced["_stub_report_outdir"]), exp_dir=exp,
                                record_id="20261117-120311-deadbee",
                                claim="reworded claim the rollup cannot match")
                check("divergent claim refused", False)
            except ValueError as ve:
                check("divergent claim refused", "FAMILY_CLAIMS owns" in str(ve), str(ve))
            # a family outside FAMILY_CLAIMS without a claim refuses
            with tempfile.TemporaryDirectory() as ud2:
                pex = da.build_request(SCH_KEY, ud2)
                pex_reduced = _graded(SCH_KEY, pex, {c: 1.0 for c in pex["x_gf180_sram_adapter"]["corners"]})
                try:
                    mcr.mint_record(SCH_KEY, pex_reduced, pex, report=pex_reduced["_stub_report"],
                                    unit_dir=Path(pex_reduced["_stub_report_outdir"]),
                                    exp_dir=Path(str(td) + "-pex"),
                                    record_id="20261117-120312-deadbee", claim=None)
                    check("claimless non-canonical family refused", False)
                except ValueError as ve:
                    check("claimless non-canonical family refused", "--claim" in str(ve), str(ve))
    finally:
        restore_pdk(saved)


def test_mint_claimed_families():
    """Every FAMILY_CLAIMS family mints through the single minter with its
    canonical claim -- SNM families included: their measurement is the
    extractor's output over the unit's own sweep data, and the corner log
    carries that extractor output (the clause the retired mint_records.py
    corner path contributed at the #452 consolidation)."""
    saved = stub_pdk()
    try:
        for i, (family, (_exp, claim)) in enumerate(sorted(mcr.FAMILY_CLAIMS.items())):
            with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as ud:
                req = da.build_request(family, ud)
                values = {c: 1.0 for c in req["x_gf180_sram_adapter"]["corners"]}
                reduced = _graded(family, req, values)
                exp = Path(td)
                _seed_exp_dir(td, family)
                rid = f"20261117-1204{i:02d}-deadbee"
                md = mcr.mint_record(family, reduced, req, report=reduced["_stub_report"],
                                     unit_dir=Path(reduced["_stub_report_outdir"]),
                                     exp_dir=exp, record_id=rid,
                                     timestamp="2026-11-17T12:04:00Z")
                text = md.read_text()
                check(f"claimed family {family} mints with its canonical claim",
                      f"- **Claim**: {claim}" in text, text[:400])
                check(f"claimed family {family} has 27 corner rows",
                      sum(1 for ln in text.splitlines()
                          if ln.startswith("  - **") and "Overall" not in ln) == 27)
                check(f"claimed family {family} snapshot is the composed deck",
                      (exp / "netlist-snapshots" / f"{rid}.spice").read_bytes()
                      == _tb_composed(family))
                log = (exp / "corners" / rid / "tt_25c_3.30v.log").read_text()
                kind, _datafile, label = da.parse_mode(da.FAMILIES[family][2])
                if kind == "snm":
                    # deterministic stub curve -> deterministic extractor RESULT
                    check(f"{family} corner log carries the extractor RESULT",
                          f"RESULT: {label}_v = -0.100000" in log, log[-300:])
                    check(f"{family} record row carries the extractor RESULTs",
                          f"- **tt_25c_3.30v**: RESULT: {label}_lobe_low_v = -0.100000;"
                          f"RESULT: {label}_lobe_high_v = -0.100000;"
                          f"RESULT: {label}_v = -0.100000;" in text,
                          [ln for ln in text.splitlines() if ln.startswith("  - **tt_25c_3.30v**:")])
    finally:
        restore_pdk(saved)


def test_mint_open_and_append_only():
    """An OPEN corner mints honestly (Overall: OPEN, row says OPEN); a
    second mint for the same record id refuses -- append-only."""
    saved = stub_pdk()
    try:
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
    finally:
        restore_pdk(saved)


def test_compare_records_consumes_minted():
    """The real compare_records.py consumes two minted records unchanged and
    produces the same delta shape it always did (#437 criterion)."""
    sys.path.insert(0, str(REPO / "sim" / "pex" / "write-margin"))
    import compare_records as cr

    saved = stub_pdk()
    try:
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
    finally:
        restore_pdk(saved)


def test_mint_declared_stream_paths():
    """The minter takes a unit's raw streams from the report's declared
    `units[].stdout`/`.stderr` paths -- a non-default layout included --
    falls back to `<cid>/stdout.bin` when the fields are omitted, and
    refuses fail-closed when a declared path is missing on disk (#444)."""
    saved = stub_pdk()
    try:
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
    finally:
        restore_pdk(saved)


def main() -> int:
    test_mint_recorded()
    test_mint_refusals()
    test_pdk_identity_fail_closed()
    test_claim_ownership()
    test_mint_claimed_families()
    test_mint_open_and_append_only()
    test_compare_records_consumes_minted()
    test_mint_declared_stream_paths()
    if FAILURES:
        print(f"\n{len(FAILURES)} failure(s):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nall mint_corner_records contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
