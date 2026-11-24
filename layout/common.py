"""Shared bootstrap and determinism helpers for the layout generators.

Every generator under ``layout/`` and ``views/gen_socket.py`` is invoked
directly by path (``layout/verify.sh``, ``views/verify.sh``,
``signoff/regenerate.sh``), so none of them can import a sibling the ordinary
way. Until now each carried its own hand copy of the same three helpers
(issue #330): a file-path module loader, the GDS writer options that keep
output byte-deterministic, and the um -> dbu conversion. They live here once
now. Issue #475 moved the fifth duplicated idiom here too: registering a GDS
layer and attaching its PDK display name (``register_layer``), together with
the array-level Via2/Metal3 layer constants the array, the column periphery,
and the macro had each defined on their own.

``ROOT`` is resolved from this file's own location and asserted to be the
repository root (``.git`` present), matching ``sim/lib/repo_root.py``'s
fail-loudly convention rather than a fixed parent depth that silently points
at the wrong tree when a script is relocated.

Importing this module needs no ``klayout``: ``save_options`` and
``register_layer`` lazy-import it, so ``ROOT`` / ``load_module`` / ``nm`` /
the layer constants stay usable in klayout-less environments.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
assert (_ROOT / ".git").exists(), (
    f"no .git at {_ROOT}: layout/common.py must sit one level below a repository root"
)
ROOT = str(_ROOT)


def load_module(name: str, rel: str):
    """Execute the repo-relative file ``rel`` as module ``name`` and return it.

    Registers ``sys.modules[name]`` before executing, exactly like the four
    ``_load()`` copies this replaces did. Callers rely on distinct names
    (``_sram_bitcell_generate``, ``sram_array_generate``, ...) so the same
    file can be held as several independent module objects side by side --
    never pass a name a plain ``import`` could also claim (``generate``).
    """
    path = os.path.join(ROOT, rel)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Array-level gf180mcu drawing layers (GDS layer/datatype), read from the
# PDK's own libs.tech/klayout/tech/gf180mcu.lyp exactly like the bitcell set
# in layout/bitcell/generate.py. The bitcell itself draws nothing above
# Metal2; the array, the column periphery, and the macro all do. Defined here
# once (issue #475) so a layer renumbered in one generator cannot silently
# diverge from the others. ``ARRAY_LAYER_NAMES`` holds their PDK display
# names; the below-Metal3 names stay in layout/bitcell/generate.py's
# ``_LAYER_NAMES``, and layout/periphery/column/generate.py merges the two
# tables for the layers its periphery draws on.
# ---------------------------------------------------------------------------
L_VIA2 = (38, 0)
L_METAL3 = (42, 0)
L_METAL3_LBL = (42, 10)

ARRAY_LAYER_NAMES = {
    L_VIA2: "Via2",
    L_METAL3: "Metal3",
    L_METAL3_LBL: "Metal3_Label",
}


def save_options():
    """Writer options that make the emitted GDS byte-stable (see each
    generator docstring's "Determinism" section): no GDSII header timestamp."""
    import klayout.db as kdb

    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


def register_layer(layout, lp: tuple[int, int], names: dict[tuple[int, int], str]) -> int:
    """Create (or find) GDS layer ``lp`` in ``layout`` and attach its name.

    The one copy of the idiom every generator used to hand-roll (issue #475):
    ``layout.layer(*lp)`` plus ``set_info`` with a ``LayerInfo`` carrying the
    PDK display name from ``names``. A layer missing from ``names`` is still
    created and returned, just left unnamed -- the most permissive of the
    behaviours this replaced, and unreachable at every current call site,
    where all drawn layers are named. Lazy-imports klayout like
    :func:`save_options`, so importing this module stays klayout-free.
    """
    import klayout.db as kdb

    li = layout.layer(*lp)
    name = names.get(lp)
    if name is not None:
        layout.set_info(li, kdb.LayerInfo(lp[0], lp[1], name))
    return li


def nm(v: float) -> int:
    """Micrometres -> integer database units (1 dbu = 1 nm)."""
    return int(round(v * 1000))
