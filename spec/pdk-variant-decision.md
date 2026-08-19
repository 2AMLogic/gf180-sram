# Decision record: pin `gf180mcuD`, not `gf180mcuC`

**Status**: Decided, 2026-08-19
**Resolves**: #86 ("Pin gf180mcuD (not gf180mcuC) — spec, design/, layout/,
and sim/ evidence all cite the wrong shuttle variant")
**Amends**: `design/README.md` and `layout/README.md` "Tool / PDK versions"
sections, `sim/README.md` "Pinned PDK revision" and its cold-start snippet,
`sim/lib/pdk_env.sh`'s default variant, `design/xschemrc`'s default variant,
`spec/kb-scale-integration.md`'s LEF-read example, and
`measurements/generate_report.py`'s generated report (citation-only — see
"What this record does not change")
**Does not amend**: `spec/bitcell-decision.md` — that record's `gf180mcuC`
citations are inside verbatim, dated terminal transcripts (2026-08-05) and
are left untouched per this repo's evidence conventions; it now carries a
forward pointer to this record instead.

## Question

Every PDK-variant citation in this repo reads `gf180mcuC`. Is that the
correct variant to build and verify against, or does a fleet-wide ruling
pin a different one — and if the variant changes, does any of this repo's
electrical or geometric evidence need re-running, or only re-citing?

## Answer

**Pin `gf180mcuD`, at the same `open_pdks` commit already cited everywhere
in this repo (`c6d73a35f524070e85faff4a6a9eef49553ebc2b`). No simulation or
layout evidence needs to be re-run — this is a citation-only correction,
justified below with direct file-level evidence, not asserted.**

### Why `gf180mcuD`

`gf180-tmds-tx#9` DR-0006 (amended 2026-08-19) is the fleet-wide operator
ruling: every `gf180-*` canary's actual tape-out path runs through
wafer.space, whose GF180MCU shuttle runs advertise the `gf180mcuD` stack
(`product/drone-controller/landscape/datasheets/silicon/report.md`).
TinyTapeout's GF submits go through wafer.space too, so every observed
tape-out path for this fleet is D, not C. This repo has no local reason to
diverge from that ruling — nothing in `spec/sram.md` or
`spec/bitcell-decision.md` ties this design to metal-stack option C
specifically; `gf180mcuC` was used incidentally, as "any of the four"
process variants, during the 2026-08-05 bitcell survey
(`spec/bitcell-decision.md`), and every downstream citation in this repo
just inherited that incidental choice rather than a deliberate one.

This repo's own audit trail (`2AMLogic/2am#350`, cross-repo) flagged this
repo as one of two (of eleven audited) `gf180-*` canaries whose evidence
tree is internally consistent but pinned to the wrong variant against that
ruling.

### `gf180mcuC` vs `gf180mcuD`: what actually differs

Both are the same `open_pdks` commit
(`c6d73a35f524070e85faff4a6a9eef49553ebc2b`), installed side by side on this
host under `~/.volare/gf180mcuC` and `~/.volare/gf180mcuD`. Verified
directly, 2026-08-19:

```
$ diff -u ~/.volare/gf180mcuC/.config/nodeinfo.json ~/.volare/gf180mcuD/.config/nodeinfo.json
--- gf180mcuC/.config/nodeinfo.json
+++ gf180mcuD/.config/nodeinfo.json
@@ -1,10 +1,10 @@
 {
     "foundry": "GF",
     "foundry-name": "Global Foundries",
-    "node": "gf180mcuC",
+    "node": "gf180mcuD",
     "feature-size": "180nm",
     "status": "active",
-    "description": "... 5 metal layer backend stack + 0.9um thick top metal + ...",
+    "description": "... 5 metal layer backend stack + 1.1um thick top metal + ...",
```

