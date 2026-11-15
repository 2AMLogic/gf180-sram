#!/usr/bin/env python3
"""Offline contract tests for sim/lib/parity_compare.py (#230 full-grid parity).

No ngspice, no PDK, no fleet: every fixture below is hand-built (record
files in the records' own row grammar, stub reduced.json gradings, a stub
SNM extractor plus one integration case against the real snm_extract.py on
a synthetic sweep). Nothing here is physical evidence and no fixture result
may be quoted as a measurement.

Covers, per the curated acceptance criteria: exact match, a seeded mismatch,
a corner present in one side only, an OPEN corner, the SNM tolerance
boundary at 30 uV, and the deck_sha256 present-and-equal assertion.

Run: python3 sim/lib/test_parity_compare.py   (or via `npm run test`)
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parity_compare as pc  # noqa: E402

REPO = pc.REPO_ROOT
CMP = REPO / "sim/lib/parity_compare.py"
CORNERS = ["ff_-40c_2.97v", "tt_25c_3.30v", "ss_125c_3.63v"]
COMPOSED_SHA = "a" * 64
OTHER_SHA = "b" * 64


def write_record(path, rows):
    """A record file in the append-only records' own Result-row grammar."""
    lines = ["# Record fixture", "", "- **Claim**: fixture claim", "- **Result**:"]
    for cid, values in rows.items():
        if values == "OPEN":
            lines.append(f"  - **{cid}**: OPEN")
        else:
            body = "".join(f"RESULT: {k} = {v};" for k, v in values.items())
            lines.append(f"  - **{cid}**: {body}")
    lines.append("  - **Overall: recorded** -- fixture")
    path.write_text("\n".join(lines) + "\n")


def make_reduced(family, corners, *, sha=COMPOSED_SHA):
    """A stub reduce --json-out grading: recorded corners with given results."""
    return {
        "family": family,
        "mode": "",
        "expected": corners,
        "expected_deck_sha256": sha,
        "coverage_errors": [],
        "corners": [
            {
                "id": cid,
                "status": "recorded",
                "reasons": [],
                "results": corners[cid],
                "engine_exit_code": 0,
                "deck_sha256": sha,
            }
            if isinstance(corners[cid], dict)
            else {"id": cid, "status": "OPEN", "reasons": corners[cid],
                  "results": {}, "engine_exit_code": 0, "deck_sha256": sha}
            for cid in corners
        ],
        "overall": "recorded",
    }


def make_request(path, family):
    path.write_text(json.dumps({
        "engine": "ngspice", "decks": [],
        "x_gf180_sram_adapter": {
            "family": family, "composed_deck_sha256": COMPOSED_SHA,
            "corners": CORNERS, "corner_count": len(CORNERS), "full_grid": False,
        },
    }))


