# design — schematics and netlists

Schematic capture is [xschem](http://xschem.sourceforge.net/); netlisting is
xschem's own batch netlister (invoked below); simulation is
[ngspice](http://ngspice.sourceforge.net/), per `CLAUDE.md`'s stated flow.
This directory holds T1 checklist item 1 (issue #21): the 6T bitcell and the
`spec/sram.md`-ratified 256 x 32 bitcell-array *core* — storage cells plus
their wordline/bitline/power ports only. Address decode, column mux, sense
amp and write driver (the rest of a full 1RW macro's pin list: `A`, `CEN`,
`CLK`, `D`, `Q`, `GWEN`, `WEN`) were out of that issue's scope; they are
issue #203's, see "Periphery and macro top (issue #203)" below.

```
design/
  xschemrc                repo xschem config: resolves the gf180mcu PDK,
                           adds design/ to the symbol search path
  bitcell_6t.sch           6T SRAM storage cell schematic
  bitcell_6t.sym           its subcircuit symbol (used by the array below)
  generate_array.py         generator: tiles bitcell_6t.sym into the
                           256 x 32 array schematic (see "Why a generator"
                           below)
  sram_256x32_array.sch     MACHINE-GENERATED 256 x 32 array schematic
                           (8,192 bitcell_6t instances) -- do not hand-edit
  netlist/
    bitcell_6t.spice         xschem-derived netlist of bitcell_6t.sch
    sram_256x32_array.spice  xschem-derived netlist of sram_256x32_array.sch
```

## The bitcell: `bitcell_6t.sch`

Standard 6T topology: two cross-coupled CMOS inverters (`MPL`/`MNL` storing
node `Q`, `MPR`/`MNR` storing `QB`) plus two NMOS access transistors (`MAL`,
`MAR`) gated by a shared wordline, connecting the storage nodes to a
differential bitline pair. This is the textbook 6T cell architecture — see
[OpenRAM](https://openram.org)'s `sky130_fd_bd_sram__sram_sp_cell` for the
same topology on a different PDK, cited per `CLAUDE.md` as a
reference/comparison point, not reimplemented from its source (OpenRAM has
no gf180mcu SRAM generator to draw from directly — see
`spec/bitcell-decision.md`).

Devices are gf180mcu's 3.3V core devices (`nfet_03v3` / `pfet_03v3`),
matching `spec/sram.md`'s single 3.3V supply target. Sizing (first-cut, not
yet SNM/write-margin optimized — that characterization is
`spec/sram.md`'s "Characterization" section, tracked by a downstream issue,
not this one):

| Device | Role | W | L |
|---|---|---|---|
| `MPL`/`MPR` | pull-up (`pfet_03v3`) | 0.22 um (device minimum) | 0.28 um |
| `MNL`/`MNR` | pull-down (`nfet_03v3`) | 0.36 um | 0.28 um |
| `MAL`/`MAR` | access (`nfet_03v3`) | 0.24 um | 0.28 um |

Cell ratio (pull-down/access) = 0.36/0.24 = 1.50 (> 1, for read stability).
Pull-up ratio (access/pull-up) = 0.24/0.22 = 1.09 (> 1, for writability). `L`
is drawn at both devices' model-default minimum (0.28 um) for density.

**On the reference bitcell's sizing**: `spec/bitcell-decision.md` cites
gf180mcu's own foundry-hardened SRAM IP (`gf180mcu_fd_ip_sram`) bitcell
subcircuit `018SRAM_cell1` as the topology reference. Its SPICE body is a
`*.SEEDPROM` black box in the shipped deck
(`libs.ref/gf180mcu_fd_ip_sram/spice/gf180mcu_fd_ip_sram__sram64x8m8wm1.spice`,
`.SUBCKT 018SRAM_cell1` / `** N=8 EP=0 IP=0 FDC=0` / `*.SEEDPROM` / `.ENDS`,
no device lines) — the foundry does not disclose that macro's actual
transistor sizing, only that it is an 8-device (`N=8`), 6T-family cell.
There is therefore no real sizing to cite or reproduce from that source;
this repo's sizing above is an independent first cut, consistent with
`spec/bitcell-decision.md`'s own instruction to use the foundry IP as a
topology reference, "not reimplement its exact topology verbatim."

**Ad hoc functional check** (not committed evidence — `sim/` testbenches and
formal PVT-corner SNM/write-margin measurement are a separate, downstream
issue; this was a same-session sanity check on the netlist below, not a
recorded result): `bitcell_6t.spice` was simulated standalone in ngspice
(typical corner, 27 C, VDD=3.3V) confirming (1) the cell holds a stored `1`
through a read access (`WL` pulsed, `BL`/`BLB` precharged to VDD — `Q`
stayed at 3.30V, `QB` returned to ~0V after the pulse) and (2) a
differential write pulse (`WL` asserted, `BL`=0V/`BLB`=VDD) flips it (`Q`:
3.30V -> ~0V, `QB`: ~0V -> 3.30V). This is a working bistable cell, not yet
a characterized one.

## The array: `sram_256x32_array.sch`

**Why a generator, not a hand-drawn sheet**: 256 x 32 = 8,192 bitcell
instances is not a schematic a human (or an agent driving the xschem GUI)
places by hand. `generate_array.py` writes xschem's plain-text `.sch`
format directly — the same "have the real tool do the mechanical step, and
write a script only for the part that isn't that step" split
`layout/bitcell/generate.py` / `layout/sram_256x32/generate.py` (issue #22,
PR #36) already established for the parallel GDS tiling, via the
`klayout.db` API there and direct `.sch`-text emission here (there is no
xschem Python/Tcl API surface for schematic construction as ergonomic as
`klayout.db`, so this repo's script emits the documented xschem file format
instead). **The generator does not touch netlisting** — `generate_array.py`
only produces `sram_256x32_array.sch`; turning that `.sch` into
`sram_256x32_array.spice` is xschem's own batch netlister, run unmodified,
exactly as it is for the hand-drawn `bitcell_6t.sch` (see "Regenerating the
netlists" below). That is what makes the netlist "mechanically derived from
the schematic source," per issue #21's acceptance criteria — the mechanical
step is xschem's, not this script's.

Connectivity technique: xschem merges nets purely by matching `lab=` text on
`lab_pin.sym` / `iopin.sym` / `ipin.sym` instances — no literal wire routing
is needed between instances that share a label. This is the same technique
`gf180-bandgap`'s (this org's other gf180mcu canary) `design/*.sch`
schematics use throughout (e.g. every device's bulk pin there is tied to
`vdd` via a short stub wire to a same-labelled `lab_pin`, not a routed
rail), applied here at array scale instead of by hand. Each bitcell
instance gets five such stubs:

- `WL0`..`WL255` — one wordline per row, shared by the 32 cells in that row
- `BL0`..`BL31`, `BLB0`..`BLB31` — one differential bitline pair per
  column, shared by the 256 cells in that column
- `VDD`, `VSS` — global rails, shared by all 8,192 cells

Top-level ports: 256 `WL<n>` inputs, 32 `BL<n>`/`BLB<n>` inout pairs, `VDD`,
`VSS` — the raw per-row/per-column array pins. This is the storage-array
*core* only; it does not yet expose `spec/sram.md`'s full 1RW macro pin list
(`A`, `CEN`, `CLK`, `D`, `Q`, `GWEN`, `WEN`) — that requires the periphery
(row decoder driving `WL<n>` from `A`, column mux + sense amp + write driver
multiplexing `BL<n>`/`BLB<n>` to `D`/`Q`), which is not drawn here, matching
`layout/README.md`'s equivalent scoping note for the parallel GDS array.

## Periphery and macro top (issue #203)

Implements the blocks of [`spec/periphery-architecture.md`](../spec/periphery-architecture.md)
(#202) as schematics and netlists, plus a macro top whose boundary is exactly
the #198 pins. **Schematic level only**: no layout, no extraction, no
characterisation. Every transistor size below is a first-cut smoke-sim value
chosen by this issue (the record sizes nothing); none is optimised.

```
design/
  generate_periphery.py     generator for everything below (stdlib only)
  regen_periphery.sh        generator + `klt netlist` for every block (--check = drift gate)
  check_macro_pins.py       asserts the macro netlist's ports == the #198 pin list
  xschemrc.lvs              xschemrc + `lvs_netlist 1` (live top-level .subckt)
  sram_64x128_array.sch/.sym  the 4:1 physical array (generate_array.py --rows 64 --cols 128)
  sram_256x32.sch           macro top (LVS reference): netlist/sram_256x32.spice
  sram_ctrl, row_path, col_decode, precharge_slice, io_slice   blocks
  inv* nand* and* nor3 rowdrv tg_* dff sa_latch wdrv           leaf cells
  netlist/<block>.spice     klt-netlist output, one per .sch (24 files)
```

**4:1 array, new file name.** The record says to regenerate the array as 64 rows
x 128 columns "via `generate_array.py --rows 64 --cols 128`". It is written to
**`sram_64x128_array.*`** instead of over `sram_256x32_array.*`: the committed
256 x 32 netlist is the LVS reference for the committed 256 x 32 layout
(`layout/reports/generate.sh`, `layout/reports/lvs-array.json`) and the `views/`
abstract, and overwriting it would make that evidence describe a design that is
no longer there. The 256 x 32 files are untouched. Same bitcell, 8,192
instances, `WL0..WL63`, `BL0..BL127`, `BLB0..BLB127`. Retiring the 256 x 32
files is #204/#206's call when the layout moves to 4:1.

### Hierarchy and what each block is

| Block | Contents (record row) |
|---|---|
| `sram_ctrl` | `CLK` buffer; flops on rising `CLK` for `A[7:0]`, `CEN`, `GWEN` (row 10); self-timed pulse generation (row 11) |
| `row_path` | `A[7:2]`: two 3->8 predecoders (`A[7:5]` gated by `wl_en`, `A[4:2]`), 64 x `rowdrv` (2-input AND whose output inverter is the wordline driver) (row 4) |
| `col_decode` | `A[1:0]` -> `csel[3:0]`/`cseln[3:0]`, gated by `wl_en` (rows 2, 3, 5) |
| `precharge_slice` x32 | 3 PMOS per column (two precharge, one equalise), 4 columns; released only for the selected column (row 9) |
| `io_slice` x32 | 8 transmission gates (4 per line) onto one shared pair; one latch sense amp; one write driver; `D`/`WEN` input flops; `Q` register flop (rows 3, 5-8, 10) |
| `sram_256x32` | the above, plus the array; ports `A[7:0]`, `CEN`, `GWEN`, `CLK`, `D[31:0]`, `WEN[31:0]`, `Q[31:0]`, `VDD`, `VSS` = 107 signals + 2 supplies |

Physical column `p = 4*i + s` for I/O bit `i` and select `s` (row 3); row =
`A[7:2]`, select = `A[1:0]` (row 2). `Q` is a flop clocked by a read-only strobe
(`q_clk`), so it is loaded only on a read and holds across writes and idle
cycles (row 7). A masked bit (`WEN[i]` = 1) leaves its write driver off (row 8).
Transistor counts (flattened): array 49,152; periphery 4,476; macro 53,628.

### Column-mux device type: transmission gate

The record leaves NMOS / PMOS / transmission gate open (row 5) with one
constraint: the read path must pass a bit line near `VDD`, the write path must
pull one to `VSS`. An NMOS pass gate passes a high only to `VDD - Vt` (and body
effect makes it worse), which starves the latch sense amp of common-mode; a PMOS
pass gate passes a low only down to `|Vtp|`, which cannot force a cell write.
A transmission gate (W 2 um N / 3 um P, `tg_mux`) passes both full-swing. The
cost is two devices per line per column and a complementary select pair
(`csel`/`cseln`). That is a reasoned choice, not a measured one: the smoke sim
shows it works at one corner and says nothing about which of the three is
smallest or fastest at every corner.

### Self-timed control (record rows 11-12)

`p = clk_buf & ~delay(clk_buf)` is a pulse that starts at the rising edge and
ends after a 35-stage `inv_dly` chain, so the pulse **end** is set by the delay
path, not by the `CLK` falling edge (the record's reason for departing from
OpenRAM's two-phase scheme). Then `wl_en = p & delay(p) & ~CEN` (decode settles
first), `s_en = wl_en & delay(wl_en) & read` (read only), `q_clk = s_en &
delay(s_en)` (strobes the `Q` flops), `wpn = ~(wl_en & write)`. The delay chain
is a plain inverter chain: the record's "replica/delay path" is the *delay*
variant, **not** a replica bit line, so `s_en` does not track the real
bit-line differential across PVT or array loading. Whether that is enough is
open and belongs with the corner sweep and #204's extracted loads. The `CLK`
high time must exceed the chain delay (about 5 ns nominal); no minimum clock
width is ratified or claimed.

**Write pulse >= 2 ns (row 12): met at all 27 corners.** The internal write
pulse (`wpn` low) of the control block, swept over the full ff/tt/ss x
-40/25/125 C x 2.97/3.30/3.63 V set on the batch fleet
(`sim/macro-smoke/records/20261018-082301-37ba562.md`), is 2.50 ns at its
smallest (`ff_-40c_3.63v`) and 5.98 ns at its largest (`ss_125c_2.97v`); the
nominal-only record `20261018-072248-f452949` (3.69 ns) is superseded. No
corner is under 2 ns, so the alternative clause of row 12 (a `sim/write-margin/`
re-run against a fixed 2 ns window) is not triggered. This is a schematic-level,
control-block-alone result with capacitor stand-ins for the loads; no wire RC,
no layout parasitics, no cycle time or clock-to-`Q` is claimed.

### What the smoke simulation does and does not show

`sim/macro-smoke/` (records `20261018-072247-f452949`, from the since-removed local `run.sh` flavor; the 27-corner
batch sweep of the same checks is `20261018-082302-37ba562`, 27/27 pass): ten
cycles at `tt_25c_3.30v`, one local corner. Write 0xDEADBEEF to 0xA7 and 0x12345678 to
0x3C, read both back, per-bit-masked write (low half masked) to 0xA7 reads back
0xFFFFBEEF, a `CEN`=1 cycle with `GWEN`=0 and fresh data does not write and `Q`
holds. All pass. Limits, in the record and repeated here because they are
easy to lose: the array is **reduced** to the two addressed rows with a 20 fF
bit-line stand-in (the full 8,192-cell transient did not finish in 10 minutes
on a shared host); no wire RC (the wordline RC gate is #204's); no sense-amp
offset claim (needs Monte Carlo per `spec/statistical-treatment-decision.md`;
none is made); no timing. PVT: the functional pass holds at all 27 corners, but
that is a pass/fail on the written words, not a margin. The existing `sim/` array-level evidence on
the 256 x 32 array is not rewritten.

### Netlisting

`klt netlist` with `--rcfile design/xschemrc.lvs` (not `--block`). While
building this, `--block` left the continuation lines of a wrapped top-level
pin list as `*+` comments, so the macro's pin list silently shrank to the first
line's ports (filed upstream as `2AMLogic/klayout-tools#3899`, closed the same
day; the klt on this host, `0.7.1.dev1909`, now keeps the `+` lines). Two
reasons `xschemrc.lvs` stays: xschem's `lvs_netlist` option gives a live
`.subckt` without depending on that fix, and `--block` still joins bus bits with
commas (`A[7],A[6],...`) where `lvs_netlist` gives space-separated ports.
Whether ngspice accepts the comma form was not tested. `check_macro_pins.py`
guards the pin list either way. Every netlist here ends in a bare `.end`, like
the existing ones.

## Regenerating the netlists

```bash
export PDK_ROOT="$HOME/.volare"     # parent of gf180mcuD/ -- adjust to your install
export PDK=gf180mcuD

# 1. (Only if sram_256x32_array.sch needs to change) regenerate the array
#    schematic from the generator -- pure function of --rows/--cols, no
#    wall-clock or environment-dependent content, so re-running it
#    reproduces the committed file byte-for-byte:
python3 design/generate_array.py --rows 256 --cols 32 \
    --out design/sram_256x32_array.sch

# 2. Netlist both schematics with xschem's batch netlister:
xschem -n -x -q -r --rcfile design/xschemrc -o design/netlist design/bitcell_6t.sch
xschem -n -x -q -r --rcfile design/xschemrc -o design/netlist design/sram_256x32_array.sch
```

`design/xschemrc` resolves the gf180mcu PDK from `GF180_PDK_PATH`, then
`PDK_ROOT`+`PDK`, then the usual install-prefix search (volare first,
matching the convention `gf180-bandgap`'s `design/xschemrc` established for
this org's gf180mcu canary blocks), sources the PDK's own xschemrc so the
`nfet_03v3`/`pfet_03v3` device symbols are on the library path, and adds
`design/` to the symbol search path so `sram_256x32_array.sch` finds
`bitcell_6t.sym` next to `bitcell_6t.sch` (xschem only auto-descends into a
child schematic when the referencing symbol sits at the same relative path
as the same-named `.sch`).

**Absolute-path exception (issue #109)**: xschem's own batch netlister writes
a `** sch_path: <absolute path>` / `** sym_path: <absolute path>` header
comment into every `.spice` file it generates -- this is xschem's own
netlist-writer behavior, not something `design/xschemrc` (or any other file
in this repo) controls or has a lever over. Every committed
`design/netlist/*.spice` therefore carries whatever checkout path produced
it (e.g. a `.loom/worktrees/issue-N/...` path on an agent host). This is a
documented, accepted exception to this repo's otherwise-absolute-path-free
evidence convention, not a bug to fix here: the header comment is inert
(ngspice ignores `**`-prefixed lines), it never feeds any recorded
measurement, and a re-netlist from a different checkout reproduces the same
device-level netlist body byte-for-byte modulo that one header line (see
"Freshness" below).

**Freshness (issue #21's reproducibility acceptance criterion)**: verified
directly, twice, on the versions below — `design/generate_array.py` run
twice produces a byte-identical `sram_256x32_array.sch`; `xschem`'s batch
netlister, re-run twice (with `design/netlist/*.spice` deleted between
runs) on both `bitcell_6t.sch` and `sram_256x32_array.sch`, produces
byte-identical `.spice` output both times, with zero errors or warnings.
The full 8,192-cell array netlists in well under a minute (netlist size:
`sram_256x32_array.sch` is 90,466 lines / 3.5 MB; the resulting
`sram_256x32_array.spice` is 8,557 lines / 364 KB — one shared
`.subckt bitcell_6t` definition plus 8,192 `X` instances of it, not 8,192
flattened device copies). If this ever fails to reproduce (e.g. after a
device-sizing change to `bitcell_6t.sch`, or a `--rows`/`--cols` change),
that means the committed netlist is stale relative to the committed
schematic — regenerate and re-commit both together.

## Tool / PDK versions used

- `xschem` V3.4.7 (Homebrew, macOS) for the bitcell and 256 x 32 array
  netlists; V3.4.4 (Linux, via `klt netlist`) for the #203 netlists. The two
  differ only in where they wrap long lines (re-netlisting `bitcell_6t.sch`
  with 3.4.4 gives the same devices on re-wrapped lines), so the older
  committed netlists were left as they are
- `ngspice` ngspice-47 (used for the ad hoc functional check above; not
  required to regenerate the netlists themselves)
- Python 3.14 (`generate_array.py`; stdlib only, no third-party
  dependencies)
- PDK: `gf180mcuD`, `open_pdks` commit
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (same commit
  `spec/bitcell-decision.md` verified against), installed via
  [volare](https://github.com/efabless/volare) under `~/.volare/gf180mcuD`
  — see `spec/pdk-variant-decision.md` for why `gf180mcuD`, not the
  `gf180mcuC` this section cited before, and why nothing above needed to be
  re-run as a result (SPICE device models are byte-identical between the
  two variants)

## Related

- `spec/sram.md` — ratified organization (1 kB, 256 x 32, single fixed
  instance) and port target (1RW) this design targets.
- `spec/bitcell-decision.md` — the decision record establishing that
  gf180mcu's 6T bitcell exists only embedded in `gf180mcu_fd_ip_sram`, not
  as a standalone primitive, so this repo draws its own.
- `spec/pdk-variant-decision.md` — pins `gf180mcuD` as the PDK variant cited
  above, and shows why none of this design's netlists needed to be
  regenerated as a result.
- `layout/README.md` — the parallel GDS-side array-tiling generator (issue
  #22, PR #36) was originally built against an explicitly-labeled
  placeholder bitcell because this issue had not yet landed. PR #55
  (`ce56f59`) replaced that placeholder with a real, device-level 6T
  bitcell layout derived from `bitcell_6t.sch`'s sizing, tiled into the
  256 x 32 array; see `layout/README.md`'s "Status (2026-08-16)" section
  for DRC/LVS results.
