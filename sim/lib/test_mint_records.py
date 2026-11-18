#!/usr/bin/env python3
"""sim/lib/test_mint_records.py -- offline contract tests for the Monte
Carlo record minter and the corner-minting delegation (#272, #452).

`mint_records.py` owns the Monte Carlo path (`mint_mc`) since the #452
consolidation; its `corner` CLI subcommand delegates the deterministic
minting to `sim/lib/mint_corner_records.py`'s single minter (whose own
contract is pinned by test_mint_corner_records.py). These tests pin, with
stub artifacts -- the same stub-report discipline test_deck_adapter.py
documents -- the MC contract and the delegation. They are contract checks,
**not** physical evidence: nothing here ran ngspice.

Covered:
  * the `corner` CLI delegates: it mints the family's canonical
    FAMILY_CLAIMS claim through mint_corner_records.mint_record (PDK and
    Run lines included) into the family's experiment dir, and prints
    `record-id:`;
  * mc minting rebuilds the sample-set document from the reducer's
    measurements, writes per-draw raw logs (seed + value, or the OPEN
    reason), summary.json, and renders the record from the `klt yield`
    report a stub `klt` emits (KLT/--klt injectable, so CI needs no real
    klt and no PDK: pdk_identity is stubbed too);
  * the mc CLI offers exactly the claimed families at argparse (#446).

Run: `python3 sim/lib/test_mint_records.py` (in `npm test`).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deck_adapter  # noqa: E402
import deck_adapter as da  # noqa: E402
import mint_corner_records as mcr  # noqa: E402
import mint_records  # noqa: E402

REPO = da.REPO_ROOT
FAILURES: list[str] = []

STUB_PDK = {
    "variant": "gf180mcuD", "version": "f6eeac7" + "0" * 33,
    "design_inc_rel": "libs.tech/ngspice/design.ngspice",
    "model_file_rel": "libs.tech/ngspice/sm141064.ngspice",
}


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def _full_grid_stub(family: str, tmp: Path) -> tuple[dict, dict, dict, Path]:
    """Full-grid request + real reduce grading over stub unit outputs.

    NOT a measurement: every corner's stdout carries one stub RESULT line.
    Returns (request, report, reduced, unit-dir) -- the artifact triple the
    `corner` subcommand consumes."""
    req = da.build_request(family, str(tmp / "stage"))
    outdir = tmp / "units"
    units = []
    for cid in req["x_gf180_sram_adapter"]["corners"]:
        (outdir / cid).mkdir(parents=True, exist_ok=True)
        (outdir / cid / "stdout.bin").write_text("RESULT: stub_v = 1.0\n")
        (outdir / cid / "stderr.bin").write_bytes(b"")
        units.append({"id": cid, "status": "pass", "exit_code": 0, "timed_out": False,
                      "missing_outputs": [], "stdout": f"{cid}/stdout.bin",
                      "stderr": f"{cid}/stderr.bin",
                      "deck_sha256": req["x_gf180_sram_adapter"]["composed_deck_sha256"]})
    report = {"mode": "decks", "status": "pass", "unit_count": len(units), "units": units,
              "outdir": str(outdir),
              "environment": {"engine_version": "47",
                              "remote": {"job_id": "klt-sim-stub", "ami_id": "ami-stub"}}}
    exp_ids, exp_sha = da.expected_from_request(family, req)
    reduced = da.reduce_report(family, report, outdir=outdir,
                               expected_ids=exp_ids, expected_deck_sha256=exp_sha)
    return req, report, reduced, outdir


def test_corner_cli_delegates(tmp: Path) -> None:
    """`mint_records.py corner` mints through the single corner minter
    (mint_corner_records.mint_record) with the family's canonical
    FAMILY_CLAIMS claim, PDK and Run lines included, and prints
    `record-id:` (#452)."""
    family = "write-margin"
    req, report, reduced, units = _full_grid_stub(family, tmp)
    exp = tmp / "exp"
    (exp / "testbench").mkdir(parents=True)
    exp_dir, tb, _mode, _staged = da.FAMILIES[family]
    shutil.copyfile(REPO / exp_dir / "testbench" / tb, exp / "testbench" / tb)
    (tmp / "request.json").write_text(json.dumps(req))
    (tmp / "reduced.json").write_text(json.dumps(reduced))
    (tmp / "report.json").write_text(json.dumps(report))

    rid = "20270101-000000-def5678"
    saved = mcr.pdk_identity
    mcr.pdk_identity = lambda: dict(STUB_PDK)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            rc = mint_records.main([
                "corner", family,
                "--request", str(tmp / "request.json"),
                "--reduced", str(tmp / "reduced.json"),
                "--report", str(tmp / "report.json"),
                "--unit-dir", str(units),
                "--supersedes", "20200101-000000-abc1234 (PDK re-pin, issue #272)",
                "--record-id", rid,
                "--exp-dir", str(exp),
            ])
    finally:
        mcr.pdk_identity = saved
    check("corner CLI exits 0", rc == 0, str(rc))
    check("corner CLI prints record-id", f"record-id: {rid}" in out.getvalue(),
          out.getvalue())
    record = exp / "records" / f"{rid}.md"
    check("corner CLI wrote the record", record.is_file(), str(record))
    text = record.read_text()
    canonical = mint_records.FAMILY_CLAIMS[family][1]
    check("delegated mint carries the canonical claim",
          f"- **Claim**: {canonical}" in text, text[:400])
    check("delegated mint carries the PDK line",
          f"- **PDK**: `{STUB_PDK['variant']}`, open_pdks `{STUB_PDK['version']}`" in text)
    check("delegated mint carries the Run line with the fleet job",
          "job `klt-sim-stub`" in text)
    check("delegated mint carries Supersedes verbatim",
          "- **Supersedes**: 20200101-000000-abc1234 (PDK re-pin, issue #272)" in text)
    check("delegated snapshot is the composed deck",
          (exp / "netlist-snapshots" / f"{rid}.spice").read_bytes()
          == da.compose_deck((REPO / exp_dir / "testbench" / tb).read_text(encoding="utf-8")).encode())


CANNED_YIELD_JSON = json.dumps({
    "payload": {
        "status": "reported",
        "warnings": ["stub run-level warning"],
        "measurements": [{
            "name": "stub_v@tt_25c_3.30v", "unit": "V",
            "yield": {"empirical": {"confidence_interval": {"low": 0.98}}},
            "capability": {"cpk": 4.0, "sigma_to_spec": 12.0},
            "distribution": {"mean": 0.25, "stddev": 0.02},
            "sample_size": {"verdict": "sufficient"},
            "negative_control": {"verdict": "detected"},
        }],
    }
})


def stub_mc_request(tmp: Path) -> tuple[Path, dict, str]:
    family = "read-snm"
    cid = "tt_25c_3.30v"
    seed = mint_records.deck_adapter.mc.derive_seed(1, cid, "mm", 0)
    request = {
        "engine": "ngspice", "decks": [], "options": {},
        "x_gf180_sram_adapter": {
            "campaign": "monte-carlo", "family": family,
            "mode": deck_adapter.MC_FAMILIES[family][0],
            "key": deck_adapter.MC_FAMILIES[family][1],
            "testbench": f"{family}/testbench/tb.spice",
            "testbench_sha256": "a" * 64, "composed_deck_sha256": "b" * 64,
            "base_seed": 1, "corners": [cid],
            "n_mismatch": 2, "n_determinism_control": 1, "n_negative_control": 1,
            "nc_mismatch_scale": 20.0, "nc_vdd": None, "spiceinit_sha256": "c" * 64,
            "units": [],
        },
    }
    reduced = {
        "family": family, "mode": request["x_gf180_sram_adapter"]["mode"],
        "key": "stub_v", "expected_units": 4,
        "expected_deck_sha256": "b" * 64, "coverage_errors": [], "infra_failures": [],
        "batches": {
            cid: {
                "mm": {"seed_labels": ["s1", "s2"],
                       "samples": [(0, {"stub_v": 0.25}, []), (1, {}, ["RESULT-ERROR: not bistable"])]},
                "ctrl": {"seed_labels": ["s3"],
                         "samples": [(0, {"stub_v": 0.249999}, [])]},
                "nc": {"seed_labels": ["s4"],
                       "samples": [(0, {"stub_v": -0.001}, [])]},
            },
        },
        "measurements": [{
            "name": "stub_v@" + cid, "unit": "V",
            "samples": [0.25], "errored": 1,
            "limits": {"min": 0.0}, "source_corners": [cid],
            "negative_control": {"samples": [-0.001], "errored": 0,
                                 "description": "known-bad variant: sw_stat_mismatch=20"},
        }],
    }
    request_path = tmp / "mc-request.json"
    request_path.write_text(json.dumps(request))
    reduced_path = tmp / "mc-reduced.json"
    reduced_path.write_text(json.dumps(reduced))
    return request_path, reduced_path, seed


def install_stub_klt(tmp: Path) -> Path:
    shim = tmp / "klt-shim"
    shim.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "klt-stub 0.0.0"; exit 0; fi\n'
        'for a in "$@"; do if [ "$a" = "json" ]; then cat <<\'EOT\'\n'
        + CANNED_YIELD_JSON + "\nEOT\nexit 0; fi; done\n"
        'echo "stub text report"; exit 0\n'
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return shim


def test_mc_mint(tmp: Path) -> None:
    family = "read-snm"
    cid = "tt_25c_3.30v"
    tb = tmp / "repo3" / "sim" / family / "testbench" / deck_adapter.FAMILIES[family][1]
    tb.parent.mkdir(parents=True)
    tb.write_text("* stub\n")
    request_path, reduced_path, _seed = stub_mc_request(tmp)
    shim = install_stub_klt(tmp)
    os.environ["KLT"] = str(shim)
    saved = mint_records.pdk_identity
    mint_records.pdk_identity = lambda: dict(STUB_PDK)
    try:
        record = mint_records.mint_mc(
            family, request_path, reduced_path,
            supersedes="20260921-124232-cf5e975 (unpinned environment, #272 re-qualification)",
            record_id="20270101-000001-abc0001", repo_root=tmp / "repo3",
            now=mint_records.datetime(2027, 1, 1, tzinfo=mint_records.timezone.utc),
            klt_bin=str(shim),
        )
    finally:
        mint_records.pdk_identity = saved
        os.environ.pop("KLT", None)

    mc = tmp / "repo3" / "sim" / family / "mc"
    sample_doc = json.loads((mc / "samples" / "20270101-000001-abc0001.json").read_text())
    check("sample doc keeps the reducer's measurements verbatim",
          sample_doc["measurements"] == json.loads(reduced_path.read_text())["measurements"])
    prov = sample_doc["provenance"]
    check("sample doc pins the PDK by identity",
          prov["pdk"]["variant"] == "gf180mcuD" and "f6eeac7" in prov["pdk"]["version"])
    check("sample doc discloses the pinned engine environment",
          "environment-pin-decision" in prov["engine_environment"])

    raw = (mc / "raw-logs" / "20270101-000001-abc0001" / f"{cid}.log").read_text()
    check("raw log records the seed and value of every draw",
          "sample 0 seed=s1: RESULT: stub_v = 0.25" in raw)
    check("raw log records the OPEN reason, not a coerced value",
          "sample 1 seed=s2: OPEN -- RESULT-ERROR: not bistable" in raw)
    summary = json.loads((mc / "raw-logs" / "20270101-000001-abc0001" / "summary.json").read_text())
    check("summary tallies errored draws per corner",
          summary["corners"][0]["mm_n_ok"] == 1 and summary["corners"][0]["mm_n_errored"] == 1)
    check("determinism control collapses to a distinct-value list",
          summary["corners"][0]["det_distinct_values"] == [0.249999])

    text = record.read_text()
    check("record carries the yield table row from the report",
          "| `tt_25c_3.30v` | 1 | 1 | 0.25 | 0.02 | 0.98 | 4 | 12 | sufficient | detected |" in text)
    check("record determinism-control row",
          "| `tt_25c_3.30v` | 1 | 0 | 0.249999 | PINNED |" in text)
    check("record Supersedes line verbatim",
          "- **Supersedes**: 20260921-124232-cf5e975 (unpinned environment, #272 re-qualification)" in text)
    check("record Reproduce is the deck-mode path, not the retired CLI",
          "deck_adapter.py mc-build read-snm" in text
          and "run_mc_campaign.py --experiment" not in text)
    check("record carries the negative-control description",
          "sw_stat_mismatch=20" in text)
    check("record embeds the yield text report verbatim",
          "stub text report" in text)
    check("no absolute host path in the record", str(tmp) not in text)


def test_infra_accounted() -> None:
    """Infra failures mint only when every one is a counted negative-control
    errored draw; any mm/ctrl failure or unaccounted nc failure aborts."""
    def reduced(infra):
        return {
            "batches": {
                "ff_25c_3.30v": {
                    "mm": {"seed_labels": ["s1"], "samples": [(0, {"k": 1.0}, [])]},
                    "ctrl": {"seed_labels": ["s2"], "samples": [(0, {"k": 1.0}, [])]},
                    "nc": {"seed_labels": ["s3", "s4"],
                           "samples": [(11, {}, ["R: expected data file not produced"]),
                                       (12, {"k": -0.5}, [])]},
                },
            },
            "infra_failures": infra,
        }

    ok = reduced([{"id": "mc.ff_25c_3.30v.nc.00011.R", "reason": "declared outputs missing"}])
    out = mint_records._check_infra_accounted({}, ok)
    check("accounted nc infra failure classifies", len(out) == 1)

    for name, infra in [
        ("unaccounted nc infra aborts",
         [{"id": "mc.ff_25c_3.30v.nc.00012.L", "reason": "declared outputs missing"}]),
        ("mm infra aborts", [{"id": "mc.ff_25c_3.30v.mm.00003.L", "reason": "timed out"}]),
        ("ctrl infra aborts", [{"id": "mc.ff_25c_3.30v.ctrl.00000.R", "reason": "timed out"}]),
    ]:
        try:
            mint_records._check_infra_accounted({}, reduced(infra))
            check(name, False)
        except SystemExit:
            check(name, True)


def test_mc_cli_claim_gating() -> None:
    """Every MC_CLAIMS family resolves in MC_FAMILIES, the mc CLI offers
    exactly the claimed families at argparse, and an unclaimed family is
    refused with a readable 'invalid choice' -- never a bare KeyError
    inside mint_mc (#446)."""
    for family in mint_records.MC_CLAIMS:
        check(f"mc claimed family {family} resolves in MC_FAMILIES",
              family in deck_adapter.MC_FAMILIES)
    for family in sorted(deck_adapter.MC_FAMILIES):
        if family in mint_records.MC_CLAIMS:
            continue
        err = io.StringIO()
        refused = False
        try:
            with contextlib.redirect_stderr(err):
                mint_records.main(["mc", family, "--request", "nonexistent.json",
                                   "--reduced", "nonexistent.json"])
        except SystemExit:
            refused = "invalid choice" in err.getvalue()
        except Exception:
            refused = False
        check(f"mc CLI refuses unclaimed family {family} before mint_mc",
              refused)
    for family in sorted(mint_records.MC_CLAIMS):
        offered = False
        try:
            mint_records.main(["mc", family, "--request", "nonexistent.json",
                               "--reduced", "nonexistent.json"])
        except SystemExit:
            offered = False
        except Exception:
            offered = True
        check(f"mc CLI still offers claimed family {family}", offered)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_corner_cli_delegates(tmp / "t1")
        test_mc_mint(tmp / "t3")
        test_infra_accounted()
        test_mc_cli_claim_gating()
    if FAILURES:
        print(f"\n{len(FAILURES)} failure(s):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nall mint_records contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
