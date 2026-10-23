#!/usr/bin/env python3
"""Validate stored-evidence manifests under manifests/artifacts/.

New sim/signoff evidence bytes go to the fleet artifact store through
`scripts/store_artifacts.py` (`klt artifact put`); git keeps only the
manifest and a Markdown summary. This is the git-side check of that
contract. For every `manifests/artifacts/*.manifest.json` in the working
tree it fails when:

  * the manifest is not `{schema_version: 1, entries: [..]}` with at least
    one entry, or an entry has missing/unknown fields, a bad sha256/size, or
    a non-canonical relative `name` or a duplicate `name`;
  * an entry's `uri` is not `artifact:<key>` (an `s3://` URI, a URL or any
    other scheme is refused) or the key does not end in the entry's sha256;
  * any manifest text names a storage bucket or cloud account
    (`s3://`, `arn:aws:`);
  * the bytes of a stored object (matched by sha256) are also tracked in
    git -- the point of a manifest is that the bytes are *not* committed.

It never contacts the broker: schema-valid is not hash-verified. Run
`klt artifact verify <manifest>` from a fleet worker for that. Stdlib only.

Exit codes: 0 ok; 1 a manifest is invalid; 2 git error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = "manifests/artifacts"
MANIFEST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.manifest\.json$")
# Files other than manifests allowed beside them: the README and the
# per-run Markdown summaries the writer emits.
OTHER_ALLOWED_RE = re.compile(r"^(README\.md|[A-Za-z0-9][A-Za-z0-9._-]*\.summary\.md)$")

REQUIRED = ("sha256", "size", "kind", "producer", "uri")
OPTIONAL = ("name", "media_type")
PRODUCER_FIELDS = ("tool", "version", "loom.repo", "commit")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
URI_RE = re.compile(r"^artifact:([^/\s]\S*)$")
STORAGE_RE = re.compile(r"s3://|arn:aws:")


def canonical_name(name) -> bool:
    return (isinstance(name, str) and name != "" and not name.startswith("/")
            and "\\" not in name and "\0" not in name
            and posixpath.normpath(name) == name
            and not {"", ".", ".."} & set(name.split("/")))


def entry_problems(entry) -> list[str]:
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    problems = []
    missing = [f for f in REQUIRED if f not in entry]
    extra = sorted(set(entry) - set(REQUIRED) - set(OPTIONAL))
    if missing:
        problems.append(f"missing {', '.join(missing)}")
    if extra:
        problems.append(f"unknown field(s) {', '.join(extra)}")
    sha = entry.get("sha256")
    if not isinstance(sha, str) or not SHA256_RE.match(sha):
        problems.append("sha256 must be 64 lowercase hex digits")
    size = entry.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        problems.append("size must be a positive integer")
    if entry.get("kind") != "evidence":
        problems.append("kind must be 'evidence'")
    producer = entry.get("producer")
    if not isinstance(producer, dict) or set(producer) != set(PRODUCER_FIELDS):
        problems.append(f"producer must carry exactly {', '.join(PRODUCER_FIELDS)}")
    uri = entry.get("uri")
    m = URI_RE.match(uri) if isinstance(uri, str) else None
    if m is None:
        problems.append("uri must be artifact:<key> (no other scheme)")
    elif m.group(1).rsplit("/", 1)[-1] != sha:
        problems.append("uri key does not end in the entry's sha256")
    if "name" in entry and not canonical_name(entry["name"]):
        problems.append("name must be a canonical relative path")
    if "media_type" in entry and not isinstance(entry["media_type"], str):
        problems.append("media_type must be a string")
    return problems


def manifest_problems(manifest) -> list[str]:
    if (not isinstance(manifest, dict)
            or set(manifest) != {"schema_version", "entries"}
            or manifest.get("schema_version") != 1
            or not isinstance(manifest.get("entries"), list)):
        return ["not {schema_version: 1, entries: [...]}"]
    if not manifest["entries"]:
        return ["has no entries"]
    problems = []
    seen = set()
    for i, entry in enumerate(manifest["entries"]):
        problems += [f"entry {i}: {p}" for p in entry_problems(entry)]
        name = entry.get("name") if isinstance(entry, dict) else None
        if isinstance(name, str):
            if name in seen:
                problems.append(f"entry {i}: duplicate name {name!r}")
            seen.add(name)
    return problems


def tracked_blobs(repo: Path) -> dict[int, list[str]]:
    """{size: [path, ..]} of tracked regular files outside manifests/."""
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"git ls-files failed: {exc}") from exc
    by_size: dict[int, list[str]] = {}
    for raw in out.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        if rel.startswith(MANIFEST_DIR + "/"):
            continue
        p = repo / rel
        if p.is_symlink() or not p.is_file():
            continue
        by_size.setdefault(p.stat().st_size, []).append(rel)
    return by_size


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(repo: Path) -> int:
    mdir = repo / MANIFEST_DIR
    errors: list[str] = []
    manifests = entries = 0
    valid: list[tuple[str, dict]] = []
    if mdir.is_dir():
        for p in sorted(mdir.iterdir()):
            rel = f"{MANIFEST_DIR}/{p.name}"
            if OTHER_ALLOWED_RE.match(p.name) and p.is_file():
                continue
            if not MANIFEST_RE.match(p.name) or not p.is_file() or p.is_symlink():
                errors.append(f"{rel}: only <bench>-<run-id>.manifest.json, "
                              "<bench>-<run-id>.summary.md and README.md belong here")
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if STORAGE_RE.search(text):
                errors.append(f"{rel}: names a storage bucket or cloud account "
                              "(s3:// or arn:aws:)")
            try:
                manifest = json.loads(text)
            except ValueError as exc:
                errors.append(f"{rel}: not valid JSON: {exc}")
                continue
            problems = manifest_problems(manifest)
            errors += [f"{rel}: {m}" for m in problems]
            if not problems:
                manifests += 1
                valid.append((rel, manifest))
    if valid:
        try:
            by_size = tracked_blobs(repo)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        cache: dict[str, str] = {}
        for rel, manifest in valid:
            for entry in manifest["entries"]:
                entries += 1
                for cand in by_size.get(entry["size"], []):
                    if cand not in cache:
                        cache[cand] = sha256_of(repo / cand)
                    if cache[cand] == entry["sha256"]:
                        errors.append(
                            f"{rel}: stored object {entry.get('name', entry['sha256'])} "
                            f"is also committed as {cand}; stored evidence bytes must "
                            "not be committed (no blob fallback)")
    if errors:
        print(f"FAIL: {len(errors)} stored-evidence manifest problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"OK: {manifests} manifest(s), {entries} entr{'y' if entries == 1 else 'ies'} "
          f"in {MANIFEST_DIR}/: schema valid, artifact: URIs only, no stored bytes "
          "committed. Bytes NOT hash-verified here (no broker contact); run "
          "`klt artifact verify <manifest>` from a fleet worker.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=REPO_ROOT, help="repo root (default: this repo)")
    args = ap.parse_args(argv)
    return check(args.repo.resolve())


if __name__ == "__main__":
    sys.exit(main())
