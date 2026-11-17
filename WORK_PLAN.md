# Work Plan

Prioritized roadmap generated automatically from current GitHub label state by
the Guide role's document maintenance phase. Everything between the markers
below is machine-generated and overwritten wholesale on each update; do not
hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#349**: config: widen Guide doc-maintenance debounce windows to 6h/12h
- **#384**: chore(loom): resync installed Loom to v0.19.1302

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim

## Important

`loom:important`; taken before unlabelled work.

- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS
- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance
- **#373**: deck_adapter mc-reduce: the MC path never checks composed_deck_sha256, so MC receipts have no deck-bytes-unchanged check at all
- **#388**: Consolidate duplicated klt request skeleton and Q-word grading across smoke, access-power, min-clock-pulse benches
- **#392**: Four committed sim/pex/*/testbench/tb_* benches are pinned by no signoff wrapper
- **#400**: Committed-bytes rule's corners[].result_lines clause is satisfied by zero committed deterministic receipts
- **#415**: Ungated-receipt-table warning text misdescribes the newly-surfaced second-table shape

## In Progress

Issues currently being built (`loom:building`).

- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)
- **#379**: ci.yml header and repo-hygiene attestation prose: two residual accuracy gaps (1 of 5 jobs unnamed; harness suites not all under sim/lib/)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#264**: feat: store new evidence bytes in the artifact store, commit manifests only

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#349**: config: widen Guide doc-maintenance debounce windows to 6h/12h
- **#384**: chore(loom): resync installed Loom to v0.19.1302
- **#414**: docs(ci): name array-schematics in attestation and fix harness test locations

## Proposed

Issues carrying `loom:curated`.

- **#206**: Assemble macro-level GDS with ratified pins; macro DRC and LVS *(curated)*
- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim *(curated)*
- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS *(curated)*
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact) *(curated)*
- **#285**: T1 item 4 (LVS): re-run array LVS under pinned klt 0.8.0 so its input binds a committed file (input_verified is null) *(curated)*
- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance *(curated)*
- **#373**: deck_adapter mc-reduce: the MC path never checks composed_deck_sha256, so MC receipts have no deck-bytes-unchanged check at all *(curated)*
- **#379**: ci.yml header and repo-hygiene attestation prose: two residual accuracy gaps (1 of 5 jobs unnamed; harness suites not all under sim/lib/) *(curated)*
- **#392**: Four committed sim/pex/*/testbench/tb_* benches are pinned by no signoff wrapper *(curated)*
- **#400**: Committed-bytes rule's corners[].result_lines clause is satisfied by zero committed deterministic receipts *(curated)*
- **#415**: Ungated-receipt-table warning text misdescribes the newly-surfaced second-table shape *(curated)*

## Proposed (Architect / Hermit)

- **#252**: Consolidate duplicated layout-generator helpers (_load, save_options) *(hermit)*
- **#330**: Split the shared periphery-layout library out of layout/periphery/column/generate.py *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 2 |
| Very important | 1 |
| Important | 2 |
| Ready (`loom:issue`) | 6 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 3 |
| Curated | 11 |
| Architect / Hermit proposals | 2 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
