#!/usr/bin/env python3
"""sim/lib/mint_corner_records.py -- mint an append-only corner evidence
record from a graded `klt sim` deck-mode run (#437).

The #230 cutover retired `sim/lib/run_corner_sweep.sh`, which both ran the
27-corner grid AND minted the append-only evidence record
(`records/<record-id>.md`, `corners/<record-id>/<corner-id>.log`,
`netlist-snapshots/<record-id>.spice`). Deck mode replaces only the first
half: `deck_adapter.py build` stages, `klt sim` runs, `deck_adapter.py
reduce` grades. This module is the second half -- the record minter the
by-hand pex write-margin legs (#95, deck port #437) and the reference
families (#272) mint with.

Two corner minters grew in parallel on 2026-11-17 while #272 and #437 were
both in flight -- this one and `sim/lib/mint_records.py`'s `mint_corner` --
and had already drifted apart (netlist provenance, fail-closed coverage
rules, record line shapes). #452 consolidated them: this module is now the
**single** deterministic corner-record minter, for every family in
`deck_adapter.FAMILIES` -- the five ratified characterization families,
whose Claim strings `FAMILY_CLAIMS` below owns, and the by-hand pex
write-margin legs, which pass theirs via `--claim`. `sim/lib/
mint_records.py` keeps only the Monte Carlo path (`mint_mc`), which has no
counterpart here, and its `corner` CLI subcommand delegates to this module.

It writes exactly the record format every `sim/<experiment>/` directory
uses (sim/README.md "Summary record format"; the byte template is the
retired launcher's), from a `deck_adapter.py reduce` grading -- never from
an engine exit status, and never from an offline stub. Fail-closed rules:

* the grading must be a full-grid `reduce` output for this family with
  zero coverage errors -- a bounded parity run grades decks, it never
  mints a record claiming the full ratified matrix;
* the grading must pin this request's composed deck sha256, and the
  experiment dir's testbench must still compose to exactly those deck
  bytes -- the netlist snapshot is the composed deck (the bytes that
  actually ran), checked against the request rather than assumed;
* a family in `FAMILY_CLAIMS` mints with its canonical Claim string; a
  divergent `--claim` refuses (render_signoff_table.py finds records by
  Claim substring, so a reworded claim would mint a record the rollup
  cannot see);
* every corner graded `recorded` must have its raw engine stdout/stderr
  under the unit dir -- a record whose raw log is missing is not minted;
* a report-declared stream path that is absolute or resolves outside the
  unit dir refuses -- evidence is read from the run's own output only (#448);
* the PDK is resolved by identity (`sim/lib/pdk_env.sh`, which fails
  non-zero on a drifted tree) before anything is written -- an unpinned
  environment never mints;
* any existing artifact for the record id (record, snapshot, corners dir)
  makes the mint refuse: append-only means never overwrite.

A corner graded `OPEN` does not block a mint (the launcher minted OPEN
records too -- an open result is recorded as open, never dropped, per
spec/sram.md's Signoff definition); the record's Overall line says so
honestly, and `sim/pex/write-margin/generate.sh` gates its own flow on the
grading being fully `recorded` before minting.

Two deliberate improvements over the retired launcher. Its **Netlist
provenance** field was boilerplate that always named
`design/netlist/bitcell_6t.spice` regardless of the DUT the testbench
actually `.include`s (documented as a known cosmetic limitation in
`sim/pex/README.md`); the minter names the family's real staged DUT
file(s), and the pex legs' provenance word says `extracted` where the
launcher's copy said `schematic`. And its records carried no PDK identity
and no run pinning: every record this module mints adds a **PDK** line
(resolved by identity, never by install path) and a **Run** line (the
fleet `environment.remote` job id and the pinned run-directory
`.spiceinit` sha the units executed under, issue #338) -- the fields the
#272 re-qualification records needed.

Usage:
    mint_corner_records.py <family> <reduced.json> --request REQUEST.json
                           --report REPORT.json --unit-dir DIR
                           [--claim TEXT] [--supersedes TEXT] [--exp-dir DIR]

`reduced.json` is `deck_adapter.py reduce ... --json-out`'s output;
`--report` is the same `klt sim` report `reduce` graded (its `units[]`
declare each unit's stream paths); `--unit-dir` is the same outdir
`klt sim -o` wrote and `reduce --outdir` read. Each unit's raw
stdout/stderr resolve through `deck_adapter.unit_stream_relpath` -- the
report's declared `units[].stdout`/`.stderr`, falling back to the default
per-unit layout `<corner-id>/stdout.bin` + `stderr.bin` -- the identical
rule the grader used (#444), containment-checked against the unit dir
(#448). `--claim` is required for families outside `FAMILY_CLAIMS` (the
pex legs); `FAMILY_CLAIMS` families default to their canonical Claim. The
experiment directory defaults to the family's own under the repo root;
`--exp-dir` exists for offline tests. Prints `record-id: <id>` on success.
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

import deck_adapter as da  # noqa: E402
from corner_matrix import PROCESSES, TEMPS, VDDS, corner_id, corners  # noqa: E402
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

# family -> (experiment dir under sim/, Claim text). The Claim text is the
# exact string the current records carry (RECORD_CLAIMS in
# render_signoff_table.py matches its substring against whatever minting
# writes, so a reword here would silently retarget the rollups) -- which is
# why mint_record refuses a divergent --claim for these families.
FAMILY_CLAIMS = {
    "read-snm": ("read-snm", "spec/sram.md Characterization -- read SNM"),
    "hold-snm": ("hold-snm", "spec/sram.md Characterization -- hold SNM"),
    "write-margin": ("write-margin", "spec/sram.md Characterization -- write margin (write trip voltage)"),
    "read-access": ("access-time", "spec/sram.md Characterization -- read access time (bit-line differential proxy)"),
    "write-access": ("access-time", "spec/sram.md Characterization -- write access time"),
}


def git_short_sha(repo_root: Path = REPO_ROOT) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip() if out.returncode == 0 else "nogit"


def new_record_id(repo_root: Path = REPO_ROOT) -> str:
    """`<YYYYMMDD>-<HHMMSS>-<short-git-sha>` -- the launcher's convention
    (sim/README.md); sorts chronologically as a plain string."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{git_short_sha(repo_root)}"


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
    claim=None,
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
    both from the clock/git. `claim` defaults to the family's canonical
    FAMILY_CLAIMS string; families outside FAMILY_CLAIMS must pass one.
    """
    _exp_dir_default, tb_name, mode, staged_files = da.FAMILIES[family]
    kind, datafile, snm_label = da.parse_mode(mode)
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
    if reduced.get("expected_deck_sha256") != meta.get("composed_deck_sha256"):
        raise ValueError("reduced grading does not pin this request's composed deck sha256")
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

    # The Claim: canonical text is FAMILY_CLAIMS' (see its comment) -- a
    # divergent explicit claim would mint a record the signoff rollup
    # cannot find, and no claim at all for a family with no canonical
    # string leaves the record substantiating nothing enumerable.
    canonical = FAMILY_CLAIMS.get(family, (None, None))[1]
    if canonical is None and not claim:
        raise ValueError(
            f"{family}: not in FAMILY_CLAIMS, so it has no canonical Claim "
            "-- pass --claim (the text of the spec/sram.md claim this "
            "record substantiates)"
        )
    if canonical is not None and claim not in (None, canonical):
        raise ValueError(
            f"{family}: FAMILY_CLAIMS owns its Claim text ({canonical!r}); "
            "render_signoff_table.py matches records by Claim substring, so "
            "a divergent claim would mint a record the rollup cannot see"
        )
    claim = claim or canonical

    exp = Path(exp_dir)
    tb_path = exp / "testbench" / tb_name
    if not tb_path.is_file():
        raise FileNotFoundError(f"testbench not found under experiment dir: {tb_path}")
    if tb_path.read_bytes() != (Path(repo_root) / meta["testbench"]).read_bytes():
        raise ValueError(
            f"experiment dir's testbench differs from the request's source "
            f"({meta['testbench']}) -- the record must snapshot the run's own deck source"
        )
    # The snapshot is the composed deck -- the bytes that actually ran --
    # re-composed from the testbench and checked against the sha256 the
    # request recorded (and the reducer asserted per unit).
    deck_bytes = da.compose_deck(tb_path.read_text(encoding="utf-8")).encode("utf-8")
    if da._sha256(deck_bytes) != meta["composed_deck_sha256"]:
        raise ValueError(
            "testbench no longer composes to the request's deck bytes "
            f"(sha256 {meta.get('composed_deck_sha256')}) -- the snapshot "
            "must be the bytes the fleet actually ran"
        )
    pdk = pdk_identity()
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
            rel = da.unit_stream_relpath(unit_entry, cid, stream, base=unit)
            p = unit / rel
            if p.is_file():
                streams.append(p.read_bytes().decode("utf-8", errors="replace"))
            elif entry is not None and entry.get("status") == "recorded":
                raise ValueError(f"raw {rel} missing for recorded corner {cid} under {unit}")
        streams.append(f"=== corner: {cid} (process={process} temp={temp}C vdd={vdd}V) ===\n")
        streams.append(f"=== ngspice exit status: {entry.get('engine_exit_code') if entry else None} ===\n")
        if kind == "snm":
            # The SNM families' measurement is extracted from the unit's own
            # sweep data, not from a RESULT line the engine printed -- the
            # corner log carries the extractor's output over that data, the
            # same text the reducer graded (datafile at the reducer's own
            # <unit>/<cid>/<datafile> location).
            data = unit / cid / datafile
            if data.is_file():
                streams.append(da._snm_lines(data, snm_label))
            else:
                streams.append(f"RESULT-ERROR: {snm_label} -- expected data file {datafile} not produced\n")
        log_bodies[cid] = "".join(streams)

    open_count = sum(1 for c in graded if c["status"] != "recorded")
    short_sha = git_short_sha(repo_root)
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

    env = report.get("environment") or {}
    remote = env.get("remote") or {}
    lines = [
        f"# Record {record_id}",
        "",
        f"- **Record ID**: {record_id}",
        f"- **Claim**: {claim}",
        f"- **Netlist provenance**: {provenance_word} (`{rel(tb_path)}`, DUT per {staged_clause} at `{short_sha}`)",
        f"- **PDK**: `{pdk['variant']}`, open_pdks `{pdk['version']}` (issue #173 pin, `sim/lib/pdk_pin.txt`)",
        f"- **Run**: `klt sim` deck mode on the batch fleet (#230 cutover path), job `{remote.get('job_id') or 'unknown'}` "
        f"(ngspice {env.get('engine_version') or 'unknown'}, `{remote.get('ami_id', 'unknown')}`); pinned run-directory "
        f"`.spiceinit` staged per unit (issue #338, sha256 `{meta.get('spiceinit_sha256', 'unknown')}`; "
        f"spec/environment-pin-decision.md)",
        "- **Corner matrix run**:",
        f"  - Process: {' '.join(PROCESSES)}",
        f"  - Temperature: {' '.join(TEMPS)} C",
        f"  - Supply: {' '.join(VDDS)} V",
        f"  - ({len(axes)} corner points total -- full process x temp x supply matrix, per spec/sram.md's ratified corner set)",
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
            f"  - **Overall: recorded** -- all {len(graded)} corners produced a measured result; see "
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
    snapshot.write_bytes(deck_bytes)
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
    ap.add_argument("--claim", default=None,
                    help="the spec/sram.md claim this record substantiates "
                         "(written verbatim); required for families outside "
                         "FAMILY_CLAIMS, which default to their canonical claim")
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
