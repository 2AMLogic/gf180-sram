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

The MC-mode classes (`McDirectExactPerSample`, `McSnmPairPre213`) cover the
Monte Carlo increment the same way: exact per-sample index-ordered
comparison, the ctrl anchor against the deterministic record, a compacted
negative-control array with a differing errored count, the deck_sha256
absent/wrong/matching triple on the MC path, the 30 uV boundary per mm
sample, a missing sweep pair, and a seed-drift rejection -- all on tiny
hand-built fixtures. Stub results are contract checks, **not** physical
evidence.

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

import deck_adapter as da  # noqa: E402
import parity_compare as pc  # noqa: E402
import run_mc_campaign as mc_mod  # noqa: E402

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

    def test_unit_label_matches_family_unit(self):
        """The max-|delta| block labels each metric with its family's unit:
        seconds for the access-time families, volts for the others (#359)."""
        for family, metric, unit in (
            ("read-access", "read_access_time_s", "s"),
            ("write-margin", "write_trip_voltage_v", "V"),
        ):
            with self.subTest(family=family):
                with tempfile.TemporaryDirectory() as d:
                    tmp = Path(d)
                    rows = exact_record_rows(family, CORNERS)
                    record = tmp / "record.md"
                    write_record(record, rows)
                    reduced = tmp / "reduced.json"
                    reduced.write_text(json.dumps(make_reduced(family, rows)))
                    rc, out, summary = run_cmp(tmp, family, reduced, record=record)
                    self.assertEqual(rc, 0, out)
                    self.assertEqual(summary["unit"], unit)
                    self.assertIn(f"- `{metric}`: 0.000e+00 {unit} (gated)", out)
                    if family == "write-margin":
                        self.assertIn("- `write_vdd_v`: 0.000e+00 V\n", out)

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


# --------------------------------------------------------------------------
# MC mode (mc-build/mc-reduce parity) -- offline contract fixtures.
# --------------------------------------------------------------------------

MC_CORNERS = ["tt_25c_3.30v", "ff_125c_2.97v"]
SEED = 20260817
SIGMOID_SWEEP = """0.0 3.3e0
0.2 3.29e0
0.4 3.2e0
0.6 2.6e0
0.8 0.6e0
1.0 0.1e0
1.2 0.02e0
"""


def mc_request_dict(family, corners=MC_CORNERS, *, n=6, n_control=2, n_nc=3,
                    seed=SEED, nc_mismatch_scale=20.0, nc_vdd=None):
    """A stub mc-build request: same x_gf180_sram_adapter shape, tiny counts."""
    mode, key = da.MC_FAMILIES[family]
    kind, datafile, _label = da.parse_mc_mode(mode)
    pair = kind == "snm-pair"
    units = []
    for cid in corners:
        process, temp, vdd = cid.split("_")[0], cid.split("_")[1].rstrip("c"), cid.split("_")[2].rstrip("v")
        for kind_name, sw in (("mm", 1), ("ctrl", 0), ("nc", nc_mismatch_scale)):
            unit_vdd = nc_vdd if (kind_name == "nc" and nc_vdd is not None) else vdd
            for i in range({"mm": n, "ctrl": n_control, "nc": n_nc}[kind_name]):
                sides = ("L", "R") if pair else (None,)
                for side in sides:
                    k = f"{kind_name}-{side}" if side else kind_name
                    units.append({
                        "id": da.mc_unit_id(cid, kind_name, i, side),
                        "corner_id": cid, "process": process, "temp": temp, "vdd": unit_vdd,
                        "kind": kind_name, "index": i, "side": side,
                        "seed": mc_mod.derive_seed(seed, cid, k, i),
                        "sw_stat_mismatch": sw,
                    })
    composed = "c" * 64
    return {
        "engine": "ngspice", "decks": [], "options": {},
        "x_gf180_sram_adapter": {
            "campaign": "monte-carlo", "family": family, "mode": mode, "key": key,
            "testbench": "tb", "testbench_sha256": "0" * 64, "composed_deck_sha256": composed,
            "base_seed": seed, "corners": list(corners),
            "n_mismatch": n, "n_determinism_control": n_control, "n_negative_control": n_nc,
            "nc_mismatch_scale": nc_mismatch_scale, "nc_vdd": nc_vdd,
            "units": units,
        },
    }, composed


