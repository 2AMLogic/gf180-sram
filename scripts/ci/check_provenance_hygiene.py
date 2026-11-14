#!/usr/bin/env python3
"""Fail the build on a NEW host-path leak in a committed evidence report.

Issue #340, implementing issue #109's ratified provenance-hygiene rule as a
check instead of a convention. Two halves, deliberately asymmetric:

  * **Mint time** -- `layout/reports/generate.sh` routes every report through
    `layout/reports/commit_report.py`, which strips the generating checkout's
    root and the run's scratch dir out of the whole document and then refuses
    (via `klt env-provenance lint-envelope`) to write a report that still
    holds ANY absolute path. Nothing is grandfathered there: the report does
    not exist yet.
  * **PR time** -- this check, which runs klayout-tools' own
    `klt env-provenance scan` over the *already committed* reports. `scan`
    asks the narrower question ("does this record name a person": a
    home-directory-shaped path) because the broader one has pre-existing
    answers this repo is not allowed to rewrite.

Which is why this check has a baseline at all. Issue #109's regression
condition is that no pre-existing file under `layout/reports/` is modified
retroactively, and three committed reports were already leaking when the
check landed. Running `scan` over the bare glob would therefore be red on
arrival. So the three are **named** in
`scripts/ci/provenance-leak-baseline.txt` and printed on every run -- the
grandfathering is visible in the output rather than hidden in a narrowed
glob, so a reader of a green build can still see that three known leaks
exist. A finding that is not in the baseline fails the build; a baseline
entry that no longer matches a finding also fails it, so the list cannot rot
into a blanket exemption.

Needs `klt` (klayout-tools >= 0.8.0) on PATH. Run via
`scripts/ci/check-provenance-hygiene.sh`; `--self-test` exercises the
classifier itself on synthetic fixtures.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).resolve().parent / "provenance-leak-baseline.txt"
# Tracked JSON evidence reports. sim/ is deliberately absent: its records are
# append-only and carry their own documented exceptions (xschem header
# comments, the `klt sim` environment block) -- see issue #340's scope.
GLOBS = ("layout/reports/*.json", "views/reports/*.json")


class Finding(NamedTuple):
    path: str
    line: int
    kind: str

    def key(self) -> str:
        return f"{self.path}:{self.line}:{self.kind}"


def read_baseline(path: Path) -> dict[str, str]:
    """Map `path:line:kind` -> the reason comment, from the baseline file."""
    entries: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entry, _, reason = stripped.partition("#")
        entry = entry.strip()
        if entry.count(":") != 2:
            sys.exit(
                f"FATAL: {path}:{lineno}: expected `<path>:<line>:<kind>`, "
                f"got {entry!r}"
            )
        entries[entry] = reason.strip()
    return entries


def tracked_reports(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", *GLOBS],
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(line for line in proc.stdout.splitlines() if line)


def scan(root: Path, files: list[str]) -> list[Finding]:
    """Run `klt env-provenance scan`; return its findings."""
    cmd = ["klt", "env-provenance", "scan", "--format", "json", *files]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=root)
    if proc.returncode not in (0, 3):
        sys.exit(
            f"FATAL: `klt env-provenance scan` exited {proc.returncode} "
            "(expected 0 = clean or 3 = findings), so this check did not run "
            "and must not be read as a pass.\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    report = json.loads(proc.stdout)
    return [
        Finding(entry["file"], leak["line"], leak["kind"])
        for entry in report.get("files", [])
        for leak in entry.get("leaks", [])
    ]


def _display(path: Path, root: Path) -> str:
    """Repo-relative when it can be (the real run), absolute otherwise."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def check(root: Path, baseline_path: Path) -> int:
    baseline = read_baseline(baseline_path)
    files = tracked_reports(root)
    if not files:
        print(
            "FATAL: no tracked reports matched "
            f"{' '.join(GLOBS)} -- this check cannot run and is not a pass.",
            file=sys.stderr,
        )
        return 1
    findings = scan(root, files)
    by_key = {f.key(): f for f in findings}

    new = [f for f in findings if f.key() not in baseline]
    stale = sorted(set(baseline) - set(by_key))
    grandfathered = sorted(set(baseline) & set(by_key))

    print(
        f"klt env-provenance scan: {len(files)} tracked report(s) under "
        f"{', '.join(GLOBS)}"
    )
    # Always print the grandfathered set, pass or fail: a green run must still
    # show that these known leaks exist (issue #340).
    if grandfathered:
        print(
            f"grandfathered: {len(grandfathered)} pre-existing leak(s), "
            "never rewritten retroactively per issue #109 "
            f"({_display(baseline_path, root)}):"
        )
        for key in grandfathered:
            print(f"  - {key}  # {baseline[key]}")
    else:
        print("grandfathered: none")

    status = 0
    if new:
        # Name the field's location, not the leaked text: `klt env-provenance
        # scan --help` warns that its findings quote the leaking path, and a
        # CI log outlives the host it names.
        print(
            f"\nFAIL: {len(new)} NEW host-path leak(s) in committed evidence:",
            file=sys.stderr,
        )
        for finding in sorted(new):
            print(f"  - {finding.key()}", file=sys.stderr)
        print(
            "\n  These reports name a home directory on the generating host.\n"
            "  See the leaking text locally (not in CI logs) with:\n"
            f"      klt env-provenance scan {' '.join(sorted({f.path for f in new}))}\n"
            "  Reports under layout/reports/ are minted by\n"
            "  layout/reports/generate.sh, which routes every one through\n"
            "  layout/reports/commit_report.py and will not write a file that\n"
            "  still carries an absolute path. A new leak therefore means a\n"
            "  report was written some other way -- fix the generator, do not\n"
            "  add a line to the baseline.",
            file=sys.stderr,
        )
        status = 1
    if stale:
        print(
            f"\nFAIL: {len(stale)} baseline entry/entries no longer match a "
            "real finding:",
            file=sys.stderr,
        )
        for key in stale:
            print(f"  - {key}", file=sys.stderr)
        print(
            f"\n  Delete these lines from {_display(baseline_path, root)}.\n"
            "  A stale allow-list entry silently widens into an exemption for\n"
            "  whatever leak later lands at that path and line.",
            file=sys.stderr,
        )
        status = 1
    if status == 0:
        print(f"ok: no new host-path leak in {len(files)} committed report(s)")
    return status


