# sim/wordline-rc -- wordline RC gate (issue #204)

`spec/periphery-architecture.md` adopted the 4:1, 64 x 128 array **conditionally**: #204 must
extract the far-end wordline delay at `ss_125c_2.97v` and compare it with the 2 ns write-pulse
floor and the read path. This directory is that measurement. The verdict and the options it
opens are in `spec/wordline-rc-decision.md`; the numbers are in `records/`.

## What is simulated

A real `rowdrv` (`design/netlist/rowdrv.spice`, 6u/3u output stage) drives an extracted wordline
from its landing-pad end. The wordline is one row of the committed array generator
(`layout/sram_256x32/generate.py --rows 1 --cols N`) extracted with parasitics:

```
source sim/lib/pdk_env.sh
V="$(basename "$GF180_VARIANT_DIR")"; R="$(dirname "$GF180_VARIANT_DIR")"
python3 layout/sram_256x32/generate.py --rows 1 --cols 128 --top-name wl_row_128 -o row128.gds
python3 layout/sram_256x32/generate.py --rows 1 --cols 64  --top-name wl_row_64  -o row64.gds
klt extract --deck gf180mcu --pdk "$V" --pdk-root "$R" --parasitics --distributed-rc \
  --critical-net WL0 row128.gds -o sim/wordline-rc/dut/wl_row_128.extracted.spice
klt extract ... row64.gds -o sim/wordline-rc/dut/wl_row_64.extracted.spice      # same flags
```

`dut/*.extracted.spice` are those outputs verbatim (frozen). The extracted `WL0` is a per-segment
RC chain through every access-gate (21.97 kohm and 110.7 fF of wire for 128 cells; 10.99 kohm
and 55.4 fF for 64). Device gate capacitance is the PDK model's, from the 256 (128) `nfet_03v3`
access transistors in the same netlist.

`gen.py` writes `testbench/`, `requests/` and the `dut/*.ported.spice` copies. Three topologies
x two resistance cases:

| Topology | What it is |
|---|---|
| `row128` | the ratified 4:1 row, 128 cells, fed from the left landing pad |
| `centre` | 4:1 with a centre decoder: one `rowdrv` feeding two 64-cell halves from their pad ends |
| `row64` | 2:1: a 64-cell row fed from the left |

`x1` uses the extractor's Poly2 resistance as reported; `x1p5` multiplies every `WL0` segment by 1.5.
The extractor applies no process or temperature scaling to Poly2 R, so `x1p5` brackets that
unknown. 1.5 is a bound, not a PDK number.

Each run applies two input pulses: 2.0 ns (the floor of `spec/write-pulse-width-decision.md`)
and 5.88 ns (the `wl_en` width the control block makes at this corner, `sim/macro-smoke`
record `20261018-082301-37ba562`). Probes are digitised at 10/50/90 % of `VDD` and masked per
pulse, so a level the far end never reaches in a pulse shows as an `error` measurement
("out of interval"), not as a crossing borrowed from the other pulse. That is why the `row128`
runs report corner status `error`; it is the result.

## Re-run

```
python3 sim/wordline-rc/gen.py
PDK_ROOT=<pdk root> klt sim sim/wordline-rc/requests/wl_rc_row128_x1.json --backend local --format json
```

One corner per request, so `--backend local` is the right backend (one unit, about 12 s).
A 27-corner sweep belongs on the batch fleet.

## Known limits of the bench (also in the record)

* Single corner, `ss_125c_2.97v`, as the architecture record names. Not the 27-corner set.
* The extracted `WL0` pin node is the 129th of 256 gates, in the **middle** of the chain
  (2AMLogic/klayout-tools#3937), so driving the pin feeds the line from its centre. The first
  version of this bench did exactly that and read as a pass; the `*.ported.spice` copies expose
  the pad-end node instead. The `centre` topology reproduces that earlier (wrong for the
  as-drawn array) figure on purpose: it is the centre-decoder case.
* The drive is an ideal pulse into both `rowdrv` inputs, not the predecoder's slew.
* The bit lines are held at `VDD` and the cells' storage nodes are left to the simulator's
  operating point; only the access gates load the wordline here.
* Measurements are on digitised probes at a 5 ps step, so values are good to about 5 ps.