def write_mc_fixture_tree(tmp, request, composed, *, corner_inc_seeds=None,
                          sweep_values=None, unit_overrides=None):
    """Stage the returned-unit-tree side: corner.inc per unit (+ sweeps/stdout)."""
    meta = request["x_gf180_sram_adapter"]
    family = meta["family"]
    mode = meta["mode"]
    kind, datafile, label = da.parse_mc_mode(mode)
    outdir = tmp / "out"
    report_units = []
    for m in meta["units"]:
        uid = m["id"]
        unit = outdir / uid
        unit.mkdir(parents=True, exist_ok=True)
        seed = m["seed"]
        if corner_inc_seeds is not None and uid in corner_inc_seeds:
            seed = corner_inc_seeds[uid]
        (unit / "corner.inc").write_text(
            f"* corner: process={m['process']} seed={seed}\n.options seed={seed}\n"
        )
        u = {"id": uid, "status": "pass", "exit_code": 0, "timed_out": False,
             "duration_s": 0.1, "deck": "tb.spice", "deck_sha256": composed,
             "stdout": f"{uid}/stdout.bin", "stderr": f"{uid}/stderr.bin",
             "outputs": [datafile] if datafile else [], "missing_outputs": [],
             "host_resolved": [], "diagnostics": []}
        if unit_overrides:
            u.update(unit_overrides.get(uid, {}))
            if unit_overrides.get(uid, {}).get("deck_sha256", composed) is None:
                del u["deck_sha256"]
        report_units.append(u)
        if datafile:
            values = (sweep_values or {}).get(uid)
            if values is None:
                values = {"0.0 3.3\n0.5 2.6\n0.8 0.6\n1.2 0.02\n"}
            (unit / datafile).write_text(next(iter(values)) if isinstance(values, set) else values)
        (unit / "stdout.bin").write_text("")
        (unit / "stderr.bin").write_text("")
    report = {"mode": "decks", "units": report_units, "outdir": str(outdir),
              "status": "pass", "engine": "ngspice"}
    (tmp / "report.json").write_text(json.dumps(report))
    return outdir, report


def mc_results_for(family, m, *, ctrl_value=1.0):
    """The per-sample results dict a stub mc-reduce grading carries."""
    mode, key = da.MC_FAMILIES[family]
    kind, _datafile, label = da.parse_mc_mode(mode)
    if kind == "direct":
        vals = {key: ctrl_value}
        if key == "write_trip_voltage_v":
            vals["write_vdd_v"] = 3.3  # the record row's second metric
        return vals
    return {f"{label}_lobe_low_v": ctrl_value, f"{label}_lobe_high_v": ctrl_value,
            f"{label}_v": ctrl_value}


def mc_reduced_dict(family, request, *, ctrl_value=1.0, mm_values=None, nc_errored_ids=(),
                    mm_errored_indices=(), ctrl_values=None):
    """A stub mc-reduce --json-out grading for the stub request."""
    meta = request["x_gf180_sram_adapter"]
    key = meta["key"]
    n, n_ctrl, n_nc = meta["n_mismatch"], meta["n_determinism_control"], meta["n_negative_control"]
    batches = {}
    measurements = []
    for cid in meta["corners"]:
        per_kind = {}
        for kind_name, count in (("mm", n), ("ctrl", n_ctrl), ("nc", n_nc)):
            samples = []
            for i in range(count):
                units_for = [u for u in meta["units"]
                             if u["corner_id"] == cid and u["kind"] == kind_name and u["index"] == i]
                errs = []
                if kind_name == "mm" and i in mm_errored_indices:
                    errs = ["RESULT-ERROR: stub"]
                value = ctrl_value
                if kind_name == "mm" and mm_values:
                    value = mm_values[cid][i]
                if kind_name == "ctrl" and ctrl_values:
                    value = ctrl_values[cid][i]
                if kind_name == "nc" and any(u["index"] == i for u in units_for
                                             if u["id"] in nc_errored_ids):
                    errs = ["RESULT-ERROR: nc stub"]
                samples.append((i, mc_results_for(family, units_for[0], ctrl_value=value), errs))
            per_kind[kind_name] = {"seed_labels": [str(u["seed"]) for u in meta["units"]
                                                   if u["corner_id"] == cid and u["kind"] == kind_name],
                                   "samples": samples}
        batches[cid] = per_kind
        mm_tally = [v for i, v in enumerate((mm_values or {}).get(cid, [ctrl_value] * n))
                    if i not in mm_errored_indices]
        measurement = {"name": f"{key}@{cid}", "unit": "V", "samples": mm_tally,
                       "errored": len(mm_errored_indices), "limits": {"min": 0.0},
                       "source_corners": [cid]}
        measurement["negative_control"] = {
            "samples": [ctrl_value] * (n_nc - len([i for i in range(n_nc)
                                                   if any(u["index"] == i for u in meta["units"]
                                                          if u["corner_id"] == cid and u["kind"] == "nc"
                                                          and u["id"] in nc_errored_ids)])),
            "errored": len(nc_errored_ids) // len(meta["corners"]),
            "description": "stub nc",
        }
        measurements.append(measurement)
    return {"family": family, "mode": meta["mode"], "key": key,
            "expected_units": len(meta["units"]), "coverage_errors": [],
            "infra_failures": [], "batches": batches, "measurements": measurements,
            "overall": "recorded"}


