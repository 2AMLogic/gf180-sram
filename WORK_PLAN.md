# Work Plan

Prioritized roadmap generated automatically from current GitHub label state by
the Guide role's document maintenance phase. Everything between the markers
below is machine-generated and overwritten wholesale on each update; do not
hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#174**: feat(sim): pin open_pdks f6eeac7 and reject mismatched PDK trees
- **#228**: sim: wordline RC gate fails for the left-fed 4:1 row; propose superseding decision

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3
- **#204**: Draw row decoder and wordline driver layout, pitch-matched to the array

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3

## In Progress

Issues currently being built (`loom:building`).

- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#174**: feat(sim): pin open_pdks f6eeac7 and reject mismatched PDK trees
- **#228**: sim: wordline RC gate fails for the left-fed 4:1 row; propose superseding decision

## Proposed

Issues carrying `loom:curated`.

- **#204**: Draw row decoder and wordline driver layout, pitch-matched to the array *(curated)*
- **#160**: T1 item 6: make the klt yield report's samples path resolve from any working directory *(curated)*
- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3 *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 2 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 2 |
| Curated | 3 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
