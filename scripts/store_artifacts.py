#!/usr/bin/env python3
"""Store a run's evidence bytes in the artifact store; commit manifest + summary.

    python3 scripts/store_artifacts.py <bench> <run-id> <staged-dir>

Every regular file under <staged-dir> is stored with `klt artifact put` under
the logical name `<bench>/<run-id>/<relative path>`. The repo then gains
exactly two files:

    manifests/artifacts/<bench>-<run-id>.manifest.json
    manifests/artifacts/<bench>-<run-id>.summary.md   (name, size, sha256 per object)

<staged-dir> must be outside the repo or under the git-ignored
`.artifact-scratch/`, so the bytes can never be committed by accident. Run it
as a post-step of a sim/signoff runner once the run's outputs are staged.

Fail closed: if $KLT_ARTIFACT_BROKER is unset, `klt` lacks `artifact put`, or
the broker is unreachable or refuses, exit 10 with nothing written (no
manifest, no summary) and no fallback to committing bytes. Never write the
broker URL anywhere in the repo.

Exit codes: 0 stored; 1 usage / bad staged directory; 10 not stored.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ".artifact-scratch"
MANIFEST_DIR = "manifests/artifacts"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
EXIT_OK, EXIT_USAGE, EXIT_NOT_STORED = 0, 1, 10


class NotStored(Exception):
    pass


def preflight() -> str:
    if not os.environ.get("KLT_ARTIFACT_BROKER"):
        raise NotStored("$KLT_ARTIFACT_BROKER is not set")
    klt = shutil.which("klt")
    if not klt:
        raise NotStored("klt is not on PATH")
    try:
        p = subprocess.run([klt, "artifact", "put", "--help"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise NotStored(f"cannot run klt: {exc}") from exc
    if p.returncode != 0:
        raise NotStored("this klt has no `artifact put` (needs klayout-tools 7e3561f or later)")
    return klt


def staged_problem(staged: Path) -> str | None:
    if not staged.is_dir():
        return f"{staged} is not a directory"
    try:
        rel = staged.relative_to(REPO_ROOT)
    except ValueError:
        return None  # outside the repo
    if rel.parts and rel.parts[0] == SCRATCH:
        return None
    return f"{staged} is inside the repo but not under {SCRATCH}/; stage evidence in git-ignored scratch"


def stage_files(staged: Path) -> list[Path]:
    files = sorted(p for p in staged.rglob("*") if p.is_file() and not p.is_symlink())
    if not files:
        raise NotStored(f"no files under {staged}")
    return files


def summary_markdown(bench: str, run_id: str, manifest: dict) -> str:
    lines = [
        f"# Stored evidence: {bench} {run_id}",
        "",
        "Bytes are in the fleet artifact store, not in git. Fetch or check them from a "
        f"fleet worker with `klt artifact verify manifests/artifacts/{bench}-{run_id}.manifest.json`.",
        "",
        "| name | size (bytes) | sha256 |",
        "|---|---:|---|",
    ]
    for e in manifest["entries"]:
        lines.append(f"| `{e['name']}` | {e['size']} | `{e['sha256']}` |")
    return "\n".join(lines) + "\n"


def store(klt: str, bench: str, run_id: str, staged: Path, repo: Path) -> Path:
    manifest_path = repo / MANIFEST_DIR / f"{bench}-{run_id}.manifest.json"
    summary_path = manifest_path.with_name(f"{bench}-{run_id}.summary.md")
    if manifest_path.exists() or summary_path.exists():
        raise NotStored(f"{manifest_path.name} already exists; run ids are append-only")
    files = stage_files(staged)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_manifest = Path(tmp) / "m.manifest.json"
        for f in files:
            name = f"{bench}/{run_id}/{f.relative_to(staged).as_posix()}"
            try:
                p = subprocess.run(
                    [klt, "artifact", "put", "--manifest", str(tmp_manifest),
                     "--name", name, str(f)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            except OSError as exc:
                raise NotStored(f"cannot run klt: {exc}") from exc
            if p.returncode != 0:
                detail = (p.stderr or p.stdout).strip().splitlines()[-1:] or ["no output"]
                raise NotStored(f"klt artifact put failed for {name}: {detail[0]}")
        manifest = json.loads(tmp_manifest.read_text(encoding="utf-8"))
        summary = summary_markdown(bench, run_id, manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_manifest), manifest_path)
        summary_path.write_text(summary, encoding="utf-8")
    return manifest_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bench")
    ap.add_argument("run_id")
    ap.add_argument("staged", type=Path)
    args = ap.parse_args(argv)
    for label, value in (("bench", args.bench), ("run-id", args.run_id)):
        if not ID_RE.match(value):
            print(f"ERROR: bad {label} {value!r}", file=sys.stderr)
            return EXIT_USAGE
    staged = args.staged.resolve()
    problem = staged_problem(staged)
    if problem:
        print(f"ERROR: {problem}", file=sys.stderr)
        return EXIT_USAGE
    try:
        klt = preflight()
        manifest = store(klt, args.bench, args.run_id, staged, REPO_ROOT)
    except NotStored as exc:
        print(f"EVIDENCE NOT STORED -- nothing written (fail closed): {exc}", file=sys.stderr)
        return EXIT_NOT_STORED
    rel = manifest.relative_to(REPO_ROOT)
    print(f"stored; commit {rel} and {rel.with_name(rel.name.replace('.manifest.json', '.summary.md'))}")
    print(f"then: klt artifact verify {rel}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