def run_cmp(tmp, family, reduced, *, record=None, request=None, sweep_dir=None,
            pre213=None, tolerance=None):
    cmd = [sys.executable, str(CMP), family, str(reduced)]
    if record:
        cmd += ["--record", str(record)]
    if request:
        cmd += ["--request", str(request)]
    if sweep_dir:
        cmd += ["--sweep-dir", str(sweep_dir)]
    if pre213:
        cmd += ["--pre213", str(pre213)]
    if tolerance is not None:
        cmd += ["--tolerance-v", str(tolerance)]
    json_out = tmp / "summary.json"
    cmd += ["--json-out", str(json_out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    summary = json.loads(json_out.read_text()) if json_out.is_file() else None
    return proc.returncode, proc.stdout + proc.stderr, summary


def exact_record_rows(family, corners):
    """Record rows and matching reduced results: identical values."""
    values = {
        "write-margin": lambda cid: {"write_trip_voltage_v": 1.9, "write_vdd_v": 3.3},
        "read-access": lambda cid: {"read_access_time_s": 1.7e-10},
    }[family]
    return {cid: values(cid) for cid in corners}


class ParityCompareExactFamilies(unittest.TestCase):
    """The three RESULT:-emitting families: exact float equality."""

    def test_exact_match_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record = tmp / "record.md"
            write_record(record, exact_record_rows("write-margin", CORNERS))
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("write-margin", exact_record_rows("write-margin", CORNERS))))
            request = tmp / "request.json"
            make_request(request, "write-margin")
            rc, out, summary = run_cmp(tmp, "write-margin", reduced, record=record,
                                       request=request)
            self.assertEqual(rc, 0, out)
            self.assertEqual(summary["overall"], "parity")
            self.assertEqual(summary["coverage"]["corners"], len(CORNERS))
            self.assertTrue(summary["deck_sha256"]["checked"])
            self.assertEqual(summary["deck_sha256"]["errors"], [])
            self.assertIn("EXACT", out)
            self.assertIn("Overall: **parity**", out)

    def test_seeded_mismatch_fails_with_delta(self):
        rows = exact_record_rows("write-margin", CORNERS)
        reduced_rows = exact_record_rows("write-margin", CORNERS)
        reduced_rows["tt_25c_3.30v"]["write_trip_voltage_v"] += 1e-3
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record = tmp / "record.md"
            write_record(record, rows)
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("write-margin", reduced_rows)))
            rc, out, summary = run_cmp(tmp, "write-margin", reduced, record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["overall"], "MISMATCH")
            bad = [c for c in summary["corners"] if c["id"] == "tt_25c_3.30v"][0]
            self.assertEqual(bad["status"], "MISMATCH")
            self.assertTrue(any("write_trip_voltage_v" in r for r in bad["reasons"]), bad["reasons"])
            # the untouched corners still show parity
            good = [c for c in summary["corners"] if c["id"] == "ff_-40c_2.97v"][0]
            self.assertEqual(good["status"], "parity")

    def test_secondary_metric_mismatch_fails(self):
        """write_vdd_v is in the record row too; it must match as well."""
        rows = exact_record_rows("write-margin", CORNERS)
        reduced_rows = exact_record_rows("write-margin", CORNERS)
        reduced_rows["ss_125c_3.63v"]["write_vdd_v"] += 0.01
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record = tmp / "record.md"
            write_record(record, rows)
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("write-margin", reduced_rows)))
            rc, _out, summary = run_cmp(tmp, "write-margin", reduced, record=record)
            self.assertNotEqual(rc, 0)
            bad = [c for c in summary["corners"] if c["id"] == "ss_125c_3.63v"][0]
            self.assertEqual(bad["status"], "MISMATCH")

    def test_corner_missing_from_fleet_report(self):
        rows = exact_record_rows("read-access", CORNERS)
        reduced_rows = {k: v for k, v in rows.items() if k != "ss_125c_3.63v"}
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record = tmp / "record.md"
            write_record(record, rows)
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("read-access", reduced_rows)))
            rc, _out, summary = run_cmp(tmp, "read-access", reduced, record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["coverage"]["missing_in_fleet"], ["ss_125c_3.63v"])
            self.assertEqual(summary["coverage"]["missing_in_record"], [])
            self.assertTrue(any("not the fleet report" in p for p in summary["problems"]))

    def test_corner_missing_from_record(self):
        rows = {k: v for k, v in exact_record_rows("read-access", CORNERS).items()
                if k != "ff_-40c_2.97v"}
        reduced_rows = exact_record_rows("read-access", CORNERS)
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record = tmp / "record.md"
            write_record(record, rows)
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("read-access", reduced_rows)))
            rc, _out, summary = run_cmp(tmp, "read-access", reduced, record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["coverage"]["missing_in_record"], ["ff_-40c_2.97v"])

    def test_fleet_open_corner_is_reported_not_parified(self):
        rows = exact_record_rows("read-access", CORNERS)
        reduced_rows = dict(rows)
        reduced_rows["tt_25c_3.30v"] = ["engine timed out"]
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record = tmp / "record.md"
            write_record(record, rows)
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("read-access", reduced_rows)))
            rc, out, summary = run_cmp(tmp, "read-access", reduced, record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["overall"], "OPEN")
            bad = [c for c in summary["corners"] if c["id"] == "tt_25c_3.30v"][0]
            self.assertEqual(bad["status"], "OPEN")
            self.assertEqual(bad["reasons"], ["engine timed out"])
            self.assertIn("Non-parity corners", out)
            self.assertNotIn("tt_25c_3.30v` | EXACT", out)

    def test_record_open_corner_cannot_be_compared(self):
        rows = exact_record_rows("read-access", CORNERS)
        rows["ff_-40c_2.97v"] = "OPEN"
        reduced_rows = exact_record_rows("read-access", CORNERS)
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record = tmp / "record.md"
            write_record(record, rows)
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("read-access", reduced_rows)))
            rc, _out, summary = run_cmp(tmp, "read-access", reduced, record=record)
            self.assertNotEqual(rc, 0)
            bad = [c for c in summary["corners"] if c["id"] == "ff_-40c_2.97v"][0]
            self.assertEqual(bad["status"], "MISMATCH")
            self.assertTrue(any("no measured value" in r for r in bad["reasons"]))


