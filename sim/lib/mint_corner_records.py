#!/usr/bin/env python3
"""sim/lib/mint_corner_records.py -- mint an append-only corner evidence
record from a graded `klt sim` deck-mode run (#437).

The #230 cutover retired `sim/lib/run_corner_sweep.sh`, which both ran the
27-corner grid AND minted the append-only evidence record
(`records/<record-id>.md`, `corners/<record-id>/<corner-id>.log`,
`netlist-snapshots/<record-id>.spice`). Deck mode replaces only the first
half: `deck_adapter.py build` stages, `klt sim` runs, `deck_adapter.py
reduce` grades. This module is the second half -- the record minter the
by-hand pex write-margin legs (#95, deck port #437) need to regenerate
their append-only evidence. The reference-record half of the same gap is
filled by `sim/lib/mint_records.py` (#272), which also mints the SNM and
Monte Carlo families this module deliberately refuses -- see its docstring
for the split.

It writes exactly the record format every `sim/<experiment>/` directory
uses (sim/README.md "Summary record format"; the byte template is the
retired launcher's), from a `deck_adapter.py reduce` grading -- never from
an engine exit status, and never from an offline stub. Fail-closed rules:

* the grading must be a full-grid `reduce` output for this family with
  zero coverage errors -- a bounded parity run grades decks, it never
  mints a record claiming the full ratified matrix;
* only `direct`-mode families are mintable here -- the SNM families'
  committed records are launcher-era evidence, not regenerated through
  this path (their deck-mode migration went through the parity receipts);
* every corner graded `recorded` must have its raw engine stdout/stderr
  under the unit dir -- a record whose raw log is missing is not minted;
* any existing artifact for the record id (record, snapshot, corners dir)
  makes the mint refuse: append-only means never overwrite.

A corner graded `OPEN` does not block a mint (the launcher minted OPEN
records too -- an open result is recorded as open, never dropped, per
spec/sram.md's Signoff definition); the record's Overall line says so
honestly, and `sim/pex/write-margin/generate.sh` gates its own flow on the
grading being fully `recorded` before minting.

One deliberate improvement over the retired launcher: its **Netlist
provenance** field was boilerplate that always named
`design/netlist/bitcell_6t.spice` regardless of the DUT the testbench
actually `.include`s (documented as a known cosmetic limitation in
`sim/pex/README.md`). The minter names the family's real staged DUT
file(s), and the pex legs' provenance word says `extracted` where the
launcher's copy said `schematic`.

Usage:
    mint_corner_records.py <family> <reduced.json> --request REQUEST.json
                           --report REPORT.json --unit-dir DIR --claim TEXT
                           [--supersedes TEXT] [--exp-dir DIR]

`reduced.json` is `deck_adapter.py reduce ... --json-out`'s output;
`--report` is the same `klt sim` report `reduce` graded (its `units[]`
declare each unit's stream paths); `--unit-dir` is the same outdir
`klt sim -o` wrote and `reduce --outdir` read. Each unit's raw
stdout/stderr resolve through `deck_adapter.unit_stream_relpath` -- the
report's declared `units[].stdout`/`.stderr`, falling back to the default
per-unit layout `<corner-id>/stdout.bin` + `stderr.bin` -- the identical
rule the grader used (#444). The experiment directory defaults to the
family's own under the repo root; `--exp-dir` exists for offline tests.
Prints `record-id: <id>` on success.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deck_adapter as da  # noqa: E402
from corner_matrix import corner_id, corners  # noqa: E402
from repo_root import find_repo_root  # noqa: E402

REPO_ROOT = find_repo_root(Path(__file__))

# The record's **Netlist provenance** word per family. Every family in the
# repo whose records predate the pex workflow is a schematic-side run (the
# launcher hard-coded this word -- see the module docstring's honesty note),
# so "schematic" is the honest default; the extracted pex leg overrides.
PROVENANCE_WORD = {
    "pex-write-margin-schematic": "schematic",
    "pex-write-margin-extracted": "extracted",
}
DEFAULT_PROVENANCE_WORD = "schematic"


def _git_short_sha(repo_root: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip() if out.returncode == 0 else "nogit"


def new_record_id(repo_root: Path = REPO_ROOT) -> str:
    """`<YYYYMMDD>-<HHMMSS>-<short-git-sha>` -- the launcher's convention
    (sim/README.md); sorts chronologically as a plain string."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{_git_short_sha(repo_root)}"


def _corner_axes():
    """{corner_id: (process, temp, vdd)} from the one ratified source."""
    return {corner_id(*c): c for c in corners()}


