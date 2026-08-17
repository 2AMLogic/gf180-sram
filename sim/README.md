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
| `sim/write-margin/` | `testbench/tb_write_margin.spice` | Write margin, as write trip voltage (WTV): the weakest "0" a write driver can present on the losing bit line and still flip the cell within a fixed pulse width. WTV **is** the recorded margin — a real write driver presents 0 V, so WTV is exactly its head-room before the write stops working, and `spec/sram.md`'s "positive margin at every corner" applies to it verbatim. (`sim/signoff-summary.md` currently derives it the other way round, as `VDD - WTV`; both are positive at every corner so no verdict differs, but the definition still needs settling once — tracked as #59.) | `.include`s `design/netlist/bitcell_6t.spice` directly |
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
- **Statistical convention** -- `N/A` for every record under `corners/` (a
  corner-matrix claim, not a Monte Carlo/mismatch distribution claim). The
  Monte Carlo/mismatch claims live in their own record tree under
  `sim/<experiment>/mc/` and carry their own convention field -- see
  "Monte Carlo / yield evidence records" below.
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

## Monte Carlo / yield evidence records

The corner records above answer "does this sizing have margin at every
ratified PVT point?" They cannot answer "does it have margin on a part that
actually came out of a fab?", because a corner matrix moves every device
together and real silicon does not: the two halves of a 6T cell draw
*independent* threshold and current-factor offsets, and inter-inverter
mismatch is the dominant real failure mode for both SNM and write margin.
That is a statistical claim, and per klayout-tools'
`docs/design-evidence-tiers.md` item 6 a statistical claim needs Monte Carlo
evidence with a recorded seed, a sample count, a deterministic negative
control, and results **combined with — not instead of —** process corners,
published as a `klt yield` JSON report.

Those records live in a parallel tree beside the corner records, never
replacing them:

```
sim/
  <experiment-slug>/
    corners/ records/ ...        # the deterministic 9-corner evidence above
    mc/
      samples/
        <record-id>.json         # the klt yield sample-set document: every
                                 #   individual draw, per corner, plus the
                                 #   negative control's own draws
      yield-reports/
        <record-id>.json         # `klt yield --format json` -- the machine-
                                 #   checkable artifact item 6 asks for
        <record-id>.txt          # the same report, `--format text`
      raw-logs/
        <record-id>/
          <corner-id>.log        # one line per draw: sample index, the seed
                                 #   that produced it, and its value (or the
                                 #   reason it produced none)
          summary.json           # per-corner rollup + full campaign metadata
      records/
        <record-id>.md           # append-only summary record, same field set
                                 #   as the corner records plus the MC rows
```

`<record-id>` and the append-only rule are exactly as above: a re-run mints a
new id and never edits an existing record.

### Running a campaign

`sim/lib/run_mc_campaign.py` drives it (`--help` documents every flag). The
three campaigns whose records are committed here were produced by:

```bash
C9="--corner ff:-40:2.97 --corner ff:25:3.30 --corner ff:125:2.97 \
    --corner tt:-40:3.63 --corner tt:25:3.30 --corner tt:125:2.97 \
    --corner ss:-40:3.63 --corner ss:25:2.97 --corner ss:125:3.63"

./sim/lib/run_mc_campaign.py --experiment read-snm \
  --testbench sim/read-snm/testbench/tb_read_snm.spice \
  --mode snm-pair:read_snm_sweep.txt:read_snm --key read_snm_v \
  $C9 --n 200 --n-control 4 --n-nc 100 --nc-mismatch-scale 20 \
  --seed 20260817 --claim "spec/sram.md Characterization -- read SNM (Monte Carlo ...)"
```

(the hold-SNM and write-margin invocations differ only in testbench, mode,
key, and negative-control defect — each committed record's own "Reproduce"
section carries its exact command line).

### Which corners, and why not all of them

`spec/sram.md`'s corner set is process × temperature × voltage, "all
combinations". The MC campaigns run a **9-point subset** of it, chosen to
cover every one of the nine process × temperature cells and all three supply
levels, and to include the corner the deterministic records already identify
as worst for read SNM (`ff_125c_2.97v`) and the one they identify as best
(`ss_-40c_3.63v`), so the campaign brackets the observed range rather than
sampling the middle of it. Each committed record names its own corner list.

This is a subset because MC multiplies the corner count by the sample count,
not because the remaining points are uninteresting — the deterministic
records still cover the matrix exhaustively, and the MC records say so in
their "Corner matrix run" field. **No estimate is pooled across corners**:
each corner is its own measurement with its own limits, its own confidence
interval, and its own negative control, because each corner is a different
population.

### What is randomized

