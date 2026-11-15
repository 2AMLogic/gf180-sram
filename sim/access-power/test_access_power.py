#!/usr/bin/env python3
"""Offline tests for the access-energy grader in access_power.py (issue #329).

Builds synthetic `klt-sim-report.json`-shaped dicts -- no PDK, no ngspice, no
batch fleet -- so they run in CI. Pins down the fail-closed contract the
measured record depends on: 27/27 well-formed corners grade `PASS` and exit
`0`; a corner missing from the report, a duplicated corner, a `null`
measurement, a repeated measurement name, a read cycle that
returned the wrong word, or a corner outside the ratified matrix is reported
`OPEN` (exit `2`) and never silently dropped; a non-physical charge is `FAIL`
(exit `1`). Also pins the `E = Q x VDD` arithmetic and the sign convention,
since those are what the committed record's numbers mean.

Run: python3 sim/access-power/test_access_power.py   (or via `npm run test`)
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import access_power as ap  # noqa: E402  (path-injected import)

# The probe-measured tt/3.300V/25C charges (local single corner, 2026-11-14):
# raw `.meas ... INTEG i(vvdd)` is negative while VVDD supplies the circuit.
RAW_Q_WRITE = -8.54123e-11
RAW_Q_READ = -8.25659e-11

EXPECTED_WORD = 0xDEADBEEF


def corner(process, vdd, temp, q_write=RAW_Q_WRITE, q_read=RAW_Q_READ, word=EXPECTED_WORD):
    """One well-formed report corner: both charge integrals plus 32 Q probes."""
    meas = [
        {"name": "q_write", "value": q_write, "unit": "C", "status": "pass"},
        {"name": "q_read", "value": q_read, "unit": "C", "status": "pass"},
    ]
    for b in range(32):
        v = vdd if word is not None and (word >> b) & 1 else 0.0
        meas.append({"name": f"q{b}_rd", "value": v, "unit": "V", "status": "pass"})
    return {
        "corner_id": ap.corner_id(process, vdd, temp),
        "process": process,
        "supply_v": {"vvdd": vdd},
        "temperature_c": temp,
        "status": "pass",
        "measurements": meas,
    }


def full_report():
    """A 27/27 report over the ratified matrix, every corner well-formed."""
    return {"status": "pass", "corners": [corner(p, v, t) for p, v, t in ap.expected_corners()]}


def grade(report):
    """check_klt(report) -> (exit_code, [RESULT: lines])."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "klt-sim-report.json"
        path.write_text(json.dumps(report))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = ap.check_klt(str(path))
    return code, [ln for ln in buf.getvalue().splitlines() if ln.startswith("RESULT:")]


def line_for(lines, label):
    """The one RESULT: line naming `label`."""
    hits = [ln for ln in lines if f" {label} " in ln]
    assert len(hits) == 1, f"expected exactly one line for {label}, got {hits}"
    return hits[0]


class TestAllPass(unittest.TestCase):
    def test_27_well_formed_corners_pass(self):
        code, lines = grade(full_report())
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 28)  # 27 corners + the rollup
        self.assertEqual(sum(" PASS " in ln for ln in lines[:27]), 27)
        self.assertIn("access_power = PASS over 27 corners (0 open, 0 fail)", lines[-1])

    def test_energy_is_charge_times_that_corners_supply(self):
        _, lines = grade(full_report())
        # 85.41 pC x 3.30 V = 281.9 pJ; 85.41 pC x 2.97 V = 253.7 pJ.
        self.assertIn("e_write=281.9 pJ (q=85.41 pC)", line_for(lines, "tt/3.300V/25C"))
        self.assertIn("e_write=253.7 pJ (q=85.41 pC)", line_for(lines, "tt/2.970V/25C"))
        self.assertIn("vdd=3.63 V", line_for(lines, "ss/3.630V/125C"))

    def test_read_energy_reported_separately_from_write(self):
        _, lines = grade(full_report())
        self.assertIn("e_read=272.5 pJ (q=82.57 pC)", line_for(lines, "tt/3.300V/25C"))


