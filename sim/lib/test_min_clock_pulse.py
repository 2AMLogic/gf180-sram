#!/usr/bin/env python3
"""Offline contract tests for sim/min-clock-pulse/pulse.py (#328).

No ngspice, no PDK, no fleet. The fixture reports under
sim/min-clock-pulse/testdata/ are hand-built STUBS in the real klt-sim-report
shape (their scenario table is in that directory's generator header): they
exercise the grader's contract -- per-corner VDD bit definedness, OPEN vs
FAIL, the fold rule (smallest passing width with no failing or unmeasured
width above it), the >= max-grid and pass-island sentinels -- not physical
evidence, and no fixture result may be quoted as a measurement.

Two pins beyond the grader:
- the derived stimulus constants (PERIOD == high + low, SAMPLE < high,
  SETUP < low) hold at every grid point, so the macro-smoke stimulus
  confound cannot silently return;
- the generated (10, 10) body is line-for-line smoke.py's committed
  `tb_macro_write_read.klt.spice` modulo comment lines, so the 10/10 ns
  variant is provably the same bench as the ratified baseline.

Run: python3 sim/lib/test_min_clock_pulse.py   (or via `npm run test`)
"""
from __future__ import annotations

import io
import json
import contextlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB.parent / "macro-smoke"))
sys.path.insert(0, str(LIB.parent / "min-clock-pulse"))

import corner_matrix as cm  # noqa: E402
import pulse  # noqa: E402
import smoke  # noqa: E402
from repo_root import find_repo_root  # noqa: E402

REPO = find_repo_root(Path(__file__))
FIXTURES = REPO / "sim/min-clock-pulse/testdata"
MACRO_SMOKE_BODY = REPO / "sim/macro-smoke/testbench/tb_macro_write_read.klt.spice"

# corner_id -> (high-axis display, low-axis display) the fold must report for
# the committed fixture set (scenario table in testdata's generator header).
EXPECTED_FOLD = {
    "tt_25c_3.30v": ("4 ns", "4 ns"),
    "ff_-40c_2.97v": ("8 ns", ">= 10 ns"),
    "ss_125c_2.97v": ("OPEN", ">= 10 ns"),
    "ff_125c_3.63v": ("10 ns", "8 ns"),
    "ss_-40c_3.63v": ("OPEN", "4 ns"),
    "tt_125c_2.97v": ("4 ns", "4 ns"),
    "tt_-40c_3.63v": ("OPEN", "OPEN"),
}


def fixture(tag: str) -> dict:
    return json.loads((FIXTURES / f"fixture_min_clk_{tag}.json").read_text())


def content_lines(path: Path) -> list[str]:
    """A generated body minus comment/blank lines (the generated part)."""
    return [l for l in path.read_text().splitlines() if l.strip() and not l.lstrip().startswith("*")]


class DerivedConstantsTest(unittest.TestCase):
    """The stimulus-confound guard: every grid point derives its own constants."""

    def test_relationships_hold_everywhere(self):
        for high, low in pulse.grid_points():
            d = pulse.derived(high, low)
            self.assertEqual(d["PERIOD"], high + low, f"h{high:g}_l{low:g} PERIOD")
            self.assertLess(d["SAMPLE"], high, f"h{high:g}_l{low:g}: SAMPLE must sit inside the high phase")
            self.assertGreater(d["SAMPLE"], 0.0, f"h{high:g}_l{low:g}: SAMPLE must be positive")
            self.assertLess(d["SETUP"], low, f"h{high:g}_l{low:g}: SETUP must sit inside the low phase")
            self.assertGreater(d["SETUP"], 0.0, f"h{high:g}_l{low:g}: SETUP must be positive")

    def test_grid_shape(self):
        """Two 1-D sweeps sharing the 10/10 baseline: 9 variants, not 10, and
        the high axis brackets above 10 ns (to 14 ns) per the second verified
        correction -- the control chain at ss_125c_2.97v already needs
        7.78-8.68 ns of the high phase."""
        self.assertEqual(len(pulse.grid_points()), 9)
        self.assertEqual(len({pulse.variant_tag(*p) for p in pulse.grid_points()}), 9)
        self.assertEqual(max(pulse.CLK_HIGH_GRID), 14.0)
        self.assertEqual(pulse.derived(10.0, 10.0), {"PERIOD": 20.0, "SAMPLE": 9.0, "SETUP": 6.0})
        self.assertEqual(pulse.derived(4.0, 4.0), {"PERIOD": 8.0, "SAMPLE": 3.0, "SETUP": 3.0})


