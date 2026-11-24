#!/usr/bin/env python3
"""Lockstep tests for render_signoff_table's per-corner table (#488).

No ngspice, no PDK, no fleet: each test renders the real committed records
with a synthetic sixth RECORD_CLAIMS family patched in.

Why these tests exist. #487 drove render()'s per-corner table *body* from
RECORD_CLAIMS, but the header row and its `|---|` separator were still
hardcoded 12-column text and the "Source records" / "Aggregate" loops
still iterated FAMILY_LABELS. A sixth family therefore rendered 14-cell
body rows under a 12-column header -- a malformed Markdown table, not an
error -- and a family with no FAMILY_LABELS entry was silently dropped
from two sections. The CI byte-identity gate cannot see either: a
regenerated artifact is always "in sync" with its own generator. These
tests make the invariant mechanical.

Run: python3 sim/lib/test_render_signoff_table.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))

import render_signoff_table as rst  # noqa: E402
from repo_root import find_repo_root  # noqa: E402

REPO = find_repo_root(Path(__file__))

# The synthetic sixth family, bound to read SNM's committed record so
# render() resolves it from real evidence with nothing stubbed on disk.
SIXTH = "read-snm-dup"
SIXTH_LABEL = "Read SNM (again)"


def render_with(with_label: bool = True) -> str:
    """render() over the committed records with SIXTH appended to
    RECORD_CLAIMS. Its label, when present, is placed *first* in
    FAMILY_LABELS, so a section that iterates FAMILY_LABELS puts the sixth
    family first while one that iterates RECORD_CLAIMS puts it last."""
    claims = {**rst.RECORD_CLAIMS, SIXTH: rst.RECORD_CLAIMS["read-snm"]}
    labels = dict(rst.FAMILY_LABELS)
    if with_label:
        labels = {SIXTH: SIXTH_LABEL, **labels}
    with mock.patch.object(rst, "RECORD_CLAIMS", claims), \
            mock.patch.object(rst, "FAMILY_LABELS", labels):
        return rst.render(REPO)


def section(text: str, heading: str) -> list[str]:
    """The lines between `## <heading>` and the next `## ` heading."""
    return text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0].splitlines()


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip("|").split("|")]


def bullets(text: str, heading: str) -> list[str]:
    return [ln for ln in section(text, heading) if ln.startswith("- ")]


class PerCornerTableFollowsRecordClaimsTest(unittest.TestCase):
    """Header, `|---|` separator and body rows are one table: same width,
    columns in RECORD_CLAIMS order, each `<label> (<unit>)` then `Verdict`."""

    def setUp(self):
        table = [cells(ln) for ln in section(render_with(), "Per-corner results")
                 if ln.startswith("|")]
        self.header, self.separator, *self.body = table
        self.width = 2 + 2 * (len(rst.RECORD_CLAIMS) + 1)

    def test_header_separator_and_every_body_row_have_the_same_width(self):
        self.assertEqual(len(self.header), self.width)
        self.assertEqual(self.separator, ["---"] * self.width)
        self.assertTrue(self.body, "no per-corner rows rendered")
        for row in self.body:
            self.assertEqual(len(row), self.width, row)

    def test_header_columns_are_the_record_claims_families_with_their_units(self):
        self.assertEqual(self.header[0], "Corner")
        self.assertEqual(self.header[-1], "Row overall (SNM + margin)")
        labels = self.header[1:-1:2]
        verdicts = self.header[2:-1:2]
        self.assertEqual(verdicts, ["Verdict"] * (len(rst.RECORD_CLAIMS) + 1))
        self.assertEqual(
            labels,
            [
                "Read SNM (V)",
                "Hold SNM (V)",
                "Write margin (V)",
                "Read access time (s)",
                "Write access time (s)",
                "Read SNM (again) (V)",
            ],
        )

    def test_body_rows_carry_the_sixth_familys_record(self):
        for row in self.body:
            self.assertEqual(row[-1], "PASS", row)
            self.assertEqual(row[11], row[1], row)
            self.assertEqual(row[12], "RECORDED", row)


class SectionsFollowRecordClaimsTest(unittest.TestCase):
    """Source records and Aggregate iterate RECORD_CLAIMS and index
    FAMILY_LABELS[family] -- never iterate the label table itself."""

    def test_source_records_and_aggregate_list_every_family_in_record_claims_order(self):
        text = render_with()
        for heading in ("Source records", "Aggregate"):
            with self.subTest(heading=heading):
                lines = bullets(text, heading)
                self.assertEqual(len(lines), len(rst.RECORD_CLAIMS) + 1)
                self.assertTrue(lines[0].startswith("- Read SNM: "), lines[0])
                self.assertTrue(lines[-1].startswith(f"- {SIXTH_LABEL}: "), lines[-1])

    def test_family_without_a_label_is_a_loud_keyerror(self):
        with self.assertRaises(KeyError) as cm:
            render_with(with_label=False)
        self.assertEqual(cm.exception.args, (SIXTH,))


if __name__ == "__main__":
    unittest.main()