class TestFailsClosed(unittest.TestCase):
    def test_missing_corner_is_open_not_dropped(self):
        rep = full_report()
        dropped = rep["corners"].pop(13)
        self.assertEqual(dropped["corner_id"], "tt/3.300V/25C")
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        self.assertEqual(len(lines), 28)  # the absent corner still gets a line
        self.assertIn("RESULT: tt/3.300V/25C OPEN (corner absent from report)", lines)
        self.assertIn("access_power = OPEN over 27 corners (1 open, 0 fail)", lines[-1])

    def test_26_corner_report_does_not_exit_zero(self):
        rep = full_report()
        rep["corners"].pop()
        self.assertEqual(len(rep["corners"]), 26)
        self.assertNotEqual(grade(rep)[0], 0)

    def test_null_charge_measurement_is_open(self):
        rep = full_report()
        rep["corners"][0] = corner("ff", 2.97, -40, q_write=None)
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        line = line_for(lines, "ff/2.970V/-40C")
        self.assertIn("OPEN", line)
        self.assertIn("q_write=unmeasured", line)
        self.assertNotIn("e_write=", line)

    def test_null_q_probe_is_open(self):
        rep = full_report()
        c = corner("ff", 2.97, -40)
        c["measurements"][5]["value"] = None
        rep["corners"][0] = c
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        self.assertIn("unmeasured_q_bits=1", line_for(lines, "ff/2.970V/-40C"))

    def test_wrong_read_word_is_open_and_carries_no_energy(self):
        rep = full_report()
        rep["corners"][0] = corner("ff", 2.97, -40, word=0xDEADBEEE)
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        line = line_for(lines, "ff/2.970V/-40C")
        self.assertIn("OPEN", line)
        self.assertIn("read_word=0xDEADBEEE expected=0xDEADBEEF", line)
        self.assertNotIn("e_write=", line)

    def test_undefined_q_level_is_open(self):
        rep = full_report()
        c = corner("ff", 2.97, -40)
        c["measurements"][2]["value"] = 1.5  # between 0.2*VDD and 0.8*VDD
        rep["corners"][0] = c
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        self.assertIn("undefined_q_bits=1", line_for(lines, "ff/2.970V/-40C"))

    def test_non_physical_charge_is_fail(self):
        rep = full_report()
        # A positive raw integral means the rail absorbed net charge over the
        # cycle: not a draw, so not an access energy.
        rep["corners"][0] = corner("ff", 2.97, -40, q_write=+8.5e-11)
        code, lines = grade(rep)
        self.assertEqual(code, 1)
        line = line_for(lines, "ff/2.970V/-40C")
        self.assertIn("FAIL", line)
        self.assertIn("non-physical", line)
        self.assertIn("access_power = FAIL", lines[-1])

    def test_zero_charge_is_fail(self):
        rep = full_report()
        rep["corners"][0] = corner("ff", 2.97, -40, q_read=0.0)
        self.assertEqual(grade(rep)[0], 1)

    def test_corner_outside_the_ratified_matrix_is_open(self):
        rep = full_report()
        rep["corners"].append(corner("tt", 3.00, 85))
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        self.assertIn("access_power = OPEN over 28 corners (1 open, 0 fail)", lines[-1])
        self.assertTrue(
            any("not in the ratified 27-point matrix" in ln for ln in lines),
            lines,
        )

    def test_duplicate_corner_is_open_whichever_copy_is_last(self):
        rep = full_report()
        # Bad copy first, good copy last -- exactly the order in which a
        # last-wins merge would silently keep the good one and exit 0.
        dup = [i for i, c in enumerate(rep["corners"]) if c["corner_id"] == "tt/3.300V/25C"]
        self.assertEqual(len(dup), 1)
        rep["corners"][dup[0]] = corner("tt", 3.30, 25, word=0xDEADBEEE)
        rep["corners"].append(corner("tt", 3.30, 25))
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        line = line_for(lines, "tt/3.300V/25C")
        self.assertIn("OPEN", line)
        self.assertIn("duplicate corner in report", line)
        self.assertNotIn("e_write=", line)
        self.assertIn("access_power = OPEN over 27 corners (1 open, 0 fail)", lines[-1])

    def test_duplicate_unexpected_corner_reports_the_duplication(self):
        rep = full_report()
        rep["corners"].append(corner("tt", 3.00, 85))
        rep["corners"].append(corner("tt", 3.00, 85))
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        self.assertIn("access_power = OPEN over 28 corners (1 open, 0 fail)", lines[-1])
        self.assertTrue(
            any("duplicate corner in report" in ln for ln in lines),
            lines,
        )

    def test_repeated_measurement_name_is_open_whichever_copy_is_last(self):
        rep = full_report()
        c = corner("ff", 2.97, -40)
        # A second q_write claim appended after the good one: a last-wins
        # grader would keep the good copy and grade this corner PASS.
        c["measurements"].append(
            {"name": "q_write", "value": None, "unit": "C", "status": "pass"}
        )
        rep["corners"][0] = c
        code, lines = grade(rep)
        self.assertEqual(code, 2)
        line = line_for(lines, "ff/2.970V/-40C")
        self.assertIn("OPEN", line)
        self.assertIn("q_write=unmeasured", line)
        self.assertNotIn("e_write=", line)

    def test_empty_report_is_27_open_rows(self):
        code, lines = grade({"status": "pass", "corners": []})
        self.assertEqual(code, 2)
        self.assertEqual(sum("corner absent from report" in ln for ln in lines), 27)


