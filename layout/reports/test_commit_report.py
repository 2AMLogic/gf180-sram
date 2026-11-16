#!/usr/bin/env python3
"""Tests for layout/reports/commit_report.py (issue #340).

Run: python3 layout/reports/test_commit_report.py   (or via `npm run test`)

What these assert is the property the ten hand-written scrub blocks did not
have: that the rewrite reaches fields nobody listed. `test_rewrites_fields_no_
one_listed` is the regression test for the actual bug -- a path in a field the
old per-block code never mentioned (nested, in a list, in a dict key's value,
in prose) is still rewritten -- and `test_lint_refuses_to_commit_a_leak` is
the regression test for the guard: a report that still carries an absolute
path is NOT written, and the run fails.

The lint tests need `klt` on PATH (klayout-tools >= 0.8.0 for
`env-provenance lint-envelope`); they skip without it rather than passing
vacuously.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "commit_report.py"
HAVE_KLT = shutil.which("klt") is not None


def run(args, check=True):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=check,
    )


class CommitTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.root = self.tmp / "checkout"
        self.work = self.tmp / "scratch"
        self.root.mkdir()
        self.work.mkdir()
        self.raw = self.tmp / "raw.json"
        self.out = self.tmp / "out.json"
        self.addCleanup(self._td.cleanup)

    def commit(self, payload, *extra, check=True):
        self.raw.write_text(json.dumps(payload))
        return run(
            [
                "commit",
                str(self.raw),
                str(self.out),
                "--root",
                str(self.root),
                "--work",
                str(self.work),
                *extra,
            ],
            check=check,
        )

    def test_rewrites_fields_no_one_listed(self):
        """The whole document is rewritten, not an allow-list of fields."""
        payload = {
            # the fields the old blocks did hand-list
            "netlist_path": f"{self.work}/array.spice",
            "layout": f"{self.root}/layout/sram_256x32/sram_256x32_array.gds",
            "reference": f"{self.root}/design/netlist/sram_256x32_array.spice",
            # ... and the ones they did not
            "file": {"path": f"{self.root}/layout/bitcell/sram_bitcell_6t.gds"},
            "deck_file": f"{self.work}/native/main.drc",
            "inputs": [f"{self.root}/a.gds", {"spef": f"{self.work}/x.spef"}],
            "description": f"reference netlist {self.work}/ref.spice not found",
            "exactly_root": str(self.root),
            "untouched": "design/netlist/row_path.spice",
            "status": "extracted",
        }
        self.commit(payload, "--skip-lint")
        got = json.loads(self.out.read_text())
        self.assertEqual(got["netlist_path"], "array.spice")
        self.assertEqual(
            got["layout"], "layout/sram_256x32/sram_256x32_array.gds"
        )
        self.assertEqual(got["reference"], "design/netlist/sram_256x32_array.spice")
        self.assertEqual(got["file"]["path"], "layout/bitcell/sram_bitcell_6t.gds")
        self.assertEqual(got["deck_file"], "native/main.drc")
        self.assertEqual(got["inputs"][0], "a.gds")
        self.assertEqual(got["inputs"][1]["spef"], "x.spef")
        self.assertEqual(got["description"], "reference netlist ref.spice not found")
        self.assertEqual(got["exactly_root"], ".")
        self.assertEqual(got["untouched"], "design/netlist/row_path.spice")
        # and nothing anywhere still names the generating host's directories
        self.assertNotIn(str(self.root), self.out.read_text())
        self.assertNotIn(str(self.work), self.out.read_text())

    def test_set_drop_print_and_trailing_newline(self):
        payload = {
            "status": "clean",
            "violation_count": 0,
            "file": f"{self.work}/column_abut.gds",
            "devices": [1, 2, 3],
            "nets": [4],
        }
        proc = self.commit(
            payload,
            "--skip-lint",
            "--drop",
            "devices",
            "--drop",
            "nets",
            "--set",
            "file=(scratch composite) see generate.py --abut",
            "--set",
            "_note=devices[]/nets[] omitted",
            "--print",
            "drc-column-abut: {status} | violations: {violation_count}",
        )
        self.assertEqual(
            proc.stdout.strip(), "drc-column-abut: clean | violations: 0"
        )
        raw = self.out.read_bytes()
        self.assertTrue(raw.endswith(b"\n"), "committed report must end in a newline")
        got = json.loads(raw)
        self.assertNotIn("devices", got)
        self.assertNotIn("nets", got)
        self.assertEqual(got["file"], "(scratch composite) see generate.py --abut")
        # --set on a new field appends it last, as the committed reports carry `_note`
        self.assertEqual(list(got)[-1], "_note")
        self.assertIn('"status": "clean"', raw.decode(), "indent=2 re-dump")

    def test_status_subcommand_prints_from_a_committed_report(self):
        self.out.write_text(json.dumps({"status": "clean", "violation_count": 7}))
        proc = run(
            [
                "status",
                str(self.out),
                "--print",
                "drc-row-path: {status} | violations: {violation_count}",
            ]
        )
        self.assertEqual(proc.stdout.strip(), "drc-row-path: clean | violations: 7")

    @unittest.skipUnless(HAVE_KLT, "needs klt (klayout-tools) on PATH")
    def test_lint_refuses_to_commit_a_leak(self):
        """A path outside $ROOT/$WORK survives the rewrite -> nothing committed."""
        proc = self.commit(
            {"status": "clean", "file": "/home/someone-else/elsewhere/top.gds"},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("absolute host path", proc.stdout + proc.stderr)
        self.assertFalse(
            self.out.exists(), "a leaking report must never land on the committed one"
        )
        # ... and the leaking text itself is not echoed into the log
        self.assertNotIn("someone-else", proc.stdout + proc.stderr)
        # the staged temp file is cleaned up too
        self.assertEqual(list(self.out.parent.glob(".out.json.*")), [])

    @unittest.skipUnless(HAVE_KLT, "needs klt (klayout-tools) on PATH")
    def test_lint_passes_a_scrubbed_report(self):
        self.commit(
            {
                "status": "extracted",
                "netlist_path": f"{self.work}/bitcell.spice",
                "file": {"path": f"{self.root}/layout/bitcell/sram_bitcell_6t.gds"},
            }
        )
        got = json.loads(self.out.read_text())
        self.assertEqual(got["netlist_path"], "bitcell.spice")

    @unittest.skipUnless(HAVE_KLT, "needs klt (klayout-tools) on PATH")
    def test_allow_prefix_admits_a_machine_wide_install(self):
        self.commit(
            {"status": "clean", "pdk_root": "/opt/pdk/gf180mcuD/libs.tech"},
            "--allow-prefix",
            "/opt/pdk",
        )
        self.assertTrue(self.out.exists())


if __name__ == "__main__":
    unittest.main()
