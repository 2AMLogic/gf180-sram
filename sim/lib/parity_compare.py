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

MC mode -- the Monte Carlo counterpart for #230's `mc-build`/`mc-reduce`
increment, compared against the committed MC sample-set (whose values
predate the #213 extractor, so the SNM families are recomputed per sample
with the historical `--pair` extractor) and anchored per corner on the
committed *deterministic* record via the `ctrl` batch:

    parity_compare.py mc <family> <reduced.json> --request REQUEST.json
                         --report REPORT.json [--samples SAMPLES.json]
                         [--record PATH] [--unit-dir DIR] [--sweep-dir DIR]
                         [--pre213 PATH] [--tolerance-v 3e-05] [--json-out FILE]

`--record` overrides the latest-record lookup (offline tests use fixtures).
`--sweep-dir` / `--pre213` are required for the SNM families; the corner-mode
sweep layout is `<sweep-dir>/<corner-id>/<datafile>` (per-corner
subdirectories, `deck_adapter.py reduce --outdir`); the MC sweep layout is
`<sweep-dir>/<unit-id>/<datafile>` (per-unit directories, the deck report's
own unit tree).
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
import run_mc_campaign as mc  # noqa: E402
from render_signoff_table import (  # noqa: E402
    MC_SAMPLE_SETS,
    RECORD_CLAIMS,
    latest_record_for_claim,
    parse_record,
)
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