A full recursive file-tree diff between the two variant roots (`find | diff`)
shows **no added or removed files** — only the expected variant-labelled
filename renames (`gf180mcuC.tech` -> `gf180mcuD.tech`,
`gf180mcuC_setup.tcl` -> `gf180mcuD_setup.tcl`, etc., under `libs.tech/`).
The two variants are the same PDK content wrapped in a different metal-stack
option, exactly as `gf180-tmds-tx#9` DR-0006 describes.

The magic `.tech` DRC/parasitic rule deck diff (content, not filenames)
isolates the actual behavioral delta to **Metal5 only**:

```
$ diff <(sed s/gf180mcuC/X/g ~/.volare/gf180mcuC/libs.tech/magic/gf180mcuC.tech) \
       <(sed s/gf180mcuD/X/g ~/.volare/gf180mcuD/libs.tech/magic/gf180mcuD.tech)
<  width *m5,rm5 440 "Metal5 width < %d (MT.1)"
>  width *m5,rm5 360 "Metal5 width < %d (MT.1)"
<  spacing allm5,obsm5  allm5,obsm5 460 ... "Metal5 spacing < %d (MT.2a)"
>  spacing allm5,obsm5  allm5,obsm5 380 ... "Metal5 spacing < %d (MT.2a)"
<  area allm5,obsm5 526500 440 "Metal5 minimum area < %a (MT.4)"
>  area allm5,obsm5 562500 360 "Metal5 minimum area < %a (MT.4)"
<  widespacing allm5,obsm5 10000 allm5,obsm5  600 ...
>  widespacing allm5,obsm5 10000 allm5,obsm5  500 ...
<  resist (allm5)/metal5  	    40 / 49 / 31   (three corners)
>  resist (allm5)/metal5  	    60 / 70 / 50   (three corners)
<  device rsubcircuit tm9k  rm5 *m5 ...
>  device rsubcircuit tm11k rm5 *m5 ...
```

Every differing rule is scoped to `allm5`/`obsm5`/`rm5` (Metal5 and its
resistor device) — width, spacing, area, and sheet-resistance rules that
follow directly from the 0.9 um vs 1.1 um top-metal thickness the
`nodeinfo.json` description states. **No rule below Metal5 differs at
all** — confirmed by the same diff producing zero hunks outside the
Metal5-tagged lines above, matching `gf180-tmds-tx` DR-0010's finding that
only Metal5-specific geometry/parasitics differ between variants.

### Sensitivity determination (task item 3): NOT sensitive — evidenced, not asserted

Per DR-0010's pattern (show, don't assert), each of this repo's evidence
classes was checked directly against both installed variants:

1. **SPICE device models — byte-identical.** Every model file this repo's
   `sim/` testbenches actually source
   (`sim/lib/pdk_env.sh` -> `GF180_MODEL_FILE`/`GF180_DESIGN_INC`, used by
   every `run_corner_sweep.sh` invocation via `.lib '$GF180_MODEL_FILE'
   ...`) is byte-for-byte identical between the two variant roots:

   ```
   $ diff -q ~/.volare/gf180mcuC/libs.tech/ngspice/sm141064.ngspice      ~/.volare/gf180mcuD/libs.tech/ngspice/sm141064.ngspice
   $ diff -q ~/.volare/gf180mcuC/libs.tech/ngspice/sm141064_mim.ngspice  ~/.volare/gf180mcuD/libs.tech/ngspice/sm141064_mim.ngspice
   $ diff -q ~/.volare/gf180mcuC/libs.tech/ngspice/design.ngspice        ~/.volare/gf180mcuD/libs.tech/ngspice/design.ngspice
   $ diff -q ~/.volare/gf180mcuC/libs.tech/ngspice/smbb000149.ngspice    ~/.volare/gf180mcuD/libs.tech/ngspice/smbb000149.ngspice
   ```

   All four `diff -q` invocations produced no output (identical). Since
   every read/write SNM, write-margin (WTV), and access-time record under
   `sim/*/records/` and `sim/*/mc/records/` is a device-level ngspice
   simulation against these exact model files, and the models are
   unchanged, **every recorded numeric value is unaffected by the C-vs-D
   distinction** — a re-run against `gf180mcuD` would reproduce the same
   corner values already committed, corner ID for corner ID.

