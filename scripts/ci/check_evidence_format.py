#!/usr/bin/env python3
"""Validate repo-hygiene and evidence-record format invariants for gf180-sram.

This is intentionally thin scaffolding (see issue #28): this repo has not yet
landed design sources, testbenches, or a ratified evidence-record grammar
(#21, #24), so there is nothing to validate at the *content* level yet. What
this script enforces instead is the structural convention that already
exists today:

  1. Every top-level "deliverable" directory (design/, sim/, layout/,
     views/, measurements/) carries a README.md, so the repo layout
     documented in the root README stays accurate.
  2. Raw/scratch simulation artifacts (*.raw, *.log, *.vcd, *.vvp) are never
     committed under sim/, layout/, or measurements/ -- except the one
     documented append-only exception already carved out by .gitignore:
     per-corner ngspice logs under `sim/<experiment>/corners/**/*.log`.
     This turns a documented .gitignore comment into an enforced CI check
     instead of an honor-system convention.
  3. Relative markdown links between tracked docs resolve to a file that
     actually exists, so cross-references (spec/ <-> design/ <-> sim/ <->
     README.md) don't silently rot as the repo grows.
  4. `sim/signoff-summary.md` -- the derived per-corner PASS/FAIL rollup
     over the append-only records under `sim/*/records/` -- is byte-identical
     to what `sim/lib/render_signoff_table.py` renders from those records
     today. The rollup is a *derivation*, so a new corner-sweep record that
     supersedes an old one silently invalidates it; this check turns that
     into a CI failure with the regeneration command attached, rather than a
     stale signoff table nobody notices. Pure Python -- it reads committed
     records, it does not run ngspice or need a PDK.

As the harness and evidence-record grammar land (#21, #24), this script is
the place to grow real per-record field validation -- it does not invent
that grammar itself.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Top-level directories that must always carry a README.md describing scope.
DELIVERABLE_DIRS = ["design", "sim", "layout", "views", "measurements"]

# Directories that hold evidence records (per CLAUDE.md: "sim/ results are
# append-only evidence") and are therefore subject to the raw-artifact check.
EVIDENCE_DIRS = ["sim", "layout", "measurements"]

# Extensions that are raw/scratch simulator output and must never be
# committed, mirroring the *.raw / *.log / *.vcd / *.vvp rules in .gitignore.
RAW_ARTIFACT_EXTENSIONS = {".raw", ".log", ".vcd", ".vvp"}

# The documented exceptions (see .gitignore): per-corner ngspice logs and
# per-sample Monte Carlo logs are committed append-only evidence.
RAW_ARTIFACT_ALLOW_GLOBS = [
    "sim/*/corners/**/*.log",
    "sim/*/mc/raw-logs/**/*.log",
]

# Markdown/doc files to link-check. Kept to design-relevant docs (not the
# Loom-managed .loom/ or .claude/ trees, which are out of this issue's scope).
LINK_CHECK_GLOBS = [
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "WORK_PLAN.md",
    "WORK_LOG.md",
    "spec/**/*.md",
    "design/**/*.md",
    "sim/**/*.md",
    "layout/**/*.md",
    "views/**/*.md",
    "measurements/**/*.md",
]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# The derived per-corner PASS/FAIL rollup and the script that renders it from
# the append-only records under sim/*/records/ (see check 4 above).
SIGNOFF_SUMMARY = "sim/signoff-summary.md"
SIGNOFF_RENDERER = "sim/lib/render_signoff_table.py"


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def check_readmes(tracked: set[str], errors: list[str]) -> None:
    for d in DELIVERABLE_DIRS:
        readme = f"{d}/README.md"
        if readme not in tracked or not (REPO_ROOT / readme).is_file():
            errors.append(
                f"missing {readme}: every deliverable directory listed in "
                "the root README's \"Repo layout\" table must carry a "
                "README.md describing its scope"
            )


def check_raw_artifacts(tracked: set[str], errors: list[str]) -> None:
    for path in sorted(tracked):
        parts = path.split("/")
        if not parts or parts[0] not in EVIDENCE_DIRS:
            continue
        ext = Path(path).suffix
        if ext not in RAW_ARTIFACT_EXTENSIONS:
            continue
        if any(fnmatch.fnmatch(path, pattern) for pattern in RAW_ARTIFACT_ALLOW_GLOBS):
            continue
        errors.append(
            f"disallowed raw artifact committed: {path} (extension {ext!r}) "
            "-- raw/scratch simulator output is not evidence; only "
            "sim/<experiment>/corners/**/*.log and "
            "sim/<experiment>/mc/raw-logs/**/*.log are documented "
            "append-only exceptions (see .gitignore)"
        )


def resolve_glob(pattern: str, tracked: set[str]) -> list[str]:
    matches = []
    for path in tracked:
        if fnmatch.fnmatch(path, pattern):
            matches.append(path)
    return matches


def check_markdown_links(tracked: set[str], errors: list[str]) -> None:
    doc_paths: set[str] = set()
    for pattern in LINK_CHECK_GLOBS:
        doc_paths.update(resolve_glob(pattern, tracked))

    for doc in sorted(doc_paths):
        full = REPO_ROOT / doc
        try:
            text = full.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"could not read {doc}: {exc}")
            continue

        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target:
                continue
            # Skip external links, mail links, and pure same-file anchors.
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Strip an in-file anchor off a relative link, e.g. foo.md#bar.
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (full.parent / target_path).resolve()
            if not resolved.exists():
                errors.append(
                    f"broken relative link in {doc}: target {target!r} "
                    f"does not resolve to an existing file ({resolved})"
                )


def check_signoff_summary_fresh(tracked: set[str], errors: list[str]) -> None:
    """Assert sim/signoff-summary.md still matches its generator's output."""
    if SIGNOFF_SUMMARY not in tracked or SIGNOFF_RENDERER not in tracked:
        # Neither file exists yet in this checkout -- nothing to derive from.
        return

    try:
        rendered = subprocess.run(
            [sys.executable, str(REPO_ROOT / SIGNOFF_RENDERER), str(REPO_ROOT)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        errors.append(
            f"{SIGNOFF_RENDERER} failed (exit {exc.returncode}); it must be "
            f"able to re-derive {SIGNOFF_SUMMARY} from the committed records "
            f"under sim/*/records/. stderr:\n{exc.stderr.strip()}"
        )
        return

    committed = (REPO_ROOT / SIGNOFF_SUMMARY).read_text(encoding="utf-8")
    if committed != rendered:
        errors.append(
            f"{SIGNOFF_SUMMARY} is stale: it does not match what "
            f"{SIGNOFF_RENDERER} renders from the records currently under "
            f"sim/*/records/ (a newer record probably superseded one of its "
            f"sources). Regenerate and commit it:\n"
            f"      python3 {SIGNOFF_RENDERER} > {SIGNOFF_SUMMARY}"
        )


def main() -> int:
    tracked = set(tracked_files())
    errors: list[str] = []

    check_readmes(tracked, errors)
    check_raw_artifacts(tracked, errors)
    check_markdown_links(tracked, errors)
    check_signoff_summary_fresh(tracked, errors)

    if errors:
        print("evidence-format check FAILED:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(f"\n{len(errors)} error(s)", file=sys.stderr)
        return 1

    print(
        f"evidence-format check passed: {len(tracked)} tracked files, "
        f"{len(DELIVERABLE_DIRS)} deliverable READMEs present, no disallowed "
        "raw artifacts, no broken relative doc links, "
        f"{SIGNOFF_SUMMARY} in sync with {SIGNOFF_RENDERER}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