class OPSSharedWithSmokeTest(unittest.TestCase):
    """The OPS table and reduced_array are imported from smoke.py, not
    copied (since #405; the access_power.py pattern).

    Decision: keep test_ops_table_identical / test_reduced_array_identical
    as cheap anchors -- they fail loudly if a local copy is ever
    reintroduced. Folding them into the gen_klt body pin was rejected:
    that pin does not cover the OPS table or reduced_array() directly."""

    def test_ops_table_identical(self):
        self.assertEqual(pulse.OPS, smoke.OPS)

    def test_reduced_array_identical(self):
        a, b = [], []
        pulse.reduced_array(a.append)
        smoke.reduced_array(b.append)
        self.assertEqual(a, b)

    def test_h10_l10_body_is_the_macro_smoke_bench(self):
        """At (10, 10) the derived constants reproduce smoke.py's fixed ones,
        so the generated body must equal the committed baseline body except
        for its header comments."""
        mine = content_lines(REPO / "sim/min-clock-pulse/testbench/tb_min_clk_h10_l10.klt.spice")
        theirs = content_lines(MACRO_SMOKE_BODY)
        self.assertEqual(mine, theirs)
        # and the generated function itself, in a scratch tree
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "body.spice"
            p.write_text(pulse.gen_klt(10.0, 10.0))
            self.assertEqual(content_lines(p), theirs)


class GenKltTest(unittest.TestCase):
    """gen-klt writes the whole 9-point grid, idempotently."""

    def test_gen_all_writes_grid_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tb1, rq1 = Path(tmp) / "a" / "testbench", Path(tmp) / "a" / "requests"
            with contextlib.chdir(Path(tmp)):
                pulse.gen_all(tb1, rq1)
            bodies = sorted(p.name for p in tb1.glob("tb_min_clk_*.klt.spice"))
            reqs = sorted(p.name for p in rq1.glob("min_clk_*.json"))
            self.assertEqual(len(bodies), 9)
            self.assertEqual(len(reqs), 9)
            self.assertEqual(
                bodies, sorted(f"tb_min_clk_{pulse.variant_tag(h, l)}.klt.spice" for h, l in pulse.grid_points())
            )
            self.assertTrue((tb1 / pulse.DUT_COPY).exists())
            for h, l in pulse.grid_points():
                tag = pulse.variant_tag(h, l)
                req = json.loads((rq1 / f"min_clk_{tag}.json").read_text())
                self.assertEqual(req["netlist"], f"../testbench/tb_min_clk_{tag}.klt.spice")
            # second run: byte-identical (idempotency is the committed-files contract)
            tb2, rq2 = Path(tmp) / "b" / "testbench", Path(tmp) / "b" / "requests"
            pulse.gen_all(tb2, rq2)
            for d1, d2, pat in ((tb1, tb2, "*.spice"), (rq1, rq2, "*.json")):
                for p1 in sorted(d1.glob(pat)):
                    p2 = d2 / p1.name
                    self.assertTrue(p2.exists(), p1.name)
                    self.assertEqual(p1.read_bytes(), p2.read_bytes(), p1.name)

    def test_request_tracks_period(self):
        """Every .meas AT is this variant's edge(i)+SAMPLE and the tran ends
        at edge(9)+PERIOD -- the absolute times move with the swept pair."""
        n_ops = len(pulse.OPS)
        sampled = [i for i, o in enumerate(pulse.OPS) if o[6] is not None]
        for high, low in pulse.grid_points():
            tag = pulse.variant_tag(high, low)
            req = pulse.klt_request(high, low)
            d = pulse.derived(high, low)
            ats = set()
            for m in req["measurements"]:
                at = float(re.search(r"AT=([0-9.]+)n", m["spice"]).group(1))
                i = int(re.search(r"_op(\d+)$", m["name"]).group(1))
                self.assertEqual(at, pulse.edge(i, d["PERIOD"]) + d["SAMPLE"], (tag, m["name"]))
                ats.add(i)
            self.assertEqual(ats, set(sampled))
            self.assertEqual(len(req["measurements"]), len(sampled) * 32)
            self.assertEqual(
                req["analysis"]["args"],
                f"0.02n {pulse.edge(n_ops - 1, d['PERIOD']) + d['PERIOD']:g}n",
            )
            self.assertEqual(len(req["corners"]["process"]), len(cm.PROCESSES))
            self.assertEqual(req["corners"]["supply_v"]["vvdd"], [float(v) for v in cm.VDDS])
            self.assertEqual(req["corners"]["temperature_c"], [int(t) for t in cm.TEMPS])


