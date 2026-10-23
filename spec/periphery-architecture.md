# Decision record: periphery architecture, macro floorplan, and pin placement

**Status**: Proposed for ratification via PR approval (2AMLogic/2am#357 standing
policy — the operator's PR approval is the ratification act)
**Resolves**: #202 (child of #201)
**Amends**: nothing. `spec/sram.md` (256 words × 32 bits, 1RW, 27-corner set,
signoff thresholds) and `spec/macro-interface-decision.md` (#198: pin widths,
polarity, per-bit `WEN`, 1-cycle read latency) are inputs and are unchanged.
**Consumed by**: #203 (periphery schematics), #204/#205 (periphery layout),
#206 (macro assembly), #199 (LEF), #200 (Liberty).

## Why this is decided here

`layout/README.md` § "Scope" states that decode, column mux, sense amps, write
drivers and control are not drawn, and `design/` has no periphery netlist.
Every downstream piece needs one agreed floorplan and pin placement first.
This record fixes the architecture and the geometry budgets; it does **not**
size any transistor (that is #203) and ratifies **no** timing number.

## How the references were read

Three sources, with different strength of evidence. Each row below says which
one it rests on.

1. **Foundry macro** `gf180mcu_fd_ip_sram__sram256x8m8wm1`
   (`~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_ip_sram/`, `open_pdks`
   `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, per
   `spec/pdk-variant-decision.md`). Read 2026-10-18:
   - `lef/`: size 431.860 × 340.880 µm; every signal pin is Metal2 at the
     bottom edge (`y` = 0 to 5.000, pins about 1.12 µm wide); `VDD`/`VSS` are
     Metal2/Metal3 (`VSS` also Metal1) along the top edge.
   - `cdl/` (subcircuit names and port lists only; no transistor-level
     analysis was done): `xpredec0` (`A[1:0]` → 4 lines), `xpredec1`
     (`A[2:0]` → 8 lines), `ypredec1` (8 column-select lines per side,
     `ly[7:0]`/`ry[7:0]`), `xdec32`/`xdec8`/`xdec` (row decode with
     separate `LWL[n]`/`RWL[n]` outputs), `ypass_gate`, `sa`, `sacntl_2`,
     `saout_m2` (one per I/O; ports `b[7:0]`/`bb[7:0]` and a `WEN` input),
     `wen_v2`. `men` and `clk` feed the predecoders.
2. **OpenRAM** (`VLSIDA/OpenRAM`, `stable` branch docs, fetched 2026-10-18):
   - `basic_setup.md`: "OpenRAM currently does not support gf180mcu for SRAM
     generation"; ROM generation for gf180mcu is experimental. Sky130 is the
     supported open PDK.
   - `architecture.md`: each port has a column multiplexer, address decoder
     with wordline driver, sense amplifier, write driver, bitline precharge,
     and "Control Logic with Replica Bitline".
   - `control_logic.md`: `clk_buf` drives the DFFs; `wl_en` is a buffered
     gated clock; `p_en_bar` is the inverse of the gated clock and stays
     active during writes (half-select protection); `w_en` follows the
     registered `we`; `s_en` is `BUF(DELAY(rbl_bl))` from a replica bitcell
     column fired only on reads; addresses and data are captured on the
     rising edge, precharge and decode happen with clock high, and the
     read or write happens with clock low (data valid after the falling
     edge).
   - **Not verified here**: OpenRAM's column-address bit assignment, sense-amp
     and mux transistor topology, and write-mask support were not found in
     the pages above and are not claimed.
3. **Design reasoning from numbers already in this repo** (bitcell
   4.46 × 5.40 µm, array 143.15 × 1382.40 µm, `sim/` records). Where a row
   rests only on this, it says so, and it is a judgment, not a measurement.

Finding for the OpenRAM half of the issue's reference requirement: **OpenRAM
has no gf180mcu SRAM periphery.** The reference for gf180mcu is the foundry
macro above; OpenRAM's sky130 generator is the reference for scheme, not for
cells.

## Decisions

| # | Item | Choice | Reference | Adopted / differs, and why |
|---|---|---|---|---|
| 1 | Column-mux ratio | **4:1.** Physical array **64 rows × 128 columns** (same 8,192 bitcells, same bitcell) | Foundry `saout_m2` takes `b[7:0]`/`bb[7:0]`: **8:1** per I/O | Differs. At 8:1 our 32 I/Os give 32 rows × 256 columns = 1141 × 173 µm (about 6.6:1, wide); at 1:1 the array stays 1:9.7 and a sense amp plus write driver must fit one 4.46 µm column pitch. 4:1 gives 570.9 × 345.6 µm (about 1.65:1) and a 17.84 µm slice per I/O. Judgment from geometry, not measurement. See "Consequences of 4:1" |
| 2 | Address split | Row = `A[7:2]` (64 rows); column select = `A[1:0]` | Foundry splits `A[1:0]`/`A[2:0]` into x-predecoders and uses a separate y-predecoder for column select | Internal choice; pins stay `A[7:0]` per #198. Which bits select the column is not visible at the interface |
| 3 | Physical column order | Column `p = 4·i + s` for I/O bit `i`, select `s` (the four columns of a bit are adjacent) | Foundry `saout` groups the 8 `b/bb` pairs of one I/O | Follows. Puts each bit's sense amp, write driver and `D`/`WEN`/`Q` pins in one 17.84 µm slice |
| 4 | Row decoder | 6→64: two 3→8 predecoders (`A[7:5]`, `A[4:2]`), then a 2-input AND per row, then a wordline driver, **pitch-matched to the 5.40 µm row pitch**, placed on the **left** edge and landing on the existing per-row `Metal1` wordline pads | Foundry: predecoders (`xpredec0/1`) plus `xdec32`/`xdec8`, decoder between left and right wordline halves. OpenRAM: "Address Decoder(s)" plus "Wordline Driver(s)" (hierarchical structure not confirmed from the pages read) | Predecode plus final stage follows both. **Differs** on sidedness: foundry drives from the middle (`LWL`/`RWL`); this record drives from one side because the committed array's landing-pad strip is at the left edge (#121). See "Wordline RC gate" |
| 5 | Column mux | Pass gates on each `BL`/`BLB` pair, 4 per I/O, controlled by the decoded `A[1:0]`; one shared pair per I/O feeds the sense amp and the write driver. Device type and sizing are #203's. Constraint: the read path must pass a bit line near `VDD`, the write path must pull one line to `VSS` | Foundry `ypass_gate`; OpenRAM "Column Multiplexer(s)" | Follows in structure. Device type left open on purpose: no evidence in hand chooses between NMOS, PMOS and transmission gates |
| 6 | Sense amp | One latch-type (cross-coupled) differential sense amp per I/O, enabled by a self-timed `s_en`, at the 17.84 µm slice pitch | Foundry `sa` + `sacntl_2` per I/O; OpenRAM "Sense Amplifier(s)" with replica-timed `s_en` | Follows. Topology detail and offset tolerance are #203's, evaluated with Monte Carlo as `spec/statistical-treatment-decision.md` requires for a mismatch-driven quantity |
| 7 | Output hold | The sense-amp result is captured into a 32-bit `Q` register loaded **only** on a read (`CEN` = 0, `GWEN` = 1). Writes and idle cycles do not touch it | Foundry model: registered `Q`, unchanged by a write (`spec/macro-interface-decision.md`) | Follows #198 items 3 and 8 ("`Q` holds across writes") |
| 8 | Write driver | One per I/O, enabled by `~WEN[i] & ~GWEN` after the input flop; drives one line of the selected pair to `VSS` through the mux. A masked bit (`WEN[i]` = 1) leaves that I/O's lines precharged | Foundry `saout` has a `WEN` input per I/O; OpenRAM `w_en` follows the registered write enable | Follows; per-bit mask is the #198 decision. A masked bit on an asserted row is a read-like disturb of the cell, covered by read SNM (`sim/read-snm/`), exactly as #198 recorded |
| 9 | Precharge | Bit-line precharge/equalize to `VDD` on every column, active whenever the wordline is off; kept **on for unselected columns** during an access | OpenRAM `p_en_bar`: active through writes for half-select protection. Foundry: `pcb` into `sa`/`ypass_gate` | Follows OpenRAM's reason. The 3 unselected columns of every I/O and the 96 unselected I/Os' columns on the active row are half-selected; the disturb is the read case already measured |
| 10 | Input capture | `A`, `CEN`, `GWEN`, `D`, `WEN` are captured on the rising edge of `CLK` (74 + `CEN`/`GWEN` flops/latches) | OpenRAM: DFFs on `clk_buf`; foundry: all setup/hold arcs against rising `CLK` | Follows. Needed because the internal pulse outlives the interface hold window |
| 11 | CLK-to-internal-pulse scheme | The rising edge starts a **self-timed** access: decode, then `wl_en` pulse, then `s_en` (read) or write-driver enable (write), then reset and precharge. The pulse **end** is set by a replica/delay path, not by the falling edge of `CLK` | OpenRAM: replica-bitline-timed `s_en`, but wordline and evaluation are gated by the **low phase** of `CLK`. Foundry: single registered `Q`, clock-to-`Q` arcs from rising `CLK` | **Differs** from OpenRAM's two-phase scheme. With the low-phase scheme the clock-to-`Q` delay depends on `CLK` duty cycle, an interface property #198 does not allow itself. #198 states `Q` valid after the rising edge, which the self-timed scheme gives. No duty-cycle or minimum-pulse number is ratified here |
| 12 | Write pulse | The internal write pulse must be **at least 2 ns at every corner**, or `sim/write-margin/` must be re-run at the shorter pulse under a new record | `spec/write-pulse-width-decision.md` | Not a new timing target. The write-margin evidence was measured against a fixed 2 ns window; a shorter macro pulse would silently make that evidence not apply. The cost is a floor on achievable cycle time, which is stated, not hidden |
| 13 | Read latency | 1 `CLK` cycle, as #198 | `spec/macro-interface-decision.md` item 8 | Unchanged. This record does not show it is achievable at any period; see the standing caveat in #198 |

### Consequences of 4:1

- **Bit lines get 4× shorter, wordlines get 4× longer.** Bit line: 64 rows ×
  5.40 µm = 345.6 µm (was 1382.4). Wordline: 128 cells × 4.46 µm = 570.9 µm
  (was 142.7). The `sim/access-time/` testbench uses a 20 fF bit-line
  stand-in and says the real column capacitance is layout-derived; it is
  unaffected in kind, and a 256-row column is the case it was conservative
  about.
- **The committed array is not the 4:1 array.** `layout/sram_256x32/` is
  256 × 32 physical and `design/netlist/sram_256x32_array.spice` declares
  `WL0..WL255`, `BL0..BL31`, `BLB0..BLB31`. Under this record the array
  becomes `WL0..WL63`, `BL0..BL127`, `BLB0..BLB127`. The generator takes
  `--rows/--cols` and the bitcell does not change, but regenerating the array,
  its netlist and its LVS/DRC reports is **not done here** (out of scope: no
  layout). It belongs to #203/#204's first step, and `sim/` array-level
  claims tied to the 256 × 32 physical array (`sim/pex/`) stay valid for what
  they measured and are not extended to the new array.
- **No ratified item changes.** `spec/sram.md` fixes 256 words × 32 bits as
  the *logical* organization and calls the word/bit split a free choice; the
  interface is `A[7:0]`, `D[31:0]`, `Q[31:0]`. Nothing at the pins changes.
  The sentence in `spec/sram.md` "on the fixed 256 × 32 array" reads as the
  logical array. If the operator reads it as physical, that is a separate spec
  decision to file, not an edit here.
- **Half-select grows.** On a read, 127 of 128 columns see a wordline-high,
  precharged bit-line pair. The measured read SNM (`sim/read-snm/`) is the
  relevant evidence and is per-cell, so it applies unchanged.

### Wordline RC gate (what would make this record wrong)

The wordline is `Poly2` across the full cell width (`layout/README.md`), now
571 µm driven from one end. No `Poly2` resistance or extracted wordline RC is
in the repo, so far-end wordline delay is **unmeasured**. This record therefore
adopts 4:1 conditionally. #204 (decoder layout) must extract the far-end
wordline delay at the worst corner (`ss_125c_2.97v`) and compare it with the
write pulse in row 12 and the read path. If it does not fit, the fallbacks are,
in order:

1. **4:1 with a centre decoder**, as the foundry macro does (`LWL`/`RWL`):
   two 64-column halves of 285 µm each. Costs a second landing-pad strip in
   the array.
2. **2:1** (128 rows × 64 columns, 285.4 × 691.2 µm), keeping the left-edge
   strip, at the cost of a pitch of 8.92 µm per I/O slice for the sense amp
   and write driver.

Either is a new decision record superseding rows 1 and 4, not an edit here.

## Floorplan

Macro orientation as drawn, origin at lower left. All numbers are budgets from
the array and cell pitches, not area claims.

```
 top      VDD / VSS straps (Metal3)        bit-line precharge row (above array)
          +---------+-----------------------------------------+
          | row     |                                         |
          | decode  |      bitcell array                      |
          | + WL    |      64 rows x 128 columns              |
          | drivers |      570.9 x 345.6 um + 0.43 um strip   |
          | (5.40   |                                         |
          |  pitch) |                                         |
          +---------+-----------------------------------------+
          | control | column mux | SA | write driver | Q reg    |  32 slices
          | + input |      each slice 17.84 um wide           |  x 17.84 um
          | flops   |                                         |
 bottom   +---------+-----------------------------------------+
          signal pins: A, CEN, GWEN, CLK, D, WEN, Q  (Metal2, bottom edge)
```

- **Array**: unchanged cell, re-tiled 64 × 128. Left edge keeps the 0.43 µm
  `Metal1` wordline landing-pad strip, one pad per row, so the decoder lands
  on `WL0..WL63` exactly as #121 provides. `BL<c>`/`BLB<c>` keep their
  full-height `Metal1`, so the mux (bottom) and the precharge (top) both reach
  them.
- **Left**: row predecode, row decode and wordline drivers at 5.40 µm pitch.
- **Bottom**: column mux, sense amp, write driver and `Q` register in 32
  slices of 17.84 µm; control logic, the replica path and the input flops sit
  in the bottom-left corner under the decoder.
- **Top**: precharge row and the supply straps.
- Periphery dimensions (decoder width, bottom-band height) are **not decided
  here**; they follow from #203's sizing and are fixed by #204/#205.
- Reference for scale only: the foundry 256 × 8 macro is 431.86 × 340.88 µm
  (0.147 mm²) for 2,048 bits. This record makes no area comparison; the
  periphery has no sizing yet.

## Pin placement and layers

All 107 signal pins follow the foundry convention: **Metal2, bottom edge,
vertical stubs about 5 µm deep** (foundry LEF: `y` = 0 to 5.000, 1.12 µm
wide). This lets a consumer route to this macro as it would to
`gf180mcu_fd_ip_sram`. Names, widths and polarity are exactly #198's.

| Pin | Dir | Width | Polarity | Placement |
|---|---|---|---|---|
| `A[7:0]` | in | 8 | — | Bottom edge, left group (nearest the decoder and control) |
| `CEN` | in | 1 | active low | Bottom edge, left group |
| `GWEN` | in | 1 | active low (write) | Bottom edge, left group |
| `CLK` | in | 1 | rising edge | Bottom edge, left group |
| `D[31:0]` | in | 32 | — | Bottom edge, in the slice of its own bit, `D[i]` in slice `i` |
| `WEN[31:0]` | in | 32 | active low, per bit | Bottom edge, slice `i` |
| `Q[31:0]` | out | 32 | — | Bottom edge, slice `i` |
| `VDD`, `VSS` | inout | 1 each | — | Top edge, `Metal3` straps, as the foundry macro does; ties into the periphery are #206's |

Slice `i` is 17.84 µm wide and carries three pins (`D[i]`, `WEN[i]`, `Q[i]`),
about 5.9 µm each, against a 1.12 µm pin width. Bit order is `[31:0]`
descending with `i` increasing along `x`, so `Q[i]` sits over its own sense
amp. The pin count is 8 + 1 + 1 + 1 + 32 + 32 + 32 = 107 signals plus two
supplies.

Internal nets `WL0..WL63` and `BL0..BL127`/`BLB0..BLB127` stay array-internal
at macro level. The array abstract still exposes them for array-level checks,
so the existing `WL*` landing pads and `BL*/BLB*` pins remain usable.

## What this record does not do

- Size any transistor, draw any schematic or layout, or generate LEF/Liberty
  (#203–#206, #199, #200).
- Change `spec/sram.md` or `spec/macro-interface-decision.md`.
- Ratify a cycle time, clock-to-`Q`, setup/hold, or minimum clock width.
- Claim 4:1 is right: it is a geometry-driven judgment held conditional on the
  wordline RC gate above.
- Reimplement OpenRAM. Where OpenRAM's scheme is adopted (replica-timed sense
  enable, half-select precharge, per-I/O sense and write through a column
  mux) the record says so; where it differs (single-sided decode, self-timed
  pulse end) it says why. For gf180mcu there is no OpenRAM periphery to
  compare against.

## References

- `spec/sram.md`, `spec/macro-interface-decision.md`,
  `spec/write-pulse-width-decision.md`, `spec/bitcell-decision.md`,
  `spec/statistical-treatment-decision.md`.
- `layout/README.md` § "The array", "Scope".
- `sim/access-time/testbench/tb_read_access_time.spice` (20 fF stand-in),
  `sim/read-snm/`, `sim/write-margin/`.
- `gf180mcu_fd_ip_sram__sram256x8m8wm1` LEF and CDL under
  `~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_ip_sram/`.
- OpenRAM `stable` docs: `basic_setup.md`, `architecture.md`,
  `control_logic.md` (`https://github.com/VLSIDA/OpenRAM/tree/stable/docs/source`).