class DeckShaAssertion(unittest.TestCase):
    """The #347 gap: absence must fail, not silently pass."""

    def _run(self, tmp, sha_value, with_request=True):
        rows = exact_record_rows("write-margin", CORNERS)
        record = tmp / "record.md"
        write_record(record, rows)
        reduced = make_reduced("write-margin", rows, sha=sha_value)
        if sha_value is None:
            for entry in reduced["corners"]:
                del entry["deck_sha256"]
        reduced_path = tmp / "reduced.json"
        reduced_path.write_text(json.dumps(reduced))
        request = tmp / "request.json"
        if with_request:
            make_request(request, "write-margin")
        return run_cmp(tmp, "write-margin", reduced_path, record=record,
                       request=request if with_request else None)

    def test_absent_deck_sha_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            rc, _out, summary = self._run(tmp, None)
            self.assertNotEqual(rc, 0)
            self.assertTrue(all("absent" in e for e in summary["deck_sha256"]["errors"]))
            self.assertEqual(len(summary["deck_sha256"]["errors"]), len(CORNERS))

    def test_wrong_deck_sha_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            rc, _out, summary = self._run(tmp, OTHER_SHA)
            self.assertNotEqual(rc, 0)
            self.assertTrue(all("differs" in e for e in summary["deck_sha256"]["errors"]))

    def test_matching_deck_sha_passes_and_no_request_skips(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            rc, _out, summary = self._run(tmp, COMPOSED_SHA)
            self.assertEqual(rc, 0)
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            rc, _out, summary = self._run(tmp, OTHER_SHA, with_request=False)
            self.assertEqual(rc, 0)
            self.assertFalse(summary["deck_sha256"]["checked"])


STUB_EXTRACTOR = """#!/usr/bin/env python3
import sys
path, label = sys.argv[1], sys.argv[2]
ys = []
with open(path) as f:
    for line in f:
        parts = line.split()
        if len(parts) >= 2:
            try:
                ys.append(float(parts[1]))
            except ValueError:
                pass
v = max(ys)
print(f"RESULT: {label}_lobe_low_v = {v:.6f}")
print(f"RESULT: {label}_lobe_high_v = {v:.6f}")
print(f"RESULT: {label}_v = {v:.6f}")
"""


class SnmToleranceBoundary(unittest.TestCase):
    """The recorded metric gates at <= 30 uV; lobes are tabulated only."""

    def _setup(self, tmp, fleet_v_by_corner):
        pre213 = tmp / "pre213.py"
        pre213.write_text(STUB_EXTRACTOR)
        rows, reduced_rows = {}, {}
        for cid, fleet_v in fleet_v_by_corner.items():
            sweep = tmp / "sweeps" / cid / "read_snm_sweep.txt"
            sweep.parent.mkdir(parents=True, exist_ok=True)
            sweep.write_text("0.0 0.1\n1.0 0.2\n2.0 " + repr(fleet_v) + "\n")
            rows[cid] = {"read_snm_lobe_low_v": 0.5, "read_snm_lobe_high_v": 0.5,
                         "read_snm_v": 0.5}
            reduced_rows[cid] = {"read_snm_v": 0.28912}  # current-extractor value: unused here
        record = tmp / "record.md"
        write_record(record, rows)
        reduced = tmp / "reduced.json"
        reduced.write_text(json.dumps(make_reduced("read-snm", reduced_rows)))
        return record, reduced, pre213

    def test_delta_exactly_at_tolerance_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record, reduced, pre213 = self._setup(tmp, {"tt_25c_3.30v": 0.50003})
            rc, out, summary = run_cmp(tmp, "read-snm", reduced, record=record,
                                       sweep_dir=tmp / "sweeps", pre213=pre213)
            self.assertEqual(rc, 0, out)
            m = summary["corners"][0]["metrics"]["read_snm_v"]
            self.assertEqual(m["verdict"], "WITHIN-TOL")
            self.assertIn("pre-#213 extractor", out)

    def test_delta_one_ustep_above_tolerance_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record, reduced, pre213 = self._setup(tmp, {"tt_25c_3.30v": 0.500031})
            rc, out, summary = run_cmp(tmp, "read-snm", reduced, record=record,
                                       sweep_dir=tmp / "sweeps", pre213=pre213)
            self.assertNotEqual(rc, 0)
            m = summary["corners"][0]["metrics"]["read_snm_v"]
            self.assertEqual(m["verdict"], "ABOVE-TOL")
            self.assertTrue(any("exceeds" in r for r in summary["corners"][0]["reasons"]))

    def test_exact_zero_delta_is_exact(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record, reduced, pre213 = self._setup(tmp, {"tt_25c_3.30v": 0.5})
            rc, _out, summary = run_cmp(tmp, "read-snm", reduced, record=record,
                                        sweep_dir=tmp / "sweeps", pre213=pre213)
            self.assertEqual(rc, 0)
            self.assertEqual(summary["corners"][0]["metrics"]["read_snm_v"]["verdict"], "EXACT")

    def test_missing_sweep_file_is_not_parity(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record, reduced, pre213 = self._setup(tmp, {"tt_25c_3.30v": 0.5})
            (tmp / "sweeps" / "tt_25c_3.30v" / "read_snm_sweep.txt").unlink()
            rc, _out, summary = run_cmp(tmp, "read-snm", reduced, record=record,
                                        sweep_dir=tmp / "sweeps", pre213=pre213)
            self.assertNotEqual(rc, 0)
            corner = summary["corners"][0]
            self.assertEqual(corner["status"], "MISMATCH")
            self.assertTrue(any("not found" in r for r in corner["reasons"]))

    def test_extractor_result_error_is_not_parity(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record, reduced, pre213 = self._setup(tmp, {"tt_25c_3.30v": 0.5})
            pre213.write_text(
                "import sys\nprint('RESULT-ERROR: x -- boom', file=sys.stderr)\nsys.exit(1)\n"
            )
            rc, _out, summary = run_cmp(tmp, "read-snm", reduced, record=record,
                                        sweep_dir=tmp / "sweeps", pre213=pre213)
            self.assertNotEqual(rc, 0)
            self.assertTrue(any("RESULT-ERROR" in r or "exited 1" in r
                                for r in summary["corners"][0]["reasons"]))


class RealExtractorIntegration(unittest.TestCase):
    """The full SNM path against the real snm_extract.py on a synthetic sweep.

    This exercises read_xy/the extractor subprocess end to end; the values
    are derived from the same synthetic curve on both sides, which makes this
    a plumbing check of parity_compare, not physical evidence.
    """

    @staticmethod
    def _sigmoid_sweep(path):
        # an inverter-like VTC: high at low x, falling through the midpoint
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for i in range(201):
            x = i * 0.005
            y = 3.3 / (1.0 + pow(2.718281828459045, 25.0 * (x - 0.9)))
            lines.append(f"{x:.6f}  {y:.8e}")
        path.write_text("\n".join(lines) + "\n")

    def _fleet_values(self, tmp, pre213, cid):
        proc = subprocess.run(
            [sys.executable, str(pre213), str(tmp / "sweeps" / cid / "read_snm_sweep.txt"), "read_snm"],
            capture_output=True, text=True,
        )
        return pc.parse_result_lines(proc.stdout)

    def test_real_extractor_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            pre213 = REPO / "sim/lib/snm_extract.py"
            for cid in CORNERS:
                self._sigmoid_sweep(tmp / "sweeps" / cid / "read_snm_sweep.txt")
            rows = {}
            for cid in CORNERS:
                vals = self._fleet_values(tmp, pre213, cid)
                self.assertEqual(set(vals), {"read_snm_lobe_low_v", "read_snm_lobe_high_v", "read_snm_v"})
                rows[cid] = vals
            record = tmp / "record.md"
            write_record(record, rows)
            reduced_rows = {cid: {"read_snm_v": 0.0} for cid in CORNERS}
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("read-snm", reduced_rows)))
            rc, out, summary = run_cmp(tmp, "read-snm", reduced, record=record,
                                       sweep_dir=tmp / "sweeps", pre213=pre213)
            self.assertEqual(rc, 0, out)
            for corner in summary["corners"]:
                for m in corner["metrics"].values():
                    self.assertEqual(m["verdict"], "EXACT")

    def test_real_extractor_catches_over_tolerance_perturbation(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            pre213 = REPO / "sim/lib/snm_extract.py"
            for cid in CORNERS:
                self._sigmoid_sweep(tmp / "sweeps" / cid / "read_snm_sweep.txt")
            rows = {}
            for i, cid in enumerate(CORNERS):
                vals = self._fleet_values(tmp, pre213, cid)
                if i == 1:
                    vals = dict(vals, read_snm_v=vals["read_snm_v"] + 50e-6)
                rows[cid] = vals
            record = tmp / "record.md"
            write_record(record, rows)
            reduced_rows = {cid: {"read_snm_v": 0.0} for cid in CORNERS}
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("read-snm", reduced_rows)))
            rc, _out, summary = run_cmp(tmp, "read-snm", reduced, record=record,
                                        sweep_dir=tmp / "sweeps", pre213=pre213)
            self.assertNotEqual(rc, 0)
            bad = summary["corners"][1]
            self.assertEqual(bad["status"], "MISMATCH")


class Household(unittest.TestCase):
    def test_reduced_family_must_match(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            record = tmp / "record.md"
            write_record(record, exact_record_rows("read-access", CORNERS))
            reduced = tmp / "reduced.json"
            reduced.write_text(json.dumps(make_reduced("write-margin", {})))
            rc, out, _ = run_cmp(tmp, "read-access", reduced, record=record)
            self.assertNotEqual(rc, 0)
            self.assertIn("not 'read-access'", out)

    def test_unknown_family_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            rc, out, _ = run_cmp(tmp, "no-such-family", tmp / "none.json")
            self.assertNotEqual(rc, 0)


def main() -> int:
    unittest.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
