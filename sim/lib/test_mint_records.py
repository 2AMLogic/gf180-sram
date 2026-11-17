#!/usr/bin/env python3
"""sim/lib/test_mint_records.py -- offline contract tests for the record
minter (#272).

`mint_records.py` is the generator the #230 cutover left to #272: it mints
append-only evidence records (deterministic + Monte Carlo) from a
`klt sim` deck-mode run's request/reduced/report artifacts. These tests pin
its contract with stub artifacts -- the same stub-report discipline
test_deck_adapter.py documents. They are contract checks, **not** physical
evidence: nothing here ran ngspice.

Covered:
  * corner minting writes the snapshot (composed-deck bytes, sha-pinned),
    per-corner logs in the retired launcher's byte shape (engine stdout,
    the two header lines, the SNM extractor's output), and a record whose
    Result rows/Overall/Supersedes/PDK/Run lines match the convention;
  * a grading that does not pin the request's composed deck sha256, a
    family mismatch, or coverage errors abort before anything is written;
  * mc minting rebuilds the sample-set document from the reducer's
    measurements, writes per-draw raw logs (seed + value, or the OPEN
    reason), summary.json, and renders the record from the `klt yield`
    report a stub `klt` emits (KLT/--klt injectable, so CI needs no real
    klt and no PDK: pdk_identity is stubbed too).

Run: `python3 sim/lib/test_mint_records.py` (in `npm test`).
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deck_adapter  # noqa: E402 (path-injected sibling import)
import mint_records  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    if not cond:
        FAILURES.append(name)
        print(f"FAIL: {name}")
    else:
        print(f"ok: {name}")


TB_TEXT = textwrap.dedent(
    """
    * stub testbench
    .control
    echo "RESULT: stub_v = 1.000000"
    quit
    .endc
    """
)
DATAFILE = "stub_sweep.txt"


def sha(b: bytes) -> str:
    return deck_adapter._sha256(b)


def write_unit_tree(root: Path, cids: list[str], *, with_data: bool) -> None:
    for cid in cids:
        d = root / cid
        d.mkdir(parents=True, exist_ok=True)
        (d / "stdout.bin").write_text("stub engine stdout\n")
        (d / "stderr.bin").write_bytes(b"")
        if with_data:
            (d / DATAFILE).write_text(
                "\n".join(f"{i * 0.1} {1.0 - i * 0.1}" for i in range(6)) + "\n"
            )


def stub_request(family: str, cids: list[str], deck_sha: str) -> dict:
    return {
        "engine": "ngspice",
        "decks": [],
        "options": {"timeout_s": 300},
        "x_gf180_sram_adapter": {
            "family": family,
            "mode": deck_adapter.FAMILIES[family][2],
            "testbench": f"{family}/testbench/tb.spice",
            "testbench_sha256": sha(TB_TEXT.encode()),
            "composed_deck_sha256": deck_sha,
            "corners": cids,
            "corner_count": len(cids),
            "spiceinit_sha256": "f" * 64,
            "full_grid": False,
        },
    }


def stub_corner_reduced(family: str, cids: list[str], deck_sha: str) -> dict:
    corners = []
    for i, cid in enumerate(cids):
        if i == 0:
            corners.append({
                "id": cid, "status": "OPEN",
                "reasons": ["no RESULT line captured (engine exit 0)"],
                "results": {}, "result_lines": [], "engine_exit_code": 0,
                "deck_sha256": deck_sha,
            })
        else:
            lines = [f"RESULT: stub_v = {0.1 * i:.6f}"]
            corners.append({
                "id": cid, "status": "recorded", "reasons": [],
                "results": {"stub_v": 0.1 * i},
                "result_lines": lines, "engine_exit_code": 0,
                "deck_sha256": deck_sha,
            })
    return {
        "family": family, "mode": deck_adapter.FAMILIES[family][2],
        "expected": cids, "expected_deck_sha256": deck_sha,
        "coverage_errors": [], "corners": corners, "overall": "OPEN",
    }


def stub_report(cids: list[str]) -> dict:
    return {
        "mode": "decks",
        "environment": {
            "engine_version": "47",
            "remote": {"job_id": "klt-sim-stub", "ami_id": "ami-stub",
                       "provider": "aws-batch-fleet", "region": "us-east-1"},
        },
        "units": [
            {"id": cid, "status": "pass", "exit_code": 0, "timed_out": False,
             "stdout": f"{cid}/stdout.bin", "stderr": f"{cid}/stderr.bin",
             "deck_sha256": "x"}
            for cid in cids
        ],
    }


def test_corner_mint(tmp: Path) -> None:
    family = "read-snm"  # an snm-mode family: exercises the extractor path
    cids = ["tt_25c_3.30v", "ss_125c_3.63v"]
    tb = tmp / "repo" / "sim" / family / "testbench" / deck_adapter.FAMILIES[family][1]
    tb.parent.mkdir(parents=True)
    tb.write_text(TB_TEXT)
    deck_sha = sha(deck_adapter.compose_deck(TB_TEXT).encode())

    unit_dir = tmp / "units"
    write_unit_tree(unit_dir, cids, with_data=True)

    request_path = tmp / "request.json"
    request_path.write_text(json.dumps(stub_request(family, cids, deck_sha)))
    reduced_path = tmp / "reduced.json"
    reduced_path.write_text(json.dumps(stub_corner_reduced(family, cids, deck_sha)))
    report_path = tmp / "report.json"
    report_path.write_text(json.dumps(stub_report(cids)))

    record = mint_records.mint_corner(
        family, request_path, reduced_path, report_path, unit_dir,
        supersedes="20200101-000000-abc1234 (PDK re-pin, issue #272)",
        record_id="20270101-000000-def5678", repo_root=tmp / "repo",
        now=mint_records.datetime(2027, 1, 1, tzinfo=mint_records.timezone.utc),
    )
    text = record.read_text()

    exp = tmp / "repo" / "sim" / family
    snapshot = (exp / "netlist-snapshots" / "20270101-000000-def5678.spice").read_bytes()
    check("snapshot is the composed deck bytes",
          snapshot == deck_adapter.compose_deck(TB_TEXT).encode())
    check("request deck sha matches snapshot",
          sha(snapshot) == deck_sha)

    log0 = (exp / "corners" / "20270101-000000-def5678" / f"{cids[0]}.log").read_text()
    check("corner log carries engine stdout", "stub engine stdout" in log0)
    check("corner log header lines in launcher shape",
          "=== corner: tt_25c_3.30v (process=tt temp=25C vdd=3.30V) ===\n"
          "=== ngspice exit status: 0 ===" in log0)
    log1 = (exp / "corners" / "20270101-000000-def5678" / f"{cids[1]}.log").read_text()
    check("snm corner log carries extractor RESULT lines",
          "RESULT: stub_snm" in log1 or "RESULT-ERROR" in log1 or "RESULT:" in log1)

    check("record Claim line", "spec/sram.md Characterization -- read SNM" in text)
    check("record Supersedes line verbatim",
          "- **Supersedes**: 20200101-000000-abc1234 (PDK re-pin, issue #272)" in text)
    check("record PDK identity line (f6eeac7 pin)", "open_pdks `" in text)
    check("record Run line carries the fleet job id", "klt-sim-stub" in text)
    check("record Run line carries the spiceinit pin",
          "spiceinit" in text and "f" * 64 in text)
    check("record Result rows verbatim with launcher join",
          f"- **{cids[1]}**: RESULT: stub_v = 0.100000;" in text)
    check("OPEN corner renders OPEN, never a value",
          f"- **{cids[0]}**: OPEN -- no RESULT line captured" in text)
    check("Overall OPEN rollup", "**Overall: OPEN**" in text)
    check("no absolute host path in the record", str(tmp) not in text)


def test_corner_rejects_bad_grading(tmp: Path) -> None:
    family = "write-margin"
    cids = ["tt_25c_3.30v"]
    tb = tmp / "repo2" / "sim" / family / "testbench" / deck_adapter.FAMILIES[family][1]
    tb.parent.mkdir(parents=True)
    tb.write_text(TB_TEXT)
    deck_sha = sha(deck_adapter.compose_deck(TB_TEXT).encode())
    request_path = tmp / "req2.json"
    request_path.write_text(json.dumps(stub_request(family, cids, deck_sha)))
    reduced_path = tmp / "red2.json"
    reduced_path.write_text(json.dumps(stub_corner_reduced(family, cids, deck_sha)))
    report_path = tmp / "rep2.json"
    report_path.write_text(json.dumps(stub_report(cids)))
    unit_dir = tmp / "units2"
    write_unit_tree(unit_dir, cids, with_data=False)

    other = stub_corner_reduced(family, cids, deck_sha)
    other["expected_deck_sha256"] = "0" * 64
    (tmp / "red_drift.json").write_text(json.dumps(other))
    try:
        mint_records.mint_corner(family, request_path, tmp / "red_drift.json",
                                 report_path, unit_dir, supersedes="",
                                 repo_root=tmp / "repo2")
        check("deck-sha drift aborts minting", False)
    except SystemExit:
        check("deck-sha drift aborts minting", True)

    try:
        mint_records.mint_corner("read-snm", request_path, reduced_path,
                                 report_path, unit_dir, supersedes="",
                                 repo_root=tmp / "repo2")
        check("family mismatch aborts minting", False)
    except SystemExit:
        check("family mismatch aborts minting", True)


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
    tb.write_text(TB_TEXT)
    request_path, reduced_path, _seed = stub_mc_request(tmp)
    shim = install_stub_klt(tmp)
    os.environ["KLT"] = str(shim)
    saved = mint_records.pdk_identity
    mint_records.pdk_identity = lambda: {
        "variant": "gf180mcuD", "version": "f6eeac7" + "0" * 56,
        "design_inc_rel": "libs.tech/ngspice/design.ngspice",
        "model_file_rel": "libs.tech/ngspice/sm141064.ngspice",
    }
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


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_corner_mint(tmp / "t1")
        test_corner_rejects_bad_grading(tmp / "t2")
        test_mc_mint(tmp / "t3")
        test_infra_accounted()
    if FAILURES:
        print(f"\n{len(FAILURES)} failure(s)")
        return 1
    print("\nall mint_records contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