class FoldAxisTest(unittest.TestCase):
    """The per-axis reduction rule, directly."""

    def test_monotonic_knee(self):
        grid = (4.0, 6.0, 8.0, 10.0)
        s = {4.0: "FAIL", 6.0: "FAIL", 8.0: "PASS", 10.0: "PASS"}
        self.assertEqual(pulse.fold_axis(s, grid), ("8 ns", ""))

    def test_smallest_width_passing(self):
        grid = (4.0, 6.0, 8.0, 10.0)
        s = {w: "PASS" for w in grid}
        self.assertEqual(pulse.fold_axis(s, grid), ("4 ns", ""))

    def test_no_passing_width_is_open(self):
        grid = (4.0, 6.0, 8.0, 10.0)
        s = {w: "FAIL" for w in grid}
        display, note = pulse.fold_axis(s, grid)
        self.assertEqual(display, "OPEN")
        self.assertIn("no passing width", note)

    def test_pass_island_not_smoothed(self):
        grid = (4.0, 6.0, 8.0, 10.0, 12.0, 14.0)
        s = {4.0: "FAIL", 6.0: "PASS", 8.0: "FAIL", 10.0: "PASS", 12.0: "PASS", 14.0: "PASS"}
        display, note = pulse.fold_axis(s, grid)
        self.assertEqual(display, "10 ns")
        self.assertIn("pass island at 6 ns", note)

    def test_min_at_largest_grid_point_is_sentinel(self):
        grid = (4.0, 6.0, 8.0, 10.0)
        s = {4.0: "FAIL", 6.0: "FAIL", 8.0: "FAIL", 10.0: "PASS"}
        display, _ = pulse.fold_axis(s, grid)
        self.assertEqual(display, ">= 10 ns")

    def test_unmeasured_width_is_open(self):
        grid = (4.0, 6.0, 8.0, 10.0)
        s = {4.0: "PASS", 6.0: "OPEN", 8.0: "PASS", 10.0: "PASS"}
        display, note = pulse.fold_axis(s, grid)
        self.assertEqual(display, "OPEN")
        self.assertIn("unmeasured", note)


