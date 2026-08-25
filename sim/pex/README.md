# sim/pex -- post-layout PEX (issue #23 T1 item 7, closed out by #95)

## Status

Issue #23 grouped T1 items 3 (DRC clean), 4 (LVS clean), and 7 (post-layout
PEX) into one verification pass. Items 3 and 4 closed with committed,
provenance-carrying reports (`layout/reports/`). Item 7 could **not** close
against the ratified T1-item-9 testbenches directly (#24,
`sim/{read-snm,hold-snm,write-margin,access-time}/testbench/*.spice`) --
`klt pex` refuses to run against any of the five without modification, for
reasons that turned out to be structural, not a missing flag or a stale
tool version (see "What was tried against the #24 testbenches themselves"
below, preserved from the original #23 writeup).

Issue #95 closed item 7 for real, per-measurement, with **new, parallel**
artifacts -- none of the ratified #24 testbench sources were modified:

| Measurement | Path | Result |
| --- | --- | --- |
| Write access time | `klt pex`-native (`access-time/`) | **Closed** -- genuine 27-corner schematic-vs-extracted delta, `status: pass`, `delta` non-empty, `reference_netlist` names the real DUT. |
| Read access time | `klt pex`-native (`access-time/`) | **Closed** -- same, 27/27 corners. |
| Write margin (write trip voltage) | By-hand extraction workflow (`write-margin/`) | **Closed** -- `klt pex` itself cannot run this testbench's bisection search (no `.meas`-only equivalent), so this replicates its intent by hand: `klt extract --parasitics` + `sim/lib/run_corner_sweep.sh` run twice (schematic SUBCKT vs extracted netlist), diffed per corner. 27/27 corners, genuine non-vacuous delta. |
| Read SNM / hold SNM | N/A | **No PEX-compatible path exists** -- structural, not a tooling gap; see "read-snm/hold-snm: no PEX-compatible path" below. |

Issue #106 re-ran every measurement above against the post-issue-#103
bitcell revision (see "Freshness" below); the pre-#103 records that first
closed item 7 remain committed, unedited, under `pre-issue-103/`.

Per `CLAUDE.md`'s "no claim without a testbench": every delta below is a
real `ngspice` run, not an interpolation or an assumption, and none of it
relaxes `spec/sram.md`'s ratified corner set or measurement definitions --
each parallel testbench measures the same physical quantity the ratified
#24 testbench measures, at the same 27 ratified corners, with the specific,
disclosed simplifications each subdirectory's own testbench file documents
inline.

## `access-time/` -- `klt pex`-native (closed)

`access-time/dut/bitcell_6t_subckt.spice` -- a `.SUBCKT`-wrapped copy of
`design/netlist/bitcell_6t.spice`'s own six device cards (mechanically
derived by `access-time/dut/generate.sh`, never hand-transcribed), with a
pin interface (`BL BLB Q QB VDD VSS WL`) matching `klt extract`'s own
output byte-for-byte. This is what makes a `klt-pex`-native testbench
possible at all: the ratified testbenches `.include` `bitcell_6t.spice`
**flat** (its own `.subckt`/`.ends` wrapper is commented out by xschem's
netlister -- see `sim/README.md`), which is exactly what those testbenches
need but is incompatible with `klt pex`'s DUT-`.include`-swap convention
(`docs/cli/pex.md` "The DUT `.include` swap" needs a `.SUBCKT` on both
sides with a matching interface).

`access-time/testbench/tb_{read,write}_access_time.pex.spice` -- new,
parallel `klt sim` request netlist bodies (circuit-body-only, no
`.control`/`.end` of their own, per `docs/cli/sim.md`'s "Netlist
convention"). Each `.include`s exactly one file (the DUT wrapper above) and
instantiates it via `XDUT BL BLB Q QB VDD VSS WL sram_bitcell_6t`. Three
disclosed simplifications relative to the ratified #24 testbenches (each
documented inline, in the file that makes the tradeoff):

