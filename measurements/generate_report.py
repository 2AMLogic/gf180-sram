#!/usr/bin/env python3
"""Render the aggregated SRAM macro characterization report.

Closes the gap `sim/README.md` and `spec/sram.md` leave open: no single
document in this repo summarizes per-spec-row performance (read SNM, hold
SNM, write margin, read/write access time) across the ratified 27-corner PVT
matrix *and* the Monte Carlo / yield evidence (issue #26), with every number
traceable to the `sim/` evidence record it rests on. `sim/signoff-summary.md`
already does this for the deterministic 27-corner data alone (issue #25); this
script adds the MC/yield layer on top and combines both into one artifact, per
klayout-tools `docs/design-evidence-tiers.md` item 8.

This script does not run any simulation and does not modify any committed
`sim/` record (the append-only rule stays intact, `sim/README.md`
"Append-only rule"). It only *derives* a report from already-committed
evidence, reusing `sim/lib/render_signoff_table.py`'s own record-selection
and rendering logic so the two documents can never silently disagree about
which record is "latest" for a given claim.

Usage:
    python3 measurements/generate_report.py [repo-root]

Output: a Markdown document on stdout. The repo commits this as
`measurements/characterization-report.md`, regenerated (not hand-edited)
whenever any of the source records below is superseded by a fresh sweep or
campaign:

    python3 measurements/generate_report.py > measurements/characterization-report.md

Freshness / staleness check: `scripts/ci/check_evidence_format.py` re-renders
this report from whatever records are committed and fails CI if
`measurements/characterization-report.md` does not match byte-for-byte --
the same enforcement `sim/signoff-summary.md` already has. The report's own
"Provenance" section below also names every source record's ID and git sha
directly, so a human can spot staleness without running anything.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SIM_LIB = REPO_ROOT / "sim" / "lib"
sys.path.insert(0, str(SIM_LIB))
import render_signoff_table as signoff  # noqa: E402  (path-injected import)

# The three stability-margin measurements that have Monte Carlo / yield
# evidence (issue #26). Access time has no MC campaign -- it is not a
# statistical-margin claim, see spec/sram.md's Characterization section.
MC_MEASUREMENTS = [
    ("read-snm", "read SNM", "Read SNM"),
    ("hold-snm", "hold SNM", "Hold SNM"),
    ("write-margin", "write margin", "Write margin"),
]

FIELD_RE = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.*)$")


def record_id_and_sha(path: Path) -> tuple[str, str]:
    """<record-id> = <YYYYMMDD>-<HHMMSS>-<short-sha> (sim/README.md); split
    off the trailing short git sha."""
    record_id = path.stem
    parts = record_id.split("-", 2)
    sha = parts[2] if len(parts) == 3 else "?"
    return record_id, sha


def parse_fields(text: str) -> dict[str, str]:
    """Collect every top-level '- **Label**: value' bullet into a dict, first
    occurrence wins. Used for the small set of scalar metadata fields (Record
    ID, Timestamp / author, Seed, Sample count, ...) each record type carries
    -- not for the per-corner Result rows, which have their own parser."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        m = FIELD_RE.match(line.strip())
        if m:
            fields.setdefault(m.group(1), m.group(2))
    return fields


def field_like(fields: dict[str, str], *substrings: str) -> str | None:
    """Look up a field whose label contains every one of `substrings`
    (case-insensitive) -- tolerates the odd inline backtick/formatting
    variance between record types without requiring an exact label match."""
    for label, value in fields.items():
        lowered = label.lower()
        if all(s.lower() in lowered for s in substrings):
            return value
    return None


def latest_mc_record_for_claim(records_dir: Path, claim_substring: str) -> Path:
    """Same convention as signoff.latest_record_for_claim, applied to the
    parallel sim/<experiment>/mc/records/ tree (sim/README.md, "Monte Carlo
    / yield evidence records")."""
    candidates = []
    for path in sorted(records_dir.glob("*.md")):
        text = path.read_text()
        for line in text.splitlines():
            if line.startswith("- **Claim**:") and claim_substring in line:
                candidates.append(path)
                break
    if not candidates:
        raise SystemExit(
            f"no MC record under {records_dir} has a Claim containing "
            f"{claim_substring!r}"
        )
    return sorted(candidates)[-1]


def rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


