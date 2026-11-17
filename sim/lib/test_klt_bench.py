#!/usr/bin/env python3
"""Offline contract tests for sim/lib/klt_bench.py (#388).

No ngspice, no PDK, no fleet. klt_bench owns the `klt sim` request skeleton
and the Q-word defined-bit rule that the three macro-netlist benches
(macro-smoke, access-power, min-clock-pulse) previously copied, so these tests
pin the rule itself: the strictly-outside-20% definedness band against the
corner's own VDD (a probe exactly on 0.2*VDD or 0.8*VDD is undefined), the
VDD/2 bit decision (a tie reads 0), the unmeasured-bit fail-closed counting,
the `q{b}_{suffix}` FIND emitter's exact card text and ordering, and the
request skeleton's literal values and key order -- the order is what keeps
every bench's committed request JSON byte-identical across the switch.

Run: python3 sim/lib/test_klt_bench.py   (or via `npm run test`)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))

import corner_matrix as cm  # noqa: E402
import klt_bench  # noqa: E402

VDD = 3.3


def ideal_word(word):
    """32 probe voltages that read `word` unambiguously at any VDD: the rail
    itself for 1 bits, 0.0 V for 0 bits."""
    return [vdd_if_bit_or_zero(VDD, word, b) for b in range(32)]


def vdd_if_bit_or_zero(vdd, word, b):
    return vdd if (word >> b) & 1 else 0.0


class ReadWordTest(unittest.TestCase):
    """The defined-bit rule, at and around both boundaries."""

    def test_ideal_rails_rebuild_the_word(self):
        word, undefined, unmeasured = klt_bench.read_word(ideal_word(0xDEADBEEF), VDD)
        self.assertEqual((word, undefined, unmeasured), (0xDEADBEEF, 0, 0))

    def test_exactly_20pct_of_vdd_is_undefined(self):
        bits = ideal_word(0x0)
        bits[3] = 0.2 * VDD
        _, undefined, unmeasured = klt_bench.read_word(bits, VDD)
        self.assertEqual((undefined, unmeasured), (1, 0))

    def test_exactly_80pct_of_vdd_is_undefined(self):
        bits = ideal_word(0x0)
        bits[7] = 0.8 * VDD
        _, undefined, _ = klt_bench.read_word(bits, VDD)
        self.assertEqual(undefined, 1)

    def test_just_inside_the_bands_is_defined(self):
        bits = ideal_word(0x0)
        bits[3] = 0.2 * VDD - 1e-9  # strictly below the 20% rail -> defined 0
        bits[7] = 0.8 * VDD + 1e-9  # strictly above the 80% rail -> defined 1
        word, undefined, unmeasured = klt_bench.read_word(bits, VDD)
        self.assertEqual((undefined, unmeasured), (0, 0))
        self.assertEqual((word >> 3) & 1, 0)
        self.assertEqual((word >> 7) & 1, 1)

    def test_exactly_half_vdd_reads_zero(self):
        bits = ideal_word(0x0)
        bits[11] = VDD / 2  # the tie is not > VDD/2, so the bit reads 0
        word, undefined, _ = klt_bench.read_word(bits, VDD)
        self.assertEqual((word >> 11) & 1, 0)
        self.assertEqual(undefined, 1)  # mid-rail is inside the undefined band

    def test_just_above_half_vdd_reads_one(self):
        bits = ideal_word(0x0)
        bits[11] = VDD / 2 + 1e-9
        word, _, _ = klt_bench.read_word(bits, VDD)
        self.assertEqual((word >> 11) & 1, 1)

    def test_band_scales_with_that_corners_own_vdd(self):
        # The same absolute voltage is defined-low at 3.3 V and undefined at
        # 2.97 V: grading is against the corner's own supply, never a global.
        v = 0.62  # strictly below 20% of 3.3 V (0.66), at/above 20% of 2.97 V (0.594)
        self.assertLess(v, 0.2 * VDD)
        self.assertGreaterEqual(v, 0.2 * 2.97)
        bits = ideal_word(0x0)
        bits[0] = v
        _, undefined_low_vdd, _ = klt_bench.read_word(bits, VDD)
        _, undefined_at_297, _ = klt_bench.read_word(bits, 2.97)
        self.assertEqual(undefined_low_vdd, 0)
        self.assertEqual(undefined_at_297, 1)

    def test_unmeasured_bit_is_counted_and_contributes_zero(self):
        expected = 0xDEADBEEF & ~(1 << 5)
        bits = ideal_word(0xDEADBEEF)
        bits[5] = None
        word, undefined, unmeasured = klt_bench.read_word(bits, VDD)
        self.assertEqual((word, undefined, unmeasured), (expected, 0, 1))

    def test_all_unmeasured_is_an_empty_word(self):
        self.assertEqual(klt_bench.read_word([None] * 32, VDD), (0, 0, 32))


class QProbesTest(unittest.TestCase):
    """The FIND v(Q[b]) emitter: exact card text, 32 per sample, ordered."""

    def test_exact_card_text(self):
        probe = klt_bench.q_probes([("op3", 45.0)])[0]
        self.assertEqual(
            probe,
            {
                "name": "q0_op3",
                "spice": ".meas tran q0_op3 FIND v(Q[0]) AT=45n",
                "unit": "V",
            },
        )

    def test_at_time_uses_g_formatting(self):
        probes = klt_bench.q_probes([("rd", 14.1)])
        self.assertEqual(probes[9]["spice"], ".meas tran q9_rd FIND v(Q[9]) AT=14.1n")

    def test_32_bits_per_sample_in_sample_then_bit_order(self):
        probes = klt_bench.q_probes([("op1", 25.0), ("rd", 45.0)])
        self.assertEqual(len(probes), 64)
        self.assertEqual([p["name"] for p in probes[:2]], ["q0_op1", "q1_op1"])
        self.assertEqual(probes[31]["name"], "q31_op1")
        self.assertEqual(probes[32]["name"], "q0_rd")
        self.assertEqual(probes[63]["name"], "q31_rd")

    def test_suffix_prefixes_the_bit_index_not_the_other_way(self):
        probes = klt_bench.q_probes([("x", 1.0)])
        self.assertEqual(probes[12]["name"], "q12_x")


class BaseRequestTest(unittest.TestCase):
    """The skeleton: literal values, and the key order the JSONs serialise."""

    def test_literal_skeleton(self):
        req = klt_bench.base_request("../testbench/tb.klt.spice", "0.02n 205n", [])
        self.assertEqual(
            req,
            {
                "netlist": "../testbench/tb.klt.spice",
                "engine": "ngspice",
                "models": {"lib": klt_bench.MODELS_LIB},
                "corners": klt_bench.corners_block(),
                "analysis": {"kind": "tran", "args": "0.02n 205n"},
                "measurements": [],
                "netlist_source": "schematic",
                "options": {"timeout_s": klt_bench.TIMEOUT_S},
            },
        )

    def test_key_order_is_the_committed_json_order(self):
        """json.dumps preserves dict insertion order, so this order IS the
        committed requests' byte format."""
        req = klt_bench.base_request("n", "a", [])
        self.assertEqual(
            list(req),
            [
                "netlist",
                "engine",
                "models",
                "corners",
                "analysis",
                "measurements",
                "netlist_source",
                "options",
            ],
        )

    def test_shared_constants_are_the_ones_the_copies_carried(self):
        self.assertEqual(
            klt_bench.MODELS_LIB,
            "$PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.ngspice",
        )
        self.assertEqual(klt_bench.TIMEOUT_S, 1500)

    def test_corners_block_is_the_ratified_matrix(self):
        block = klt_bench.corners_block()
        self.assertEqual(
            block["process"],
            [{"name": p, "sections": [cm.LIB_SECTION[p]]} for p in cm.PROCESSES],
        )
        self.assertEqual(block["supply_v"]["vvdd"], [float(v) for v in cm.VDDS])
        self.assertEqual(block["temperature_c"], [int(t) for t in cm.TEMPS])
        self.assertEqual(
            len(block["process"]) * len(block["temperature_c"]) * len(block["supply_v"]["vvdd"]),
            len(cm.corner_ids()),
        )


if __name__ == "__main__":
    unittest.main()