class FixtureGradingTest(unittest.TestCase):
    """The grader against the checked-in fixture reports."""

    def test_fixtures_cover_the_grid(self):
        for h, l in pulse.grid_points():
            f = FIXTURES / f"fixture_min_clk_{pulse.variant_tag(h, l)}.json"
            self.assertTrue(f.exists(), f.name)
            rep = json.loads(f.read_text())
            m = re.search(r"tb_min_clk_(h\d+_l\d+)\.klt\.spice", rep["netlist"]["path"])
            self.assertEqual(m.group(1), pulse.variant_tag(h, l), f.name)

    def test_check_klt_exit_1_on_fail(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pulse.check_klt(FIXTURES / "fixture_min_clk_h10_l10.json")
        self.assertEqual(code, 1)
        lines = out.getvalue().splitlines()
        self.assertIn("RESULT: tt_25c_3.30v h10_l10 PASS", lines[0])
        self.assertTrue(any("tt_-40c_3.63v h10_l10 FAIL" in l for l in lines))
        self.assertIn("RESULT: h10_l10 = FAIL over 7 corners", lines[-1])

    def test_check_klt_exit_2_when_only_open(self):
        rep = fixture("h06_l10")
        for c in rep["corners"]:  # strip every measurement: nothing was measured
            c["measurements"] = []
            c["status"] = "error"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pulse.check_klt(rep)
        self.assertEqual(code, 2)
        self.assertIn("klt_status=error", out.getvalue())
        self.assertIn("= OPEN over 7 corners", out.getvalue())

    def test_check_klt_exit_0_all_pass(self):
        rep = fixture("h10_l10")
        for c in rep["corners"]:  # rail-clean expected words: everything passes
            vdd = c["supply_v"]["vvdd"]
            c["measurements"] = [
                {"name": f"q{b}_op{i}", "value": vdd if (o[6] >> b) & 1 else 0.0, "unit": "V", "status": "pass"}
                for i, o in enumerate(pulse.OPS) if o[6] is not None for b in range(32)
            ]
            c["status"] = "pass"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pulse.check_klt(rep)
        self.assertEqual(code, 0)

    def test_vdd_definedness_at_2_97_and_3_63(self):
        """The same 2.40 V '1'-bit voltage is defined (>0.8*VDD) at 2.97 V and
        undefined at 3.63 V: grading is against each corner's own VDD."""
        _, verdicts = pulse.grade_report(FIXTURES / "fixture_min_clk_h04_l10.json")
        lo = verdicts["tt_125c_2.97v"]
        hi = verdicts["tt_-40c_3.63v"]
        self.assertEqual(lo["status"], "PASS")
        self.assertEqual(lo["undefined_bits"], 0)
        self.assertEqual(hi["status"], "FAIL")
        self.assertEqual(hi["undefined_bits"], 1)
        self.assertEqual(hi["words_bad"], 1)

    def test_errored_corner_is_open_not_fail(self):
        """A corner klt sim did not measure (status error, no values) grades
        OPEN with the klt status named, never FAIL."""
        _, verdicts = pulse.grade_report(FIXTURES / "fixture_min_clk_h06_l10.json")
        v = verdicts["ss_-40c_3.63v"]
        self.assertEqual(v["status"], "OPEN")
        self.assertEqual(v["klt_status"], "error")
        self.assertEqual(v["unmeasured_bits"], 224)

    def test_grade_set_folds_to_expected_minima(self):
        reports = sorted(FIXTURES.glob("fixture_min_clk_*.json"))
        self.assertEqual(len(reports), 9)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pulse.grade_set(reports)
        self.assertEqual(code, 2)  # sentinel axes present (recorded, not a crash)
        mins = {}
        for line in out.getvalue().splitlines():
            m = re.match(r"MIN: (\S+) high=(.+?) low=(.+?)\s+\[", line)
            if m:
                mins[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
        self.assertEqual(mins, EXPECTED_FOLD)
        notes = out.getvalue()
        self.assertIn("pass island at 6 ns", notes)  # ff_125c_3.63v high
        self.assertIn("unmeasured at ['6 ns']", notes)  # ss_-40c_3.63v high
        self.assertIn("no passing width in the swept grid", notes)  # ss_125c_2.97v high
        self.assertIn("sentinel axes", notes)

    def test_grade_set_missing_variant_is_structural_error(self):
        reports = sorted(FIXTURES.glob("fixture_min_clk_*.json"))[:-1]  # drop one variant
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = pulse.grade_set(reports)
        self.assertEqual(code, 1)

    def grade_set_captured(self, paths):
        """Run grade_set with stdout/stderr captured; return (code, out, err)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pulse.grade_set(paths)
        return code, out.getvalue(), err.getvalue()

    def fixture_reports_by_tag(self) -> dict:
        """fixture file path for every variant tag, from the file names."""
        prefix = len("fixture_min_clk_")
        return {
            p.stem[prefix:]: p for p in sorted(FIXTURES.glob("fixture_min_clk_*.json"))
        }

    def test_grade_set_duplicate_plus_omission_is_structural_error(self):
        """A repeated variant plus an omitted one passes today's occurrence
        count (#365). Either ordering is caller error: exit 1, an ERROR whose
        missing list names the omitted tag, and no MIN line on stdout."""
        by_tag = self.fixture_reports_by_tag()
        self.assertEqual(len(by_tag), 9)
        for dup, omit in (("h06_l10", "h04_l10"), ("h04_l10", "h06_l10")):
            argv = [by_tag[t] for t in sorted(by_tag) if t != omit]
            argv.append(by_tag[dup])
            self.assertEqual(len(argv), 9)
            code, out, err = self.grade_set_captured(argv)
            self.assertEqual(code, 1, f"{dup} twice, {omit} omitted")
            self.assertIn(f"missing: ['{omit}']", err)
            self.assertNotIn("Traceback", err)
            self.assertNotIn("MIN:", out)

    def test_grade_set_complete_set_plus_duplicate_is_structural_error(self):
        """A complete grid plus one repeated report (10 args) must exit 1 with
        the repeated-tag error, never the occurrence-count '7 of 6 variants
        (missing: [])' nonsense (#365)."""
        by_tag = self.fixture_reports_by_tag()
        argv = [by_tag[t] for t in sorted(by_tag)] + [by_tag["h06_l10"]]
        code, out, err = self.grade_set_captured(argv)
        self.assertEqual(code, 1)
        self.assertIn("h06_l10 more than once", err)
        self.assertIn("one report per variant", err)
        self.assertNotIn("(missing: [])", err)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("MIN:", out)

    def test_grade_set_rejects_off_axis_variant(self):
        """A variant on neither 1-D axis (both widths off the held values) is
        a structural error, silently folded into no axis."""
        rep = fixture("h10_l04")
        rep["netlist"]["path"] = "sim/min-clock-pulse/testbench/tb_min_clk_h06_l06.klt.spice"
        (tmp := tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)).write(
            json.dumps(rep)
        )
        tmp.close()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = pulse.grade_set([tmp.name])
        self.assertEqual(code, 1)
        Path(tmp.name).unlink()

    def fabricated(self, src_tag: str, dst_tag: str) -> str:
        """A copy of a fixture report re-tagged as `dst_tag` via its
        netlist.path (the substitution technique of the off-axis test)."""
        rep = fixture(src_tag)
        rep["netlist"]["path"] = f"sim/min-clock-pulse/testbench/tb_min_clk_{dst_tag}.klt.spice"
        (tmp := tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)).write(
            json.dumps(rep)
        )
        tmp.close()
        return tmp.name

    def short_report(self, src_tag: str, drop_cid: str) -> str:
        """A copy of a fixture report minus one corners[] entry."""
        rep = fixture(src_tag)
        rep["corners"] = [c for c in rep["corners"] if c["corner_id"] != drop_cid]
        (tmp := tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)).write(
            json.dumps(rep)
        )
        tmp.close()
        return tmp.name

    def test_grade_set_rejects_off_grid_substitution(self):
        """An on-axis, off-grid tag (h07_l10) substituting for an omitted grid
        point (h04_l10) keeps a distinct count at 6 of 6 (#382 AC1) — the set
        test must reject it: exit 1, no MIN line, and the error names BOTH
        halves (missing h04_l10, unexpected h07_l10), with no "N of M" count
        framing to read as a 6-of-6 contradiction (AC2)."""
        by_tag = self.fixture_reports_by_tag()
        fab = self.fabricated("h04_l10", "h07_l10")
        argv = [p for t, p in by_tag.items() if t != "h04_l10"] + [fab]
        try:
            code, out, err = self.grade_set_captured(argv)
        finally:
            Path(fab).unlink()
        self.assertEqual(code, 1)
        self.assertIn("missing: ['h04_l10']", err)
        self.assertIn("unexpected: ['h07_l10']", err)
        self.assertNotIn("of 6 variants", err)  # count framing invites "6 of 6, yet wrong"
        self.assertNotIn("Traceback", err)
        self.assertNotIn("MIN:", out)

    def test_grade_set_no_min_before_corner_short_error(self):
        """A report short one corners[] entry is a structural error before any
        minimum prints (#382 AC3): exit 1 and zero MIN lines, whichever end of
        sorted(corner_id) the dropped corner sits at. #365's AC3 held for the
        uniform-corner case only; this makes it unconditional."""
        by_tag = self.fixture_reports_by_tag()
        for drop in ("tt_25c_3.30v", "tt_-40c_3.63v"):  # sorts 7th of 7 / 5th of 7
            short = self.short_report("h14_l10", drop)
            argv = [p for t, p in by_tag.items() if t != "h14_l10"] + [short]
            try:
                code, out, err = self.grade_set_captured(argv)
            finally:
                Path(short).unlink()
            self.assertEqual(code, 1, f"dropped {drop}")
            self.assertEqual([l for l in out.splitlines() if l.startswith("MIN:")], [],
                             f"MIN printed before the error (dropped {drop})")
            self.assertIn(drop, err)
            self.assertNotIn("Traceback", err)

    def test_grade_set_corner_set_error_names_both_reports_when_short_is_first(self):
        """The corner-set baseline seeds from whichever report arrives first,
        so a short report placed FIRST in argv would make the error blame the
        next (complete) report (#403). The message must name both reports --
        the current tag and the report the baseline came from -- and keep
        exit 1 with zero MIN lines."""
        by_tag = self.fixture_reports_by_tag()
        short = self.short_report("h14_l10", "tt_25c_3.30v")
        argv = [short] + [p for t, p in by_tag.items() if t != "h14_l10"]
        try:
            code, out, err = self.grade_set_captured(argv)
        finally:
            Path(short).unlink()
        self.assertEqual(code, 1)
        self.assertEqual([l for l in out.splitlines() if l.startswith("MIN:")], [])
        self.assertIn("corner set differs from h14_l10", err)  # baseline named
        self.assertIn("unexpected: ['tt_25c_3.30v']", err)  # vs the short baseline
        self.assertNotIn("missing:", err)  # empty half omitted, not "[]"
        self.assertNotIn("unexpected: []", err)
        self.assertNotIn("Traceback", err)

    def test_grade_set_corner_set_error_halves_follow_set_difference(self):
        """The cross-report error prints only the non-empty halves, relative
        to the baseline report (#403): a short baseline facing a report with
        an extra corner id prints only the unexpected half; a report with a
        corner id renamed past the baseline prints both halves."""
        def variant(src_tag, mutate):
            rep = fixture(src_tag)
            mutate(rep)
            (tmp := tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)).write(
                json.dumps(rep)
            )
            tmp.close()
            return tmp.name

        def add_corner(rep):
            extra = json.loads(json.dumps(rep["corners"][0]))
            extra["corner_id"] = "tt_99c_9.99v"
            rep["corners"].append(extra)

        def rename_corner(rep):
            for c in rep["corners"]:
                if c["corner_id"] == "tt_25c_3.30v":
                    c["corner_id"] = "tt_99c_9.99v"

        baseline = self.short_report("h14_l10", "tt_25c_3.30v")  # 6 of 7 corners
        extra = variant("h04_l10", add_corner)  # 7 real + 1 bogus
        try:
            code, out, err = self.grade_set_captured([baseline, extra])
            self.assertEqual(code, 1)
            self.assertIn("corner set differs from h14_l10", err)
            self.assertIn("unexpected: ['tt_25c_3.30v', 'tt_99c_9.99v']", err)
            self.assertNotIn("missing:", err)
            self.assertNotIn("Traceback", err)
            self.assertNotIn("MIN:", out)
        finally:
            Path(baseline).unlink()
            Path(extra).unlink()

        full = self.fixture_reports_by_tag()["h14_l10"]  # complete, untouched
        renamed = variant("h04_l10", rename_corner)
        try:
            code, out, err = self.grade_set_captured([full, renamed])
            self.assertEqual(code, 1)
            self.assertIn("corner set differs from h14_l10", err)
            self.assertIn("missing: ['tt_25c_3.30v']", err)
            self.assertIn("unexpected: ['tt_99c_9.99v']", err)
            self.assertIn("; ", err)  # both halves, joined as in the per-corner error
            self.assertNotIn("Traceback", err)
            self.assertNotIn("MIN:", out)
        finally:
            Path(renamed).unlink()

    def test_grade_set_below_grid_substitution_is_structural_error(self):
        """A substitute below the grid floor (h03_l10 for an omitted h14_l10)
        used to reach fold_axis with the grid's top point missing and raise an
        uncaught KeyError: 14.0 (#382 AC4). The set test rejects it first:
        exit 1 with an ERROR, never a traceback."""
        by_tag = self.fixture_reports_by_tag()
        fab = self.fabricated("h14_l10", "h03_l10")
        argv = [p for t, p in by_tag.items() if t != "h14_l10"] + [fab]
        try:
            code, out, err = self.grade_set_captured(argv)
        finally:
            Path(fab).unlink()
        self.assertEqual(code, 1)
        self.assertIn("missing: ['h14_l10']", err)
        self.assertIn("unexpected: ['h03_l10']", err)
        self.assertNotIn("KeyError", err)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("MIN:", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
