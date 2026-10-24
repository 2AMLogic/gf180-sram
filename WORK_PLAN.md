# Work Plan

Prioritized roadmap generated automatically from current GitHub label state by
the Guide role's document maintenance phase. Everything between the markers
below is machine-generated and overwritten wholesale on each update; do not
hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3
- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim

## In Progress

Issues currently being built (`loom:building`).

- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#264**: feat: store new evidence bytes in the artifact store, commit manifests only

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#174**: feat(sim): pin open_pdks f6eeac7 and reject mismatched PDK trees

## Proposed

Issues carrying `loom:curated`.

- **#160**: T1 item 6: make the klt yield report's samples path resolve from any working directory *(curated)*
- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3 *(curated)*
- **#206**: Assemble macro-level GDS with ratified pins; macro DRC and LVS *(curated)*
- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim *(curated)*
- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS *(curated)*
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact) *(curated)*

## Proposed (Architect / Hermit)

- **#252**: Consolidate duplicated layout-generator helpers (_load, save_options) *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 1 |
| Curated | 6 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
