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
| `design-evidence-tiers.md` | Vendored copy of `klayout-tools`' checklist definition ([`docs/design-evidence-tiers.md`](https://github.com/2AMLogic/klayout-tools/blob/main/docs/design-evidence-tiers.md)), pinned at upstream commit `cf91a08d854c6be53bb39bf72cd0ad5b93dc89a4` ("feat(signoff): verify a citation's input against the artifact, not just the envelope", 2026-09-21; file sha256 `fcb3864360c8d0182217e07240ee55ddf95a1da407a9bd16a921e19802632106`). Passed to grading via `--tiers-doc` because the newest checklist item — item 11, "Power delivery (structural)" (added 2026-09-17, klayout-tools#2025) — exists in no released `klt` yet: the released `klt signoff` parses the item skeleton from this vendored copy so every item gets its row. When a `klt` release whose bundled checklist has eleven items ships, drop this file and the `--tiers-doc` flag and re-grade. |

CI (the `signoff` job in `.github/workflows/ci.yml`) re-grades the manifest on
every PR and requires byte-identical output to the committed
`signoff-report.json` — so a manifest citation whose underlying artifact has
since changed (layout GDS, reference netlist, PEX report, MC samples
document, characterization report) fails CI instead of silently rotting. The
fix is always the same one-liner: `./signoff/regenerate.sh`, then commit the
refreshed report.

## Grader distribution discipline

