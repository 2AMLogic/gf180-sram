#!/usr/bin/env python3
"""sim/lib/run_mc_campaign.py -- Monte Carlo mismatch campaign for a
sim/<experiment>/testbench/*.spice fixture, at a caller-selected subset of
the ratified 9-corner PVT matrix (spec/sram.md "Characterization" -> "Corner
set"), producing a `klt yield` sample-set document and JSON/text yield
report per sim/README.md's MC/yield evidence-record convention.

Issue #26 ("Produce Monte Carlo / yield evidence for the SRAM stability
margins"): the buildable half of T1 checklist item 6 -- no `klt yield`
report existed anywhere in this repo before this script. Builds on top of
sim/lib/run_corner_sweep.sh's deterministic 9-corner evidence (#24/#25):
this script does not replace that evidence, it *combines* with it -- MC runs
at a caller-selected subset of the same 9 corners (never nominal-only), so
the two data sets sit side by side under the same claim.

## Mismatch mechanism

gf180mcu's `sm141064.ngspice` gates per-instance MOS mismatch
(threshold-voltage and current-factor jitter, `delvto='mis_vth*sw_stat_mismatch'`
/ `mulu0='1-mis_k*sw_stat_mismatch'` inside each `nfet_03v3`/`pfet_03v3`
`.subckt`) behind the single global `.param sw_stat_mismatch` switch, already
pulled in by every `typical`/`ff`/`ss` `.LIB` section via `.lib
'sm141064.ngspice' fets_mm` -- see `docs/cli/sim.md`'s "Known-good mismatch
mechanisms" (`2AMLogic/klayout-tools`) for the general contract; this
script's `_corner_inc` implements exactly the gf180mcu branch of that
contract (a `.param` toggle, not a `.lib` section name, so `corners.process`-
style section selection cannot express it -- confirmed empirically during
this issue's implementation, see "Known ngspice/PDK-file quirk" below).

Per-instance mismatch is seeded via ngspice's `.options seed=<n>` (must
appear before any `.lib`/`.include` card that reads it, per ngspice's
documented `AGAUSS`/`GAUSS` seeding mechanism -- also the seed contract
`docs/cli/sim.md`'s "Monte Carlo sampling" section documents for `klt sim`
itself). This script does not invoke `klt sim` directly: none of this
repo's four testbenches are a bare "circuit body" (`klt sim`'s required
netlist shape, no `.control`/`.end` of their own) -- each already carries
its own `.control` block performing a DC sweep + `wrdata` (SNM fixtures) or
a bisection search (write margin) that must run unmodified for cross-
comparability with the existing deterministic corner-sweep evidence. This
script instead re-implements exactly `sim/lib/run_corner_sweep.sh`'s own
per-corner ngspice-subprocess invocation pattern, with a `.options seed=`
line and `sw_stat_mismatch` override added to the generated `corner.inc`,
and feeds the resulting per-sample values to `klt yield` as a sample-set
document -- the "Sample-set document" input shape `docs/cli/yield.md`
documents for a draw that did not come from `klt sim` itself.

## Known ngspice/PDK-file quirk: redefining an already-`.param`-block-scoped
## name via a second, separate `.param` card corrupts later single-line
## `.param` cards in the same deck (discovered empirically during this
## issue's implementation)

`design.ngspice`'s `sw_stat_mismatch`/`sw_stat_global`/`mc_skew`/
`res_mc_skew`/`cap_mc_skew`/`fnoicor` defaults are all ONE `.param` card
(`.param` followed by six `+`-continuation lines). Overriding just
`sw_stat_mismatch` afterward with a second, independent `.param
sw_stat_mismatch = 1` card parses without any diagnostic but silently
corrupts ngspice's recognition of a *later*, unrelated single-line `.param`
card further down the same deck (reproduced with
`sim/write-margin/testbench/tb_write_margin.spice`'s own `.param VWRITE=0`:
"Error on line 42 or its substitute: ... unknown parameter (vwrite)",
"incomplete or empty netlist"). Redefining a name that was never part of
that combined card (a fresh, testbench-scoped name) does not trigger this.
The fix this script uses: never `.include` `design.ngspice` at all for an
MC-mismatch run -- instead, emit the exact same six defaults as this
script's own single `.param` card, with `sw_stat_mismatch` set to the
caller's requested value. This is an ngspice-parser/PDK-model-file
interaction, not a `klt` gap, so it is not filed against
`2AMLogic/klayout-tools` per CLAUDE.md's friction protocol (which scopes
filed gaps to the `klt` tool itself); it is recorded here so it is not
silently rediscovered later.

## Two-instance SNM Monte Carlo (`snm-pair` mode)

`sim/read-snm/testbench/tb_read_snm.spice` and
`sim/hold-snm/testbench/tb_hold_snm.spice` are decoupled *single* half-cell
fixtures (see each file's own header for why -- `bitcell_6t`'s Q/QB nodes
are not independently accessible from outside the subcircuit). The
deterministic 9-corner claim (#24/#25) gets away with a single sweep because
`sim/lib/snm_extract.py`'s self-composed method (`f(f(x))`) assumes the two
physical half-cells are *identical* devices -- true with mismatch off. Under
`sw_stat_mismatch=1`, that assumption is exactly what a real inter-inverter
mismatch SNM campaign needs to NOT make: the two half-cells of a fabricated
part draw *independent* per-instance thresholds. Self-composing one
mismatched draw's curve does not model that (it only asks "what if both
inverters shifted together," which does not degrade the butterfly SNM the
way genuine L/R asymmetry does).

This script's `--mode snm-pair:<datafile>:<label>` (used for read/hold SNM
MC, as opposed to plain `snm:<datafile>:<label>` for the deterministic
corner sweep) instead runs the *same unmodified* single-half-cell testbench
**twice** per Monte Carlo sample -- once standing in for the "L" inverter,
once for "R" -- each with its own independently-derived seed, and combines
the two independent VTC sweeps via `snm_extract.py --pair`, the direct
two-curve generalization of the self-composed method (see that script's
module docstring for the derivation). The testbench file itself is
unmodified either way -- read-snm's and hold-snm's existing, already-
reviewed `.spice` files serve both the deterministic single-sweep claim and
the two-instance MC claim without a fork.

Usage:
    sim/lib/run_mc_campaign.py --experiment read-snm \\
        --testbench sim/read-snm/testbench/tb_read_snm.spice \\
        --mode snm-pair:read_snm_sweep.txt:read_snm --key read_snm_v \\
        --corner tt:25:3.30 --corner ff:125:2.97 --corner ss:-40:3.63 \\
        --claim "spec/sram.md Characterization -- read SNM (Monte Carlo)" \\
        --n 100 --n-control 8 --seed 20260817

    sim/lib/run_mc_campaign.py --experiment write-margin \\
        --testbench sim/write-margin/testbench/tb_write_margin.spice \\
        --mode direct --key write_trip_voltage_v --margin-vdd-key write_vdd_v \\
        --corner tt:25:3.30 --corner tt:-40:2.97 \\
        --claim "spec/sram.md Characterization -- write margin (Monte Carlo)" \\
        --n 100 --n-control 8 --seed 20260817

Requires: ngspice and python3 on PATH; a gf180mcu PDK install resolvable by
sim/lib/pdk_env.sh; `klt` (klayout-tools) on PATH with the yield/native
extension built (see docs/cli/yield.md "Building the native extension").
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

# gf180mcu process-corner label -> the model file's own bare `.LIB` section
# name (same mapping sim/lib/run_corner_sweep.sh uses -- "tt" is this
# repo's/spec's label for gf180mcu's "typical" section).
LIB_SECTION = {"ff": "ff", "tt": "typical", "ss": "ss"}

# design.ngspice's own defaults for every name its combined `.param` card
# sets, reproduced verbatim here (see module docstring, "Known ngspice/
# PDK-file quirk") so this script never needs to redefine `sw_stat_mismatch`
# via a second, independent `.param` card.
_DESIGN_DEFAULTS = {
    "sw_stat_global": 0,
    "mc_skew": 3,
    "res_mc_skew": 3,
    "cap_mc_skew": 3,
    "fnoicor": 0,
}

RESULT_RE = re.compile(r"^RESULT:\s*(\S+)\s*=\s*([\-0-9.eE+]+)\s*;?\s*$", re.MULTILINE)
RESULT_ERROR_RE = re.compile(r"^RESULT-ERROR:.*$", re.MULTILINE)


def resolve_pdk() -> dict[str, str]:
    """Resolve the gf180mcu PDK the same way sim/lib/pdk_env.sh does, by
    sourcing that script in a subshell and capturing what it exports -- so
    this script's PDK resolution can never drift from the bash runner's.
    """
    proc = subprocess.run(
        ["bash", "-c", f"source '{SCRIPT_DIR}/pdk_env.sh' && env"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.exit(f"run_mc_campaign.py: pdk_env.sh failed:\n{proc.stderr}")
    env = {}
    for line in proc.stdout.splitlines():
        if "=" in line and line.startswith("GF180_"):
            k, _, v = line.partition("=")
            env[k] = v
    for required in ("GF180_MODEL_FILE", "GF180_DESIGN_INC", "GF180_VARIANT_DIR"):
        if required not in env:
            sys.exit(f"run_mc_campaign.py: pdk_env.sh did not export {required}")
    return env


def derive_seed(base_seed: int, corner_id: str, kind: str, sample_index: int) -> int:
    """Reproducible per-sample seed: SHA-256 of (base_seed, corner, kind,
    sample_index), never Python's salted built-in hash() -- same
    reproducibility bar docs/cli/sim.md's own seed contract states
    (`2AMLogic/klayout-tools`). `kind` is "mm" (mismatch) or "ctrl"
    (deterministic negative control) so the two draws never collide even at
    the same sample_index.
    """
    digest = hashlib.sha256(f"{base_seed}:{corner_id}:{kind}:{sample_index}".encode()).hexdigest()
    # ngspice seeds are plain positive integers; keep well under 2**31.
    return (int(digest[:8], 16) % 2_000_000_000) + 1


def corner_id(process: str, temp: str, vdd: str) -> str:
    return f"{process}_{temp}c_{vdd}v"


def build_corner_inc(pdk: dict[str, str], process: str, temp: str, vdd: str, seed: int, sw_stat_mismatch: float) -> str:
    section = LIB_SECTION[process]
    lines = [
        "* Generated by sim/lib/run_mc_campaign.py -- do not edit, do not commit.",
        f"* corner: process={process} temp={temp}C vdd={vdd}V sw_stat_mismatch={sw_stat_mismatch} seed={seed}",
        f".options seed={seed}",
        ".param",
        f"+ sw_stat_global = {_DESIGN_DEFAULTS['sw_stat_global']}",
        f"+ sw_stat_mismatch = {sw_stat_mismatch}",
        f"+ mc_skew = {_DESIGN_DEFAULTS['mc_skew']}",
        f"+ res_mc_skew = {_DESIGN_DEFAULTS['res_mc_skew']}",
        f"+ cap_mc_skew = {_DESIGN_DEFAULTS['cap_mc_skew']}",
        f"+ fnoicor = {_DESIGN_DEFAULTS['fnoicor']}",
        f".lib '{pdk['GF180_MODEL_FILE']}' {section}",
        f".temp {temp}",
        f".param VDDC={vdd}",
    ]
    return "\n".join(lines) + "\n"


def run_one(testbench_text: str, corner_inc_text: str, mode: str, tb_name: str) -> tuple[str, dict[str, float], list[str]]:
    """Run one ngspice invocation in a scratch directory; return
    (combined log text, {key: value} extracted results, [error strings]).
    """
    with tempfile.TemporaryDirectory(prefix="mc-campaign-") as tmp:
        work = Path(tmp)
        (work / "corner.inc").write_text(corner_inc_text, encoding="utf-8")
        (work / tb_name).write_text(testbench_text, encoding="utf-8")
        proc = subprocess.run(
            ["ngspice", "-b", tb_name],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        log = proc.stdout + proc.stderr
        if mode.startswith("snm:"):
            _, datafile, label = mode.split(":", 2)
            data_path = work / datafile
            if data_path.exists():
                snm_proc = subprocess.run(
                    ["python3", str(SCRIPT_DIR / "snm_extract.py"), str(data_path), label],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                log += snm_proc.stdout + snm_proc.stderr
            else:
                log += f"RESULT-ERROR: {label} -- expected data file {datafile} not produced\n"

    results = {k: float(v) for k, v in RESULT_RE.findall(log)}
    errors = RESULT_ERROR_RE.findall(log)
    return log, results, errors


def run_one_snm_pair(
    testbench_text: str,
    tb_name: str,
    pdk: dict[str, str],
    process: str,
    temp: str,
    vdd: str,
    seed_l: int,
    seed_r: int,
    datafile: str,
    label: str,
    sw_stat_mismatch: float,
) -> tuple[dict[str, float], list[str]]:
    """Run the same half-cell testbench twice (seed_l for "L", seed_r for
    "R"), then combine the two independent VTC sweeps with
    `snm_extract.py --pair` -- see module docstring, "Two-instance SNM
    Monte Carlo".
    """
    with tempfile.TemporaryDirectory(prefix="mc-campaign-pair-") as tmp:
        work = Path(tmp)
        errors: list[str] = []
        data_paths: dict[str, Path] = {}
        for side, seed in (("L", seed_l), ("R", seed_r)):
            side_dir = work / side
            side_dir.mkdir()
            inc = build_corner_inc(pdk, process, temp, vdd, seed, sw_stat_mismatch)
            (side_dir / "corner.inc").write_text(inc, encoding="utf-8")
            (side_dir / tb_name).write_text(testbench_text, encoding="utf-8")
            proc = subprocess.run(
                ["ngspice", "-b", tb_name], cwd=side_dir, capture_output=True, text=True, check=False
            )
            data_path = side_dir / datafile
            if data_path.exists():
                data_paths[side] = data_path
            else:
                errors.append(
                    f"{side}: expected data file {datafile} not produced (ngspice exit {proc.returncode})"
                )
        if "L" not in data_paths or "R" not in data_paths:
            return {}, errors or ["missing sweep data for L and/or R half-cell"]

        snm_proc = subprocess.run(
            ["python3", str(SCRIPT_DIR / "snm_extract.py"), "--pair", str(data_paths["L"]), str(data_paths["R"]), label],
            capture_output=True,
            text=True,
            check=False,
        )
        log = snm_proc.stdout + snm_proc.stderr

    results = {k: float(v) for k, v in RESULT_RE.findall(log)}
    errors += RESULT_ERROR_RE.findall(log)
    return results, errors


def run_batch(
    testbench_text: str,
    tb_name: str,
    mode: str,
    key: str,
    jobs: int,
    seeds: list[int],
    pdk: dict[str, str],
    process: str,
    temp: str,
    vdd: str,
    sw_stat_mismatch: float,
) -> list[tuple[int, dict[str, float], list[str]]]:
    """Run one ngspice invocation per seed in `seeds`, up to `jobs` at a
    time (ThreadPoolExecutor -- each unit of work is a blocking
    `subprocess.run`, so the GIL is released for the duration and this is
    real OS-level parallelism, the same pattern
    2AMLogic/gf180-bandgap's sim/mc-untrimmed/run_mc_untrimmed.py uses for
    its own (group, temperature) point sweep). Returns results in the same
    order as `seeds`, regardless of completion order -- corners share
    nothing, so this changes wall-clock time only, never which seed produced
    which recorded value.
    """
    results: list[tuple[int, dict[str, float], list[str]] | None] = [None] * len(seeds)

    def work(i: int, seed: int):
        inc = build_corner_inc(pdk, process, temp, vdd, seed, sw_stat_mismatch)
        _log, res, errs = run_one(testbench_text, inc, mode, tb_name)
        return i, res, errs

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = {pool.submit(work, i, seed): i for i, seed in enumerate(seeds)}
        for future in concurrent.futures.as_completed(futures):
            i, res, errs = future.result()
            results[i] = (i, res, errs)
    return [r for r in results if r is not None]


def run_batch_pair(
    testbench_text: str,
    tb_name: str,
    datafile: str,
    label: str,
    jobs: int,
    seed_pairs: list[tuple[int, int]],
    pdk: dict[str, str],
    process: str,
    temp: str,
    vdd: str,
    sw_stat_mismatch: float,
) -> list[tuple[int, dict[str, float], list[str]]]:
    """`run_batch`'s two-instance sibling: each unit of work is one
    `run_one_snm_pair` call (two ngspice invocations + one snm_extract.py
    --pair combination), up to `jobs` samples in flight at a time.
    """
    results: list[tuple[int, dict[str, float], list[str]] | None] = [None] * len(seed_pairs)

    def work(i: int, seed_l: int, seed_r: int):
        res, errs = run_one_snm_pair(
            testbench_text, tb_name, pdk, process, temp, vdd, seed_l, seed_r, datafile, label, sw_stat_mismatch
        )
        return i, res, errs

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = {pool.submit(work, i, sl, sr): i for i, (sl, sr) in enumerate(seed_pairs)}
        for future in concurrent.futures.as_completed(futures):
            i, res, errs = future.result()
            results[i] = (i, res, errs)
    return [r for r in results if r is not None]


def _fmt(value, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def render_record(summary: dict, sample_doc: dict, json_report_text: str, text_report_text: str, args) -> str:
    """Render the append-only Markdown evidence record for this campaign.

    Same field set sim/lib/run_corner_sweep.sh's deterministic records carry
    (Record ID / Claim / Netlist provenance / Corner matrix run / Statistical
    convention / Result / Links / Timestamp / Supersedes -- see sim/README.md
    "Summary record format"), with the MC-specific rows item 6 of
    klayout-tools' docs/design-evidence-tiers.md requires (seed, sample
    count, negative control) and the per-corner yield/capability rollup
    lifted verbatim out of the `klt yield` JSON report, so the record never
    restates a number the report did not produce.
    """
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

    prov = sample_doc["provenance"]
    overall = payload.get("status", "n/a")
    warnings = payload.get("warnings") or []

    lines = [
        f"# MC/yield record `{summary['record_id']}`",
        "",
        f"- **Record ID**: `{summary['record_id']}`",
        f"- **Kind**: Monte Carlo mismatch campaign + `klt yield` report (statistical evidence, klayout-tools `docs/design-evidence-tiers.md` item 6)",
        f"- **Claim**: {summary['claim']}",
        f"- **Testbench**: `{prov['testbench']}`",
        "- **Netlist provenance**: schematic (this repo has not yet produced an extracted netlist; a post-layout re-run would record `extracted` here and reference this record via **Supersedes**)",
        f"- **Corner matrix run**: {len(summary['corners'])} corner points from `spec/sram.md`'s "
        "ratified process x temperature x voltage set "
        f"({', '.join('`' + c['corner_id'] + '`' for c in summary['corners'])}) -- a deliberate "
        'Monte Carlo subset, chosen per `sim/README.md` "Which corners, and why not all of them". '
        "MC results **combine with**, and never replace, the deterministic corner records under "
        f"`sim/{summary['experiment']}/records/`, which sweep that set exhaustively.",
        f"- **Statistical convention**: Monte Carlo, per-instance device mismatch only "
        f"(`{prov['mismatch']['switch']}=1`; `{prov['mismatch']['mechanism']}`). "
        "Global/process variation is carried by the corner axis, not resampled -- so each corner is its own "
        "population and no estimate is pooled across corners.",
        f"- **Seed**: `{summary['seed']}` (base). Per-sample seed = {prov['mismatch']['seed_derivation']}; "
        f"delivered to ngspice as `{prov['mismatch']['seeding']}`.",
        f"- **Sample count**: {summary['n_mismatch']} mismatch samples per corner, "
        f"{summary['n_determinism_control']} determinism-control samples per corner, "
        f"{summary['n_negative_control']} negative-control samples per corner.",
        f"- **Spec limits**: `min = {prov['spec_limits']['min']}` V -- {prov['spec_limits']['source']}. "
        "No `target_yield` is declared: `spec/sram.md` ratifies no yield target for these rows "
        "(that is exactly the open operator decision tracked as issue #20), and this harness does not "
        "invent one. The estimates below are therefore *reported* against the spec's own `> 0` limit, "
        "with Cpk / sigma-to-spec as the quantitative margin statement.",
        f"- **PDK**: `{prov['pdk_variant_dir']}` -- **`klt`**: `{prov['klt_version']}` -- "
        f"**git**: `{summary['git_sha']}`",
        f"- **`klt yield` overall status**: `{overall}` (exit code {summary['klt_yield_exit_code']})",
        f"- **Timestamp / author**: {summary['timestamp']} / {summary['author']}",
        "- **Supersedes**: (none)",
        "",
        "## Per-corner result (verbatim from the `klt yield` JSON report)",
        "",
        "| Corner | N | errored | mean (V) | stddev (V) | empirical yield, 95% lower bound | Cpk | sigma-to-spec | sample-size verdict | negative control |",
        "|---|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "`errored` counts draws that produced no usable measurement (for the SNM fixtures: a draw whose "
        "butterfly was not bistable, so no square exists to measure). `klt yield` excludes them from every "
        "statistic, so a record with a non-zero `errored` column states a yield estimate *conditioned on a "
        "measurable draw* -- read the errored count alongside it, never the yield alone.",
        "",
        "## Determinism control (mismatch off)",
        "",
        "With `sw_stat_mismatch=0` the campaign must reproduce, exactly and identically for every draw, the "
        "number the deterministic corner sweep already recorded for the same corner. This is what ties the MC "
        "evidence to the ratified 9-corner evidence rather than leaving it a parallel, unanchored claim.",
        "",
        "| Corner | N | errored | distinct value(s) (V) | verdict |",
        "|---|---|---|---|---|",
        *det_rows,
        "",
        "## Negative control",
        "",
        (
            f"Deliberate defect: **{summary['negative_control_description']}**, drawn with its own independent, "
            "reproducibly-derived seeds and analysed by `klt yield` against the *same* spec limits as the nominal "
            "measurement. A `detected` verdict means the control's empirical yield is lower **and** its exact "
            "(Clopper-Pearson) confidence interval does not overlap the nominal's -- i.e. these statistics "
            "demonstrably do detect a degraded design, rather than being assumed to."
            if summary["n_negative_control"] > 0
            else "None declared for this campaign -- `klt yield` flags that with a run-level warning (see below)."
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
        f"- Deterministic 9-corner records for the same claim: `sim/{summary['experiment']}/records/`",
        "",
        "## Reproduce",
        "",
        "```bash",
        "sim/lib/run_mc_campaign.py \\",
        f"  --experiment {args.experiment} \\",
        f"  --testbench {prov['testbench']} \\",
        f"  --mode '{args.mode}' --key {args.key} \\",
        *([f"  --margin-vdd-key {args.margin_vdd_key} \\"] if args.margin_vdd_key else []),
        *[f"  --corner {c} \\" for c in args.corners],
        f"  --n {args.n} --n-control {args.n_control} --n-nc {args.n_nc} \\",
        f"  --nc-mismatch-scale {args.nc_mismatch_scale:g}"
        + (f" --nc-vdd {args.nc_vdd}" if args.nc_vdd else "")
        + " \\",
        f"  --seed {args.seed} \\",
        f"  --claim {json.dumps(args.claim)}",
        "```",
        "",
        "## `klt yield` text report (verbatim)",
        "",
        "```",
        text_report_text.rstrip("\n"),
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--experiment", required=True, help="experiment dir name under sim/, e.g. read-snm")
    ap.add_argument("--testbench", required=True, type=Path, help="path to the .spice testbench")
    ap.add_argument(
        "--mode", required=True,
        help='"direct" (see sim/lib/run_corner_sweep.sh), "snm:<datafile>:<label>" (single-curve, self-composed -- not recommended for MC, see module docstring), or "snm-pair:<datafile>:<label>" (two independent half-cell instances per sample -- used for read/hold SNM MC)',
    )
    ap.add_argument("--key", required=True, help="RESULT key to extract as this campaign's measurement, e.g. read_snm_v")
    ap.add_argument(
        "--margin-vdd-key", default=None,
        help="RESULT key holding this corner's VDD (e.g. write_vdd_v); when given, the recorded measurement is (that value - --key's value) -- spec/sram.md's margin = VDD - WTV definition for write margin, rather than the raw trip-voltage key itself -- and the output measurement name gains a '_margin' suffix.",
    )
    ap.add_argument("--claim", required=True, help="free-text spec/sram.md claim this record substantiates")
    ap.add_argument(
        "--corner",
        action="append",
        required=True,
        dest="corners",
        metavar="process:temp:vdd",
        help="a corner from the ratified 9-corner matrix to run MC at, e.g. tt:25:3.30 -- repeatable, must appear at least twice (AC: multiple corners, not nominal-only)",
    )
    ap.add_argument("--n", type=int, default=100, help="mismatch samples per corner (default: 100)")
    ap.add_argument(
        "--n-control", type=int, default=8,
        help="deterministic (mismatch-off) control samples per corner (default: 8). This is the harness-fidelity control: with sw_stat_mismatch=0 every draw must collapse onto ONE value, and that value must be the same number sim/lib/run_corner_sweep.sh's deterministic 9-corner record reports for this corner. It is NOT the negative control -- see --n-nc.",
    )
    ap.add_argument(
        "--n-nc", type=int, default=0,
        help="negative-control samples per corner (default: 0 = none, which klt yield flags with a run-level warning). The negative control is a seeded, KNOWN-BAD variant of the same fixture -- see --nc-mismatch-scale / --nc-vdd -- whose samples are emitted into the sample-set document's `negative_control` block so `klt yield` can check that the statistics actually detect a degraded design (docs/cli/yield.md, 'Negative control').",
    )
    ap.add_argument(
        "--nc-mismatch-scale", type=float, default=1.0,
        help="sw_stat_mismatch value for the negative-control batch (default: 1.0, i.e. no inflation). A value K > 1 scales gf180mcu's per-instance Vt/current-factor mismatch sigma by exactly K (delvto='mis_vth*sw_stat_mismatch', mulu0='1-mis_k*sw_stat_mismatch' -- linear in the switch), i.e. docs/cli/yield.md's own 'a mismatch seed pushed past spec' defect. Keep K well under 1/sigma(mis_k) (~50 for these devices) or mulu0 goes non-physical in the tails.",
    )
    ap.add_argument(
        "--nc-vdd", default=None,
        help="supply, in volts, for the negative-control batch (default: the corner's own VDD). A value below spec/sram.md's ratified 2.97 V minimum is docs/cli/yield.md's other named defect, 'a corner known to fail'.",
    )
    ap.add_argument(
        "--nc-description", default=None,
        help="free-text description of the deliberate defect, written into the sample-set document's negative_control.description (default: auto-generated from --nc-mismatch-scale/--nc-vdd).",
    )
    ap.add_argument("--seed", type=int, required=True, help="base seed for this campaign (recorded in the evidence record)")
    ap.add_argument("--limit-min", type=float, default=0.0, help="spec lower limit for this measurement (default: 0.0, spec/sram.md's '> 0' margin requirement)")
    ap.add_argument("--author", default="agent-builder")
    ap.add_argument(
        "-j", "--jobs", type=int, default=min(8, os.cpu_count() or 2),
        help="parallel ngspice invocations per corner (default: min(8, cpu_count)) -- useful on a workstation with idle cores, per klt sim's own local-parallel guidance; each sample is an independent, seed-identical-regardless-of-order draw, so this changes wall-clock time only, never a recorded value.",
    )
    args = ap.parse_args()

    if len(args.corners) < 2:
        sys.exit("run_mc_campaign.py: at least two --corner points are required (AC: multiple corners, not nominal-only)")

    pdk = resolve_pdk()
    args.testbench = args.testbench.resolve()
    # Same @@REPO_ROOT@@ substitution sim/lib/run_corner_sweep.sh performs:
    # tb_write_margin.spice / tb_*_access_time.spice `.include` the DUT via
    # this placeholder (not a repo-relative path) because they run from a
    # scratch directory outside the repo tree -- see sim/README.md
    # "Netlist provenance and the @@REPO_ROOT@@ substitution".
    testbench_text = args.testbench.read_text(encoding="utf-8").replace("@@REPO_ROOT@@", str(REPO_ROOT))
    tb_name = args.testbench.name

    git_sha = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    ).stdout.strip() or "nogit"
    record_id = f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{git_sha}"

    exp_dir = REPO_ROOT / "sim" / args.experiment
    mc_dir = exp_dir / "mc"
    logs_dir = mc_dir / "raw-logs" / record_id
    samples_dir = mc_dir / "samples"
    reports_dir = mc_dir / "yield-reports"
    records_dir = mc_dir / "records"
    for d in (logs_dir, samples_dir, reports_dir, records_dir):
        d.mkdir(parents=True, exist_ok=True)

    is_pair_mode = args.mode.startswith("snm-pair:")
    if is_pair_mode:
        _, pair_datafile, pair_label = args.mode.split(":", 2)

    def do_batch(kind: str, n: int, sw_stat_mismatch: float, process: str, temp: str, vdd: str, cid: str):
        if n <= 0:
            return [], []
        if is_pair_mode:
            seed_pairs = [
                (derive_seed(args.seed, cid, f"{kind}-L", i), derive_seed(args.seed, cid, f"{kind}-R", i))
                for i in range(n)
            ]
            raw = run_batch_pair(
                testbench_text, tb_name, pair_datafile, pair_label, args.jobs, seed_pairs, pdk, process, temp, vdd, sw_stat_mismatch
            )
            seed_labels = [f"L={sl},R={sr}" for sl, sr in seed_pairs]
        else:
            seeds = [derive_seed(args.seed, cid, kind, i) for i in range(n)]
            raw = run_batch(testbench_text, tb_name, args.mode, args.key, args.jobs, seeds, pdk, process, temp, vdd, sw_stat_mismatch)
            seed_labels = [str(s) for s in seeds]
        return raw, seed_labels

    measurements = []
    per_corner_summary = []

    def extract_value(results: dict[str, float]) -> float | None:
        """Raw --key value, or (--margin-vdd-key value - --key value) when
        --margin-vdd-key is given (spec/sram.md's margin = VDD - WTV
        definition for write margin) -- None if a needed key is missing.
        """
        if args.key not in results:
            return None
        if args.margin_vdd_key is None:
            return results[args.key]
        if args.margin_vdd_key not in results:
            return None
        return results[args.margin_vdd_key] - results[args.key]

    measurement_key = args.key if args.margin_vdd_key is None else f"{args.key}_margin"

    def collect(raw, seed_labels, heading: str) -> tuple[list[float], int, list[str]]:
        """Turn one batch's raw per-sample results into (values, errored,
        log-lines). A sample that produced no usable RESULT is counted as
        `errored` and excluded from `values` -- never coerced to a number --
        matching `klt yield`'s own null/`errored` handling (docs/cli/yield.md,
        "Sample-set document").
        """
        values: list[float] = []
        errored = 0
        lines = [heading]
        for i, results, errors in raw:
            seed = seed_labels[i]
            value = extract_value(results)
            if errors or value is None:
                errored += 1
                reason = "; ".join(errors) if errors else f"no RESULT for {args.key}"
                lines.append(f"sample {i} seed={seed}: OPEN -- {reason}")
            else:
                values.append(value)
                lines.append(f"sample {i} seed={seed}: RESULT: {measurement_key} = {value!r}")
        return values, errored, lines

    nc_enabled = args.n_nc > 0
    nc_description = args.nc_description
    if nc_enabled and nc_description is None:
        parts = [f"sw_stat_mismatch={args.nc_mismatch_scale:g} ({args.nc_mismatch_scale:g}x the PDK's per-instance Vt/current-factor mismatch sigma)"]
        if args.nc_vdd is not None:
            parts.append(f"VDD={args.nc_vdd} V (below spec/sram.md's ratified 2.97 V minimum)")
        nc_description = "known-bad variant: " + ", ".join(parts)

    for corner_spec in args.corners:
        process, temp, vdd = corner_spec.split(":")
        cid = corner_id(process, temp, vdd)
        print(
            f"corner {cid}: {args.n} mismatch + {args.n_control} determinism-control"
            + (f" + {args.n_nc} negative-control" if nc_enabled else "")
            + " samples",
            flush=True,
        )

        mm_raw, mm_seed_labels = do_batch("mm", args.n, 1, process, temp, vdd, cid)
        mm_values, mm_errors, mm_log_lines = collect(
            mm_raw, mm_seed_labels, f"=== corner {cid} -- mismatch samples (sw_stat_mismatch=1) ==="
        )

        # Determinism (harness-fidelity) control: mismatch OFF. Every draw
        # must collapse onto one value, and that value must equal what
        # sim/lib/run_corner_sweep.sh's deterministic record reports for this
        # corner -- the check that this MC harness is driving the same
        # fixture the 9-corner evidence was taken from, i.e. that these MC
        # results *combine with* the process corners rather than replace them.
        det_raw, det_seed_labels = do_batch("ctrl", args.n_control, 0, process, temp, vdd, cid)
        det_values, det_errors, det_log_lines = collect(
            det_raw, det_seed_labels, f"=== corner {cid} -- determinism control (sw_stat_mismatch=0) ==="
        )

        nc_values: list[float] = []
        nc_errors = 0
        nc_log_lines: list[str] = []
        if nc_enabled:
            nc_vdd = args.nc_vdd if args.nc_vdd is not None else vdd
            nc_raw, nc_seed_labels = do_batch("nc", args.n_nc, args.nc_mismatch_scale, process, temp, nc_vdd, cid)
            nc_values, nc_errors, nc_log_lines = collect(
                nc_raw,
                nc_seed_labels,
                f"=== corner {cid} -- negative control ({nc_description}) ===",
            )

        (logs_dir / f"{cid}.log").write_text(
            "\n".join(mm_log_lines + [""] + det_log_lines + ([""] + nc_log_lines if nc_log_lines else [])) + "\n",
            encoding="utf-8",
        )

        det_distinct = sorted(set(det_values))
        det_pinned = len(det_distinct) <= 1
        print(
            f"  mismatch: {len(mm_values)} ok, {mm_errors} open -- "
            f"determinism control: {len(det_values)} ok, {det_errors} open, "
            f"{'PINNED (identical)' if det_pinned else 'NOT PINNED -- unexpected spread'}"
            + (f" -- negative control: {len(nc_values)} ok, {nc_errors} open" if nc_enabled else ""),
            flush=True,
        )

        measurement = {
            "name": f"{measurement_key}@{cid}",
            "unit": "V",
            "samples": mm_values,
            "errored": mm_errors,
            "limits": {"min": args.limit_min},
            "source_corners": [cid],
        }
        if nc_enabled:
            measurement["negative_control"] = {
                "samples": nc_values,
                "errored": nc_errors,
                "description": nc_description,
            }
        measurements.append(measurement)
        per_corner_summary.append(
            {
                "corner_id": cid,
                "process": process,
                "temp_c": temp,
                "vdd_v": vdd,
                "mm_n_ok": len(mm_values),
                "mm_n_errored": mm_errors,
                "det_n_ok": len(det_values),
                "det_n_errored": det_errors,
                "det_distinct_values": det_distinct,
                "det_pinned": det_pinned,
                "nc_n_ok": len(nc_values),
                "nc_n_errored": nc_errors,
            }
        )

    klt = shutil.which("klt")
    if klt is None:
        sys.exit("run_mc_campaign.py: klt not found on PATH -- cannot produce a klt yield report")
    klt_version = subprocess.run(
        [klt, "--version"], capture_output=True, text=True, check=False
    ).stdout.strip() or "unknown"

    mismatch_provenance = {
        "switch": "sw_stat_mismatch",
        "model_file": pdk["GF180_MODEL_FILE"],
        "mechanism": "delvto='mis_vth*sw_stat_mismatch' / mulu0='1-mis_k*sw_stat_mismatch' per nfet_03v3/pfet_03v3 instance",
        "seeding": ".options seed=<derived>, one independent ngspice invocation per sample",
        "seed_derivation": "sha256(base_seed:corner_id:kind:sample_index), truncated to a positive 31-bit integer",
    }

    sample_doc = {
        "measurements": measurements,
        "provenance": {
            "record_id": record_id,
            "claim": args.claim,
            "testbench": str(args.testbench.relative_to(REPO_ROOT)),
            "key": measurement_key,
            "seed": args.seed,
            "n_mismatch": args.n,
            "n_determinism_control": args.n_control,
            "n_negative_control": args.n_nc,
            "negative_control_description": nc_description,
            "corners": [corner_id(*c.split(":")) for c in args.corners],
            "spec_limits": {
                "min": args.limit_min,
                "source": "spec/sram.md 'Characterization' -- read SNM / hold SNM / write margin must be strictly positive at every corner",
            },
            "mismatch": mismatch_provenance,
            "pdk_variant_dir": pdk["GF180_VARIANT_DIR"],
            "klt_version": klt_version,
            "git_sha": git_sha,
        },
    }
    samples_path = samples_dir / f"{record_id}.json"
    samples_path.write_text(json.dumps(sample_doc, indent=2) + "\n", encoding="utf-8")

    json_report_path = reports_dir / f"{record_id}.json"
    text_report_path = reports_dir / f"{record_id}.txt"
    json_proc = subprocess.run(
        [klt, "yield", str(samples_path), "--format", "json"],
        capture_output=True, text=True, check=False,
    )
    text_proc = subprocess.run(
        [klt, "yield", str(samples_path), "--format", "text"],
        capture_output=True, text=True, check=False,
    )
    json_report_path.write_text(json_proc.stdout, encoding="utf-8")
    text_report_path.write_text(text_proc.stdout + ("\n" + text_proc.stderr if text_proc.returncode != 0 else ""), encoding="utf-8")
    if json_proc.returncode != 0:
        print(f"WARNING: klt yield exited {json_proc.returncode}:\n{json_proc.stderr}", file=sys.stderr)

    summary = {
        "record_id": record_id,
        "experiment": args.experiment,
        "key": measurement_key,
        "claim": args.claim,
        "seed": args.seed,
        "n_mismatch": args.n,
        "n_determinism_control": args.n_control,
        "n_negative_control": args.n_nc,
        "negative_control_description": nc_description,
        "corners": per_corner_summary,
        "samples_path": str(samples_path.relative_to(REPO_ROOT)),
        "json_report_path": str(json_report_path.relative_to(REPO_ROOT)),
        "text_report_path": str(text_report_path.relative_to(REPO_ROOT)),
        "raw_logs_dir": str(logs_dir.relative_to(REPO_ROOT)),
        "klt_yield_exit_code": json_proc.returncode,
        "klt_version": klt_version,
        "git_sha": git_sha,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "author": args.author,
    }
    summary_path = logs_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    record_path = records_dir / f"{record_id}.md"
    record_path.write_text(
        render_record(summary, sample_doc, json_proc.stdout, text_proc.stdout, args), encoding="utf-8"
    )

    print(f"\nwrote {samples_path}")
    print(f"wrote {json_report_path}")
    print(f"wrote {text_report_path}")
    print(f"wrote {summary_path}")
    print(f"wrote {record_path}")
    print(f"record-id: {record_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
