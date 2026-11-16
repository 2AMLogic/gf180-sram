#!/usr/bin/env python3
"""Offline tests for two gates in scripts/ci/check_evidence_format.py:
the receipt "Files in" gate (issue #356) and the T1 item-9
testbench-attestation gate (issue #357).

The receipt gate resolves every backticked path in a receipt's "## Files
in `<dir>/`" table against the committed file list. The attestation gate
requires every tracked sim/*/testbench/tb_* bench to be pinned by
sim/testbenches.signoff.json. These tests exercise the pure helpers in
both directions -- a missing concrete path and a zero-match placeholder
row fail; an exempt row and the repo's two real deck-parity receipts
pass; an unpinned bench fails naming it while pinned non-bench paths and
the tb_-prefixless DUT copies pass -- with no git, no PDK and no
simulator.

Run: python3 scripts/ci/test_check_evidence_format.py   (or via `npm run test`)
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_evidence_format as cef  # noqa: E402

REPO = cef.REPO_ROOT
RECEIPT_DOCS = ("20261114-tt_25c_3.30v.md", "20261115-full-grid.md")


def deck_parity_files() -> set[str]:
    """Files committed under the two receipt dirs, as repo-relative paths."""
    files: set[str] = set()
    base = REPO / "sim" / "deck-parity"
    for doc in RECEIPT_DOCS:
        receipt_dir = base / doc.removesuffix(".md")
        for p in receipt_dir.rglob("*"):
            if p.is_file():
                files.add(p.relative_to(REPO).as_posix())
    return files


def receipt(dir_name: str, file_cell: str, what_cell: str = "description") -> str:
    """A minimal receipt: heading, header row, separator, one data row."""
    return (
        f"## Files in `{dir_name}/`\n\n"
        "| File | What |\n"
        "|---|---|\n"
        f"| {file_cell} | {what_cell} |\n"
        "\nTimestamp / author: test.\n"
    )


class ParseFilesTablesTest(unittest.TestCase):
    def test_heading_dir_and_cells_parsed(self):
        tables = cef.parse_files_tables(
            receipt("run-a", "`ok.json`", "the `klt sim` envelope (none committed)")
        )
        self.assertEqual(tables, [("run-a", [(["ok.json"], True)])])

    def test_multi_token_cell(self):
        tables = cef.parse_files_tables(receipt("run-a", "`a.json`, `b.json`"))
        self.assertEqual(tables[0][1], [(["a.json", "b.json"], False)])

    def test_non_receipt_heading_ignored(self):
        # .loom/README.md's "## Files in This Directory" must not parse
        # (defense in depth; it is also outside LINK_CHECK_GLOBS).
        text = (
            "## Files in This Directory\n\n"
            "| File | What |\n|---|---|\n| `nope.json` | x |\n"
        )
        self.assertEqual(cef.parse_files_tables(text), [])

    def test_prose_before_table_and_after_it(self):
        text = (
            "## Files in `run-a/`\n\n"
            "Committed per the bounded-bytes rule: `request.json`, prose...\n\n"
            "| File | What |\n|---|---|\n| `a.json` | the `units/` scratch is not committed |\n"
            "\nTimestamp.\n\n## Next section\n"
        )
        tables = cef.parse_files_tables(text)
        self.assertEqual(tables[0][1], [(["a.json"], False)])


class UnresolvedRowsTest(unittest.TestCase):
    FILES = [
        "sim/deck-parity/run-a/batch-set-envelope.json",
        "sim/deck-parity/run-a/hold-snm/request.json",
    ]

    def test_missing_concrete_path_fails(self):
        findings = cef.unresolved_files_table_rows(
            receipt("run-a", "`missing-artifact.json`"), "sim/deck-parity", self.FILES
        )
        self.assertEqual(
            findings,
            [
                (
                    "missing-artifact.json",
                    "sim/deck-parity/run-a/missing-artifact.json",
                )
            ],
        )

    def test_zero_match_placeholder_fails(self):
        # The #346 shape: <family>/stdout.log with no stdout.log under any
        # family. Placeholders must be expanded, not skipped.
        findings = cef.unresolved_files_table_rows(
            receipt("run-a", "`<family>/stdout.log`"), "sim/deck-parity", self.FILES
        )
        self.assertEqual(len(findings), 1)
        token, pattern = findings[0]
        self.assertEqual(token, "<family>/stdout.log")
        self.assertEqual(pattern, "sim/deck-parity/run-a/*/stdout.log")

    def test_none_committed_row_accepted_with_zero_matches(self):
        findings = cef.unresolved_files_table_rows(
            receipt("run-a", "`<family>/stdout.log`", "engine stdout (none committed)"),
            "sim/deck-parity",
            self.FILES,
        )
        self.assertEqual(findings, [])

    def test_placeholder_never_literal(self):
        # <family> expands inconsistently across one token (`hold-snm` the
        # directory vs `hold_snm_sweep.txt` the file), so each <...> is a
        # glob, never a literal substitution.
        files = ["receipts/run/hold-snm/c01/hold_snm_sweep.txt"]
        findings = cef.unresolved_files_table_rows(
            receipt("run", "`<family>/<corner-id>/<family>_sweep.txt`"),
            "receipts",
            files,
        )
        self.assertEqual(findings, [])

    def test_placeholder_does_not_cross_directories(self):
        # <family>/stdout.log is not satisfied by a deeper a/b/stdout.log.
        findings = cef.unresolved_files_table_rows(
            receipt("run-a", "`<family>/stdout.log`"),
            "sim/deck-parity",
            ["sim/deck-parity/run-a/a/b/stdout.log"],
        )
        self.assertEqual(len(findings), 1)

    def test_resolution_scoped_to_heading_dir(self):
        findings = cef.unresolved_files_table_rows(
            receipt("run-b", "`request.json`"),
            "sim/deck-parity",
            ["sim/deck-parity/run-a/request.json"],
        )
        self.assertEqual(len(findings), 1)

    def test_what_cell_tokens_never_scanned(self):
        # Only the table's first column is parsed: the What cell is full of
        # backticked non-paths that must never produce a finding.
        what = "the `klt sim` envelope; its `units/` scratch, `--batch-set` flag and `x_gf180_sram_adapter` sha256 are not paths here"
        findings = cef.unresolved_files_table_rows(
            receipt("run-a", "`batch-set-envelope.json`", what),
            "sim/deck-parity",
            ["sim/deck-parity/run-a/batch-set-envelope.json"],
        )
        self.assertEqual(findings, [])

    def test_multi_token_cell_reports_only_missing(self):
        findings = cef.unresolved_files_table_rows(
            receipt("run-a", "`batch-set-envelope.json`, `gone.json`"),
            "sim/deck-parity",
            ["sim/deck-parity/run-a/batch-set-envelope.json"],
        )
        self.assertEqual([t for t, _ in findings], ["gone.json"])

    def test_full_grid_row_shape_resolves(self):
        files = [
            "r/run/hold-snm/c01/corner.inc",
            "r/run/read-snm/c02/corner.inc",
            "r/run/hold-snm/c01/hold_snm_sweep.txt",
        ]
        for cell in (
            "`<family>/<corner-id>/corner.inc`",
            "`<family>/<corner-id>/<family>_sweep.txt`",
        ):
            self.assertEqual(
                cef.unresolved_files_table_rows(receipt("run", cell), "r", files),
                [],
                cell,
            )

    def test_error_message_names_doc_row_and_pattern(self):
        msg = cef.files_table_error(
            "sim/deck-parity/20261115-full-grid.md",
            "<family>/<corner-id>/stdout.log",
            "sim/deck-parity/20261115-full-grid/*/stdout.log",
        )
        self.assertIn("20261115-full-grid.md", msg)
        self.assertIn("<family>/<corner-id>/stdout.log", msg)
        self.assertIn("(none committed)", msg)


class RealReceiptsTest(unittest.TestCase):
    def test_both_real_receipts_pass(self):
        files = deck_parity_files()
        self.assertTrue(files, "receipt artifact dirs missing from checkout")
        for doc in RECEIPT_DOCS:
            text = (REPO / "sim" / "deck-parity" / doc).read_text(encoding="utf-8")
            self.assertEqual(
                cef.unresolved_files_table_rows(text, "sim/deck-parity", files),
                [],
                f"{doc} must fully resolve",
            )

    def test_exemption_inventory(self):
        # The only intentional zero-match row in the repo is the full-grid
        # stdout row; the one-corner receipt has none.
        base = REPO / "sim" / "deck-parity"
        one = cef.parse_files_tables((base / RECEIPT_DOCS[0]).read_text(encoding="utf-8"))
        grid = cef.parse_files_tables((base / RECEIPT_DOCS[1]).read_text(encoding="utf-8"))
        self.assertEqual(sum(1 for _, ex in one[0][1] if ex), 0)
        self.assertEqual(sum(1 for _, ex in grid[0][1] if ex), 1)

    def test_full_grid_stdout_row_requires_exemption(self):
        # Without the (none committed) token the intentional stdout row
        # fails -- the exemption is what keeps main green.
        path = REPO / "sim" / "deck-parity" / RECEIPT_DOCS[1]
        text = path.read_text(encoding="utf-8")
        self.assertIn(cef.NONE_COMMITTED_TOKEN, text)
        stripped = text.replace(cef.NONE_COMMITTED_TOKEN, "(deliberately absent)")
        findings = cef.unresolved_files_table_rows(
            stripped, "sim/deck-parity", deck_parity_files()
        )
        self.assertEqual(
            [t for t, _ in findings], ["<family>/<corner-id>/stdout.log"]
        )


class FilesTableCoverageTest(unittest.TestCase):
    """The coverage line and the ungated-table warning (issue #372)."""

    def test_coverage_counts_from_the_error_walk(self):
        # One walk returns the findings and the counts together: 2 tables,
        # 1 non-exempt row, 1 exempt row, 1 unresolved token.
        doc = (
            receipt("run-a", "`missing.json`")
            + "\n"
            + receipt("run-b", "`ok.json`", "(none committed)")
        )
        findings, coverage = cef.walk_files_tables(
            doc, "sim/deck-parity", ["sim/deck-parity/run-b/ok.json"]
        )
        self.assertEqual([t for t, _ in findings], ["missing.json"])
        self.assertEqual(
            coverage, cef.FilesTableCoverage(tables=2, rows=1, rows_exempt=1)
        )

    def test_coverage_clause_reports_counts(self):
        clause = cef.files_table_coverage_clause(
            cef.FilesTableCoverage(tables=3, rows=26, rows_exempt=1)
        )
        self.assertIn("3", clause)
        self.assertIn('receipt "Files in" tables gated', clause)
        self.assertIn("26 rows resolved", clause)
        self.assertIn("1 exempt row skipped", clause)
        zero = cef.files_table_coverage_clause(cef.FilesTableCoverage(0, 0, 0))
        self.assertIn('0 receipt "Files in" tables gated', zero)
        self.assertIn("0 rows resolved", zero)

    def test_coverage_clause_pluralizes_exempt_rows(self):
        clause = cef.files_table_coverage_clause(
            cef.FilesTableCoverage(tables=1, rows=2, rows_exempt=2)
        )
        self.assertIn("2 exempt rows skipped", clause)

    def test_main_success_line_uses_the_coverage_clause(self):
        source = inspect.getsource(cef.main)
        self.assertIn("files_table_coverage_clause", source)

    def test_matching_heading_produces_no_warning(self):
        self.assertEqual(
            cef.ungated_receipt_headings(receipt("run-a", "`ok.json`")), []
        )

    def test_each_heading_deviation_warns_but_does_not_fail(self):
        # The five measured deviations (issue #372): the identical table
        # under each is invisible to the gate -- a warning naming the
        # heading, and zero findings (so the run still exits 0).
        deviations = [
            "## Files in `run-a`",  # no trailing slash
            "## Files in run-a/",  # no backticks
            "### Files in `run-a/`",  # h3
            "## Files committed in `run-a/`",  # extra words before
            "## Files in `run-a/` (committed bytes)",  # extra words after
        ]
        table = "| File | What |\n|---|---|\n| `whatever.json` | x |\n"
        for heading in deviations:
            text = f"{heading}\n\n{table}\n"
            unmatched = cef.ungated_receipt_headings(text)
            self.assertEqual(unmatched, [heading], heading)
            warning = cef.ungated_files_table_warning("sim/deck-parity/r.md", heading)
            self.assertIn("sim/deck-parity/r.md", warning)
            self.assertIn(heading, warning)
            findings, _ = cef.walk_files_tables(
                text, "sim/deck-parity", ["sim/deck-parity/run-a/whatever.json"]
            )
            self.assertEqual(findings, [], heading)

    def test_table_with_no_preceding_heading_warns(self):
        text = "| File | What |\n|---|---|\n| `a.json` | x |\n"
        self.assertEqual(cef.ungated_receipt_headings(text), [""])

    def test_fenced_comment_between_heading_and_table_is_not_warned(self):
        # Issue #408 shape (1): a bash fence between a gated heading and
        # its table must not make the warning fire -- the gate gates this
        # table, so the warning shadowing the gate stays silent.
        text = (
            "## Files in `run-a/`\n\n"
            "```bash\n"
            "# regenerate\n"
            "./x.sh\n"
            "```\n\n"
            "| File | What |\n"
            "|---|---|\n"
            "| `ok.json` | the thing |\n"
        )
        self.assertEqual(
            cef.parse_files_tables(text), [("run-a", [(["ok.json"], False)])]
        )
        self.assertEqual(cef.ungated_receipt_headings(text), [])

    def test_second_table_under_one_heading_warns(self):
        # Issue #408 shape (2): the parser consumes only the FIRST table
        # in a section, so a second "| File | What |" table under the same
        # gated heading is ungated and must be warned about.
        text = (
            "## Files in `run-a/`\n\n"
            "| File | What |\n"
            "|---|---|\n"
            "| `a.json` | one |\n"
            "\nSome prose.\n\n"
            "| File | What |\n"
            "|---|---|\n"
            "| `b.json` | two |\n"
        )
        self.assertEqual(
            cef.parse_files_tables(text), [("run-a", [(["a.json"], False)])]
        )
        self.assertEqual(
            cef.ungated_receipt_headings(text), ["## Files in `run-a/`"]
        )

    def test_receipt_docs_scope(self):
        tracked = {
            "sim/deck-parity/20261114-tt_25c_3.30v.md",  # top-level receipt
            "sim/deck-parity/README.md",  # excluded
            "sim/deck-parity/20261115-full-grid/parity-compare.md",  # nested
            "sim/macro-smoke/README.md",  # other experiment
            "README.md",  # repo root
        }
        self.assertEqual(cef.receipt_docs(tracked), [
            "sim/deck-parity/20261114-tt_25c_3.30v.md"
        ])

    def test_non_receipt_readme_tables_stay_silent(self):
        # The three sim/*/README.md directory listings are not receipts:
        # they carry | File | What | tables under unmatched headings, and
        # the warning must emit nothing for them (issue #372 AC).
        for readme in (
            "sim/access-power/README.md",
            "sim/macro-smoke/README.md",
            "sim/min-clock-pulse/README.md",
        ):
            text = (REPO / readme).read_text(encoding="utf-8")
            self.assertTrue(
                cef.ungated_receipt_headings(text),
                f"{readme} fixture: expected an ungated-shaped table",
            )
            self.assertEqual(
                cef.receipt_docs({readme}), [], f"{readme} must be out of scope"
            )

    def test_live_receipts_emit_no_warnings(self):
        tracked = set(p.relative_to(REPO).as_posix()
                      for p in (REPO / "sim" / "deck-parity").glob("*.md"))
        warnings: list[str] = []
        cef.check_ungated_receipt_tables(tracked, warnings)
        self.assertEqual(warnings, [])

    def test_live_coverage_is_nonzero_and_consistent(self):
        # Same walk, both outputs: the counts must equal the per-doc parse
        # totals, and the shipped tree must gate every receipt table.
        tracked = {
            p.relative_to(REPO).as_posix()
            for p in (REPO / "sim" / "deck-parity").rglob("*.md")
        }
        _, coverage = cef.walk_files_tables(
            (REPO / "sim" / "deck-parity" / "20261115-full-grid.md").read_text(
                encoding="utf-8"
            ),
            "sim/deck-parity",
            [],
        )
        self.assertEqual(coverage.tables, 1)
        self.assertEqual(coverage.rows + coverage.rows_exempt, 10)


class BenchAttestationTest(unittest.TestCase):
    """The item-9 gate (issue #357): every tracked
    sim/<experiment>/testbench/tb_* bench must be pinned by
    sim/testbenches.signoff.json."""

    PINNED = {
        "sim/README.md",
        "sim/lib/pdk_pin.txt",
        "sim/lib/run_corner_sweep.sh",
        "sim/macro-smoke/testbench/tb_ctrl_pulse.klt.spice",
        "sim/wordline-rc/testbench/tb_wl_rc_row64_x1.klt.spice",
    }
    BENCHES = {
        "sim/macro-smoke/testbench/tb_ctrl_pulse.klt.spice",
        "sim/wordline-rc/testbench/tb_wl_rc_row64_x1.klt.spice",
    }

    def test_exact_match_yields_no_gaps(self):
        self.assertEqual(cef.attestation_gaps(self.BENCHES, self.PINNED), [])

    def test_missing_bench_yields_one_gap_naming_it(self):
        benches = self.BENCHES | {
            "sim/access-power/testbench/tb_access_power.klt.spice"
        }
        self.assertEqual(
            cef.attestation_gaps(benches, self.PINNED),
            ["sim/access-power/testbench/tb_access_power.klt.spice"],
        )

    def test_pinned_non_bench_not_reported_spurious(self):
        # Gaps are computed over benches only: the wrapper's non-bench
        # pins (sim/README.md, sim/lib/*) are never flagged as extra.
        self.assertEqual(cef.attestation_gaps(set(), self.PINNED), [])

    def test_dut_copy_without_tb_prefix_is_not_a_bench(self):
        # sram_256x32.noarray.spice sits in both testbench/ dirs but is an
        # array-stripped DUT netlist, not a bench -- the tb_ prefix rule
        # keeps it out of the bench set (issue #357, Out of Scope).
        for path in (
            "sim/macro-smoke/testbench/sram_256x32.noarray.spice",
            "sim/min-clock-pulse/testbench/sram_256x32.noarray.spice",
        ):
            self.assertFalse(cef.is_bench_path(path), path)
        tracked = {
            *self.BENCHES,
            "sim/macro-smoke/testbench/sram_256x32.noarray.spice",
        }
        self.assertEqual(cef.bench_paths(tracked), self.BENCHES)

    def test_bench_path_requires_one_experiment_level(self):
        self.assertFalse(cef.is_bench_path("sim/macro-smoke/tb_x.spice"))
        self.assertFalse(cef.is_bench_path("sim/a/b/testbench/tb_x.spice"))
        self.assertFalse(cef.is_bench_path("design/testbench/tb_x.spice"))
        self.assertTrue(
            cef.is_bench_path(
                "sim/min-clock-pulse/testbench/tb_min_clk_h10_l10.klt.spice"
            )
        )

    def test_repo_wrapper_pins_every_committed_bench(self):
        # The shipped tree must satisfy the gate: walk the checkout (no
        # git) and compare against the committed wrapper.
        benches = {
            p.relative_to(REPO).as_posix()
            for p in (REPO / "sim").glob("*/testbench/tb_*")
            if p.is_file()
        }
        self.assertTrue(benches, "no benches found -- fixture broken")
        pinned = set(cef.pinned_attestation_paths(cef.TESTBENCH_ATTESTATION))
        self.assertEqual(cef.attestation_gaps(benches, pinned), [])


class EnumerationTest(unittest.TestCase):
    def test_docstring_and_success_message_enumerate_the_check(self):
        self.assertIn("Files in", cef.__doc__ or "")
        self.assertIn("Files in", inspect.getsource(cef.main))


if __name__ == "__main__":
    unittest.main()
