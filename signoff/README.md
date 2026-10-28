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
| *(retired)* `design-evidence-tiers.md` | Formerly a vendored copy of `klayout-tools`' checklist definition, passed via `--tiers-doc` because no released `klt` before 0.6.0 bundled the eleventh item (item 11, "Power delivery (structural)", klayout-tools#2025). Retired by issue #158: the then-pinned `klayout-tools==0.6.0` wheel (now 0.7.0, which bundles it too) bundles the eleven-item checklist itself (`t1_item_count: 11`, `build_t1_item_count: 11`), so grading passes no `--tiers-doc`. The report's `source_doc` is now the bundled `docs/design-evidence-tiers.md`, and `source_doc_content_hash` pins the bundled copy's content, so a checklist change inside the grading wheel shows up as report drift. |

CI (the `signoff` job in `.github/workflows/ci.yml`) re-grades the manifest on
every PR and requires byte-identical output to the committed
`signoff-report.json` — so a manifest citation whose underlying artifact has
since changed (layout GDS, reference netlist, PEX report, MC samples
document, characterization report) fails CI instead of silently rotting. The
fix is always the same one-liner: `./signoff/regenerate.sh`, then commit the
refreshed report.

## Grader distribution discipline

Regeneration and CI grade with the **released PyPI registry wheel** of
`klayout-tools==0.8.0`, never the `klt` already on this host. Under the same
version string, a `uv tool install git+...` snapshot or a full-checkout
install of the klayout-tools repo can grade differently. This was observed
live under the previous 0.5.0 pin: an 11-item-era full-repo install under
the name "0.5.0", and the v0.5.0 tag snapshot whose bundled checklist
predated item 11 entirely (filed upstream as klayout-tools#2216). The
released wheel reports the git tag it was built from. For the active pin,
`klt version --format json` reports `package_version: 0.8.0`,
`git_tag: v0.8.0`, `is_release: true` (git commit
`c572046be644e0407f693f2410f3abb799d68a3a`, `grading_ruleset_id`
`sha256:46c446d84423b7399ee1cf957b3d49801ae4f42a0bda53da92f435776cf977c4`;
the report's own `build` block echoes the same identity). `regenerate.sh`
and `scripts/ci/check_signoff_freshness.py` both assert that identity
before grading. Keep the version pin in `regenerate.sh`, the CI job,
`check_signoff_freshness.py`, and the install hint in
`scripts/ci/check-signoff-freshness.sh` in sync (all say `0.8.0` today).

Re-grade on 0.8.0 (issue #275): the pin moved from 0.7.0 to 0.8.0 and the
record was regenerated with no evidence artifact or manifest edited. **The
verdict changed: 11/11 -> 8/11 met.** Items 1 (Design sources), 9 (Testbenches
shipped) and 10 (Repo hygiene) now grade `unmet` / `wrong_kind`: the 0.8.0
grader no longer accepts the placeholder citations (the native envelopes
issue #126 cited there) for those rows. Items 2-8 and 11 stay `met`, with
citation fields re-rendered. The spec was not relaxed and no citation was
swapped to restore 11/11; choosing evidence of the right kind for items 1, 9
and 10 is tracked as a follow-up issue.

Re-cite on 0.8.0 (issue #277): items 1, 9 and 10 now cite artifact-anchored
`kind: generic` wrappers (`design/design.signoff.json`,
`sim/testbenches.signoff.json`, `repo-hygiene.signoff.json`), each declaring
its `t1_item` and pinning a named file set through `provenance.input.paths`;
`./signoff/regenerate.sh` refreshes those pins. The verdict is back to 11/11
met, tier T1. Item 2 still cites a native placeholder envelope (see below).

Re-grade on 0.7.0 (issue #194): the pin moved from 0.6.0 to 0.7.0 and the
record was regenerated with no evidence artifact edited. **No row changed
status or reason**; the verdict stays 11/11 met, tier T1. What did change in
the record: `build` (0.7.0 identity above), `source_doc_content_hash` (the
bundled checklist moved to `sha256:4c67ffc5...` from `sha256:63eeec72...`),
the checklist prose carried in the item 6, 8 and 11 rows' `text`, and two
disclosure fields the 0.7.0 grader newly echoes -- `yield_campaign` on item
6's citation (`sample_size: sufficient`, `negative_control: detected`, no
undersized or undetected measurements) and `power_delivery.supply_unlabelled_islands`
on item 11's (`{}`: the cited ERC supply spec declares no `nets[].roles`, so
the severed-rail question is "not measured", not "zero"). Item 6's blocker
(#160, missing native `yield` extension) is unchanged and out of scope here.

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
verdict is **11/11 met, tier T1** (graded by the released `klt` 0.8.0; see "Re-grade on 0.8.0" and "Re-cite on 0.8.0" above). Read it with its caveats: item 2 is `met` only because issue #126 re-cited it on
operator direction -- it is still a placeholder citation: the grader accepts a passing envelope there without checking
that it bears on the item, so that row is *not* evidence for its
item (see the note after the table). Items 1, 9 and 10 are `met` through
artifact-anchored generic wrappers (issue #277): the grader checks that the
named files re-hash to the pins, not that their content bears on the item, so
the wrapper summaries state only what the files are and what the pins do not
prove. Item 11 became `met` with issue #159 (the `ties[]` re-mint and the
compound ERC + LVS citation, see its row). (Historical: when this
directory was created, a mostly-`unmet` mechanical reading was the expected
and accepted outcome, because the checklist moved on 2026-09-17 and no
hand-read survived that change.)

| Item | Verdict today | Why — and what would change it |
|---|---|---|
| 1 — Design sources | **met** (issue #277) | Cites `design/design.signoff.json`, a `kind: generic`, `t1_item: 1` wrapper whose `provenance.input.paths` pins `design/README.md`, `design/generate_array.py`, the bitcell and 256×32 array schematics, and the netlists derived from them (`design/netlist/bitcell_6t.spice`, `sram_256x32_array.spice`). Not proven by the grader or CI: that the netlists were regenerated from the schematics -- `design/README.md` documents the commands and a hand-verified freshness check; CI does not re-run xschem. |
| 2 — Layout | **met** (cited by issue #126, operator-directed) | Cites `layout/reports/drc-array.json`, whose `provenance.input.content_hash` pins the committed array GDS. `klt signoff` (0.5.0, and still 0.6.0) grades this item on *some* passing native envelope being cited, not on topical relevance, and rejects `kind: generic` here (only item 8 accepts it) — so the citation satisfies the grader and does not itself prove the item; the substance is the human audit: committed bitcell + array GDS, deterministically regenerated by `./layout/verify.sh` step 1. |
| 3 — DRC clean | **met** | Cites `layout/reports/drc-array.json` — `status: clean` over the full 256×32 array, its `provenance.input.content_hash` pinning the committed array GDS byte-for-byte. Coverage disclosure, read from the report rather than assumed: the curated deck checked 9 of its 18 layers against this layout; 4 in-stream layers carry no rules (`31/0`, `32/0`, `34/10`, `42/10`) and 19 rules were skipped — and the curated deck cannot see the 5 rule families the PDK's native deck flags on the foundry's own bitcell (issue #103, `layout/reports/sram-rule-survey.md`). A "clean" from a deck with disclosed holes is disclosed here, not hidden. |
| 4 — LVS clean | **met** | Cites `layout/reports/lvs-array.json` re-minted by issue #128 under a post-klayout-tools#1969 `klt` (that records LVS `provenance.input`): `status: match`, 49,152/49,152 devices, 16,706/16,706 nets against the committed array netlist, with the manifest's pin now the report's own `provenance.input.content_hash` (the extracted layout side's digest — the same content `environment.layout_sha256` records, which the reference netlist's `environment.reference_sha256` corroborates independently). The bitcell LVS report was re-minted the same way (`layout/reports/lvs-bitcell.json`, `status: match`). Disclosed: the pin is recorded by the minting run, not re-derived by the grader, and `klt lvs --check` cannot re-hash the layout side of a committed report whose layout netlist lived in the mint's scratch dir — same class as the DRC deck-hash pin; the extract + compare are reproducible via `layout/reports/generate.sh` steps 3-4. |
| 5 — Full corner verification | **met** | Cites `sim/signoff-sim-envelope.json` — the minted `klt sim`-shaped envelope issue #128 asked for, transcribed verbatim from the same five append-only corner records [`sim/signoff-summary.md`](../sim/signoff-summary.md) rolls up: `status: pass` over all 27 corners, per-row worst-case (binding) corner recorded, the manifest pin equal to its `provenance.input.content_hash` (the sha256 of those five record files). It is **a minted envelope, not a live `klt sim` run** — the envelope's own `mint` block discloses this, names its five sources by path and sha256, and states the structural reason: this block's SNM and write-trip methodologies cannot be expressed as ngspice `.meas` cards over a bare circuit body, so the ratified sweep runner cannot be hosted by the verb. A mint is weaker evidence than a first-party sweep would be; the disclosure cost is paid in `sim/README.md` § "The minted `klt sim` envelope" and in CI check 6, which keeps the envelope byte-identical to `sim/lib/mint_sim_envelope.py`'s output. If a `klt sim` release ever hosts these methodologies, re-run under the verb and retire the mint. |
| 6 — Monte Carlo evidence | **met** | Cites the read-SNM `klt yield` report re-minted by issue #128 with the #109-fixed harness (`sim/read-snm/mc/yield-reports/20260921-124232-cf5e975.json`, `status: reported` — still no `target_yield`, per `spec/target-yield-decision.md`). Its `samples` field is now repo-relative (`sim/read-snm/mc/samples/20260921-124232-cf5e975.json`), so the grader re-locates and re-hashes the samples document and the manifest pin verifies. Read SNM is cited as the most binding of the three statistical rows (its worst-case corner holds the smallest margin, 0.215 V vs hold SNM's 0.930 V and write margin's 1.641 V); the manifest's evidence shape holds one citation per item until `klt signoff` accepts compound per-item citations. All three campaigns were re-run with the same seeds, sample counts, negative controls, and corner subsets as their committed 2026-08-17 predecessors — per-instance mismatch draws differ (host ngspice RNG), and the harness-fidelity control pins each campaign to the deterministic 27-corner records exactly (`PINNED (identical)` at every corner, reproducibility preserved by recorded seeds): `sim/read-snm/mc/records/20260921-124232-cf5e975.md`, `sim/hold-snm/mc/records/20260921-124534-cf5e975.md`, `sim/write-margin/mc/records/20260921-124804-cf5e975.md`. The old yield reports stay committed (append-only) with their superseded, still-correct statistics. |
| 7 — Post-layout verification | **met** | Cites `sim/pex/access-time/reports/read-access-time.pex.json` — `klt pex`, `status: pass`, 27/27 corners, read access time schematic-vs-extracted, `provenance.input.content_hash` pinning the committed bitcell GDS byte-for-byte. Item 7 accepts a `klt pex` report and nothing else. Disclosed: the envelope predates `klt pex`'s `body_bias` block, so the citation reports no body-bias statement at all (never "every device body was biased"); and read/hold SNM have no PEX-compatible path for a structural reason Seevinck's method imposes — fully investigated and disclosed in [`sim/pex/README.md`](../sim/pex/README.md), needing a new isolated-inverter layout deliverable rather than a re-verification. |
| 8 — Characterization report | **met** | Cites `measurements/characterization.signoff.json` — a hand-rolled `kind: generic` envelope (the one item this wrapper is allowed to satisfy) asserting the aggregated [`characterization-report.md`](../measurements/characterization-report.md): per-spec-row values across all 27 corners plus the MC/yield summaries, with the envelope's `provenance.input.content_hash` pinning that report and CI's existing check 5 keeping it byte-identical to `measurements/generate_report.py`'s output. |
| 9 — Testbenches shipped | **met** (issue #277) | Cites `sim/testbenches.signoff.json`, a `kind: generic`, `t1_item: 9` wrapper pinning `sim/README.md` (inventory, pinned PDK revision, cold-start invocation), `sim/lib/pdk_pin.txt`, `sim/lib/run_corner_sweep.sh` and the committed ngspice testbenches. Not proven: that the testbenches run -- that needs ngspice and the pinned PDK, which CI does not install. |
| 10 — Repo hygiene | **met** (issue #277) | Cites `repo-hygiene.signoff.json`, a `kind: generic`, `t1_item: 10` wrapper pinning the root `README.md` (what the block is, a spec table, a how-to-reproduce index), `LICENSE` (Apache-2.0) and `.github/workflows/ci.yml`. Not proven: that CI is green -- the pins only fix which files were attested. |
| 11 — Power delivery (structural) | **met** (issue #159; `graded_by_build: true`) | Compound citation, a list of two reports: (a) `layout/reports/erc-array-supply.json`, a `klt erc` 0.6.0 run over the committed array GDS against `layout/sram_256x32/erc-supply-spec.json` with both ties declared -- `erc_finding_count: 0` (zero `erc.unconnected_net`, `erc.supply_short`, `erc.missing_tie`); `erc_coverage` lists `erc.missing_tie` for `nwell_tie` (Nwell 21/0, net VDD) and `substrate_tie` (`well_layer: null` + `well_boxes`, net VSS) as checked, `skipped: []`, and the substrate tie is graded `checked_by_well_assertion` (the well itself is the spec's assertion -- disclosed, falsifiable, see `layout/reports/README.md`); input `content_hash` equals the committed array GDS; the tie check was proven able to fail by a negative control (wrong tie net fires `erc.missing_tie`, recorded in `layout/reports/README.md` § "Item 11"); and (b) `layout/reports/lvs-array.json` (`status: match`, VDD/VSS paired in `net_correspondence`), pinned exactly as item 4 pins it. The ERC report is an abridged envelope that stays recognizable to the grader: it keeps a top-level `gates` list (first 4 of 16,640 entries, verbatim, `gate_count` the true total) plus `gate_role`, and keeps `erc_coverage`, `erc_findings`, `erc_finding_count` and provenance in full. Reading the rendered `power_delivery` block: `ties_checked_by_well_assertion` names the substrate tie. Full reading in `layout/reports/README.md` § "Item 11". |

**Item 2: what `met` means here.** Until 2026-10-02 items 1, 2, 9 and 10
were deliberately left uncited. No `klt` verb binds to them. On 2026-10-02 the
operator granted bronze (T1) on the human-audited record
([`spec/t1-grant-2026-10-02.md`](../spec/t1-grant-2026-10-02.md)) and, in
issue #126, directed that they be re-cited so the mechanical verdict tracks
the granted tier. Under 0.8.0 the native placeholder citations stopped
grading for items 1, 9 and 10 and were replaced by artifact-anchored generic
wrappers (issue #277, above). Item 2 (Layout) still cites
`layout/reports/drc-array.json`, a related native envelope: `met` there means
only that a passing envelope is cited, **not** that it is evidence for the
item; the substance is the human audit (committed bitcell + array GDS,
deterministically regenerated by `./layout/verify.sh` step 1). The tool gap
is tracked upstream at klayout-tools#2718.
