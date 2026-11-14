#!/usr/bin/env python3
"""Check the macro GDS pin labels against the #198 pin list (issue #247).

Compares the labels of ``layout/macro/sram_256x32.gds`` with the list
``design/check_macro_pins.py`` already holds for the netlist: A[7:0], CEN, GWEN, CLK,
D[31:0], WEN[31:0], Q[31:0], VDD, VSS. Fails on

* any pin missing, any extra label, or a duplicated one (labels in every cell count,
  so a block's leftover label is an extra pin);
* a signal label that is not on the Metal2 label layer (36/10), not over Metal2 drawn
  metal (36/0), or not on the bottom edge (``spec/periphery-architecture.md`` "Pin
  placement and layers");
* a supply label that is not on the Metal3 label layer (42/10), not over Metal3 metal
  (42/0), or not on the top edge;
* ``D[i]``/``WEN[i]``/``Q[i]`` not increasing along x with ``i`` (slice ``i`` is the
  ``i``-th 17.84 um slice from the left).

    python3 layout/macro/check_pins.py [macro.gds]

Needs the ``klayout`` module (``uv run --with klayout python3 ...``).
"""
import importlib.util
import os
import re
import sys

import klayout.db as kdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT = os.path.join(HERE, "sram_256x32.gds")
TOP = "sram_256x32"
EDGE_UM = 1.0          # a bottom-edge pin label sits within this of the bottom of the bbox
TOP_EDGE_UM = 12.0     # the supply straps lie within this of the top of the bbox


def expected():
    spec = importlib.util.spec_from_file_location("_check_macro_pins", os.path.join(ROOT, "design", "check_macro_pins.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.expected()


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    ly = kdb.Layout()
    ly.read(path)
    top = ly.cell(TOP)
    bbox = top.dbbox()
    labels = []                                # (name, (layer, dt), x, y, cell)
    for c in ly.each_cell():
        for li in ly.layer_indexes():
            info = ly.get_info(li)
            for s in c.shapes(li).each():
                if s.is_text():
                    labels.append((s.text.string, (info.layer, info.datatype),
                                   s.text.x * ly.dbu, s.text.y * ly.dbu, c.name))
    want = expected()
    errors = []
    names = [l[0] for l in labels]
    missing = [p for p in want if p not in names]
    extra = sorted({n for n in names if n not in want})
    dup = sorted({n for n in names if names.count(n) > 1})
    if missing:
        errors.append(f"missing pins: {missing}")
    if extra:
        errors.append(f"extra labels: {extra}")
    if dup:
        errors.append(f"duplicated labels: {dup}")
    stray = sorted({l[4] for l in labels if l[4] != TOP})
    if stray:
        errors.append(f"labels outside the top cell, in {stray}")

    metal = {}
    for lp in ((36, 0), (42, 0)):
        li = ly.find_layer(*lp)
        r = kdb.Region(top.begin_shapes_rec(li)) if li is not None else kdb.Region()
        r.merge()
        metal[lp] = r

    xs = {}
    for name, lp, x, y, _ in labels:
        if name not in want:
            continue
        supply = name in ("VDD", "VSS")
        want_lbl, want_mtl = ((42, 10), (42, 0)) if supply else ((36, 10), (36, 0))
        if lp != want_lbl:
            errors.append(f"{name}: label on {lp[0]}/{lp[1]}, expected {want_lbl[0]}/{want_lbl[1]}")
        probe = kdb.Region(kdb.Box(int(round(x / ly.dbu)) - 2, int(round(y / ly.dbu)) - 2,
                                   int(round(x / ly.dbu)) + 2, int(round(y / ly.dbu)) + 2))
        if (probe - metal[want_mtl]).is_empty() is False:
            errors.append(f"{name}: label at ({x:.3f}, {y:.3f}) is not over {want_mtl[0]}/{want_mtl[1]} metal")
        if supply:
            if y < bbox.top - TOP_EDGE_UM:
                errors.append(f"{name}: not on the top edge (y={y:.3f}, top={bbox.top:.3f})")
        else:
            if y > bbox.bottom + EDGE_UM:
                errors.append(f"{name}: not on the bottom edge (y={y:.3f}, bottom={bbox.bottom:.3f})")
            m = re.fullmatch(r"(D|WEN|Q)\[(\d+)\]", name)
            if m:
                xs.setdefault(m.group(1), {})[int(m.group(2))] = x
    for bus, byi in xs.items():
        order = [byi[i] for i in sorted(byi)]
        if any(b <= a for a, b in zip(order, order[1:])):
            errors.append(f"{bus}[i] does not increase with i along x")
    # each slice carries all three of its pins: slice i spans 17.84 um from the left half's edge
    if errors:
        print(f"FAIL: {len(errors)} pin problem(s) in {os.path.relpath(path, ROOT)}")
        for e in errors:
            print("  " + e)
        return 1
    print(f"PASS: {len(want) - 2} signal pins on Metal2 along the bottom edge + VDD/VSS Metal3 straps "
          f"on the top edge; no missing, extra or duplicate label")
    return 0


if __name__ == "__main__":
    sys.exit(main())
