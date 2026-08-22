# SRAM design-rule survey and foundry-bitcell DRC comparison (issue #8)

This document does two things `layout/README.md` and `spec/bitcell-decision.md`
both flagged as open ("the custom bitcell's own DRC waiver/special-rule status
is not yet established"):

- **Part A** — surveys gf180mcu's DRM for the `SramCore` (108/5) marker-scoped
  rule allowances, citing the PDK's own rule-deck source directly (the same
  way `layout/bitcell/generate.py`'s constants cite the generic rules they
  satisfy), and states plainly which rule families the marker does and does
  not touch.
- **Part B** — runs `klt drc --deck gf180mcu` (the curated deck this repo's
  own DRC evidence already uses) against a shipped `gf180mcu_fd_ip_sram`
  macro GDS — the foundry's own hardened bitcell, not this repo's
  custom-drawn one — and separately attempts and records the PDK-native
  `klt drc --engine klayout` engine.

No change to `layout/bitcell/generate.py`'s drawn geometry was made or is
proposed here; per the issue, this is a survey and a comparison run only.

## Part A: what the `SramCore` (108/5) marker relaxes

**Source of truth.** gf180mcu's own KLayout DRC-DSL rule deck ships inside
the PDK install as per-topic Ruby fragments under
`libs.tech/klayout/tech/drc/rule_decks/*.drc`
(`~/.volare/gf180mcuD/...`, `open_pdks` commit
`c6d73a35f524070e85faff4a6a9eef49553ebc2b` — the same commit
`spec/bitcell-decision.md` and `spec/pdk-variant-decision.md` cite), assembled
into one runnable script by `libs.tech/klayout/tech/drc/run_drc.py`. The
marker itself is defined in `rule_decks/layers_def.drc:216`:

```ruby
sramcore = get_polygons(108, 5)
```