def worst_case_rows() -> list[dict]:
    """One row per spec-row measurement: the worst value across all 27
    ratified corners, which corner produced it, its verdict, and the exact
    sim/ record it was read from -- the per-number citation acceptance
    criterion #2 asks for, at the granularity that matters (the extreme
    value is what a reviewer checks first)."""
    read_snm_record = signoff.latest_record_for_claim(
        REPO_ROOT / "sim/read-snm/records", "read SNM"
    )
    hold_snm_record = signoff.latest_record_for_claim(
        REPO_ROOT / "sim/hold-snm/records", "hold SNM"
    )
    write_margin_record = signoff.latest_record_for_claim(
        REPO_ROOT / "sim/write-margin/records", "write margin"
    )
    read_at_record = signoff.latest_record_for_claim(
        REPO_ROOT / "sim/access-time/records", "read access time"
    )
    write_at_record = signoff.latest_record_for_claim(
        REPO_ROOT / "sim/access-time/records", "write access time"
    )

    read_snm = signoff.parse_record(read_snm_record)
    hold_snm = signoff.parse_record(hold_snm_record)
    write_margin = signoff.parse_record(write_margin_record)
    read_at = signoff.parse_record(read_at_record)
    write_at = signoff.parse_record(write_at_record)

    def extreme(
        parsed: dict, key: str, record: Path, unit: str, pick_min: bool, verdict_fn
    ) -> dict:
        best_corner = None
        best_val = None
        for corner in signoff.CORNER_ORDER:
            entry = parsed.get(corner)
            if not isinstance(entry, dict) or key not in entry:
                continue
            val = entry[key]
            if best_val is None or (val < best_val if pick_min else val > best_val):
                best_val, best_corner = val, corner
        fmt = signoff.fmt_v if unit == "V" else signoff.fmt_s
        return {
            "value": fmt(best_val) if best_val is not None else "--",
            "unit": unit,
            "corner": best_corner or "--",
            "verdict": verdict_fn(best_val),
            "record": record,
        }

    return [
        {
            "measurement": "Read SNM",
            **extreme(
                read_snm, "read_snm_v", read_snm_record, "V", True, signoff.verdict_threshold
            ),
        },
        {
            "measurement": "Hold SNM",
            **extreme(
                hold_snm, "hold_snm_v", hold_snm_record, "V", True, signoff.verdict_threshold
            ),
        },
        {
            "measurement": "Write margin (WTV)",
            **extreme(
                write_margin,
                "write_trip_voltage_v",
                write_margin_record,
                "V",
                True,
                signoff.verdict_threshold,
            ),
        },
        {
            "measurement": "Read access time (slowest)",
            **extreme(
                read_at,
                "read_access_time_s",
                read_at_record,
                "s",
                False,
                signoff.verdict_recorded,
            ),
        },
        {
            "measurement": "Write access time (slowest)",
            **extreme(
                write_at,
                "write_access_time_s",
                write_at_record,
                "s",
                False,
                signoff.verdict_recorded,
            ),
        },
    ]