def pre213_pair_values(pre213_path, path_l, path_r, label):
    """Run the historical extractor's `--pair` mode over one L/R sweep pair.

    The MC path's shape: `run_mc_campaign.run_batch_pair` combined two
    independently-mismatched half-cell sweeps per sample with
    `snm_extract.py --pair`, and the committed MC sample-sets predate #213,
    so every per-sample SNM value is recomputed with the historical
    extractor the same way. Same (values, problems) contract as
    `pre213_values`.
    """
    problems = []
    proc = subprocess.run(
        [sys.executable, str(pre213_path), "--pair", str(path_l), str(path_r), label],
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
    records_rel, _claim, metric, unit = RECORD_CLAIMS[family]
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
        "unit": unit,
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


def _delta_stats(deltas):
    """Reduction of a per-sample |delta| list to the receipt's distribution."""
    if not deltas:
        return None
    ads = sorted(abs(d) for d in deltas)

    def pct(p):
        return ads[min(len(ads) - 1, int(p * (len(ads) - 1)))]

    return {
        "n": len(ads), "max": ads[-1], "mean": sum(ads) / len(ads),
        "p50": pct(0.50), "p95": pct(0.95),
    }


def _seed_identity_errors(request, unit_dir):
    """Re-derive every manifest unit's seed and check the returned bytes.

    The seed lives in the unit's `corner.inc` (`.options seed=N`, written by
    `run_mc_campaign.build_corner_inc`), which deck mode stages into the unit
    directory and the fleet returns, so the *returned* tree is what is
    checked -- not the request's own manifest values.
    """
    meta = request.get("x_gf180_sram_adapter") or {}
    base_seed = meta.get("base_seed")
    if base_seed is None:
        return ["request has no x_gf180_sram_adapter.base_seed to derive seeds from"]
    errors = []
    for m in meta.get("units") or []:
        k = f"{m['kind']}-{m['side']}" if m.get("side") else m["kind"]
        expected = mc.derive_seed(base_seed, m["corner_id"], k, m["index"])
        inc = Path(unit_dir) / m["id"] / "corner.inc"
        if not inc.is_file():
            errors.append(f"{m['id']}: returned unit tree has no corner.inc to read the seed from")
            continue
        got = None
        for line in inc.read_text(errors="replace").splitlines():
            sm = re.search(r"\.options\s+seed=(\d+)", line)
            if sm:
                got = int(sm.group(1))
                break
        if got is None:
            errors.append(f"{m['id']}: corner.inc has no .options seed= line")
        elif got != expected:
            errors.append(
                f"{m['id']}: seed drift -- returned corner.inc seed={got}, "
                f"derive_seed says {expected}"
            )
    return errors


def _pair_values_at(sweep_dir, uid, datafile, pre213, label):
    """(values, problems) for one snm-pair unit's returned L/R sweep files.

    Files missing is a distinct problem string the caller classifies as an
    infrastructure OPEN, not a value mismatch.
    """
    uid_r = ".".join(uid.split(".")[:-1]) + ".R"
    pl = Path(sweep_dir) / uid / datafile
    pr = Path(sweep_dir) / uid_r / datafile
    if not pl.is_file() or not pr.is_file():
        return None, [f"returned sweep pair not found ({pl.name}/{pr.name})"]
    return pre213_pair_values(pre213, pl, pr, label)


def _mm_sweep_value(sweep_dir, cid, kind, idx, datafile, pre213, label, metric):
    """(values, problems) -- the pre-#213 RESULT dict for one pair unit."""
    uid = deck_adapter.mc_unit_id(cid, kind, idx, "L")
    vals, probs = _pair_values_at(sweep_dir, uid, datafile, pre213, label)
    if probs:
        return None, probs
    if metric not in vals:
        return None, [f"no {metric} in extractor output"]
    return vals, []


def compare_mc(family, reduced, request, report, sample_set_path, record_path, *,
               unit_dir=None, sweep_dir=None, pre213=None,
               tolerance_v=TOLERANCE_V_DEFAULT):
    """Compare one family's MC deck-mode grading against its committed sample-set.

    MC counterpart of `compare` (the 2026-11-15 curated acceptance criteria
    for #230's Monte Carlo increment). Asserts, here and independently of
    `mc-reduce`'s own grading (which checks deck bytes and seeds too -- the
    comparator reads the *returned* units rather than trusting the reducer):

    * deck bytes: every report unit's `deck_sha256` present and equal to the
      request's `composed_deck_sha256`;
    * seed identity: every returned unit's `corner.inc` seed equals
      `run_mc_campaign.derive_seed(base_seed, corner, kind[-side], index)`;
    * the reducer's own grading was structurally clean (`coverage_errors`
      empty); `mc-reduce`'s `overall` and any infra failures are carried
      verbatim in the summary -- infra failures on mm/ctrl units break
      parity, infra failures on nc units are the errored draws the
      committed record also excluded, so they are reported per unit with
      reasons and parity-breaks only through the nc errored-count
      comparison, never as parity data points;
    * determinism control: every corner's `ctrl` samples collapse onto one
      value equal to the committed *deterministic* record at that corner
      (exact for the direct family; through the pre-#213 extractor with the
      30 uV gate for the SNM families, whose committed MC values predate
      #213);
    * mismatch batch: every sample compared in index order against the
      committed sample-set's array (exact for the direct family; pre-#213
      on the fleet's own sweeps, gated, for the SNM families), reduced to a
      per-corner max/distribution; an errored or unextractable sample is
      reported `OPEN`, never parity;
    * negative control: usable values in surviving order against the
      committed compacted array **and** equal errored counts (both sides
      compact errored draws, so index alignment is not assumed here).

    Returns the summary dict `--json-out` writes; `overall` is "parity" only
    when all of the above hold.
    """
    if family not in RECORD_CLAIMS:
        raise SystemExit(f"unknown family {family!r}; known: {sorted(RECORD_CLAIMS)}")
    if family not in MC_SAMPLE_SETS:
        raise SystemExit(f"family {family!r} has no committed MC sample-set binding")
    _records_rel, _claim, metric, unit = RECORD_CLAIMS[family]
    mode, key = deck_adapter.MC_FAMILIES[family]
    kind, datafile, label = deck_adapter.parse_mc_mode(mode)
    is_snm = kind in ("snm", "snm-pair")
    if is_snm and (sweep_dir is None or pre213 is None):
        raise SystemExit(
            f"{family} is an SNM family: --sweep-dir and --pre213 are required "
            f"(the committed MC values come from the pre-#213 extractor)"
        )

    meta = request.get("x_gf180_sram_adapter") or {}
    manifest = meta.get("units") or []
    composed = meta.get("composed_deck_sha256")
    base = Path(unit_dir or report.get("outdir") or ".")

    problems = []  # global (request shape / coverage / sha / seeds) failures

    # -- request / report shape -----------------------------------------------
    if meta.get("campaign") != "monte-carlo" or meta.get("family") != family:
        problems.append("request is not a Monte Carlo request for this family")
    if report.get("mode") != "decks" or not isinstance(report.get("units"), list):
        problems.append("report is not a deck-list report (mode != 'decks')")
    report_units = report.get("units") or []
    reported_ids = [u.get("id") for u in report_units]
    manifest_ids = [m["id"] for m in manifest]
    dupes = sorted({i for i in reported_ids if reported_ids.count(i) > 1})
    if dupes:
        problems.append(f"duplicate unit ids in report: {dupes}")
    missing_units = sorted(set(manifest_ids) - set(reported_ids))
    extra_units = sorted(set(reported_ids) - set(manifest_ids))
    if missing_units:
        problems.append(f"units in the request but not the report: {missing_units}")
    if extra_units:
        problems.append(f"units in the report but not the request: {extra_units}")

    # -- deck bytes: present AND equal, for every unit (asserted here independently
    #    of mc-reduce's own deck check; the comparator reads the returned units)
    deck_sha_errors = []
    if not composed:
        problems.append("request has no x_gf180_sram_adapter.composed_deck_sha256 to assert against")
    else:
        for u in report_units:
            sha = u.get("deck_sha256")
            if sha is None:
                deck_sha_errors.append(f"{u.get('id')}: deck_sha256 absent from the report unit")
            elif sha != composed:
                deck_sha_errors.append(f"{u.get('id')}: deck_sha256 differs from the composed deck")
        problems.extend(deck_sha_errors)

    # -- seed identity, against the returned unit tree
    seed_errors = _seed_identity_errors(request, base)
    problems.extend(seed_errors)

    # -- the reducer's own grading ---------------------------------------------
    # coverage_errors is structural and always a problem. Infra failures on
    # mm/ctrl units are parity-breaking (their samples grade errored below);
    # infra failures on nc units are the errored draws the committed record
    # also excluded -- they are reported per corner and parity-breaks only
    # through the nc errored-count comparison, never as parity data points.
    reduce_errors = list(reduced.get("coverage_errors") or [])
    infra = reduced.get("infra_failures") or []
    infra_by_id = {f.get("id"): f.get("reason") for f in infra}
    for uid, reason in sorted(infra_by_id.items()):
        if ".nc." not in uid:
            reduce_errors.append(f"{uid}: {reason}")
    problems.extend(reduce_errors)

    # -- committed sides --------------------------------------------------------
    record = parse_record(Path(record_path))
    sample_set = json.loads(Path(sample_set_path).read_text())
    ss_by_name = {m.get("name"): m for m in sample_set.get("measurements", [])}
    corners_requested = list(meta.get("corners") or [])
    ss_missing = [c for c in corners_requested if f"{key}@{c}" not in ss_by_name]
    if ss_missing:
        problems.append(f"corners missing from the committed sample-set: {ss_missing}")
    n_mm = int(meta.get("n_mismatch") or 0)
    n_ctrl = int(meta.get("n_determinism_control") or 0)
    n_nc = int(meta.get("n_negative_control") or 0)

    batches = reduced.get("batches") or {}
    corners = []
    for cid in corners_requested:
        ss = ss_by_name.get(f"{key}@{cid}")
        batch = batches.get(cid) or {}
        corner = {"id": cid, "status": "parity", "reasons": [],
                  "determinism_control": None, "determinism_control_metrics": {},
                  "mismatch": None, "negative_control": None}

        def fail(status, reason):
            if corner["status"] == "parity":
                corner["status"] = status
            corner["reasons"].append(reason)

        # ---- determinism control ------------------------------------------
        ctrl = batch.get("ctrl", {}).get("samples") or []
        rec_row = record.get(cid)
        ctrl_vals = []
        if len(ctrl) != n_ctrl:
            fail("OPEN", f"ctrl batch has {len(ctrl)} samples, request asked for {n_ctrl}")
        if ss is None:
            fail("MISMATCH", "no committed sample-set measurement for this corner")
        if not isinstance(rec_row, dict):
            fail("MISMATCH", "committed deterministic record has no measured row for this corner")
        ctrl_probs = []
        for idx, results, errs in ctrl:
            if errs:
                ctrl_probs.append(("OPEN", f"ctrl sample {idx} errored: {'; '.join(errs)}"))
                continue
            if is_snm:
                vals, probs = _mm_sweep_value(sweep_dir, cid, "ctrl", idx, datafile,
                                              pre213, label, metric)
                if probs:
                    ctrl_probs.append(("OPEN", f"ctrl sample {idx}: {'; '.join(probs)}"))
                    continue
            else:
                vals = dict(results or {})
            if metric not in vals:
                ctrl_probs.append(("OPEN", f"ctrl sample {idx}: no {metric} in its results"))
                continue
            ctrl_vals.append(vals)
        if ctrl_vals and isinstance(rec_row, dict):
            distinct = sorted({v[metric] for v in ctrl_vals})
            if len(distinct) != 1:
                ctrl_probs.append(
                    ("MISMATCH", f"ctrl samples are not pinned: {len(distinct)} distinct "
                                 f"{metric} values {distinct}")
                )
            for mkey, rec_val in rec_row.items():
                if mkey not in ctrl_vals[0]:
                    ctrl_probs.append(("MISMATCH", f"ctrl samples missing record metric {mkey}"))
                    continue
                deltas = [v[mkey] - rec_val for v in ctrl_vals]
                delta = deltas[0]
                if is_snm:
                    # SNM: the committed MC ctrl values predate #213, so the
                    # recorded metric is gated, the lobes tabulated only.
                    if abs(delta) > tolerance_v + _FLOAT_EPS:
                        verdict = "ABOVE-TOL"
                        ctrl_probs.append(
                            ("OPEN", f"ctrl {mkey}: |delta| {abs(delta):.3e} V exceeds the "
                                     f"{tolerance_v:.0e} V tolerance")
                        )
                    else:
                        verdict = "EXACT" if delta == 0.0 else "WITHIN-TOL"
                elif any(abs(d) > _FLOAT_EPS for d in deltas):
                    verdict = "MISMATCH"
                    ctrl_probs.append(
                        ("MISMATCH", f"ctrl {mkey}: record {rec_val!r} vs ctrl {ctrl_vals[0][mkey]!r}")
                    )
                else:
                    verdict = "EXACT"
                corner["determinism_control_metrics"][mkey] = {
                    "record": rec_val, "fleet": ctrl_vals[0][mkey],
                    "delta": delta, "verdict": verdict,
                }
        corner["determinism_control"] = {
            "n_expected": n_ctrl, "n_ok": len(ctrl_vals),
            "metrics": corner.pop("determinism_control_metrics"),
        }
        for status, p in ctrl_probs:
            fail(status, p)

        # ---- mismatch batch -------------------------------------------------
        mm = batch.get("mm", {}).get("samples") or []
        mm_probs, mm_deltas = [], []
        mm_open = 0
        ss_samples = (ss or {}).get("samples") or []
        ss_errored = int((ss or {}).get("errored") or 0)
        if ss is not None:
            if len(mm) != n_mm:
                mm_probs.append(("OPEN", f"mm batch has {len(mm)} samples, request asked for {n_mm}"))
            if ss_errored != 0:
                mm_probs.append(
                    ("MISMATCH", f"committed sample-set has {ss_errored} errored mm draws -- its "
                                 f"array is compacted, exact index-order comparison is not sound")
                )
            elif len(ss_samples) != n_mm:
                mm_probs.append(
                    ("MISMATCH", f"committed sample-set has {len(ss_samples)} mm values, "
                                 f"request staged {n_mm}")
                )
        mm_by_index = {i: (results, errs) for i, results, errs in mm}
        for i in range(min(n_mm, len(ss_samples)) if ss else 0):
            results, errs = mm_by_index.get(i, (None, ["missing from the reduced report"]))
            if errs:
                mm_open += 1
                mm_probs.append(("OPEN", f"mm sample {i} errored: {'; '.join(errs)}"))
                continue
            if is_snm:
                vals, probs = _mm_sweep_value(sweep_dir, cid, "mm", i, datafile,
                                              pre213, label, metric)
                fleet_v = (vals or {}).get(metric)
                if probs:
                    mm_open += 1
                    mm_probs.append(("OPEN", f"mm sample {i}: {'; '.join(probs)}"))
                    continue
            else:
                if key not in (results or {}):
                    mm_open += 1
                    mm_probs.append(("OPEN", f"mm sample {i}: no {key} in its results"))
                    continue
                fleet_v = results[key]
            committed_v = ss_samples[i]
            delta = fleet_v - committed_v
            mm_deltas.append(delta)
            if is_snm and abs(delta) > tolerance_v + _FLOAT_EPS:
                mm_probs.append(
                    ("OPEN", f"mm sample {i}: |delta| {abs(delta):.3e} V exceeds the "
                             f"{tolerance_v:.0e} V tolerance")
                )
            elif not is_snm and delta != 0.0:
                mm_probs.append(("MISMATCH", f"mm sample {i}: committed {committed_v!r} "
                                             f"vs fleet {fleet_v!r}"))
        corner["mismatch"] = {
            "n_expected": n_mm, "n_compared": len(mm_deltas), "n_open": mm_open,
            "deltas": _delta_stats(mm_deltas),
        }
        for status, p in mm_probs:
            fail(status, p)

        # ---- negative control -------------------------------------------------
        nc_probs = []
        nc_entry = None
        ss_nc = (ss or {}).get("negative_control") or {}
        nc_batch = batch.get("nc", {}).get("samples") or []
        want_key = metric if is_snm else key
        usable = [(i, results) for i, results, errs in nc_batch
                  if not errs and want_key in (results or {})]
        fleet_errored = len(nc_batch) - len(usable)
        nc_deltas, nc_open = [], 0
        if fleet_errored != int(ss_nc.get("errored") or 0):
            nc_probs.append(
                ("MISMATCH", f"negative-control errored-count mismatch: fleet {fleet_errored} "
                             f"vs committed {ss_nc.get('errored')} -- a differing errored set "
                             f"is a finding")
            )
        if len(usable) != len(ss_nc.get("samples") or []):
            nc_probs.append(
                ("MISMATCH", f"usable negative-control count mismatch: fleet {len(usable)} vs "
                             f"committed {len(ss_nc.get('samples') or [])}")
            )
        for (i, results), committed_v in zip(usable, ss_nc.get("samples") or []):
            if is_snm:
                vals, probs = _mm_sweep_value(sweep_dir, cid, "nc", i, datafile,
                                              pre213, label, metric)
                fleet_v = (vals or {}).get(metric)
                if probs:
                    nc_open += 1
                    nc_probs.append(("OPEN", f"nc sample {i}: {'; '.join(probs)}"))
                    continue
            else:
                fleet_v = results[want_key]
            delta = fleet_v - committed_v
            nc_deltas.append(delta)
            if is_snm and abs(delta) > tolerance_v + _FLOAT_EPS:
                nc_probs.append(
                    ("OPEN", f"nc sample {i}: |delta| {abs(delta):.3e} V exceeds the "
                             f"{tolerance_v:.0e} V tolerance")
                )
            elif not is_snm and delta != 0.0:
                nc_probs.append(("MISMATCH", f"nc sample {i}: committed {committed_v!r} "
                                             f"vs fleet {fleet_v!r}"))
        # The nc units that graded OPEN -- engine deaths and extraction
        # errors alike. Reported with reasons, never counted as parity: the
        # committed record excluded the same draws (its own errored count is
        # compared above), so these units appear on neither compared array.
        infra_ids = {uid for uid in infra_by_id if uid.startswith(f"mc.{cid}.nc.")}
        open_units = [{"id": uid, "reason": infra_by_id[uid]} for uid in sorted(infra_ids)]
        for i, _results, errs in nc_batch:
            if not errs:
                continue
            mine = [o for o in open_units
                    if o["id"].endswith(f".nc.{i:05d}.L") or o["id"].endswith(f".nc.{i:05d}.R")]
            for e in errs:
                if e not in [m["reason"] for m in mine]:
                    open_units.append({"id": f"{cid} nc sample {i}", "reason": e})
        nc_entry = {
            "n_expected": n_nc, "n_usable": len(usable), "n_open": nc_open,
            "errored_fleet": fleet_errored, "errored_committed": int(ss_nc.get("errored") or 0),
            "deltas": _delta_stats(nc_deltas), "open_units": open_units,
        }
        corner["negative_control"] = nc_entry
        for status, p in nc_probs:
            fail(status, p)

        corners.append(corner)

    overall = "parity"
    if problems or any(c["status"] != "parity" for c in corners):
        overall = "OPEN" if any(c["status"] == "OPEN" for c in corners) else "MISMATCH"
    return {
        "kind": "mc",
        "family": family,
        "mode": mode,
        "recorded_metric": metric,
        "unit": unit,
        "comparison": "pre213-tolerance" if is_snm else "exact",
        "tolerance_v": tolerance_v,
        "record": str(record_path),
        "sample_set": str(sample_set_path),
        "coverage": {
            "corners": len(corners_requested),
            "units": {"expected": len(manifest_ids), "reported": len(reported_ids)},
            "missing_in_report": missing_units,
            "missing_in_samples": ss_missing,
        },
        "deck_sha256": {"checked": bool(composed), "errors": deck_sha_errors},
        "seed_identity": {"checked": True, "errors": seed_errors},
        "reduce_grading": {
            "coverage_errors": list(reduced.get("coverage_errors") or []),
            "overall": reduced.get("overall"),
            "infra_failures": [
                {"id": f.get("id"), "reason": f.get("reason")}
                for f in reduced.get("infra_failures") or []
            ],
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
        unit = summary["unit"]
        for key, d in sorted(max_deltas.items()):
            gate = " (gated)" if key == metric else ""
            lines.append(f"- `{key}`: {d:.3e} {unit}{gate}")
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
    records_rel, claim, _metric, _unit = RECORD_CLAIMS[family]
    return latest_record_for_claim(REPO_ROOT / "sim" / records_rel, claim)


def default_sample_set_path(family):
    return REPO_ROOT / "sim" / MC_SAMPLE_SETS[family]


def render_mc_markdown(summary):
    """The MC comparison table the receipt embeds, on stdout."""
    family = summary["family"]
    metric = summary["recorded_metric"]
    cov = summary["coverage"]
    sha = summary["deck_sha256"]
    seed = summary["seed_identity"]
    unit = summary["unit"]
    if summary["comparison"] == "pre213-tolerance":
        rule = (
            f"pre-#213 extractor (`e140796^`) `--pair` mode applied to the fleet's own "
            f"per-sample sweep pairs; tolerance {summary['tolerance_v']:.0e} V on the "
            f"recorded metric `{metric}` (lobes tabulated, not gated)"
        )
    else:
        rule = "exact float equality on every sample, in index order"
    lines = [f"## Parity comparison (Monte Carlo): `{family}`", ""]
    lines += [
        f"- Committed sample-set: `{summary['sample_set']}`",
        f"- Determinism-control anchor: `{summary['record']}`",
        f"- Comparison rule: {rule}",
        f"- Coverage: {cov['units']['reported']}/{cov['units']['expected']} units;"
        f" {cov['corners']} corners"
        + (f" -- missing in report: {cov['missing_in_report']}" if cov["missing_in_report"] else "")
        + (f" -- missing in sample-set: {cov['missing_in_samples']}" if cov["missing_in_samples"] else ""),
        f"- Deck bytes asserted: {sha['checked']}"
        + (f" -- errors: {sha['errors']}" if sha["errors"]
           else " (all units present-and-equal)" if sha["checked"] else ""),
        f"- Seed identity asserted: {seed['checked']}"
        + (f" -- errors: {len(seed['errors'])}" if seed["errors"] else " (all units derive_seed-equal)"),
        "",
    ]
    for corner in summary["corners"]:
        lines.append(f"### Corner `{corner['id']}` -- {corner['status']}")
        lines.append("")
        ctrl = corner["determinism_control"] or {}
        lines.append(f"- Determinism control: {ctrl.get('n_ok', 0)}/{ctrl.get('n_expected', 0)} usable;"
                     " anchored against the committed deterministic record:")
        lines += ["", "  | Metric | Record | Ctrl | Delta | Verdict |",
                  "  |---|---|---|---|---|"]
        for mkey, m in (ctrl.get("metrics") or {}).items():
            lines.append(f"  | {mkey} | {m['record']!r} | {m['fleet']!r} | {m['delta']:.3e} | {m['verdict']} |")
        mm = corner["mismatch"] or {}
        lines.append(f"- Mismatch batch: {mm.get('n_compared', 0)}/{mm.get('n_expected', 0)} compared,"
                     f" {mm.get('n_open', 0)} OPEN")
        dstats = mm.get("deltas")
        if dstats:
            lines.append(
                f"  - per-sample |delta| distribution: n={dstats['n']}, max={dstats['max']:.3e} {unit},"
                f" mean={dstats['mean']:.3e} {unit}, p50={dstats['p50']:.3e} {unit}, p95={dstats['p95']:.3e} {unit}"
            )
        nc = corner["negative_control"] or {}
        if nc:
            lines.append(
                f"- Negative control: {nc.get('n_usable', 0)} usable vs committed "
                f"{nc.get('errored_committed', 0)} errored (fleet errored "
                f"{nc.get('errored_fleet', 0)}); compared in surviving order"
            )
            nstats = nc.get("deltas")
            if nstats:
                lines.append(
                    f"  - per-sample |delta| distribution: n={nstats['n']}, max={nstats['max']:.3e} {unit},"
                    f" mean={nstats['mean']:.3e} {unit}, p50={nstats['p50']:.3e} {unit}, p95={nstats['p95']:.3e} {unit}"
                )
            for o in nc.get("open_units") or []:
                lines.append(f"  - OPEN unit `{o['id']}`: {o['reason']} (never counted as parity)")
        if corner["reasons"]:
            lines += ["", "  **Non-parity findings**:"]
            lines += [f"  - ({corner['status']}) {r}" for r in corner["reasons"]]
        lines.append("")
    lines.append(f"**Overall: {summary['overall']}**"
                 f" -- {sum(1 for c in summary['corners'] if c['status'] == 'parity')}"
                 f"/{len(summary['corners'])} corners at parity.")
    if summary["problems"]:
        lines += ["", "**Comparison-level problems**:", *(f"- {p}" for p in summary["problems"])]
    return "\n".join(lines) + "\n"


def main_mc(argv) -> int:
    ap = argparse.ArgumentParser(
        description="MC mode: compare an mc-reduce grading against the committed MC sample-set")
    ap.add_argument("family", help="one of: %s" % ", ".join(sorted(MC_SAMPLE_SETS)))
    ap.add_argument("reduced", help="deck_adapter.py mc-reduce --json-out file")
    ap.add_argument("--request", required=True,
                    help="the request.json mc-build wrote (manifest, seeds, composed deck sha256)")
    ap.add_argument("--report", required=True,
                    help="klt sim's deck report (units[].deck_sha256 -- the comparator's "
                         "deck-bytes evidence, asserted independently of mc-reduce's own check)")
    ap.add_argument("--samples", help="committed MC sample-set (default: the family's binding "
                                      "in render_signoff_table.MC_SAMPLE_SETS)")
    ap.add_argument("--record", help="deterministic record for the ctrl anchor "
                                     "(default: family's latest under sim/*/records)")
    ap.add_argument("--unit-dir", help="returned unit tree root (<unit-id>/corner.inc, sweeps); "
                                       "default: the report's outdir")
    ap.add_argument("--sweep-dir", help="directory holding <unit-id>/<datafile> (SNM families)")
    ap.add_argument("--pre213", help="path to the pre-#213 snm_extract.py (SNM families)")
    ap.add_argument("--tolerance-v", type=float, default=TOLERANCE_V_DEFAULT,
                    help="SNM recorded-metric tolerance in volts (default 3e-05 = 30 uV)")
    ap.add_argument("--json-out", help="write the machine-readable summary here")
    args = ap.parse_args(argv)

    reduced = json.loads(Path(args.reduced).read_text())
    if reduced.get("family") != args.family:
        print(f"reduced.json is for family {reduced.get('family')!r}, not {args.family!r}",
              file=sys.stderr)
        return 2
    record_path = Path(args.record) if args.record else default_record_path(args.family)
    samples_path = Path(args.samples) if args.samples else default_sample_set_path(args.family)
    request = json.loads(Path(args.request).read_text())
    report = json.loads(Path(args.report).read_text())

    summary = compare_mc(
        args.family, reduced, request, report, samples_path, record_path,
        unit_dir=args.unit_dir, sweep_dir=args.sweep_dir, pre213=args.pre213,
        tolerance_v=args.tolerance_v,
    )
    for field in ("record", "sample_set"):
        try:
            summary[field] = str(Path(summary[field]).relative_to(REPO_ROOT))
        except ValueError:
            pass
    sys.stdout.write(render_mc_markdown(summary))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, indent=1) + "\n")
    return 0 if summary["overall"] == "parity" else 1


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "mc":
        return main_mc(argv[1:])
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
    try:
        summary["record"] = str(record_path.relative_to(REPO_ROOT))
    except ValueError:
        summary["record"] = str(record_path)
    sys.stdout.write(render_markdown(summary))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, indent=1) + "\n")
    return 0 if summary["overall"] == "parity" else 1


if __name__ == "__main__":
    raise SystemExit(main())
