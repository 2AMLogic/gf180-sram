#!/usr/bin/env python3
"""sim/lib/env_provenance.py -- hand-rolled equivalent of `klt env-provenance`
(2AMLogic/klayout-tools `docs/cli/env-provenance.md`), for use by this repo's
own evidence-minting scripts on a host where the installed `klt` does not yet
ship that subcommand.

Issue #109: MC/yield (and other) evidence-minting scripts were embedding raw
absolute host filesystem paths -- including full agent-worktree paths -- into
committed evidence records. `klt env-provenance`'s documented model
(https://github.com/2AMLogic/klayout-tools, `docs/cli/env-provenance.md`) is
the fix this repo wants: repo-relative paths for anything inside the repo,
and *no path at all* (identity only -- name/version, never location) for
anything genuinely external, like a PDK install. This module reimplements
just that path-classification piece by hand, matching the doc's `{path,
scope}` shape, so a record written today reads the same way a record written
once `klt env-provenance` is available on this host would.

Verified 2026-08-25 against this implementation host's installed `klt`
(pipx, `klayout-tools 0.2.0`): `klt env-provenance --help` fails (`invalid
choice: 'env-provenance'`) and `klayout_tools.env_provenance` is not
importable from that install's own venv either -- the CLI subcommand and the
underlying module both post-date 0.2.0. Re-check `klt --version` /
`klt env-provenance --help` before assuming this module is still needed; if
`klt env-provenance` (or the `klayout_tools.env_provenance` module) becomes
available on a future host, prefer it directly and retire this file.

Only the piece these scripts actually need is reproduced here (external-vs-
repo path classification); host-id pseudonymization and OS/tool-version
collection are not implemented since nothing in this repo currently emits
those fields.
"""
from __future__ import annotations

from pathlib import Path


def repo_relative_path(path: str | Path | None, repo_root: str | Path) -> dict:
    """Classify `path` the way `klt env-provenance emit`'s `paths` field
    does: `{"path": <repo-relative POSIX path>, "scope": "repo"}` for
    anything under `repo_root`, or `{"path": None, "scope": "external"}` for
    anything outside it -- the absolute path is never returned. `path=None`
    (nothing resolved) returns `{"path": None, "scope": "absent"}`, a third,
    distinct case the doc's model also carries.
    """
    if path is None:
        return {"path": None, "scope": "absent"}
    resolved = Path(path).resolve()
    root = Path(repo_root).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return {"path": None, "scope": "external"}
    return {"path": rel.as_posix() if str(rel) != "." else ".", "scope": "repo"}


def pdk_identity(variant_dir: str | Path, version: str | None, source: str) -> dict:
    """The PDK-specific analogue of `repo_relative_path`: a gf180mcu PDK
    install is *always* external to this repo (it is a separate PDK install,
    e.g. under `~/.volare`), so per the doc's "external input pinned by
    identity, not location" rule this never carries a path at all -- only
    the variant name and resolved `open_pdks` version, the same
    `{name, version}` shape `klt extract`/`klt pex`'s own `provenance.pdk`
    block already uses (verified empirically against this repo's committed
    `sim/pex/write-margin/dut/extract-report.json`).
    """
    return {
        "variant": Path(variant_dir).name,
        "version": version or "unknown",
        "source": source,
    }
