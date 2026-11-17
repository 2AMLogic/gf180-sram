#!/usr/bin/env python3
"""sim/lib/run_mc_campaign.py -- MC campaign identity library (the local
campaign launcher was retired at the #230 deck-mode cutover).

History (#26, #230): this module used to BE the Monte Carlo campaign -- a
hand-launched local `ngspice -b` process pool (`ThreadPoolExecutor`, one
subprocess per sample) that staged its own scratch decks, minted the
`klt yield` sample-set documents, yield reports and MC records under
`sim/<experiment>/mc/`. The staged `klt sim` deck-mode migration (#230)
replaced it: the operator rulings of 2026-10-19 and 2026-11-14 authorized
the migration and its bounded parity runs, the receipts
`sim/deck-parity/20261115-mc-2corner.md` and
`sim/deck-parity/20261116-mc-9corner.md` demonstrated measurement parity
for the committed 9-corner x 3-family MC matrix (13,680 units: all 5,400
mismatch samples within the 30 uV gate, `write-margin` exact, every
determinism-control anchor exact under the `.spiceinit` pin, every
negative-control errored set matching), and
`spec/environment-pin-decision.md` settled the evidence-environment
question that gated the switch. The pool, the campaign CLI and the record
renderer were removed at cutover; `sim/README.md` "Staged migration to
`klt sim` deck mode" records the details.

What survives, and why: the deck adapter (`sim/lib/deck_adapter.py`
`mc-build`/`mc-reduce`) and the comparator (`sim/lib/parity_compare.py`)
import this module's seed and `corner.inc` derivations, so every fleet MC
deck stays byte-identical to what the retired pool staged from the same
(base_seed, corner, kind, index) -- the identity the parity receipts
asserted. Re-deriving either elsewhere is how that identity would drift;
they stay here, imported, unchanged:

- `derive_seed(base_seed, corner_id, kind, sample_index)` -- the per-sample
  ngspice `.options seed=` value.
- `build_corner_inc(...)` -- the generated `corner.inc` for one MC unit,
  with the batch's `sw_stat_mismatch` and the unit's seed baked in.
- `RESULT_RE` / `RESULT_ERROR_RE` -- the `RESULT:`/`RESULT-ERROR:` grammar
  the testbenches' own `.control` blocks emit and every reducer parses.
- `LIB_SECTION` / `corner_id` -- re-exported from
  `sim/lib/corner_matrix.py` (#331), the single owner of the ratified
  matrix and the `tt -> typical` model-section mapping, because callers
  (`sim/lib/deck_adapter.py`) already reach them as `mc.LIB_SECTION` /
  `mc.corner_id`.

The committed MC evidence (`sim/*/mc/`) predates the retirement and is
append-only; each record's "Reproduce" section carries the exact CLI
invocation that produced it. Those command lines no longer run:
`mc-build` + `klt sim` + `mc-reduce` is the generator now, and minting NEW
MC records under the pinned environment is #272's re-qualification.

## Mismatch mechanism (unchanged, still load-bearing)

gf180mcu's `sm141064.ngspice` gates per-instance MOS mismatch
(threshold-voltage and current-factor jitter, `delvto='mis_vth*sw_stat_mismatch'`
/ `mulu0='1-mis_k*sw_stat_mismatch'` inside each `nfet_03v3`/`pfet_03v3`
`.subckt`) behind the single global `.param sw_stat_mismatch` switch, already
pulled in by every `typical`/`ff`/`ss` `.LIB` section via `.lib
'sm141064.ngspice' fets_mm` -- see `docs/cli/sim.md`'s "Known-good mismatch
mechanisms" (`2AMLogic/klayout-tools`) for the general contract;
`build_corner_inc` below implements exactly the gf180mcu branch of that
contract (a `.param` toggle, not a `.lib` section name, so `corners.process`-
style section selection cannot express it -- confirmed empirically during
this issue's implementation, see "Known ngspice/PDK-file quirk" below).

## Known ngspice/PDK-file quirk: redefining an already-`.param`-block-scoped
## name via a second, separate `.param` card corrupts later single-line
## `.param` cards in the same deck (discovered empirically; still the
## reason `build_corner_inc` emits the full defaults card itself)

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
The fix `build_corner_inc` still uses: never `.include` `design.ngspice` at
all for an MC-mismatch run -- instead, emit the exact same six defaults as
this module's own single `.param` card, with `sw_stat_mismatch` set to the
caller's requested value. This is an ngspice-parser/PDK-model-file
interaction, not a `klt` gap, so it is not filed against
`2AMLogic/klayout-tools` per CLAUDE.md's friction protocol (which scopes
filed gaps to the `klt` tool itself); it is recorded here so it is not
silently rediscovered later.

## Two-instance SNM Monte Carlo (`snm-pair` mode)

`sim/read-snm/testbench/tb_read_snm.spice` and
`sim/hold-snm/testbench/tb_hold_snm.spice` are decoupled *single* half-cell
fixtures (see each file's own header for why -- `bitcell_6t`'s Q/QB nodes
are not independently accessible from outside the subcircuit). With
mismatch off, one sweep suffices because `sim/lib/snm_extract.py`'s
self-composed method (`f(f(x))`) assumes the two physical half-cells are
*identical* devices. Under `sw_stat_mismatch=1`, that assumption is exactly
what an inter-inverter mismatch SNM campaign must NOT make: the two
half-cells of a fabricated part draw *independent* per-instance thresholds.
The retired pool therefore ran the *same unmodified* single-half-cell
testbench **twice** per Monte Carlo sample -- once standing in for the "L"
inverter, once for "R" -- each with its own independently-derived seed
(`kind` = `mm-L` / `mm-R` in `derive_seed`), and combined the two
independent VTC sweeps via `snm_extract.py --pair`, the direct two-curve
generalization of the self-composed method (see that script's module
docstring for the derivation). The deck adapter preserves that contract
exactly: `mc-build` for the SNM families stages two decks per sample
(`mc.<corner>.<kind>.<index>.L` / `.R`) with seeds from this module's
`derive_seed`, and `mc-reduce` re-pairs them. The testbench files
themselves were never modified -- read-snm's and hold-snm's existing,
already-reviewed `.spice` files serve both the deterministic single-sweep
claim and the two-instance MC claim without a fork.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(SCRIPT_DIR))
# The ratified corner matrix has a single owner, sim/lib/corner_matrix.py
# (#331): the `tt -> typical` model-section mapping and the corner-id format
# are imported, never re-derived here. Re-exported under this module's own
# names because callers (sim/lib/deck_adapter.py) already reach them as
# `mc.LIB_SECTION` / `mc.corner_id`.
from corner_matrix import LIB_SECTION, corner_id  # noqa: E402,F401

# design.ngspice's own defaults for every name its combined `.param` card
# sets, reproduced verbatim here (see module docstring, "Known ngspice/
# PDK-file quirk") so an MC unit's corner.inc never needs to redefine
# `sw_stat_mismatch` via a second, independent `.param` card.
_DESIGN_DEFAULTS = {
    "sw_stat_global": 0,
    "mc_skew": 3,
    "res_mc_skew": 3,
    "cap_mc_skew": 3,
    "fnoicor": 0,
}

RESULT_RE = re.compile(r"^RESULT:\s*(\S+)\s*=\s*([\-0-9.eE+]+)\s*;?\s*$", re.MULTILINE)
RESULT_ERROR_RE = re.compile(r"^RESULT-ERROR:.*$", re.MULTILINE)


def derive_seed(base_seed: int, corner_id: str, kind: str, sample_index: int) -> int:
    """Reproducible per-sample seed: SHA-256 of (base_seed, corner, kind,
    sample_index), never Python's salted built-in hash() -- same
    reproducibility bar docs/cli/sim.md's own seed contract states
    (`2AMLogic/klayout-tools`). `kind` is "mm" (mismatch), "ctrl"
    (determinism control) or "nc" (negative control), with an "-L"/"-R"
    suffix per half-cell in `snm-pair` mode, so no two draws collide even
    at the same sample_index.
    """
    digest = hashlib.sha256(f"{base_seed}:{corner_id}:{kind}:{sample_index}".encode()).hexdigest()
    # ngspice seeds are plain positive integers; keep well under 2**31.
    return (int(digest[:8], 16) % 2_000_000_000) + 1


def build_corner_inc(pdk: dict[str, str], process: str, temp: str, vdd: str, seed: int, sw_stat_mismatch: float) -> str:
    """The generated `corner.inc` for one MC unit. Kept byte-for-byte as the
    retired pool wrote it (the parity receipts assert deck bytes against
    it); `sim/lib/deck_adapter.py mc-build` composes every fleet MC deck
    from this function.
    """
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


_RETIRED_MSG = """\
run_mc_campaign.py: the local Monte Carlo campaign pool was retired at the
#230 deck-mode cutover; this module is now the identity library
(derive_seed / build_corner_inc / the RESULT grammar) the deck adapter
imports, and it no longer runs a campaign.