2. **This repo's committed layout geometry never reaches Metal5 (or even
   Metal4).** Grepping every drawn layer in `layout/bitcell/generate.py`
   and `layout/sram_256x32/generate.py` (the only two layout generators in
   this repo) shows drawn geometry limited to `Poly2`, `COMP`, `Contact`,
   `Metal1`, `Metal2`, and `Metal3` (array-level `VDD`/`VSS` straps) — no
   `Metal4` or `Metal5` reference anywhere. The only rule delta between the
   two variants is Metal5-scoped (see above), so it cannot affect this
   layout's DRC cleanliness, extracted device count, or LVS match — those
   checks never touch the layer the two variants disagree about.

3. **`klt`'s curated DRC/LVS engine doesn't consume the PDK's variant-scoped
   rule deck at all.** `layout/README.md`'s DRC/LVS results come from
   `klt drc --deck gf180mcu` / `klt extract --deck gf180mcu` / `klt lvs`,
   which run `klt`'s own generic curated `gf180mcu` deck (`klt drc --help`:
   `--deck` accepts only `sky130`, `gf180mcu`, `sg13g2` — one deck per
   process family, not one per variant). The PDK's own magic `.tech` file
   (the one place the Metal5 rule delta actually lives) is only consumed by
   `klt`'s alternate `--engine klayout` path, which `layout/README.md`
   documents as unused on this host (issue #23's scope). So this repo's
   committed DRC/LVS results do not depend on the variant-scoped rule deck
   at all, independent of point 2 above.

4. **The foundry reference macro used for the area comparison is
   byte-identical too.** `spec/bitcell-decision.md` and `layout/README.md`
   ("Area: measured against the foundry's own bitcell") both read
   `gf180mcu_fd_ip_sram`'s shipped GDS/SPICE/LEF as a comparison dataset.
   Checked directly:

   ```
   $ diff -q ~/.volare/gf180mcuC/libs.ref/gf180mcu_fd_ip_sram/gds/gf180mcu_fd_ip_sram__sram64x8m8wm1.gds \
             ~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_ip_sram/gds/gf180mcu_fd_ip_sram__sram64x8m8wm1.gds
   $ diff -q ~/.volare/gf180mcuC/libs.ref/gf180mcu_fd_ip_sram/spice/gf180mcu_fd_ip_sram__sram64x8m8wm1.spice \
             ~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_ip_sram/spice/gf180mcu_fd_ip_sram__sram64x8m8wm1.spice
   $ diff -q ~/.volare/gf180mcuC/libs.ref/gf180mcu_fd_ip_sram/lef/gf180mcu_fd_ip_sram__sram512x8m8wm1.lef \
             ~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_ip_sram/lef/gf180mcu_fd_ip_sram__sram512x8m8wm1.lef
   ```

   All three produced no output (identical). (The `libs.ref/.../mag/*.mag`
   Magic-format views *do* differ textually, but only in an embedded `tech
   gf180mcuC`/`tech gf180mcuD` technology-name header line, not in drawn
   geometry — and this repo does not use Magic views at all, only
   GDS/SPICE/LEF via `klt`/ngspice, so that difference is moot here.)

**Conclusion**: bit-line parasitic capacitance was the plausible
load-bearing path this record was tasked with checking (per DR-0010's
ESD-pad-capacitance precedent), but this design's bit lines run on `Metal1`
and its array-level supply straps on `Metal2`/`Metal3` only — layers the two
variants do not disagree on at all. Combined with byte-identical SPICE
models and a variant-agnostic DRC/LVS engine, **no read/write margin,
access-time, or Monte Carlo yield figure in this repo is sensitive to the
C-vs-D metal-stack difference.** A re-run would reproduce the committed
numbers exactly; only the citation was ever wrong.

## What this record changes

- `design/README.md`, `layout/README.md` "Tool / PDK versions" — re-cited to
  `gf180mcuD`.
- `sim/README.md` "Pinned PDK revision" and its cold-start `export
  PDK=...` example, `sim/lib/pdk_env.sh`'s default variant fallback
  (`${PDK:-gf180mcuC}`), and `design/xschemrc`'s default-variant fallback
  (`gf180mcuC`) — these are not just documentation, they are the literal
  default a future un-parameterized run of this repo's regeneration/sim
  commands would resolve to. Per the issue's own evidence ("no
  `DEFAULT_VARIANT` fallback pointing at D anywhere in this repo"), leaving
  these defaulted to C would silently reproduce the mismatch on the next
  regeneration even after this record lands, so they are corrected here
  rather than left as a documentation-only fix.
- `spec/kb-scale-integration.md`'s LEF-read example command — re-cited
  (the LEF itself is confirmed byte-identical above, so its quoted `SIZE`
  output is unchanged).
- `measurements/characterization-report.md` — regenerated via
  `measurements/generate_report.py` (not hand-edited) after adding a fixed
  correction paragraph citing this record; the underlying `sim/*/records/*.md`
  and `sim/*/mc/records/*.md` source records are **not** rewritten, per this
  repo's append-only evidence convention (`sim/README.md`, "Append-only
  rule") — they remain historical entries correctly dated and correctly
  showing the tool state (`gf180mcuC`) as it was actually run at the time,
  and this record is what a reader now consults to know that a `gf180mcuD`
  re-run would reproduce them unchanged.

## What this record does not change

- No `sim/*/records/*.md` or `sim/*/mc/records/*.md` file is edited or
  re-run — the sensitivity determination above establishes a re-run is
  unnecessary, and this repo's append-only convention would forbid editing
  them in place regardless.
- No layout GDS is regenerated — `layout/bitcell/generate.py` and
  `layout/sram_256x32/generate.py` read the PDK only for the layer/datatype
  map (`layout/README.md`, "Tool / PDK versions"), and neither generator's
  output depends on which variant supplies that map (both variants' layer
  tables agree below Metal5, and neither generator draws Metal4/Metal5).
- `spec/bitcell-decision.md` is left untouched. Its `gf180mcuC` citations
  are inside verbatim 2026-08-05 terminal transcripts documenting what was
  actually run that day — rewriting them would misrepresent the historical
  record. A pointer to this decision record has been added near its top
  instead.
- `spec/sram.md` is unaffected — it does not cite a PDK variant at all.

## References

- `gf180-tmds-tx#9`, DR-0006 (amended 2026-08-19) — fleet-wide operator
  ruling pinning `gf180mcuD` for every `gf180-*` canary, citing
  `product/drone-controller/landscape/datasheets/silicon/report.md`
  (wafer.space GF180MCU shuttle stack).
- `gf180-tmds-tx#9`, DR-0010 — the precedent for how to reason about which
  artifacts need re-running vs. re-citing when a PDK-variant pin changes
  (SPICE device models and `klt`'s curated DRC/LVS deck are variant-agnostic;
  only Metal5-specific geometry/parasitics differ), applied directly above.
- `2AMLogic/2am#350` — the cross-repo audit that filed this issue
  (`gf180-sram#86`) after surveying PDK-variant pinning across all
  `gf180-*` fleet canaries.
- `spec/bitcell-decision.md` — the 2026-08-05 record whose incidental use of
  `gf180mcuC` (among all four variants, `A`/`B`/`C`/`D`) became this repo's
  de facto, undeliberate default.
- `~/.volare/gf180mcuC/.config/nodeinfo.json`,
  `~/.volare/gf180mcuD/.config/nodeinfo.json` — the variant description
  strings ("0.9um thick top metal" vs "1.1um thick top metal") this record's
  diffs above are drawn from, both at `open_pdks` commit
  `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
