#!/usr/bin/env python3
"""Drift tests for the ratified corner matrix's single owner (#331).

No ngspice, no PDK, no fleet: every check here is a pure comparison between
`sim/lib/corner_matrix.py`, `sim/lib/run_corner_sweep.sh` (the shell copy that
cannot import Python and is deliberately the reference), the three Python
consumers, and the one **committed** artifact that renders the axis product.

Why these tests exist. The matrix used to live in four independent places and
only `deck_adapter.py` was guarded against the launcher
(`test_deck_adapter.py::test_corner_inc_matches_launcher` /
`::test_launcher_loop_axes_match`, both still in force and unweakened). The
product had already drifted once -- `spec/sram.md`'s prose said "9" until #53
corrected it to 27 (`spec/corner-count-correction.md`) -- and
`render_signoff_table.py` renders `3 x 3 x 3 = 27` into the committed
`sim/signoff-summary.md`. Change an axis with nothing watching and that
committed artifact keeps asserting the old product, silently. These tests are
what makes that loud.

Run: python3 sim/lib/test_corner_matrix.py   (or via `npm run test`)
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB.parent / "macro-smoke"))

import corner_matrix as cm  # noqa: E402
import deck_adapter as da  # noqa: E402
import render_signoff_table as rst  # noqa: E402
import run_mc_campaign as mc  # noqa: E402
import smoke  # noqa: E402
from repo_root import find_repo_root  # noqa: E402

REPO = find_repo_root(Path(__file__))
LAUNCHER = REPO / "sim/lib/run_corner_sweep.sh"


def launcher_axis(name: str) -> list[str]:
    """The launcher's own `NAME=(...)` shell array, as word tokens."""
    m = re.search(rf"^{name}=\((.*?)\)", LAUNCHER.read_text(), re.M)
    if m is None:  # pragma: no cover - a missing array is itself the failure
        raise AssertionError(f"{LAUNCHER} has no {name}=(...) array")
    return m.group(1).split()


def launcher_lib_section() -> dict[str, str]:
    """The launcher's own `declare -A LIB_SECTION=([k]=v ...)` mapping."""
    text = LAUNCHER.read_text()
    m = re.search(r"^declare -A LIB_SECTION=\((.*?)\)\s*$", text, re.M)
    if m is None:  # pragma: no cover
        raise AssertionError(f"{LAUNCHER} has no LIB_SECTION mapping")
    return dict(re.findall(r"\[(\w+)\]=(\S+)", m.group(1)))


class OwnerMatchesLauncherTest(unittest.TestCase):
    """The owner is compared against the shell copy, which stays the reference."""

    def test_axes_match_launcher(self):
        for name, axis in (("PROCESSES", cm.PROCESSES), ("TEMPS", cm.TEMPS), ("VDDS", cm.VDDS)):
            self.assertEqual(
                launcher_axis(name), list(axis),
                f"{name} drifted from {LAUNCHER.name}; both own the ratified "
                'spec/sram.md "Corner set" axis',
            )

    def test_axis_points_are_text(self):
        """Every axis point is the spec's literal label (corner_matrix's rule).

        `3.30` must survive into `tt_25c_3.30v` and `.param VDDC=3.30`; no
        numeric type round-trips that trailing zero. Temperature follows the
        same rule so there is one uniform type, not a per-axis exception.
        """
        for name, axis in (("PROCESSES", cm.PROCESSES), ("TEMPS", cm.TEMPS), ("VDDS", cm.VDDS)):
            for point in axis:
                self.assertIsInstance(point, str, f"{name} point {point!r} is not text")

    def test_lib_section_matches_launcher(self):
        self.assertEqual(launcher_lib_section(), cm.LIB_SECTION)
        self.assertEqual(sorted(cm.LIB_SECTION), sorted(cm.PROCESSES))

    def test_corner_count_is_the_axis_product(self):
        product = len(cm.PROCESSES) * len(cm.TEMPS) * len(cm.VDDS)
        ids = cm.corner_ids()
        self.assertEqual(len(ids), product)
        self.assertEqual(len(set(ids)), product, "corner ids are not distinct")
        # The launcher derives its count from its own arrays rather than
        # hardcoding it (run_corner_sweep.sh, "Derived, never hardcoded");
        # confirm it still does, so the two counts cannot disagree.
        self.assertRegex(
            LAUNCHER.read_text(),
            r"CORNER_COUNT=\$\(\(\s*\$\{#PROCESSES\[@\]\}\s*\*\s*\$\{#TEMPS\[@\]\}\s*\*\s*\$\{#VDDS\[@\]\}\s*\)\)",
            "run_corner_sweep.sh no longer derives CORNER_COUNT from its axes",
        )

    def test_corner_order_is_the_launcher_loop_order(self):
        """process outermost, then temperature, then voltage."""
        expected = [
            cm.corner_id(p, t, v)
            for p in launcher_axis("PROCESSES")
            for t in launcher_axis("TEMPS")
            for v in launcher_axis("VDDS")
        ]
        self.assertEqual(cm.corner_ids(), expected)