Per-instance device mismatch only — gf180mcu's `sm141064.ngspice` gates
threshold-voltage and current-factor jitter (`delvto='mis_vth*sw_stat_mismatch'`,
`mulu0='1-mis_k*sw_stat_mismatch'`) behind the single `.param
sw_stat_mismatch` switch, and the campaign sets it per batch. Global process
variation is *not* resampled: it is carried by the corner axis, which is what
"combined with, not instead of, process corners" means here concretely.

Seeding is reproducible end to end. The campaign takes one base `--seed`, and
each individual draw's ngspice `.options seed=` value is
`sha256(base_seed:corner_id:batch_kind:sample_index)` truncated to a positive
31-bit integer — never Python's salted built-in `hash()`. Every seed is
written into `raw-logs/<record-id>/<corner-id>.log` next to the value it
produced, so any single draw can be re-run in isolation.

### Two controls, doing different jobs

| Batch | `sw_stat_mismatch` | Question it answers |
|---|---|---|
| mismatch | `1` | The measurement. What does the margin distribution look like? |
| determinism control | `0` | Is this harness even driving the same fixture the corner records came from? Every draw must collapse onto **one** value, and that value must equal the corner record's own number for that corner. |
| negative control | a deliberate defect | Can these statistics detect a bad design at all, or are they only ever confirming a good one? |

The determinism control is what anchors the MC evidence to the ratified
corner evidence. The negative control is `docs/cli/yield.md`'s requirement:
"a yield statistic that has never been shown to detect a bad design is not
evidence, it is an assumption." `klt yield` analyses the control's own draws
against the *same* spec limits and returns `detected` only when the control's
yield is lower **and** its exact confidence interval does not overlap the
nominal draw's — a point estimate that merely looks worse is not enough.

The defect differs per measurement because the physical failure mechanisms
differ, and each record states its own:

- **read SNM** — mismatch drawn at 20× the PDK's own sigma (`docs/cli/yield.md`'s
  "a mismatch seed pushed past spec"). Read stability is mismatch-limited, so
  inflating mismatch alone breaks it.
- **hold SNM** — supply collapsed to 0.50 V, far below the ratified 2.97 V
  minimum and below this cell's data-retention voltage, with 12× mismatch.
  Hold stability is *not* mismatch-limited at 3.3 V (20× mismatch does not
  produce a single failing draw); its real failure mechanism is retention
  voltage, so that is what the control attacks.
- **write margin** — supply collapsed to 0.60 V with 6× mismatch: a write
  that no longer completes inside the fixed 1.8 ns pulse.

### A failing draw must be a number, not an error

This is the subtlety that decides whether a yield campaign means anything.
`klt yield` excludes a null/errored sample from every statistic (correctly —
an errored sample is a *measurement* failure, not a *design* failure). So if
the harness reports a design failure as an error, the exact draws the
campaign exists to count disappear from the yield, and the estimate silently
becomes "the yield among the parts that worked well enough to measure."

That is not hypothetical: the first version of this campaign did exactly
that, and its deliberately-degraded negative control came back
`not_detected` — every failing draw had been filed as an error. Both
extraction paths were changed so a failure is a value:

- `sim/lib/snm_extract.py` reports a **signed** SNM. Positive values are the
  classical Seevinck butterfly square; a draw whose two mismatched half-cells
  no longer latch reports `-d`, the *bistability deficit* — how far the
  composed loop map misses re-crossing the diagonal. `d → 0` at the
  bifurcation, so the quantity is continuous through zero rather than a
  sentinel bolted onto the failing side; `sim/lib/test_snm_extract.py` pins
  that continuity down against analytic VTCs.
- `sim/write-margin/testbench/tb_write_margin.spice` reports a **negative**
  WTV (one search resolution below zero) for a cell that does not flip even
  with the bit line pulled to ground. Previously that case was
  indistinguishable from a genuine WTV of exactly 0.

Only a draw with no measurable structure at all is still an open result, and
the campaign counts those separately (`errored` in the report, `n_errored` in
`summary.json`). **A record with a non-zero errored count states a yield
conditioned on a measurable draw** — read the two numbers together.

The same episode is why `tb_write_margin.spice` now bisects instead of
scanning 41 points: at VDD/40 resolution the trip point quantized onto one
grid value for every draw at a corner, giving a sample standard deviation of
5e-16 V and a Cpk of 1.3e15. A measurement whose resolution swamps the effect
under study cannot substantiate a statistical claim. Because that changed the
testbench, the deterministic write-margin corner record was re-run against it
and the new record's **Supersedes** field names the one it replaces — the
older record stays committed, as the append-only rule requires, but stops
being the current answer. Every one of the 27 determinism-control draws
across the three campaigns reproduces its corner record's value exactly.

### Limits, and the one number this repo does not invent

