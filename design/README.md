# design — schematics and netlists

Schematic capture is [xschem](http://xschem.sourceforge.net/); netlisting is
xschem's own batch netlister (invoked below); simulation is
[ngspice](http://ngspice.sourceforge.net/), per `CLAUDE.md`'s stated flow.
This directory holds T1 checklist item 1 (issue #21): the 6T bitcell and the
`spec/sram.md`-ratified 256 x 32 bitcell-array *core* — storage cells plus
their wordline/bitline/power ports only. Address decode, column mux, sense
amp and write driver (the rest of a full 1RW macro's pin list: `A`, `CEN`,
`CLK`, `D`, `Q`, `GWEN`, `WEN`) are periphery, out of this issue's scope; see
"Scope" below.

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

## Regenerating the netlists

```bash
export PDK_ROOT="$HOME/.volare"     # parent of gf180mcuC/ -- adjust to your install
export PDK=gf180mcuC

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

- `xschem` V3.4.7 (Homebrew, macOS)
- `ngspice` ngspice-47 (used for the ad hoc functional check above; not
  required to regenerate the netlists themselves)
- Python 3.14 (`generate_array.py`; stdlib only, no third-party
  dependencies)
- PDK: `gf180mcuC`, `open_pdks` commit
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (same commit
  `spec/bitcell-decision.md` verified against), installed via
  [volare](https://github.com/efabless/volare) under `~/.volare/gf180mcuC`

## Related

- `spec/sram.md` — ratified organization (1 kB, 256 x 32, single fixed
  instance) and port target (1RW) this design targets.
- `spec/bitcell-decision.md` — the decision record establishing that
  gf180mcu's 6T bitcell exists only embedded in `gf180mcu_fd_ip_sram`, not
  as a standalone primitive, so this repo draws its own.
- `layout/README.md` — the parallel GDS-side array-tiling generator (issue
  #22, PR #36), built against an explicitly-labeled placeholder bitcell
  because this issue had not landed yet; that placeholder should be
  replaced with a real bitcell layout derived from `bitcell_6t.sch`'s sizing
  as a follow-up now that this issue has landed.
