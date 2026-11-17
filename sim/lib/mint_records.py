#!/usr/bin/env python3
"""sim/lib/mint_records.py -- mint append-only evidence records from a
`klt sim` deck-mode run.

The #230 cutover retired the two launchers that minted this repo's evidence
(`run_corner_sweep.sh` for the deterministic 27-corner records, the
`run_mc_campaign.py` pool for the Monte Carlo records) and replaced the *run*
path with `sim/lib/deck_adapter.py` + `klt sim`. The minting the cutover
left undone is now split between two modules: `sim/lib/mint_corner_records.py`
(landed from the #437 deck port while #272 was in flight) mints the
`direct`-mode pex-write-margin legs (#95) with their per-family staged-DUT
provenance, while this module mints the #272 reference families -- the SNM
families, the `direct` reference families, and the whole Monte Carlo path.
The `corner` CLI below mints exactly the families FAMILY_CLAIMS names; the
families outside it are `mint_corner_records.py`'s domain, not missing here.
#272's re-qualification of the reference records under the `f6eeac7` PDK pin
(`sim/lib/pdk_pin.txt`) is this module's first customer: every new record
carries a **Supersedes** line naming the record it replaces and the retired
records stay committed, append-only, untouched (sim/README.md "Append-only
rule").

It writes exactly the artifacts the retired launchers wrote, into the same
directory shapes sim/README.md documents:

* `corner` -- one deterministic record per family:
    `sim/<exp>/netlist-snapshots/<record-id>.spice`,
    `sim/<exp>/corners/<record-id>/<corner-id>.log`,
    `sim/<exp>/records/<record-id>.md`.
  Inputs: the `deck_adapter.py build` request, the `deck_adapter.py reduce`
  --json-out grading, the deck report, and the collected unit tree (the
  `klt sim -o` directory holding each unit's stdout/stderr and SNM sweep
  data). Nothing is re-simulated: the grading is `reduce`'s, the raw engine
  bytes are the fleet's own.

* `mc` -- one Monte Carlo record per family plus the artifact set
  sim/README.md's MC convention requires:
    `sim/<exp>/mc/samples/<record-id>.json` (the `klt yield` sample-set
    document, rebuilt from `mc-reduce`'s measurements),
    `sim/<exp>/mc/yield-reports/<record-id>.{json,txt}` (`klt yield`, run
    from the reports directory with a report-relative samples path -- the
    invocation shape the #109/#160 provenance rules pin),
    `sim/<exp>/mc/raw-logs/<record-id>/<corner-id>.log` + `summary.json`
    (per-draw seed + value, or the reason a draw produced none),
    `sim/<exp>/mc/records/<record-id>.md`.
  Inputs: the `deck_adapter.py mc-build` request and the `mc-reduce`
  --json-out grading.

Provenance hygiene (sim/README.md, issue #109): every path this module
writes into a record or JSON document is repo-relative; the PDK is recorded
by identity (variant + resolved open_pdks version from `sim/lib/pdk_env.sh`),
never by install location. `--supersedes` is written verbatim into the
record's Supersedes field and is how #272's records point at the `c6d73a3`
records they replace.

Deterministic-record fields the retired launcher did not have (and #272's
records need): a **PDK** identity line and a **Run** line carrying the fleet
`environment.remote` job id and the pinned run-directory `.spiceinit` the
units executed under (issue #338; spec/environment-pin-decision.md) -- the
acceptance test for the re-qualification reads both from the record.

Usage:
    python3 sim/lib/mint_records.py corner <family> \
        --request <stage>/<family>/request.json \
        --reduced <out>/<family>-reduced.json \
        --report <out>/request-<i>/report.json \
        --unit-dir <out>/request-<i> \
        --supersedes "<record-id> (<reason>)"

    python3 sim/lib/mint_records.py mc <family> \
        --request <scratch>/<family>.json \
        --reduced <scratch>/<family>-reduced.json \
        --supersedes "<record-id> (<reason>)"

`--record-id` overrides the freshly minted `<YYYYMMDD>-<HHMMSS>-<sha>` id
(tests use this; live runs should not).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Single owners, never re-derived: the ratified matrix (#331), the repo-root
# helper (#337), the deck composer / SNM grading the fleet run itself used
# (#230), and the MC identity library (derive_seed / RESULT grammar) the
# cutover kept alive.
import deck_adapter  # noqa: E402 (path-injected sibling import)
from corner_matrix import PROCESSES, TEMPS, VDDS  # noqa: E402
from repo_root import find_repo_root  # noqa: E402

REPO_ROOT = find_repo_root(Path(__file__))

AUTHOR = "agent-builder"

# family -> (experiment dir under sim/, Claim text). The Claim text is the
# exact string the current records carry (RECORD_CLAIMS in
# render_signoff_table.py matches its substring against whatever minting
# writes, so a reword here would silently retarget the rollups).
FAMILY_CLAIMS = {
    "read-snm": ("read-snm", "spec/sram.md Characterization -- read SNM"),
    "hold-snm": ("hold-snm", "spec/sram.md Characterization -- hold SNM"),
    "write-margin": ("write-margin", "spec/sram.md Characterization -- write margin (write trip voltage)"),
    "read-access": ("access-time", "spec/sram.md Characterization -- read access time (bit-line differential proxy)"),
    "write-access": ("access-time", "spec/sram.md Characterization -- write access time"),
}

MC_CLAIMS = {
    "read-snm": "spec/sram.md Characterization -- read SNM (Monte Carlo device mismatch, combined with the ratified 9-corner PVT matrix)",
    "hold-snm": "spec/sram.md Characterization -- hold SNM (Monte Carlo device mismatch, combined with the ratified 9-corner PVT matrix)",
    "write-margin": "spec/sram.md Characterization -- write margin, as write trip voltage (Monte Carlo device mismatch, combined with the ratified 9-corner PVT matrix)",
}

SPEC_LIMITS_SOURCE = (
    "spec/sram.md 'Characterization' -- read SNM / hold SNM / write margin "
    "must be strictly positive at every corner"
)


def git_short_sha() -> str:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip() or "nogit"


def pdk_identity() -> dict[str, str]:
    """Resolve the PDK by identity via sim/lib/pdk_env.sh (never a path).

    The env file fails non-zero when the resolved install is not the pin, so
    a drifted tree cannot be minted into a record silently.
    """
    out = subprocess.run(
        ["bash", "-c",
         'source sim/lib/pdk_env.sh >/dev/null 2>&1; '
         'printf "%s\\t%s\\t%s\\t%s" "$GF180_VARIANT_DIR" "$GF180_PDK_VERSION" '
         '"$GF180_DESIGN_INC" "$GF180_MODEL_FILE"'],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise SystemExit(
            f"pdk_env.sh failed ({out.returncode}): {out.stderr.strip()}"
        )
    variant_dir, version, design_inc, model_file = out.stdout.split("\t")
    if not variant_dir or not version:
        raise SystemExit("pdk_env.sh resolved no PDK identity")
    model_rel = os.path.relpath(model_file, variant_dir)
    return {
        "variant": Path(variant_dir).name,
        "version": version,
        "design_inc_rel": os.path.relpath(design_inc, variant_dir),
        "model_file_rel": model_rel,
    }


def klt_version(klt: str | None = None) -> str:
    klt = klt or os.environ.get("KLT", "klt")
    out = subprocess.run([klt, "--version"], capture_output=True, text=True, check=False)
    return out.stdout.strip() or "unknown"


def mint_record_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{now:%Y%m%d-%H%M%S}-{git_short_sha()}"


def _rel(path: Path, repo_root: Path = REPO_ROOT) -> str:
    return str(Path(path).resolve().relative_to(Path(repo_root).resolve()))


def _corner_axes(cid: str) -> tuple[str, str, str]:
    """('ff_-40c_2.97v') -> ('ff', '-40', '2.97')."""
    process, rest = cid.split("_", 1)
    temp, vdd = rest.split("c_")
    return process, temp, vdd[:-1]


def _load(json_path: Path) -> dict:
    return json.loads(Path(json_path).read_text(encoding="utf-8"))


def _check_request_pair(family: str, request: dict, reduced: dict) -> None:
    """Fail closed before anything is written: the grading must be this
    request's, the decks must be the composed bytes, and the coverage must
    be exact (exit 0 is never a PASS -- sim/README.md)."""
    meta = request.get("x_gf180_sram_adapter") or {}
    if meta.get("family") != family:
        raise SystemExit(f"request is for family {meta.get('family')!r}, not {family!r}")
    if reduced.get("family") != family:
        raise SystemExit(f"reduced grading is for family {reduced.get('family')!r}, not {family!r}")
    sha = meta.get("composed_deck_sha256")
    if reduced.get("expected_deck_sha256") != sha:
        raise SystemExit("reduced grading does not pin this request's composed deck sha256")
    if reduced.get("coverage_errors"):
        raise SystemExit(f"coverage errors in grading: {reduced['coverage_errors']}")


# --------------------------------------------------------------------------
# Deterministic corner records
# --------------------------------------------------------------------------


def _corner_log_text(unit: dict, unit_dir: Path, cid: str, mode: str) -> str:
    """One corner's log, byte-shaped like run_corner_sweep.sh wrote it:
    the engine's own stdout/stderr, then the two header lines, then (SNM
    families) the extractor's output over the unit's own sweep data."""
    log = ""
    for field, default in (("stdout", f"{cid}/stdout.bin"), ("stderr", f"{cid}/stderr.bin")):
        p = unit_dir / unit.get(field, default)
        if p.is_file():
            log += p.read_bytes().decode("utf-8", errors="replace")
    process, temp, vdd = _corner_axes(cid)
    log += f"=== corner: {cid} (process={process} temp={temp}C vdd={vdd}V) ===\n"
    exit_code = unit.get("exit_code")
    log += f"=== ngspice exit status: {'none' if exit_code is None else exit_code} ===\n"
    kind, datafile, label = deck_adapter.parse_mode(mode)
    if kind == "snm":
        data = unit_dir / cid / datafile
        if data.is_file():
            log += deck_adapter._snm_lines(data, label)
        else:
            log += f"RESULT-ERROR: {label} -- expected data file {datafile} not produced\n"
    return log


def mint_corner(family: str, request_path: Path, reduced_path: Path, report_path: Path,
                unit_dir: Path, supersedes: str, record_id: str | None = None,
                repo_root: Path = REPO_ROOT, now: datetime | None = None) -> Path:
    request = _load(request_path)
    reduced = _load(reduced_path)
    report = _load(report_path)
    _check_request_pair(family, request, reduced)

    exp_dir, claim = FAMILY_CLAIMS[family]
    _exp, tb_name, mode, _staged = deck_adapter.FAMILIES[family]
    meta = request["x_gf180_sram_adapter"]
    pdk = pdk_identity()

    # The snapshot is the composed deck -- the bytes that actually ran --
    # re-composed from the committed testbench and checked against the
    # sha256 the request recorded (and the reducer asserted per unit).
    tb_path = repo_root / "sim" / exp_dir / "testbench" / tb_name
    deck_bytes = deck_adapter.compose_deck(tb_path.read_text(encoding="utf-8")).encode("utf-8")
    if deck_adapter._sha256(deck_bytes) != meta["composed_deck_sha256"]:
        raise SystemExit("committed testbench no longer composes to the request's deck bytes")

    rid = record_id or mint_record_id(now)
    ts = f"{(now or datetime.now(timezone.utc)):%Y-%m-%dT%H:%M:%SZ}"
    root = Path(repo_root)
    snapshot_path = root / "sim" / exp_dir / "netlist-snapshots" / f"{rid}.spice"
    corners_dir = root / "sim" / exp_dir / "corners" / rid
    records_dir = root / "sim" / exp_dir / "records"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    corners_dir.mkdir(parents=True, exist_ok=True)
    records_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(deck_bytes)

    units_by_id = {u.get("id"): u for u in report.get("units", [])}
    result_rows = []
    overall_open = False
    for corner in reduced["corners"]:
        cid = corner["id"]
        unit = units_by_id.get(cid)
        if unit is None:
            raise SystemExit(f"corner {cid} graded but absent from the deck report")
        (corners_dir / f"{cid}.log").write_text(
            _corner_log_text(unit, Path(unit_dir), cid, mode), encoding="utf-8"
        )
        if corner["status"] != "recorded":
            overall_open = True
            reasons = "; ".join(corner["reasons"]) or "no RESULT line captured"
            result_rows.append(f"  - **{cid}**: OPEN -- {reasons}")
        else:
            joined = ";".join(l.strip() for l in corner["result_lines"]) + ";"
            result_rows.append(f"  - **{cid}**: {joined}")

    remote = (report.get("environment") or {}).get("remote") or {}
    job_id = remote.get("job_id") or "unknown"
    engine_version = (report.get("environment") or {}).get("engine_version") or "unknown"
    n = len(reduced["corners"])
    if overall_open:
        overall = (
            f"  - **Overall: OPEN** -- at least one corner did not produce a valid measured result "
            f"(see per-corner notes above); per spec/sram.md's Signoff definition this corner is "
            f"recorded as an open result, not dropped from the corner set."
        )
    else:
        overall = (
            f"  - **Overall: recorded** -- all {n} corners produced a measured result; see "
            f"sim/README.md for how to interpret sign-off against spec/sram.md's positive-margin "
            f"requirement."
        )

    spiceinit_sha = meta.get("spiceinit_sha256", "unknown")
    lines = [
        f"# Record {rid}",
        "",
        f"- **Record ID**: {rid}",
        f"- **Claim**: {claim}",
        f"- **Netlist provenance**: schematic (`{_rel(tb_path, root)}`, DUT per "
        f"`design/netlist/bitcell_6t.spice` at `{git_short_sha()}`)",
        f"- **PDK**: `{pdk['variant']}`, open_pdks `{pdk['version']}` (issue #173 pin, `sim/lib/pdk_pin.txt`)",
        f"- **Run**: `klt sim` deck mode on the batch fleet (#230 cutover path), job `{job_id}` "
        f"(ngspice {engine_version}, `{remote.get('ami_id', 'unknown')}`); pinned run-directory "
        f"`.spiceinit` staged per unit (issue #338, sha256 `{spiceinit_sha}`; "
        f"spec/environment-pin-decision.md)",
        "- **Corner matrix run**:",
        f"  - Process: {' '.join(PROCESSES)}",
        f"  - Temperature: {' '.join(TEMPS)} C",
        f"  - Supply: {' '.join(VDDS)} V",
        f"  - ({n} corner points total -- full process x temp x supply matrix, per spec/sram.md's "
        f"ratified corner set)",
        "- **Statistical convention**: N/A (corner-matrix claim, not a distribution claim)",
        "- **Result**:",
        *result_rows,
        overall,
        "- **Links**:",
        f"  - Testbench: `{_rel(tb_path, root)}`",
        f"  - Netlist snapshot: `{_rel(snapshot_path, root)}`",
        f"  - Raw logs: `{_rel(corners_dir, root)}/`",
        f"- **Timestamp / author**: {ts}, {AUTHOR}",
    ]
    if supersedes:
        lines.append(f"- **Supersedes**: {supersedes}")
    else:
        lines.append("- **Supersedes**: (none -- first record for this claim)")

    record_path = records_dir / f"{rid}.md"
    if record_path.exists():
        raise SystemExit(
            f"record already exists: {record_path} -- record ids are "
            "<UTC-timestamp>-<sha>; re-run (or pass --record-id) so two "
            "records minted in the same second do not collide"
        )
    record_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote snapshot: {snapshot_path}")
    print(f"wrote {n} corner logs under {corners_dir}")
    print(f"wrote record: {record_path}")
    print(f"record-id: {rid}")
    return record_path


# --------------------------------------------------------------------------
# Monte Carlo records
# --------------------------------------------------------------------------


def _fmt(value, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def build_sample_doc(family: str, request: dict, reduced: dict, rid: str,
                     nc_description: str, klt_ver: str, sha: str, pdk: dict,
                     key: str | None = None) -> dict:
    """The `klt yield` sample-set document, rebuilt from `mc-reduce`'s
    measurements -- the same shape the retired pool's main() wrote."""
    meta = request["x_gf180_sram_adapter"]
    exp_dir, _ = FAMILY_CLAIMS[family]
    tb_rel = meta["testbench"]  # already sim/-relative (FAMILIES carries the prefix)
    _mode, default_key = deck_adapter.MC_FAMILIES[family]
    key = key or reduced.get("key") or default_key
    provenance = {
        "record_id": rid,
        "claim": MC_CLAIMS[family],
        "testbench": tb_rel,
        "key": key,
        "seed": meta["base_seed"],
        "n_mismatch": meta["n_mismatch"],
        "n_determinism_control": meta["n_determinism_control"],
        "n_negative_control": meta["n_negative_control"],
        "negative_control_description": nc_description,
        "corners": meta["corners"],
        "spec_limits": {"min": 0.0, "source": SPEC_LIMITS_SOURCE},
        "mismatch": {
            "switch": "sw_stat_mismatch",
            "model_file": pdk["model_file_rel"],
            "mechanism": (
                "delvto='mis_vth*sw_stat_mismatch' / mulu0='1-mis_k*sw_stat_mismatch' "
                "per nfet_03v3/pfet_03v3 instance"
            ),
            "seeding": ".options seed=<derived>, one independent ngspice invocation per sample",
            "seed_derivation": (
                "sha256(base_seed:corner_id:kind:sample_index), truncated to a positive "
                "31-bit integer"
            ),
        },
        "pdk": {
            "variant": pdk["variant"],
            "version": pdk["version"],
            "source": "sim/lib/pdk_env.sh resolution (GF180_PDK_PATH / PDK_ROOT+PDK / standard install prefix)",
        },
        "klt_version": klt_ver,
        "git_sha": sha,
        "engine_environment": (
            "pinned run-directory .spiceinit staged per deck unit (issue #338; "
            "spec/environment-pin-decision.md)"
        ),
    }
    return {"measurements": reduced["measurements"], "provenance": provenance}


