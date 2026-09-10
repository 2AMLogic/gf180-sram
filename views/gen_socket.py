#!/usr/bin/env python3
"""Generate ``sram_256x32_array.socket.json`` -- the `klt socket-check` /
`klt lef-abstract` socket descriptor for the 256 x 32 array, straight from
``layout/sram_256x32/generate.py``'s own drawn geometry.

## Why this reads the layout back instead of re-deriving coordinates

``layout/sram_256x32/generate.py`` already computes every port's exact
position once, when it draws that port's text label (``BL<col>``/
``BLB<col>`` on Metal1, ``WL<row>`` on its Metal1 landing pad, ``VDD``/
``VSS`` on Metal3 -- see that module's docstring and its ``build()``
function; the wordline landing pads are issue #121). Re-implementing
those 322 coordinate formulas here, by hand, a second time would be exactly
the "hand-typed 322 entries" issue #120 says not to do -- and worse, it
would silently drift from the generator the moment either changes without
the other being updated.

Instead, this script **builds the same ``kdb.Layout`` the generator itself
builds** (calling its ``build()`` function directly -- not re-parsing the
committed GDS, so this stays a generator-to-generator relationship with no
extra serialisation round-trip) and reads the text labels straight back off
it: one socket ``pins[]`` entry per drawn text shape, named and positioned
exactly as the generator placed it. The array's outline comes from the same
built layout's own bounding box, so a change to ``ROWS``/``COLS`` or to the
bitcell pitch regenerates a self-consistent socket automatically.

## Pin layer choice: the label layer, not the drawing layer

``klt socket-check``'s ``pins`` check looks for a **text label** on each
pin's declared ``(layer, datatype)`` at its declared position (see
``klayout_tools.socket_check`` module docstring: "every declared pin has a
text label, on its declared layer"). ``layout/bitcell/generate.py`` and
``layout/sram_256x32/generate.py`` draw every port label on a dedicated
``_LBL`` datatype -- ``Metal1_Label`` (34, 10), ``Metal3_Label`` (42, 10) --
separate from the drawn conductor's own datatype (``*_0``), matching
gf180mcu's own ``libs.tech/klayout/tech/gf180mcu.map`` convention (that
file's ``PIN`` purpose lines resolve those same ``_LBL`` datatypes to the
same LEF layer name as the drawing datatype). So each pin's socket ``layer``
here is deliberately the *label* datatype -- the only choice ``klt
socket-check`` can actually find a match against for this committed GDS. See
``views/README.md`` ("Pin geometry: why every pin comes back `synthesized`,
never `drawn`") for what this choice means downstream, in `klt lef-abstract`.

Since issue #121 the array draws a Poly2-to-Metal1 landing pad per wordline
and labels ``WL<row>`` on that pad, so **every** pin in this descriptor now
sits on a ``Metal1_Label``/``Metal3_Label`` layer that resolves to a `TYPE
ROUTING` LEF layer. ``Poly2_Label`` (30, 10) is deliberately no longer read:
nothing is labelled there any more, and Poly2 never resolved to a routing
layer, which is exactly why all 256 ``WL<row>`` pins used to come back
``geometry_source: "none"``.

## Direction / use classification

Per issue #120's Scope item 1: ``WL*`` -> ``INPUT``/``SIGNAL`` (a wordline
is driven into the array, never driven out of it, in this core-only macro);
``BL*``/``BLB*`` -> ``INOUT``/``SIGNAL`` (a bitline is both driven, on a
write, and sensed, on a read, by periphery this macro does not draw);
``VDD`` -> ``INOUT``/``POWER``; ``VSS`` -> ``INOUT``/``GROUND``.

## Determinism

Run from the repo root::

    uv run --with klayout python3 views/gen_socket.py

Writes ``views/sram_256x32_array.socket.json`` (or ``--out``'s target) with
a fixed, sorted key order and 2-space indent, so re-running leaves ``git
diff`` empty -- exactly the same determinism contract
``layout/sram_256x32/generate.py``'s GDS output already makes, extended to
this descriptor.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ARRAY_GENERATE_PATH = os.path.join(
    _HERE, "..", "layout", "sram_256x32", "generate.py"
)


def _load_array_generator():
    """Import ``layout/sram_256x32/generate.py`` under a name that will
    never collide with its own internal ``import generate as bitcell``.

    That module inserts ``layout/bitcell`` onto ``sys.path`` and does
    ``import generate as bitcell`` (see its own docstring) -- a plain ``import
    generate`` here would register *this* import under the module name
    ``"generate"`` in ``sys.modules`` first, so the array module's own later
    ``import generate as bitcell`` would find itself already cached and bind
    the array module (not the bitcell module) to ``bitcell``. Loading via
    ``importlib.util.spec_from_file_location`` under a distinct module name
    (``sram_array_generate``) leaves the bare ``"generate"`` name free for
    the array module's own import to resolve correctly, exactly as it does
    when ``layout/sram_256x32/generate.py`` is run directly as a script.
    """
    spec = importlib.util.spec_from_file_location(
        "sram_array_generate", _ARRAY_GENERATE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["sram_array_generate"] = module
    spec.loader.exec_module(module)
    return module


def _classify(name: str) -> tuple[str, str]:
    if name.startswith("WL"):
        return "INPUT", "SIGNAL"
    if name.startswith("BL"):  # matches both BL<n> and BLB<n>
        return "INOUT", "SIGNAL"
    if name == "VDD":
        return "INOUT", "POWER"
    if name == "VSS":
        return "INOUT", "GROUND"
    raise ValueError(f"unclassified port name: {name!r}")


def build_descriptor(array_gen, rows: int, cols: int) -> dict:
    bitcell = array_gen.bitcell

    layout = array_gen.build(rows=rows, cols=cols)
    top = layout.cell(array_gen.TOP_CELL)
    dbu = layout.dbu

    bbox = top.bbox()
    outline = {
        "x0": round(bbox.left * dbu, 6),
        "y0": round(bbox.bottom * dbu, 6),
        "x1": round(bbox.right * dbu, 6),
        "y1": round(bbox.top * dbu, 6),
    }

    label_layers = (
        bitcell.L_METAL1_LBL,  # BL<col> / BLB<col> / WL<row> (issue #121)
        array_gen.L_METAL3_LBL,  # VDD / VSS
    )

    pins = []
    for layer_pair in label_layers:
        layer_index = layout.find_layer(*layer_pair)
        if layer_index is None:
            continue
        for shape in top.shapes(layer_index).each():
            if not shape.is_text():
                continue
            text = shape.text
            name = text.string
            direction, use = _classify(name)
            pins.append(
                {
                    "name": name,
                    "layer": [layer_pair[0], layer_pair[1]],
                    "x": round(text.x * dbu, 6),
                    "y": round(text.y * dbu, 6),
                    "direction": direction,
                    "use": use,
                }
            )

    pins.sort(key=lambda p: p["name"])

    return {
        "schema": "klt.socket/1",
        "name": array_gen.TOP_CELL,
        "outline": outline,
        "pins": pins,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=None, help="default: the array generator's own ROWS (256)")
    parser.add_argument("--cols", type=int, default=None, help="default: the array generator's own COLS (32)")
    parser.add_argument(
        "-o",
        "--out",
        default=os.path.join(_HERE, "sram_256x32_array.socket.json"),
    )
    args = parser.parse_args()

    array_gen = _load_array_generator()
    rows = args.rows if args.rows is not None else array_gen.ROWS
    cols = args.cols if args.cols is not None else array_gen.COLS

    descriptor = build_descriptor(array_gen, rows, cols)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(descriptor, handle, indent=2, sort_keys=False)
        handle.write("\n")
    print(f"wrote {args.out}")
    print(f"{len(descriptor['pins'])} pins, outline {descriptor['outline']}")


if __name__ == "__main__":
    main()
