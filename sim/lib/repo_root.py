"""Locate the repository root by marker search instead of a fixed parent depth.

`Path(__file__).resolve().parents[N]` silently points at the wrong tree when a
script is relocated deeper or shallower. Walk upward to the first ancestor that
contains `.git` (a directory in a clone, a file in a git worktree) and fail
loudly when there is none.
"""
from __future__ import annotations

from pathlib import Path

MARKER = ".git"


def find_repo_root(start: Path) -> Path:
    """Return the nearest ancestor of `start` (inclusive) containing `.git`."""
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / MARKER).exists():
            return candidate
    raise RuntimeError(
        f"no repository root found: no ancestor of {start} contains {MARKER}; "
        "pass the root explicitly"
    )