def run_klt_yield(klt: str, samples_path: Path, reports_dir: Path):
    """`klt yield` (JSON then text) from the reports directory with a
    report-relative samples path -- the #109/#160 invocation shape."""

    samples_rel = os.path.relpath(samples_path, reports_dir)
    procs = []
    for fmt in ("json", "text"):
        proc = subprocess.run(
            [klt, "yield", str(samples_rel), "--format", fmt],
            cwd=reports_dir, capture_output=True, text=True, check=False,
        )
        procs.append(proc)
    return procs[0], procs[1]


def render_mc_record(summary: dict, json_report_text: str, text_report_text: str,
                     supersedes: str, minted: str, nc_infra: list | None = None) -> str:
    """The MC record, field-for-field the retired pool's render_record()
    output (same field set sim/README.md documents), with the Supersedes
    line parameterized and the deck-mode Reproduce block this generator
    actually ran."""
    try:
        report = json.loads(json_report_text)
    except (ValueError, TypeError):
        report = {}
    payload = report.get("payload") or report
    by_name = {m.get("name"): m for m in (payload.get("measurements") or [])}

    rows = []
    for corner in summary["corners"]:
        name = f"{summary['key']}@{corner['corner_id']}"
        m = by_name.get(name, {})
        emp = ((m.get("yield") or {}).get("empirical") or {})
        ci = emp.get("confidence_interval") or {}
        cap = m.get("capability") or {}
        dist = m.get("distribution") or {}
        size = m.get("sample_size") or {}
        nc = m.get("negative_control") or {}
        rows.append(
            "| `{cid}` | {n} | {errored} | {mean} | {sd} | {yl} | {cpk} | {sts} | {verdict} | {ncv} |".format(
                cid=corner["corner_id"],
                n=corner["mm_n_ok"],
                errored=corner["mm_n_errored"],
                mean=_fmt(dist.get("mean")),
                sd=_fmt(dist.get("stddev")),
                yl=_fmt(ci.get("low")),
                cpk=_fmt(cap.get("cpk")),
                sts=_fmt(cap.get("sigma_to_spec")),
                verdict=size.get("verdict", "n/a"),
                ncv=nc.get("verdict", "none declared"),
            )
        )

    det_rows = [
        "| `{cid}` | {ok} | {errored} | {values} | {pinned} |".format(
            cid=c["corner_id"],
            ok=c["det_n_ok"],
            errored=c["det_n_errored"],
            values=", ".join(_fmt(v) for v in c["det_distinct_values"]) or "(none)",
            pinned="PINNED" if c["det_pinned"] else "**NOT PINNED**",
        )
        for c in summary["corners"]
    ]

    prov = summary["provenance"]
    overall = payload.get("status", "n/a")
    warnings = payload.get("warnings") or []
    meta = summary["request_meta"]

    lines = [
        f"# MC/yield record `{summary['record_id']}`",
        "",
        f"- **Record ID**: `{summary['record_id']}`",
        "- **Kind**: Monte Carlo mismatch campaign + `klt yield` report (statistical evidence, "
        "klayout-tools `docs/design-evidence-tiers.md` item 6)",
        f"- **Claim**: {prov['claim']}",
        f"- **Testbench**: `{prov['testbench']}`",
        "- **Netlist provenance**: schematic (this repo has not yet produced an extracted netlist; "
        "a post-layout re-run would record `extracted` here and reference this record via "
        "**Supersedes**)",
        f"- **Corner matrix run**: {len(summary['corners'])} corner points from `spec/sram.md`'s "
        "ratified process x temperature x voltage set "
        f"({', '.join('`' + c['corner_id'] + '`' for c in summary['corners'])}) -- a deliberate "
        "Monte Carlo subset, chosen per `sim/README.md` \"Which corners, and why not all of them\". "
        "MC results **combine with**, and never replace, the deterministic corner records under "
        f"`sim/{summary['experiment']}/records/`, which sweep that set exhaustively.",
        f"- **Statistical convention**: Monte Carlo, per-instance device mismatch only "
        f"(`{prov['mismatch']['switch']}=1`; `{prov['mismatch']['mechanism']}`). "
        "Global/process variation is carried by the corner axis, not resampled -- so each corner "
        "is its own population and no estimate is pooled across corners.",
        f"- **Seed**: `{prov['seed']}` (base). Per-sample seed = {prov['mismatch']['seed_derivation']}; "
        f"delivered to ngspice as `{prov['mismatch']['seeding']}`.",
        f"- **Sample count**: {prov['n_mismatch']} mismatch samples per corner, "
        f"{prov['n_determinism_control']} determinism-control samples per corner, "
        f"{prov['n_negative_control']} negative-control samples per corner.",
        f"- **Spec limits**: `min = {prov['spec_limits']['min']}` V -- {prov['spec_limits']['source']}. "
        "No `target_yield` is declared: `spec/sram.md` ratifies no yield target for these rows "
        "(that is exactly the open operator decision tracked as issue #20), and this harness does "
        "not invent one. The estimates below are therefore *reported* against the spec's own "
        "`> 0` limit, with Cpk / sigma-to-spec as the quantitative margin statement.",
        f"- **PDK**: `{prov['pdk']['variant']}`, open_pdks `{prov['pdk']['version']}` (issue #173 "
        f"pin, `sim/lib/pdk_pin.txt`) -- **`klt`**: `{prov['klt_version']}` -- **git**: `{summary['git_sha']}`",
        f"- **Engine environment**: {prov['engine_environment']}; `.spiceinit` sha256 "
        f"`{meta.get('spiceinit_sha256', 'unknown')}`",        f"- **`klt yield` overall status**: `{overall}` (exit code {summary['klt_yield_exit_code']})",
        f"- **Timestamp / author**: {summary['timestamp']} / {summary['author']}",
    ]
    lines.append(
        f"- **Supersedes**: {supersedes}" if supersedes
        else "- **Supersedes**: (none -- first record for this claim)"
    )
    if nc_infra:
        lines.append(
            f"- **Transport grading note**: {len(nc_infra)} known-bad negative-control draw(s) "
            "aborted the engine before producing their declared sweep output (reducer: `declared "
            "outputs missing`); each is accounted as one of the errored negative-control draws "
            "counted above -- the same draws the superseded record's own negative-control errored "
            "set contains. No mismatch or determinism-control draw is implicated."
        )
    lines += [
        "",
        "## Per-corner result (verbatim from the `klt yield` JSON report)",
        "",
        "| Corner | N | errored | mean (V) | stddev (V) | empirical yield, 95% lower bound "
        "| Cpk | sigma-to-spec | sample-size verdict | negative control |",
        "|---|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "`errored` counts draws that produced no usable measurement (for the SNM fixtures: a draw "
        "whose butterfly was not bistable, so no square exists to measure). `klt yield` excludes "
        "them from every statistic, so a record with a non-zero `errored` column states a yield "
        "estimate *conditioned on a measurable draw* -- read the errored count alongside it, "
        "never the yield alone.",
        "",
        "## Determinism control (mismatch off)",
        "",
        "With `sw_stat_mismatch=0` the campaign must reproduce, exactly and identically for every "
        "draw, the number the deterministic corner sweep already recorded for the same corner. "
        "This is what ties the MC evidence to the ratified 27-corner evidence rather than leaving "
        "it a parallel, unanchored claim.",
        "",
        "| Corner | N | errored | distinct value(s) (V) | verdict |",
        "|---|---|---|---|---|",
        *det_rows,
        "",
        "## Negative control",
        "",
        (
            f"Deliberate defect: **{prov['negative_control_description']}**, drawn with its own "
            "independent, reproducibly-derived seeds and analysed by `klt yield` against the "
            "*same* spec limits as the nominal measurement. A `detected` verdict means the "
            "control's empirical yield is lower **and** its exact (Clopper-Pearson) confidence "
            "interval does not overlap the nominal's -- i.e. these statistics demonstrably do "
            "detect a degraded design, rather than being assumed to."
            if prov["n_negative_control"] > 0
            else "None declared for this campaign -- `klt yield` flags that with a run-level "
                 "warning (see below)."
        ),
        "",
        "## `klt yield` run-level warnings",
        "",
        *([f"- {w}" for w in warnings] or ["- (none)"]),
        "",
        "## Links",
        "",
        f"- Sample-set document: [`{summary['samples_path']}`](../samples/{summary['record_id']}.json)",
        f"- `klt yield` JSON report: [`{summary['json_report_path']}`](../yield-reports/{summary['record_id']}.json)",
        f"- `klt yield` text report: [`{summary['text_report_path']}`](../yield-reports/{summary['record_id']}.txt)",
        f"- Per-sample raw logs: [`{summary['raw_logs_dir']}`](../raw-logs/{summary['record_id']})",
        f"- Deterministic 27-corner records for the same claim: `sim/{summary['experiment']}/records/`",
        "",
        "## Reproduce",
        "",
        "```bash",
        "# deck-mode path (#230 cutover); the retired run_mc_campaign.py CLI is a tombstone",
        f"python3 sim/lib/deck_adapter.py mc-build {summary['experiment']} \\",
        *[f"  --corner {':'.join(_corner_axes(c))} \\" for c in meta["corners"]],
        f"  --n {prov['n_mismatch']} --n-control {prov['n_determinism_control']} "
        f"--n-nc {prov['n_negative_control']} \\",
        f"  --nc-mismatch-scale {meta['nc_mismatch_scale']:g}"
        + (f" --nc-vdd {meta['nc_vdd']}" if meta.get("nc_vdd") is not None else "")
        + " \\",
        f"  --seed {prov['seed']} \\",
        f"  --stage-dir <scratch>/{summary['experiment']} "
        f"--request-out <scratch>/{summary['experiment']}.json",
        "# then: klt sim --batch-set <scratch>/<family>.json ... --wait-for-capacity 600",
        "# and:  python3 sim/lib/deck_adapter.py mc-reduce <family> <request> <report> ...",
        "```",
        "",
        f"Minted by `sim/lib/mint_records.py` ({minted}); grading by "
        "`deck_adapter.py mc-reduce` (deck bytes and per-unit seeds asserted by the reducer; "
        "exit 0 is never a PASS).",
        "",
        "## `klt yield` text report (verbatim)",
        "",
        "```",
        text_report_text.rstrip("\n"),
        "```",
        "",
    ]
    return "\n".join(lines)


def _check_infra_accounted(request: dict, reduced: dict) -> list[dict]:
    """Classify every infra failure: (corner, kind, sample index) must land in
    a batch sample whose errors list is non-empty -- a counted errored draw,
    never a silently dropped one -- and the kind must be 'nc' only."""
    if not reduced.get("infra_failures"):
        return []
    by_id = {}
    for cid, kinds in reduced["batches"].items():
        for kind, batch in kinds.items():
            for i, _results, errors in batch["samples"]:
                by_id[(cid, kind, i)] = bool(errors)
    unaccounted = []
    for f in reduced["infra_failures"]:
        uid = f.get("id", "")
        parts = uid.split(".")
        if len(parts) < 4:
            unaccounted.append(f)
            continue
        if parts[-1] in ("L", "R"):  # snm-pair unit: mc.<corner>.<kind>.<idx>.<side>
            cid, kind, idx = f"{parts[1]}.{parts[2]}", parts[3], int(parts[4])
        else:  # direct unit: mc.<corner>.<kind>.<idx>
            cid, kind, idx = f"{parts[1]}.{parts[2]}", parts[3], int(parts[4])
        if kind != "nc" or not by_id.get((cid, kind, idx), False):
            unaccounted.append(f)
    if unaccounted:
        raise SystemExit(
            "infra failures not accounted as counted negative-control errored "
            f"draws: {unaccounted}"
        )
    return reduced["infra_failures"]

def mint_mc(family: str, request_path: Path, reduced_path: Path, supersedes: str,
            record_id: str | None = None, repo_root: Path = REPO_ROOT,
            now: datetime | None = None, klt_bin: str | None = None) -> Path:
    request = _load(request_path)
    reduced = _load(reduced_path)
    meta = request.get("x_gf180_sram_adapter") or {}
    if meta.get("campaign") != "monte-carlo" or meta.get("family") != family:
        raise SystemExit(f"request is not a Monte Carlo request for {family!r}")
    if reduced.get("family") != family:
        raise SystemExit(f"reduced grading is for family {reduced.get('family')!r}, not {family!r}")
    if reduced.get("coverage_errors"):
        raise SystemExit(f"coverage errors in grading: {reduced['coverage_errors']}")
    # Infra failures are not automatically fatal: a known-bad negative-control
    # draw can hard-abort the engine before its declared output exists (the
    # committed campaigns show exactly these draws, e.g. hold-snm nc 11 R at
    # ff_25c_3.30v, "R: expected data file ... not produced" in the committed
    # raw log). The fatal case is a *silent* loss -- an infra failure whose
    # sample was NOT counted as an errored draw, or any failure in an mm/ctrl
    # batch (the measurement and its determinism anchors must be untouched).
    infra_accounted = _check_infra_accounted(request, reduced)

    exp_dir, _ = FAMILY_CLAIMS[family]
    _mode, default_key = deck_adapter.MC_FAMILIES[family]
    key = reduced.get("key") or default_key
    rid = record_id or mint_record_id(now)
    now = now or datetime.now(timezone.utc)
    sha = git_short_sha()
    pdk = pdk_identity()
    klt_bin_resolved = klt_bin or os.environ.get("KLT", "klt")
    klt_ver = klt_version(klt_bin_resolved)

    scale = meta["nc_mismatch_scale"]
    parts = [f"sw_stat_mismatch={scale:g} ({scale:g}x the PDK's per-instance "
             f"Vt/current-factor mismatch sigma)"]
    if meta.get("nc_vdd") is not None:
        parts.append(f"VDD={meta['nc_vdd']} V (below spec/sram.md's ratified 2.97 V minimum)")
    nc_description = "known-bad variant: " + ", ".join(parts)

    root = Path(repo_root)
    mc_dir = root / "sim" / exp_dir / "mc"
    logs_dir = mc_dir / "raw-logs" / rid
    samples_dir = mc_dir / "samples"
    reports_dir = mc_dir / "yield-reports"
    records_dir = mc_dir / "records"
    for d in (logs_dir, samples_dir, reports_dir, records_dir):
        d.mkdir(parents=True, exist_ok=True)

    sample_doc = build_sample_doc(family, request, reduced, rid, nc_description, klt_ver, sha, pdk, key=key)
    samples_path = samples_dir / f"{rid}.json"
    samples_path.write_text(json.dumps(sample_doc, indent=2) + "\n", encoding="utf-8")

    json_proc, text_proc = run_klt_yield(klt_bin_resolved, samples_path, reports_dir)
    json_report_path = reports_dir / f"{rid}.json"
    text_report_path = reports_dir / f"{rid}.txt"
    json_report_path.write_text(json_proc.stdout, encoding="utf-8")
    text_report_path.write_text(
        text_proc.stdout + ("\n" + text_proc.stderr if text_proc.returncode != 0 else ""),
        encoding="utf-8",
    )
    if json_proc.returncode != 0:
        print(f"WARNING: klt yield exited {json_proc.returncode}:\n{text_proc.stderr}",
              file=sys.stderr)

    # Per-draw raw logs: sample index, the seed(s) that produced it, and its
    # value -- or the reason it produced none (the pool's collect() format).
    per_corner_summary = []
    for cid in meta["corners"]:
        batches = reduced["batches"].get(cid, {})
        log_lines = []
        counts = {}
        for kind, _sw in deck_adapter.MC_KINDS:
            batch = batches.get(kind)
            if batch is None:
                continue
            heading = {
                "mm": f"=== corner {cid} -- mismatch samples (sw_stat_mismatch=1) ===",
                "ctrl": f"=== corner {cid} -- determinism control (sw_stat_mismatch=0) ===",
                "nc": f"=== corner {cid} -- negative control ({nc_description}) ===",
            }[kind]
            log_lines.append(heading)
            ok = errored = 0
            for i, results, errors in batch["samples"]:
                seed = batch["seed_labels"][i]
                if errors or key not in results:
                    errored += 1
                    reason = "; ".join(errors) if errors else f"no RESULT for {key}"
                    log_lines.append(f"sample {i} seed={seed}: OPEN -- {reason}")
                else:
                    ok += 1
                    log_lines.append(f"sample {i} seed={seed}: RESULT: {key} = {results[key]!r}")
            counts[kind] = (ok, errored)
            log_lines.append("")
        (logs_dir / f"{cid}.log").write_text("\n".join(log_lines).rstrip("\n") + "\n", encoding="utf-8")

        det_batch = batches.get("ctrl", {"samples": []})
        det_values = [s[1][key] for s in det_batch["samples"] if not s[2] and key in s[1]]
        det_distinct = sorted(set(det_values))
        per_corner_summary.append({
            "corner_id": cid,
            "mm_n_ok": counts.get("mm", (0, 0))[0],
            "mm_n_errored": counts.get("mm", (0, 0))[1],
            "det_n_ok": counts.get("ctrl", (0, 0))[0],
            "det_n_errored": counts.get("ctrl", (0, 0))[1],
            "det_distinct_values": det_distinct,
            "det_pinned": len(det_distinct) <= 1,
            "nc_n_ok": counts.get("nc", (0, 0))[0],
            "nc_n_errored": counts.get("nc", (0, 0))[1],
        })

    summary = {
        "record_id": rid,
        "experiment": exp_dir,
        "family": family,
        "key": key,
        "claim": MC_CLAIMS[family],
        "provenance": sample_doc["provenance"],
        "request_meta": {
            "corners": meta["corners"],
            "nc_mismatch_scale": meta["nc_mismatch_scale"],
            "nc_vdd": meta.get("nc_vdd"),
            "spiceinit_sha256": meta.get("spiceinit_sha256"),
        },
        "corners": per_corner_summary,
        "samples_path": _rel(samples_path, root),
        "json_report_path": _rel(json_report_path, root),
        "text_report_path": _rel(text_report_path, root),
        "raw_logs_dir": _rel(logs_dir, root),
        "nc_infra_draws": [
            {"id": f.get("id"), "reason": f.get("reason")} for f in infra_accounted
        ],
        "klt_yield_exit_code": json_proc.returncode,
        "klt_version": klt_ver,
        "git_sha": sha,
        "timestamp": f"{now:%Y-%m-%dT%H:%M:%SZ}",
        "author": AUTHOR,
    }
    summary_path = logs_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    record_text = render_mc_record(summary, json_proc.stdout, text_proc.stdout,
                                   supersedes, f"{rid} ({minted_by()})",
                                   nc_infra=infra_accounted)
    record_path = records_dir / f"{rid}.md"
    if record_path.exists():
        raise SystemExit(
            f"record already exists: {record_path} -- record ids are "
            "<UTC-timestamp>-<sha>; re-run (or pass --record-id) so two "
            "records minted in the same second do not collide"
        )
    record_path.write_text(record_text, encoding="utf-8")

    print(f"wrote {samples_path}")
    print(f"wrote {json_report_path}")
    print(f"wrote {text_report_path}")
    print(f"wrote {summary_path}")
    print(f"wrote {record_path}")
    print(f"record-id: {rid}")
    return record_path


def minted_by() -> str:
    return "sim/lib/mint_records.py"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("corner", help="mint one deterministic corner record")
    c.add_argument("family", choices=sorted(FAMILY_CLAIMS))
    c.add_argument("--request", required=True, type=Path)
    c.add_argument("--reduced", required=True, type=Path)
    c.add_argument("--report", required=True, type=Path)
    c.add_argument("--unit-dir", required=True, type=Path)
    c.add_argument("--supersedes", default="")
    c.add_argument("--record-id")
    m = sub.add_parser("mc", help="mint one Monte Carlo campaign record + artifacts")
    m.add_argument("family", choices=sorted(MC_CLAIMS))
    m.add_argument("--request", required=True, type=Path)
    m.add_argument("--reduced", required=True, type=Path)
    m.add_argument("--supersedes", default="")
    m.add_argument("--record-id")
    m.add_argument("--klt", help="klt binary to run `klt yield` with (default: KLT env or PATH)")
    args = ap.parse_args(argv)

    if args.cmd == "corner":
        mint_corner(args.family, args.request, args.reduced, args.report,
                    args.unit_dir, args.supersedes, record_id=args.record_id)
    else:
        mint_mc(args.family, args.request, args.reduced, args.supersedes,
                record_id=args.record_id, klt_bin=args.klt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