Regeneration and CI grade with the **released PyPI registry wheel** of
`klayout-tools==0.5.0`, never the `klt` already on this host. Under the same
version string, a `uv tool install git+...` snapshot or a full-checkout
install of the klayout-tools repo can grade differently — observed live: an
11-item-era full-repo install under the name "0.5.0", and the v0.5.0 tag
snapshot whose bundled checklist predates item 11 entirely (filed upstream
as klayout-tools#2216). The released
wheel reports the git tag it was built from (`klt version --format json` →
`git_tag: v0.5.0`, `is_release: true`); `regenerate.sh` and
`scripts/ci/check_signoff_freshness.py` both assert that identity before
grading. Keep the version pin in `regenerate.sh`, the CI job, and
`check_signoff_freshness.py` in sync (all three say `0.5.0` today).

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
verdict is **3/11 met** — and per the issue that created this directory, an
honest mostly-`unmet` mechanical reading is the desired outcome: the
checklist moved on 2026-09-17 and no hand-read survived that; a report that
says less than the old hand-read did is worth more than prose nobody can
re-verify.

| Item | Verdict today | Why — and what would change it |
|---|---|---|
| 1 — Design sources | unmet `no_evidence` | No `klt` verb grades this item — a claim about what the repo *contains* (committed schematics, generator, derived netlists), not a runnable check. Uncited by deliberate choice (citing an unrelated passing envelope to turn the row green is the documented anti-pattern). The human-audited evidence stands: [`design/README.md`](../design/README.md) (bitcell + array schematics, byte-identical regeneration) and [`layout/README.md`](../layout/README.md). |
| 2 — Layout | unmet `no_evidence` | Same structural reason as item 1. Human-audited: committed bitcell + array GDS, deterministically regenerated by `./layout/verify.sh` step 1. |
| 3 — DRC clean | **met** | Cites `layout/reports/drc-array.json` — `status: clean` over the full 256×32 array, its `provenance.input.content_hash` pinning the committed array GDS byte-for-byte. Coverage disclosure, read from the report rather than assumed: the curated deck checked 9 of its 18 layers against this layout; 4 in-stream layers carry no rules (`31/0`, `32/0`, `34/10`, `42/10`) and 19 rules were skipped — and the curated deck cannot see the 5 rule families the PDK's native deck flags on the foundry's own bitcell (issue #103, `layout/reports/sram-rule-survey.md`). A "clean" from a deck with disclosed holes is disclosed here, not hidden. |
| 4 — LVS clean | unmet `stale_evidence` | The check genuinely passes — `layout/reports/lvs-array.json` records `status: match`, 49,152/49,152 devices, 16,706/16,706 nets against the committed array netlist — but that report was minted by a `klt` that did not yet record `provenance.input.content_hash` for LVS, so the manifest's pin (the committed reference netlist's hash, which the report's own `environment.reference_sha256` corroborates) cannot be verified by the grader: unmet for freshness-opacity, not for a failed compare. Re-minting the report under a `klt` that pins LVS inputs turns this row `met` — issue #128. |
| 5 — Full corner verification | unmet `no_evidence` | The 27-corner sweep exists and passed — per-corner append-only records plus the derived [`sim/signoff-summary.md`](../sim/signoff-summary.md) ("Overall signoff: PASS") — but it was never minted as a `klt sim` JSON envelope, the only evidence kind this item accepts. Issue #128: mint the sim envelope from the existing records. |
| 6 — Monte Carlo evidence | unmet `stale_evidence` | Cites the read-SNM `klt yield` report (`sim/read-snm/mc/yield-reports/20260817-102455-ce56f59.json`, `status: reported` — no `target_yield` is set, per `spec/target-yield-decision.md`). The manifest pins the hash of the committed samples document (`sim/read-snm/mc/samples/20260817-102455-ce56f59.json`), but the committed yield report names its `samples` by an author-machine absolute path — the provenance-hygiene hole tracked by issue #109 — so the grader cannot re-locate and re-hash what the report was computed from: unmet for freshness-opacity. The hold-SNM and write-margin campaigns (`sim/hold-snm/mc/`, `sim/write-margin/mc/`) carry the same shape and the same limitation. Issue #128: re-running the MC campaigns with the #109-fixed harness (repo-relative paths) turns all three gradeable. |
| 7 — Post-layout verification | **met** | Cites `sim/pex/access-time/reports/read-access-time.pex.json` — `klt pex`, `status: pass`, 27/27 corners, read access time schematic-vs-extracted, `provenance.input.content_hash` pinning the committed bitcell GDS byte-for-byte. Item 7 accepts a `klt pex` report and nothing else. Disclosed: the envelope predates `klt pex`'s `body_bias` block, so the citation reports no body-bias statement at all (never "every device body was biased"); and read/hold SNM have no PEX-compatible path for a structural reason Seevinck's method imposes — fully investigated and disclosed in [`sim/pex/README.md`](../sim/pex/README.md), needing a new isolated-inverter layout deliverable rather than a re-verification. |
| 8 — Characterization report | **met** | Cites `measurements/characterization.signoff.json` — a hand-rolled `kind: generic` envelope (the one item this wrapper is allowed to satisfy) asserting the aggregated [`characterization-report.md`](../measurements/characterization-report.md): per-spec-row values across all 27 corners plus the MC/yield summaries, with the envelope's `provenance.input.content_hash` pinning that report and CI's existing check 5 keeping it byte-identical to `measurements/generate_report.py`'s output. |
| 9 — Testbenches shipped | unmet `no_evidence` | Same structural reason as item 1. Human-audited: [`sim/README.md`](../sim/README.md) inventories all five committed testbenches with the pinned PDK revision and cold-start invocation. |
| 10 — Repo hygiene | unmet `no_evidence` | Same structural reason as item 1. Human-audited: this README and the root README and `LICENSE` in-repo; `.github/workflows/ci.yml` runs on every PR and push. |
| 11 — Power delivery (structural) | unmet `unrecognized_envelope` | **The evidence now exists** — committed by issue #124: the supply spec `layout/sram_256x32/erc-supply-spec.json` and the `klt erc` report `layout/reports/erc-array-supply.json` (`erc_finding_count: 0` — zero `erc.unconnected_net`, zero `erc.supply_short` naming VDD/VSS, i.e. each declared supply resolves to exactly one electrical island; the check proven to compute via a negative control; input `content_hash` matching the committed array GDS; `erc.missing_tie` not computed, disclosed with its standing-in well-tie evidence — item 4's own `lvs-array.json` carries VDD/VSS in `net_correspondence` against the SPICE reference — full reading in `layout/reports/README.md` § "Item 11"). The row is now **cited** in the manifest (pinned to the same array-GDS `content_hash` item 3's citation pins) but stays mechanically unmet: the pinned 0.5.0 grading wheel predates item 11's grading rules entirely (klayout-tools#2057), so it renders the cited envelope `unrecognized_envelope` — cited-but-unreadable, distinguishable from `no_evidence`. Turning the row `met` needs all three of: (i) a **released** `klt` that grades item 11, adopted per this directory's grading discipline (the regenerate.sh pin, the CI job's pip install, and `check_signoff_freshness.py`'s pin move together, and the vendored `design-evidence-tiers.md` + `--tiers-doc` retire at the same time); (ii) the supply spec **regaining `ties[]`**, minted under the post-#2169-fix `klt`: the false-`erc.supply_short` ties[] blocker is fixed upstream (klayout-tools#2186, 2026-09-20 — tie conduction scoped to tap sites, the tie graph isolated) and the checklist's item 11 now demands zero `erc.missing_tie` *from a tie the run actually checked*, rendering a tie-less spec `supply_spec_incomplete`; #124's committed evidence deliberately omits `ties[]` because it was minted under the pre-fix `klt`, where declaring them collapsed the supply read (the spec's `_comment` records the decision), so a re-mint with a checked `ties[]` (the `Nwell`/`Comp∩Nplus` VDD tap is declarable; gf180mcu's substrate is an undrawn p-well, so a substrate-tie entry may additionally need an upstream answer for PDKs that draw no p-well boundary — tool-tracker territory, this design has only `Nwell` 21/0 to scope) replaces that recorded gap; (iii) issue #128's LVS re-mint with input provenance, so item 4's own LVS report — the analog column's supplies-in-`net_correspondence` half — becomes citable the same turn. |

Items 1, 2, 9 and 10 are uncited by deliberate choice: the grader accepts
any passing envelope for them without checking topical relevance (there is
no verb to bind them to), and citing an envelope that does not actually
support the claim — to make rows go green — is the failure mode this
manifest exists to prevent. Their evidence remains the committed,
human-auditable artifacts named above.