Each measurement is analysed against `min = 0` — `spec/sram.md`'s own
requirement that read SNM, hold SNM, and write margin be strictly positive at
every corner. Note that `klt yield`'s `min` is **inclusive**, so a draw of
exactly `0.0` would count as passing; both extraction paths above therefore
report a failing draw as strictly negative, never as zero.

No `target_yield` is declared, and that is deliberate. `spec/sram.md`
ratifies no yield target for these rows — whether they are statistical rows
at all, and what they would have to hit, is the open operator decision
tracked as issue #20 — and agents do not extend the ratified spec to make a
result pass or fail. So `klt yield` reports these measurements rather than
grading them, and emits a run-level warning saying so. That warning is
accurate and is left in the committed reports on purpose: it is the machine-
readable form of a real, open spec gap, not noise to be silenced. The
quantitative margin statement in the meantime is **Cpk / sigma-to-spec** —
the fitted distance from the mean to the spec limit, in sample standard
deviations, with its own confidence interval.

Read the two yield estimates the report prints side by side, as
`docs/cli/yield.md` describes: the empirical (Clopper-Pearson) estimate
cannot see past the samples it has, so with zero observed failures it can
only bound from below ("at least 98.17% at 95% confidence, N = 200" — never
"100% yield"); the parametric estimate extrapolates into a tail nothing was
sampled from, and is only as good as the Anderson-Darling normality verdict
printed beside it.

## Interpreting these results against sign-off

`spec/sram.md`'s Signoff definition requires read SNM, hold SNM, and write
margin to be **strictly positive** at every one of the 9 corners, plus a
recorded access time, before this macro is "functional across PVT." The
records generated during this issue's own implementation (see
`sim/*/records/*.md`) show exactly that -- all 9 corners, all four
measurements, strictly positive margins and recorded access times -- for
the current `bitcell_6t` sizing. That is a real, if narrow, first data
point: it is evidence this sizing has *some* margin at every ratified
corner, and it is not yet informed by any deliberate SNM/write-margin
optimization (`design/README.md` already flags the current sizing as "a
first cut, not yet SNM/write-margin optimized").

The Monte Carlo records under `sim/*/mc/` extend that, but do not turn it
into a sign-off claim either. `spec/sram.md`'s Signoff definition asks for a
strictly-positive recorded margin per corner, which the corner records
supply; the MC records add what a corner matrix structurally cannot -- a
mismatch-driven distribution behind each of those numbers, with a confidence
interval and a sigma-to-spec figure. What they still do not supply is a
*yield claim*, because the spec states no yield target to claim against
(issue #20), and because a plain-random campaign at N = 200 per corner
bounds the empirical per-cell yield only to roughly 98% at 95% confidence --
whereas an 8192-bit array needs per-cell yield far beyond what a few hundred
samples can resolve. Closing that gap needs a ratified target and a
variance-reduced (importance-sampled) campaign, not more of the same draws.
Both records are schematic-level; a post-layout re-run against an extracted
netlist would supersede them.

### Explicit per-corner pass/fail rollup

The paragraph above summarizes the aggregate outcome; `sim/signoff-summary.md`
is the **explicit per-corner, per-metric PASS/FAIL** table `spec/sram.md`'s
Signoff definition calls for -- one row per corner point, with a verdict
column for read SNM, hold SNM, write margin (PASS/FAIL against the `> 0`
threshold), and read/write access time (RECORDED, since the spec only
requires these be recorded, not compared against a numeric threshold). It is
generated by `sim/lib/render_signoff_table.py` directly from the five
records above -- a read-only derivation, not a new record, so it does not
touch the append-only convention above -- and must be regenerated whenever
one of those five records is superseded by a fresh sweep:

```bash
python3 sim/lib/render_signoff_table.py > sim/signoff-summary.md
```

That regeneration is **enforced, not remembered**: `scripts/ci/check_evidence_format.py`
(the `evidence-record format` CI job, and `npm run lint` locally) re-renders
the table from whatever records are committed and fails if
`sim/signoff-summary.md` does not match byte-for-byte, printing the command
above. The check is pure Python over the committed records -- it does not
run ngspice and needs no PDK -- so landing a superseding record without
refreshing the rollup is a red CI status rather than a silently stale
signoff table. The renderer always reads the *latest* record per claim (by
`<record-id>`, which sorts chronologically), so superseding a record is the
only action needed on the evidence side.

`sim/signoff-summary.md` also notes a corner-count discrepancy worth
flagging here: it reports 27 corner points per record (`process x
temperature x voltage`, `3 x 3 x 3`), matching what every one of the five
records above actually contains, while `spec/sram.md`'s "Corner set"
section computes that same product as "9 corners" -- see #53 for the
tracked spec-text correction (unaffected pass/fail outcome; not fixed here
since `spec/sram.md` edits are out of scope for the issue that added this
rollup).
