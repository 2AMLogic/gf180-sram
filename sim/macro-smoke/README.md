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
loop, and has not been run.
