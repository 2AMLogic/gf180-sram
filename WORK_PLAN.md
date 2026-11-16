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
- **#372**: Evidence gate: receipt "Files in" coverage is invisible — a receipt with no matching table heading is silently ungated
- **#373**: deck_adapter mc-reduce: the MC path never checks composed_deck_sha256, so MC receipts have no deck-bytes-unchanged check at all
- **#388**: Consolidate duplicated klt request skeleton and Q-word grading across smoke, access-power, min-clock-pulse benches
- **#392**: Four committed sim/pex/*/testbench/tb_* benches are pinned by no signoff wrapper
- **#393**: commit_report.py: --print templates are unguarded, so a malformed one tracebacks AFTER out.json is already committed
- **#394**: Dedupe pulse.py's copied smoke.py stimulus/testbench code (~50-110 LOC)

## In Progress

Issues currently being built (`loom:building`).

- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)
- **#332**: Remove the duplicated evidence-format CI run and the stale 'nothing has landed yet' scaffolding framing
- **#381**: Amended committed-bytes rule: MC receipts carry no preserved RESULT: lines, and the stated byte cost measures raw line text rather than committed growth
- **#382**: sim: grade-set completeness is a distinct count, not a set — an off-grid variant can substitute for an omitted grid point

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#264**: feat: store new evidence bytes in the artifact store, commit manifests only
- **#398**: docs: scope deck-parity committed-bytes rule to reduce output, relabel byte figure as raw text

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#349**: config: widen Guide doc-maintenance debounce windows to 6h/12h
- **#384**: chore(loom): resync installed Loom to v0.19.1302

## Proposed

Issues carrying `loom:curated`.

- **#206**: Assemble macro-level GDS with ratified pins; macro DRC and LVS *(curated)*
- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim *(curated)*
- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS *(curated)*
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact) *(curated)*
- **#285**: T1 item 4 (LVS): re-run array LVS under pinned klt 0.8.0 so its input binds a committed file (input_verified is null) *(curated)*
- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance *(curated)*
- **#372**: Evidence gate: receipt "Files in" coverage is invisible — a receipt with no matching table heading is silently ungated *(curated)*
- **#373**: deck_adapter mc-reduce: the MC path never checks composed_deck_sha256, so MC receipts have no deck-bytes-unchanged check at all *(curated)*
- **#381**: Amended committed-bytes rule: MC receipts carry no preserved RESULT: lines, and the stated byte cost measures raw line text rather than committed growth *(curated)*
- **#382**: sim: grade-set completeness is a distinct count, not a set — an off-grid variant can substitute for an omitted grid point *(curated)*
- **#392**: Four committed sim/pex/*/testbench/tb_* benches are pinned by no signoff wrapper *(curated)*
- **#393**: commit_report.py: --print templates are unguarded, so a malformed one tracebacks AFTER out.json is already committed *(curated)*

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
| Ready (`loom:issue`) | 7 |
| In Progress (`loom:building`) | 4 |
| PRs awaiting review | 2 |
| Approved PRs awaiting merge | 2 |
| Curated | 12 |
| Architect / Hermit proposals | 2 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