class ConsumersHaveNoPrivateCopyTest(unittest.TestCase):
    """One assertion per consumer: it reports the owner's corners, in order."""

    def test_deck_adapter(self):
        self.assertEqual(da.corner_ids(), cm.corner_ids())
        self.assertIs(da.LIB_SECTION, cm.LIB_SECTION)
        self.assertEqual(list(da.TEMPS), list(cm.TEMPS))

    def test_render_signoff_table(self):
        self.assertEqual(rst.CORNER_ORDER, cm.corner_ids())
        # The rendered "N x N x N = N" note reads these three names directly,
        # so identity here is what keeps the committed artifact's product live.
        self.assertIs(rst.PROCESSES, cm.PROCESSES)
        self.assertIs(rst.TEMPS, cm.TEMPS)
        self.assertIs(rst.VDDS, cm.VDDS)

    def test_run_mc_campaign(self):
        self.assertIs(mc.LIB_SECTION, cm.LIB_SECTION)
        self.assertIs(mc.corner_id, cm.corner_id)
        self.assertEqual(
            [mc.corner_id(*c) for c in cm.corners()], cm.corner_ids(),
            "run_mc_campaign's corner ids drifted from the owner's",
        )

    def test_macro_smoke_request(self):
        corners = smoke.klt_request()["corners"]
        self.assertEqual(
            corners["process"],
            [{"name": p, "sections": [cm.LIB_SECTION[p]]} for p in cm.PROCESSES],
        )
        self.assertEqual(corners["supply_v"]["vvdd"], [float(v) for v in cm.VDDS])
        self.assertEqual(corners["temperature_c"], [int(t) for t in cm.TEMPS])
        # klt sim crosses these three axes, so the request sweeps the product.
        self.assertEqual(
            len(corners["process"]) * len(corners["temperature_c"]) * len(corners["supply_v"]["vvdd"]),
            len(cm.corner_ids()),
        )

    def test_macro_smoke_committed_request_is_current(self):
        """The checked-in request must be what `smoke.py gen-klt` emits today."""
        committed = json.loads(
            (REPO / "sim/macro-smoke/requests/macro_write_read.json").read_text()
        )
        self.assertEqual(committed, smoke.klt_request())


class CommittedSignoffArtifactTest(unittest.TestCase):
    """The named hazard: a committed artifact asserting a stale axis product."""

    def setUp(self):
        self.text = (REPO / "sim/signoff-summary.md").read_text()

    def test_table_rows_are_the_owners_corners_in_order(self):
        rows = re.findall(r"^\| (\w\S*c_\S+v) \|", self.text, re.M)
        self.assertEqual(rows, cm.corner_ids())

    def test_rendered_product_matches_the_owner(self):
        p, t, v, total = (
            len(cm.PROCESSES), len(cm.TEMPS), len(cm.VDDS), len(cm.corner_ids()),
        )
        self.assertIn(f"the table below has {total} rows", self.text)
        self.assertIn(f"`{p} x {t} x {v} = {total}`", self.text)
        self.assertIn(f"all {total} corner points", self.text)

    def test_artifact_is_byte_identical_to_a_fresh_render(self):
        """`render_signoff_table.py` is the only author of this file.

        Regenerating it must be a no-op -- that is what makes the two checks
        above guards on the renderer rather than on a hand-edited file. Run as
        a subprocess, exactly the way the repo regenerates it.
        """
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(REPO / "sim/lib/render_signoff_table.py"), str(REPO)],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(proc.stdout, self.text)


if __name__ == "__main__":
    unittest.main()
