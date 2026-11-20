#!/usr/bin/env python3
"""Tests for the Verilog leg of design/check_macro_pins.py (issue #468).

The checker's `verilog_ports()` expands a Verilog module header's buses in
declaration order against the same `expected()` list the SPICE netlist leg
uses. These tests pin both directions with no simulator and no PDK: the
committed model matches; a reversed bus range (`[0:7]`, the decision
record's descending `[N-1:0]` order violated), a reordered header, an extra
port and a missing bus each fail; the committed netlist still matches; and
a source with no `module sram_256x32` header is refused.

Run: python3 scripts/ci/test_check_macro_pins.py   (or via `npm run test`)
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_spec = importlib.util.spec_from_file_location(
    "_check_macro_pins", os.path.join(ROOT, "design", "check_macro_pins.py")
)
cmp_ = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cmp_)

MODEL = os.path.join(ROOT, "views", "sram_256x32.v")
NETLIST = os.path.join(ROOT, "design", "netlist", "sram_256x32.spice")

# The committed model's header, mutated per test below.
HEADER = """
module sram_256x32 (
    input  wire [7:0]  A,
    input  wire        CEN,
    input  wire        GWEN,
    input  wire        CLK,
    input  wire [31:0] D,
    input  wire [31:0] WEN,
    output reg  [31:0] Q,
    inout  wire        VDD,
    inout  wire        VSS
);
endmodule
"""


def ports_of(source: str) -> list[str]:
    with tempfile.NamedTemporaryFile("w", suffix=".v", delete=False) as handle:
        handle.write(source)
        path = handle.name
    try:
        return cmp_.verilog_ports(path)
    finally:
        os.unlink(path)


class VerilogPins(unittest.TestCase):
    def test_committed_model_matches_expected(self):
        self.assertEqual(cmp_.verilog_ports(MODEL), cmp_.expected())

    def test_committed_netlist_still_matches(self):
        self.assertEqual(cmp_.ports(NETLIST), cmp_.expected())

    def test_reversed_bus_range_fails(self):
        got = ports_of(HEADER.replace("[7:0]  A", "[0:7]  A"))
        self.assertNotEqual(got, cmp_.expected())

    def test_reordered_header_fails(self):
        got = ports_of(HEADER.replace("    input  wire        CEN,\n", "")
                             .replace("    input  wire        GWEN,", "    input  wire        GWEN, CEN,"))
        self.assertNotEqual(got, cmp_.expected())

    def test_extra_port_fails(self):
        got = ports_of(HEADER.replace("    inout  wire        VSS", "    inout  wire        VSS,\n    inout  wire        VSSE"))
        self.assertNotEqual(got, cmp_.expected())

    def test_missing_bus_fails(self):
        got = ports_of(HEADER.replace("    input  wire [31:0] WEN,\n", ""))
        self.assertNotEqual(got, cmp_.expected())

    def test_no_module_header_refused(self):
        with self.assertRaises(SystemExit):
            ports_of("module other_macro (\n);\nendmodule\n")

    def test_comments_in_header_ignored(self):
        got = ports_of(HEADER.replace("    input  wire        CEN,",
                                      "    input  wire        CEN, /* clock enable, active low */"))
        self.assertEqual(got, cmp_.expected())


if __name__ == "__main__":
    unittest.main(verbosity=2)
