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
out and overwrites the files below in place.

## Results (DRC/LVS/extract rows as of `db3fa5c`, 2026-08-21; `erc-array-supply.json` added 2026-09-21, issue #124)

| Report | Command | Result |
|---|---|---|
| `drc-bitcell.json` | `klt drc --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds` | `status: clean`, 0 violations |
| `drc-array.json` | `klt drc --deck gf180mcu layout/sram_256x32/sram_256x32_array.gds` | `status: clean`, 0 violations |
| `extract-bitcell.json` | `klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds` | 6 devices (4 nfet + 2 pfet), 7 nets |
| `lvs-bitcell.json` | `klt lvs` vs. `design/netlist/bitcell_6t.spice` (via `layout/lvs_reference.py`) | `status: match`, 0 mismatches, 6/6 devices, 7/7 nets |
| `extract-array.json` | `klt extract --deck gf180mcu layout/sram_256x32/sram_256x32_array.gds` | 49,152 devices (32,768 nfet + 16,384 pfet), 16,706 nets, 322 pins -- `devices[]`/`nets[]` omitted from the committed file (~18 MB unabridged; every other field, including counts and provenance, is kept in full) |
| `lvs-array.json` | `klt lvs` vs. `design/netlist/sram_256x32_array.spice` | `status: mismatch` -- **expected**, see "Known gap: array-level LVS" below |
| `drc-foundry-bitcell.json` | `klt drc --deck gf180mcu` vs. the foundry's own `gf180mcu_fd_ip_sram__sram64x8m8wm1.gds` | `status: violations`, 2010 violations, all `comp.enclosing.contact.1` -- **expected**, see `sram-rule-survey.md` (issue #8) |
| `erc-array-supply.json` | `klt erc layout/sram_256x32/sram_256x32_array.gds layout/sram_256x32/erc-supply-spec.json --format json` | `erc_finding_count: 0` -- declared supplies VDD/VSS each resolve to exactly one electrical island; `status: not_checked` is the antenna half's rollup, not the supply verdict (see "Item 11" below) |

`drc-foundry-bitcell.json` is generated and maintained separately from the
five reports above -- it checks the *foundry's* macro, not this repo's own
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
mismatches, against the actual schematic-derived reference netlist (with
`layout/lvs_reference.py`'s bulk-terminal rewrite applied -- see
`layout/README.md` "Known tool gaps" #1 for why that rewrite exists and why
it is currently a no-op).

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
- `erc.missing_tie` is **not computed** by this run: the spec deliberately
  omits `ties[]`, because declaring one on a real routed design collapses
  the layout into one electrical island and reports a *false*
  `erc.supply_short` (klayout-tools#2169, reproduced four ways as
  gf180-drone-fc FRICTION F-034). Per `klt erc`'s own contract an omitted
  `ties[]` means the rule is never computed -- the committed spec and this
  section state that explicitly: it is an absence of evidence, not
  evidence of absence. The well-tie evidence that stands in for it:
  (1) `lvs-array.json`'s device-aware `match` with the supplies paired in
  `net_correspondence` above; (2) `extract-array.json`'s 16,706 extracted
  nets resolving the supplies to exactly one net each; (3) the bitcell's
  drawn taps (`Pplus` substrate strip, `Nplus`-on-`Nwell` strip,
  `layout/bitcell/generate.py`), DRC-clean in `drc-bitcell.json` /
  `drc-array.json`.
- The supply check demonstrably computes on this layout: declaring a net
  with no label anywhere in the GDS (negative control, `VDX`) fires
  `erc.unconnected_net` on the same spec/run shape -- the committed
  zero-findings result is a passed check, not a skipped one.
- `provenance.input.content_hash` matches the committed GDS
  (`sha256:c566b015...`, the same hash `drc-array.json` and
  `extract-array.json` grade), and `provenance.spec.content_hash` pins the
  committed spec. The report was minted with klt `0.5.0+gd5893304afc2`
  (klayout 0.30.12); `generate.sh`'s header documents the minimum tool
  requirement (a klt whose erc envelope carries the #1968
  status+provenance block -- released 0.5.0 predates it) and the ~26-minute
  runtime this 16,640-gate array costs `klt erc`.


## Known gap: array-level LVS (`lvs-array.json`)

`klt extract` is **flat-only** (`layout/README.md` "Known tool gaps" #2,
filed as
[klayout-tools#1085](https://github.com/2AMLogic/klayout-tools/issues/1085)):
extracting the hierarchical 256x32 array GDS (one bitcell cell + one
`CellInstArray`) flattens to 49,152 top-level devices, while the
hierarchical reference netlist (`design/netlist/sram_256x32_array.spice`,
one `.subckt bitcell_6t` + 8,192 calls) stays hierarchical. `klt lvs`
cannot pair the two circuit tops at all:

```json
"status": "mismatch",
"mismatches": [
  { "category": "topology", "description": "circuit could not be matched to a counterpart", "side": "both" },
  { "category": "topology", "description": "circuit could not be matched to a counterpart", "side": "reference" }
]
```

This is the same failure `layout/README.md` already documented from
`verify.sh`'s own bitcell-only checks; `lvs-array.json` is fresh,
reproducible evidence of it at the array level specifically, run as part of
this issue. Closing this gap needs either hierarchy-preserving extraction or
a reference-flattening path upstream in `klt` -- tracked by
klayout-tools#1085, not by this repo. Array-level connectivity is instead
argued structurally in `layout/README.md` ("The array, and why it needs
almost no array-level routing": one continuous wordline per row, one
continuous bitline pair per column, two `Metal3` supply straps) and spot-
checked by the extracted net/device counts matching the expected
`6 x 8192 = 49152` devices and `256 + 64 + 2 + 16384 = 16706` nets exactly --
not by a passing `klt lvs` run.

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