class TestGeneratorContract(unittest.TestCase):
    def test_windows_are_derived_from_the_macro_smoke_ops_table(self):
        import smoke

        wi = ap.op_index(ap.WRITE_LABEL)
        ri = ap.op_index(ap.READ_LABEL)
        self.assertEqual(ap.window(wi), (smoke.edge(wi), smoke.edge(wi) + smoke.PERIOD))
        self.assertEqual(smoke.OPS[ri][6], EXPECTED_WORD)

    def test_unknown_op_label_is_a_loud_failure(self):
        with self.assertRaises(SystemExit):
            ap.op_index("no such operation")

    def test_request_declares_the_27_point_matrix_and_both_integrals(self):
        import corner_matrix

        req = ap.klt_request()
        self.assertEqual(req["analysis"]["kind"], "tran")
        # The request's corners block is pinned against the matrix's single
        # owner, not against re-asserted literals -- so this test catches the
        # request drifting from the ratified matrix instead of pinning a
        # private copy of it.
        self.assertEqual(
            req["corners"]["process"],
            [
                {"name": p, "sections": [corner_matrix.LIB_SECTION[p]]}
                for p in corner_matrix.PROCESSES
            ],
        )
        self.assertEqual(
            req["corners"]["supply_v"]["vvdd"], [float(v) for v in corner_matrix.VDDS]
        )
        self.assertEqual(
            req["corners"]["temperature_c"], [int(t) for t in corner_matrix.TEMPS]
        )
        self.assertEqual(len(ap.expected_corners()), 27)
        names = [m["name"] for m in req["measurements"]]
        self.assertEqual(names[:2], ["q_write", "q_read"])
        self.assertEqual(len(names), 34)  # 2 integrals + 32 Q probes
        by_name = {m["name"]: m["spice"] for m in req["measurements"]}
        self.assertEqual(
            by_name["q_write"], ".meas tran q_write INTEG i(vvdd) FROM=25n TO=45n"
        )
        self.assertEqual(
            by_name["q_read"], ".meas tran q_read INTEG i(vvdd) FROM=65n TO=85n"
        )

    def test_body_is_the_macro_smoke_circuit_with_only_the_include_repointed(self):
        import smoke

        ours = [ln for ln in ap.gen_klt().splitlines() if not ln.startswith("*")]
        theirs = [ln for ln in smoke.gen_klt().splitlines() if not ln.startswith("*")]
        self.assertEqual(len(ours), len(theirs))
        diff = [(a, b) for a, b in zip(theirs, ours) if a != b]
        self.assertEqual(diff, [(ap.SMOKE_INCLUDE, ap.OUR_INCLUDE)])

    def test_committed_body_and_request_match_the_generator(self):
        here = Path(__file__).resolve().parent
        self.assertEqual(
            (here / "testbench" / "tb_access_power.klt.spice").read_text(), ap.gen_klt()
        )
        self.assertEqual(
            json.loads((here / "requests" / "access_power.json").read_text()),
            ap.klt_request(),
        )


if __name__ == "__main__":
    unittest.main()
