#!/usr/bin/env python3
"""Deck-mode adapter: the 27-corner characterization grid as a `klt sim` deck request (#230).

    deck_adapter.py build  <family> --stage-dir DIR --request-out FILE [--pdk-dir DIR]
                           [--corner P:T:V ...]
    deck_adapter.py reduce <family> <klt-sim-report.json> [--request FILE]
                           [--outdir DIR] [--json-out FILE]
    deck_adapter.py mc-build  <family> --corner P:T:V ... --seed N --stage-dir DIR --request-out FILE
    deck_adapter.py mc-reduce <family> <request.json> <klt-sim-report.json> [--outdir DIR]
    deck_adapter.py spiceinit   # print the pinned run-directory .spiceinit (#338)
    deck_adapter.py families

This is the *offline preparation* half of the #230 deck-mode cutover that
retired `run_corner_sweep.sh`. It
does NOT run ngspice, submit anything, or mint a record:

* `build` composes, for each of the 27 ratified corners (or the subset
  `--corner` names, for a bounded parity run), exactly the scratch
  directory the retired `run_corner_sweep.sh` launcher composed (the
  testbench, a generated `corner.inc`, the family's staged DUT file(s))
  and writes a `klt sim` *deck-list* request that transports those decks
  unchanged (`klayout_tools.sim_decks`). The testbench's own
  `.control`/`wrdata`/bisection logic is untouched.
* `reduce` is the caller-owned reducer. `klt sim` deck mode reports process
  success only (no measurement parsing, no grading), so this applies the
  launcher's grading -- `RESULT:` / `RESULT-ERROR:` lines, `snm_extract.py`
  for the DC-sweep families -- to a deck report and fails closed on missing
  coverage, missing declared outputs and timeouts. Exit 0 from the engine is
  never read as a measurement PASS. Pass `--request` (the file `build` wrote)
  so a bounded run is graded against exactly the corners it asked for, and
  the executed decks' `deck_sha256` is checked against the composed bytes --
  a unit that reports no `deck_sha256` is itself a coverage error, so the
  check cannot silently not-run.

The only byte-level difference from the launcher's scratch deck is the
`@@REPO_ROOT@@` token, which becomes `.` (each family's staged DUT files
land at their repo-relative paths inside the unit) instead of this
checkout's absolute path: deck mode refuses absolute includes it would have to
rewrite, and a relative include is host-independent. `build` records both the
source-testbench and composed-deck sha256 so that is auditable, and a family
staging anything beyond the legacy single DUT netlist records exactly what it
stages (path + sha256) in `x_gf180_sram_adapter.staged_inputs`.

`mc-build` / `mc-reduce` are the same pair for the Monte Carlo pool in
`run_mc_campaign.py`: one deck per (corner, kind, sample[, L/R side]) whose
`corner.inc` is `run_mc_campaign.build_corner_inc`'s output and whose seed is
`run_mc_campaign.derive_seed`'s (both imported, never re-derived), and a
reducer that regroups a deck report into the per-seed `(index, results,
errors)` tuples `run_batch`/`run_batch_pair` return. `mc-reduce` makes the
same fail-closed deck check `reduce` makes: every unit's `deck_sha256` must
equal the request's composed bytes, and a unit that reports none is itself a
coverage error, so the check cannot silently not-run.

Nothing produced here is new physical evidence; `sim/*/records/` is
append-only and untouched.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_mc_campaign as mc  # noqa: E402
import snm_extract  # noqa: E402
from corner_matrix import (  # noqa: E402
    LIB_SECTION,
    corner_id,
    corner_ids,
    corners,
)

# Re-exported, not used directly in this module: the ratified corner matrix
# has a single owner (sim/lib/corner_matrix.py, #331), and
# sim/lib/test_corner_matrix.py still reads the axes through this module
# (`da.TEMPS` et al.), so the names stay bound here as a re-export. The
# launcher-equality guards that once consumed them were retired by #438.
from corner_matrix import PROCESSES, TEMPS, VDDS  # noqa: E402,F401
from repo_root import find_repo_root  # noqa: E402

REPO_ROOT = find_repo_root(Path(__file__))

REPO_ROOT_TOKEN = "@@REPO_ROOT@@"
DUT_NETLIST = "design/netlist/bitcell_6t.spice"
PDK_VARIANT = "gf180mcuD"
MODEL_REL = f"{PDK_VARIANT}/libs.tech/ngspice/sm141064.ngspice"
DESIGN_INC_REL = f"{PDK_VARIANT}/libs.tech/ngspice/design.ngspice"
DECK_TIMEOUT_S = 300

# The pinned ngspice environment, staged as a run-directory `.spiceinit`
# (issue #338). ngspice reads `.spiceinit` from its current working
# directory, and every execution path in this repo runs the engine with cwd
# set to a per-unit scratch directory, so staging this file there makes the
# environment a property of the repo rather than of whichever host runs the
# deck. A run-directory `.spiceinit` *replaces* `$HOME/.spiceinit` (verified
# 2026-11-14, #338) rather than merging with it, so the file carries every
# line a run needs -- not just the compatibility mode.
#
# Do NOT replace this with `options.ngspice_init`: on the deck-list path
# (`klayout_tools.sim_decks`) that option is silently dropped (the worker
# request's option allowlist is timeout_s/max_workers/ngspice_binary), so a
# request setting it would record a pinned mode that was never in force.
# Upstream gap: 2AMLogic/klayout-tools#5738. The single source of truth for
# these lines is SPICEINIT_TEXT below: the `spiceinit` verb prints it and
# both deck builders stage the same bytes into every unit, and
# sim/lib/test_deck_adapter.py asserts the printed CLI output and the staged
# per-unit `.spiceinit` match the constant byte-for-byte.
SPICEINIT_NAME = ".spiceinit"
SPICEINIT_TEXT = (
    "* Pinned ngspice environment -- staged into every run directory by\n"
    "* sim/lib (issue #338). A run-directory .spiceinit replaces $HOME/.spiceinit,\n"
    "* so every setting a run needs is in this file. Single source of truth:\n"
    "* SPICEINIT_TEXT in sim/lib/deck_adapter.py; do not edit copies.\n"
    "*\n"
    "* ngbehavior=hsa: the mode the committed sim/ corpus ran under (its corner\n"
    "* logs carry 'Compatibility modes selected: hs a'), so the committed records\n"
    "* stay reproducible, and the mode the gf180mcu ngspice model decks are\n"
    "* written against (a distro-packaged ngspice supplies it via its own spinit;\n"
    "* a locally built one does not).\n"
    "set ngbehavior=hsa\n"
    "* One ngspice thread per unit: batch-fleet workers run units in parallel\n"
    "* and rely on per-worker thread pinning; a run-directory .spiceinit would\n"
    "* otherwise drop the host's num_threads and oversubscribe a shared worker.\n"
    "set num_threads=1\n"
    "* Per-finger model binning (W/NF). NOT implied by ngbehavior=hsa (verified\n"
    "* 2026-11-14, #338). Inert today -- every device in this repo is nf=1, so\n"
    "* W/nf == W and bin selection cannot change -- but pinned so drawing a\n"
    "* multi-finger device cannot silently change model-bin selection.\n"
    "set wnflag=1\n"
)

# The five characterization families the retired `run_corner_sweep.sh`
# launcher drove (sim/README.md "Cold-start invocation"), plus the two
# by-hand pex write-margin legs the #230 cutover interrupted (#437). The
# first three elements are the launcher's own invocation shape: experiment
# dir, testbench, grading mode. The fourth is the repo-relative file(s)
# staged into every unit dir when the testbench references @@REPO_ROOT@@ --
# the DUT file(s) the deck's `.include`s must resolve against once the
# token becomes `.`. The five ratified families stage the flat bitcell
# netlist (the launcher's hard-coded behavior, kept as the default so their
# requests stay byte-identical); each pex leg stages the DUT its own
# testbench `.include`s, so the existing token rewrite resolves it.
FAMILIES = {
    "read-snm": ("sim/read-snm", "tb_read_snm.spice", "snm:read_snm_sweep.txt:read_snm", (DUT_NETLIST,)),
    "hold-snm": ("sim/hold-snm", "tb_hold_snm.spice", "snm:hold_snm_sweep.txt:hold_snm", (DUT_NETLIST,)),
    "write-margin": ("sim/write-margin", "tb_write_margin.spice", "direct", (DUT_NETLIST,)),
    "read-access": ("sim/access-time", "tb_read_access_time.spice", "direct", (DUT_NETLIST,)),
    "write-access": ("sim/access-time", "tb_write_access_time.spice", "direct", (DUT_NETLIST,)),
    # By-hand pex write-margin legs (issue #95, deck port #437): direct mode,
    # same ratified 27-corner matrix as the launcher ran them. The schematic
    # leg reuses the klt-pex-compatible .SUBCKT wrapper from the access-time
    # workflow; the extracted leg includes the --pdk-bound parasitic netlist
    # write-margin/dut/generate.sh produces.
    "pex-write-margin-schematic": (
        "sim/pex/write-margin", "tb_write_margin_schematic.spice", "direct",
        ("sim/pex/access-time/dut/bitcell_6t_subckt.spice",),
    ),
    "pex-write-margin-extracted": (
        "sim/pex/write-margin", "tb_write_margin_extracted.spice", "direct",
        ("sim/pex/write-margin/dut/extracted-netlist.spice",),
    ),
}


def parse_corner_spec(spec):
    """'tt:25:3.30' -> ('tt', '25', '3.30'), restricted to the ratified matrix.

    Only a corner the spec already ratifies can be named: a bounded run is a
    subset of the committed grid, never a new corner. Axis labels are the
    spec's own literal text (corner_matrix's rule), so each field must match
    its axis verbatim.
    """
    parts = str(spec).split(":")
    if len(parts) != 3:
        raise ValueError(f"corner {spec!r} must be process:temp:vdd (e.g. tt:25:3.30)")
    process, temp, vdd = parts
    if process not in PROCESSES:
        raise ValueError(f"corner {spec!r}: process must be one of {list(PROCESSES)}")
    if temp not in TEMPS:
        raise ValueError(f"corner {spec!r}: temperature must be one of {list(TEMPS)} (spec/sram.md corner set)")
    if vdd not in VDDS:
        raise ValueError(f"corner {spec!r}: vdd must be one of {list(VDDS)} (spec/sram.md corner set)")
    return process, temp, vdd


def select_corners(corner_specs=None):
    """The ratified corners named by `corner_specs`, in the launcher's order.

    `None`/empty selects the full 27-corner grid (the default, unchanged).
    Any subset keeps the launcher's loop order so unit order never depends on
    the order the corners were named on the command line.
    """
    if not corner_specs:
        return corners()
    wanted = [parse_corner_spec(s) for s in corner_specs]
    ids = [corner_id(*c) for c in wanted]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate corners: {dupes}")
    return [c for c in corners() if c in wanted]


def compose_corner_inc(process, temp, vdd, design_inc, model_file):
    """Text identical to the heredoc the retired run_corner_sweep.sh
    launcher wrote; the shape is pinned by sim/lib/test_deck_adapter.py."""
    return (
        "* Generated by sim/lib/run_corner_sweep.sh -- do not edit, do not commit.\n"
        f"* corner: process={process} temp={temp}C vdd={vdd}V\n"
        f".include '{design_inc}'\n"
        f".lib '{model_file}' {LIB_SECTION[process]}\n"
        f".temp {temp}\n"
        f".param VDDC={vdd}\n"
    )


def compose_deck(testbench_text):
    """The launcher's `sed s|@@REPO_ROOT@@|<root>|g`, with a relative root."""
    return testbench_text.replace(REPO_ROOT_TOKEN, ".")


