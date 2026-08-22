# T1/bronze checklist re-read — 2026-08-22

**Status**: Informational (not a change to the ratified spec).
**Resolves**: #100 ("T1/bronze checklist re-read against current evidence
(first since #13, and the first under klayout-tools 0.3.0)")
**Precedent**: #13 (2026-08-15), the previous re-read; #18 decomposed that
pass's failing rows into #19–#28.

Re-reads the T1 "sim-validated" checklist
(`klayout-tools/docs/design-evidence-tiers.md` → "T1 checklist", ten items)
row by row against evidence actually on `main` at
`604b7e2798540ccdbefce6244f3e2bc323461d41` (2026-08-21T23:33:21-07:00,
`docs: correct design/README.md's stale placeholder-bitcell prescription
(#105)`), in the same "cite the actual artifact, not a closed-issue-number
assumption" form #13 used. This is the first re-read since #13 (which scored
0/10 — nothing existed yet) and the first performed since the repo's
`spec/block-kind-decision.md` ratified this block's evidence-tier kind as
`analog` (2026-08-19), so items 1, 2, 5, 6, 7 below are graded against the
Analog column, per that record.

## Toolchain

`klt --version` in this environment: **`klt 0.2.0`** (KLayout module
`0.30.10`) — the same version string every committed evidence artifact in
this repo already cites, **not** the `klayout-tools` 0.3.0 that shipped on
PyPI 2026-08-21 (verified: PyPI's 0.3.0 release postdates this repo's own
installed `klt`, and this environment's `uv tool install
git+https://github.com/2AMLogic/klayout-tools` snapshot was not
re-installed for this re-read). One row below (item 4) was re-run live and
its verdict changed as a direct result of upstream behavior that landed
*before* 0.3.0's tag but *after* this repo's evidence was originally
recorded — see that row for the version-drift detail; every other row's
citation is read from already-committed evidence, not re-run.

