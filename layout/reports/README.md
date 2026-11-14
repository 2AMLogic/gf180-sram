# layout/reports -- DRC, LVS, and ERC supply signoff evidence (issues #23, #124)

Machine-readable `klt drc`/`klt lvs`/`klt extract` reports for the layout
committed in `layout/` (issue #22), checked against the schematic sources
committed in `design/` (issue #21), plus the `klt erc` supply read that
klayout-tools' T1 item 11 grades (issue #124). `layout/README.md` already
quoted these numbers in prose; this directory is the committed,
provenance-carrying artifact those numbers cite, per issue #23's
acceptance criteria ("All three reports committed under `layout/` ... each
carrying provenance (klt version, deck/PDK content hash, design revision)
sufficient to detect staleness").

Regenerate everything here with `./layout/reports/generate.sh` (from the
repo root). It re-runs `klt drc`/`klt extract`/`klt lvs`/`klt erc` against
whatever `layout/*.gds` and `design/netlist/*.spice` are currently checked
out and overwrites the files below in place. `./layout/reports/generate.sh
--column-path` regenerates only the column-path reports (~2 min), and adding
`--native` also runs them against the PDK's native DRC deck (~3 min more);
`./layout/reports/generate.sh --macro` regenerates only
[`drc-macro.json`](drc-macro.json) (~1 min); the full run's `klt erc` step alone
is ~26 min. Every report it writes goes through one scrub-and-lint path --
see "Provenance hygiene: one scrub path" below -- and that path refuses to
write a report carrying a host-absolute path, so a run that would leak one
fails rather than committing it.

## Results (DRC/LVS/extract rows as of `db3fa5c`, 2026-08-21; `erc-array-supply.json` added 2026-09-21, issue #124; column-path rows added 2026-10-18, issue #205; `drc-macro.json` added 2026-11-14, issue #326)

| Report | Command | Result |
|---|---|---|
| `drc-bitcell.json` | `klt drc --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds` | `status: clean`, 0 violations |
| `drc-array.json` | `klt drc --deck gf180mcu layout/sram_256x32/sram_256x32_array.gds` | `status: clean`, 0 violations |
| `extract-bitcell.json` | `klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds` | 6 devices (4 nfet + 2 pfet), 7 nets |
| `lvs-bitcell.json` | `klt lvs` vs. `design/netlist/bitcell_6t.spice` | `status: match`, 0 mismatches, 6/6 devices, 7/7 nets |
| `extract-array.json` | `klt extract --deck gf180mcu layout/sram_256x32/sram_256x32_array.gds` | 49,152 devices (32,768 nfet + 16,384 pfet), 16,706 nets, 322 pins -- `devices[]`/`nets[]` omitted from the committed file (~18 MB unabridged; every other field, including counts and provenance, is kept in full) |
| `lvs-array.json` | `klt lvs` vs. `design/netlist/sram_256x32_array.spice` (`options.flatten_reference: true`, see below) | `status: match`, 49,152/49,152 devices, 16,706/16,706 nets, 322/322 pins matched -- the sole `mismatches[]` entry is a `severity: warning` `topology.flattened` disclosure, not a defect (see "Known gap: array-level LVS" below) |
| `drc-foundry-bitcell.json` | `klt drc --deck gf180mcu` vs. the foundry's own `gf180mcu_fd_ip_sram__sram64x8m8wm1.gds` | `status: violations`, 2010 violations, all `comp.enclosing.contact.1` -- **expected**, see `sram-rule-survey.md` (issue #8) |
| `erc-array-supply.json` | `klt erc layout/sram_256x32/sram_256x32_array.gds layout/sram_256x32/erc-supply-spec.json --format json` | `erc_finding_count: 0` -- declared supplies VDD/VSS each resolve to exactly one electrical island and both declared ties (`nwell_tie`, `substrate_tie`) are checked, none skipped; `status: not_checked` is the antenna half's rollup, not the supply verdict (see "Item 11" below) |
| `drc-column-precharge-slice.json`, `drc-column-io-slice.json`, `drc-column-band.json` | `klt drc --deck gf180mcu` on `layout/periphery/column/{precharge_slice,io_slice,column_band}.gds` (issue #205) | `status: clean`, 0 violations each |
| `drc-column-abut.json` | `klt drc --deck gf180mcu` on the scratch composite `periphery/column/generate.py --abut` builds: the committed 64 x 128 array with `io_band` below and `precharge_band` above (the composite is not committed; `file` says so) | `status: clean`, 0 violations -- the bit-line seam and the first/last slice against the array's edges |
| `drc-native-column-precharge-slice.json`, `drc-native-column-io-slice.json`, `drc-native-column-abut.json` | `klt drc --engine klayout` with the PDK's native deck (`generate.sh --column-path --native`) | `status: clean`, 0 violations, `coverage_assertion` 640 expected = 640 observed rule categories |
| `drc-row-path.json`, `extract-row-path.json`, `lvs-row-path.json` | `klt drc --deck gf180mcu`, `klt extract`, and `klt lvs` (inline extraction, `options.flatten_reference: true`) on `layout/periphery/row/row_path.gds` vs. `design/netlist/row_path.spice` (issue #204; `generate.sh --row-path`) | DRC `status: clean`, 0 violations; 528 devices (264 nfet + 264 pfet), 279 nets, 79 pins; LVS `status: match`, 528/528 devices, 279/279 nets, 79/79 pins, `mismatches[]` only the `topology.flattened` disclosure and the "no bjt" note. Strip only -- no physical-fit, parasitic or wordline-RC claim; PDK-native deck not run (not installed on the generating host) |
| `drc-sram-ctrl.json`, `extract-sram-ctrl.json`, `lvs-sram-ctrl.json`, `drc-col-decode.json`, `extract-col-decode.json`, `lvs-col-decode.json` | `klt drc --deck gf180mcu`, `klt extract`, and `klt lvs` (inline extraction, `options.flatten_reference: true`) on `layout/periphery/control/{sram_ctrl,col_decode}.gds` vs. `design/netlist/{sram_ctrl,col_decode}.spice` (issue #246; `generate.sh --control`) | DRC `status: clean`, 0 violations on both; `sram_ctrl` 356 devices, 171 nets, 35 pins and `col_decode` 40 devices, 27 nets, 15 pins, each LVS `status: match` with everything matched and `mismatches[]` only the `topology.flattened` disclosure and the "no bjt" note. Block level only -- no timing, delay-calibration, parasitic or physical-fit claim; PDK-native deck not run |
| [`drc-macro.json`](drc-macro.json) | `klt drc --deck gf180mcu --format json layout/macro/sram_256x32.gds` on the assembled macro, hierarchical top cell `sram_256x32` (issue #326; `generate.sh --macro`) | `status: clean`, 0 violations -- 51 rules checked, 63 inapplicable, 97 unmodeled, 11 layers. **No macro LVS or extract counterpart exists** (see "Known gap: macro-level LVS" below): macro-level DRC and the pin check are the only macro verdicts in this repo. First report here minted under the pinned released `klayout-tools==0.8.0` with `klayout==0.30.12`, so it carries `schema_version: 3` and an object-valued `file` where the older rows carry `schema_version: 1`/`2` and a string |
| `extract-column-precharge-slice.json`, `extract-column-io-slice.json` | `klt extract --deck gf180mcu` on the slices | 12 devices (pfet), 14 nets, 14 pins; 99 devices (50 nfet + 49 pfet), 59 nets, 26 pins |
| `lvs-column-precharge-slice.json`, `lvs-column-io-slice.json` | `klt lvs` (inline `layout.file` + `deck`, `options.flatten_reference: true`) vs. `design/netlist/{precharge,io}_slice.spice` | `status: match`; 12/12 and 99/99 devices, 14/14 and 59/59 nets, 14/14 and 26/26 pins. `mismatches[]` holds only `severity: warning` entries: the `topology.flattened` disclosure and "device class absent on both sides" notes -- no `net.supply_fragmented` |

`drc-foundry-bitcell.json` is generated and maintained separately from the
reports above -- it checks the *foundry's* macro, not this repo's own
layout, so it is not part of `generate.sh`'s regeneration loop (nothing in
`design/`/`layout/` changing would ever change it). See
[`sram-rule-survey.md`](sram-rule-survey.md) (issue #8) for the full survey
of gf180mcu's `SramCore` (108/5) marker-scoped rule allowances this result
is evidence for, and the separate native-engine (`klt drc --engine klayout`)
investigation.

Every report's own `provenance` block records `klt_version`, the deck's
`content_hash`, and (for DRC/extract) the input GDS's `content_hash` --
together with this table's git revision, that is what "fresh" means for
these reports: re-run `generate.sh` at a later commit and diff the
`content_hash`/`netlist_sha256` fields against the committed ones to detect
staleness, exactly as `sim/README.md`'s corner records use `netlist_sha256`
for the same purpose.

## Item 3 (DRC clean): what this does and does not cover

`klt drc --deck gf180mcu` is `klt`'s own curated Region-primitive deck (the
`--engine curated` default) -- **not** a PDK-native KLayout `.lydrc`/`.drc`
deck. `klt drc --engine klayout` (the PDK-native engine, issue #565 upstream)
remains unavailable in the environment this issue ran in: there is no
standalone `klayout` binary on `PATH`, and `--pdk gf180mcuD` resolves no
native deck script for this PDK variant without an explicit `--deck-file`
(same command layout/README.md flagged before this issue; still true today,
verified by re-running it here). Issue #23's own acceptance criterion for
item 3 asks specifically for the `klt drc --deck gf180mcu` report, which is
what these files are -- but a caller reading "DRC clean" here should read it
as "clean against `klt`'s curated deck," not "signed off against the
foundry's own DRC-DSL rule deck." `drc-bitcell.json`'s and
`drc-array.json`'s own `coverage.rules_skipped`/`deck_scope` fields enumerate
exactly which rule families the curated deck does not model (implant
spacing, density, antenna, latch-up, the DRM's `SramCore`-marker rules --
see `layout/README.md` "What this does and does not prove" for the same
list in prose).

## Item 4 (LVS clean): bitcell only, by design

`lvs-bitcell.json` is a full, clean LVS: 6/6 devices, 7/7 nets, 0
mismatches, directly against the schematic-derived reference netlist, with no
rewrite of the reference (see `layout/README.md` "Known tool gaps" #1 for
the bulk-net history).

## Item 11 (power delivery, structural): the array supply read

`erc-array-supply.json` is the machine-readable artifact klayout-tools'
T1 item 11 ("Power delivery (structural)", added 2026-09-17,
klayout-tools#2025) grades for this block: a `klt erc` supply-spec run
against the full array GDS, produced by `generate.sh` step 5 from the
committed spec `layout/sram_256x32/erc-supply-spec.json` (whose inline
`_comment` block justifies every stackup entry, via layer, label layer, and
deliberate omission from three verified sources: the block's own GDS, the
PDK's own `gf180mcu.lyp` at the pinned open_pdks revision, and klt's
curated gf180mcu deck layer table).

This block is ratified `analog` (`spec/block-kind-decision.md`), so item
11's *Analog* column applies: the `klt erc` supply evidence, plus item 4's
own LVS report having actually carried the supply nets in its compare.
Both halves are committed here:

- the ERC report itself: `erc_finding_count: 0` -- zero
  `erc.unconnected_net` and zero `erc.supply_short` name VDD or VSS,
  which is exactly "each declared supply resolves to one electrical
  island" (the rule fires on **zero** matches, and on **more than one**, a
  split rail -- so zero findings is a positive one-island verdict, not an
  absence; the two `Metal3` straps are the array feature that makes each
  supply one island, and a run without them would show 32 per-column
  islands).
- `lvs-array.json`: `net_correspondence` pairs layout `VDD` -> reference
  `VDD` and layout `VSS` -> reference `VSS`, both `pin: true` -- a SPICE
  reference carries the supplies by construction, which is item 11's own
  stated satisfaction for the analog column.

What the other report fields do and do not mean:

- `status: "not_checked"` is **not** a supply verdict and **not** a fail:
  klt's status rollup (#2109/#2115) reports the antenna half, and klt has
  no transcribed gf180mcu antenna-limit table, so every antenna level
  reads `unchecked` and the rollup refuses to read `clean`. Item 11's pass
  conditions are the ERC finding rules, not the overall status -- and an
  antenna or floating-gate finding, were one to appear, is a real defect
  that does not block item 11 (klayout-tools#1994).
- `erc.missing_tie` IS computed by this run (issue #159). The spec declares
  two `ties[]` (derivation in the spec's `_comment`, from
  `layout/bitcell/generate.py` `X_TIE`/`Y_NTIE_*`/`Y_PTIE_*` and the GDS):
  `nwell_tie` (Nwell 21/0, tap = Comp 22/0 AND Nplus 32/0, net VDD) and
  `substrate_tie` (gf180mcu draws no p-well, so `well_layer: null` +
  one `well_boxes` entry per row, tap = Comp 22/0 AND Pplus 31/0, net VSS;
  klayout-tools#2255). The earlier omission (false `erc.supply_short`,
  klayout-tools#2169) is fixed upstream (#2186) and in the released klt
  0.6.0. In the committed report `erc_coverage` has `checked: 16644`
  (16,640 `erc.floating_gate` + `erc.missing_tie` for each tie +
  `erc.net_connectivity` for VDD and VSS), `skipped: 0`,
  `checked_by_well_assertion: 1` (the substrate tie: its well region is the
  spec's assertion, which `klt erc` accepts only if non-degenerate and
  falsifiable; disclosed, not hidden). `erc_coverage` is kept in full in the
  committed abridgement, as are `erc_findings`, `erc_finding_count`,
  `ties_disclosure` and `provenance`; `gates[]` is truncated to its first 4
  of 16,640 entries (verbatim; `gate_count` is the true total) so the
  envelope stays recognizable to `klt signoff` (a top-level `gates` list
  plus `gate_role`), and the antenna `coverage` row arrays are collapsed.
  A zero finding count is only evidence because those tie entries sit in
  `checked` and `skipped` is empty. `lvs-array.json` is still cited beside
  it (the manifest's item 11 is the list [ERC report, LVS report]).
- The supply check demonstrably computes on this layout: declaring a net
  with no label anywhere in the GDS (negative control, `VDX`, issue #124)
  fires `erc.unconnected_net` on the same spec/run shape.
- Negative control for the tie check (issue #159). Tool: released
  `klayout-tools==0.6.0` (git tag `v0.6.0`, commit `c622e8ad`, klayout
  0.30.12) via `uvx`. Changed field: `ties[0].net` of the committed spec,
  `"VDD"` -> `"VSS"` (the N-well tap is then declared to be tied to the
  wrong supply); nothing else differs (spec saved temporarily as
  `spec-wrongnet.json`, content hash `sha256:b39bfb63...`; the committed
  spec is untouched). Command (run from the repo root, ~26 min):

  ```sh
  uvx --from "klayout-tools==0.8.0" klt erc \
      layout/sram_256x32/sram_256x32_array.gds spec-wrongnet.json --format json
  ```

  Result: exit code 3, `erc_status: violations`, `erc_finding_count: 256`,
  every finding `{"rule": "erc.missing_tie", "layer": "nwell_tie", "net":
  "VSS", "description": "well/tub tap is not connected to declared net
  'VSS'"}` -- one per row (first finding bbox `left 430, bottom 1039960,
  right 143150, top 1041940` in nm); no other rule fires, and `erc_coverage`
  still lists both ties as checked. So the tie check computes and can
  fail on this layout. (The positive run's exit code is 4: the antenna half
  reads `not_checked` by design; `generate.sh` tolerates exactly that.)
  Only the N-well tie has a recorded negative control; no control has yet
  been run on `substrate_tie` (the asserted-well tie).
- `provenance.input.content_hash` matches the committed GDS
  (`sha256:c566b015...`, the same hash `drc-array.json` and
  `extract-array.json` grade), and `provenance.spec.content_hash`
  (`sha256:f4ff7786...`) pins the committed spec. The report was minted with
  the released klt 0.6.0 (klayout 0.30.12); the ~26-minute runtime is what
  this 16,640-gate array costs `klt erc`.


## Known gap: macro-level LVS (no `lvs-macro.json`)

`drc-macro.json` has **no LVS or extract counterpart, deliberately**. There is no
`lvs-macro.json` and no `extract-macro.json` in this directory, and no stub stands
in for either -- so **no macro-level connectivity claim is made anywhere in this
repo**, in either direction. The assembled macro is DRC-clean and its 109 pins are
checked (`layout/macro/check_pins.py`, `layout/verify.sh` step 5f); whether the
blocks' abutted pins actually *connect* is unverified.

The blocker is hierarchical LVS compare in the tool:
[2AMLogic/klayout-tools#5322](https://github.com/2AMLogic/klayout-tools/issues/5322)
is open, and the macro LVS deliverable is tracked in issue #247 (which stays open
for exactly that). The per-block LVS rows in the table above each prove one cell
against its own netlist and do **not** compose into a macro-level verdict.

When #5322 lands, the macro LVS report belongs here as `lvs-macro.json`, added by
#247 -- with its own row in the table above and this section retired.

## Known gap: array-level LVS (`lvs-array.json`)

`klt extract` is **flat-only** (`layout/README.md` "Known tool gaps" #2,
filed as
[klayout-tools#1085](https://github.com/2AMLogic/klayout-tools/issues/1085)):
extracting the hierarchical 256x32 array GDS (one bitcell cell + one
`CellInstArray`) flattens to 49,152 top-level devices, while the
hierarchical reference netlist (`design/netlist/sram_256x32_array.spice`,
one `.subckt bitcell_6t` + 8,192 calls) stays hierarchical. Until the
compare side learned to handle that asymmetry, `klt lvs` could not pair
the two circuit tops at all -- an earlier revision of this section quoted
a `"status": "mismatch"` result whose `circuit could not be matched to a
counterpart` topology mismatches were described as the expected outcome.

That compare-side failure is resolved. `klt lvs` grew a
`flatten_reference` option (klayout-tools#1085, **closed 2026-08-17**
upstream), and #112 adopted it here: `generate.sh` regenerates this report
with `options.flatten_reference: true`, which flattens the *reference*'s
hierarchy in-process -- collapsing every subcircuit-call instance in place
-- so the already-flat extracted layout side gets a directly comparable
counterpart. The committed report now reads:

```json
"status": "match",
"mismatch_count": 1,
"mismatches": [
  {
    "category": "topology.flattened",
    "severity": "warning",
    "description": "options.flatten_reference flattened the reference netlist before comparing: 2 circuit(s) were collapsed into 1 top-level circuit(s), substituting every subcircuit-call instance in place -- this compare verified topology only after removing the original hierarchy boundaries on this side (see docs/cli/lvs.md, \"topology.flattened\")",
    "side": "reference"
  }
],
"counts": {
  "nets": { "layout": 16706, "reference": 16706, "matched": 16706 },
  "devices": { "layout": 49152, "reference": 49152, "matched": 49152 },
  "pins": { "layout": 322, "reference": 0, "matched": 322 }
}
```

with `options.flatten_reference: true` echoed in the report's `options`
block, and 49,152/49,152 devices, 16,706/16,706 nets, and 322/322 pins
matched. The single `mismatches[]` entry is the expected
`severity: warning` `topology.flattened` **disclosure of the flatten
itself**, not a defect -- `mismatch_count` counts every `mismatches[]`
entry, warnings included, which is why a matched compare still carries a
`1`.

The *known gap* that remains is extraction-side: `klt extract` still only
ever produces a flat layout-side netlist, and the hierarchy reconciliation
happens inside `klt lvs`'s compare, not in extraction. That limitation is
still real and is what makes the reference-side flatten necessary at all,
but it no longer blocks a passing array-level compare: array/macro-level
LVS is achievable today via `options.flatten_reference`, exactly as
`layout/README.md` "Known tool gaps" #2 states for these same reports
(its structural array-connectivity narrative now backs a *passing*
`klt lvs` run instead of standing in for the missing one).

Not resolved here: item 4's LVS provenance/freshness for the array report
(the `stale_evidence` grading reason, issue #128) is a separate, still-open
gap and stays tracked there.

## Provenance hygiene: one scrub path

Every report in this directory is written by exactly one piece of code --
[`commit_report.py`](commit_report.py), called from `generate.sh` as
`commit_report <raw-json> <out-json> [--set F=V] [--drop F] [--print FMT]`.
There is no second path, and that is the point. It does three things to every
report, in order:

1. **Rewrite.** The generating checkout's root (`$ROOT`) and the run's scratch
   directory (`$WORK`) are stripped out of *every string in the document* --
   any nesting depth, any field, including fields `klt` has not invented yet.
   A `$ROOT`-rooted path becomes its repo-relative form
   (`layout/periphery/row/row_path.gds`); a `$WORK`-rooted path collapses to
   its basename (`row_path.spice`), because the scratch directory does not
   survive the run and `netlist_sha256` / `provenance.input.content_hash` are
   what actually pin that file's content. **No field is named anywhere in the
   script**, so no field can be left off a list.
2. **Check, with the tool's own linter.** The rewritten report is handed to
   `klt env-provenance lint-envelope` *before* it is moved into place. A report
   that still holds any absolute path is **not written** -- the run fails, with
   the offending field named. Two fields are deliberate prose rather than paths
   and are set explicitly with `--set`: the scratch abutted composite's `file`
   (`drc-column-abut.json`, `drc-native-column-abut.json`) and the PDK-native
   `deck` (`drc-native-column-*.json`).
3. **Re-dump** with `indent=2` and a trailing newline, then print the status
   line (`--print` is a `str.format` template over the report's top-level
   fields).

Before issue #340 this was ten inline `python3 -c` blocks in `generate.sh`,
each with its own hand-picked list of fields to rewrite. The lists drifted, as
hand-maintained lists do, and the three reports named in the baseline below are
what that drift left behind. `python3 layout/reports/test_commit_report.py`
asserts the two properties that matter: that the rewrite reaches fields nobody
listed, and that the guard refuses to commit a leak.

This implements issue #109's ratified rule -- repo-relative paths in committed
evidence, and existing records never rewritten retroactively -- with one
implementation instead of one per block.

### The CI half, and what is grandfathered

[`scripts/ci/check-provenance-hygiene.sh`](../../scripts/ci/check-provenance-hygiene.sh)
runs `klt env-provenance scan` over the tracked JSON reports under
`layout/reports/` and `views/reports/` on every PR (the `provenance-hygiene`
job, on the same pinned `klayout-tools==0.8.0` as the `signoff` job).

It asks a **narrower** question than the mint-time guard above: `scan` reports
home-directory-shaped paths ("does this record name a person"), while
`lint-envelope` reports *any* absolute path ("does every reference still
resolve on another checkout"). Mint time can afford the stricter question
because nothing is grandfathered there -- the report does not exist yet. PR
time cannot, because three reports were already leaking when the check landed
and #109 forbids rewriting them:

| Report | Field | Why it is still there |
|---|---|---|
| `drc-foundry-bitcell.json` | `file` | The foundry's own macro GDS, read from the generating host's PDK install (`~/.volare`). Not produced by `generate.sh` at all -- it checks the foundry macro, not this repo's layout -- so no generator change covers it. |
| `extract-array.json` | `file` | Minted by issue #128 from an agent worktree, before `klt` emitted a repo-relative `file` and before the #109 rule existed. |
| `extract-bitcell.json` | `file` | Same vintage, same cause. |

Those three are named in
[`scripts/ci/provenance-leak-baseline.txt`](../../scripts/ci/provenance-leak-baseline.txt)
and **printed on every run, pass or fail**, so a green build still shows that
three known leaks exist rather than hiding them in a narrowed glob. Anything
not in that file fails the build; a baseline entry that no longer matches a
real finding *also* fails it, so the list cannot rot into a blanket exemption.
Whether to re-mint the three is an operator call, not a cleanup -- and when it
is made, the fix is to re-run `generate.sh` (the first two) and delete the
corresponding baseline lines.

Two more absolute paths survive in committed reports that `scan` does not
flag, because they name no user: `lvs-array.json`'s `layout` and
`lvs-bitcell.json`'s `layout`/`reference` hold `/tmp/tmp.<random>/...` scratch
paths from the run that minted them. `commit_report` collapses those today
(they are `$WORK`-rooted), so the next legitimate re-mint clears them; they are
left as-is here for the same append-only reason.

## Freshness note: snapshot, not append-only

Unlike `sim/*/records/` (append-only per `sim/README.md`), the files in this
directory are **overwritten in place** by every `generate.sh` run. That is
deliberate: DRC/LVS signoff is a property of "the layout as it stands
today," not a PVT measurement series where every historical result stays
relevant -- there is exactly one current answer to "is the committed layout
DRC-clean and LVS-matched," and re-running `generate.sh` after any
`design/`/`layout/` change is how a caller re-establishes it. Git history
(`git log -- layout/reports/`) is the append-only trail here, not a
directory-naming convention.

## References

- `layout/README.md` -- the layout this directory verifies, its scope, and
  the same known-gap list this file's "Known gap" section cites.
- `design/README.md` -- the schematic/netlist sources these reports compare
  against.
- Issue #23 -- the acceptance criteria this directory satisfies (items 3, 4;
  item 7, post-layout PEX, is `sim/pex/`'s job, not this directory's -- see
  `sim/pex/README.md`).
- [`commit_report.py`](commit_report.py) -- the single scrub-and-lint path
  every report here is written by, and
  [`test_commit_report.py`](test_commit_report.py) its tests (issue #340).
- Issues #109 and #340 -- the provenance-hygiene rule these reports follow
  (#109 ratified it; #340 gave it one implementation and the CI guard
  described in "Provenance hygiene: one scrub path" above).
