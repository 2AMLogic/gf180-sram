# sim/min-clock-pulse — minimum clock pulse width (issue #328)

The "Minimum clock pulse" row of `spec/area-clock-pulse-power-decision.md`
("shortest `CLK` high/low width at which the macro still completes a correct
read/write, per corner", status *not yet measured*): this directory is that
measurement. It is not a pass threshold, a cycle-time claim, or Liberty
content (#200); the spec's status table is dated and stays as is.

## What is swept

The same reduced-array macro bench as `sim/macro-smoke` (identical `OPS`
table, `reduced_array()` and 20 fF bit-line stand-in, copied verbatim —
pinned by `sim/lib/test_min_clock_pulse.py`), with `(clk_high, clk_low)` as
generator arguments. `klt sim`'s corner axes are PVT only, so the swept axis
lives outside the request: one generated body + request per grid point, the
`sim/wordline-rc/` shape. Two 1-D sweeps sharing the 10/10 ns baseline
(9 variants, not 10; **2 ns resolution, deliberate**):

| Sweep | Swept axis | Held | Variants |
|---|---|---|---|
| High | `clk_high` ∈ {4, 6, 8, 10, 12, 14} ns | `clk_low` = 10 ns | `h04_l10` … `h14_l10` |
| Low | `clk_low` ∈ {4, 6, 8, 10} ns | `clk_high` = 10 ns | `h10_l04`, `h10_l06`, `h10_l08`, (`h10_l10` = baseline) |

The grid brackets **above** 10 ns on purpose: the control chain at
`ss_125c_2.97v` already needs 7.78 ns (write) / 8.68 ns (read) of the high
phase (`sim/macro-smoke/records/20261018-082301-37ba562.md`), so a grid
stopping at 10 ns would report "no passing width" at the slow corners without
having bracketed them.

`smoke.py`'s timing constants are not parameterised on pulse width and would
fabricate a false minimum if swept naively (`SAMPLE = 9.0` ns is only a valid
probe time while `CLK_HIGH > 9.0`; `SETUP = 6.0` ns must sit inside the low
phase). `pulse.py` **derives** them per variant instead —
`PERIOD = high + low`, `SAMPLE = high − 1.0`, `SETUP = min(6.0, low − 1.0)` —
and stamps them in each generated body's header. At (10, 10) they reproduce
smoke.py's exactly and the body is line-for-line `tb_macro_write_read.klt.spice`.

| File | What |
|---|---|
| `pulse.py` | `gen-klt`: all bodies + requests + the DUT copy; `check-klt`: grade one variant's report per corner; `grade-set`: fold variants → per-corner minimum |
| `testbench/tb_min_clk_<h>_<l>.klt.spice` | one body per grid point (generated) |
| `testbench/sram_256x32.noarray.spice` | copy of `sim/macro-smoke/testbench/`'s stripped DUT (same file, byte for byte) |
| `requests/min_clk_<h>_<l>.json` | one 27-corner request per grid point (generated) |
| `testdata/` | offline grader fixtures (`sim/lib/test_min_clock_pulse.py`, run by `npm test`; no PDK, no ngspice) |
| `corners/<record-id>/` | per-corner logs + the `klt-sim-report.json` per variant (append-only) |
| `records/` | append-only summary record |
| `netlist-snapshots/<record-id>.<variant>.spice` | frozen body per variant, as actually run |

## Grading

`check-klt <report>` grades each corner against that corner's own VDD (a bit
is defined if within 20 % of a rail — the smoke.py rule); a variant passes a
corner only if all 7 sampled words match and no bit is undefined. A corner
`klt sim` did not measure (errored/failed, missing values) is **OPEN**, never
FAIL — bench evidence, not a macro failure.

`grade-set <reports...>` folds the per-variant verdicts into the per-corner
minimum on each axis: the smallest grid width that passes **and** has no
failing or unmeasured width above it. Pass each variant's report exactly
once, and pass only reports that all carry the same corner set: every
corner is validated against its axis grid — the set of variant tags must
equal the grid exactly, so an off-grid tag is as much an error as a missing
one — before any minimum prints. A structural error (a variant off the
grid or repeated on an axis, a corner short of the full variant set, or
reports disagreeing on the corner-id set) is an `ERROR:` line on stderr
and exit 1, with **no** minimums reported. A pass island below the reported
minimum is recorded in a NOTE, not smoothed. Sentinels per AC2, never
dropped: `>= <max grid>` (smallest passing width is the largest grid point —
the grid does not bracket the minimum) and `OPEN` (nothing passes, or a
width went unmeasured).

## Runtime and how to re-run

~5–7 min per corner per variant (tran length scales with `PERIOD`); the
9-variant × 27-corner grid is ≈ 22 CPU-hours, so it belongs on the batch
fleet, never a local loop:

```bash
python3 sim/min-clock-pulse/pulse.py gen-klt
klt sim --batch-set sim/min-clock-pulse/requests/*.json \
  --wait-for-capacity 600 --max-in-flight 4 --hosts 9 --max-units-per-job 3 \
  -o <outdir> --format json
python3 sim/min-clock-pulse/pulse.py check-klt <outdir>/.../klt-sim-report.json
python3 sim/min-clock-pulse/pulse.py grade-set <outdir>/.../*.json
```

Single-corner debug probe (the only local run this bench warrants): copy
`requests/min_clk_h10_l10.json`, reduce each corner axis to one point
(process `tt`, `vvdd` `[3.3]`, temperature `[25]`), run
`klt sim <copy> --backend local -o <dir>`, and grade with `check-klt`; the
10/10 ns variant must reproduce the macro-smoke baseline verdict (all words
match, `undefined_bits=0`) — that equivalence is also pinned offline by
`sim/lib/test_min_clock_pulse.py`.

## Records

| Record | Result |
|---|---|
| `records/20261115-010427-185a422.md` | collection complete: 243/243 corner-runs ran (`klt sim` status `pass`; two-phase: batch-set + 51 re-collected `lost_shard` corners), functional grading 212/243 PASS, 31 FAIL -- the fails are the sub-minimum widths the sweep exists to find (9 variants x 27 corners); min CLK high = 4 ns at the two `ff`/−40 C/fast-supply corners (grid floor), 6 ns at 20 corners, 8 ns at 5 corners (`ss` 125 C at every supply, `tt/2.970V/125C`, `ss/2.970V/25C`); min CLK low = 4 ns (grid floor) at 26 of 27 corners, 6 ns at `ss_125c_2.97v` |

