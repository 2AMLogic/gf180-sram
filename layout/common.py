"""Shared bootstrap and determinism helpers for the layout generators.

Every generator under ``layout/`` and ``views/gen_socket.py`` is invoked
directly by path (``layout/verify.sh``, ``views/verify.sh``,
``signoff/regenerate.sh``), so none of them can import a sibling the ordinary
way. Until now each carried its own hand copy of the same three helpers
(issue #330): a file-path module loader, the GDS writer options that keep
output byte-deterministic, and the um -> dbu conversion. They live here once
now.

``ROOT`` is resolved from this file's own location and asserted to be the
repository root (``.git`` present), matching ``sim/lib/repo_root.py``'s
fail-loudly convention rather than a fixed parent depth that silently points
at the wrong tree when a script is relocated.

Importing this module needs no ``klayout``: ``save_options`` lazy-imports it,
so ``ROOT`` / ``load_module`` / ``nm`` stay usable in klayout-less
environments.
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


def save_options():
    """Writer options that make the emitted GDS byte-stable (see each
    generator docstring's "Determinism" section): no GDSII header timestamp."""
    import klayout.db as kdb

    opts = kdb.SaveLayoutOptions()
    opts.gds2_write_timestamps = False
    return opts


def nm(v: float) -> int:
    """Micrometres -> integer database units (1 dbu = 1 nm)."""
    return int(round(v * 1000))