confirming the issue's own citation of `SramCore` as GDS layer/datatype
`108/5`. Two dedicated rule-table fragments exist and run only `if FEOL`:
`rule_decks/sram_3p3.drc` (6 rules, the 3.3V/`_LV` domain) and
`rule_decks/sram_5p0.drc` (8 rules, the 5V/`_MV` domain). Every rule in both
files scopes its check to geometry `.and(sramcore)` (or, for `S.DF.8_MV`,
`.and(sramcore)` via the shared `sram_mv`/`sram_lv` helper regions built at
the top of each file) — i.e. these 14 rules **only fire inside a drawn
`108/5` marker box**; outside it, the generic rule (same rule family, no `S.`
prefix) applies instead. This was confirmed empirically in Part B: running
the real native deck against a layout that does *not* draw the `108/5`
marker (this repo's own custom bitcell) executes all 14 `S.*` rules but they
report zero violations, because the geometry they scope to (`poly2.and(sram_lv)`,
etc.) is empty.

### Rule-by-rule: SramCore-relaxed vs. generic

Every row below is a same-named rule family with a marker-scoped SRAM variant
and a generic (non-`sramcore`) variant, cited to `rule_decks/*.drc:<line>`
under `~/.volare/gf180mcuD/libs.tech/klayout/tech/drc/`:

| Rule family | Generic rule id : value | SramCore rule id : value | Relaxation |
|---|---|---|---|
| Poly2 overlap of contact | `CO.3` : 0.07µm (`contact.drc:63`) | `S.CO.3_LV` : 0.04µm (`sram_3p3.drc:61`) | −0.03µm (43%) |
| COMP overlap of contact (3.3V) | `CO.4` : 0.07µm (`contact.drc:73`) | `S.CO.4_LV` : 0.03µm (`sram_3p3.drc:72`) | −0.04µm (57%) |
| COMP overlap of contact (5V) | `CO.4` : 0.07µm (`contact.drc:73`) | `S.CO.4_MV` : 0.04µm (`sram_5p0.drc:100`) | −0.03µm (43%) |
| Field Poly2 to unrelated/related COMP spacing (5V) | `PL.5a_MV`/`PL.5b_MV` : 0.3µm (`poly2.drc:114,127`) | `S.PL.5a_MV`/`S.PL.5b_MV` : 0.12µm (`sram_5p0.drc:84,91`) | −0.18µm (60%) |
| Nwell overlap of PCOMP outside DNWELL (3.3V) | `DF.4c_LV` : 0.43µm (`comp.drc:170`) | `S.DF.4c_LV` : 0.4µm (`sram_3p3.drc:40`) | −0.03µm (7%) |
| Nwell overlap of PCOMP outside DNWELL (5V) | `DF.4c_MV` : 0.6µm (`comp.drc:180`) | `S.DF.4c_MV` : 0.45µm (`sram_5p0.drc:40`) | −0.15µm (25%) |
| COMP extend beyond gate / source-drain overhang (5V) | `DF.6_MV` : 0.4µm (`comp.drc:239`) | `S.DF.6_MV` : 0.32µm (`sram_5p0.drc:49`) | −0.08µm (20%) |
| LVPWELL spacer to PCOMP inside DNWELL (5V) | `DF.7_MV` : 0.6µm (`comp.drc:255`) | `S.DF.7_MV` : 0.45µm (`sram_5p0.drc:56`) | −0.15µm (25%) |
| LVPWELL overlap of NCOMP inside DNWELL (5V) | `DF.8_MV` : 0.6µm (`comp.drc:271`) | `S.DF.8_MV` : 0.45µm (`sram_5p0.drc:64`) | −0.15µm (25%) |
| Nwell(outside DNWELL)-to-NCOMP spacing (3.3V) | `DF.16_LV` : 0.43µm (`comp.drc:383`) | `S.DF.16_LV` : 0.4µm (`sram_3p3.drc:50`) | −0.03µm (7%) |
| Nwell(outside DNWELL)-to-NCOMP spacing (5V) | `DF.16_MV` : 0.6µm (`comp.drc:392`) | `S.DF.16_MV` : 0.45µm (`sram_5p0.drc:74`) | −0.15µm (25%) |
| Metal1 minimum width | `M1.1` : 0.23µm (`metal1.drc:28`) | `S.M1.1_LV` : 0.22µm (`sram_3p3.drc:102`) | −0.01µm (4%) |

`S.CO.6_ii_LV` (`sram_3p3.drc:88`, a contact/metal1-overlap corner-case check)
has no single-number generic counterpart to diff against — it is a
SRAM-only refinement of the generic `CO.6` family's corner-case logic, not a
simple threshold relaxation.

### What the marker does **not** touch

The issue asked specifically about implant spacing, density, antenna,
latch-up, and poly/contact spacing. Poly/contact spacing is covered above
(it **is** relaxed, in the `CO.3`/`CO.4`/`PL.5a`/`PL.5b` rows). The other
four categories were checked by grepping every rule-table fragment for the
`sramcore` identifier:

```
$ grep -rn sramcore libs.tech/klayout/tech/drc/rule_decks/*.drc
```

- **Implant spacing (`Nplus`/`Pplus`)**: `rule_decks/nplus.drc` and
  `rule_decks/pplus.drc` contain **zero** references to `sramcore`. No
  implant-layer rule has a SRAM-marker-scoped variant in this DRM revision —
  the bitcell's `Nplus`/`Pplus` geometry is checked at the same generic
  thresholds as anywhere else in the chip.
- **Density**: `rule_decks/density.drc` (`PL.8`, `M1.4`...`MT.3` density
  rules) contains **zero** references to `sramcore`.
- **Antenna**: `rule_decks/antenna.drc` (`ANT.1`, `ANT.8`, `ANT.16_*`, ...)
  contains **zero** references to `sramcore`.
- **Latch-up**: this DRM revision has no dedicated latch-up rule *category*
  at all — the only DRC rules mentioning "latch up" in prose are two
  LDNMOS/LDPMOS guard-ring completeness rules (`MDN.13d`/neighboring rules in
  `rule_decks/ldnmos.drc`, `MDP.3` family in `rule_decks/ldpmos.drc`),
  unrelated to SRAM and with **zero** `sramcore` references.

So the marker's actual scope is narrower than "implant/density/antenna/
latch-up plus poly/contact spacing" might suggest: it relaxes exactly 12
distinct numeric FEOL thresholds (14 rule ids, since `DF.4c`/`DF.16` each
have paired `_LV`/`_MV` SRAM variants) across contact-to-poly/COMP overlap,
field-poly-to-COMP spacing, Nwell/LVPWELL-to-COMP spacing under DNWELL, and
one Metal1-width rule — and touches implant, density, antenna and latch-up
rules **not at all**.

### What `klt drc --deck gf180mcu` (the curated deck) models of this

None of it. `layout/reports/drc-bitcell.json`'s and `drc-array.json`'s own
`coverage.deck_layers` lists never include `108/5` — the curated deck has no
concept of the `SramCore` marker layer at all, so it cannot apply (or even
recognize) any of the 12 relaxations above. It checks every layout,
SRAM-marked or not, at the generic thresholds only. This is a preexisting,
already-documented fact (`layout/README.md` "What this does and does not
prove", `layout/reports/README.md` "Item 3"); Part B below makes it a
concrete, measured consequence rather than a stated limitation.

## Part B: DRC against the foundry's own hardened bitcell macro

### B.1 — curated deck (`klt drc --deck gf180mcu`)

```
$ klt drc --deck gf180mcu --format json \
    ~/.volare/gf180mcuD/libs.ref/gf180mcu_fd_ip_sram/gds/gf180mcu_fd_ip_sram__sram64x8m8wm1.gds
```

Committed as `layout/reports/drc-foundry-bitcell.json` (same schema and
provenance shape as `drc-bitcell.json`/`drc-array.json`). Result:

| | |
|---|---|
| Input | `gf180mcu_fd_ip_sram__sram64x8m8wm1.gds` (431.86 x 232.88µm, 30,608 polygons — the same macro `layout/README.md`'s "Area" section already measures the bitcell pitch from) |
| `status` | `violations` |
| `violation_count` | **2010** |
| `rule_counts` | `{"comp.enclosing.contact.1": 2010}` — every single violation is the same rule |
| Runtime | ~46s |

`comp.enclosing.contact.1` is the curated deck's generic COMP-overlap-of-
contact check — the same rule family as `CO.4`/`S.CO.4_LV`/`S.CO.4_MV` above
(generic 0.07µm; SRAM-marker-relaxed to 0.03–0.04µm). Every sampled
violation's `source_cell` is `018SRAM_cell1_64x8m81` or
`018SRAM_cell1_dummy_64x8m81` — the internal 6T bitcell subcircuit
`spec/bitcell-decision.md` already identified by name — confirming these
2010 flags land inside the bitcell array, not the macro's periphery. The
report's own `coverage.layers_in_stream_without_rules` includes `"108/5"`:
the macro's GDS **does** draw the `SramCore` marker (as expected — it is the
foundry's own hardened SRAM bitcell), the curated deck sees the layer stream
containing it, and still has no rule keyed to it. This is the curated deck's
missing-marker gap made concrete: it very likely reports the foundry's own
known-good, presumably-signed-off macro as non-clean because it checks
contact/COMP overlap at the generic 0.07µm threshold everywhere, including
inside the `SramCore`-marked region where 0.03–0.04µm is the PDK's own
intended, legal threshold.

### B.2 — native engine (`klt drc --engine klayout`)

**Available, but does not resolve automatically.** A standalone `klayout`
binary is present on `$PATH` in this environment (`klayout -v` → `KLayout
0.28.16`) — unlike the state `layout/README.md` previously recorded ("no
standalone `klayout` binary on `$PATH`"), so that specific blocker has
lifted. However:

```
$ klt drc --engine klayout --pdk gf180mcuD --format json layout/bitcell/sram_bitcell_6t.gds
{"error": {"message": "no PDK-native klayout DRC deck script found for this
PDK variant -- pass --deck-file to point at one directly ..."}}
```

This matches `klt`'s own documented limitation
(`klayout-tools`'s `docs/cli/drc.md` → "Engine" → "klayout" → "Deck
resolution"): gf180mcu ships its native deck as topic fragments
(`rule_decks/*.drc`) plus a Python assembly script (`run_drc.py`), not a
single ready-to-run `<variant>.lydrc`/`.drc` file the way sky130 does, so
`klt`'s resolver correctly finds nothing and asks for `--deck-file`.

**`--deck-file` against the PDK's per-variant macro wrapper also fails.**
gf180mcu's `libs.tech/klayout/tech/macros/gf180mcu_drc.lydrc` looks like a
candidate `--deck-file` target, but it is a GUI-macro wrapper that reads
`RBA::CellView.active.filename` (an already-loaded layout) and shells out to
`run_drc.py` itself — it does not accept `klt`'s `-rd input=<path>`
convention at all. Pointed at it directly:

```
$ klt drc --engine klayout --deck-file .../gf180mcu_drc.lydrc --format json layout/bitcell/sram_bitcell_6t.gds
{"error": {"message": "klayout did not produce a report file -- the deck
script likely failed before completing. klayout's own output: ...
running python3 .../run_drc.py --path= --variant=C --run_dir=... --macro_gen"}}
```

Note `--path=` is empty — the wrapper never saw `klt`'s `-rd input=...`
because it doesn't read that variable at all.

**A pre-built deck (the PDK's own escape hatch) resolves the file-shape
problem but hits a second, more serious gap.** `run_drc.py --macro_gen`
(the PDK's own documented way to materialize a single runnable `.drc` from
the fragments — attempted here directly, outside `klt`, since `klt` has no
path to invoke `run_drc.py` itself) produces a `main.drc` that *does* read
plain `-rd`-settable globals (`$input`, `$report`, and also `$feol`,
`$beol`, `$metal_top`, `$metal_level`, `$mim_option`, ...). Handed to `klt
drc --engine klayout --deck-file main.drc`:

```
$ klt drc --engine klayout --deck-file /tmp/gf180_drc_run/main.drc --format json layout/bitcell/sram_bitcell_6t.gds
{"status": "clean", "violation_count": 0, "coverage": {"deck_layers": [], ...}}
```

This looks like a clean pass but is not one. `klt`'s `--engine klayout`
subprocess invocation (`klayout_tools/drc.py`,
`run_drc_klayout_engine`) hard-codes exactly two `-rd` arguments:

```python
cmd = ["klayout", "-b", "-r", deck_file, "-rd", f"input={path}", "-rd", f"report={report_path}"]
```

`main.drc`'s own `FEOL`/`BEOL` globals default to `false` when `$feol`/
`$beol` are unset (`bool_check?(nil)` → `false`), and its FEOL/BEOL
condition wraps essentially every rule in the file, so this
invocation silently executes **zero** rules and reports `status: clean`
indistinguishable from a genuinely clean run. This is a real, generic `klt`
gap (a PDK-native deck that reads feature-toggle globals beyond `input`/
`report` silently no-ops under `--engine klayout`), not specific to this
repo's design — filed upstream as
[klayout-tools#1302](https://github.com/2AMLogic/klayout-tools/issues/1302)
per `CLAUDE.md`'s friction protocol.

**Direct verification (bypassing `klt` entirely).** To get a real answer for
this issue despite the gap above, `main.drc` was invoked directly with the
full set of `-rd` variables it actually needs
(`feol=true beol=true metal_top=11K metal_level=5LM mim_option=B`, matching
`gf180mcuD`'s variant per `spec/pdk-variant-decision.md`):

```
$ klayout -b -r /tmp/gf180_drc_run/main.drc \
    -rd input=<gds> -rd report=<out>.lyrdb \
    -rd feol=true -rd beol=true -rd metal_top=11K -rd metal_level=5LM -rd mim_option=B \
    -rd offgrid=true -rd connectivity=false
```

This is **not** a `klt`-mediated run (no `klt` JSON report, no committed
provenance in the schema the other `layout/reports/*.json` files use) — it
is direct evidence gathered to answer this issue's native-engine question,
recorded here in prose rather than as a committed structured report, since
`klt` itself cannot currently produce one for this PDK.

| Target | Rules executed | Violations | Runtime |
|---|---|---|---|
| Foundry macro (`gf180mcu_fd_ip_sram__sram64x8m8wm1.gds`) | 547 (incl. all 14 `S.*` SramCore rules) | **3**, all `NW.2b_MV` ("Min. Nwell Space (Outside DNWELL) [Different potential]: 1.7µm") | 167s |
| This repo's custom bitcell (`layout/bitcell/sram_bitcell_6t.gds`) | 547 (incl. all 14 `S.*` SramCore rules) | 21, across `NP.5a`, `PP.5a`, `DF.4c_LV`, `CO.6a`, `CO.6b` — **zero** `S.*` violations | 3.7s |

**This directly confirms Part A's hypothesis.** Against the foundry's own
macro, the true native deck — with the `SramCore`-relaxed thresholds
actually in effect — finds **zero** violations in the `comp.enclosing.
contact.1`/`CO.4`/`S.CO.4` rule family, versus the curated deck's 2010. The
3 real violations it does find (`NW.2b_MV`, an Nwell-spacing-at-different-
potential rule, likely at the macro's periphery/pad ring, not the bitcell
array) are in a rule family this survey's Part A did not identify as
`SramCore`-relaxed at all, so the curated deck's blind spot is not
implicated in them. Together with the `source_cell` attribution in B.1, this
is strong evidence that the curated deck's 2010-violation result against the
foundry bitcell is (almost entirely) an artifact of its missing `SramCore`
awareness, not a real defect in GlobalFoundries' own hardened macro.

Against this repo's *own* custom bitcell, the native run surfaces 21
violations the curated deck's own `coverage.rules_skipped` already disclosed
it cannot see (`NP.5a`/`PP.5a` are implant-overlap-of-gate rules — the
"implant spacing" category Part A confirms `SramCore` does not relax, so
these are not waived by drawing the marker; `DF.4c_LV`/`CO.6a`/`CO.6b` are
other unmodeled generic FEOL rules). **This is a new finding, out of this
issue's scope to act on** (`generate.py`'s drawn geometry is explicitly not
touched here) — filed as a separate, non-blocking follow-up:
[gf180-sram#103](https://github.com/2AMLogic/gf180-sram/issues/103) (see "Follow-up" below).

### B.3 — summary

| | Curated deck (`klt drc --deck gf180mcu`) | Native deck (direct `klayout -b -r`, full FEOL+BEOL+SramCore config) |
|---|---|---|
| Foundry macro | 2010 violations, all `comp.enclosing.contact.1` inside the bitcell array | 3 violations, all `NW.2b_MV`, unrelated to the bitcell array |
| This repo's custom bitcell | 0 violations (`layout/reports/drc-bitcell.json`) | 21 violations across 5 generic (non-SramCore) rule families |

## Conclusion for `spec/bitcell-decision.md`

The custom bitcell's DRC waiver/special-rule status, left "not yet
established" by `spec/bitcell-decision.md`, is now established as follows:
the custom bitcell draws **no** `SramCore` (108/5) marker and is checked
(both by the curated deck and, per B.2, by the real native deck) at generic
thresholds throughout — it neither claims nor benefits from any of the 12
relaxations Part A catalogs. It could legally go tighter under those
allowances (a valid, complete finding per this issue's acceptance criteria);
doing so is a re-layout, out of scope here. Separately, B.2's native run
found 21 real (non-SramCore-related) native-deck violations against the
custom bitcell that neither `klt`'s curated deck nor this repo's prior DRC
evidence could see — tracked as a follow-up, not fixed here.

## Follow-up

Filed: a non-blocking issue tracking the 21 native-deck violations found
against this repo's custom bitcell in B.2 (`NP.5a`, `PP.5a`, `DF.4c_LV`,
`CO.6a`, `CO.6b`) — investigate and, if real, fix in a future layout
revision; out of scope for this survey-and-comparison issue.

## Reproducing

- Part A's table: grep `libs.tech/klayout/tech/drc/rule_decks/*.drc` for
  `sramcore` and the cited rule ids, under any `gf180mcu{A,B,C,D}` PDK root
  (all four share the same `open_pdks` commit per `spec/bitcell-decision.md`).
- B.1: `klt drc --deck gf180mcu --format json <foundry-macro-gds>` — see
  `layout/reports/drc-foundry-bitcell.json`'s own `provenance` block for the
  exact `klt_version`/deck `content_hash`/input `content_hash` this table
  was produced from.
- B.2: not reproducible via `klt` alone today (that is the gap
  klayout-tools#1302 tracks) — reproduce via the direct `klayout -b -r`
  invocation shown above, after `python3 run_drc.py --macro_gen
  --variant=D --run_dir=<dir> --path=<any-file>` (the `--path` value is
  unused by `--macro_gen`; it is only there because `run_drc.py`'s CLI
  requires *a* value) to materialize `<dir>/main.drc`. `run_drc.py`
  requires the `docopt` PyPI package, not otherwise a dependency of this
  repo or of `klt`.

## References

- `layout/README.md` — "What this does and does not prove", the prose
  version of B.1's finding this document now backs with a run.
- `layout/reports/README.md` — the provenance convention
  `drc-foundry-bitcell.json` follows.
- `spec/bitcell-decision.md` — the "not yet established" language this
  document resolves.
- `spec/pdk-variant-decision.md` — pins `gf180mcuD` (`metal_top=11K`,
  `metal_level=5LM`, `mim_option=B`), the variant configuration B.2's direct
  invocation uses.
- [klayout-tools#1302](https://github.com/2AMLogic/klayout-tools/issues/1302)
  — the generic `--engine klayout` silent-no-op-on-missing-`-rd`-variables
  gap filed from B.2.