def mc_sample_set_dict(family, request, *, mm_values=None, nc_errored=0,
                       nc_samples=None, ctrl_note=None):
    """The committed-sample-set side: klt yield document shape, tiny counts."""
    meta = request["x_gf180_sram_adapter"]
    key = meta["key"]
    n, n_nc = meta["n_mismatch"], meta["n_negative_control"]
    measurements = []
    for cid in meta["corners"]:
        measurements.append({
            "name": f"{key}@{cid}", "unit": "V",
            "samples": (mm_values or {}).get(cid, [1.0] * n),
            "errored": 0, "limits": {"min": 0.0}, "source_corners": [cid],
            "negative_control": {
                "samples": nc_samples.get(cid, [1.0] * (n_nc - nc_errored)),
                "errored": nc_errored, "description": ctrl_note or "stub nc",
            },
        })
    return {"measurements": measurements, "provenance": {"seed": meta["base_seed"], "key": key}}


def run_cmp_mc(tmp, family, reduced, *, request, report, samples, record,
               sweep_dir=None, pre213=None, tolerance=None, unit_dir=None):
    cmd = [sys.executable, str(CMP), "mc", family, str(reduced),
           "--request", str(request), "--report", str(report),
           "--samples", str(samples), "--record", str(record)]
    if sweep_dir:
        cmd += ["--sweep-dir", str(sweep_dir)]
    if pre213:
        cmd += ["--pre213", str(pre213)]
    if unit_dir:
        cmd += ["--unit-dir", str(unit_dir)]
    if tolerance is not None:
        cmd += ["--tolerance-v", str(tolerance)]
    json_out = tmp / "summary.json"
    cmd += ["--json-out", str(json_out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    summary = json.loads(json_out.read_text()) if json_out.is_file() else None
    return proc.returncode, proc.stdout + proc.stderr, summary


class McDirectExactPerSample(unittest.TestCase):
    """write-margin: deterministic per-sample exact comparison, in index order."""

    def _fixture(self, tmp, mm_fleet=None, mm_committed=None, ctrl_value=1.91003,
                 nc_errored_ids=(), nc_fleet_errored=0, nc_committed_errored=0):
        family = "write-margin"
        request, composed = mc_request_dict(family)
        n = request["x_gf180_sram_adapter"]["n_mismatch"]
        mm_committed = mm_committed if mm_committed is not None else [0.5 + 0.001 * i for i in range(n)]
        mm_fleet = mm_fleet if mm_fleet is not None else list(mm_committed)
        reduced = mc_reduced_dict(family, request, mm_values={
            c: mm_fleet for c in request["x_gf180_sram_adapter"]["corners"]},
            ctrl_values={c: [ctrl_value] * 2 for c in request["x_gf180_sram_adapter"]["corners"]},
            nc_errored_ids=nc_errored_ids)
        n_nc = request["x_gf180_sram_adapter"]["n_negative_control"]
        ss = mc_sample_set_dict(family, request, mm_values={
            c: mm_committed for c in request["x_gf180_sram_adapter"]["corners"]},
            nc_samples={c: [0.9] * (n_nc - nc_committed_errored) for c in request["x_gf180_sram_adapter"]["corners"]},
            nc_errored=nc_committed_errored)
        write_mc_fixture_tree(tmp, request, composed)
        # nc committed values must equal the stub reduced nc values (ctrl_value)
        for m in ss["measurements"]:
            m["negative_control"]["samples"] = [ctrl_value] * len(m["negative_control"]["samples"])
        for cid, per in reduced["batches"].items():
            per["nc"] = {"seed_labels": per["nc"]["seed_labels"],
                         "samples": [(i, mc_results_for(family, {"id": ""}, ctrl_value=ctrl_value),
                                      ["RESULT-ERROR: nc"] if i == 0 and nc_fleet_errored else [])
                                     for i, _r, _e in per["nc"]["samples"]]}
        (tmp / "request.json").write_text(json.dumps(request))
        (tmp / "reduced.json").write_text(json.dumps(reduced))
        (tmp / "samples.json").write_text(json.dumps(ss))
        record = tmp / "record.md"
        write_record(record, {c: {"write_trip_voltage_v": ctrl_value, "write_vdd_v": 3.3}
                              for c in request["x_gf180_sram_adapter"]["corners"]})
        return request, reduced, ss, record

    def test_exact_match_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            rc, out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                          request=tmp / "request.json", report=tmp / "report.json",
                                          samples=tmp / "samples.json", record=record)
            self.assertEqual(rc, 0, out)
            self.assertEqual(summary["overall"], "parity")
            self.assertEqual(summary["deck_sha256"]["errors"], [])
            self.assertEqual(summary["seed_identity"]["errors"], [])
            mm = summary["corners"][0]["mismatch"]
            self.assertEqual(mm["n_compared"], mm["n_expected"])
            self.assertEqual(mm["deltas"]["max"], 0.0)
            self.assertIn("**Overall: parity**", out)

    def test_mc_distribution_lines_read_summary_unit(self):
        """The per-sample |delta| distribution lines label all four stats with
        summary["unit"], not a literal V (#378). A seconds unit proves the key
        is read; the unmutated write-margin summary proves volts still render.
        No MC_SAMPLE_SETS binding is added or asserted: the renderer is a pure
        function of the summary dict."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            rc, out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                          request=tmp / "request.json", report=tmp / "report.json",
                                          samples=tmp / "samples.json", record=record)
            self.assertEqual(rc, 0, out)

            # Volts no-regression: a real write-margin summary renders V on
            # both the mismatch-batch and negative-control distribution lines
            # of every corner.
            rendered = pc.render_mc_markdown(summary)
            dist_lines = [ln for ln in rendered.splitlines()
                          if "per-sample |delta| distribution" in ln]
            self.assertEqual(len(dist_lines), 2 * len(summary["corners"]), rendered)
            for ln in dist_lines:
                self.assertRegex(ln, r"max=\S+ V, mean=\S+ V, p50=\S+ V, p95=\S+ V$")

            # Unit read: the renderer reads summary["unit"] for the same lines.
            summary["unit"] = "s"
            rendered_s = pc.render_mc_markdown(summary)
            dist_lines_s = [ln for ln in rendered_s.splitlines()
                            if "per-sample |delta| distribution" in ln]
            self.assertEqual(len(dist_lines_s), 2 * len(summary["corners"]), rendered_s)
            for ln in dist_lines_s:
                self.assertNotIn(" V,", ln)
                self.assertRegex(ln, r"max=\S+ s, mean=\S+ s, p50=\S+ s, p95=\S+ s$")

            # Guards unmoved: a corner with no mm deltas and no nc deltas
            # still renders, without a distribution line.
            for c in summary["corners"]:
                (c.get("mismatch") or {}).pop("deltas", None)
                (c.get("negative_control") or {}).pop("deltas", None)
            rendered_nod = pc.render_mc_markdown(summary)
            self.assertNotIn("per-sample |delta| distribution", rendered_nod)

    def test_wrong_value_at_one_index_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            n = request["x_gf180_sram_adapter"]["n_mismatch"]
            mm_fleet = [0.5 + 0.001 * i for i in range(n)]
            mm_fleet[3] += 1e-3
            for c in request["x_gf180_sram_adapter"]["corners"]:
                for i, (idx, results, errs) in enumerate(reduced["batches"][c]["mm"]["samples"]):
                    reduced["batches"][c]["mm"]["samples"][i] = (idx, dict(results, write_trip_voltage_v=mm_fleet[idx]), errs)
            (tmp / "reduced.json").write_text(json.dumps(reduced))
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["overall"], "MISMATCH")
            self.assertTrue(any("mm sample 3" in r for c in summary["corners"] for r in c["reasons"]))

    def test_reordered_samples_fail(self):
        """Index order matters: a rotated array is not parity."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            n = request["x_gf180_sram_adapter"]["n_mismatch"]
            rotated = [(0.5 + 0.001 * ((i + 1) % n)) for i in range(n)]
            for c in request["x_gf180_sram_adapter"]["corners"]:
                for i, (idx, results, errs) in enumerate(reduced["batches"][c]["mm"]["samples"]):
                    reduced["batches"][c]["mm"]["samples"][i] = (idx, dict(results, write_trip_voltage_v=rotated[idx]), errs)
            (tmp / "reduced.json").write_text(json.dumps(reduced))
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)

    def test_errored_mm_sample_is_open_not_parity(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            for c in request["x_gf180_sram_adapter"]["corners"]:
                samples = reduced["batches"][c]["mm"]["samples"]
                reduced["batches"][c]["mm"]["samples"][2] = (2, {}, ["RESULT-ERROR: bistable"])
                reduced["measurements"][0 if c == request["x_gf180_sram_adapter"]["corners"][0] else 1]["errored"] = 1
                reduced["measurements"][0 if c == request["x_gf180_sram_adapter"]["corners"][0] else 1]["samples"] = [
                    v for (i, r, e) in samples if i != 2 for v in [r["write_trip_voltage_v"]]]
            reduced["overall"] = "OPEN"
            (tmp / "reduced.json").write_text(json.dumps(reduced))
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["overall"], "OPEN")
            self.assertTrue(any("mm sample 2" in r for c in summary["corners"] for r in c["reasons"]))

    def test_ctrl_not_pinned_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            for c in request["x_gf180_sram_adapter"]["corners"]:
                samples = reduced["batches"][c]["ctrl"]["samples"]
                reduced["batches"][c]["ctrl"]["samples"][1] = (
                    samples[1][0], dict(samples[1][1], write_trip_voltage_v=1.5), samples[1][2])
            (tmp / "reduced.json").write_text(json.dumps(reduced))
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["overall"], "MISMATCH")
            self.assertTrue(any("not pinned" in r for c in summary["corners"] for r in c["reasons"]))

    def test_ctrl_anchor_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp, ctrl_value=1.91003)
            for c in request["x_gf180_sram_adapter"]["corners"]:
                for i, (idx, results, errs) in enumerate(reduced["batches"][c]["ctrl"]["samples"]):
                    reduced["batches"][c]["ctrl"]["samples"][i] = (
                        idx, dict(results, write_trip_voltage_v=results["write_trip_voltage_v"] + 1e-3), errs)
            (tmp / "reduced.json").write_text(json.dumps(reduced))
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)
            self.assertTrue(any("ctrl write_trip_voltage_v" in r
                                for c in summary["corners"] for r in c["reasons"]))

    def test_negative_control_errored_count_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp, nc_errored_ids=(
                "mc.tt_25c_3.30v.nc.00000",), nc_fleet_errored=1, nc_committed_errored=2)
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)
            self.assertTrue(any("errored-count mismatch" in r
                                for c in summary["corners"] for r in c["reasons"]))

    def test_deck_sha_absent_or_wrong_fails_on_mc_path(self):
        for sha_value in (None, "d" * 64):
            with tempfile.TemporaryDirectory() as d:
                tmp = Path(d)
                request, reduced, ss, record = self._fixture(tmp)
                overrides = {}
                if sha_value is None:
                    overrides = {u["id"]: {"deck_sha256": None}
                                 for u in request["x_gf180_sram_adapter"]["units"][:1]}
                else:
                    overrides = {u["id"]: {"deck_sha256": sha_value}
                                 for u in request["x_gf180_sram_adapter"]["units"][:1]}
                write_mc_fixture_tree(tmp, request, request["x_gf180_sram_adapter"]["composed_deck_sha256"],
                                      unit_overrides=overrides)
                rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                               request=tmp / "request.json", report=tmp / "report.json",
                                               samples=tmp / "samples.json", record=record)
                self.assertNotEqual(rc, 0)
                self.assertEqual(len(summary["deck_sha256"]["errors"]), 1)
                self.assertIn("absent" if sha_value is None else "differs",
                              summary["deck_sha256"]["errors"][0])

    def test_nc_engine_deaths_with_matching_counts_stay_parity(self):
        """nc units that die on both sides (committed errored count matches)
        are reported OPEN with reasons but do not break parity."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            family = "write-margin"
            corners = request["x_gf180_sram_adapter"]["corners"]
            dead = {f"mc.{corners[0]}.nc.00000", f"mc.{corners[1]}.nc.00001"}
            for c in corners:
                per = reduced["batches"][c]["nc"]["samples"]
                reduced["batches"][c]["nc"]["samples"] = [
                    (i, ({} if f"mc.{c}.nc.{i:05d}" in dead else r),
                     ["exit without RESULT"] if f"mc.{c}.nc.{i:05d}" in dead else e)
                    for i, r, e in per
                ]
            reduced["infra_failures"] = [{"id": uid, "reason": "declared outputs missing"}
                                         for uid in sorted(dead)]
            reduced["overall"] = "OPEN"
            n_nc = request["x_gf180_sram_adapter"]["n_negative_control"]
            for k, c in enumerate(corners):
                reduced["measurements"][k]["negative_control"]["errored"] = 1
                reduced["measurements"][k]["negative_control"]["samples"] = \
                    [1.91003] * (n_nc - 1)
            for m in ss["measurements"]:
                m["negative_control"]["errored"] = 1
                m["negative_control"]["samples"] = [1.91003] * (n_nc - 1)
            (tmp / "reduced.json").write_text(json.dumps(reduced))
            (tmp / "samples.json").write_text(json.dumps(ss))
            rc, out, summary = run_cmp_mc(tmp, family, tmp / "reduced.json",
                                          request=tmp / "request.json", report=tmp / "report.json",
                                          samples=tmp / "samples.json", record=record)
            self.assertEqual(rc, 0, out)
            self.assertEqual(summary["overall"], "parity")
            nc0 = summary["corners"][0]["negative_control"]
            self.assertEqual(nc0["errored_fleet"], nc0["errored_committed"])
            self.assertTrue(nc0["open_units"])
            self.assertIn("never counted as parity", out)

    def test_nc_engine_deaths_with_mismatched_counts_fail(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            corners = request["x_gf180_sram_adapter"]["corners"]
            dead = {f"mc.{corners[0]}.nc.00000", f"mc.{corners[0]}.nc.00001"}
            for c in corners:
                per = reduced["batches"][c]["nc"]["samples"]
                reduced["batches"][c]["nc"]["samples"] = [
                    (i, ({} if f"mc.{c}.nc.{i:05d}" in dead else r),
                     ["exit without RESULT"] if f"mc.{c}.nc.{i:05d}" in dead else e)
                    for i, r, e in per
                ]
            reduced["infra_failures"] = [{"id": uid, "reason": "declared outputs missing"}
                                         for uid in sorted(dead)]
            reduced["overall"] = "OPEN"
            # committed recorded only ONE errored draw per corner: a finding
            n_nc = request["x_gf180_sram_adapter"]["n_negative_control"]
            for k, c in enumerate(corners):
                reduced["measurements"][k]["negative_control"]["errored"] = 1
                reduced["measurements"][k]["negative_control"]["samples"] = [1.91003] * (n_nc - 1)
            for m in ss["measurements"]:
                m["negative_control"]["errored"] = 1
                m["negative_control"]["samples"] = [1.91003] * (n_nc - 1)
            (tmp / "reduced.json").write_text(json.dumps(reduced))
            (tmp / "samples.json").write_text(json.dumps(ss))
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)
            self.assertTrue(any("errored-count mismatch" in r
                                for c in summary["corners"] for r in c["reasons"]))

    def test_mm_infra_failure_breaks_parity(self):
        """An infra failure on an mm unit is parity-breaking, unlike nc."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            corners = request["x_gf180_sram_adapter"]["corners"]
            dead = f"mc.{corners[0]}.mm.00002"
            per = reduced["batches"][corners[0]]["mm"]["samples"]
            reduced["batches"][corners[0]]["mm"]["samples"] = [
                (i, ({} if i == 2 else r), ["exit without RESULT"] if i == 2 else e)
                for i, r, e in per
            ]
            reduced["infra_failures"] = [{"id": dead, "reason": "declared outputs missing"}]
            reduced["overall"] = "OPEN"
            reduced["measurements"][0]["errored"] = 1
            reduced["measurements"][0]["samples"] = [
                r["write_trip_voltage_v"] for i, r, _e in per if i != 2]
            (tmp / "reduced.json").write_text(json.dumps(reduced))
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["overall"], "OPEN")
            self.assertTrue(any("mm sample 2" in r
                                for c in summary["corners"] for r in c["reasons"]))

    def test_seed_drift_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, reduced, ss, record = self._fixture(tmp)
            drifted = {request["x_gf180_sram_adapter"]["units"][0]["id"]: 42}
            write_mc_fixture_tree(tmp, request, request["x_gf180_sram_adapter"]["composed_deck_sha256"],
                                  corner_inc_seeds=drifted)
            rc, _out, summary = run_cmp_mc(tmp, "write-margin", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record)
            self.assertNotEqual(rc, 0)
            self.assertEqual(len(summary["seed_identity"]["errors"]), 1)
            self.assertIn("seed drift", summary["seed_identity"]["errors"][0])
            self.assertIn("derive_seed says", summary["seed_identity"]["errors"][0])


