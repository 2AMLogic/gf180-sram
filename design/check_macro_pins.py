#!/usr/bin/env python3
"""Check the macro top netlist exposes exactly the #198 pins (issue #203).

Reads design/netlist/sram_256x32.spice and compares the `.subckt sram_256x32`
port list, in order, with spec/macro-interface-decision.md's table: A[7:0],
CEN, GWEN, CLK, D[31:0], WEN[31:0], Q[31:0] (all `[N-1:0]` descending) plus
VDD and VSS. Fails if any port is missing, extra or reordered, which also
catches an internal net (WL*, BL*, BLB*, control nets) leaking onto the macro
boundary. Polarity is a property of the logic, not the name; the functional
smoke test (sim/macro-smoke/) is what exercises it.

    python3 design/check_macro_pins.py [netlist]
"""
import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).parent / "netlist" / "sram_256x32.spice"


def expected():
    pins = [f"A[{i}]" for i in range(7, -1, -1)] + ["CEN", "GWEN", "CLK"]
    for bus in ("D", "WEN", "Q"):
        pins += [f"{bus}[{i}]" for i in range(31, -1, -1)]
    return pins + ["VDD", "VSS"]


def ports(netlist):
    lines = Path(netlist).read_text().splitlines()
    for i, line in enumerate(lines):
        if re.match(r"\.subckt\s+sram_256x32\s", line, re.I):
            text = line
            for cont in lines[i + 1 :]:
                if not cont.startswith("+"):
                    break
                text += " " + cont[1:]
            return text.split()[2:]
    raise SystemExit("no live .subckt sram_256x32 in " + str(netlist))


def main():
    got = ports(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    want = expected()
    if got != want:
        print(f"FAIL: {len(got)} ports, expected {len(want)}")
        print("  missing:", [p for p in want if p not in got])
        print("  extra:  ", [p for p in got if p not in want])
        if sorted(got) == sorted(want):
            print("  same set, different order")
        return 1
    print(f"PASS: macro boundary is exactly the {len(want) - 2} #198 signals + VDD/VSS, in order")
    return 0


if __name__ == "__main__":
    sys.exit(main())
