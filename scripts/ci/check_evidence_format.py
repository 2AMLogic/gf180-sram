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
  5. `measurements/characterization-report.md` -- the aggregated per-spec-row
     characterization report (issue #27) combining the deterministic
     27-corner evidence with the Monte Carlo / yield evidence (issue #26) --
     is byte-identical to what `measurements/generate_report.py` renders
     today, the same freshness enforcement as check 4 above, applied to the
     report that depends on both the corner records and the MC/yield records.
   6. `sim/signoff-sim-envelope.json` -- the minted `klt sim`-shaped evidence
      envelope for T1 item 5 (issue #128), transcribed by
      `sim/lib/mint_sim_envelope.py` from the same five corner records
      check 4 rolls up and pinned by the signoff manifest's item-5
      content hash -- is byte-identical to what that minter renders today,
      the same freshness enforcement as checks 4/5 above. A new
      corner-sweep record that supersedes one of the envelope's five
      sources changes the envelope's `provenance.input.content_hash` with
      it, so this check turns a stale item-5 citation into a CI failure
      naming the regeneration command rather than silently pinning
      transcribed values that no longer match the committed records.

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
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]

# Top-level directories that must always carry a README.md describing scope.
DELIVERABLE_DIRS = ["design", "sim", "layout", "views", "measurements", "signoff"]

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
    # The signoff README only (not the vendored upstream tiers doc inside
    # signoff/, whose external cross-references are klayout-tools' to keep
    # current, not this repo's CI to police).
    "signoff/README.md",
]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


class DerivedFile(NamedTuple):
    """A committed file that a script re-derives from the append-only records."""

    committed: str
    generator: str
    verb: str  # how the generator's output is described: "renders" / "mints"
    sources: str  # records the generator reads, as worded in error text
    stale_extra: str = ""  # appended inside the "(a newer record ...)" note
    regen_extra: str = ""  # appended after "Regenerate and commit it"


# Derived files, each re-generated from the append-only records under
# sim/*/records/ (see checks 4-6 above).
SIGNOFF_SUMMARY = DerivedFile(
    "sim/signoff-summary.md",  # per-corner PASS/FAIL rollup
    "sim/lib/render_signoff_table.py",
    "renders",
    "sim/*/records/",
)
CHARACTERIZATION_REPORT = DerivedFile(
    "measurements/characterization-report.md",  # aggregated characterization report
    "measurements/generate_report.py",
    "renders",
    "sim/*/records/ and sim/*/mc/records/",
)
# The minted klt-sim-shaped evidence envelope for T1 item 5, minted from the
# same five corner records the signoff summary rolls up (issue #128).
SIM_ENVELOPE = DerivedFile(
    "sim/signoff-sim-envelope.json",
    "sim/lib/mint_sim_envelope.py",
    "mints",
    "sim/*/records/",
    stale_extra=(
        ", which changes its provenance.input.content_hash and with it the "
        "signoff manifest's item-5 pin"
    ),
    regen_extra=", then re-run ./signoff/regenerate.sh",
)
DERIVED_FILES = [SIGNOFF_SUMMARY, CHARACTERIZATION_REPORT, SIM_ENVELOPE]


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


def check_derived_fresh(
    tracked: set[str], errors: list[str], spec: DerivedFile
) -> None:
    """Assert a committed derived file still matches its generator's output."""
    if spec.committed not in tracked or spec.generator not in tracked:
        # Neither file exists yet in this checkout -- nothing to derive from.
        return

    try:
        rendered = subprocess.run(
            [sys.executable, str(REPO_ROOT / spec.generator), str(REPO_ROOT)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        errors.append(
            f"{spec.generator} failed (exit {exc.returncode}); it must be "
            f"able to re-derive {spec.committed} from the committed records "
            f"under {spec.sources}. stderr:\n{exc.stderr.strip()}"
        )
        return

    committed = (REPO_ROOT / spec.committed).read_text(encoding="utf-8")
    if committed != rendered:
        errors.append(
            f"{spec.committed} is stale: it does not match what "
            f"{spec.generator} {spec.verb} from the records currently under "
            f"{spec.sources} (a newer record probably superseded one of its "
            f"sources{spec.stale_extra}). Regenerate and commit "
            f"it{spec.regen_extra}:\n"
            f"      python3 {spec.generator} > {spec.committed}"
        )


def main() -> int:
    tracked = set(tracked_files())
    errors: list[str] = []

    check_readmes(tracked, errors)
    check_raw_artifacts(tracked, errors)
    check_markdown_links(tracked, errors)
    for spec in DERIVED_FILES:
        check_derived_fresh(tracked, errors, spec)

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
        + ", ".join(f"{d.committed} in sync with {d.generator}" for d in DERIVED_FILES)
        + "."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
