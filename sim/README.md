# sim -- testbenches and PVT-corner evidence records

This directory holds the ngspice testbenches and simulation results for the
four measurements `spec/sram.md`'s Characterization section ratifies (read
SNM, hold SNM, write margin, read/write access time), plus the corner-sweep
runner and evidence-record convention that ties a testbench to a recorded
result. Per `CLAUDE.md`: "no claim without a testbench... `sim/` results are
append-only evidence."

## Testbench inventory

| Experiment dir | Testbench(es) | Measures | DUT access |
|---|---|---|---|
| `sim/read-snm/` | `testbench/tb_read_snm.spice` | Read SNM (butterfly-curve square side, cell held under a read access: BL precharged, WL asserted) | Device-level replica of one `bitcell_6t` half-cell (see "Why two of the testbenches don't `.include` the DUT" below) |
| `sim/hold-snm/` | `testbench/tb_hold_snm.spice` | Hold SNM (same fixture, WL deasserted -- standby/retention condition) | Device-level replica, as above |
| `sim/write-margin/` | `testbench/tb_write_margin.spice` | Write margin, as write trip voltage (WTV): the weakest "0" a write driver can present on the losing bit line and still flip the cell within a fixed pulse width. Margin = VDD − WTV. | `.include`s `design/netlist/bitcell_6t.spice` directly |
| `sim/access-time/` | `testbench/tb_read_access_time.spice` | Read access time: WL assertion to a defined bit-line sensing differential (3% of VDD) developing on the precharged-then-floated bit-line pair -- see "Read access time is a proxy metric" below | `.include`s `design/netlist/bitcell_6t.spice` directly |
| `sim/access-time/` | `testbench/tb_write_access_time.spice` | Write access time: WL assertion to the internal storage node `Q` crossing VDD/2 | `.include`s `design/netlist/bitcell_6t.spice` directly |

Each experiment directory follows the same layout (adapted from
[`2AMLogic/gf180-bandgap`](https://github.com/2AMLogic/gf180-bandgap)'s
`sim/README.md` evidence-record convention, cited per `CLAUDE.md`'s
instruction to use this org's other gf180mcu canary as a reference rather
than re-deriving one from scratch):

```
sim/
  <experiment-slug>/            # e.g. read-snm, write-margin
    testbench/                  # the fixed testbench source(s), reused
                                 # unmodified across every corner run
    netlist-snapshots/
      <record-id>.spice         # frozen copy of the testbench as actually
                                 # used for that record
    corners/
      <record-id>/
        <corner-id>.log         # raw ngspice output, one per PVT point
    records/
      <record-id>.md            # append-only summary record
```

- **`<record-id>`** = `<YYYYMMDD>-<HHMMSS>-<short-git-sha>`, minted fresh by
  `sim/lib/run_corner_sweep.sh` on every invocation. A re-run never edits an
  existing record; it mints a new one. Nothing under `corners/`,
  `netlist-snapshots/`, or `records/` is ever edited or deleted after being
  committed (see "Append-only rule" below).
- **`<corner-id>`** = `<process>_<temp>c_<supply>v`, e.g. `ff_-40c_2.97v`,
  `tt_25c_3.30v`, `ss_125c_3.63v` -- one per point in the ratified 9-corner
  matrix below.

## The ratified 9-corner PVT matrix

Per `spec/sram.md`'s "Characterization" -> "Corner set" (which this repo's
testbenches sweep exhaustively, not as a subset):

| Axis | Points |
|---|---|
| Process | `ff`, `tt`, `ss` |
| Temperature | `-40 C`, `25 C`, `125 C` |
| Supply | `2.97 V`, `3.30 V`, `3.63 V` (±10% of the 3.3V target) |

3 x 3 x 3 = 9 corners, every one of them run for every record -- a corner
that fails to converge or measure is recorded as an **open result** (see
each testbench's own comments and `sim/lib/run_corner_sweep.sh`'s record
generation), never silently dropped from the set, per `spec/sram.md`'s
Signoff definition.

`process` labels `ff`/`tt`/`ss` map onto the PDK model file's own `.LIB`
section names as `ff`->`ff`, `tt`->`typical`, `ss`->`ss` (gf180mcu's
`sm141064.ngspice` calls its nominal corner "typical", not "tt" --
`sim/lib/run_corner_sweep.sh` does this mapping so every record's
`<corner-id>` still reads `tt_...`, matching the ratified spec's own
vocabulary).

