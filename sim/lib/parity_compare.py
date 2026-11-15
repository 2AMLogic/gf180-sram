#!/usr/bin/env python3
"""Mechanical parity comparison for the #230 full-grid deck-mode receipt.

Compares one family's `deck_adapter.py reduce` grading (`reduced.json`) against
that family's latest committed record under `sim/*/records/`, prints the
markdown comparison table the receipt embeds, and exits non-zero on any
mismatch, missing corner, `OPEN` corner or over-threshold delta. A comparison
nobody can re-run is not verification; this is the re-runnable form.

What it asserts, per the 2026-11-15 curated acceptance criteria for #230:

* **Coverage, asserted not assumed**: the reduced report and the record must
  cover exactly the same corner ids (all 27 of the ratified matrix for the
  full-grid receipt). The comparison keys on the record's *parsed per-corner
  rows*, never on its header corner count -- the `write-margin` record's
  header says "9 corner points total" while listing all 27, and records are
  append-only so that inaccuracy stays.
* **Deck bytes, asserted here not inherited**: with `--request`, every
  `reduced.json` corner entry must carry a `deck_sha256` that is *present and
  equal* to the request's `composed_deck_sha256`. #347 measured that
  `reduce_report`'s own drift check skips a unit whose `deck_sha256` is
  `None` or absent, so `reduce`'s silence is not proof the decks matched.
* **`RESULT:`-emitting families** (`write-margin`, `read-access`,
  `write-access`): every metric in the record's row must reproduce *exactly*
  (float equality -- both sides are parsed from the same `RESULT:` grammar at
  the same printed precision).
* **The two SNM families** (`read-snm`, `hold-snm`): the committed record's
  SNM values use the pre-#213 extractor (see `sim/README.md` "Earlier SNM
  values over-read"), so the fleet's returned `*_sweep.txt` per corner is run
  through the historical extractor (`--pre213`, the `e140796^` script) and
  compared to the record with the documented tolerance: **<= 30 uV** on the
  recorded metric (`<label>_v`; 10x the 3 uV residual actually measured at
  `tt_25c_3.30v`, attributed to the ngspice compatibility-mode difference,
  #338). Every metric's per-corner delta is tabulated; lobe intermediates are
  tabulated too, but only the recorded metric gates the verdict, per the AC.

It is a comparator and nothing more: it never re-runs a simulation, never
mints a record, and never writes under `sim/*/records`. Record values come
from `render_signoff_table.latest_record_for_claim()` / `parse_record()` via
the shared `RECORD_CLAIMS` table -- no second record parser, by design.

Usage:
    parity_compare.py <family> <reduced.json> [--request REQUEST.json]
                      [--record PATH] [--sweep-dir DIR] [--pre213 PATH]
                      [--tolerance-v 3e-05] [--json-out FILE]

`--record` overrides the latest-record lookup (offline tests use fixtures).
`--sweep-dir` / `--pre213` are required for the SNM families; the sweep file
for corner C is `<sweep-dir>/C/<datafile>` -- the per-corner subdirectory
layout `deck_adapter.py reduce --outdir` produces and the receipt commits.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deck_adapter  # noqa: E402
from render_signoff_table import RECORD_CLAIMS, latest_record_for_claim, parse_record  # noqa: E402
from repo_root import find_repo_root  # noqa: E402

REPO_ROOT = find_repo_root(Path(__file__))

# 10x the one residual actually measured (3 uV / 2.7 ppm at tt_25c_3.30v,
# attributed to the compatibility-mode difference #338). Curated 2026-11-15.
TOLERANCE_V_DEFAULT = 30e-6
# abs-delta comparisons get this slack so binary-float parsing noise (a
# decimal like 0.50003 is not exactly representable) cannot flip a boundary.
_FLOAT_EPS = 1e-12

RESULT_RE = re.compile(r"RESULT:\s*(\w+)\s*=\s*([-+0-9.eE]+)\s*;?")
RESULT_ERROR_RE = re.compile(r"^RESULT-ERROR:.*$", re.MULTILINE)


def parse_result_lines(text):
    """{metric: float} from RESULT: lines, like the reducer's own grammar."""
    return {k: float(v) for k, v in RESULT_RE.findall(text)}


