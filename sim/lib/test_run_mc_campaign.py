#!/usr/bin/env python3
"""Tests for run_mc_campaign.run_klt_yield (issue #160): the `klt yield`
invocation must pass a report-directory-relative samples path with
cwd=<report dir>, for JSON and text alike. No Monte Carlo campaign is run.

Run: python3 sim/lib/test_run_mc_campaign.py   (or via `npm run test`)
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_mc_campaign as rmc


class RunKltYieldTest(unittest.TestCase):
    def _run(self, root: Path):
        samples = root / "sim" / "x" / "mc" / "samples" / "id1.json"
        reports = root / "sim" / "x" / "mc" / "yield-reports"
        samples.parent.mkdir(parents=True)
        reports.mkdir(parents=True)
        calls = []

        def fake_run(argv, **kw):
            calls.append((argv, kw))
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(rmc.subprocess, "run", side_effect=fake_run):
            rmc.run_klt_yield("klt", samples, reports)
        return calls, reports

    def test_report_relative_path_and_cwd_for_both_formats(self):
        with tempfile.TemporaryDirectory() as td:
            calls, reports = self._run(Path(td))
            self.assertEqual(len(calls), 2)
            fmts = []
            for argv, kw in calls:
                self.assertEqual(argv[:3], ["klt", "yield", "../samples/id1.json"])
                self.assertEqual(kw["cwd"], reports)
                fmts.append(argv[argv.index("--format") + 1])
            self.assertEqual(fmts, ["json", "text"])

    def test_path_with_spaces_stays_one_argv_element(self):
        with tempfile.TemporaryDirectory() as td:
            calls, _ = self._run(Path(td) / "a dir with spaces")
            for argv, _kw in calls:
                self.assertEqual(argv[2], "../samples/id1.json")
                self.assertNotIn(td, " ".join(argv))


if __name__ == "__main__":
    unittest.main()