## Pinned PDK revision

`open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, same pin
already recorded in `spec/bitcell-decision.md` and `design/README.md`.
`sim/lib/pdk_env.sh` resolves the installed PDK (via `PDK_ROOT`+`PDK`,
`GF180_PDK_PATH`, or a standard install prefix -- same resolution order
`design/xschemrc` already established) and reports the resolved
`open_pdks` version at the top of every `run_corner_sweep.sh` invocation, so
a drifted install is visible rather than silent. Reuse this same pin for
consistency unless a documented reason requires bumping it.

## Cold-start invocation

Prerequisites: `ngspice` and `python3` on `PATH`; a gf180mcu PDK install
(volare-installed, or any location `sim/lib/pdk_env.sh` resolves -- see that
file's header for the exact resolution order).

```bash
# 1. Install/point at the pinned PDK revision, e.g. via volare:
#      volare enable --pdk gf180mcu c6d73a35f524070e85faff4a6a9eef49553ebc2b
export PDK_ROOT="$HOME/.volare"      # parent of gf180mcuC/ -- adjust to your install
export PDK=gf180mcuC

# 2. From a clean checkout, run any one testbench across the full 9-corner
#    matrix (each of the 5 testbenches below takes well under a minute; a
#    single-bitcell circuit has no reason to be slow):
./sim/lib/run_corner_sweep.sh sim/read-snm      sim/read-snm/testbench/tb_read_snm.spice           "snm:read_snm_sweep.txt:read_snm"   "spec/sram.md Characterization -- read SNM"
./sim/lib/run_corner_sweep.sh sim/hold-snm      sim/hold-snm/testbench/tb_hold_snm.spice           "snm:hold_snm_sweep.txt:hold_snm"   "spec/sram.md Characterization -- hold SNM"
./sim/lib/run_corner_sweep.sh sim/write-margin  sim/write-margin/testbench/tb_write_margin.spice   "direct"                            "spec/sram.md Characterization -- write margin (write trip voltage)"
./sim/lib/run_corner_sweep.sh sim/access-time   sim/access-time/testbench/tb_read_access_time.spice  "direct"                          "spec/sram.md Characterization -- read access time (bit-line differential proxy)"
./sim/lib/run_corner_sweep.sh sim/access-time   sim/access-time/testbench/tb_write_access_time.spice "direct"                          "spec/sram.md Characterization -- write access time"