def parse_mode(mode):
    """('direct', None, None) or ('snm', datafile, label)."""
    if mode == "direct":
        return "direct", None, None
    if mode.startswith("snm:"):
        _, datafile, label = mode.split(":", 2)
        return "snm", datafile, label
    raise ValueError(f"unsupported mode {mode!r}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_testbench_and_staged(exp_dir, tb_name, staged_files, repo_root):
    """(tb_bytes, deck_bytes, needs_staging, staged) for one family's testbench.

    The load-and-validate half both deck builders share: read the family
    testbench, compose the transport deck (`@@REPO_ROOT@@` -> `.`), and
    resolve the family's staged DUT inputs (#437) -- validated only when
    the testbench actually references the token, kept in FAMILIES order as
    (repo-relative path, absolute source) pairs.
    """
    tb_path = Path(repo_root) / exp_dir / "testbench" / tb_name
    tb_bytes = tb_path.read_bytes()
    tb_text = tb_bytes.decode("utf-8")
    deck_bytes = compose_deck(tb_text).encode("utf-8")
    needs_staging = REPO_ROOT_TOKEN in tb_text
    staged = []
    for rel in staged_files:
        src = Path(repo_root) / rel
        if needs_staging and not src.is_file():
            raise FileNotFoundError(f"staged deck input not found: {src}")
        staged.append((rel, src))
    return tb_bytes, deck_bytes, needs_staging, staged


def _stage_unit(stage, uid, tb_name, deck_bytes, corner_inc_text, needs_staging, staged, datafile):
    """Stage one unit dir under `stage` and return its deck-list entry.

    The per-unit half both deck builders share: the deck bytes, the
    generated `corner.inc`, the pinned run-directory `.spiceinit` (#338,
    transported as a staged deck input because the deck path silently
    drops `options.ngspice_init`), and -- when the testbench references
    the REPO_ROOT token -- the family's staged DUT inputs at their
    repo-relative paths, wrapped as the `{id, deck, timeout_s, inputs[,
    outputs]}` entry, with a declared output colliding with the staged
    `.spiceinit` refused.
    """
    unit = stage / "units" / uid
    unit.mkdir(parents=True, exist_ok=True)
    (unit / tb_name).write_bytes(deck_bytes)
    (unit / "corner.inc").write_text(corner_inc_text, encoding="utf-8")
    (unit / SPICEINIT_NAME).write_text(SPICEINIT_TEXT, encoding="utf-8")
    if needs_staging:
        for rel, src in staged:
            dest = unit / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
    entry = {
        "id": uid,
        "deck": f"units/{uid}/{tb_name}",
        "timeout_s": DECK_TIMEOUT_S,
        "inputs": [{"path": f"units/{uid}/{SPICEINIT_NAME}", "name": SPICEINIT_NAME}],
    }
    if datafile:
        if datafile == SPICEINIT_NAME:
            raise ValueError(
                f"declared output {datafile!r} collides with the staged {SPICEINIT_NAME}"
            )
        entry["outputs"] = [datafile]
    return entry


def _base_deck_request(decks, pdk_dir):
    """The request envelope both builders write; `pdk_dir` must already be
    absolutized by the caller (None leaves `models` unset so the executing
    host resolves the `$PDK_ROOT/...` includes)."""
    request = {"engine": "ngspice", "decks": decks, "options": {"timeout_s": DECK_TIMEOUT_S}}
    if pdk_dir is not None:
        request["models"] = {"pdk_root": os.path.dirname(pdk_dir)}
    return request


def build_request(family, stage_dir, *, pdk_dir=None, repo_root=REPO_ROOT, corner_specs=None):
    """Write per-corner unit dirs under `stage_dir` and return the request dict.

    `pdk_dir` (absolute path to the gf180mcuD variant dir) is written into
    corner.inc verbatim and `models.pdk_root` is set to its parent; by default
    the includes use the literal `$PDK_ROOT/gf180mcuD/...` form, which the
    executing host resolves.

    `corner_specs` (e.g. `["tt:25:3.30"]`) bounds the request to those ratified
    corners -- the bounded parity run the migration needs before cutover. The
    default is the full 27-corner grid. The deck bytes are identical either
    way; only which corners are staged changes, and the selection is recorded
    in `x_gf180_sram_adapter.corners` so `reduce` expects exactly that set.
    """
    exp_dir, tb_name, mode, staged_files = FAMILIES[family]
    kind, datafile, _label = parse_mode(mode)
    tb_bytes, deck_bytes, needs_staging, staged = _load_testbench_and_staged(
        exp_dir, tb_name, staged_files, repo_root
    )

    if pdk_dir is not None:
        pdk_dir = os.path.abspath(pdk_dir)
        design_inc = f"{pdk_dir}/libs.tech/ngspice/design.ngspice"
        model_file = f"{pdk_dir}/libs.tech/ngspice/sm141064.ngspice"
    else:
        design_inc = f"$PDK_ROOT/{DESIGN_INC_REL}"
        model_file = f"$PDK_ROOT/{MODEL_REL}"

    stage = Path(stage_dir)
    selected = select_corners(corner_specs)
    units = []
    for process, temp, vdd in selected:
        cid = corner_id(process, temp, vdd)
        units.append(_stage_unit(
            stage, cid, tb_name, deck_bytes,
            compose_corner_inc(process, temp, vdd, design_inc, model_file),
            needs_staging, staged, datafile,
        ))

    request = _base_deck_request(units, pdk_dir)
    meta = {
        "family": family,
        "mode": mode,
        "testbench": f"{exp_dir}/testbench/{tb_name}",
        "testbench_sha256": _sha256(tb_bytes),
        "composed_deck_sha256": _sha256(deck_bytes),
        "corners": [corner_id(*c) for c in selected],
        "corner_count": len(units),
        # The pinned .spiceinit every unit carries (#338); recorded so the
        # environment the request ran under is auditable from the request.
        "spiceinit_sha256": _sha256(SPICEINIT_TEXT.encode("utf-8")),
        "full_grid": len(selected) == len(corners()),
    }
    # Per-family DUT staging audit (#437): the launcher-equivalent default
    # (the flat bitcell netlist only) adds no key, so the five ratified
    # families' requests stay byte-identical; a family staging anything else
    # records exactly what it stages, with the staged bytes' sha256.
    if list(staged_files) != [DUT_NETLIST]:
        meta["staged_inputs"] = [
            {"path": rel, "sha256": _sha256(src.read_bytes())} for rel, src in staged
        ]
    request["x_gf180_sram_adapter"] = meta
    return request


# --------------------------------------------------------------------------
# Reducer
# --------------------------------------------------------------------------


def _snm_extract_lines(paths, label):
    """snm_extract's stdout+stderr for one SNM measurement: a single sweep
    file, or the L/R pair `--pair` grades. The launcher's `>> log 2>&1`
    shape: every RESULT/RESULT-ERROR line is captured and concatenated,
    and an unreadable or too-short data file is a RESULT-ERROR, never a
    crash."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            pts = [snm_extract.read_xy(str(p)) for p in paths]
            if any(len(p) < 5 for p in pts):
                names = " or ".join(str(p) for p in paths)
                print(f"RESULT-ERROR: {label} -- fewer than 5 data points in {names}", file=sys.stderr)
            else:
                for p in pts:
                    p.sort(key=lambda pt: pt[0])
                snm_extract._run(pts[0], pts[1] if len(pts) > 1 else None, label)
        except (ValueError, OSError) as exc:
            print(f"RESULT-ERROR: {label} -- {exc}", file=sys.stderr)
    return out.getvalue() + err.getvalue()


def _snm_lines(datafile_path, label):
    """snm_extract's stdout+stderr for one data file (launcher: `>> log 2>&1`).

    Kept as its own name: sim/lib/mint_corner_records.py calls it directly
    to mint per-corner record streams."""
    return _snm_extract_lines([datafile_path], label)


def expected_from_request(family, request):
    """(expected corner ids, composed deck sha256) for a request `build` wrote.

    Pinning coverage to the request is what lets a *bounded* run grade as
    `recorded`: without it the reducer expects all 27 corners and a one-corner
    parity run is indistinguishable from a 26-corner loss.
    """
    meta = request.get("x_gf180_sram_adapter") or {}
    if meta.get("campaign") == "monte-carlo":
        raise ValueError("request is a Monte Carlo deck request -- use mc-reduce")
    if meta.get("family") != family:
        raise ValueError(f"request is for family {meta.get('family')!r}, not {family!r}")
    sha = meta.get("composed_deck_sha256")
    if not sha:
        raise ValueError("request has no x_gf180_sram_adapter.composed_deck_sha256")
    ids = list(meta.get("corners") or corner_ids())
    return ids, sha


def unit_stream_relpath(unit, cid, stream, *, base):
    """A unit's raw engine stream location, relative to the report's
    outdir: the path the report's `units[]` entry declares
    (`unit['stdout']` / `unit['stderr']`), falling back to the per-unit
    default layout `<cid>/<stream>.bin`. Every reader of a deck report's
    streams -- the reduce grader, the MC log reader, the record minter
    (`mint_corner_records.py`) -- resolves streams through this one rule,
    so the grading and the evidence minting cannot drift apart (#444).

    `base` is the report's outdir the path resolves against, and the
    resolved path must stay inside it: a declared path that is absolute,
    or whose resolved form is not inside the outdir, refuses fail-closed
    (ValueError) rather than reading outside the run's own output (#448).
    Containment is judged on `Path.resolve()`d paths, so a symlink under
    the outdir pointing outside is caught by the same rule -- resolve()
    semantics is the chosen behaviour."""
    rel = unit.get(stream, f"{cid}/{stream}.bin")
    root = Path(base).resolve()
    resolved = (Path(base) / rel).resolve()
    if Path(rel).is_absolute() or not resolved.is_relative_to(root):
        raise ValueError(
            f"declared {stream} path {rel!r} for unit {cid} is absolute or "
            f"resolves outside the report outdir {root} -- refusing"
        )
    return rel


def _check_deck_coverage(report, expected, expected_deck_sha256, *, missing_label):
    """(coverage_errors, by_id) for a deck report against `expected` ids.

    The fail-closed coverage half both reducers share (#373): the report
    must be a deck-list report; no duplicate, missing, or unexpected unit
    ids; and when composed deck bytes are pinned, every executed unit's
    `deck_sha256` must equal them, with a unit reporting none itself a
    coverage error -- so the deck-bytes check cannot silently not-run.
    `missing_label` names one expected id ("corners" for the deterministic
    grid, "units" for the MC pool) in the missing-coverage error.
    """
    coverage_errors = []
    if report.get("mode") != "decks" or not isinstance(report.get("units"), list):
        coverage_errors.append("report is not a deck-list report (mode != 'decks')")
        units = []
    else:
        units = report["units"]
    ids = [u.get("id") for u in units]
    dupes = sorted({i for i in ids if ids.count(i) > 1}, key=str)
    if dupes:
        coverage_errors.append(f"duplicate unit ids: {dupes}")
    missing = [c for c in expected if c not in ids]
    extra = [i for i in ids if i not in expected]
    if missing:
        coverage_errors.append(f"missing {missing_label}: {missing}")
    if extra:
        coverage_errors.append(f"unexpected unit ids: {extra}")
    if expected_deck_sha256 is not None:
        drifted = sorted(
            (u.get("id") for u in units
             if u.get("deck_sha256") is not None and u.get("deck_sha256") != expected_deck_sha256),
            key=str,
        )
        if drifted:
            coverage_errors.append(f"deck bytes differ from the composed deck for: {drifted}")
        unreported = sorted(
            (u.get("id") for u in units if u.get("deck_sha256") is None),
            key=str,
        )
        if unreported:
            coverage_errors.append(f"deck_sha256 not reported for: {unreported}")
    by_id = {}
    for u in units:
        by_id.setdefault(u.get("id"), u)
    return coverage_errors, by_id


def _read_log(base, unit, uid):
    """A unit's captured stdout+stderr text, resolved through
    unit_stream_relpath's one stream rule (#444) -- the same rule the
    record minter reads by -- with a stream that is not a file
    contributing nothing."""
    log = ""
    for stream in ("stdout", "stderr"):
        p = base / unit_stream_relpath(unit, uid, stream, base=base)
        if p.is_file():
            log += p.read_bytes().decode("utf-8", errors="replace")
    return log


def _unit_infra_reasons(unit):
    """The engine-level OPEN reasons one report unit contributes: it timed
    out, never ran, or lacked a declared output."""
    reasons = []
    if unit.get("timed_out") or unit.get("status") == "timeout":
        reasons.append("engine timed out")
    elif unit.get("exit_code") is None:
        reasons.append("engine never ran")
    if unit.get("missing_outputs"):
        reasons.append(f"declared outputs missing: {unit['missing_outputs']}")
    return reasons


def reduce_report(family, report, *, outdir=None, expected_ids=None, expected_deck_sha256=None):
    """Grade a `klt sim` deck report with the launcher's rules.

    Returns {"family", "expected", "coverage_errors", "corners": [...],
    "overall"}; overall is "recorded" only if coverage is exact and every
    corner produced a RESULT with no RESULT-ERROR, else "OPEN".

    `expected_ids` (from `expected_from_request`) bounds the expected coverage
    to the corners the request actually asked for; the default is the full
    27-corner grid. `expected_deck_sha256`, when given, must equal every
    unit's reported `deck_sha256` -- the deck-bytes-unchanged claim, checked
    rather than assumed. A unit whose `deck_sha256` is None or absent is
    itself a coverage error ("deck_sha256 not reported for: [...]"): a check
    that cannot run must never look like one that passed.
    """
    _exp, _tb, mode, _staged = FAMILIES[family]
    kind, datafile, label = parse_mode(mode)
    if expected_ids is None:
        expected = corner_ids()
    else:
        expected = list(expected_ids)
        if not expected:
            raise ValueError("expected corner list is empty")
        unknown = [c for c in expected if c not in corner_ids()]
        if unknown:
            raise ValueError(f"not ratified corner ids: {unknown}")
    base = Path(outdir or report.get("outdir") or ".")

    coverage_errors, by_id = _check_deck_coverage(
        report, expected, expected_deck_sha256, missing_label="corners"
    )

    graded = []
    for cid in expected:
        unit = by_id.get(cid)
        if unit is None:
            graded.append({"id": cid, "status": "OPEN", "reasons": ["no unit in report"], "results": {}, "result_lines": []})
            continue
        reasons = _unit_infra_reasons(unit)
        unit_dir = base / cid
        log = _read_log(base, unit, cid)
        if kind == "snm":
            data = unit_dir / datafile
            if data.is_file():
                log += _snm_lines(data, label)
            else:
                log += f"RESULT-ERROR: {label} -- expected data file {datafile} not produced\n"
        errors = RESULT_ERROR_RE.findall(log)
        results, result_lines = {}, []
        for m in RESULT_RE.finditer(log):
            results[m.group(1)] = float(m.group(2))
            result_lines.append(m.group(0))
        reasons += errors
        if not errors and not results:
            reasons.append(f"no RESULT line captured (engine exit {unit.get('exit_code')})")
        graded.append(
            {
                "id": cid,
                "status": "OPEN" if reasons else "recorded",
                "reasons": reasons,
                "results": results,
                "result_lines": result_lines,
                "engine_exit_code": unit.get("exit_code"),
                "deck_sha256": unit.get("deck_sha256"),
            }
        )

    ok = not coverage_errors and all(g["status"] == "recorded" for g in graded)
    return {
        "family": family,
        "mode": mode,
        "expected": expected,
        "expected_deck_sha256": expected_deck_sha256,
        "coverage_errors": coverage_errors,
        "corners": graded,
        "overall": "recorded" if ok else "OPEN",
    }


# --------------------------------------------------------------------------
# Monte Carlo (run_mc_campaign.py pool) -- offline deck-mode migration path
# --------------------------------------------------------------------------

# Per-family MC mode (run_mc_campaign.py --mode) and default --key. The SNM
# fixtures use the two-instance `snm-pair` mode (module docstring of
# run_mc_campaign.py); the others are `direct`.
MC_FAMILIES = {
    "read-snm": ("snm-pair:read_snm_sweep.txt:read_snm", "read_snm_v"),
    "hold-snm": ("snm-pair:hold_snm_sweep.txt:hold_snm", "hold_snm_v"),
    "write-margin": ("direct", "write_trip_voltage_v"),
    "read-access": ("direct", "read_access_time_s"),
    "write-access": ("direct", "write_access_time_s"),
}
MC_UNIT_PREFIX = "mc"
# Batch kinds, in the order run_mc_campaign.main() runs them, with the
# sw_stat_mismatch each uses (None = the caller's --nc-mismatch-scale).
MC_KINDS = (("mm", 1), ("ctrl", 0), ("nc", None))

RESULT_RE = mc.RESULT_RE
RESULT_ERROR_RE = mc.RESULT_ERROR_RE


def parse_mc_mode(mode):
    """('direct',None,None) | ('snm',datafile,label) | ('snm-pair',datafile,label)."""
    if mode == "direct":
        return "direct", None, None
    for prefix in ("snm-pair", "snm"):
        if mode.startswith(prefix + ":"):
            _, datafile, label = mode.split(":", 2)
            return prefix, datafile, label
    raise ValueError(f"unsupported MC mode {mode!r}")


def mc_unit_id(cid, kind, index, side=None):
    base = f"{MC_UNIT_PREFIX}.{cid}.{kind}.{index:05d}"
    return f"{base}.{side}" if side else base


def _parse_corner(spec):
    parts = spec.split(":")
    if len(parts) != 3 or parts[0] not in mc.LIB_SECTION:
        raise ValueError(f"corner {spec!r} must be process:temp:vdd with process in {sorted(mc.LIB_SECTION)}")
    return tuple(parts)


def mc_plan(family, corner_specs, *, n, n_control, n_nc, seed, nc_mismatch_scale=1.0, nc_vdd=None):
    """Ordered manifest of every sample unit; seeds come from mc.derive_seed."""
    mode, _key = MC_FAMILIES[family]
    kind_of_mode = parse_mc_mode(mode)[0]
    counts = {"mm": n, "ctrl": n_control, "nc": n_nc}
    manifest = []
    for spec in corner_specs:
        process, temp, vdd = _parse_corner(spec)
        cid = mc.corner_id(process, temp, vdd)
        for kind, sw in MC_KINDS:
            sw = nc_mismatch_scale if sw is None else sw
            unit_vdd = nc_vdd if (kind == "nc" and nc_vdd is not None) else vdd
            for i in range(max(0, counts[kind])):
                sides = ("L", "R") if kind_of_mode == "snm-pair" else (None,)
                for side in sides:
                    k = f"{kind}-{side}" if side else kind
                    manifest.append({
                        "id": mc_unit_id(cid, kind, i, side),
                        "corner_id": cid, "process": process, "temp": temp, "vdd": unit_vdd,
                        "kind": kind, "index": i, "side": side,
                        "seed": mc.derive_seed(seed, cid, k, i),
                        "sw_stat_mismatch": sw,
                    })
    return manifest


def build_mc_request(family, stage_dir, corner_specs, *, n, n_control, n_nc, seed,
                     nc_mismatch_scale=1.0, nc_vdd=None, pdk_dir=None, repo_root=REPO_ROOT):
    """Stage one unit dir per MC sample and return the deck-list request.

    Request fields are `decks`/`options`/`models` only -- no generated-corner or
    `monte_carlo` fields. The plan (seed per unit) rides in `x_gf180_sram_adapter`.
    """
    if len(corner_specs) < 2:
        raise ValueError("at least two corners are required (nominal-only is not an MC campaign)")
    exp_dir, tb_name, _, staged_files = FAMILIES[family]
    mode, key = MC_FAMILIES[family]
    kind, datafile, _label = parse_mc_mode(mode)
    tb_bytes, deck_bytes, needs_staging, staged = _load_testbench_and_staged(
        exp_dir, tb_name, staged_files, repo_root
    )
    if pdk_dir is not None:
        pdk_dir = os.path.abspath(pdk_dir)
        model_file = f"{pdk_dir}/libs.tech/ngspice/sm141064.ngspice"
    else:
        model_file = f"$PDK_ROOT/{MODEL_REL}"

    manifest = mc_plan(family, corner_specs, n=n, n_control=n_control, n_nc=n_nc, seed=seed,
                       nc_mismatch_scale=nc_mismatch_scale, nc_vdd=nc_vdd)
    stage = Path(stage_dir)
    decks = []
    for m in manifest:
        inc = mc.build_corner_inc({"GF180_MODEL_FILE": model_file}, m["process"], m["temp"],
                                  m["vdd"], m["seed"], m["sw_stat_mismatch"])
        m["corner_inc_sha256"] = _sha256(inc.encode("utf-8"))
        decks.append(_stage_unit(stage, m["id"], tb_name, deck_bytes, inc,
                                 needs_staging, staged, datafile))

    request = _base_deck_request(decks, pdk_dir)
    request["x_gf180_sram_adapter"] = {
        "campaign": "monte-carlo",
        "family": family,
        "mode": mode,
        "key": key,
        "testbench": f"{exp_dir}/testbench/{tb_name}",
        "testbench_sha256": _sha256(tb_bytes),
        "composed_deck_sha256": _sha256(deck_bytes),
        "base_seed": seed,
        "corners": [mc.corner_id(*_parse_corner(c)) for c in corner_specs],
        "n_mismatch": n, "n_determinism_control": n_control, "n_negative_control": n_nc,
        "nc_mismatch_scale": nc_mismatch_scale, "nc_vdd": nc_vdd,
        # The pinned .spiceinit every unit carries (#338); see build_request.
        "spiceinit_sha256": _sha256(SPICEINIT_TEXT.encode("utf-8")),
        "units": manifest,
    }
    return request


def _snm_pair_lines(path_l, path_r, label):
    """snm_extract.py --pair's stdout+stderr, in-process."""
    return _snm_extract_lines([path_l, path_r], label)


def reduce_mc_report(family, request, report, *, outdir=None, key=None, limit_min=0.0):
    """Regroup a deck report into run_batch/run_batch_pair-shaped results.

    Returns {"batches": {corner_id: {kind: {"seed_labels": [...],
    "samples": [(index, results, errors), ...]}}}, "measurements": [...],
    "coverage_errors", "infra_failures", "expected_deck_sha256", "overall"}.
    `samples` is in sample order (seed order) exactly as run_batch returns it;
    `measurements` is the `klt yield` sample-set measurement list
    run_mc_campaign.main() builds. `overall` is "recorded" only if coverage
    is exact, every unit's `deck_sha256` equals the request's composed deck
    bytes, and no unit timed out, never ran, lacked a declared output, or
    exited without any RESULT line; a RESULT-ERROR (e.g. a non-bistable
    draw) stays an errored sample, as in the pool. A request without a
    `composed_deck_sha256` -- or a unit that reports none -- is itself a
    coverage error, so the deck check cannot silently not-run. Exit 0 is
    never read as a PASS.
    """
    meta = request.get("x_gf180_sram_adapter") or {}
    mode, default_key = MC_FAMILIES[family]
    kind, datafile, label = parse_mc_mode(mode)
    key = key or default_key
    manifest = meta.get("units") or []
    composed = meta.get("composed_deck_sha256") or None
    base = Path(outdir or report.get("outdir") or ".")

    coverage_errors = []
    if meta.get("campaign") != "monte-carlo" or meta.get("family") != family:
        coverage_errors.append("request is not a Monte Carlo request for this family")
    if composed is None:
        coverage_errors.append("request has no x_gf180_sram_adapter.composed_deck_sha256")
    for m in manifest:  # seed identity: the request must still carry derive_seed's values
        k = f"{m['kind']}-{m['side']}" if m.get("side") else m["kind"]
        if m["seed"] != mc.derive_seed(meta.get("base_seed"), m["corner_id"], k, m["index"]):
            coverage_errors.append(f"seed drift for {m['id']}")
    expected = [m["id"] for m in manifest]
    deck_errors, by_id = _check_deck_coverage(report, expected, composed, missing_label="units")
    coverage_errors += deck_errors

    infra = []

    def unit_state(uid):
        """(log text, data-file path, infra reasons) for one deck unit."""
        unit = by_id.get(uid)
        if unit is None:
            return "", None, ["no unit in report"]
        reasons = _unit_infra_reasons(unit)
        return _read_log(base, unit, uid), (base / uid / datafile if datafile else None), reasons

    # sample index -> (results, errors) per (corner, kind)
    grouped = {}
    seed_labels = {}
    for m in manifest:
        grouped.setdefault((m["corner_id"], m["kind"]), {}).setdefault(m["index"], {})[m["side"]] = m
    for (cid, knd), by_index in grouped.items():
        samples, labels = [], []
        for i in sorted(by_index):
            sides = by_index[i]
            notes, results = [], {}
            log = ""
            if kind == "snm-pair":
                paths = {}
                for side in ("L", "R"):
                    m = sides[side]
                    text, data, reasons = unit_state(m["id"])
                    for r in reasons:
                        notes.append(f"{side}: {r}")
                        infra.append({"id": m["id"], "reason": r})
                    if data is not None and data.is_file():
                        paths[side] = data
                    elif not reasons:
                        notes.append(f"{side}: expected data file {datafile} not produced")
                        infra.append({"id": m["id"], "reason": f"data file {datafile} not produced"})
                labels.append(f"L={sides['L']['seed']},R={sides['R']['seed']}")
                if len(paths) == 2:
                    log = _snm_pair_lines(paths["L"], paths["R"], label)
            else:
                m = sides[None]
                text, data, reasons = unit_state(m["id"])
                for r in reasons:
                    notes.append(r)
                    infra.append({"id": m["id"], "reason": r})
                log = text
                if kind == "snm":
                    if data is not None and data.is_file():
                        log += _snm_lines(data, label)
                    else:
                        log += f"RESULT-ERROR: {label} -- expected data file {datafile} not produced\n"
                labels.append(str(m["seed"]))
            results = {k: float(v) for k, v in RESULT_RE.findall(log)}
            errors = RESULT_ERROR_RE.findall(log)
            if not errors and not results and not notes:
                notes.append("no RESULT line captured")
                for m in sides.values():
                    infra.append({"id": m["id"], "reason": "exit without RESULT"})
            samples.append((i, results, notes + errors))
        seed_labels[(cid, knd)] = labels
        grouped[(cid, knd)] = samples

    batches, measurements = {}, []
    nc_desc = (f"known-bad variant: sw_stat_mismatch={meta.get('nc_mismatch_scale'):g}"
               + (f", VDD={meta['nc_vdd']} V" if meta.get("nc_vdd") is not None else "")) \
        if meta.get("n_negative_control", 0) > 0 else None

    def tally(samples):
        values, errored = [], 0
        for _i, results, errs in samples:
            if errs or key not in results:
                errored += 1
            else:
                values.append(results[key])
        return values, errored

    for cid in meta.get("corners", []):
        per_kind = {}
        for knd, _sw in MC_KINDS:
            if (cid, knd) in grouped:
                per_kind[knd] = {"seed_labels": seed_labels[(cid, knd)], "samples": grouped[(cid, knd)]}
        batches[cid] = per_kind
        if "mm" not in per_kind:
            continue
        vals, errored = tally(per_kind["mm"]["samples"])
        measurement = {"name": f"{key}@{cid}", "unit": "V", "samples": vals, "errored": errored,
                       "limits": {"min": limit_min}, "source_corners": [cid]}
        if "nc" in per_kind:
            nvals, nerr = tally(per_kind["nc"]["samples"])
            measurement["negative_control"] = {"samples": nvals, "errored": nerr, "description": nc_desc}
        measurements.append(measurement)

    ok = not coverage_errors and not infra
    return {
        "family": family, "mode": mode, "key": key, "expected_units": len(expected),
        "expected_deck_sha256": composed,
        "coverage_errors": coverage_errors, "infra_failures": infra,
        "batches": batches, "measurements": measurements,
        "overall": "recorded" if ok else "OPEN",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("families")
    sub.add_parser(
        "spiceinit",
        help="print SPICEINIT_TEXT -- the pinned run-directory .spiceinit "
        "(#338). Both builders stage it as a per-unit deck input; a local "
        "single-point probe redirects this verb's stdout into its scratch "
        "directory's .spiceinit so a hand-run pins the same environment "
        "deck mode stages",
    )
    b = sub.add_parser("build")
    b.add_argument("family", choices=sorted(FAMILIES))
    b.add_argument("--stage-dir", required=True)
    b.add_argument("--request-out", required=True)
    b.add_argument("--pdk-dir")
    b.add_argument("--corner", action="append", dest="corners", metavar="process:temp:vdd",
                   help="bound the request to this ratified corner (repeatable; default: all 27)")
    r = sub.add_parser("reduce")
    r.add_argument("family", choices=sorted(FAMILIES))
    r.add_argument("report")
    r.add_argument("--outdir")
    r.add_argument("--json-out")
    r.add_argument("--request",
                   help="the request `build` wrote: expect exactly its corners and deck sha256 "
                        "(required to grade a bounded run; without it all 27 corners are expected)")
    mb = sub.add_parser("mc-build")
    mb.add_argument("family", choices=sorted(MC_FAMILIES))
    mb.add_argument("--corner", action="append", required=True, dest="corners", metavar="process:temp:vdd")
    mb.add_argument("--n", type=int, default=100)
    mb.add_argument("--n-control", type=int, default=8)
    mb.add_argument("--n-nc", type=int, default=0)
    mb.add_argument("--nc-mismatch-scale", type=float, default=1.0)
    mb.add_argument("--nc-vdd", default=None)
    mb.add_argument("--seed", type=int, required=True)
    mb.add_argument("--stage-dir", required=True)
    mb.add_argument("--request-out", required=True)
    mb.add_argument("--pdk-dir")
    mr = sub.add_parser("mc-reduce")
    mr.add_argument("family", choices=sorted(MC_FAMILIES))
    mr.add_argument("request")
    mr.add_argument("report")
    mr.add_argument("--outdir")
    mr.add_argument("--key")
    mr.add_argument("--limit-min", type=float, default=0.0)
    mr.add_argument("--json-out")
    args = ap.parse_args(argv)

    if args.cmd == "mc-build":
        req = build_mc_request(
            args.family, args.stage_dir, args.corners, n=args.n, n_control=args.n_control,
            n_nc=args.n_nc, seed=args.seed, nc_mismatch_scale=args.nc_mismatch_scale,
            nc_vdd=args.nc_vdd, pdk_dir=args.pdk_dir,
        )
        Path(args.request_out).write_text(json.dumps(req, indent=2) + "\n")
        print(f"wrote {len(req['decks'])} decks; request: {args.request_out}")
        return 0
    if args.cmd == "mc-reduce":
        request = json.loads(Path(args.request).read_text())
        report = json.loads(Path(args.report).read_text())
        result = reduce_mc_report(args.family, request, report, outdir=args.outdir,
                                  key=args.key, limit_min=args.limit_min)
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(result, indent=2) + "\n")
        for m in result["measurements"]:
            print(f"{m['name']}: {len(m['samples'])} ok, {m['errored']} open")
        for e in result["coverage_errors"]:
            print(f"COVERAGE: {e}", file=sys.stderr)
        for f in result["infra_failures"]:
            print(f"OPEN: {f['id']}: {f['reason']}", file=sys.stderr)
        print(f"overall: {result['overall']}")
        return 0 if result["overall"] == "recorded" else 1

    if args.cmd == "families":
        for name, (d, tb, mode, staged) in sorted(FAMILIES.items()):
            print(f"{name}\t{d}/testbench/{tb}\t{mode}\t{','.join(staged)}")
        return 0
    if args.cmd == "spiceinit":
        # Byte-exact stdout (no print()'s trailing-newline doubling): a
        # local single-point probe redirects this straight into its scratch
        # .spiceinit, and the test suite asserts those bytes equal
        # SPICEINIT_TEXT.
        sys.stdout.write(SPICEINIT_TEXT)
        return 0
    if args.cmd == "build":
        req = build_request(args.family, args.stage_dir, pdk_dir=args.pdk_dir,
                            corner_specs=args.corners)
        Path(args.request_out).write_text(json.dumps(req, indent=2) + "\n")
        print(f"wrote {len(req['decks'])} decks; request: {args.request_out}")
        return 0
    report = json.loads(Path(args.report).read_text())
    expected_ids = expected_sha = None
    if args.request:
        expected_ids, expected_sha = expected_from_request(
            args.family, json.loads(Path(args.request).read_text())
        )
    result = reduce_report(args.family, report, outdir=args.outdir,
                           expected_ids=expected_ids, expected_deck_sha256=expected_sha)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2) + "\n")
    for c in result["corners"]:
        print(f"{c['id']}: {c['status']} {c['results'] or c['reasons']}")
    for e in result["coverage_errors"]:
        print(f"COVERAGE: {e}", file=sys.stderr)
    print(f"overall: {result['overall']}")
    return 0 if result["overall"] == "recorded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