def parse_md_table(text: str, heading_prefix: str) -> list[list[str]]:
    """Extract the first Markdown table's rows (including header + separator)
    that appears after a line starting with `heading_prefix`."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(heading_prefix):
            start = i
            break
    if start is None:
        raise SystemExit(f"heading starting with {heading_prefix!r} not found")
    rows: list[list[str]] = []
    in_table = False
    for line in lines[start:]:
        if line.strip().startswith("|"):
            in_table = True
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif in_table:
            break
    return rows


def mc_summary(slug: str, claim_substring: str) -> dict:
    records_dir = REPO_ROOT / "sim" / slug / "mc" / "records"
    record = latest_mc_record_for_claim(records_dir, claim_substring)
    text = record.read_text()
    fields = parse_fields(text)

    table = parse_md_table(text, "## Per-corner result")
    data_rows = table[2:]  # skip header + separator
    # Columns: Corner | N | errored | mean | stddev | empirical yield lower
    # bound | Cpk | sigma-to-spec | sample-size verdict | negative control
    cpks = [float(r[6]) for r in data_rows if r[6] not in ("", "-")]
    sigmas = [float(r[7]) for r in data_rows if r[7] not in ("", "-")]
    detected = sum(1 for r in data_rows if r[9] == "detected")

    record_id, sha = record_id_and_sha(record)
    return {
        "record": record,
        "record_id": record_id,
        "sha": sha,
        "timestamp": (field_like(fields, "timestamp") or "?").split()[0].rstrip(","),
        "sample_count": field_like(fields, "sample count") or "?",
        "seed": field_like(fields, "seed") or "?",
        "n_corners": len(data_rows),
        "min_cpk": min(cpks) if cpks else None,
        "min_sigma_to_spec": min(sigmas) if sigmas else None,
        "negative_control_detected": detected,
        "negative_control_total": len(data_rows),
    }


def embed_mc_record(slug: str, claim_substring: str) -> str:
    """Embed the source MC record verbatim through its warnings section
    (metadata + per-corner table + determinism control + negative control +
    klt-yield warnings), dropping the Links/Reproduce/verbatim-text-report
    tail that would otherwise duplicate the same numbers a third time."""
    records_dir = REPO_ROOT / "sim" / slug / "mc" / "records"
    record = latest_mc_record_for_claim(records_dir, claim_substring)
    text = record.read_text()
    lines = text.splitlines()

    cut = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "## Links":
            cut = i
            break

    body_lines = lines[1:cut]  # drop the record's own "# MC/yield record ..." title
    demoted = []
    for line in body_lines:
        if line.startswith("## "):
            demoted.append("#### " + line[3:])
        else:
            demoted.append(line)
    body = "\n".join(demoted).strip("\n")

    return (
        f"Source: `{rel(record)}` (full record; raw per-sample logs,"
        f" sample-set JSON, and the verbatim `klt yield` text report are"
        f" linked from that file, not reproduced here).\n\n{body}\n"
    )


def render_signoff_embed() -> str:
    """Run sim/lib/render_signoff_table.py fresh and embed its output
    verbatim (headers demoted by one level) -- the exact same generator
    sim/signoff-summary.md is regenerated from, so the two can never
    silently disagree about the 27-corner data."""
    result = subprocess.run(
        [sys.executable, str(SIM_LIB / "render_signoff_table.py"), str(REPO_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()
    demoted = []
    for line in lines:
        if line.startswith("# "):
            demoted.append("### " + line[2:])
        elif line.startswith("## "):
            demoted.append("#### " + line[3:])
        else:
            demoted.append(line)
    return "\n".join(demoted).strip("\n") + "\n"


def main() -> int:
    global REPO_ROOT
    if len(sys.argv) > 1:
        REPO_ROOT = Path(sys.argv[1]).resolve()

    worst = worst_case_rows()
    mc_stats = {slug: mc_summary(slug, claim) for slug, claim, _ in MC_MEASUREMENTS}

    lines: list[str] = []
    lines.append("# SRAM macro characterization report")
    lines.append("")
    lines.append(
        "Auto-generated by `measurements/generate_report.py` -- do not"
        " hand-edit. Regenerate with:"
    )
    lines.append("")
    lines.append(
        "```bash\npython3 measurements/generate_report.py >"
        " measurements/characterization-report.md\n```"
    )
    lines.append("")
    lines.append(
        "This is the single, current, aggregated artifact `spec/sram.md`'s"
        " Characterization section and klayout-tools"
        " `docs/design-evidence-tiers.md` item 8 ask for: per-spec-row"
        " performance (read SNM, hold SNM, write margin, read/write access"
        " time) across every one of the ratified 27-corner"
        " process x temperature x voltage PVT points (`spec/sram.md`,"
        " \"Corner set\"), plus the Monte Carlo / mismatch yield evidence"
        " (issue #26) over a deliberate 9-corner subset of that matrix"
        " (`sim/README.md`, \"Which corners, and why not all of them\")."
        " Every number below is a read-only derivation from the"
        " append-only records already committed under `sim/` -- this"
        " script runs no simulation and edits no record."
    )
    lines.append("")
    lines.append(
        "**Netlist provenance**: schematic-level for every record cited"
        " here -- this repo has not yet produced a DRC/LVS-clean, extracted"
        " netlist (`layout/` is in progress). A post-layout re-run of any"
        " measurement would supersede its record and this report would be"
        " regenerated to reflect it. **Bitcell sizing status**:"
        " `design/README.md` records the current `bitcell_6t` sizing as"
        " \"an independent first cut,\" not yet deliberately optimized for"
        " SNM or write margin -- the margins below are real evidence for"
        " this sizing, not yet informed by any such optimization pass."
    )
    lines.append("")

    # --- Provenance / staleness check -------------------------------------
    lines.append("## Provenance (staleness check)")
    lines.append("")
    lines.append(
        "Every number in this report traces to exactly one of the source"
        " records below -- the report is a derivation, not a restatement."
        " If a newer record now exists under `sim/*/records/` or"
        " `sim/*/mc/records/` for any of these claims (i.e. the IDs below"
        " no longer match what `sim/lib/render_signoff_table.py`'s own"
        " `latest_record_for_claim` selects), this report is stale --"
        " regenerate it with the command above."
        " `scripts/ci/check_evidence_format.py` enforces this automatically"
        " on every PR, the same way it already enforces"
        " `sim/signoff-summary.md`'s freshness."
    )
    lines.append("")
    lines.append("| Row | Kind | Source record | Record ID | Git sha | Timestamp |")
    lines.append("|---|---|---|---|---|---|")
    for row in worst:
        record_id, sha = record_id_and_sha(row["record"])
        fields = parse_fields(row["record"].read_text())
        ts = (field_like(fields, "timestamp") or "?").split()[0].rstrip(",")
        lines.append(
            f"| {row['measurement']} | 27-corner PVT | `{rel(row['record'])}` |"
            f" `{record_id}` | `{sha}` | {ts} |"
        )
    for slug, claim, label in MC_MEASUREMENTS:
        stats = mc_stats[slug]
        lines.append(
            f"| {label} | Monte Carlo / yield (9-corner subset) |"
            f" `{rel(stats['record'])}` | `{stats['record_id']}` |"
            f" `{stats['sha']}` | {stats['timestamp']} |"
        )
    lines.append("")

    # --- Per-spec-row summary -----------------------------------------------
    lines.append("## Per-spec-row summary (worst case across all 27 corners)")
    lines.append("")
    lines.append(
        "The extreme value across the full 27-corner matrix for each"
        " spec-row measurement -- the number a signoff review checks"
        " first. Full per-corner detail is in \"Full 27-corner PVT"
        " results\" below."
    )
    lines.append("")
    lines.append("| Measurement | Extreme value | Corner | Verdict | Source record |")
    lines.append("|---|---|---|---|---|")
    for row in worst:
        lines.append(
            f"| {row['measurement']} | {row['value']} {row['unit']} |"
            f" `{row['corner']}` | {row['verdict']} | `{rel(row['record'])}` |"
        )
    lines.append("")

    # --- MC / yield summary ---------------------------------------------
    lines.append("## Monte Carlo / yield summary (9-corner subset)")
    lines.append("")
    lines.append(
        "Device-mismatch statistical evidence (issue #26), combined"
        " with -- not instead of -- the deterministic corner evidence"
        " above, per klayout-tools `docs/design-evidence-tiers.md` item 6."
        " Each campaign draws 200 mismatch samples, 4 determinism-control"
        " samples (must reproduce the deterministic corner record exactly),"
        " and 100 negative-control samples (a deliberately degraded"
        " variant, which must show a detectably lower yield) per corner."
        " No `target_yield` is declared -- `spec/sram.md` ratifies no yield"
        " target for these rows (open decision, issue #20) -- so these"
        " numbers are *reported* against the `> 0` spec limit via Cpk /"
        " sigma-to-spec, never graded pass/fail."
    )
    lines.append("")
    lines.append(
        "| Measurement | Corners sampled | Min Cpk | Min sigma-to-spec |"
        " Negative control | Source record |"
    )
    lines.append("|---|---|---|---|---|---|")
    for slug, claim, label in MC_MEASUREMENTS:
        stats = mc_stats[slug]
        cpk = f"{stats['min_cpk']:.4f}" if stats["min_cpk"] is not None else "--"
        sigma = (
            f"{stats['min_sigma_to_spec']:.4f}"
            if stats["min_sigma_to_spec"] is not None
            else "--"
        )
        nc = f"{stats['negative_control_detected']}/{stats['negative_control_total']} detected"
        lines.append(
            f"| {label} | {stats['n_corners']} | {cpk} | {sigma} | {nc} |"
            f" `{rel(stats['record'])}` |"
        )
    lines.append("")

    for slug, claim, label in MC_MEASUREMENTS:
        lines.append(f"### {label} -- Monte Carlo / yield detail")
        lines.append("")
        lines.append(embed_mc_record(slug, claim))

    # --- Full 27-corner PVT detail ------------------------------------------
    lines.append("## Full 27-corner PVT results")
    lines.append("")
    lines.append(
        "Embedded verbatim from `sim/lib/render_signoff_table.py`'s own"
        " output -- the identical generator `sim/signoff-summary.md` is"
        " built from, re-run fresh for this report so the two documents"
        " can never silently disagree."
    )
    lines.append("")
    lines.append(render_signoff_embed())

    sys.stdout.write("\n".join(lines).rstrip("\n") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