def pre213_values(pre213_path, sweep_path, label):
    """Run the historical extractor over one fleet sweep file.

    Returns (values, problems): values is {metric: float} from the script's
    RESULT lines; problems lists failure reasons (non-zero exit,
    RESULT-ERROR lines, or no RESULT lines at all -- never treated as data).
    """
    problems = []
    proc = subprocess.run(
        [sys.executable, str(pre213_path), str(sweep_path), label],
        capture_output=True, text=True, timeout=120,
    )
    out = proc.stdout + proc.stderr
    problems += [m.strip() for m in RESULT_ERROR_RE.findall(out)]
    if proc.returncode != 0:
        problems.append(f"pre-#213 extractor exited {proc.returncode}")
    values = parse_result_lines(proc.stdout)
    if not values and not problems:
        problems.append("pre-#213 extractor produced no RESULT lines")
    return values, problems


def _verdict(delta, tolerance_v):
    """EXACT / WITHIN-TOL / ABOVE-TOL for one metric's delta."""
    if delta == 0.0:
        return "EXACT"
    if abs(delta) <= tolerance_v + _FLOAT_EPS:
        return "WITHIN-TOL"
    return "ABOVE-TOL"


def compare(family, reduced, record_path, *, request=None, sweep_dir=None,
            pre213=None, tolerance_v=TOLERANCE_V_DEFAULT):
    """Compare one family's reduced grading against its committed record.

    Returns the summary dict `--json-out` writes; `overall` is "parity" only
    when coverage is exact, the deck-sha assertion passes (when a request is
    given), and every corner reproduces the record (exactly, or within
    tolerance on the recorded metric for the SNM families).
    """
    if family not in RECORD_CLAIMS:
        raise SystemExit(f"unknown family {family!r}; known: {sorted(RECORD_CLAIMS)}")
    records_rel, _claim, metric = RECORD_CLAIMS[family]
    _exp_dir, _tb, mode = deck_adapter.FAMILIES[family]
    kind, datafile, label = deck_adapter.parse_mode(mode)

    problems = []          # global (coverage / deck-bytes) failures
    record = parse_record(Path(record_path))

    fleet_ids = [c.get("id") for c in reduced.get("corners", [])]
    dupes = sorted({i for i in fleet_ids if fleet_ids.count(i) > 1})
    if dupes:
        problems.append(f"duplicate corner ids in reduced report: {dupes}")
    rec_ids = set(record)
    flt_ids = set(fleet_ids)
    missing_in_record = sorted(flt_ids - rec_ids)
    missing_in_fleet = sorted(rec_ids - flt_ids)
    if missing_in_record:
        problems.append(f"corners in the fleet report but not the record: {missing_in_record}")
    if missing_in_fleet:
        problems.append(f"corners in the record but not the fleet report: {missing_in_fleet}")

    # Deck-bytes assertion: present AND equal, for every unit (the #347 gap:
    # reduce skips an absent field, so absence must fail here, not pass).
    deck_sha_errors = []
    if request is not None:
        composed = (request.get("x_gf180_sram_adapter") or {}).get("composed_deck_sha256")
        if not composed:
            problems.append("request has no x_gf180_sram_adapter.composed_deck_sha256 to assert against")
        else:
            for entry in reduced.get("corners", []):
                sha = entry.get("deck_sha256")
                if sha is None:
                    deck_sha_errors.append(f"{entry.get('id')}: deck_sha256 absent from the report unit")
                elif sha != composed:
                    deck_sha_errors.append(f"{entry.get('id')}: deck_sha256 differs from the composed deck")
            problems.extend(deck_sha_errors)

    corners = []
    by_id = {}
    for entry in reduced.get("corners", []):
        by_id.setdefault(entry.get("id"), entry)
    for cid in fleet_ids:
        entry = by_id.get(cid)
        record_row = record.get(cid)
        if entry is None:  # duplicate collapsed; already a global problem
            continue
        if entry.get("status") != "recorded":
            corners.append({
                "id": cid, "status": "OPEN", "reasons": list(entry.get("reasons", [])),
                "metrics": {},
            })
            continue
        if record_row == "OPEN" or record_row is None:
            corners.append({
                "id": cid, "status": "MISMATCH",
                "reasons": ["record has no measured value for this corner"],
                "metrics": {},
            })
            continue
        if kind == "snm":
            if sweep_dir is None or pre213 is None:
                raise SystemExit(
                    f"{family} is an SNM family: --sweep-dir and --pre213 are required "
                    f"(the record's values come from the pre-#213 extractor)"
                )
            sweep_path = Path(sweep_dir) / cid / datafile
            if not sweep_path.is_file():
                corners.append({
                    "id": cid, "status": "MISMATCH",
                    "reasons": [f"declared sweep output not found: {sweep_path}"],
                    "metrics": {},
                })
                continue
            fleet_vals, probs = pre213_values(pre213, sweep_path, label)
            if probs:
                corners.append({"id": cid, "status": "MISMATCH", "reasons": probs, "metrics": {}})
                continue
        else:
            fleet_vals = entry.get("results") or {}

        metrics = {}
        corner_ok = True
        reasons = []
        for key, record_val in record_row.items():
            if key not in fleet_vals:
                corner_ok = False
                reasons.append(f"metric {key} missing from the fleet result")
                metrics[key] = {"record": record_val, "fleet": None, "delta": None,
                                "verdict": "MISMATCH"}
                continue
            fleet_val = fleet_vals[key]
            delta = fleet_val - record_val
            if kind == "snm" and key != metric:
                # Lobe intermediates: tabulated, not gated (AC pins the
                # threshold to the recorded metric).
                verdict = _verdict(delta, tolerance_v)
            else:
                verdict = "EXACT" if delta == 0.0 else "MISMATCH"
                if kind != "snm" and delta != 0.0:
                    corner_ok = False
                    reasons.append(f"{key}: record {record_val!r} vs fleet {fleet_val!r}")
                elif kind == "snm" and verdict != "EXACT":
                    if abs(delta) > tolerance_v + _FLOAT_EPS:
                        corner_ok = False
                        reasons.append(
                            f"{key}: |delta| {abs(delta):.3e} V exceeds the {tolerance_v:.0e} V tolerance"
                        )
                        verdict = "ABOVE-TOL"
                    else:
                        verdict = "WITHIN-TOL"
            metrics[key] = {"record": record_val, "fleet": fleet_val,
                            "delta": delta, "verdict": verdict}
        for key in fleet_vals:
            if key not in record_row:
                corner_ok = False
                reasons.append(f"metric {key} not in the record row")
                metrics[key] = {"record": None, "fleet": fleet_vals[key], "delta": None,
                                "verdict": "MISMATCH"}
        corners.append({
            "id": cid,
            "status": "parity" if corner_ok else "MISMATCH",
            "reasons": reasons,
            "metrics": metrics,
        })

    overall = "parity"
    if problems or any(c["status"] != "parity" for c in corners):
        overall = "OPEN" if any(c["status"] == "OPEN" for c in corners) else "MISMATCH"
    return {
        "family": family,
        "mode": mode,
        "recorded_metric": metric,
        "comparison": "pre213-tolerance" if kind == "snm" else "exact",
        "tolerance_v": tolerance_v,
        "record": str(record_path),
        "coverage": {
            "corners": len(set(fleet_ids) & rec_ids),
            "missing_in_record": missing_in_record,
            "missing_in_fleet": missing_in_fleet,
        },
        "deck_sha256": {
            "checked": request is not None,
            "errors": deck_sha_errors,
        },
        "corners": corners,
        "problems": problems,
        "overall": overall,
    }