# 3. Inspect a corner's raw log or the generated record:
cat sim/read-snm/corners/<record-id>/tt_25c_3.30v.log
cat sim/read-snm/records/<record-id>.md
```

Expected output: each run prints one line per corner
(`  tt_25c_3.30v: RESULT: read_snm_v = 0.381267;`, etc.), then reports the
paths it wrote. Every `RESULT: <key>_v = <value>` line is in volts; every
`RESULT: <key>_s = <value>` line (access time) is in seconds. A corner that
instead prints `RESULT-ERROR: ...` did not produce a valid measurement --
that is reported in the generated record as an explicit **open result**, not
papered over.

To run a single testbench/corner by hand (e.g. while iterating on the
testbench itself), see "ngspice control-language notes" below for the two
substitutions (`corner.inc`, `@@REPO_ROOT@@`) `run_corner_sweep.sh` performs
that a bare `ngspice -b tb_*.spice` invocation needs done manually first.

## Why two of the testbenches don't `.include` the DUT

`sim/write-margin/` and `sim/access-time/` `.include` `design/netlist/bitcell_6t.spice`
directly -- and it works as a *flat* include, not a subcircuit call, because
xschem's batch netlister comments out that file's `.subckt`/`.ends` wrapper
(it was netlisted as a standalone top-level schematic, not as a child of
another one -- see `design/README.md` "Regenerating the netlists"). That
means `.include`ing it exposes its internal storage nodes `Q` and `QB` as
ordinary top-level nets alongside its `BL`/`BLB`/`WL`/`VDD`/`VSS` ports,
which is exactly what write-margin and access-time need (driving/reading
the bit lines and wordline, then reading `Q` directly).

`sim/read-snm/` and `sim/hold-snm/`, by contrast, do **not** `.include` that
file. The classical butterfly-curve SNM extraction (Seevinck et al.,
"Static-Noise Margin Analysis of MOS SRAM Cells," IEEE JSSC 1987) needs to
sweep one storage inverter's input independently of the other's output --
i.e. it needs to *break* the cross-coupled feedback loop, not just read both
sides of it. That is not possible working only with `bitcell_6t`'s exposed
nodes (`Q`/`QB` are wired directly to each other's gates by the netlist;
there is no port to inject a decoupling source through without editing the
DUT itself, which is out of this issue's scope -- `design/` is a read-only
dependency here). Both SNM testbenches instead build one storage inverter +
its access transistor at the device level, using the exact same models,
`W`/`L`, and parasitic-area formulas as `design/netlist/bitcell_6t.spice`
(cited verbatim in each testbench's header) -- this is the standard,
documented workaround for characterizing a black-box bistable cell's
noise margin, not a shortcut around the real DUT. Because `bitcell_6t`'s two
half-cells are identical devices, one inverter's Vout-vs-Vin sweep *is* the
other inverter's transfer function too (the second butterfly branch is the
same curve reflected about the `Vout=Vin` diagonal), so a single DC sweep
per corner is sufficient -- see `sim/lib/snm_extract.py`'s module docstring
for the full derivation and, importantly, for why that script composes the
sweep with itself (`f(f(x))`) rather than building an explicit
sorted-and-swapped inverse table, which turned out to be numerically
fragile near a saturated VTC rail during this issue's own validation.

## Read access time is a proxy metric

`design/sram_256x32_array.sch`'s array core (per `design/README.md`) is
storage cells only -- address decode, column mux, sense amp, and write
driver are out of scope for the design issue that produced it (#21) and have
not been drawn. `spec/sram.md`'s "valid Q output" therefore has no sense-amp
output to measure yet. `tb_read_access_time.spice` instead measures exactly
the primitive spec/sram.md itself allows for when full-array/full-macro
simulation isn't available ("a representative column/bitcell testbench"):
the delay from wordline assertion to the precharged, then floated, bit-line
pair developing a 3%-of-VDD sensing differential -- a conservative,
commonly-cited minimum offset a real sense amp would need. Once a sense amp
is designed (a downstream issue), replace this proxy with a true
clock-to-`Q` measurement through that circuit; this testbench's structure
(corner sweep, record format) does not need to change to accommodate that,
only its `.meas` target.

## ngspice control-language notes

Two mechanisms recur across these testbenches and are non-obvious enough to
call out explicitly (both were wrong on the first attempt during this
issue's implementation, and the failure mode in each case is silent/wrong
rather than a clear error):

- **`.param` values are not directly readable from a `.control` block.**
  `let x = VDDC` (where `VDDC` is a `.param`) fails with "no such device or
  model name". The documented workaround: read the value off a device that
  was itself set from that parameter, via `@<device>[<attr>]`, e.g.
  `let vddc_ctl = @vvdd[dc]` after `VVDD VDD 0 DC VDDC`. Every testbench
  here names its supply source `VVDD` for exactly this reason. Compute any
  needed derived value (half, a percentage, ...) as its own `let` first,
  then substitute it into a `meas`/`alterparam` command with `$&name` --
  `meas tran ... val=$&vddc_half rise=1` works; `val={VDDC/2}` and
  `val='VDDC/2'` do not inside a `.control` block (both parse fine in
  ordinary netlist-level lines, e.g. `.dc VIN 0 {VDDC} ...`, which is why
  the two forms look interchangeable until they aren't).
- **A parameter sweep loop is `alterparam <name> = $&<vector>` followed by
  `reset`, inside a `dowhile`/`foreach`** -- `alter <name> = ...` (no
  `param`) targets a device instance, not a `.param`, and silently fails to
  change anything for a parameter substituted into a source's waveform.
  `sim/write-margin/testbench/tb_write_margin.spice`'s bisection-style
  search over the write-trip voltage is the worked example.

## Netlist provenance and the `@@REPO_ROOT@@` substitution

`sim/write-margin/testbench/tb_write_margin.spice` and both
`sim/access-time/testbench/*.spice` files `.include` the DUT via a
`@@REPO_ROOT@@/design/netlist/bitcell_6t.spice` placeholder, not a
repo-relative path. `sim/lib/run_corner_sweep.sh` substitutes
`@@REPO_ROOT@@` with this checkout's absolute path before copying the
testbench into each corner's scratch working directory (a `mktemp -d`
outside the repo tree, so a repo-relative `.include` would not resolve
there). Running one of these three files directly with a bare
`ngspice -b tb_*.spice` (bypassing the runner) requires substituting that
token yourself first, e.g.
`sed "s|@@REPO_ROOT@@|$(pwd)|g" tb_write_margin.spice > /tmp/tb.spice`.

## Summary record format

Each `records/<record-id>.md` (auto-generated by `run_corner_sweep.sh`)
carries:

- **Record ID** -- matches the filename and the corresponding
  `netlist-snapshots/`/`corners/` subdirectory.
- **Claim** -- the `spec/sram.md` row this record substantiates (passed as
  this script's 4th argument).
- **Netlist provenance** -- `schematic` (this repo has not yet reached
  layout/extraction; a post-layout re-run, once `layout/` produces an
  extracted netlist, would record `extracted` here instead and reference
  this record via **Supersedes**).
- **Corner matrix run** -- always the full 9-point matrix (see above); a
  record that ever runs a subset must say why, per this convention.
- **Statistical convention** -- `N/A` for every testbench here (a
  corner-matrix claim, not a Monte Carlo/mismatch distribution claim; no
  such claim exists yet in this repo).
- **Result** -- every corner's `RESULT:` line(s) verbatim, plus an overall
  `recorded`/`OPEN` rollup (`OPEN` for any corner that produced no valid
  `RESULT:` line -- see "Append-only rule" below for what happens to that
  record).
- **Links** -- the testbench, netlist snapshot, and raw per-corner log
  directory, all repo-relative.
- **Timestamp / author**.
- **Supersedes** -- `(none)` for every record here (all first records for
  their claim); a later corrected or post-layout re-run of the same claim
  would reference the record it supersedes.

## Append-only rule

Nothing under `corners/`, `netlist-snapshots/`, or `records/` is edited or
deleted once committed -- including a record whose Result rolls up to
**OPEN**. A corner that fails to converge or measure is not a reason to
delete or rerun-and-overwrite that record; it is the recorded evidence that
the corner was attempted and did not close, per `spec/sram.md`'s Signoff
definition ("Any corner that cannot be closed is recorded as an open result
in `sim/`, not silently dropped from the corner set"). A fix (to the
testbench, the bitcell sizing, or the corner itself) gets verified by a
**new** record, referencing the one it supersedes.

## Interpreting these results against sign-off

`spec/sram.md`'s Signoff definition requires read SNM, hold SNM, and write
margin to be **strictly positive** at every one of the 9 corners, plus a
recorded access time, before this macro is "functional across PVT." The
records generated during this issue's own implementation (see
`sim/*/records/*.md`) show exactly that -- all 9 corners, all four
measurements, strictly positive margins and recorded access times -- for
the current `bitcell_6t` sizing. That is a real, if narrow, first data
point: it is evidence this sizing has *some* margin at every ratified
corner, not a full characterization (no Monte Carlo/mismatch analysis
exists yet -- spec/sram.md's Signoff definition does not require one, and
none is claimed here) and not yet informed by any deliberate SNM/write-margin
optimization (`design/README.md` already flags the current sizing as "a
first cut, not yet SNM/write-margin optimized").

### Explicit per-corner pass/fail rollup

The paragraph above summarizes the aggregate outcome; `sim/signoff-summary.md`
is the **explicit per-corner, per-metric PASS/FAIL** table `spec/sram.md`'s
Signoff definition calls for -- one row per corner point, with a verdict
column for read SNM, hold SNM, write margin (PASS/FAIL against the `> 0`
threshold), and read/write access time (RECORDED, since the spec only
requires these be recorded, not compared against a numeric threshold). It is
generated by `sim/lib/render_signoff_table.py` directly from the five
records above -- a read-only derivation, not a new record, so it does not
touch the append-only convention above -- and should be regenerated whenever
one of those five records is superseded by a fresh sweep:

```bash
python3 sim/lib/render_signoff_table.py > sim/signoff-summary.md
```

`sim/signoff-summary.md` also notes a corner-count discrepancy worth
flagging here: it reports 27 corner points per record (`process x
temperature x voltage`, `3 x 3 x 3`), matching what every one of the five
records above actually contains, while `spec/sram.md`'s "Corner set"
section computes that same product as "9 corners" -- see #53 for the
tracked spec-text correction (unaffected pass/fail outcome; not fixed here
since `spec/sram.md` edits are out of scope for the issue that added this
rollup).
