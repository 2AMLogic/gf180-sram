#!/usr/bin/env python3
"""Regression tests for the #230 deck-mode cutover's two exit-2 tombstones.

The cutover retired the local sim grid launchers. Two entry points that
committed records' "Reproduce" blocks still name were reduced to loud
tombstones -- exit 2 with an explanation, never a silent exit 0:

- `sim/lib/run_mc_campaign.py` (the retired Monte Carlo pool CLI; the
  deck-mode replacement is `sim/lib/deck_adapter.py mc-build` +
  `klt sim --backend batch`).
- `sim/pex/write-margin/generate.sh` (the by-hand PEX write-margin
  workflow; its deck-mode port is tracked as #437).

Both were verified by hand at cutover review and pinned by nothing, so an
edit that made either exit 0 silently would strand a reader following a
committed record's Reproduce block. These subprocess tests make that loud.
Pure Python -- each tombstone refuses up front, before any ngspice or PDK
work, so no test here needs either.

Run: python3 sim/lib/test_cutover_tombstones.py   (or via `npm run test`)
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))

from repo_root import find_repo_root  # noqa: E402

REPO = find_repo_root(LIB)


class RunMcCampaignTombstoneTest(unittest.TestCase):
    """`python3 sim/lib/run_mc_campaign.py` refuses with exit 2."""

    def test_cli_exits_2_naming_the_retirement(self):
        proc = subprocess.run(
            [sys.executable, "sim/lib/run_mc_campaign.py"],
            capture_output=True,
            cwd=REPO,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 2, proc.stderr.decode())
        stderr = proc.stderr.decode()
        self.assertIn("retired", stderr)
        # The message must route the reader to the deck-mode replacement.
        self.assertIn("deck_adapter.py", stderr)


class WriteMarginGenerateTombstoneTest(unittest.TestCase):
    """`./sim/pex/write-margin/generate.sh` refuses with exit 2."""

    def test_script_exits_2_naming_the_interruption(self):
        proc = subprocess.run(
            ["./sim/pex/write-margin/generate.sh"],
            capture_output=True,
            cwd=REPO,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 2, proc.stderr.decode())
        stderr = proc.stderr.decode()
        self.assertIn("deck-mode cutover", stderr)
        # Refusal happens up front: nothing ran, so stdout stays empty and
        # the dead legs below the tombstone never execute.
        self.assertEqual(proc.stdout, b"")


if __name__ == "__main__":
    unittest.main()