To run a Monte Carlo campaign now (per sim/README.md "Staged migration to
`klt sim` deck mode"; grids go through the batch fleet, never a local pool):

  python3 sim/lib/deck_adapter.py mc-build <family> \\
      --corner <process:temp:vdd> [--corner ... --corner ...] \\
      --n <n> --n-control <n> --n-nc <n> \\
      --nc-mismatch-scale <k> [--nc-vdd <v>] --seed <base-seed> \\
      --stage-dir <scratch> --request-out <scratch>/request.json
  klt sim <scratch>/request.json --backend batch --wait-for-capacity 600 \\
      -o <out> --report-out <out>/report.json
  python3 sim/lib/deck_adapter.py mc-reduce <family> <scratch>/request.json \\
      <out>/report.json --outdir <receipt>/<family> \\
      --json-out <receipt>/<family>/reduced.json

A single corner may be probed locally with `klt sim ... --backend local`.
The committed records under sim/*/mc/ are append-only evidence; their
"Reproduce" command lines (which name this script's retired CLI) are the
historical invocations that produced them. Minting new MC records under
the pinned environment is #272's re-qualification.
"""


if __name__ == "__main__":
    # Loud tombstone, never a silent no-op: a reader following a committed
    # record's Reproduce block must learn the pool is gone, not watch an
    # importable module exit 0 having done nothing.
    print(_RETIRED_MSG, file=sys.stderr)
    raise SystemExit(2)