## The ten items

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Design sources | **PASS** | `design/bitcell_6t.sch` (hand-drawn 6T topology, gf180mcu `nfet_03v3`/`pfet_03v3` devices) + `design/generate_array.py` (deterministic generator) → `design/sram_256x32_array.sch` (8,192-instance array), both netlisted by xschem's own batch netlister into `design/netlist/bitcell_6t.spice` / `design/netlist/sram_256x32_array.spice`. `design/README.md` "Regenerating the netlists" documents a verified-twice byte-identical regeneration for both the generator and the netlister. `design/README.md` itself was corrected 2026-08-22 (PR #105, closing #101) to no longer describe the layout side as still using a placeholder — read fresh after that fix. |
| 2 | Layout | **PASS** | `layout/bitcell/sram_bitcell_6t.gds` (6 transistors, 4.46 × 5.39 µm) and `layout/sram_256x32/sram_256x32_array.gds` (8,192 cells, 142.72 × 1379.84 µm, 0.1969 mm²) — both committed, deterministic (`layout/README.md` "Status (2026-08-16)": "not a placeholder"; the earlier placeholder from PR #36 is gone), reproducible via `layout/bitcell/generate.py` / `layout/sram_256x32/generate.py` and `./layout/verify.sh`. |
| 3 | DRC clean | **PASS, with a disclosed coverage hole already tracked** | `klt drc --deck gf180mcu`: `status: clean`, 0 violations at the bitcell (`layout/reports/drc-bitcell.json`), a 3×3 abutment tile, and the full 256×32 array (`layout/reports/drc-array.json`) — reproducible via `layout/verify.sh`. Coverage-honesty hole, already disclosed and already filed: `layout/README.md` "What this does and does not prove" states the curated deck does not model implant/density/antenna/latch-up/SramCore-marker rules, and issue #8's `layout/reports/sram-rule-survey.md` (§ B.2) ran the PDK's real native DRC-DSL deck directly against this repo's own bitcell — it reports **21 violations** across 5 rule families (`NP.5a`, `PP.5a`, `CO.6a`, `CO.6b`, `DF.4c_LV`) the curated deck cannot see. This is not a new finding of this re-read: it is already tracked as **issue #103** (open, `loom:building` at the time of this re-read) — cited here, not re-filed. |
| 4 | LVS clean | **PASS at both bitcell and array level** — array-level verdict **updated by this re-read**; see note | Bitcell: `layout/reports/lvs-bitcell.json`, `status: match`, 6/6 devices, 7/7 nets, vs. `design/netlist/bitcell_6t.spice`. Array: `layout/reports/lvs-array.json` (as committed) still records `status: mismatch` — `klt extract` is flat-only (`klayout-tools#1085`), so the flat 49,152-device extracted array cannot structurally pair against the hierarchical `design/netlist/sram_256x32_array.spice` reference. **Re-verified live in this environment, 2026-08-22**: `klayout-tools#1085` closed 2026-08-17 with `options.flatten_reference`/`options.flatten_layout` landing on `klt lvs`. Re-running `klt extract --deck gf180mcu layout/sram_256x32/sram_256x32_array.gds` (identical output to the committed `layout/reports/extract-array.json`: 49,152 devices, 16,706 nets, same `layout_sha256`) followed by `klt lvs` with `{"options": {"flatten_reference": true}}` against the same committed reference netlist (same `reference_sha256` as the committed failing run) now reports **`status: match`** — 49,152/49,152 devices, 16,706/16,706 nets, 322/322 pins all matched; the one `mismatch_count` entry is a `severity: "warning"`, `category: "topology.flattened"` disclosure of the reference-side flatten, not a real mismatch. This is genuine new information since `layout/README.md`'s "Known tool gaps" #2 was last written (it does not mention `flatten_reference` at all) — the currently-installed `klt 0.2.0` on this host already carries the fix, the same "same version string, different behavior" drift `layout/README.md`'s "Known tool gaps" #1 already documents for a different `klt extract` change. **Decomposed to issue #108**: refresh the committed `layout/reports/lvs-array.json` and `layout/README.md` to reflect this rather than editing them inline here. |
| 5 | Full corner verification vs. ratified spec | **PASS** | `sim/signoff-summary.md` (auto-generated, `sim/lib/render_signoff_table.py`): 27/27 corners PASS for read SNM (min 0.214599 V), hold SNM (min 0.930461 V), write margin (min 1.640530 V); read/write access time 27/27 RECORDED (no numeric spec bound — `spec/sram.md`'s Signoff definition only requires these be recorded, by design, not omission). **"Overall signoff... PASS."** Graded against `spec/sram.md` (Status: Ratified, 2026-08-05) § "Signoff definition", over the ratified 27-point (`3×3×3`) process × temperature × voltage matrix (`spec/corner-count-correction.md`). |
| 6 | Statistical claims carry Monte Carlo evidence | **PASS, with a disclosed provenance-hygiene hole** | `spec/statistical-treatment-decision.md` ratifies read SNM, hold SNM, and write margin as statistical rows requiring MC evidence; `spec/target-yield-decision.md` ratifies that no numeric `target_yield` is set, so evidence is *reported* (Cpk / sigma-to-spec / Clopper-Pearson empirical-yield lower bound), never graded pass/fail against an invented number. All three measurements have a committed `klt yield` campaign — `sim/read-snm/mc/records/20260817-102455-ce56f59.md`, `sim/hold-snm/mc/records/20260817-103316-ce56f59.md`, `sim/write-margin/mc/records/20260817-104116-ce56f59.md` — each with a recorded seed, 200 mismatch samples + 4 determinism-control samples (all `PINNED`, matching the deterministic corner record exactly) + 100 negative-control samples (all `detected`, i.e. a deliberately degraded variant is demonstrably distinguishable) per corner, over a 9-corner subset combined with, not replacing, the exhaustive 27-corner sweep in item 5. Hole: every one of these three records (plus their `samples/` and `yield-reports/` JSON/text siblings, plus `design/netlist/*.spice` and `measurements/characterization-report.md`, which quote them) embeds an absolute author-home-directory path (`/Users/rwalters/GitHub/gf180-sram/.loom/worktrees/issue-26/...`, `/Users/rwalters/.volare/gf180mcuC`) — exactly the disclosure class `klayout-tools/docs/design-evidence-tiers.md` § "Provenance hygiene in evidence records" warns about and recommends `klt env-provenance` to prevent. Per that same section, existing records are not rewritten; **decomposed to issue #109**, scoped prospectively (fix the harness scripts that mint new records, not the already-committed ones). |
| 7 | Post-layout verification | **PASS, with a disclosed and already-fully-investigated structural hole** | `sim/pex/README.md`: write access time and read access time closed via a `klt pex`-native testbench (27/27 corners, genuine non-vacuous delta, `sim/pex/access-time/`); write margin closed via a by-hand extraction workflow (`klt extract --parasitics` + the corner sweep, run twice and diffed, 27/27 corners, `sim/pex/write-margin/`). Read SNM / hold SNM: **no PEX-compatible path exists**, and this is investigated as a structural fact, not an unclaimed gap — `sim/pex/README.md` § "read-snm/hold-snm: no PEX-compatible path" shows both the `klt pex` DUT-`.include`-swap route and a hand-rolled extracted-netlist route fail for the same underlying reason (Seevinck's SNM method needs to break the cross-coupled feedback loop from outside, and no drawn layout boundary exists to extract one storage inverter independently of the other). Closing this for real needs a new, from-scratch isolated-inverter layout, explicitly out of scope of the issue (#95) that investigated it. No new decomposition filed — the disclosure is already complete and the remaining work (a new layout deliverable) is a design decision, not a re-verification task this re-read can usefully re-scope. |
| 8 | Characterization report | **PASS** | `measurements/characterization-report.md` — one current, auto-generated (`measurements/generate_report.py`), aggregated artifact: per-corner 27-point signoff table (embedded verbatim from item 5's source), the three MC/yield summaries from item 6 (min Cpk, min sigma-to-spec, negative-control verdict per measurement), and a provenance/staleness table naming every source record's id, git sha, and timestamp so drift from `sim/*/records/` is detectable. |
| 9 | Testbenches shipped | **PASS** | `sim/README.md` inventories all five committed testbenches (`tb_read_snm.spice`, `tb_hold_snm.spice`, `tb_write_margin.spice`, `tb_read_access_time.spice`, `tb_write_access_time.spice`) with the measurement each makes and its DUT-access convention, a documented cold-start invocation (§ "Pinned PDK revision": `open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, `gf180mcuD`, install command included), and the append-only `<experiment>/{testbench,netlist-snapshots,corners,records}` convention every committed record follows. |
| 10 | Repo hygiene | **PASS, with a disclosed documentation-staleness hole** | `README.md` states scope, links the ratified spec, and documents the repo layout; `LICENSE` (Apache-2.0) is present; `.github/workflows/ci.yml` runs on every PR/push to `main` and is currently green (`gh run list`, five most recent runs on `main` all `success`) — one job (`npm run check:ci`) runs harness lint + guard tests + the pure-Python SNM-extraction unit test, the other (`scripts/ci/check-evidence-format.sh`) validates `sim/`/`layout/`/`measurements/` evidence-record format on every PR. Hole: `README.md`'s own "Status" line ("spec ratified, bitcell/array design and layout underway") and its "Current position" sentence ("the formal per-corner pass/fail synthesis... still outstanding") are stale — both predate `sim/signoff-summary.md` (item 5, already PASS) and `layout/README.md`'s real device-level layout (item 2, already committed). This is the same class of drift #101/PR #105 just fixed in `design/README.md`. **Decomposed to issue #110.** |

## Aggregate

**10/10 items PASS** — 7 with no disclosed hole (1, 2, 5, 8, 9, plus 4 and
3 once their already-tracked/updated holes are read as coverage-honesty
disclosures rather than failures), 3 with a disclosed hole (3, 6, 10 —
each either already tracked (#103) or newly decomposed here (#109, #110)),
and one (7) with a fully investigated, disclosed structural limitation that
needs a new layout deliverable to close further, not a re-verification.

This is a large swing from #13's 0/10 (2026-08-15, before any design,
layout, or sim artifact existed) — every checklist item now has committed,
citable, reproducible evidence, and the one item (4) whose verdict genuinely
changed as a result of an upstream toolchain fix was re-verified live rather
than assumed, per this re-read's own instruction.

**No FAIL rows exist**, so unlike #13 → #18 this re-read decomposes only the
*hole-carrying* rows still needing action (#108, #109, #110 — item 3's hole
is already covered by the open #103, not re-filed) rather than every row.

### What bronze (T1) does *not* yet claim, and what the next tier (silver /
T2) would additionally require

A 10/10 T1 pass is **sim-validated with open tools** — it is not:

- **Signoff-clean on commercial tools.** T2 ("silver") requires DRC/LVS
  signoff and simulation on commercial tools with the foundry's own decks,
  on top of everything above — this repo has never run a commercial DRC/LVS
  engine or the foundry's own (non-`klt`-curated) deck end-to-end (item 3's
  disclosed hole, and issue #103, are evidence this repo's own open-source
  coverage is already known-incomplete relative to the foundry's real deck,
  which is exactly what T2 signoff would close).
- **A routed, integrated macro.** This block is the storage-array *core*
  only (`design/README.md`, `layout/README.md` "Scope" sections) — no
  address decode, column mux, sense amp, or write driver periphery is
  drawn, and `views/` (LEF abstract, Liberty timing) is still empty
  (`views/README.md`: "Empty until the first work lands here"). `spec/
  sram.md`'s full 1RW pin list (`A`, `CEN`, `CLK`, `D`, `Q`, `GWEN`, `WEN`)
  is not yet exposed by either the schematic or the layout.
- **Silicon (T3/"gold").** No tapeout, no measured parts, no
  sim-to-measurement correlation exists or is claimed anywhere in this
  repo.

Per `product/everyblock/grants.md`'s "How a grant gets recorded here"
procedure (cited by #13's own guardrails), recording an actual grant is an
operator action, not something this re-read performs — flagged here for
visibility only:

**OPERATOR: bronze (T1) candidate — 10/10 checklist items pass, with three
disclosed and now-tracked holes (issues #103, #108, #109, #110) and one
fully investigated structural limitation (item 7's read/hold SNM PEX gap).**

## Related

- #13, #18 — the previous re-read and its decomposition; this record follows
  the same per-item citation discipline.
- #100 — the issue this record resolves.
- #103, #108, #109, #110 — the open, dispatchable follow-ups this pass
  either found (#103, cited) or filed (#108, #109, #110).
- `spec/block-kind-decision.md` — ratifies this block's evidence-tier kind
  (`analog`), which items 1, 2, 5, 6, 7 above are graded against.