# --- self-test ------------------------------------------------------------
# The guard has to be able to fail, or a green status check means nothing.
# These fixtures drive the real `klt env-provenance scan` over a throwaway git
# repo, so what is exercised is the whole path: glob -> scan -> classify.

SELF_TEST_GLOB_DIR = "layout/reports"


def _fixture_repo(tmp: Path, leaking: bool) -> Path:
    root = tmp / ("leaky" if leaking else "clean")
    (root / SELF_TEST_GLOB_DIR).mkdir(parents=True)
    (root / SELF_TEST_GLOB_DIR / "drc-clean.json").write_text(
        json.dumps({"file": "layout/bitcell/sram_bitcell_6t.gds"}, indent=2) + "\n"
    )
    if leaking:
        (root / SELF_TEST_GLOB_DIR / "extract-leaky.json").write_text(
            json.dumps(
                {"file": "/home/someone/checkout/layout/sram_256x32/a.gds"}, indent=2
            )
            + "\n"
        )
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    return root


def self_test() -> int:
    failures: list[str] = []

    def expect(label: str, got: int, want: int) -> None:
        verdict = "ok" if got == want else "FAIL"
        print(f"  [{verdict}] {label}: exit {got} (want {want})")
        if got != want:
            failures.append(label)

    print("self-test: the guard must be able to fail")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        clean = _fixture_repo(tmp, leaking=False)
        empty_baseline = tmp / "empty.txt"
        empty_baseline.write_text("# no grandfathered leaks\n")
        expect("clean repo, empty baseline -> pass", check(clean, empty_baseline), 0)

        leaky = _fixture_repo(tmp, leaking=True)
        expect(
            "new leak, empty baseline -> fail", check(leaky, empty_baseline), 1
        )

        covering = tmp / "covering.txt"
        covering.write_text(
            f"{SELF_TEST_GLOB_DIR}/extract-leaky.json:2:home-path  # grandfathered\n"
        )
        expect(
            "same leak, named in baseline -> pass", check(leaky, covering), 0
        )

        stale = tmp / "stale.txt"
        stale.write_text(
            f"{SELF_TEST_GLOB_DIR}/drc-clean.json:3:home-path  # not a real finding\n"
        )
        expect("stale baseline entry -> fail", check(clean, stale), 1)

    if failures:
        print(f"\nself-test FAILED: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("self-test: all 4 cases behaved as specified")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the classifier against synthetic clean/leaking fixtures",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    return check(REPO_ROOT, BASELINE)


if __name__ == "__main__":
    sys.exit(main())
