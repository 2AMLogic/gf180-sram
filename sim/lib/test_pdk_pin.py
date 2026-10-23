#!/usr/bin/env python3
"""Tests for the PDK revision pin check in sim/lib/pdk_env.sh (issue #173).

Builds fake PDK trees in a temp dir -- no real PDK, no ngspice -- so they run
in CI. Pins down: the pinned revision resolves; a stale `c6d73a3` tree is
rejected naming found vs pinned; an undeterminable revision is rejected; the
SOURCES-file fallback works; ~/.ciel wins over a stray ~/.volare.

Run: python3 sim/lib/test_pdk_pin.py   (or via `npm run test`)
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent
PIN = (LIB / "pdk_pin.txt").read_text().strip()
OLD = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"


def fake_variant(root: Path, sha: str | None, sources: str | None = None) -> Path:
    """<root>/<family>/versions/<sha>/gf180mcuD, symlinked at <root>/gf180mcuD."""
    base = root / "store" / "versions" / (sha or "unversioned")
    ng = base / "gf180mcuD" / "libs.tech" / "ngspice"
    ng.mkdir(parents=True)
    (ng / "sm141064.ngspice").write_text("*\n")
    (ng / "design.ngspice").write_text("*\n")
    if sources is not None:
        (base / "gf180mcuD" / "SOURCES").write_text(sources)
    root.mkdir(exist_ok=True)
    (root / "gf180mcuD").symlink_to(base / "gf180mcuD")
    return root


def resolve(home: Path, **env_extra: str) -> subprocess.CompletedProcess:
    env = {"PATH": os.environ["PATH"], "HOME": str(home), **env_extra}
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}/pdk_env.sh" && echo "VERSION=$GF180_PDK_VERSION"'],
        env=env, capture_output=True, text=True,
    )


class PdkPin(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.home = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_pinned_revision_resolves(self):
        fake_variant(self.home / ".ciel", PIN)
        r = resolve(self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"VERSION={PIN}", r.stdout)

    def test_stale_volare_tree_rejected(self):
        fake_variant(self.home / ".volare", OLD)
        r = resolve(self.home)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(OLD, r.stderr)
        self.assertIn(PIN, r.stderr)
        self.assertIn("mismatch", r.stderr)

    def test_ciel_preferred_over_stray_volare(self):
        fake_variant(self.home / ".ciel", PIN)
        fake_variant(self.home / ".volare", OLD)
        r = resolve(self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"VERSION={PIN}", r.stdout)

    def test_override_pointing_at_wrong_revision_rejected(self):
        fake_variant(self.home / ".ciel", PIN)
        stale = fake_variant(self.home / "stale", OLD)
        r = resolve(self.home, GF180_PDK_PATH=str(stale / "gf180mcuD"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(OLD, r.stderr)

    def test_undeterminable_revision_rejected(self):
        fake_variant(self.home / ".ciel", None)
        r = resolve(self.home)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("undeterminable", r.stderr)

    def test_sources_file_fallback(self):
        fake_variant(self.home / ".ciel", None, sources=f"open_pdks {PIN}\n")
        r = resolve(self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"VERSION={PIN}", r.stdout)


if __name__ == "__main__":
    unittest.main()
