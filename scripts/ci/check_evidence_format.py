#!/usr/bin/env python3
"""Validate repo-hygiene and evidence-record format invariants for gf180-sram.

Added for issue #28 (T1 checklist item 10) and run by the `evidence-record
format` CI job. It is pure Python over committed files -- it never runs
ngspice and needs no PDK -- and it covers two kinds of invariant: the
structural conventions that keep the repo's evidence findable and clean
(checks 1-3), and the freshness of every artifact derived from the
append-only records (checks 4-6). It does not pass judgement on the
measurements themselves: the spec tier verdict over that evidence is graded
by `klt signoff`, via scripts/ci/check-signoff-freshness.sh.

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
   7. A receipt's "Files in `<dir>/`" table names bytes that are actually
      committed: every backticked path in the table's first (File) column
      must resolve to at least one tracked file under `<dir>/`, with
      `<...>` placeholders glob-expanded (`<family>/<corner-id>/stdout.log`
      demands a stdout.log under some family/corner directory, not a
      literal file of that name). A row whose What cell carries the
      literal `(none committed)` token is exempt -- the documented way to
      say a row describes artifacts deliberately not committed. Like
      check 3, this closes the gap where a receipt cites evidence as
      inline code in a table rather than as a markdown link, so a receipt
      asserting evidence it does not commit fails CI naming the row
      instead of reporting green (issue #356). The gate also reports its
      own coverage -- tables gated, rows resolved -- in the success line,
      so a receipt whose heading deviates (table invisible to the gate)
      shows up as a dropped count plus a warning rather than as silence,
      and a receipt-shaped table under an unmatched heading in a
      deck-parity receipt is warned about without failing CI (issue
      #372). Prose committed-bytes sections are deliberately out of
      scope: prose claims are not machine-checkable.
   8. `sim/testbenches.signoff.json` -- the T1 item 9 "Testbenches shipped"
      attestation -- pins an explicitly enumerated path set, and that
      enumeration must track what `sim/` actually ships: every tracked
      `sim/<experiment>/testbench/tb_*` bench must appear in the wrapper's
      `provenance.input.paths`. Nothing else couples the enumeration to
      the tree, so every new bench silently lands outside the verdict of
      record while item 9 keeps grading `met` -- the drift recurred three
      times (#310, #350, #328), twice while issue #357 was open, which is
      why this is a CI failure rather than a data fix. Pure Python over
      committed files -- no ngspice, no PDK, no `klt`.

Checks 4-6 share one shape: re-render a committed derived artifact from the
records it is derived from, byte-compare, and fail with the regeneration
command attached. That is what makes a new corner-sweep record that
supersedes an older one a CI failure rather than a silently stale rollup
nobody notices. A new derived artifact under sim/, layout/ or measurements/
belongs here as another check of the same shape.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple

# sys.path bootstrap only (#337): the fixed depth survives just here, where a
# wrong depth is a loud ImportError instead of a silently wrong tree.
SIM_LIB = Path(__file__).resolve().parents[2] / "sim" / "lib"
sys.path.insert(0, str(SIM_LIB))
from repo_root import find_repo_root  # noqa: E402  (path-injected import)

REPO_ROOT = find_repo_root(Path(__file__))

# Top-level directories that must always carry a README.md describing scope.
DELIVERABLE_DIRS = ["design", "sim", "layout", "views", "measurements", "signoff"]

# Directories that hold evidence records (per CLAUDE.md: "sim/ results are
# append-only evidence") and are therefore subject to the raw-artifact check.
EVIDENCE_DIRS = ["sim", "layout", "measurements"]

# Extensions that are raw/scratch simulator output and must never be
# committed, mirroring the *.raw / *.log / *.vcd / *.vvp rules in .gitignore.
RAW_ARTIFACT_EXTENSIONS = {".raw", ".log", ".vcd", ".vvp"}

# The documented exceptions (see .gitignore): per-corner ngspice logs,
# per-sample Monte Carlo logs, and a deck-mode parity receipt's engine streams
# are committed append-only evidence.
RAW_ARTIFACT_ALLOW_GLOBS = [
    "sim/*/corners/**/*.log",
    "sim/*/mc/raw-logs/**/*.log",
    "sim/deck-parity/**/*.log",
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

# --- "Files in" receipt-table gate (issue #356) -------------------------
# A receipt documents what a run committed via a "## Files in `<dir>/`"
# markdown table whose first (File) column holds backticked paths. Those
# are inline code, not markdown links, so LINK_RE never sees them; the
# checks below resolve them directly against the tracked file list.

# The heading pins the directory the table's paths live under, relative
# to the receipt's own parent directory.
FILES_TABLE_HEADING_RE = re.compile(
    r"^##\s+Files in\s+`([^`]+?)/`\s*$", re.MULTILINE
)
# Every backticked token in the File column is a path (a cell may hold
# more than one, comma-separated). The What column is prose full of
# backticked non-paths (`klt sim`, `--batch-set`, `units/`) and is never
# scanned for paths.
BACKTICKED_TOKEN_RE = re.compile(r"`([^`]+)`")
# A `<...>` placeholder in a File-column token stands for one path
# segment of any name. Note `<family>` expands inconsistently across a
# token (`hold-snm` the directory vs `hold_snm_sweep.txt` the file), so
# placeholders are glob-matched per segment, never literally substituted.
PLACEHOLDER_RE = re.compile(r"<[^<>]*>")
# The exemption token: a row whose What cell contains it describes
# artifacts deliberately not committed, and is accepted with zero
# matches. Documented in sim/deck-parity/README.md's committed-bytes rule.
NONE_COMMITTED_TOKEN = "(none committed)"
# A markdown table separator row such as `|---|---|`.
TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:|-]*$")

# The receipt docs the ungated-table warning scans (issue #372): top-level
# sim/deck-parity/*.md only, README.md excluded. The `| File | What |`
# tables elsewhere (the sim/*/README.md directory listings) are not run
# receipts and must stay outside the warning.
RECEIPT_DOC_RE = re.compile(r"^sim/deck-parity/[^/]+\.md$")


class FilesTableCoverage(NamedTuple):
    """What the receipt "Files in" walk actually looked at (issue #372).

    Counts accumulated by the same walk that produces the unresolved-entry
    errors, so the coverage line in main()'s success message cannot
    disagree with what was checked: a drop to 0 shows up in the CI log
    instead of a fixed assertion reporting green over an ungated receipt.
    """

    tables: int  # "## Files in `<dir>/`" sections parsed
    rows: int  # non-exempt rows walked (each resolved on the success path)
    rows_exempt: int  # rows skipped via the (none committed) token


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


def link_check_docs(tracked: set[str]) -> set[str]:
    """Docs the markdown-link and receipt-table checks scan."""
    doc_paths: set[str] = set()
    for pattern in LINK_CHECK_GLOBS:
        doc_paths.update(resolve_glob(pattern, tracked))
    return doc_paths


def check_markdown_links(tracked: set[str], errors: list[str]) -> None:
    for doc in sorted(link_check_docs(tracked)):
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


def walk_files_table_sections(
    doc_text: str,
) -> Iterator[tuple[str, int, list[list[str]]]]:
    """Walk every "## Files in `<dir>/`" section of a receipt (issue #408).

    Yields one ``(dir_name, header_line, rows)`` triple per heading, where
    ``rows`` is the raw cell rows the section's table contributed (header
    row first, separator rows already dropped -- exactly what
    :func:`parse_files_tables` consumes) and ``header_line`` is the
    0-based full-document line index of the table line taken as the
    header row (``-1`` when the section has no table). Sharing this one
    walk is what lets the ungated-table warning (issue #372) and the
    parser agree on which ``| File | What |`` rows are gated, instead of
    re-deriving gated-ness with a second, differently-shaped scan.
    """
    headings = list(FILES_TABLE_HEADING_RE.finditer(doc_text))
    for i, heading in enumerate(headings):
        section_end = (
            headings[i + 1].start() if i + 1 < len(headings) else len(doc_text)
        )
        line_offset = doc_text.count("\n", 0, heading.end())
        rows: list[list[str]] = []
        header_line = -1
        in_table = False
        for k, line in enumerate(
            doc_text[heading.end():section_end].splitlines()
        ):
            stripped = line.strip()
            if not stripped.startswith("|"):
                if in_table:
                    break
                continue
            in_table = True
            if TABLE_SEPARATOR_RE.match(stripped):
                continue
            if not rows:
                header_line = line_offset + k
            rows.append([c.strip() for c in stripped.strip("|").split("|")])
        yield heading.group(1), header_line, rows


def parse_files_tables(
    doc_text: str,
) -> list[tuple[str, list[tuple[list[str], bool]]]]:
    """Parse every "## Files in `<dir>/`" section of a receipt.

    Returns one ``(dir_name, rows)`` pair per heading. Each row is
    ``(tokens, exempt)``: the backticked tokens of the File cell (the
    table's first column -- the What column is never scanned, it is full
    of backticked non-paths) and whether the What cell carries the
    ``(none committed)`` exemption token. Skips prose between the heading
    and the table, the ``| File | What |`` header and ``|---|---|``
    separator rows; the table ends at the first non-table line or the
    next heading.
    """
    tables: list[tuple[str, list[tuple[list[str], bool]]]] = []
    for dir_name, _header_line, rows in walk_files_table_sections(doc_text):
        parsed: list[tuple[list[str], bool]] = []
        for cells in rows[1:]:  # rows[0] is the "| File | What |" header
            file_cell = cells[0] if cells else ""
            what_cell = cells[1] if len(cells) > 1 else ""
            parsed.append(
                (
                    BACKTICKED_TOKEN_RE.findall(file_cell),
                    NONE_COMMITTED_TOKEN in what_cell,
                )
            )
        tables.append((dir_name, parsed))
    return tables


def glob_segment_match(pattern: str, path: str) -> bool:
    """fnmatch per path segment, so `*` (a `<...>` placeholder) stays
    inside one directory level -- `<a>/<b>/f.txt` must not be satisfied
    by a deeper `a/b/c/f.txt` that happens to exist."""
    pattern_parts = pattern.split("/")
    path_parts = path.split("/")
    if len(pattern_parts) != len(path_parts):
        return False
    return all(
        fnmatch.fnmatch(segment, pattern_segment)
        for segment, pattern_segment in zip(path_parts, pattern_parts)
    )


def walk_files_tables(
    doc_text: str, base_dir: str, file_list: Iterable[str]
) -> tuple[list[tuple[str, str]], FilesTableCoverage]:
    """Single walk of a receipt's "Files in" tables (issue #372).

    Returns the unresolved ``(token, glob_pattern)`` findings -- what
    :func:`unresolved_files_table_rows` reports -- together with the
    :class:`FilesTableCoverage` counted along the way. One walk for both
    so the reported coverage cannot disagree with the errors produced:
    on the success path every non-exempt row counted is a row resolved.
    """
    findings: list[tuple[str, str]] = []
    tables = rows = rows_exempt = 0
    for dir_name, doc_rows in parse_files_tables(doc_text):
        tables += 1
        prefix = f"{base_dir.rstrip('/')}/{dir_name}"
        for tokens, exempt in doc_rows:
            if exempt:
                rows_exempt += 1
                continue
            rows += 1
            for token in tokens:
                pattern = f"{prefix}/{PLACEHOLDER_RE.sub('*', token)}"
                if not any(glob_segment_match(pattern, p) for p in file_list):
                    findings.append((token, pattern))
    return findings, FilesTableCoverage(tables, rows, rows_exempt)


def unresolved_files_table_rows(
    doc_text: str, base_dir: str, file_list: Iterable[str]
) -> list[tuple[str, str]]:
    """Resolve a receipt's "Files in" tables against committed files.

    Pure helper: takes the receipt text, the repo-relative directory the
    receipt lives in (its heading dirs resolve under it), and the tracked
    file list, so it unit-tests without a git checkout. Returns
    ``(token, glob_pattern)`` for every File-cell token that resolves to
    zero committed files; exempt rows (What cell carries
    ``(none committed)``) are skipped entirely.
    """
    findings, _ = walk_files_tables(doc_text, base_dir, file_list)
    return findings


def files_table_error(doc: str, token: str, pattern: str) -> str:
    return (
        f'unresolved "Files in" table entry in {doc}: {token!r} '
        f"matches no committed file (pattern {pattern!r} resolved "
        f"to 0 files); commit the artifact, or annotate the row's "
        f"What cell with {NONE_COMMITTED_TOKEN!r} if nothing is "
        "intentionally committed for it"
    )


def check_receipt_files_tables(
    tracked: set[str], errors: list[str]
) -> FilesTableCoverage:
    """Walk every doc's "Files in" tables, collecting errors; return the
    coverage the same walk counted (issue #372)."""
    tables = rows = rows_exempt = 0
    for doc in sorted(link_check_docs(tracked)):
        full = REPO_ROOT / doc
        try:
            text = full.read_text(encoding="utf-8")
        except OSError:
            # Already reported by check_markdown_links over the same set.
            continue
        base_dir = full.parent.relative_to(REPO_ROOT).as_posix()
        findings, coverage = walk_files_tables(text, base_dir, tracked)
        tables += coverage.tables
        rows += coverage.rows
        rows_exempt += coverage.rows_exempt
        for token, pattern in findings:
            errors.append(files_table_error(doc, token, pattern))
    return FilesTableCoverage(tables, rows, rows_exempt)


def receipt_docs(tracked: set[str]) -> list[str]:
    """Top-level deck-parity receipts: sim/deck-parity/*.md, README.md
    excluded. The ungated-table warning's scan set (issue #372)."""
    return sorted(
        doc
        for doc in link_check_docs(tracked)
        if RECEIPT_DOC_RE.match(doc) and Path(doc).name != "README.md"
    )


def ungated_receipt_headings(doc_text: str) -> list[str]:
    """Headings a ``| File | What |`` table sits under in a receipt doc
    that the receipt files gate does NOT gate (issue #372). The table
    under such a heading is invisible to check 7; the caller warns, it
    does not fail. Returns the nearest heading line per offending table
    (empty string when the table has no preceding heading at all).

    Gated-ness is decided by :func:`walk_files_table_sections` itself, not
    re-derived: every ``| File | What |`` header row whose line index the
    gate's walk consumed is gated, and every other one is ungated (issue
    #408). That fixes both shapes where a backward heading scan disagreed
    with the parser -- a ``#`` line inside a fence between a gated heading
    and its table (warned on a table the gate gates), and a second table
    under one heading (silently skipped, the exact case #372 exists to
    surface). The backward scan remains only to name a heading in the
    warning text; it is message text, not a gate.
    """
    lines = doc_text.splitlines()
    gated_headers = {
        header_line
        for _, header_line, _ in walk_files_table_sections(doc_text)
        if header_line >= 0
    }
    unmatched: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if cells != ["File", "What"]:
            continue
        if i in gated_headers:
            continue
        heading = ""
        for j in range(i - 1, -1, -1):
            candidate = lines[j].strip()
            if candidate.startswith("#"):
                heading = candidate
                break
        unmatched.append(heading)
    return unmatched


def ungated_files_table_warning(doc: str, heading: str) -> str:
    return (
        f'ungated receipt table in {doc}: a "| File | What |" table sits '
        f"under heading {heading!r}, which does not match the gated "
        "'## Files in `<dir>/`' heading grammar -- the table is NOT "
        "checked by the receipt files gate. Fix the heading (## Files in "
        "`<receipt-dir>/`) or document the artifacts in prose if they are "
        "not a committed-bytes inventory"
    )


def check_ungated_receipt_tables(tracked: set[str], warnings: list[str]) -> None:
    """Warn (never fail) when a receipt's table is shaped like a "Files in"
    table but sits under a heading the gate cannot see (issue #372)."""
    for doc in receipt_docs(tracked):
        try:
            text = (REPO_ROOT / doc).read_text(encoding="utf-8")
        except OSError:
            continue
        for heading in ungated_receipt_headings(text):
            warnings.append(ungated_files_table_warning(doc, heading))


def files_table_coverage_clause(coverage: FilesTableCoverage) -> str:
    """The success-line fragment reporting check 7's coverage (issue #372)."""
    clause = (
        f'({coverage.tables} receipt "Files in" tables gated, '
        f"{coverage.rows} rows resolved"
    )
    if coverage.rows_exempt:
        noun = "row" if coverage.rows_exempt == 1 else "rows"
        clause += f", {coverage.rows_exempt} exempt {noun} skipped"
    return clause + ")"


# --- T1 item-9 testbench-attestation gate (issue #357) ------------------
# The item-9 wrapper ("Testbenches shipped") pins an explicitly enumerated
# path set; nothing else ties that enumeration to what sim/ ships, so every
# new bench silently lands outside the verdict of record while the item
# keeps grading `met`. This check makes the drift a CI failure.

# The wrapper whose pinned set must cover every tracked bench.
TESTBENCH_ATTESTATION = "sim/testbenches.signoff.json"


def is_bench_path(path: str) -> bool:
    """A bench is `sim/<experiment>/testbench/tb_*`: exactly one experiment
    level, a `testbench/` directory, and a `tb_` file prefix. The prefix
    rule deliberately excludes the array-stripped DUT netlist copies
    (`sram_256x32.noarray.spice`) that also live in testbench/ dirs -- item
    9 attests benches, not derived design netlists."""
    parts = path.split("/")
    return (
        len(parts) == 4
        and parts[0] == "sim"
        and parts[2] == "testbench"
        and parts[3].startswith("tb_")
    )


def bench_paths(tracked: set[str]) -> set[str]:
    """The tracked files that are benches under the is_bench_path rule."""
    return {p for p in tracked if is_bench_path(p)}


def attestation_gaps(bench_paths: set[str], pinned: set[str]) -> list[str]:
    """Benches the item-9 wrapper fails to pin, sorted.

    Pure helper: takes the tracked bench set and the wrapper's pinned
    paths, so it unit-tests without a repo walk. A pinned path that is not
    a bench (sim/README.md, the DUT netlist copies) is never reported --
    gaps are computed over benches only.
    """
    return sorted(bench_paths - pinned)


def pinned_attestation_paths(wrapper: str) -> list[str]:
    doc = json.loads((REPO_ROOT / wrapper).read_text(encoding="utf-8"))
    return [
        member["path"]
        for member in doc.get("provenance", {}).get("input", {}).get("paths", [])
    ]


def check_testbench_attestation(tracked: set[str], errors: list[str]) -> None:
    if TESTBENCH_ATTESTATION not in tracked:
        # Wrapper not committed in this checkout -- nothing to compare.
        return
    gaps = attestation_gaps(
        bench_paths(tracked), set(pinned_attestation_paths(TESTBENCH_ATTESTATION))
    )
    for path in gaps:
        errors.append(
            f"unattested testbench: {path} is tracked under "
            "sim/<experiment>/testbench/ but absent from the T1 item-9 "
            f"wrapper {TESTBENCH_ATTESTATION} (provenance.input.paths) -- "
            'add it as {"path": ...} and re-run ./signoff/regenerate.sh '
            "so the verdict of record keeps covering every committed bench"
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
    warnings: list[str] = []

    check_readmes(tracked, errors)
    check_raw_artifacts(tracked, errors)
    check_markdown_links(tracked, errors)
    coverage = check_receipt_files_tables(tracked, errors)
    check_ungated_receipt_tables(tracked, warnings)
    check_testbench_attestation(tracked, errors)
    for spec in DERIVED_FILES:
        check_derived_fresh(tracked, errors, spec)

    # Warnings are signal, never verdict (issue #372): an ungated
    # receipt-shaped table must not change the exit status.
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    if errors:
        print("evidence-format check FAILED:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(f"\n{len(errors)} error(s)", file=sys.stderr)
        return 1

    print(
        f"evidence-format check passed: {len(tracked)} tracked files, "
        f"{len(DELIVERABLE_DIRS)} deliverable READMEs present, no disallowed "
        "raw artifacts, no broken relative doc links, every receipt "
        '"Files in" table entry resolves to committed files '
        + files_table_coverage_clause(coverage)
        + ", "
        + ", ".join(f"{d.committed} in sync with {d.generator}" for d in DERIVED_FILES)
        + ", every tracked sim/<experiment>/testbench/tb_* bench pinned by "
        + TESTBENCH_ATTESTATION
        + "."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
