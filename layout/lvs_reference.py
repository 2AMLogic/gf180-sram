#!/usr/bin/env python3
"""Rewrite a ``design/netlist/*.spice`` reference for comparison against a
``klt extract`` netlist, changing **only** the device bulk terminals.

## Why this exists

``klt``'s gf180mcu extraction deck declares no well-tie/tap layer
(``ExtractionDeck.tap is None``), so historically the ``Nplus``-in-``Nwell``
and ``Pplus``-on-substrate tie strips this repo's bitcell draws could not be
recognised as ties: every extracted NMOS body landed on a synthesized global
substrate net, and every extracted PMOS body on an anonymous ``Nwell`` net,
regardless of what the schematic reference says. `klt extract` used to warn
about exactly this ("N PMOS devices tie their body to an anonymous net with
no DC bias path -- 'gf180mcu' has no distinct well-tie/tap layer for this
PMOS body").

That per-device-type bulk-net name is **not a stable contract**: it depends
on how the installed `klt` build's extraction deck resolves the drawn ties,
and it has already changed at least once without a `klt` version bump (see
[klayout-tools#1084](https://github.com/2AMLogic/klayout-tools/issues/1084)
and the follow-up that found the anonymous-net behaviour gone -- current
builds instead fold the drawn ties straight into the `VDD`/`VSS` nets they
contact, which already matches the schematic reference and needs no
rewriting at all).

So instead of hardcoding the expected bulk-net names, this script **derives**
them from an actual ``klt extract`` netlist (``--layout-netlist``): it scans
that netlist's device (``M``) cards for the bulk terminal the extractor
assigned to each device type (``nfet``/``pfet``), then rewrites the fourth
(bulk) terminal of every reference ``X`` device card of that type to match --
same devices, same sizing, same connectivity, same file otherwise. When the
extractor already ties bulk to `VDD`/`VSS` (current behaviour), the rewrite
is a no-op; when it synthesizes a separate net instead (the historical gap),
the rewrite substitutes that net's actual name, not a guess. The resulting
netlist is a **comparison aid, not a design source**; the design source stays
``design/netlist/*.spice``.

Filed upstream as a generic tool gap; see ``layout/README.md`` ("Known tool
gaps").

## Usage

    klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds \\
        -o /tmp/bitcell.spice
    python3 layout/lvs_reference.py design/netlist/bitcell_6t.spice \\
        --layout-netlist /tmp/bitcell.spice -o /tmp/bitcell_6t.bulkref.spice
"""

from __future__ import annotations

import argparse
import sys

#: Terminal index of the bulk on a gf180mcu MOS device card:
#: ``<prefix><name> D G S B <model> ...`` -> fields[4].
BULK_FIELD = 4

#: Device-card prefixes used by the reference netlist (SPICE subcircuit
#: calls, ``X...``) and by ``klt extract``'s output (raw MOSFET cards,
#: ``M...``) respectively.
REFERENCE_PREFIXES = ("X", "x")
LAYOUT_PREFIXES = ("M", "m")

#: Device types this script rewrites bulk terminals for.
DEVICE_TYPES = ("nfet", "pfet")


def _device_type(model: str) -> str | None:
    model = model.lower()
    for device_type in DEVICE_TYPES:
        if device_type in model:
            return device_type
    return None


def detect_body_nets(layout_lines: list[str]) -> dict[str, str]:
    """Scan a ``klt extract``-produced netlist and return, per device type
    (``nfet``/``pfet``), the bulk net name that extractor run actually
    assigned -- the first one seen for each type."""
    body_nets: dict[str, str] = {}
    for line in layout_lines:
        if line[:1] not in LAYOUT_PREFIXES:
            continue
        fields = line.split()
        if len(fields) <= BULK_FIELD + 1:
            continue
        device_type = _device_type(fields[BULK_FIELD + 1])
        if device_type is not None:
            body_nets.setdefault(device_type, fields[BULK_FIELD])
    return body_nets


def rewrite(lines: list[str], body_nets: dict[str, str]) -> tuple[list[str], int]:
    out: list[str] = []
    rewritten = 0
    for line in lines:
        if line[:1] in REFERENCE_PREFIXES:
            fields = line.split()
            if len(fields) > BULK_FIELD + 1:
                device_type = _device_type(fields[BULK_FIELD + 1])
                if device_type is not None and device_type in body_nets:
                    fields[BULK_FIELD] = body_nets[device_type]
                    rewritten += 1
                    line = " ".join(fields) + "\n"
        out.append(line)
    return out, rewritten


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("netlist", help="reference SPICE netlist to rewrite")
    parser.add_argument(
        "--layout-netlist",
        required=True,
        help=(
            "klt extract-produced netlist to read this run's actual "
            "per-device-type (nfet/pfet) bulk net names from -- see the "
            "module docstring for why this isn't hardcoded"
        ),
    )
    parser.add_argument("-o", "--out", required=True, help="output path")
    args = parser.parse_args()

    with open(args.layout_netlist, encoding="utf-8") as handle:
        layout_lines = handle.readlines()
    body_nets = detect_body_nets(layout_lines)
    missing = [t for t in DEVICE_TYPES if t not in body_nets]
    if missing:
        print(
            f"error: no {'/'.join(missing)} device(s) found in "
            f"{args.layout_netlist} to detect the bulk net from",
            file=sys.stderr,
        )
        return 1

    with open(args.netlist, encoding="utf-8") as handle:
        lines = handle.readlines()
    out, rewritten = rewrite(lines, body_nets)
    if rewritten == 0:
        print(
            f"error: no MOS 'X' device cards found in {args.netlist}",
            file=sys.stderr,
        )
        return 1
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.writelines(out)
    print(
        f"wrote {args.out} ({rewritten} device bulk terminals rewritten to "
        f"{body_nets})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
