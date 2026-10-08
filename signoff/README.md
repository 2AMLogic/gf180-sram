# signoff/ — the block's graded T1 state

This directory is the **verdict of record** for this block's gap to T1
("sim-validated", the `klt
signoff --manifest` tier-verdict report) — the state
[`spec/t1-checklist-reread-2026-08-22.md`](../spec/t1-checklist-reread-2026-08-22.md)
used to hand-carry. That re-read is retained unchanged as the dated
2026-08-22 audit snapshot it is; from the merge of the manifest onward, the
checklist state lives here and is re-derived, not re-read.

| File | What it is |
|---|---|
| `block-manifest.json` | The block manifest: this block's declared `kind` and, per T1 item, the evidence envelope cited behind it, each pinned to a `content_hash` of the committed artifact it grades. This is the file the fleet roll-up (2AMLogic/2am#956) consumes. |
| `signoff-report.json` | The committed `klt signoff --manifest block-manifest.json --format json` output — the graded per-item `met`/`unmet` table with a `reason` on every `unmet` row. Regenerate with `./signoff/regenerate.sh`. |
| `regenerate.sh` | Refreshes the item-8 evidence pin and re-grades the manifest with the pinned released klt, overwriting `signoff-report.json`. |
| *(retired)* `design-evidence-tiers.md` | Formerly a vendored copy of `klayout-tools`' checklist definition, passed via `--tiers-doc` because no released `klt` before 0.6.0 bundled the eleventh item (item 11, "Power delivery (structural)", klayout-tools#2025). Retired by issue #158: the pinned `klayout-tools==0.6.0` wheel bundles the eleven-item checklist itself (`t1_item_count: 11`, `build_t1_item_count: 11`), so grading passes no `--tiers-doc`. The report's `source_doc` is now the bundled `docs/design-evidence-tiers.md`, and `source_doc_content_hash` pins the bundled copy's content, so a checklist change inside the grading wheel shows up as report drift. |

CI (the `signoff` job in `.github/workflows/ci.yml`) re-grades the manifest on
every PR and requires byte-identical output to the committed
`signoff-report.json` — so a manifest citation whose underlying artifact has
since changed (layout GDS, reference netlist, PEX report, MC samples
document, characterization report) fails CI instead of silently rotting. The
fix is always the same one-liner: `./signoff/regenerate.sh`, then commit the
refreshed report.

## Grader distribution discipline