def render_markdown(summary):
    """The comparison table the receipt embeds, on stdout."""
    family = summary["family"]
    metric = summary["recorded_metric"]
    cov = summary["coverage"]
    sha = summary["deck_sha256"]
    lines = [f"## Parity comparison: `{family}`", ""]
    if summary["comparison"] == "pre213-tolerance":
        rule = (
            f"pre-#213 extractor (`e140796^`) applied to the fleet's own sweep data; "
            f"tolerance {summary['tolerance_v']:.0e} V on the recorded metric `{metric}` "
            f"(lobes tabulated, not gated)"
        )
    else:
        rule = "exact float equality on every metric in the record row"
    lines += [
        f"- Committed record: `{summary['record']}`",
        f"- Comparison rule: {rule}",
        f"- Coverage: {cov['corners']} corners on both sides"
        + (f" -- missing in record: {cov['missing_in_record']}" if cov["missing_in_record"] else "")
        + (f" -- missing in fleet: {cov['missing_in_fleet']}" if cov["missing_in_fleet"] else ""),
        f"- Deck bytes asserted: {sha['checked']}"
        + (f" -- errors: {sha['errors']}" if sha["errors"] else " (all units present-and-equal)"
           if sha["checked"] else ""),
        "",
        "| Corner | Metric | Record | Fleet | Delta | Verdict |",
        "|---|---|---|---|---|---|",
    ]

    def fmt(x):
        return "--" if x is None else repr(x)

    def fmt_delta(x):
        return "--" if x is None else f"{x:.3e}"

    open_reasons = []
    for corner in summary["corners"]:
        if corner["status"] == "OPEN" or not corner["metrics"]:
            open_reasons.append(f"- `{corner['id']}`: {corner['status']}"
                                + (f" -- {'; '.join(corner['reasons'])}" if corner["reasons"] else ""))
            lines.append(f"| `{corner['id']}` | -- | -- | -- | -- | "
                         f"{corner['status']} |")
            continue
        for key, m in corner["metrics"].items():
            lines.append(
                f"| `{corner['id']}` | {key} | {fmt(m['record'])} | {fmt(m['fleet'])} | "
                f"{fmt_delta(m['delta'])} | {m['verdict']} |"
            )
    lines.append("")

    max_deltas = {}
    for corner in summary["corners"]:
        for key, m in corner["metrics"].items():
            if m["delta"] is not None:
                max_deltas[key] = max(max_deltas.get(key, 0.0), abs(m["delta"]))
    if max_deltas:
        lines.append("**Maximum |delta| per metric**:")
        lines.append("")
        for key, d in sorted(max_deltas.items()):
            gate = " (gated)" if key == metric else ""
            lines.append(f"- `{key}`: {d:.3e} V{gate}")
        lines.append("")
    n_parity = sum(1 for c in summary["corners"] if c["status"] == "parity")
    n_open = sum(1 for c in summary["corners"] if c["status"] == "OPEN")
    n_mis = sum(1 for c in summary["corners"] if c["status"] == "MISMATCH")
    lines.append(
        f"**Corner verdicts**: {n_parity}/{len(summary['corners'])} parity; "
        f"{n_open} OPEN; {n_mis} MISMATCH. Overall: **{summary['overall']}**."
    )
    if open_reasons:
        lines += ["", "**Non-parity corners**:", *open_reasons]
    if summary["problems"]:
        lines += ["", "**Comparison-level problems**:", *(f"- {p}" for p in summary["problems"])]
    return "\n".join(lines) + "\n"


