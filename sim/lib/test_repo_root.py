#!/usr/bin/env python3
"""Tests for sim/lib/repo_root.py (issue #287).

Run: python3 sim/lib/test_repo_root.py   (or via `npm run test`)
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from repo_root import find_repo_root

LIB = Path(__file__).resolve().parent


class FindRepoRootTest(unittest.TestCase):
    def test_nested_depths_resolve_same_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / ".git").mkdir()
            for rel in ("sim/lib", "sim/lib/common", "a/b/c/d"):
                d = root / rel
                d.mkdir(parents=True)
                self.assertEqual(find_repo_root(d / "script.py"), root)

    def test_git_file_marker_for_worktrees(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / ".git").write_text("gitdir: /elsewhere\n")
            d = root / "sim" / "lib"
            d.mkdir(parents=True)
            self.assertEqual(find_repo_root(d), root)

    def test_no_marker_raises(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td).resolve() / "sim" / "lib"
            d.mkdir(parents=True)
            if any((p / ".git").exists() for p in (d, *d.parents)):
                self.skipTest("temp dir sits inside a git checkout")
            with self.assertRaises(RuntimeError):
                find_repo_root(d)

    def test_copied_script_in_nested_dir_uses_helper(self):
        """A script copied one level deeper still resolves the repo root."""
        import shutil
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / ".git").mkdir()
            nested = root / "sim" / "lib" / "common"
            nested.mkdir(parents=True)
            for name in ("repo_root.py", "render_signoff_table.py"):
                shutil.copy(LIB / name, nested / name)
            code = (
                "import sys; sys.path.insert(0, sys.argv[1]);"
                "import render_signoff_table as r; print(r.default_repo_root())"
            )
            out = subprocess.run(
                [sys.executable, "-I", "-c", code, str(nested)],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            self.assertEqual(Path(out), root)


if __name__ == "__main__":
    unittest.main()
