#!/usr/bin/env python3
"""Check the macro top netlist exposes exactly the #198 pins (issue #203).

Reads design/netlist/sram_256x32.spice and compares the `.subckt sram_256x32`
port list, in order, with spec/macro-interface-decision.md's table: A[7:0],
CEN, GWEN, CLK, D[31:0], WEN[31:0], Q[31:0] (all `[N-1:0]` descending) plus
VDD and VSS. Fails if any port is missing, extra or reordered, which also
catches an internal net (WL*, BL*, BLB*, control nets) leaking onto the macro
boundary. Polarity is a property of the logic, not the name; the functional
smoke test (sim/macro-smoke/) is what exercises it.

A `.v`/`.sv` argument (issue #468) is checked the same way against the
behavioural model's `module sram_256x32` port list: buses expand in
declaration order, so a reversed range (`[0:7]`) or a reordered header fails
exactly like a reordered .subckt. `expected()` stays the single owner of the
list (layout/macro/check_pins.py imports it).

    python3 design/check_macro_pins.py [netlist-or-verilog]
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


_VERILOG_SKIP = {
    "input", "output", "inout", "wire", "wand", "wor", "tri", "tri0", "tri1",
    "reg", "logic", "signed", "unsigned", "supply0", "supply1", "scalared",
    "vectored",
}


def verilog_ports(path):
    """Port list of `module sram_256x32 (...)` in a Verilog source, expanded
    in declaration order: a bus declared `[H:L]` yields bus[H], bus[H-1], ...
    bus[L], so the descending `[N-1:0]` order of the decision record is what
    `expected()` matches and a reversed `[0:N-1]` declaration fails."""
    text = Path(path).read_text()
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    m = re.search(r"\bmodule\s+sram_256x32\s*\((.*?)\)\s*;", text, re.S)
    if not m:
        raise SystemExit("no module sram_256x32(...) header in " + str(path))
    ports = []
    pending = None
    for tok in m.group(1).replace(",", " ").split():
        if tok in _VERILOG_SKIP:
            continue
        rng = re.fullmatch(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", tok)
        if rng:
            hi, lo = int(rng.group(1)), int(rng.group(2))
            pending = (hi, lo)
            continue
        if pending is not None:
            hi, lo = pending
            step = -1 if hi >= lo else 1
            ports += [f"{tok}[{i}]" for i in range(hi, lo + step, step)]
            pending = None
        else:
            ports.append(tok)
    return ports


def main():
    arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if arg.suffix in (".v", ".sv"):
        got, kind = verilog_ports(arg), "Verilog model"
    else:
        got, kind = ports(arg), "netlist"
    want = expected()
    if got != want:
        print(f"FAIL: {kind} {arg} has {len(got)} ports, expected {len(want)}")
        print("  missing:", [p for p in want if p not in got])
        print("  extra:  ", [p for p in got if p not in want])
        if sorted(got) == sorted(want):
            print("  same set, different order")
        return 1
    print(f"PASS: {kind} {arg.name} boundary is exactly the "
          f"{len(want) - 2} #198 signals + VDD/VSS, in order")
    return 0


if __name__ == "__main__":
    sys.exit(main())