def default_record_path(family):
    records_rel, claim, _metric = RECORD_CLAIMS[family]
    return latest_record_for_claim(REPO_ROOT / "sim" / records_rel, claim)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("family", help="one of: %s" % ", ".join(sorted(RECORD_CLAIMS)))
    ap.add_argument("reduced", help="deck_adapter.py reduce --json-out file")
    ap.add_argument("--request", help="the request.json build wrote; enables the deck_sha256 assertion")
    ap.add_argument("--record", help="record path override (default: family's latest under sim/*/records)")
    ap.add_argument("--sweep-dir", help="directory holding <corner-id>/<datafile> (SNM families)")
    ap.add_argument("--pre213", help="path to the pre-#213 snm_extract.py (SNM families)")
    ap.add_argument("--tolerance-v", type=float, default=TOLERANCE_V_DEFAULT,
                    help="SNM recorded-metric tolerance in volts (default 3e-05 = 30 uV)")
    ap.add_argument("--json-out", help="write the machine-readable summary here")
    args = ap.parse_args()

    reduced = json.loads(Path(args.reduced).read_text())
    if reduced.get("family") != args.family:
        print(f"reduced.json is for family {reduced.get('family')!r}, not {args.family!r}",
              file=sys.stderr)
        return 2
    record_path = Path(args.record) if args.record else default_record_path(args.family)
    request = json.loads(Path(args.request).read_text()) if args.request else None

    summary = compare(
        args.family, reduced, record_path,
        request=request, sweep_dir=args.sweep_dir, pre213=args.pre213,
        tolerance_v=args.tolerance_v,
    )
    summary["record"] = str(record_path)
    sys.stdout.write(render_markdown(summary))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, indent=1) + "\n")
    return 0 if summary["overall"] == "parity" else 1


if __name__ == "__main__":
    raise SystemExit(main())
