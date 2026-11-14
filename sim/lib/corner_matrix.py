#!/usr/bin/env python3
"""Single owner for the ratified PVT corner matrix (`spec/sram.md` "Corner set").

Three fully-crossed axes -- process x temperature x voltage -- plus the
`tt -> typical` process-label-to-model-section mapping every generated
`corner.inc` and `klt sim` request needs. The corner count is their product
(3 x 3 x 3 = 27 today) and is **derived, never hardcoded**: no consumer may
write a literal count, so an axis change cannot leave a stale product behind
in generated text or in a committed artifact.

Why this module exists (#331). The same constant was held in four
independent places -- `deck_adapter.py`, `render_signoff_table.py`,
`run_mc_campaign.py`, `sim/macro-smoke/smoke.py` -- and only the first was
drift-guarded against `run_corner_sweep.sh`. The product had already drifted
once: `spec/sram.md`'s own prose said "9" for it until #53 corrected it to 27
(`spec/corner-count-correction.md`), which is why `run_corner_sweep.sh:93-95`
derives its `CORNER_COUNT` instead of hardcoding it. The copies had also
diverged in type (`TEMPS` as ints in one, strings in another), so two
signoff-facing artifacts agreed only because `str(-40) == "-40"`.
`sim/lib/repo_root.py` sets the precedent for a shared `sim/lib` helper
imported via the `sys.path.insert` sibling-import pattern.

**Axis element type**: every axis point is the spec's own literal label, as
text. `spec/sram.md` "Corner set" writes the voltage axis as `2.97 V`,
`3.30 V`, `3.63 V`, and the trailing zero in `3.30` is significant -- it
appears verbatim in every corner id (`tt_25c_3.30v`) and in every generated
`.param VDDC=3.30` card, and no numeric type round-trips it. The temperature
axis (`-40 C`, `25 C`, `125 C`) is therefore text too, for one uniform rule
rather than a per-axis exception; it also matches the shell word tokens in
`run_corner_sweep.sh`'s own `PROCESSES`/`TEMPS`/`VDDS` arrays, which are what
the drift tests compare against. A consumer needing a number converts
explicitly at its own boundary (`sim/macro-smoke/smoke.py` does, for the
`klt sim` request's JSON `temperature_c` / `supply_v` fields).

`sim/lib/run_corner_sweep.sh` keeps its own shell copy -- it cannot import a
Python module -- and is deliberately the reference the drift tests in
`sim/lib/test_corner_matrix.py` compare this module against.
"""
from __future__ import annotations

import itertools

# Ratified corner matrix, spec/sram.md "Corner set". Same order
# sim/lib/run_corner_sweep.sh iterates, so every record's corner ordering and
# every generated unit order already match this.
PROCESSES = ("ff", "tt", "ss")
TEMPS = ("-40", "25", "125")
VDDS = ("2.97", "3.30", "3.63")

# Process-corner label -> the gf180mcu model file's own bare `.LIB` section
# name (sm141064.ngspice defines `.LIB typical` / `.LIB ff` / `.LIB ss` for
# the nfet_03v3/pfet_03v3 devices this bitcell uses; "tt" is this repo's and
# the spec's label for gf180mcu's "typical" section).
LIB_SECTION = {"ff": "ff", "tt": "typical", "ss": "ss"}


def corners() -> list[tuple[str, str, str]]:
    """(process, temp_c, vdd) for every corner, in the launcher's loop order."""
    return list(itertools.product(PROCESSES, TEMPS, VDDS))


def corner_id(process: str, temp: str, vdd: str) -> str:
    """The repo-wide corner identifier, e.g. `tt_25c_3.30v`."""
    return f"{process}_{temp}c_{vdd}v"


def corner_ids() -> list[str]:
    """Every corner id, in the launcher's loop order."""
    return [corner_id(*c) for c in corners()]
