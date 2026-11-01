# Decision record: macro interface details and Liberty corner naming

**Status**: Proposed for ratification via PR approval (2AMLogic/2am#357 standing
policy — the operator's PR approval is the ratification act)
**Resolves**: #198, items 3 and 4 of #197 (consumer request from
`gf180-riscv-soc`)
**Amends**: nothing. `spec/sram.md` § "Ports" ratified the pin *names* and the
foundry pin interface as the comparison point; this record fixes the widths,
polarity, `WEN` semantics, and read latency it left open, and names the
Liberty corners. No ratified item (256 × 32, the 27-corner set, the signoff
thresholds) changes.

## Why this is decided here

`spec/sram.md` § "Ports" lists `A`, `CEN`, `CLK`, `D`, `Q`, `GWEN`, `WEN` "matching
`gf180mcu_fd_ip_sram`" but no widths, polarity, `WEN` semantics, read latency,
or Liberty corner names. The macro LEF, the Liberty view, and any consumer
integration all need these fixed. Leaving them to the LEF/Liberty issues
(#199, #200) would ratify them implicitly, in whichever lands first, without
a record. They are fixed here instead.

## Comparison point and how it was read

The comparison point is `gf180mcu_fd_ip_sram__sram256x8m8wm1` (256 × 8, the
nearest foundry depth), read from the installed PDK
(`~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_ip_sram/`, `open_pdks`
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`, per `spec/pdk-variant-decision.md`):

- `verilog/gf180mcu_fd_ip_sram__sram256x8m8wm1.v` — the behavioral model. It
  is the only place polarity, mask semantics, and latency are stated
  operationally; the LEF carries pins only, the Liberty carries timing arcs.
- `lef/...sram256x8m8wm1.lef` — pin names and directions.
- `lib/...sram256x8m8wm1__tt_025C_3v30.lib` — bus types, `when` conditions on
  the `CLK → Q` arc, units (`time_unit : 1ns`).

Foundry facts used below (all from the Verilog model unless stated):

| Fact | Evidence in the model |
|---|---|
| `CEN` active low | `cen_flag = cen_fell & !CEN` |
| `GWEN` low = write, high = read | `write_flag = ... & !GWEN & !(&WEN)`; `read_flag = ... & GWEN` |
| `WEN[i]` active low, one bit per data bit | `we = ~WEN`; `cd4 = D & we`; `cd2 = mem[A] & WEN` — all bitwise on the 8-bit word |
| `A`, `D`, `Q`, `WEN` are all `[7:0]` for an 8-bit, 256-word macro | port declarations; Liberty `A_BUS`/`Q_BUS` `bit_width : 8` |
| Read data appears after the rising edge of `CLK` and is held | `always @(posedge clk_dly) ... qo_reg = mem[marked_a]` (registered `Q`); `Q` is not changed by a write |
| Write and read both sample on the rising edge of `CLK` | setup/hold arcs in the Liberty are all `setup_rising`/`hold_rising` against `CLK` |
| The model is not operational until `CEN` has been seen to fall once | `cen_fell` / "CEN is not reset, memory is not operational" |

## Decisions (256 × 32)

| # | Item | Choice | vs. foundry |
|---|---|---|---|
| 1 | `A` width | `A[7:0]` (256 words) | Follows — `A[7:0]` on `sram256x8m8wm1` as well; depth is what sets it |
| 2 | `D` width | `D[31:0]` | Follows the convention, widened ×4 (foundry word is 8) |
| 3 | `Q` width | `Q[31:0]` | As `D` |
| 4 | `WEN` width / semantics | `WEN[31:0]`, **per-bit** write mask; `WEN[i]` gates `D[i]` → bit `i` of the word | Follows — the foundry `WEN` width equals its word width and is applied bitwise, so the same rule at 32 bits gives `WEN[31:0]` |
| 5 | `CEN` polarity | active low | Follows |
| 6 | `GWEN` polarity | active low write (`GWEN` = 1 is a read) | Follows |
| 7 | `WEN` polarity | active low (`WEN[i]` = 0 writes bit `i`) | Follows |
| 8 | Read latency | **1 `CLK` cycle**: address sampled on a rising edge, `Q` valid after that same edge (clock-to-`Q`), held until the next read | Follows |
| 9 | Bit ordering | `[N-1:0]` descending, `WEN[i]` ↔ `D[i]` ↔ `Q[i]` | Follows (Liberty `downto : true`) |

Pins `VDD` and `VSS` (`INOUT`) are unchanged from `spec/sram.md`.

### Behavior the record fixes

- **Read**: `CEN` = 0, `GWEN` = 1 at a rising `CLK` edge. `Q` takes the word at
  `A` and holds it. `WEN` is ignored.
- **Write**: `CEN` = 0, `GWEN` = 0 at a rising `CLK` edge. Bit `i` of the word
  at `A` takes `D[i]` if `WEN[i]` = 0; bits with `WEN[i]` = 1 are unchanged.
  `WEN` all ones with `GWEN` = 0 is a no-op write.
- **`Q` across writes and idle cycles**: `Q` holds the last read value. A
  write does not drive write-through data onto `Q`. `Q` is undefined before
  the first read.
- **`CEN` at reset**: the foundry model does not operate until it has seen `CEN`
  fall once. This record adopts the same consumer-side requirement
  (hold `CEN` = 1 during reset, then assert) as an interface rule, not a
  measured property; it costs the consumer nothing and avoids promising
  power-up behavior this repo has no evidence for.

### Why per-bit `WEN` and not per-byte

Per-byte (`WEN[3:0]`) is the likelier consumer want for a RISC-V data port,
so this was weighed rather than defaulted. Per-bit was chosen because:

1. It is what the foundry convention actually is. `spec/bitcell-decision.md`
   describes the foundry `WEN[7:0]` as "per-byte-lane write enable". That is
   a mislabel for this macro: the foundry word is 8 bits, so byte-lane and
   per-bit are the same width and the model's bitwise `D & we` is per-bit.
   The ambiguity does not appear at ×8, and shows up here at ×32. Recorded
   rather than edited into `spec/bitcell-decision.md`, which is a dated
   record.
2. It matches the write mechanism measured. `sim/write-margin/` drives one
   cell's bit-line pair against its wordline; the natural implementation is a
   per-column write driver, whose enable is a per-bit signal. A per-byte mask
   is a gating of eight of those and adds no capability.
3. Per-bit is a strict superset. A consumer that wants byte strobes ties
   `WEN[8k+7:8k]` together outside the macro at zero cost; the reverse
   (recovering per-bit from per-byte) is impossible. The cost of per-bit is 32
   `WEN` pins in place of 4, a pin-count and LEF-pin cost only.

This is a derivable choice, not an operator preference call, so it is not
routed through `loom-daemon operator-decision apply`. If the consumer
integration finds the 28 extra pins unacceptable it should say so on #197;
that would be a new decision record, not an edit here.

**Consequence for evidence.** A masked column on an asserted row sees its
bit lines precharged with the wordline high — a read-like disturb of that cell,
not a write. That condition is covered by read SNM
(`sim/read-snm/`), not by write margin. `sim/write-margin/`'s testbench models
only the written column and does not claim anything about masked columns, so
no existing record is invalidated.

## Consistency with `sim/access-time/` and `sim/write-margin/`

What was actually measured, and what the choices above do and do not rest on:

- **Read latency is a protocol statement, not a timing claim.**
  `sim/access-time/records/20260817-011948-4448966.md` measures a
  *bitcell-level proxy*: wordline assertion to a 3 % of VDD bit-line
  differential on a single cell with a 20 fF bit-line stand-in. Across the 27
  corners that is 1.04e-10 s (`ff_-40c_3.63v`) to 3.57e-10 s
  (`ss_-40c_2.97v`). The testbench header says no sense amp, decode, or column
  mux exists yet, so there is no clock-to-`Q` measurement. Therefore:
  - "1 cycle" is consistent with the data (nothing measured contradicts it)
    but is **not supported by** it for any particular `CLK` period.
  - No minimum cycle time, clock-to-`Q` delay, or setup/hold is ratified here,
    consistent with `spec/write-pulse-width-decision.md` (no independent
    macro timing target). The Liberty view cannot state these until a real
    sense path is simulated; #200 must not backfill them from the proxy.
  - For scale only: the foundry macro's `CLK → Q` is about 6.5–7.7 ns at
    `tt_025C_3v30` (Liberty, `time_unit : 1ns`). The proxy is a fraction of a
    clock-to-`Q` path and is not comparable to it.
- **Write**: `sim/access-time/records/20260817-012005-4448966.md` gives write
  access 4.24e-11 s (`ff_-40c_3.63v`) to 8.49e-11 s (`ss_125c_2.97v`), far
  inside the 2 ns write-pulse window `spec/write-pulse-width-decision.md` and
  `sim/write-margin/` use. A single-cycle write is consistent with that; the
  same caveat applies (bitcell proxy, no write driver).
- **Recorded inconsistency, not hidden**: the interface here is specified
  ahead of any periphery. If periphery design (decode, sense, write driver)
  shows 1-cycle read or the `WEN` choice cannot be met at an acceptable
  period or area, that is a new decision record superseding items 4 and 8.

## Liberty corner names

### Rule

Follow the foundry file-naming convention so a consumer's corner-selection
script treats this macro and `gf180mcu_fd_ip_sram` the same:

```
<macro>__<process>_<temp>_<volt>      e.g.  <macro>__tt_025C_3v30
```

- `<process>`: `ff`, `tt`, `ss`.
- `<temp>`: `n40C`, `025C`, `125C` (foundry zero-padding and `n` for negative).
- `<volt>`: the supply to two decimals with `v` as the decimal point: `2v97`,
  `3v30`, `3v63`.
- Liberty `library(...)` name equals the file stem; `nom_process`,
  `nom_temperature`, `nom_voltage` carry the corner's own values.

The `sim/` corner id (`ff_-40c_2.97v`) is a separate, already-used evidence
label and does not change. The table below maps the two so a Liberty corner
is traceable to its `sim/` record row.

The macro cell name is not decided here.

### The 27 corners and the logic-library voltage offset

Checked 2026-10-17 against the installed
`gf180mcu_fd_sc_mcu7t5v0` and `gf180mcu_fd_sc_mcu9t5v0` libraries
(`~/.volare/gf180mcuD/libs.ref/*/lib/`, `nom_voltage` read from each file).
Both libraries expose the same 15 corners, three rails (1.8 V, 3.3 V, 5 V
domains), and only these five at the 3.3 V domain:

| Logic-library corner | `nom_voltage` |
|---|---|
| `ss_n40C_3v00`, `ss_125C_3v00` | 3.00 V |
| `tt_025C_3v30` | 3.30 V |
| `ff_n40C_3v60`, `ff_125C_3v60` | 3.60 V |

The consumer's report (ss 3.00 V, ff 3.60 V, tt 25 C / 3.30 V) is confirmed,
with the addition that the `ss` and `ff` rows exist at both −40 C and 125 C.
This macro's corner set (`spec/sram.md`, ±10 % about 3.3 V) is **not** the
logic libraries' set: the macro crosses all three process points with all
three voltages, whereas the logic libraries tie each process point to one
voltage. The offset at the matching corners is ±30 mV (`ss` 2.97 vs 3.00 V:
−30 mV; `ff` 3.63 vs 3.60 V: +30 mV; `tt` 0 mV). 5 of the 27 macro corners
have a logic-library partner at the same process and temperature; the other 22
have none and are macro-only evidence. A consumer doing STA with the logic
libraries should pair on the 5, and should not mix a macro corner with a logic
corner of a different process or temperature.

| `sim/` corner id | Liberty corner | V | Logic-library partner (offset) |
|---|---|---|---|
| `ff_-40c_2.97v` | `ff_n40C_2v97` | 2.97 | none |
| `ff_-40c_3.30v` | `ff_n40C_3v30` | 3.30 | none |
| `ff_-40c_3.63v` | `ff_n40C_3v63` | 3.63 | `ff_n40C_3v60` (+30 mV) |
| `ff_25c_2.97v` | `ff_025C_2v97` | 2.97 | none |
| `ff_25c_3.30v` | `ff_025C_3v30` | 3.30 | none |
| `ff_25c_3.63v` | `ff_025C_3v63` | 3.63 | none |
| `ff_125c_2.97v` | `ff_125C_2v97` | 2.97 | none |
| `ff_125c_3.30v` | `ff_125C_3v30` | 3.30 | none |
| `ff_125c_3.63v` | `ff_125C_3v63` | 3.63 | `ff_125C_3v60` (+30 mV) |
| `tt_-40c_2.97v` | `tt_n40C_2v97` | 2.97 | none |
| `tt_-40c_3.30v` | `tt_n40C_3v30` | 3.30 | none |
| `tt_-40c_3.63v` | `tt_n40C_3v63` | 3.63 | none |
| `tt_25c_2.97v` | `tt_025C_2v97` | 2.97 | none |
| `tt_25c_3.30v` | `tt_025C_3v30` | 3.30 | `tt_025C_3v30` (0 mV) |
| `tt_25c_3.63v` | `tt_025C_3v63` | 3.63 | none |
| `tt_125c_2.97v` | `tt_125C_2v97` | 2.97 | none |
| `tt_125c_3.30v` | `tt_125C_3v30` | 3.30 | none |
| `tt_125c_3.63v` | `tt_125C_3v63` | 3.63 | none |
| `ss_-40c_2.97v` | `ss_n40C_2v97` | 2.97 | `ss_n40C_3v00` (−30 mV) |
| `ss_-40c_3.30v` | `ss_n40C_3v30` | 3.30 | none |
| `ss_-40c_3.63v` | `ss_n40C_3v63` | 3.63 | none |
| `ss_25c_2.97v` | `ss_025C_2v97` | 2.97 | none |
| `ss_25c_3.30v` | `ss_025C_3v30` | 3.30 | none |
| `ss_25c_3.63v` | `ss_025C_3v63` | 3.63 | none |
| `ss_125c_2.97v` | `ss_125C_2v97` | 2.97 | `ss_125C_3v00` (−30 mV) |
| `ss_125c_3.30v` | `ss_125C_3v30` | 3.30 | none |
| `ss_125c_3.63v` | `ss_125C_3v63` | 3.63 | none |

Nothing here relaxes the corner set: all 27 stay required for signoff
(`spec/sram.md` § "Signoff definition"). The partner column only tells a
consumer which corners can be paired with logic-library timing.

## What this record does not do

- Generate LEF or Liberty, or any layout (#199, #200, #201).
- Change any ratified item in `spec/sram.md`.
- Ratify any timing number (cycle time, clock-to-`Q`, setup/hold).
- Provide a stand-in model for the consumer.

## References

- `spec/sram.md` § "Ports", "Corner set" — the items this record details.
- `spec/bitcell-decision.md` — foundry pin list; its "per-byte-lane" wording of
  `WEN` is corrected in the "Why per-bit" section above (not edited there).
- `spec/write-pulse-width-decision.md` — no independent timing target.
- `sim/access-time/records/20260817-011948-4448966.md`,
  `sim/access-time/records/20260817-012005-4448966.md`,
  `sim/write-margin/records/20260817-105029-ce56f59.md` — the measurements
  cited above.
- `gf180mcu_fd_ip_sram__sram256x8m8wm1` Verilog / LEF / Liberty under
  `~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_ip_sram/`, and the
  `gf180mcu_fd_sc_mcu{7,9}t5v0` Liberty corner files.


## Addendum 2026-10-27 — open_pdks re-pin to `f6eeac7` (issue #173)

The PDK revision cited in the PDK path citations above (`c6d73a35f524070e85faff4a6a9eef49553ebc2b`,
`~/.volare`) is left as written; it is a true statement about the tree it was
read from. The repo pin is now `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`
(ciel 2.6.1, `~/.ciel`), defined once in `sim/lib/pdk_pin.txt` and enforced by
`sim/lib/pdk_env.sh`; see the addendum in `spec/pdk-variant-decision.md`.
Anything here read from `~/.volare` should be re-read from `~/.ciel`
when next relied on. Re-qualification of the records is tracked on #272.
