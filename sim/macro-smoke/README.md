# sim/macro-smoke — macro write/read smoke (issue #203)

Functional smoke simulation of the macro top netlist
(`design/netlist/sram_256x32.spice`): write then read at one corner, plus the
control block's pulse widths. **One corner (`tt_25c_3.30v`), local. Not a PVT,
timing, margin or Monte Carlo result**; PVT characterisation stays with
`sim/read-snm/`, `hold-snm/`, `write-margin/` and `access-time/`.

| File | What |
|---|---|
| `smoke.py` | `gen`: writes `testbench/tb_macro_write_read.spice` from its `OPS` table; `check`: grades an ngspice log |
| `run.sh` | one-corner local run: `run.sh [process temp vdd]`, or `run.sh tt 25 3.30 ctrl` for the control-pulse testbench |
| `testbench/tb_macro_write_read.spice` | ten cycles: two writes, two reads, a per-bit-masked write, reads, a `CEN`=1 no-write cycle |
| `testbench/tb_ctrl_pulse.spice` | `sram_ctrl` alone: write-pulse, `wl_en`, `s_en`, `q_clk` widths/delays |

The macro run takes about 4 minutes. It uses a **reduced array** (the two
addressed rows populated, 20 fF per bit line for the rest) because the full
8,192-cell transient did not finish in 10 minutes; `run.sh` strips the
`sram_64x128_array` subcircuit from the netlist since ngspice keeps the first of
two same-named subcircuits. Records follow the layout in `sim/README.md`
(append-only); their "Limits" lists exactly what is not shown. A multi-corner
sweep of either testbench belongs on the batch fleet via `klt sim`, not a local
loop.

## 27-corner sweeps (issue #217)

Both testbenches have been swept over ff/tt/ss x -40/25/125 C x 2.97/3.30/3.63 V
with `klt sim` on the batch fleet. A `klt sim` request takes a circuit *body*,
so each has a `.klt.spice` twin (supply = `VVDD`, stimuli scaled by `V(VDD)`
through B-sources, probes digitised at `V(VDD)/2`) and a request under
`requests/`:

| Request | Body | Record | Result |
|---|---|---|---|
| `requests/ctrl_pulse.json` | `testbench/tb_ctrl_pulse.klt.spice` | `records/20261018-082301-37ba562.md` | `wr_wpn_width` min 2.50 ns (`ff_-40c_3.63v`); >= 2 ns at all 27 corners, periphery row 12 closed |
| `requests/macro_write_read.json` | `testbench/tb_macro_write_read.klt.spice` (+ `sram_256x32.noarray.spice`) | `records/20261018-082302-37ba562.md` | 27/27 corners return every expected word |

`smoke.py gen-klt` regenerates the macro body and request; the checked-in
`testbench/sram_256x32.noarray.spice` is `design/netlist/sram_256x32.spice`
with the `sram_64x128_array` block removed (the same `awk` as `run.sh`), and
`smoke.py check-klt <klt-sim-report.json>` grades a macro report per corner
against that corner's own VDD. Runs are about 40 s per corner (control) and
5-6 min per corner (macro) on the workers; the committed records give the exact
`klt sim` command lines.
