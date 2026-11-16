#!/usr/bin/env python3
"""Tests for layout/reports/commit_report.py (issue #340).

Run: python3 layout/reports/test_commit_report.py (CI runs it in the
`provenance-hygiene` job of .github/workflows/ci.yml -- not under
`npm run test`, whose `test` script does not list this file, because three
cases need klt and a skipped case must not look like a passing one)

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
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "commit_report.py"
HAVE_KLT = shutil.which("klt") is not None

# The array `_note` templates generate.sh hands to `commit_report
# --set-format` (issue #371). They are single-quoted in the shell and carry
# no single quote of their own, so this extraction is exact -- and reading
# them out of generate.sh (rather than re-typing them here) is what makes the
# byte-identity test below fail if the generator's template drifts.
ARRAY_NOTE_TEMPLATE = re.compile(r"--set-format '_note=([^']*)'")


def run(args, check=True, env=None):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=check,
        env=env,
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

    def commit(self, payload, *extra, check=True, env=None):
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
            env=env,
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

    def test_set_format_templates_top_level_fields(self):
        """`--set-format` renders against the post-rewrite/post-drop document."""
        payload = {
            "status": "clean",
            "device_count": 49152,
            "net_count": 16706,
        }
        self.commit(
            payload,
            "--skip-lint",
            "--set-format",
            "_note=({device_count} devices / {net_count} nets) {status}",
        )
        got = json.loads(self.out.read_text())
        self.assertEqual(got["_note"], "(49152 devices / 16706 nets) clean")

    def test_set_format_literal_braces(self):
        """`{{`/`}}` are str.format escapes, not placeholders."""
        self.commit(
            {"status": "clean"},
            "--skip-lint",
            "--set-format",
            "_note=literal {{braces}} stay {status}",
        )
        got = json.loads(self.out.read_text())
        self.assertEqual(got["_note"], "literal {braces} stay clean")

    def test_set_format_runs_after_set_and_drop(self):
        """Ordering: rewrite, then --drop, then --set, then --set-format.

        A template may cite a field `--set` introduced, and on the same
        field `--set-format` wins because it is applied last.
        """
        payload = {"status": "clean", "counts": {"devices": 3, "nets": 4}}
        self.commit(
            payload,
            "--skip-lint",
            "--drop",
            "counts",
            "--set",
            "_note=hand-typed",
            "--set",
            "who=--set then --set-format",
            "--set-format",
            "_note={who} (counts dropped)",
        )
        got = json.loads(self.out.read_text())
        self.assertNotIn("counts", got)
        self.assertEqual(got["_note"], "--set then --set-format (counts dropped)")

    def test_set_format_referencing_a_dropped_field_fails(self):
        proc = self.commit(
            {"status": "clean", "devices": [1, 2, 3]},
            "--skip-lint",
            "--drop",
            "devices",
            "--set-format",
            "_note={devices[0]} devices",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)
        self.assertFalse(self.out.exists())

    def test_set_format_rejects_a_dotted_field(self):
        """Same top-level-field rule as `--set`: no `.` in FIELD."""
        proc = self.commit(
            {"status": "clean"},
            "--skip-lint",
            "--set-format",
            "nested.field=x",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("top-level FIELD=TEMPLATE", proc.stdout + proc.stderr)

    def test_set_format_unknown_placeholder_exits_naming_the_field(self):
        """An unknown placeholder exits non-zero naming the field, not a
        traceback, and leaves no staged file behind (issue #371)."""
        proc = self.commit(
            {"status": "clean", "device_count": 3},
            "--skip-lint",
            "--set-format",
            "_note={device_count} devices / {net_count} nets",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("_note", out)
        self.assertIn("net_count", out)
        self.assertFalse(self.out.exists(), "nothing committed on a bad template")
        self.assertEqual(
            list(self.tmp.glob(".out.json.*")), [], "nothing staged either"
        )

    def test_set_format_type_error_over_a_list_exits_naming_the_field(self):
        """`{list[key]}` formats to TypeError, which is outside the old
        (KeyError, IndexError, ValueError) tuple (issue #385)."""
        proc = self.commit(
            {"status": "clean", "devices": [1, 2]},
            "--skip-lint",
            "--set-format",
            "_note={devices[key]} x",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("_note", out)
        self.assertFalse(self.out.exists(), "nothing committed on a bad template")
        self.assertEqual(
            list(self.tmp.glob(".out.json.*")), [], "nothing staged either"
        )

    def test_set_format_attribute_error_over_a_string_field_exits_naming_the_field(
        self,
    ):
        """`{str.attr}` formats to AttributeError, likewise outside the old
        tuple (issue #385)."""
        proc = self.commit(
            {"status": "clean"},
            "--skip-lint",
            "--set-format",
            "_note={status.y}",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("_note", out)
        self.assertFalse(self.out.exists(), "nothing committed on a bad template")
        self.assertEqual(
            list(self.tmp.glob(".out.json.*")), [], "nothing staged either"
        )

    def test_print_unknown_placeholder_on_commit_fails_after_committing(self):
        """A malformed `--print` template on `commit` exits non-zero with a
        FATAL message -- no traceback -- but the report IS committed: the
        template runs after os.replace, so exit status alone must not be
        read as "nothing was written" (issue #393)."""
        proc = self.commit(
            {"status": "clean", "devices": [1, 2]},
            "--skip-lint",
            "--print",
            "{nope}",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("FATAL: --print", out)
        self.assertIn("nope", out)
        self.assertIn(str(self.out), out, "message must say the report was committed")
        self.assertTrue(self.out.exists(), "the commit itself succeeded")
        self.assertEqual(
            list(self.tmp.glob(".out.json.*")), [], "nothing staged either"
        )

    def test_print_type_error_over_a_list_on_commit_fails_after_committing(self):
        """The shape measured in issue #393: `{devices[key]}` formats to
        TypeError at the post-commit `--print` site."""
        proc = self.commit(
            {"status": "clean", "devices": [1, 2]},
            "--skip-lint",
            "--print",
            "{devices[key]}",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("FATAL: --print", out)
        self.assertTrue(self.out.exists(), "the commit itself succeeded")

    def test_print_unknown_placeholder_on_status_fails_without_a_traceback(self):
        """`status --print` has nothing to commit; the same guard keeps it
        a FATAL message naming the template's error instead of a traceback
        (issue #393)."""
        self.commit({"status": "clean", "device_count": 3}, "--skip-lint")
        proc = run(["status", str(self.out), "--print", "{nope}"], check=False)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("FATAL: --print", out)
        self.assertIn("nope", out)

    def test_print_type_error_over_a_list_on_status_fails_without_a_traceback(self):
        """`{devices[key]}` on `status` formats to TypeError, covered by
        the same guard (issue #393)."""
        self.commit({"status": "clean", "devices": [1, 2]}, "--skip-lint")
        proc = run(
            ["status", str(self.out), "--print", "{devices[key]}"],
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out)
        self.assertIn("FATAL: --print", out)

    def test_generate_sh_note_templates_render_committed_notes_byte_for_byte(self):
        """Issue #371 item 1's no-op oracle: each `--set-format` template in
        generate.sh, rendered against the committed report's own field
        values, reproduces the committed `_note` byte-for-byte -- templating
        the notes changed nothing in the artifacts, so re-minting them is
        not needed to prove the swap safe."""
        text = (HERE / "generate.sh").read_text()
        templates = ARRAY_NOTE_TEMPLATE.findall(text)
        self.assertEqual(
            len(templates), 2, "generate.sh should carry exactly two _note templates"
        )
        for template in templates:
            report = (
                "extract-array-64x128.json"
                if template.endswith("--array64")
                else "extract-array.json"
            )
            committed = json.loads((HERE / report).read_text())
            rendered = template.format(**committed)
            self.assertEqual(rendered, committed["_note"], f"{report}: drift")

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
    def test_lint_findings_message_names_the_raw_input(self):
        """Issue #371 item 2: the FATAL message must point at a file that
        still exists after the process exits -- the raw input -- never at
        the `.staged` temp file the caller's `finally` just unlinked."""
        proc = self.commit(
            {"status": "clean", "file": "/home/someone-else/elsewhere/top.gds"},
            check=False,
        )
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn(str(self.raw), out, "message must name the surviving raw input")
        self.assertNotIn(".staged", out, "message must not name the deleted temp file")
        # the suggested inspect command targets that same surviving file
        self.assertIn(f"klt env-provenance lint-envelope {self.raw}", out)
        # and the diagnostic keeps its good properties: field named, text not echoed
        self.assertIn("field(s):", out)
        self.assertNotIn("someone-else", out)

    def test_lint_klt_missing_message_names_the_raw_input(self):
        """Same rule on the `klt`-not-on-PATH exit path (no real klt needed)."""
        env = {k: v for k, v in os.environ.items() if k != "PATH"}
        env["PATH"] = "/nonexistent-klt-guard"
        proc = self.commit(
            {"status": "clean", "file": f"{self.work}/a.gds"}, check=False, env=env
        )
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn("is required on PATH", out)
        self.assertIn(str(self.raw), out)
        self.assertNotIn(".staged", out)
        self.assertTrue(self.raw.exists(), "the named file must still exist")
        self.assertFalse(self.out.exists())

    def test_lint_unexpected_exit_message_names_the_raw_input(self):
        """Same rule on the unexpected-exit-code path, via a stub `klt`
        exiting 2 (expected: only 0 = clean or 3 = findings)."""
        stub = self.tmp / "bin"
        stub.mkdir()
        (stub / "klt").write_text("#!/bin/sh\nexit 2\n")
        (stub / "klt").chmod(0o755)
        env = {**os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}"}
        proc = self.commit(
            {"status": "clean", "file": f"{self.work}/a.gds"}, check=False, env=env
        )
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn("exited 2", out)
        self.assertIn(str(self.raw), out)
        self.assertNotIn(".staged", out)
        self.assertTrue(self.raw.exists(), "the named file must still exist")
        self.assertFalse(self.out.exists())
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