1. **PVT axis via `corners.process`/`supply_v`/`temperature_c`, not
   `corner.inc`.** A `klt sim` request's netlist body is corner-invariant
   text -- it cannot run the ratified testbenches' own `.param VDDC`-based
   per-corner substitution. Every voltage waveform that needs to track the
   swept VDD instead references the real `VDD` circuit node through a
   behavioral B-source (`V='V(ctrl)*V(VDD)'`), since `corners.supply_v`
   `alter`s that node directly and a behavioral expression re-evaluates
   against its actual value every timestep.
2. **Fixed literal `.ic` starting point (2.8V), not a per-corner one.** The
   ratified testbenches set `.ic v(QB)='VDDC'` (the exact corner voltage,
   available via `.param VDDC`); this file's body cannot reference the
   swept VDD in a `.ic` card, so it uses 2.8V -- comfortably below the
   27-corner matrix's lowest supply (2.97V) and far from the Q=QB
   metastable point, so the pair's own feedback settles onto whichever
   corner's real VDD is actually altered in, well before the measured
   event. See "Verification of the `.ic` simplification" below.
3. **Fixed literal sensing/switch thresholds, not per-corner-VDD-relative
   ones.** The ratified read-access-time testbench's bit-line switch model
   and 3%-of-VDD sensing threshold are corner-relative (`Vt='VDDC/2'`,
   `val=VDDC*0.03`); `.meas` cards here are supplied by the request
   document as literal text reused across every corner, so they use fixed
   nominal-VDD-relative values (`Vt=1.65V`, `Vh=0.1V`, a 0.1V sensing
   differential) instead. These are a **different**, simpler proxy
   threshold than the ratified testbench's own -- not a claim of numeric
   equivalence to it. They still work at every ratified corner (PRE/WL
   swing rail-to-rail via the same behavioral-source technique regardless
   of the fixed threshold's exact value).

`access-time/requests/{read,write}-access-time.request.json` -- the `klt
sim` request documents: full 3x3x3 process/temperature/supply matrix
(`ff`/`typical`/`ss` bundled as `ff`/`tt`/`ss`, matching this repo's
vocabulary), `models.lib` resolved via `$PDK_ROOT`/`$PDK` (env-var
expansion, matching this repo's existing PDK-pin convention -- portable,
no machine-specific path committed).

`access-time/generate.sh` runs `klt pex layout/bitcell/sram_bitcell_6t.gds
<request> --deck gf180mcu --pdk $PDK --pdk-root $PDK_ROOT` for both
measurements and writes `access-time/reports/{read,write}-access-time.pex.json`
(the full `klt pex` JSON envelope: `delta[]`, `provenance`, `pin_count_mismatch:
null`) plus `access-time/reports/klt-pex-artifacts/<name>/` (the
extracted-side netlist and generated testbench copy `klt pex` itself wrote,
kept for inspection).

### `.options rshunt` -- a new finding beyond #23's own three

Running the extracted leg for real surfaced a **fourth** structural gap,
not identified during #23: `klt extract --parasitics` lands every net's
substrate-coupling capacitance on an internal net named `vsubs`, which is
**not** exposed as a `.SUBCKT` pin -- it is a private, per-instantiation
net inside the extracted `.SUBCKT`. With no DC path to any external
reference, ngspice's DC/transient solve on the extracted leg hits a
singular matrix on that node at *every* corner:

```
Warning: singular matrix:  check node xdut.vsubs
Warning: singular matrix:  check node xdut.vsubs
Warning: Dynamic gmin stepping failed
...
```

ngspice's own gmin-stepping recovery sometimes produces *a* result anyway,
but the recovered operating point was observed to be inconsistent between
two different `print` passes in the same run during this issue's own
investigation -- not trustworthy evidence. `.options rshunt=1e12` (a large
resistor from every node to ground, ngspice's own documented remedy for
exactly this floating-node-singularity class) clears the warning entirely
and produces a stable, reproducible operating point; declared
unconditionally in both PEX-native testbench bodies (confirmed
byte-identical measured values with/without it on the schematic leg, which
has no floating nodes). This is worth its own klayout-tools friction
report (generic, no design-specific detail) as a follow-up to
klayout-tools#1255 -- filed as **klayout-tools#1263**, "`klt extract
--parasitics`: substrate-coupling net not exposed as a pin or globally
tied, causing a singular-matrix DC solve on every simulated corner of the
extracted netlist."

### Verification of the `.ic` simplification

Both PEX-native testbench bodies start from a fixed `.ic v(QB)=2.8` (not a
per-corner value) -- see simplification 2 above for why. The committed
27-corner results in `access-time/reports/*.pex.json` are the evidence this
does not silently break at either end of the ratified matrix: **every**
corner from `ff/2.970V/-40C` (lowest ratified supply) through
`ss/3.630V/125C` (highest) produced `status: "pass"` with no `error`/`fail`
row and no diagnostic naming a convergence anomaly -- inspect any
`delta[]` row's `corner_id` in either committed report to confirm.

### Results

**Current (post-issue-#103 bitcell, re-run by issue #106):**

`write-access-time`: extracted access time is consistently **~32-46%
slower** than schematic across the matrix (e.g. `tt/3.300V/25C`: schematic
70.9ps, extracted 98.4ps, `delta_pct: +38.8`) -- expected, since the write
path routes current through the extracted netlist's series-R/ground-C on
`BL`/`BLB`/`Q`/`QB` that the schematic leg has none of. 27/27 corners
`status: pass`.

`read-access-time`: extracted is **~3-5% slower** (e.g. `tt/3.300V/25C`:
schematic 25.8ps, extracted 26.8ps) -- a smaller relative delta than write
access time because the read proxy metric (bit-line sensing differential)
is dominated by the 20fF bit-line capacitance placeholder both legs share,
not by the bitcell's own extracted parasitics. 27/27 corners `status: pass`.

Full per-corner data: `access-time/reports/write-access-time.pex.json`,
`access-time/reports/read-access-time.pex.json`.

No corner's `pass`/`fail` verdict moved relative to the pre-issue-#103
baseline preserved at `pre-issue-103/access-time/reports/*.pex.json`
(both directions were `27/27 pass` before and after the bitcell fix) -- the
shift is confined to the `delta_pct` magnitudes above, from the wider
`CO_ENC_M1` M1 straps.

## `write-margin/` -- by-hand extraction workflow (closed)

`klt pex` cannot run the ratified write-margin testbench's own search at
all -- its write-trip-voltage bisection (`dowhile`/`alterparam`, see
`sim/write-margin/testbench/tb_write_margin.spice`'s own header) is a
`.control`-block *algorithm*, not a single declarative `.meas` card `klt
sim`'s request format can express. Per issue #95's own suggested path,
this instead replicates `klt pex`'s intent **by hand**, using the
*existing* `sim/lib/run_corner_sweep.sh` machinery (unmodified) against two
new, parallel testbenches that are otherwise byte-identical to the ratified
one:

- `write-margin/testbench/tb_write_margin_schematic.spice` -- same
  `VBL`/`VBLB`/`VWL` phases and bisection `.control` block as the ratified
  testbench, `.include`s `../access-time/dut/bitcell_6t_subckt.spice`
  (reused, not duplicated) via `X`-instantiation instead of a flat
  `.include`.
- `write-margin/testbench/tb_write_margin_extracted.spice` -- identical
  except its DUT `.include` targets `write-margin/dut/extracted-netlist.spice`
  (a fresh `klt extract --deck gf180mcu --pdk gf180mcuD --parasitics`
  run, `--pdk`-bound to real `nfet_03v3`/`pfet_03v3` subcircuits --
  see "Why `--pdk` binding matters" below).

`write-margin/generate.sh` runs `write-margin/dut/generate.sh` (the
extraction), then `sim/lib/run_corner_sweep.sh` against both testbenches
(minting two ordinary append-only evidence records under
`write-margin/{corners,records,netlist-snapshots}/`, in the exact same
format every other `sim/<experiment>/` directory uses), then
`write-margin/compare_records.py` (a small script that reads both records'
per-corner `RESULT: write_trip_voltage_v = ...` lines and writes a
`delta[]`-shaped table to `write-margin/delta/<schematic-id>_vs_<extracted-id>.md`
-- deliberately mirroring `klt pex`'s own JSON `delta[]` schema in
Markdown form, since `klt pex` itself never runs this measurement).

**Known cosmetic limitation**: `run_corner_sweep.sh` (reused unmodified,
per this issue's own guardrails and its "Affected Files" note that it is
"existing PVT sweep machinery, reusable for a by-hand extraction
workflow") always writes its generated record's own **Netlist provenance**
field as `schematic (<testbench path>, DUT per design/netlist/bitcell_6t.spice
at <sha>)` verbatim, regardless of which testbench it ran or what DUT that
testbench actually `.include`s -- it has no "extracted" mode and does not
introspect the testbench body. Both write-margin records here therefore
carry that same boilerplate string even for the extracted-leg record
(whose real DUT is `write-margin/dut/extracted-netlist.spice`, not
`design/netlist/bitcell_6t.spice`); each record's own **Claim** line and
the testbench *path* in that same provenance field (`tb_write_margin_extracted.spice`
vs `tb_write_margin_schematic.spice`) are the authoritative signal, not the
auto-generated "DUT per ..." clause.

### Why `--pdk` binding matters

`klt extract --deck gf180mcu --parasitics` (no `--pdk`) -- the invocation
`../generate.sh` (top-level `sim/pex/generate.sh`) uses for the committed
`extracted-netlist/sram_bitcell_6t.spice` -- writes each transistor as an
`M`-card whose model name is gf180mcu's bare, curated-deck class label
(`nfet`/`pfet`), which **no real PDK ships as a directly-simulatable
model** (see `docs/cli/extract.md` "SPICE model binding"). That netlist is
correct, useful evidence for the R/C summary it reports, but it cannot
itself be `.lib`'d against `sm141064.ngspice` and simulated. Adding `--pdk
gf180mcuD` binds each device to a real `X ... nfet_03v3`/`pfet_03v3`
subcircuit call instead, which is what both the `access-time/` PEX-native
testbenches and this by-hand write-margin workflow actually need to run
`ngspice`. `write-margin/dut/generate.sh` and `access-time/generate.sh`
both pass `--pdk`/`--pdk-root` for exactly this reason.

### Results

**Current (post-issue-#103 bitcell, re-run by issue #106):**

Extracted write trip voltage is consistently **~0.2-2.9% lower** than
schematic across all 27 corners (e.g. `tt_25c_3.30v`: schematic 1.910V,
extracted 1.878V, `delta_pct: -1.687`) -- physically sensible: bit-line and
internal-node parasitic loading from the extracted layout makes the write
path slightly weaker, so the weakest '0' the driver can still successfully
write is slightly closer to 0V (a smaller trip voltage) than the ideal
schematic case. 27/27 corners `status: pass`. Full per-corner table:
`write-margin/delta/20260822-093425-fc6ce30_vs_20260822-093435-fc6ce30.md`.

No corner's `pass`/`fail` verdict moved relative to the pre-issue-#103
baseline (`write-margin/delta/20260821-085734-b56cc29_vs_20260821-085745-b56cc29.md`,
also `27/27 pass`) -- the shift is confined to the `delta_pct` magnitudes,
from the wider `CO_ENC_M1` M1 straps.

## `read-snm`/`hold-snm`: no PEX-compatible path

**Conclusion: no PEX-compatible path exists for read SNM or hold SNM --
this is structural, not a tool gap, and not fixable by a different DUT-swap
convention.**

Both ratified testbenches (`sim/read-snm/testbench/tb_read_snm.spice`,
`sim/hold-snm/testbench/tb_hold_snm.spice`) build a **device-level
replica** of one storage inverter directly -- their `XMP`/`XMN`/`XMA`
device cards are hand-copied literals (same models, same W/L, same
parasitic-area formulas as `design/netlist/bitcell_6t.spice`, cited
verbatim in each testbench's own header), not an `.include` +
`X`-instantiation of any DUT file at all. This is the documented,
deliberate workaround for a structural limitation Seevinck's own SNM
method runs into on a black-box bistable cell: the classic butterfly-curve
extraction needs to sweep one storage inverter's input while independently
reading the *other* inverter's output, which means **breaking the
cross-coupled feedback loop** -- and `bitcell_6t`'s two storage nodes (Q,
QB) are wired directly to each other's gates with no port to inject a
decoupling source through from outside (see `sim/README.md`'s "Why two of
the testbenches don't `.include` the DUT").

This rules out `klt pex`'s DUT-`.include`-swap convention by construction
(item 3 in "What was tried against the #24 testbenches themselves" below)
-- but it *also* rules out a hand-rolled comparison analogous to
write-margin's, for a reason specific to PEX rather than to the testbench
format:

- A hand-rolled PEX comparison needs an **extracted** netlist for the
  circuit the schematic-side fixture measures -- i.e. parasitics for *one
  isolated storage inverter with its output independently accessible*, the
  same decoupled topology the schematic fixture builds at the device
  level.
- The only layout artifact that exists is `layout/bitcell/sram_bitcell_6t.gds`
  -- the **whole** 6T cell, laid out and routed as one placed unit with no
  drawn boundary demarcating "one inverter's own geometry" from the other's
  or from the shared bit-line/word-line routing. `klt extract`
  (and `klt pex`) extract a named top cell's full geometry; there is no
  mechanism (in this tool or in the SNM measurement's own definition) to
  partition an already-laid-out 6T cell into an independently-extractable
  half-cell with a physically meaningful parasitic boundary at the break
  point Seevinck's method needs.
- Using the *whole-cell* extracted netlist instead (`access-time/dut`'s or
  `write-margin/dut`'s extraction, both of which **do** expose `Q`/`QB` as
  real `.SUBCKT` pins) does not solve this either: forcing one of those pins
  externally to sweep the other inverter's input would fight the *other*
  inverter's own extracted devices, which are still actively driving that
  same node inside the extracted `.SUBCKT` -- exactly the loop-breaking
  problem the schematic-level fixture exists to route around, reproduced
  identically (not solved) at the extracted level. There is no pin-forcing
  trick that decouples a loop from the *outside* when both halves of that
  loop are still wired together on the *inside*.

Closing this for real would need laying out and independently extracting
one storage inverter in isolation (a new, from-scratch layout deliverable,
not a testbench adaptation) -- out of this issue's scope by construction
(issue #95 is a testbench-adaptation issue against the existing, already-
ratified `layout/bitcell/sram_bitcell_6t.gds`). This conclusion itself is
the honest result issue #95's own acceptance criteria asked for on this
pair: "an explicit statement (with evidence) that a hand-rolled comparison
is the honest path for this pair" is itself not available either, for the
structural reason above -- narrower than write-margin's own "by-hand
extraction, then diff" resolution.

## Freshness: re-extracted against the issue #103 bitcell revision (issue #106)

Every parasitic number under `sim/pex/` was originally extracted from the
bitcell GDS **as it stood before issue #103** (`provenance.input.content_hash`
`sha256:6b90b7d6...`). Issue #103 fixed 21 real native-deck DRC violations in
`layout/bitcell/generate.py`, which changed the drawn geometry — most
relevantly the Metal1 cross-couple strap width (0.28µm -> 0.36µm, from
`CO_ENC_M1` 0.03 -> 0.07) and the row pitch (5.39µm -> 5.40µm). Issue #106
re-ran every `generate.sh` in this directory against the post-#103 GDS
(`sha256:53d2b7aa...`, matching the currently-committed
`layout/bitcell/sram_bitcell_6t.gds`):

- `extract-report.json` / `extracted-netlist/sram_bitcell_6t.spice` --
  re-extracted; `provenance.input.content_hash` now equals
  `sha256sum layout/bitcell/sram_bitcell_6t.gds`.
- `access-time/reports/{read,write}-access-time.pex.json` -- re-run,
  `27/27 pass` both directions, same as pre-#103 (see "Results" above).
- `write-margin/` -- new record pair
  `20260822-093425-fc6ce30` (schematic) /`20260822-093435-fc6ce30`
  (extracted), new delta `write-margin/delta/20260822-093425-fc6ce30_vs_20260822-093435-fc6ce30.md`,
  `27/27 pass`, same as pre-#103.

**No PASS/FAIL verdict moved** in either the access-time or write-margin
27-corner deltas -- the wider M1 straps shifted `delta_pct` magnitudes by a
small amount (see each subdirectory's "Results" section above) but did not
flip any corner. `sim/signoff-summary.md` and
`measurements/characterization-report.md` were therefore left unchanged
(neither file cites `sim/pex/`'s PEX-native deltas at all -- both roll up
the ratified `sim/{read-snm,hold-snm,write-margin,access-time}/` schematic
records directly, which this issue did not touch).

Per `CLAUDE.md`, `sim/` is append-only evidence — the pre-#103 records were
never overwritten or back-dated. Because `sim/pex/generate.sh` and
`access-time/generate.sh` (unlike `write-margin/`'s own
`sim/lib/run_corner_sweep.sh`-based records) write to a single fixed path
rather than minting a per-run record ID, issue #106 first snapshotted their
pre-#103 output byte-for-byte into `pre-issue-103/` (see that directory's
own `README.md`) before re-running them -- so the pre-fix evidence stays
directly readable in the tree, not just recoverable via `git log`.

## `generate.sh` / `extracted-netlist/` / `extract-report.json`

`./generate.sh`, `./extract-report.json`, and
`./extracted-netlist/sram_bitcell_6t.spice` were introduced by PR #96 and
re-run against the post-#103 GDS by issue #106: a
`klt extract --deck gf180mcu --parasitics` run (no `--pdk` binding -- see
"Why `--pdk` binding matters" above for why that specific invocation is not
directly simulatable, and is retained here only as R/C-summary evidence,
superseded for simulation purposes by
`access-time/dut/bitcell_6t_subckt.spice`'s klt-pex-native extraction and
`write-margin/dut/extracted-netlist.spice`'s `--pdk`-bound one).

```bash
./sim/pex/generate.sh                 # regenerates extract-report.json + extracted-netlist/ (unbound, R/C-summary only)
./sim/pex/access-time/dut/generate.sh # regenerates the schematic SUBCKT DUT wrapper
./sim/pex/access-time/generate.sh     # regenerates read/write access-time klt pex reports
./sim/pex/write-margin/generate.sh    # regenerates the by-hand write-margin schematic-vs-extracted delta (mints new append-only records)
```

## What was tried against the #24 testbenches themselves (original #23 findings, preserved)

All three findings below were reproduced directly against this repo's own
committed layout and testbenches during #23, not hypothesized, and remain
true today: `klt pex` still cannot run any of the five ratified #24
testbenches *unmodified*. #95's own new artifacts above work around each
one without touching those files, per #95's own guardrails.

### 1. `write-margin`/`access-time` testbenches: `klt pex` refuses up front

Each of these four testbenches `.include`s **two** files: its own
`./corner.inc` (PVT parameter/model selection, generated by
`sim/lib/run_corner_sweep.sh` before each run -- see `sim/README.md`) and
the DUT (`design/netlist/bitcell_6t.spice`). `klt pex` requires **exactly
one** `.include`/`.inc` line per testbench (a deliberate, documented
restriction -- see `docs/cli/pex.md` "Exactly one `.include`/`.inc` line is
required", the fix for klayout-tools#1030) and refuses when it sees two,
naming both lines:

```
$ klt pex layout/bitcell/sram_bitcell_6t.gds <write-margin-request>.json --deck gf180mcu
testbench netlist has 2 `.include`/`.inc` directives (line 30: `.include
'./corner.inc'`; line 55: `.include
'@@REPO_ROOT@@/design/netlist/bitcell_6t.spice'`) -- klt pex swaps exactly
one of them for the extracted netlist and cannot tell which one is the DUT
...
```

### 2. Even with exactly one `.include` line, the extracted-side leg fails in ngspice

Folding `corner.inc`'s contents inline (so exactly one `.include` line
remains, pointing at the DUT) clears check 1 -- but the extracted-side run
then fails inside `ngspice`, not at `klt pex`'s own validation. The reason
is a real structural mismatch between the two sides' DUT netlists:

- `design/netlist/bitcell_6t.spice` is netlisted **flat** -- its own
  `.subckt`/`.ends` wrapper is commented out by xschem's batch netlister
  (see `sim/README.md` "Why two of the testbenches don't `.include` the
  DUT"), so `.include`ing it exposes `Q`, `QB`, and every other internal
  node as an ordinary top-level net. Every testbench that reads/drives
  `Q`/`QB` directly (`tb_write_margin.spice`, both `tb_*_access_time.spice`)
  depends on exactly this.
- `klt extract`'s output is **always** `.SUBCKT <top> <pins> ... .ENDS`
  wrapped (see `layout/reports/extract-bitcell.json`'s underlying
  `.spice`). `klt pex`'s `.include` swap re-points the one `.include` line
  at this file but does not add a matching `X`-instantiation, so on the
  extracted side `Q`/`QB`/etc. are **not** top-level nodes at all.

The read-access-time testbench's `.ic v(Q)=0 v(QB)=...` card (needed to
avoid a cross-coupled pair's DC solve landing on the unstable metastable
point -- see that testbench's own header) then targets a node that does
not exist on the extracted side:

```
Warning : IC on non-existent node - q, ignored
Warning : IC on non-existent node - qb, ignored
Error on line 156 or its substitute:
  .ic v(Q)=0 v(QB)=    3.300000000000000e+00
 Error: .ic syntax error.
    Simulation interrupted due to error!
```

`klt pex`'s own `pin_count_mismatch` diagnostic does not fire here -- it
only compares pin counts when *both* sides declare a `.SUBCKT`; the
schematic side here never does. Filed as klayout-tools#1255 ("Gap 2"). #95's
`access-time/dut/bitcell_6t_subckt.spice` is the direct fix: a `.SUBCKT`
wrapper on the schematic side too, so both legs declare the same interface.

### 3. `read-snm`/`hold-snm` testbenches: silently accepted, vacuous result

These two testbenches don't `.include` the DUT at all -- they build a
device-level replica of one storage inverter instead, the documented
workaround for sweeping SNM on a bistable cell with no port to break its
feedback loop from outside (see `sim/README.md`). Their only `.include`
line is `./corner.inc`. `klt pex`'s "exactly one `.include`" check is
satisfied -- by the wrong file:

```
$ klt pex layout/bitcell/sram_bitcell_6t.gds <read-snm-request>.json --deck gf180mcu
{ "status": "pass", "reference_netlist": ".../sim/read-snm/testbench/corner.inc", "delta": [], ... }
```

`status: pass` with `delta: []` and `reference_netlist` naming a PVT
parameter file, not the DUT -- a silent, vacuous result, not an error.
Filed as klayout-tools#1255 ("Gap 1"). #95 confirmed (see "read-snm/hold-snm:
no PEX-compatible path" above) that this pair has no fix at all, DUT-swap
convention or otherwise -- the *tool*-side gap klayout-tools#1255 tracks
(a silent vacuous pass rather than a loud refusal) is still worth fixing
upstream, independent of this repo-side conclusion.

## Follow-up

- **klayout-tools#1255** -- the two structural `klt pex` gaps in
  "What was tried against the #24 testbenches themselves" above, filed
  during #23, still open.
- **klayout-tools#1263** -- the `.options rshunt` / floating `vsubs`
  substrate-coupling-node finding above, filed during #95.
- **klayout-tools#1376** -- `klt extract --pdk-root ...`'s JSON report
  carries a top-level `pdk.root` field that echoes the (necessarily
  absolute) `--pdk-root` argument verbatim, redundant with -- and leakier
  than -- the same report's own `provenance.pdk` block, which already
  carries the PDK's identity with no path. Filed during #109;
  `write-margin/dut/generate.sh` nulls the field itself before committing
  the report in the meantime (see that script's own comment).
- **klayout-tools#1378** -- two `klt pex` findings from #109: (1) a
  relative `--outdir` containing a `../` segment corrupts `klt pex`'s own
  internal intermediate-artifact path join and the run fails outright, so
  `access-time/generate.sh` keeps `--outdir` absolute as a workaround; (2)
  `reference_netlist`/`testbenches[].schematic_netlist` are always echoed
  absolute regardless of whether every other path argument was passed
  relative, so `access-time/generate.sh` rewrites that one known value back
  to its repo-relative equivalent after the fact (see that script's own
  comments for both).
- **gf180-sram#106** -- re-extract and re-run everything in this directory
  against the issue #103 bitcell revision. **Done** -- see "Freshness"
  above.
