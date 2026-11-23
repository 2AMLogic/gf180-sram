#!/usr/bin/env python3
"""Tests for layout/common.py and its callers (issue #330).

The shared helpers consolidated by issue #330 are pinned here with no PDK
and no netlists: ``ROOT`` resolves to the repository root, ``load_module``
registers each load under its own ``sys.modules`` name (one file held as two
independent modules -- the property the periphery generators' distinct
``_sram_*_generate`` names rely on), ``nm`` converts um to dbu, and
``save_options`` disables GDSII header timestamps (skipped when klayout is
not installed; importing ``layout.common`` itself must never need klayout,
which this file demonstrates by importing it first).

The anti-duplication tests assert the consolidation sticks: no local
``def _load(`` and no ``def save_options(`` definitions remain anywhere
under ``layout/`` or ``views/`` -- every generator must take them from
``layout.common`` instead.

Run: python3 scripts/ci/test_layout_common.py   (or via `npm run test`)
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

import layout.common as common  # noqa: E402  (repo root put on sys.path above)

HAS_KLAYOUT = importlib.util.find_spec("klayout") is not None

# A small, dependency-free repo file to load under scratch names.
_CHECK_PINS_REL = "design/check_macro_pins.py"


def _python_files():
    for base in ("layout", "views"):
        for dirpath, _dirnames, filenames in os.walk(os.path.join(ROOT, base)):
            for fn in sorted(filenames):
                if fn.endswith(".py"):
                    yield os.path.join(dirpath, fn)


class TestRoot(unittest.TestCase):
    def test_root_is_repo_root(self):
        self.assertEqual(os.path.realpath(common.ROOT), os.path.realpath(ROOT))
        self.assertTrue(os.path.exists(os.path.join(common.ROOT, ".git")),
                        "ROOT must be the repository root (.git present)")


class TestLoadModule(unittest.TestCase):
    NAMES = ("_loom_test_load_a", "_loom_test_load_b")

    def tearDown(self):
        for name in self.NAMES:
            sys.modules.pop(name, None)

    def test_registers_each_name_in_sys_modules(self):
        mod = common.load_module(self.NAMES[0], _CHECK_PINS_REL)
        self.assertIs(sys.modules[self.NAMES[0]], mod)
        self.assertTrue(hasattr(mod, "expected"))  # the file actually executed

    def test_one_file_two_names_two_modules(self):
        a = common.load_module(self.NAMES[0], _CHECK_PINS_REL)
        b = common.load_module(self.NAMES[1], _CHECK_PINS_REL)
        self.assertIsNot(a, b)
        self.assertIs(sys.modules[self.NAMES[0]], a)
        self.assertIs(sys.modules[self.NAMES[1]], b)

    def test_reload_under_same_name_replaces_entry(self):
        a = common.load_module(self.NAMES[0], _CHECK_PINS_REL)
        b = common.load_module(self.NAMES[0], _CHECK_PINS_REL)
        self.assertIsNot(a, b)
        self.assertIs(sys.modules[self.NAMES[0]], b)

    @unittest.skipUnless(HAS_KLAYOUT, "klayout not installed (sram_256x32/generate.py imports it)")
    def test_distinct_names_never_collide_with_plain_imports(self):
        # The gen_socket.py contract (its _load_array_generator docstring):
        # the array generator is held under "sram_array_generate" so the bare
        # "generate" name stays free for its own `import generate as bitcell`.
        path_backup = list(sys.path)
        mod = common.load_module("_loom_test_array_gen", "layout/sram_256x32/generate.py")
        try:
            self.assertNotIn("generate", sys.modules)
            self.assertIs(sys.modules["_loom_test_array_gen"], mod)
            self.assertIs(mod.bitcell, sys.modules["generate"])
        finally:
            sys.modules.pop("_loom_test_array_gen", None)
            sys.modules.pop("generate", None)
            sys.path[:] = path_backup


class TestNm(unittest.TestCase):
    def test_um_to_dbu(self):
        self.assertEqual(common.nm(0.0), 0)
        self.assertEqual(common.nm(0.43), 430)
        self.assertEqual(common.nm(17.84), 17840)
        self.assertIsInstance(common.nm(0.28), int)


class TestSaveOptions(unittest.TestCase):
    @unittest.skipUnless(HAS_KLAYOUT, "klayout not installed (lazy-imported by layout.common)")
    def test_timestamps_disabled(self):
        opts = common.save_options()
        self.assertIsNotNone(opts)
        self.assertFalse(opts.gds2_write_timestamps)


class TestNoDuplicateHelpers(unittest.TestCase):
    def _files_defining(self, pattern):
        offenders = []
        for path in _python_files():
            if os.path.realpath(path) == os.path.realpath(os.path.join(ROOT, "layout", "common.py")):
                continue  # the single shared definition site
            with open(path, encoding="utf-8") as handle:
                if re.search(pattern, handle.read(), re.MULTILINE):
                    offenders.append(os.path.relpath(path, ROOT))
        return offenders

    def test_no_local_load_definitions(self):
        offenders = self._files_defining(r"^\s*def _load\(")
        self.assertEqual(offenders, [],
                         "def _load() copies must be replaced by layout.common.load_module")

    def test_no_save_options_definitions(self):
        offenders = self._files_defining(r"^\s*def save_options\(")
        self.assertEqual(offenders, [],
                         "def save_options() copies must be replaced by layout.common.save_options")


if __name__ == "__main__":
    unittest.main(verbosity=2)
