# Work Plan

Prioritized roadmap generated automatically from current GitHub label state by
the Guide role's document maintenance phase. Everything between the markers
below is machine-generated and overwritten wholesale on each update; do not
hand-edit that region.

<!-- guide:plan-body:start -->
_Generated: 2026-11-18T21:50:00Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#462**: docs: flag design/README.md and sim/README.md as hash-pinned by their T1 wrappers

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS *(held)*
- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance *(held)*

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)
- **#461**: Two more pinned ordinary-markdown files (design/README.md, sim/README.md) still carry no pin warning

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#264**: feat: store new evidence bytes in the artifact store, commit manifests only *(held)*

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#462**: docs: flag design/README.md and sim/README.md as hash-pinned by their T1 wrappers — closes #461

## Proposed

Issues carrying `loom:curated`.

- **#206**: Assemble macro-level GDS with ratified pins; macro DRC and LVS *(curated)* *(held)*
- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS *(curated)* *(held)*
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact) *(curated)*
- **#285**: T1 item 4 (LVS): re-run array LVS under pinned klt 0.8.0 so its input binds a committed file (input_verified is null) *(curated)* *(held)*
- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance *(curated)* *(held)*
- **#437**: Migrate the pex write-margin by-hand legs off the retired run_corner_sweep.sh (deck-mode port + parity receipt) *(curated)*
- **#461**: Two more pinned ordinary-markdown files (design/README.md, sim/README.md) still carry no pin warning *(curated)*

## Proposed (Architect / Hermit)

- **#252**: Consolidate duplicated layout-generator helpers (_load, save_options) *(hermit)* *(held)*
- **#330**: Split the shared periphery-layout library out of layout/periphery/column/generate.py *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 0 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 1 |
| Curated | 7 |
| Architect / Hermit proposals | 2 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
