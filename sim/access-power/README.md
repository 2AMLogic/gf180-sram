# sim/access-power — dynamic energy per access (issue #329)

Supply charge drawn from `VDD` over one full write cycle and one full read
cycle of the macro top netlist, converted to energy per access at each
corner's own supply, over the ratified 27-corner PVT matrix. This fills the
`spec/area-clock-pulse-power-decision.md` "Power (leakage; dynamic per
access)" row's dynamic half; the leakage half is `sim/bitcell-leakage/`
(issue #310).

**A recorded quantity, with no pass threshold** — none is proposed here, and
no spec row, Signoff definition or decision record is changed. What the number
does *not* cover is in each record's "Limits", and it is not a small list: the
array is the reduced two-row form, the bit lines are 20 fF stand-ins, and the
32 `Q[*]` output loads charge from the same rail being integrated.

| File | What |
|---|---|
| `access_power.py` | `gen-klt`: writes the body and request; `check-klt`: grades a `klt sim` report into energy per access, failing closed on a missing corner |
| `test_access_power.py` | offline grader tests (synthetic reports; no PDK, no ngspice) — runs in `npm test` |
| `requests/access_power.json` | the `klt sim` request: 27 corners, two cycle-charge integrals, 32 functional `Q` probes |
| `testbench/tb_access_power.klt.spice` | generated body — the macro-smoke circuit and stimulus, unchanged |
| `corners/<record-id>/` | the returned `klt-sim-report.json` and `batch-receipt.json` |
| `netlist-snapshots/<record-id>.spice` | the body as actually run |
| `records/<record-id>.md` | the append-only record (`sim/README.md` format) |

## The circuit is macro-smoke's, deliberately

`access_power.py` imports `sim/macro-smoke/smoke.py` and emits that
generator's body — the same reduced two-row `sram_64x128_array`, the same
20 fF bit-line stand-ins, the same 32 × 20 fF `Q[*]` load, the same ten-cycle
PWL stimulus — rather than forking 800-odd generated lines. Only the DUT
include is re-pointed at the one checked-in `sram_256x32.noarray.spice` under
`sim/macro-smoke/testbench/`. `test_access_power.py` asserts that card-level
identity, so the two decks cannot drift apart.

The point of the reuse is attributability: the energy is measured at exactly
the operating point `sim/macro-smoke` already grades functionally, so a
plausible-looking number cannot come from a circuit that was not actually
working. The request re-measures the read word for the same reason — a corner
whose read did not return `0xDEADBEEF` is recorded `OPEN` and carries no
energy number.

## What is measured, and the sign convention

Two raw `.meas` lines, each over a whole `PERIOD` (edge to edge, not over the
clock pulse), so the control-pulse chain, bit-line restore and output
charging that follow the edge are all inside the window:

```
.meas tran q_write INTEG i(vvdd) FROM=25n TO=45n   ; OPS[1] "write A7"
.meas tran q_read  INTEG i(vvdd) FROM=65n TO=85n   ; OPS[3] "read A7"
```

The windows are derived from `smoke.edge()` and the `OPS` labels, never
hard-coded, so a change to the stimulus table cannot silently move a window
off its operation.

ngspice reports the current through a voltage source as flowing from its `+`
node into the source, so `i(vvdd)` is **negative** while `VVDD` supplies the
circuit — confirmed by a local single-corner probe before any batch submit
(`tt/3.300V/25C`: `q_write = -8.54e-11`, `q_read = -8.26e-11`). The committed
report therefore holds the simulator's own signed number, and the grader
applies `q = -INTEG(i(vvdd))`, `E = q x VDD`, with the convention in one
place (`CHARGE_SIGN` in `access_power.py`). Same shape as
`sim/bitcell-leakage`'s `i_leak_vdd = -I(VVDD)`.

Energy is computed in Python from each corner's `supply_v.vvdd`, not in the
deck, so the body carries no per-corner arithmetic.

## Grading contract

`check-klt` iterates the **expected** 27-point matrix, not whatever the report
happens to contain, and prints one `RESULT:` line per corner:

| Condition | Status |
|---|---|
| both integrals present, read word correct, charge finite and positive | `PASS` |
| corner absent from the report; any measurement `null`; read word wrong or at an undefined level; a corner outside the ratified matrix | `OPEN` |
| charge present but non-physical (zero or wrong sign) | `FAIL` |

Exit `1` on any `FAIL`, `2` if only `OPEN` rows remain, `0` on all-`PASS`. A
26-corner report cannot exit `0`.

## Running it

The 27-corner sweep is a batch submit — never a local multi-corner loop:

```bash
PDK_ROOT=<pdk root> klt sim sim/access-power/requests/access_power.json \
  -o <dir> --report-out <dir>/klt-sim-report.json --format json \
  --wait-for-capacity 600
python3 sim/access-power/access_power.py check-klt <dir>/klt-sim-report.json
```

Each corner of this deck takes ~5-7 minutes, so the request carries
`remote.hosts: 14` (at most 2 units per shard). Without it the 27 units go out
as **one** batch job whose conservative bound (27 × `options.timeout_s`) is
refused against the fleet's whole-job ceiling, and a job still running at that
ceiling is killed with every unit reported `batch_job_timeout`. The first
submit for this experiment was made unsharded and abandoned for exactly that
reason; `sim/macro-smoke`'s own 27-corner run of this deck went out as 9
shards.

A single corner (debug probe) is allowed locally: copy the request, keep one
point per axis, and run `klt sim <request> --backend local -o <dir>`.
`gen-klt` regenerates the body and request byte-identically from `smoke.py`'s
tables.
