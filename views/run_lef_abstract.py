#!/usr/bin/env python3
"""Run ``klt lef-abstract`` against the 256 x 32 array -- with one runtime
patch for a real crash the unmodified installed tool hits on this design's
geometry, filed upstream (see "The workaround" below). Otherwise this is
exactly ``klt lef-abstract``: same library function
(``klayout_tools.lef_abstract.run_lef_abstract``), same arguments, same
``.lef`` writer, same JSON response shape -- this script is a thin CLI
wrapper around it, not a reimplementation.

## Equivalent (currently crashing) command

    klt lef-abstract layout/sram_256x32/sram_256x32_array.gds \\
        --socket views/sram_256x32_array.socket.json \\
        --macro-name sram_256x32_array \\
        --cell-library gf180mcu_fd_sc_mcu9t5v0 \\
        --class BLOCK --pdk gf180mcuD --format json \\
        -o views/sram_256x32_array.lef

Once the upstream fix below is released and installed, drop this script and
run that command directly -- ``views/verify.sh`` documents the switch-back.

## The workaround

``klayout_tools.lef_abstract._polygon_to_um_shape`` converts each merged,
non-rectangular OBS region into a LEF ``POLYGON`` point list via::

    simple = polygon.to_simple_polygon()   # kdb.Polygon -> kdb.SimplePolygon
    ...for pt in simple.each_point_hull()...

``kdb.Polygon.to_simple_polygon()`` returns a ``kdb.SimplePolygon``, whose
own point-iteration method is ``each_point()`` -- ``each_point_hull()``
exists only on ``kdb.Polygon`` (the hole-bearing class), not on
``SimplePolygon``. Confirmed directly against the installed `klayout` 0.30.12
package this ``klt`` build uses::

    >>> import klayout.db as kdb
    >>> kdb.SimplePolygon(kdb.Box(0,0,10,10)).each_point_hull()
    AttributeError: 'SimplePolygon' object has no attribute 'each_point_hull'

This raises for *any* design whose OBS region (routing-layer drawn shapes,
minus declared pin ports) is not a plain rectangle after merging --
guaranteed here: the array's Metal1 carries 8,192 instanced copies of the
bitcell's L-shaped cross-couple straps and tie-bar risers
(``layout/bitcell/generate.py``), so ``klt lef-abstract`` cannot complete
against this design at all in its unmodified, installed form. Filed at
2AMLogic/klayout-tools per ``CLAUDE.md``'s friction protocol -- see
``views/README.md`` for the issue link.

The patch below is the minimal, exact fix: the same point list, read via the
method that actually exists. It changes no geometry, no pin classification,
no OBS union/subtraction logic, and no output formatting -- only which
`SimplePolygon` method builds the point list already computed by the
unmodified `_resolve_obs`. This mirrors the repo's existing precedent for a
`klt` gap on this exact array (`layout/README.md` "Known tool gaps" #4:
bypassing `klt drc --engine klayout`'s gf180mcu-native-deck gap by invoking
`klayout -b -r` directly, while filing the gap upstream) -- work around a
confirmed tool bug to get real, honest evidence, rather than let a filed bug
block the whole deliverable.

## What this script does NOT patch

Nothing about pin resolution, direction/use classification, drawn-vs-
synthesized geometry_source, or unroutable_pins detection is touched --
those are the unmodified library's own logic, reported verbatim.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from klayout_tools.lef_abstract import _polygon_to_um_shape as _original_polygon_to_um_shape
from klayout_tools.lef_abstract import run_lef_abstract
import klayout_tools.lef_abstract as _lef_abstract_module


def _patched_polygon_to_um_shape(polygon, dbu_um):
    """``_original_polygon_to_um_shape``, with only its ``each_point_hull``
    call (which does not exist on the ``kdb.SimplePolygon``
    ``to_simple_polygon()`` returns) replaced by ``each_point`` (which
    does) -- see this module's docstring."""
    if polygon.is_box():
        return _original_polygon_to_um_shape(polygon, dbu_um)
    simple = polygon.to_simple_polygon()
    return {
        "kind": "polygon",
        "points_um": [
            [round(pt.x * dbu_um, 6), round(pt.y * dbu_um, 6)]
            for pt in simple.each_point()
        ],
    }


def _redact_home_path(path: str | None) -> str | None:
    """Replace the resolved home-directory prefix with ``~`` -- the same
    symbolic convention ``layout/README.md`` already uses for
    ``~/.volare/gf180mcuD`` -- so the committed report never carries a
    literal ``/Users/<name>``/``/home/<name>`` absolute path (the #109
    rule: ``views/README.md`` "Reproducibility and hygiene"). Every other
    field in the response (``pins[]``, ``unroutable_pins[]``,
    ``provenance``) already reports no raw host path -- see
    ``klayout_tools._provenance.build_provenance`` -- so this is the only
    field this script touches.
    """
    if not path:
        return path
    home = os.path.expanduser("~")
    if home and path.startswith(home):
        return "~" + path[len(home):]
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", help="path to the array GDS")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--macro-name", required=True)
    parser.add_argument("--cell-library", required=True)
    parser.add_argument("--class", dest="macro_class", default="BLOCK")
    parser.add_argument("--pdk", dest="pdk_variant", default=None)
    parser.add_argument("--pdk-root", dest="pdk_root", default=None)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--report", required=True, help="path to write the JSON response")
    args = parser.parse_args()

    _lef_abstract_module._polygon_to_um_shape = _patched_polygon_to_um_shape

    report = run_lef_abstract(
        args.file,
        args.socket,
        macro_name=args.macro_name,
        cell_library=args.cell_library,
        output_path=args.output,
        macro_class=args.macro_class,
        pdk_variant=args.pdk_variant,
        pdk_root=args.pdk_root,
    )

    report["tech_lef"] = _redact_home_path(report["tech_lef"])

    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    print(f"wrote {args.output}")
    print(f"wrote {args.report}")
    print(f"pin_count: {report['pin_count']}, unroutable: {len(report['unroutable_pins'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