PAIR_EXTRACTOR = """#!/usr/bin/env python3
# Stub pre-#213 extractor: --pair mode, reports the mean of both curves' last
# y values scaled by the LABEL_SCALE env var (default 1.0), as <label>_v plus
# two lobe intermediates.
import os, sys
args = sys.argv[1:]
assert args and args[0] == "--pair", "pair mode only"
_, path_l, path_r, label = args
def last_y(path):
    ys = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    ys.append(float(parts[1]))
                except ValueError:
                    pass
    return ys[-1]
scale = float(os.environ.get("LABEL_SCALE", "1.0"))
v = (last_y(path_l) + last_y(path_r)) / 2 * scale
print(f"RESULT: {label}_lobe_low_v = {v:.6f}")
print(f"RESULT: {label}_lobe_high_v = {v:.6f}")
print(f"RESULT: {label}_v = {v:.6f}")
"""


class McSnmPairPre213(unittest.TestCase):
    """read-snm through the --pair extractor: tolerance-gated, per sample."""

    def _fixture(self, tmp, *, committed_v=0.5, fleet_scale=1.0, drop_sweep_for=(),
                 ctrl_committed=0.5):
        family = "read-snm"
        request, composed = mc_request_dict(family)
        meta = request["x_gf180_sram_adapter"]
        n = meta["n_mismatch"]
        # committed sample-set values at committed_v; the stub extractor reads
        # a sweep tail of 0.5 and multiplies by LABEL_SCALE
        mm_committed = [committed_v] * n
        reduced = mc_reduced_dict(family, request, mm_values={c: [0.4] * n for c in meta["corners"]},
                                  ctrl_values={c: [0.4] * 2 for c in meta["corners"]})
        ss = mc_sample_set_dict(family, request, mm_values={c: mm_committed for c in meta["corners"]},
                                nc_samples={c: [committed_v] * (meta["n_negative_control"]) for c in meta["corners"]})
        sweep_values = {}
        for u in meta["units"]:
            tail = 1.0  # (1.0 + 1.0)/2 = 1.0 -> x LABEL_SCALE
            sweep_values[u["id"]] = f"0.0 3.3\n0.5 0.9\n0.8 {tail}\n"
        outdir, _report = write_mc_fixture_tree(tmp, request, composed, sweep_values=sweep_values,
                                                unit_overrides={uid: {"deck_sha256": None}
                                                                for uid in ()})
        for uid in drop_sweep_for:
            datafile = "read_snm_sweep.txt"
            p = outdir / uid / datafile
            if p.is_file():
                p.unlink()
        pre213 = tmp / "pre213.py"
        pre213.write_text(PAIR_EXTRACTOR)
        (tmp / "request.json").write_text(json.dumps(request))
        (tmp / "reduced.json").write_text(json.dumps(reduced))
        (tmp / "samples.json").write_text(json.dumps(ss))
        record = tmp / "record.md"
        write_record(record, {c: {"read_snm_lobe_low_v": ctrl_committed,
                                  "read_snm_lobe_high_v": ctrl_committed,
                                  "read_snm_v": ctrl_committed}
                              for c in meta["corners"]})
        return request, record, pre213

    def test_exact_match_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, record, pre213 = self._fixture(tmp)  # tail 1.0 -> v 1.0
            # committed all 1.0 so the stub extractor's 1.0 matches exactly
            ss = json.loads((tmp / "samples.json").read_text())
            for m in ss["measurements"]:
                m["samples"] = [1.0] * len(m["samples"])
                m["negative_control"]["samples"] = [1.0] * len(m["negative_control"]["samples"])
            (tmp / "samples.json").write_text(json.dumps(ss))
            record_path = tmp / "record2.md"
            write_record(record_path, {c: {"read_snm_lobe_low_v": 1.0,
                                           "read_snm_lobe_high_v": 1.0,
                                           "read_snm_v": 1.0}
                                       for c in request["x_gf180_sram_adapter"]["corners"]})
            rc, out, summary = run_cmp_mc(tmp, "read-snm", tmp / "reduced.json",
                                          request=tmp / "request.json", report=tmp / "report.json",
                                          samples=tmp / "samples.json", record=record_path,
                                          sweep_dir=tmp / "out", pre213=pre213)
            self.assertEqual(rc, 0, out)
            self.assertEqual(summary["overall"], "parity")
            self.assertEqual(summary["corners"][0]["mismatch"]["deltas"]["max"], 0.0)

    def test_tolerance_boundary_30uv_passes_31uv_fails(self):
        for scale, expect_pass in (("1.00003", True), ("1.000031", False)):
            with tempfile.TemporaryDirectory() as d:
                tmp = Path(d)
                request, record, pre213 = self._fixture(tmp)
                ss = json.loads((tmp / "samples.json").read_text())
                for m in ss["measurements"]:
                    m["samples"] = [1.0] * len(m["samples"])
                    m["negative_control"]["samples"] = [1.0] * len(m["negative_control"]["samples"])
                (tmp / "samples.json").write_text(json.dumps(ss))
                record_path = tmp / "record2.md"
                write_record(record_path, {c: {"read_snm_lobe_low_v": 1.0,
                                               "read_snm_lobe_high_v": 1.0,
                                               "read_snm_v": 1.0}
                                           for c in request["x_gf180_sram_adapter"]["corners"]})
                env_extractor = tmp / "pre213_env.py"
                env_extractor.write_text(
                    PAIR_EXTRACTOR.replace('os.environ.get("LABEL_SCALE", "1.0")',
                                           repr(scale))
                )
                rc, out, summary = run_cmp_mc(tmp, "read-snm", tmp / "reduced.json",
                                              request=tmp / "request.json", report=tmp / "report.json",
                                              samples=tmp / "samples.json", record=record_path,
                                              sweep_dir=tmp / "out", pre213=env_extractor)
                if expect_pass:
                    self.assertEqual(rc, 0, out)
                    self.assertEqual(summary["overall"], "parity")
                else:
                    self.assertNotEqual(rc, 0)
                    self.assertEqual(summary["overall"], "OPEN")
                    self.assertTrue(any("exceeds" in r for c in summary["corners"] for r in c["reasons"]))

    def test_missing_sweep_pair_is_open(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            request, record, pre213 = self._fixture(tmp)
            corners = request["x_gf180_sram_adapter"]["corners"]
            ss = json.loads((tmp / "samples.json").read_text())
            for m in ss["measurements"]:
                m["samples"] = [1.0] * len(m["samples"])
                m["negative_control"]["samples"] = [1.0] * len(m["negative_control"]["samples"])
            (tmp / "samples.json").write_text(json.dumps(ss))
            record_path = tmp / "record2.md"
            write_record(record_path, {c: {"read_snm_lobe_low_v": 1.0,
                                           "read_snm_lobe_high_v": 1.0,
                                           "read_snm_v": 1.0}
                                       for c in corners})
            rc, out, summary = run_cmp_mc(tmp, "read-snm", tmp / "reduced.json",
                                          request=tmp / "request.json", report=tmp / "report.json",
                                          samples=tmp / "samples.json", record=record_path,
                                          sweep_dir=tmp / "out", pre213=pre213)
            self.assertEqual(rc, 0, out)
            # now drop one mm sample's L sweep: that sample is OPEN, not parity
            unit_id = f"mc.{corners[0]}.mm.00001.L"
            (tmp / "out" / unit_id / "read_snm_sweep.txt").unlink()
            rc, _out, summary = run_cmp_mc(tmp, "read-snm", tmp / "reduced.json",
                                           request=tmp / "request.json", report=tmp / "report.json",
                                           samples=tmp / "samples.json", record=record_path,
                                           sweep_dir=tmp / "out", pre213=pre213)
            self.assertNotEqual(rc, 0)
            self.assertEqual(summary["overall"], "OPEN")
            self.assertTrue(any("sweep pair not found" in r
                                for c in summary["corners"] for r in c["reasons"]))


def main() -> int:
    unittest.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
