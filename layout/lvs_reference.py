#!/usr/bin/env python3
"""Rewrite a ``design/netlist/*.spice`` reference for comparison against a
``klt extract`` netlist, changing **only** the device bulk terminals.

## Why this exists

``klt``'s gf180mcu extraction deck declares no well-tie/tap layer
(``ExtractionDeck.tap is None``), so the ``Nplus``-in-``Nwell`` and
``Pplus``-on-substrate tie strips this repo's bitcell actually draws cannot be
recognised as ties. Every extracted NMOS body therefore lands on a synthesized
global substrate net, and every extracted PMOS body on an anonymous ``Nwell``
net — ``klt extract`` says so itself in its own warning:

    N PMOS devices tie their body to an anonymous net with no DC bias path --
    'gf180mcu' has no distinct well-tie/tap layer for this PMOS body ...

The schematic reference ties those same bodies to ``VSS`` / ``VDD``. So an
otherwise-perfect layout can never report ``status: "match"`` against the
committed reference netlist: the four bulk terminals differ by construction of
the tool, not of the design.

This script makes that difference explicit and *mechanical* instead of a hand
edit: it rewrites the fourth (bulk) terminal of every ``X`` device card to the
net name the extractor uses, and changes nothing else — same devices, same
sizing, same connectivity, same file otherwise. The resulting netlist is a
**comparison aid, not a design source**; the design source stays
``design/netlist/*.spice``.

Filed upstream as a generic tool gap; see ``layout/README.md`` ("Known tool
gaps").

## Usage

    python3 layout/lvs_reference.py design/netlist/bitcell_6t.spice \\
        -o /tmp/bitcell_6t.bulkref.spice
"""

from __future__ import annotations

import argparse
import sys

#: Net names klt's extractor gives the bodies it cannot tie to a rail. The
#: NMOS one is the deck's own ``substrate_net`` global; the PMOS one is
#: arbitrary (an anonymous Nwell net), so any unused name works as long as
#: both sides of the compare agree — ``klt lvs`` matches nets by topology,
#: not by name.
NFET_BODY_NET = "vsubs"
PFET_BODY_NET = "vnw"

#: Terminal index of the bulk on a gf180mcu MOS ``X`` card:
#: ``X<name> D G S B <model> ...`` -> fields[4].
BULK_FIELD = 4


def rewrite(lines: list[str]) -> tuple[list[str], int]:
    out: list[str] = []
    rewritten = 0
    for line in lines:
        if line[:1] in ("X", "x"):
            fields = line.split()
            if len(fields) > BULK_FIELD + 1:
                model = fields[BULK_FIELD + 1].lower()
                if "pfet" in model:
                    fields[BULK_FIELD] = PFET_BODY_NET
                    rewritten += 1
                elif "nfet" in model:
                    fields[BULK_FIELD] = NFET_BODY_NET
                    rewritten += 1
                line = " ".join(fields) + "\n"
        out.append(line)
    return out, rewritten


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("netlist", help="reference SPICE netlist to rewrite")
    parser.add_argument("-o", "--out", required=True, help="output path")
    args = parser.parse_args()

    with open(args.netlist, encoding="utf-8") as handle:
        lines = handle.readlines()
    out, rewritten = rewrite(lines)
    if rewritten == 0:
        print(
            f"error: no MOS 'X' device cards found in {args.netlist}",
            file=sys.stderr,
        )
        return 1
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.writelines(out)
    print(f"wrote {args.out} ({rewritten} device bulk terminals rewritten)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
