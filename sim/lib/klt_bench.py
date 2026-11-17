#!/usr/bin/env python3
"""Single owner for the `klt sim` request skeleton and the Q-word grading rule
shared by the three benches that run on the macro-smoke netlist (#388):
`sim/macro-smoke/smoke.py`, `sim/access-power/access_power.py` and
`sim/min-clock-pulse/pulse.py`.

#331 gave the corner *axes* a single owner (`corner_matrix.py`) because four
copies had drifted; the code that consumes those axes drifts the same way one
layer up. Before this module each bench re-listed the request skeleton
(`engine`, `models.lib`, the `corners` block, `netlist_source`,
`options.timeout_s`) and re-implemented the same defined-bit rule, so a change
to the 20%/80% rail rule or the per-unit timeout had to be made in three
places, and a missed copy silently redefined "PASS" for one bench only.

The defined-bit rule the three copies graded by (pulse.py's grader called it
"the smoke.py rule"): a
measured Q bit is *defined* iff its voltage is strictly outside the middle 20%
band of that corner's own VDD -- `v < 0.2*VDD` or `v > 0.8*VDD`, so a probe
landing exactly on 0.2*VDD or 0.8*VDD is undefined. A defined bit reads `1`
iff `v > VDD/2`; an unmeasured bit (no value in the report) is counted
separately and contributes 0 to the word, so the caller can fail closed
(OPEN) instead of grading a partial word.

Consumers import via the `sys.path.insert` sibling-import pattern
(`sim/lib/repo_root.py` sets the precedent), then call:

    base_request(netlist, tran_args, measurements)  # the request skeleton
    q_probes(samples)                               # the FIND v(Q[b]) emitter
    read_word(bit_values, vdd)                      # one 32-bit word + counts

Generated artifacts are unaffected by construction: each bench's committed
request JSON and testbench must regenerate byte-identically (pinned by the
bench's own offline test plus `sim/lib/test_corner_matrix.py`), which is what
sharing the skeleton instead of copying it buys.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The ratified corner matrix has a single owner, sim/lib/corner_matrix.py
# (#331). The `corners` block every macro-netlist request declares is derived
# from it rather than hand-listed, so no bench can sweep a different matrix
# than sim/lib/run_corner_sweep.sh and the deck adapter do.
from corner_matrix import LIB_SECTION, PROCESSES, TEMPS, VDDS  # noqa: E402

# The model library every macro-netlist request points at, and the per-unit
# simulator timeout it allows. Held once here because a change made in one
# bench's copy and missed in another silently redefined that bench's run.
MODELS_LIB = "$PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"
TIMEOUT_S = 1500

_WORD_BITS = 32


def corners_block() -> dict:
    """The ratified 27-corner matrix as a request's `corners` block. The
    owner holds every axis point as the spec's literal label (see
    corner_matrix's "Axis element type"); `klt sim` wants the two numeric
    axes as JSON numbers, so they are converted here, at the shared consumer
    boundary (each bench previously did the conversion itself)."""
    return {
        "process": [{"name": p, "sections": [LIB_SECTION[p]]} for p in PROCESSES],
        "supply_v": {"vvdd": [float(v) for v in VDDS]},
        "temperature_c": [int(t) for t in TEMPS],
    }


def base_request(netlist: str, tran_args: str, measurements: list) -> dict:
    """The `klt sim` request skeleton the three macro-netlist benches share.

    `netlist` is the request's relative path to its generated body,
    `tran_args` the transient analysis arguments (each bench derives its own
    end time), `measurements` the bench's own `.meas` list -- this module
    owns only what was previously copied three times. Bench-specific extras
    (access-power's sharding block) are added by the bench after the call.
    Keys are inserted in the order the committed request JSONs serialise
    (json.dumps preserves dict insertion order), so switching a bench to this
    helper is byte-identical for its committed request.
    """
    return {
        "netlist": netlist,
        "engine": "ngspice",
        "models": {"lib": MODELS_LIB},
        "corners": corners_block(),
        "analysis": {"kind": "tran", "args": tran_args},
        "measurements": measurements,
        "netlist_source": "schematic",
        "options": {"timeout_s": TIMEOUT_S},
    }


def q_probes(samples):
    """The `.meas tran ... FIND v(Q[b]) AT=` emitter: 32 measurements (one per
    Q bit) per sample. `samples` is an iterable of (name_suffix, at_ns); each
    yields the measurements named `q{b}_{name_suffix}`, in sample order then
    bit order, exactly as the benches previously emitted them inline."""
    return [
        {
            "name": f"q{b}_{suffix}",
            "spice": f".meas tran q{b}_{suffix} FIND v(Q[{b}]) AT={at:g}n",
            "unit": "V",
        }
        for suffix, at in samples
        for b in range(_WORD_BITS)
    ]


def read_word(bit_values, vdd: float) -> tuple:
    """Rebuild one 32-bit Q word from that corner's own probes, graded against
    that corner's own VDD. Returns (word, undefined_bits, unmeasured_bits).

    `bit_values` is the 32 probe voltages in bit order, `None` where the
    report carries no value. Definedness is the strictly-outside-20% rule (see
    the module docstring); an unmeasured bit contributes 0 to the word and is
    counted in `unmeasured_bits` so the caller can fail closed (OPEN), never
    silently grade a partial word.
    """
    word = undefined = unmeasured = 0
    for b, v in enumerate(bit_values):
        if v is None:
            unmeasured += 1
            continue
        if not (v < 0.2 * vdd or v > 0.8 * vdd):
            undefined += 1
        word |= (1 if v > vdd / 2 else 0) << b
    return word, undefined, unmeasured