Regeneration and CI grade with the **released PyPI registry wheel** of
`klayout-tools==0.6.0`, never the `klt` already on this host. Under the same
version string, a `uv tool install git+...` snapshot or a full-checkout
install of the klayout-tools repo can grade differently. This was observed
live under the previous 0.5.0 pin: an 11-item-era full-repo install under
the name "0.5.0", and the v0.5.0 tag snapshot whose bundled checklist
predated item 11 entirely (filed upstream as klayout-tools#2216). The
released wheel reports the git tag it was built from. For the active pin,
`klt version --format json` reports `package_version: 0.6.0`,
`git_tag: v0.6.0`, `is_release: true` (git commit
`c622e8addb362491664d44ba4d717f354ca88bbd`, `grading_ruleset_id`
`sha256:0d8cc27c752ce25fc78499d4c280a4b472c460ac2dbcd38e56c9694485a17156`;
the report's own `build` block echoes the same identity). `regenerate.sh`
and `scripts/ci/check_signoff_freshness.py` both assert that identity
before grading. Keep the version pin in `regenerate.sh`, the CI job,
`check_signoff_freshness.py`, and the install hint in
`scripts/ci/check-signoff-freshness.sh` in sync (all say `0.6.0` today).

The 0.6.0 wheel bundles the full eleven-item checklist and item 11's
grading rules, so grading no longer passes a vendored `--tiers-doc`
(issue #158). Moving from 0.5.0 to 0.6.0 changed no verdict on items 1-10.
It did add disclosure fields to every citation: `input_verified` (true
when the grader re-hashed the envelope's own input artifact and it
matched) and, on item 3, the DRC `coverage` summary. `input_verified` is
disclosure only and no grading rule reads it. It is `true` on items 2, 3, 6
and 7. It is `null` on items 1, 4 and 10, whose LVS envelopes name a
layout netlist that lived in the mint's scratch directory, on items 5 and
9, whose minted sim envelope names no netlist, and on item 8, a generic
envelope. Item 6's `true` comes from repository-root grading: its yield
report's `samples` path is repo-relative and resolves from the working
directory.

## Block kind: `analog`

The manifest's `kind` is **`analog`** — the ratified decision recorded in
[`spec/block-kind-decision.md`](../spec/block-kind-decision.md) (Decided,
2026-08-19, resolving #19), which grades items 1, 2, 5, 7 and 11 against the
checklist's Analog column. The issue that requested this manifest
tentatively proposed `mixed-signal`; the ratified spec record wins over the
issue's proposal, exactly as that issue asked ("confirm it against the block
rather than taking it from this issue"). Nothing changes if and until a
digital-synthesized periphery is actually designed and that decision record
is amended.

## The verdict, row by row

`klt signoff` renders every T1 item either `met` (a cited, freshly-pinned,
passing check backs it) or `unmet` with a `reason`. Today's committed
verdict is **10/11 met** (graded by the released `klt` 0.6.0). Read it with its caveats: four of those ten rows
(items 1, 2, 9, 10) are `met` only because issue #126 re-cited them on
operator direction — the grader accepts a citation there without checking
that it bears on the item, so those four rows are *not* evidence for their
items (see the note after the table). Item 11 is unmet because the cited
ERC report is an abridged envelope the grader cannot recognize, and behind
that because the row still lacks the `ties[]` and compound ERC + LVS
evidence 0.6.0 grades it on (see its row). Without the
operator-directed re-citations the reading is 6/11. (Historical: when this
directory was created, a mostly-`unmet` mechanical reading was the expected
and accepted outcome, because the checklist moved on 2026-09-17 and no
hand-read survived that change.)

| Item | Verdict today | Why — and what would change it |
|---|---|---|
| 1 — Design sources | **met** (cited by issue #126, operator-directed) | Cites `layout/reports/lvs-array.json` (`status: match`), the one native envelope whose reference side is this item's derived netlist `design/netlist/sram_256x32_array.spice`. `klt signoff` (0.5.0, and still 0.6.0) grades this item on *some* passing native envelope being cited, not on topical relevance, and rejects `kind: generic` here (only item 8 accepts it) — so the citation satisfies the grader and does not itself prove the item; the substance is the human audit: [`design/README.md`](../design/README.md) (bitcell + array schematics, generator, byte-identical regeneration) and [`layout/README.md`](../layout/README.md). |
| 2 — Layout | **met** (cited by issue #126, operator-directed) | Cites `layout/reports/drc-array.json`, whose `provenance.input.content_hash` pins the committed array GDS. `klt signoff` (0.5.0, and still 0.6.0) grades this item on *some* passing native envelope being cited, not on topical relevance, and rejects `kind: generic` here (only item 8 accepts it) — so the citation satisfies the grader and does not itself prove the item; the substance is the human audit: committed bitcell + array GDS, deterministically regenerated by `./layout/verify.sh` step 1. |
| 3 — DRC clean | **met** | Cites `layout/reports/drc-array.json` — `status: clean` over the full 256×32 array, its `provenance.input.content_hash` pinning the committed array GDS byte-for-byte. Coverage disclosure, read from the report rather than assumed: the curated deck checked 9 of its 18 layers against this layout; 4 in-stream layers carry no rules (`31/0`, `32/0`, `34/10`, `42/10`) and 19 rules were skipped — and the curated deck cannot see the 5 rule families the PDK's native deck flags on the foundry's own bitcell (issue #103, `layout/reports/sram-rule-survey.md`). A "clean" from a deck with disclosed holes is disclosed here, not hidden. |
| 4 — LVS clean | **met** | Cites `layout/reports/lvs-array.json` re-minted by issue #128 under a post-klayout-tools#1969 `klt` (that records LVS `provenance.input`): `status: match`, 49,152/49,152 devices, 16,706/16,706 nets against the committed array netlist, with the manifest's pin now the report's own `provenance.input.content_hash` (the extracted layout side's digest — the same content `environment.layout_sha256` records, which the reference netlist's `environment.reference_sha256` corroborates independently). The bitcell LVS report was re-minted the same way (`layout/reports/lvs-bitcell.json`, `status: match`). Disclosed: the pin is recorded by the minting run, not re-derived by the grader, and `klt lvs --check` cannot re-hash the layout side of a committed report whose layout netlist lived in the mint's scratch dir — same class as the DRC deck-hash pin; the extract + compare are reproducible via `layout/reports/generate.sh` steps 3-4. |
| 5 — Full corner verification | **met** | Cites `sim/signoff-sim-envelope.json` — the minted `klt sim`-shaped envelope issue #128 asked for, transcribed verbatim from the same five append-only corner records [`sim/signoff-summary.md`](../sim/signoff-summary.md) rolls up: `status: pass` over all 27 corners, per-row worst-case (binding) corner recorded, the manifest pin equal to its `provenance.input.content_hash` (the sha256 of those five record files). It is **a minted envelope, not a live `klt sim` run** — the envelope's own `mint` block discloses this, names its five sources by path and sha256, and states the structural reason: this block's SNM and write-trip methodologies cannot be expressed as ngspice `.meas` cards over a bare circuit body, so the ratified sweep runner cannot be hosted by the verb. A mint is weaker evidence than a first-party sweep would be; the disclosure cost is paid in `sim/README.md` § "The minted `klt sim` envelope" and in CI check 6, which keeps the envelope byte-identical to `sim/lib/mint_sim_envelope.py`'s output. If a `klt sim` release ever hosts these methodologies, re-run under the verb and retire the mint. |
| 6 — Monte Carlo evidence | **met** | Cites the read-SNM `klt yield` report re-minted by issue #128 with the #109-fixed harness (`sim/read-snm/mc/yield-reports/20260921-124232-cf5e975.json`, `status: reported` — still no `target_yield`, per `spec/target-yield-decision.md`). Its `samples` field is now repo-relative (`sim/read-snm/mc/samples/20260921-124232-cf5e975.json`), so the grader re-locates and re-hashes the samples document and the manifest pin verifies. Read SNM is cited as the most binding of the three statistical rows (its worst-case corner holds the smallest margin, 0.215 V vs hold SNM's 0.930 V and write margin's 1.641 V); the manifest's evidence shape holds one citation per item until `klt signoff` accepts compound per-item citations. All three campaigns were re-run with the same seeds, sample counts, negative controls, and corner subsets as their committed 2026-08-17 predecessors — per-instance mismatch draws differ (host ngspice RNG), and the harness-fidelity control pins each campaign to the deterministic 27-corner records exactly (`PINNED (identical)` at every corner, reproducibility preserved by recorded seeds): `sim/read-snm/mc/records/20260921-124232-cf5e975.md`, `sim/hold-snm/mc/records/20260921-124534-cf5e975.md`, `sim/write-margin/mc/records/20260921-124804-cf5e975.md`. The old yield reports stay committed (append-only) with their superseded, still-correct statistics. |
| 7 — Post-layout verification | **met** | Cites `sim/pex/access-time/reports/read-access-time.pex.json` — `klt pex`, `status: pass`, 27/27 corners, read access time schematic-vs-extracted, `provenance.input.content_hash` pinning the committed bitcell GDS byte-for-byte. Item 7 accepts a `klt pex` report and nothing else. Disclosed: the envelope predates `klt pex`'s `body_bias` block, so the citation reports no body-bias statement at all (never "every device body was biased"); and read/hold SNM have no PEX-compatible path for a structural reason Seevinck's method imposes — fully investigated and disclosed in [`sim/pex/README.md`](../sim/pex/README.md), needing a new isolated-inverter layout deliverable rather than a re-verification. |
| 8 — Characterization report | **met** | Cites `measurements/characterization.signoff.json` — a hand-rolled `kind: generic` envelope (the one item this wrapper is allowed to satisfy) asserting the aggregated [`characterization-report.md`](../measurements/characterization-report.md): per-spec-row values across all 27 corners plus the MC/yield summaries, with the envelope's `provenance.input.content_hash` pinning that report and CI's existing check 5 keeping it byte-identical to `measurements/generate_report.py`'s output. |
| 9 — Testbenches shipped | **met** (cited by issue #126, operator-directed) | Cites `sim/signoff-sim-envelope.json`, minted from the committed testbenches' corner records. `klt signoff` (0.5.0, and still 0.6.0) grades this item on *some* passing native envelope being cited, not on topical relevance, and rejects `kind: generic` here (only item 8 accepts it) — so the citation satisfies the grader and does not itself prove the item; the substance is the human audit: [`sim/README.md`](../sim/README.md) inventories all five committed testbenches with the pinned PDK revision and cold-start invocation. |
| 10 — Repo hygiene | **met** (cited by issue #126, operator-directed) | Cites `layout/reports/lvs-bitcell.json` (`status: match`), which has **no topical bearing** on hygiene — no `klt` envelope does; it is cited only so the grader renders a verdict. `klt signoff` (0.5.0, and still 0.6.0) grades this item on *some* passing native envelope being cited, not on topical relevance, and rejects `kind: generic` here (only item 8 accepts it) — so the citation satisfies the grader and does not itself prove the item; the substance is the human audit: this README, the root README, `LICENSE`, and `.github/workflows/ci.yml` running on every PR and push. |
| 11 — Power delivery (structural) | unmet `unrecognized_envelope` (now graded by the pinned build: `graded_by_build: true`) | **The evidence exists** — committed by issue #124: the supply spec `layout/sram_256x32/erc-supply-spec.json` and the `klt erc` report `layout/reports/erc-array-supply.json` (`erc_finding_count: 0` — zero `erc.unconnected_net`, zero `erc.supply_short` naming VDD/VSS, i.e. each declared supply resolves to exactly one electrical island; the check proven to compute via a negative control; input `content_hash` matching the committed array GDS; `erc.missing_tie` not computed, disclosed with its standing-in well-tie evidence — item 4's own `lvs-array.json` carries VDD/VSS in `net_correspondence` against the SPICE reference — full reading in `layout/reports/README.md` § "Item 11"). The row is **cited** in the manifest (pinned to the same array-GDS `content_hash` item 3's citation pins). Under the old 0.5.0 pin it rendered `unrecognized_envelope` because that wheel predated item 11's grading rules (klayout-tools#2057). **Under the 0.6.0 pin it still renders `unrecognized_envelope`, for a different, evidence-side reason**: 0.6.0 recognizes a `klt erc` envelope by its top-level `gates` list plus `gate_role`, and the committed report is abridged — its `_note` records that `gates[]` (~29.7 MB at this array size) was omitted, just as `extract-array.json` omits `devices[]`/`nets[]`. Without `gates`, the grader cannot classify the envelope at all. A throwaway probe (not committed) that only restored an empty `gates` list renders `wrong_kind`: the manifest cites the ERC report alone, and 0.6.0 grades item 11's Analog column on an ERC report together with an LVS report. The row's citation was not changed to hide this. Turning the row `met` needs: (i) ~~a **released** `klt` that grades item 11, adopted per this directory's grading discipline~~ (done by issue #158: `klayout-tools==0.6.0`, all pins moved together, vendored checklist and `--tiers-doc` retired); (ii) the supply spec **regaining `ties[]`**, minted under the post-#2169-fix `klt`: the false-`erc.supply_short` ties[] blocker is fixed upstream (klayout-tools#2186, 2026-09-20 — tie conduction scoped to tap sites, the tie graph isolated) and the checklist's item 11 demands zero `erc.missing_tie` *from a tie the run actually checked*, rendering a tie-less spec `supply_spec_incomplete`; #124's committed evidence deliberately omits `ties[]` because it was minted under the pre-fix `klt`, where declaring them collapsed the supply read (the spec's `_comment` records the decision), so a re-mint with a checked `ties[]` (the `Nwell`/`Comp∩Nplus` VDD tap is declarable; gf180mcu's substrate is an undrawn p-well, so a substrate-tie entry may need `ties[].well_layer: null` + `well_boxes`, klayout-tools#2255) replaces that recorded gap. That re-mint must also commit an ERC envelope the grader can classify, i.e. one that keeps the top-level `gates` list; (iii) ~~issue #128's LVS re-mint with input provenance~~ (landed: item 4 is `met` as of 2026-09-21), so item 4's own LVS report — the analog column's supplies-in-`net_correspondence` half — can be cited beside the ERC report once the manifest carries compound item-11 evidence. Issue #159 covers (ii) and the compound citation. |

**Items 1, 2, 9 and 10: what `met` means here.** Until 2026-10-02 these
items were deliberately left uncited. No `klt` verb binds to them, and
`klt signoff` 0.5.0 accepts *any* passing native envelope for them without
checking topical relevance, and 0.6.0 still does. It also rejects `kind: generic` for them (only
item 8 accepts it). So the only way to turn them green was to cite something
the grader cannot judge, and this directory declined to do that. On
2026-10-02 the operator granted bronze (T1) on the human-audited record
([`spec/t1-grant-2026-10-02.md`](../spec/t1-grant-2026-10-02.md)) and, in
issue #126, directed that these four items be re-cited so the mechanical
verdict tracks the granted tier. They are now cited. For these four rows,
`met` means only that "a passing native envelope is cited". **It is not
evidence for the item.** Items 1, 2 and 9 cite related envelopes. Item 10's
citation (`lvs-bitcell.json`) has **no topical bearing** on repo hygiene and
is a placeholder. For all four, the substance is still the human audit
named in each row. When a released `klt` offers a kind that can actually
evidence these items, re-cite them to that and retire these placeholder
citations. The tool gap is tracked upstream at klayout-tools#2718.
