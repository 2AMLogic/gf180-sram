#!/usr/bin/env python3
"""sim/pex/write-margin/compare_records.py -- issue #95.

Compute a per-corner schematic-vs-extracted delta for write margin (write
trip voltage) from two sim/lib/run_corner_sweep.sh evidence records --
replicating, by hand, the same delta shape `klt pex`'s own JSON report
produces for the access-time measurements in ../access-time/reports/ (see
docs/cli/pex.md's `delta[]` schema), since `klt pex` itself cannot run
write-margin's bisection-search testbench (see ../README.md).

Usage:
    ./compare_records.py <schematic-record-id> <extracted-record-id>

Reads sim/pex/write-margin/corners/<record-id>/<corner-id>.log for both
record ids (written by run_corner_sweep.sh), extracts each corner's
`RESULT: write_trip_voltage_v = <value>` line, and writes a delta table to
sim/pex/write-margin/delta/<schematic-id>_vs_<extracted-id>.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = ROOT / "sim" / "pex" / "write-margin"

PROCESSES = ["ff", "tt", "ss"]
TEMPS = [-40, 25, 125]
VDDS = ["2.97", "3.30", "3.63"]

RESULT_RE = re.compile(r"RESULT:\s*write_trip_voltage_v\s*=\s*([-\d.eE]+)")


def read_wtv(record_id: str, corner_id: str) -> float | None:
    log_path = EXPERIMENT_DIR / "corners" / record_id / f"{corner_id}.log"
    if not log_path.is_file():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    match = RESULT_RE.search(text)
    if not match:
        return None
    return float(match.group(1))


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            f"usage: {argv[0]} <schematic-record-id> <extracted-record-id>",
            file=sys.stderr,
        )
        return 2
    schematic_id, extracted_id = argv[1], argv[2]

    rows = []
    open_count = 0
    for process in PROCESSES:
        for temp in TEMPS:
            for vdd in VDDS:
                corner_id = f"{process}_{temp}c_{vdd}v"
                sch_v = read_wtv(schematic_id, corner_id)
                ext_v = read_wtv(extracted_id, corner_id)
                if sch_v is None or ext_v is None:
                    open_count += 1
                    rows.append((corner_id, sch_v, ext_v, None, "error"))
                    continue
                delta_pct = 100.0 * (ext_v - sch_v) / abs(sch_v) if sch_v != 0 else None
                rows.append((corner_id, sch_v, ext_v, delta_pct, "pass"))

    out_dir = EXPERIMENT_DIR / "delta"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{schematic_id}_vs_{extracted_id}.md"

    lines = [
        f"# Write-margin by-hand PEX delta: {schematic_id} (schematic) vs {extracted_id} (extracted)",
        "",
        "Issue #95 -- by-hand replication of `klt pex`'s schematic-vs-extracted",
        "delta report shape (docs/cli/pex.md `delta[]`), since `klt pex` cannot run",
        "write-margin's bisection-search testbench itself (see ../README.md).",
        "",
        "| corner_id | schematic write_trip_voltage_v | extracted write_trip_voltage_v | delta_pct | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for corner_id, sch_v, ext_v, delta_pct, status in rows:
        sch_s = f"{sch_v:.5f}" if sch_v is not None else "OPEN"
        ext_s = f"{ext_v:.5f}" if ext_v is not None else "OPEN"
        delta_s = f"{delta_pct:.3f}" if delta_pct is not None else "n/a"
        lines.append(f"| {corner_id} | {sch_s} | {ext_s} | {delta_s} | {status} |")

    lines.append("")
    if open_count:
        lines.append(
            f"**{open_count} corner(s) OPEN** -- no valid RESULT line on one or both legs; "
            "not silently dropped, per spec/sram.md's Signoff definition."
        )
    else:
        lines.append(
            f"All {len(rows)} corners produced a paired schematic/extracted value -- "
            "non-vacuous, per-corner delta."
        )
    lines.append("")
    lines.append(
        f"- Schematic record: `sim/pex/write-margin/records/{schematic_id}.md`"
    )
    lines.append(
        f"- Extracted record: `sim/pex/write-margin/records/{extracted_id}.md`"
    )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    print(f"{open_count} OPEN corner(s) out of {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