def _result_row(entry) -> str:
    """The record's per-corner Result row body, launcher-shaped: the raw
    `RESULT:` lines joined by `;` -- the launcher grep'd whole lines and
    `tr`'d their newlines to `;`, so each line is newline-terminated before
    the join regardless of whether the grading regex kept it. An OPEN corner
    renders an `OPEN -- ...` note listing the grading reasons."""
    if entry["status"] == "recorded":
        lines = [ln if ln.endswith("\n") else ln + "\n" for ln in entry["result_lines"]]
        return "".join(lines).replace("\n", ";")
    reasons = "; ".join(entry.get("reasons") or ["no RESULT line captured"])
    return f"OPEN -- {reasons}; see the corner log under corners/"


def mint_record(
    family,
    reduced,
    request,
    *,
    report,
    unit_dir,
    exp_dir,
    record_id,
    claim,
    supersedes="",
    repo_root=REPO_ROOT,
    timestamp=None,
):
    """Write the three append-only artifacts; returns the record's Path.

    Refuses (ValueError) on every fail-closed rule in the module docstring.
    `report` is the `klt sim` deck report `reduced` was graded from -- the
    minter resolves each unit's raw streams from its `units[]` declaration
    with the same rule as the grader (`deck_adapter.unit_stream_relpath`),
    never from a second hardcoded layout. `record_id` and `timestamp` are
    parameters only so offline tests are deterministic; the CLI derives
    both from the clock/git.
    """
    exp_dir_default, tb_name, mode, staged_files = da.FAMILIES[family]
    kind, _datafile, _label = da.parse_mode(mode)
    if kind != "direct":
        raise ValueError(
            f"{family}: record minting supports direct-mode families only "
            "(the SNM families' committed records are launcher-era evidence, "
            "not regenerated through this path)"
        )
    meta = request.get("x_gf180_sram_adapter") or {}
    if meta.get("campaign") == "monte-carlo":
        raise ValueError("request is a Monte Carlo deck request -- no corner record mints from it")
    if meta.get("family") != family:
        raise ValueError(f"request is for family {meta.get('family')!r}, not {family!r}")
    if not meta.get("full_grid"):
        raise ValueError(
            "request is not a full-grid request: a record claims the full "
            "ratified 27-corner matrix, so a bounded parity run never mints one"
        )
    if reduced.get("family") != family:
        raise ValueError(f"reduced report is for family {reduced.get('family')!r}, not {family!r}")
    if reduced.get("coverage_errors"):
        raise ValueError(f"reduced report has coverage errors: {reduced['coverage_errors']}")
    expected = reduced.get("expected") or []
    grid = [corner_id(*c) for c in corners()]
    if expected != grid:
        raise ValueError(
            "reduced report did not grade the full ratified corner grid "
            f"({len(expected)} corners) -- refusing to mint a partial record"
        )
    graded = reduced.get("corners") or []
    if [c.get("id") for c in graded] != grid:
        raise ValueError(
            "reduced report has no graded entry for every ratified corner "
            f"({len(graded)} graded) -- refusing to mint a record with a "
            "missing corner row"
        )
    if report.get("mode") != "decks" or not isinstance(report.get("units"), list):
        raise ValueError(
            "report is not a deck-list report (mode != 'decks') -- cannot "
            "resolve unit stream paths"
        )
    report_units = {}
    for u in report["units"]:
        report_units.setdefault(u.get("id"), u)

    exp = Path(exp_dir)
    tb_path = exp / "testbench" / tb_name
    if not tb_path.is_file():
        raise FileNotFoundError(f"testbench not found under experiment dir: {tb_path}")
    if tb_path.read_bytes() != (Path(repo_root) / meta["testbench"]).read_bytes():
        raise ValueError(
            f"experiment dir's testbench differs from the request's source "
            f"({meta['testbench']}) -- the record must snapshot the run's own deck source"
        )
    provenance_word = PROVENANCE_WORD.get(family, DEFAULT_PROVENANCE_WORD)

    record_md = exp / "records" / f"{record_id}.md"
    snapshot = exp / "netlist-snapshots" / f"{record_id}.spice"
    corners_dir = exp / "corners" / record_id
    for path in (record_md, snapshot, corners_dir):
        if path.exists():
            raise ValueError(f"append-only: {path} already exists -- records are never overwritten")

    by_id = {c["id"]: c for c in graded}
    axes = _corner_axes()

    unit = Path(unit_dir)
    log_bodies = {}
    for cid, (process, temp, vdd) in axes.items():
        entry = by_id.get(cid)
        if entry is not None and entry.get("status") == "recorded" and cid not in report_units:
            raise ValueError(
                f"recorded corner {cid} has no unit in the report -- the "
                "reduced grading and the report disagree; refusing"
            )
        unit_entry = report_units.get(cid, {})
        streams = []
        for stream in ("stdout", "stderr"):
            rel = da.unit_stream_relpath(unit_entry, cid, stream)
            p = unit / rel
            if p.is_file():
                streams.append(p.read_bytes().decode("utf-8", errors="replace"))
            elif entry is not None and entry.get("status") == "recorded":
                raise ValueError(f"raw {rel} missing for recorded corner {cid} under {unit}")
        streams.append(f"=== corner: {cid} (process={process} temp={temp}C vdd={vdd}V) ===\n")
        streams.append(f"=== ngspice exit status: {entry.get('engine_exit_code') if entry else None} ===\n")
        log_bodies[cid] = "".join(streams)

    open_count = sum(1 for c in graded if c["status"] != "recorded")
    short_sha = _git_short_sha(repo_root)
    staged_clause = ", ".join(f"`{rel}`" for rel in staged_files)
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def rel(p: Path) -> str:
        # In production the experiment dir lives under the repo root, and the
        # launcher's Links fields are repo-relative; an overridden exp dir
        # (offline tests) falls back to exp-dir-relative paths.
        p = p.resolve()
        try:
            return p.relative_to(Path(repo_root).resolve()).as_posix()
        except ValueError:
            return p.relative_to(exp.resolve()).as_posix()

    lines = [
        f"# Record {record_id}",
        "",
        f"- **Record ID**: {record_id}",
        f"- **Claim**: {claim}",
        f"- **Netlist provenance**: {provenance_word} (`{rel(tb_path)}`, DUT per {staged_clause} at `{short_sha}`)",
        "- **Corner matrix run**:",
        "  - Process: ff tt ss",
        "  - Temperature: -40 25 125 C",
        "  - Supply: 2.97 3.30 3.63 V",
        "  - (27 corner points total -- full process x temp x supply matrix, per spec/sram.md's ratified corner set)",
        "- **Statistical convention**: N/A (corner-matrix claim, not a distribution claim)",
        "- **Result**:",
    ]
    for cid in axes:
        entry = by_id.get(cid)
        body = _result_row(entry) if entry is not None else "OPEN -- no unit in the graded report"
        lines.append(f"  - **{cid}**: {body}")
    if open_count:
        lines.append(
            "  - **Overall: OPEN** -- at least one corner did not produce a valid measured result "
            "(see per-corner notes above); per spec/sram.md's Signoff definition this corner is "
            "recorded as an open result, not dropped from the corner set."
        )
    else:
        lines.append(
            "  - **Overall: recorded** -- all 27 corners produced a measured result; see "
            "sim/README.md for how to interpret sign-off against spec/sram.md's positive-margin "
            "requirement."
        )
    lines += [
        "- **Links**:",
        f"  - Testbench: `{rel(tb_path)}`",
        f"  - Netlist snapshot: `{rel(snapshot)}`",
        f"  - Raw logs: `{rel(corners_dir)}/`",
        f"- **Timestamp / author**: {ts}, agent-builder",
    ]
    lines.append(
        f"- **Supersedes**: {supersedes}"
        if supersedes
        else "- **Supersedes**: (none -- first record for this claim)"
    )

    corners_dir.mkdir(parents=True, exist_ok=True)
    for cid, body in log_bodies.items():
        (corners_dir / f"{cid}.log").write_text(body, encoding="utf-8")
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tb_path, snapshot)
    record_md.parent.mkdir(parents=True, exist_ok=True)
    record_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {len(log_bodies)} corner logs under {corners_dir}")
    print(f"Wrote netlist snapshot: {snapshot}")
    print(f"Wrote record: {record_md}")
    print(f"overall: {'OPEN' if open_count else 'recorded'} ({len(graded)} corners, {open_count} open)")
    return record_md


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("family", choices=sorted(da.FAMILIES))
    ap.add_argument("reduced", help="deck_adapter.py reduce --json-out output")
    ap.add_argument("--request", required=True, help="the request `build` wrote")
    ap.add_argument("--report", required=True,
                    help="the `klt sim` report `reduce` graded (its units[] "
                         "declare each unit's stream paths)")
    ap.add_argument("--unit-dir", required=True,
                    help="klt sim's -o outdir (and reduce's --outdir); stream "
                         "paths resolve per the report's declaration, "
                         "defaulting to per-unit <cid>/stdout.bin")
    ap.add_argument("--claim", required=True,
                    help="the spec/sram.md claim this record substantiates (written verbatim)")
    ap.add_argument("--supersedes", default="",
                    help="record id (plus explanation) this run supersedes")
    ap.add_argument("--exp-dir",
                    help="experiment dir (default: the family's own under the repo root; "
                         "offline tests override)")
    args = ap.parse_args(argv)

    reduced = json.loads(Path(args.reduced).read_text())
    request = json.loads(Path(args.request).read_text())
    report = json.loads(Path(args.report).read_text())
    exp_dir = args.exp_dir or str(Path(REPO_ROOT) / da.FAMILIES[args.family][0])
    record_md = mint_record(
        args.family, reduced, request,
        report=report,
        unit_dir=args.unit_dir, exp_dir=exp_dir,
        record_id=new_record_id(), claim=args.claim, supersedes=args.supersedes,
    )
    print(f"record-id: {record_md.stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
