# layout/reports -- DRC and LVS signoff evidence (issue #23, T1 items 3/4)

Machine-readable `klt drc`/`klt lvs`/`klt extract` reports for the layout
committed in `layout/` (issue #22), checked against the schematic sources
committed in `design/` (issue #21). `layout/README.md` already quoted these
numbers in prose; this directory is the committed, provenance-carrying
artifact those numbers cite, per issue #23's acceptance criteria ("All
three reports committed under `layout/` ... each carrying provenance
(klt version, deck/PDK content hash, design revision) sufficient to detect
staleness").

Regenerate everything here with `./layout/reports/generate.sh` (from the
repo root). It re-runs `klt drc`/`klt extract`/`klt lvs` against whatever
`layout/*.gds` and `design/netlist/*.spice` are currently checked out and
overwrites the files below in place.

## Results (as of `db3fa5c`, 2026-08-21)

| Report | Command | Result |
|---|---|---|
| `drc-bitcell.json` | `klt drc --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds` | `status: clean`, 0 violations |
| `drc-array.json` | `klt drc --deck gf180mcu layout/sram_256x32/sram_256x32_array.gds` | `status: clean`, 0 violations |
| `extract-bitcell.json` | `klt extract --deck gf180mcu layout/bitcell/sram_bitcell_6t.gds` | 6 devices (4 nfet + 2 pfet), 7 nets |
| `lvs-bitcell.json` | `klt lvs` vs. `design/netlist/bitcell_6t.spice` (via `layout/lvs_reference.py`) | `status: match`, 0 mismatches, 6/6 devices, 7/7 nets |
| `extract-array.json` | `klt extract --deck gf180mcu layout/sram_256x32/sram_256x32_array.gds` | 49,152 devices (32,768 nfet + 16,384 pfet), 16,706 nets, 322 pins -- `devices[]`/`nets[]` omitted from the committed file (~18 MB unabridged; every other field, including counts and provenance, is kept in full) |
| `lvs-array.json` | `klt lvs` vs. `design/netlist/sram_256x32_array.spice` | `status: mismatch` -- **expected**, see "Known gap: array-level LVS" below |
| `drc-foundry-bitcell.json` | `klt drc --deck gf180mcu` vs. the foundry's own `gf180mcu_fd_ip_sram__sram64x8m8wm1.gds` | `status: violations`, 2010 violations, all `comp.enclosing.contact.1` -- **expected**, see `sram-rule-survey.md` (issue #8) |

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
