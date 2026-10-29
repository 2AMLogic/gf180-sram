# Work Plan

Prioritized roadmap generated automatically from current GitHub label state by
the Guide role's document maintenance phase. Everything between the markers
below is machine-generated and overwritten wholesale on each update; do not
hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#264**: feat: store new evidence bytes in the artifact store, commit manifests only
- **#273**: chore(pdk): default remaining scripts to ~/.ciel and add dated re-pin entries
- **#289**: fix(sim): find repo root by .git marker instead of parents[2]

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3
- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim
- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim

## In Progress

Issues currently being built (`loom:building`).

- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)
- **#287**: Signoff scripts default repo root to parents[2], wrong if relocated deeper than sim/lib/

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#264**: feat: store new evidence bytes in the artifact store, commit manifests only
- **#273**: chore(pdk): default remaining scripts to ~/.ciel and add dated re-pin entries
- **#289**: fix(sim): find repo root by .git marker instead of parents[2]

## Proposed

Issues carrying `loom:curated`.

- **#160**: T1 item 6: make the klt yield report's samples path resolve from any working directory *(curated)*
- **#173**: Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3 *(curated)*
- **#206**: Assemble macro-level GDS with ratified pins; macro DRC and LVS *(curated)*
- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim *(curated)*
- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS *(curated)*
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact) *(curated)*
- **#285**: T1 item 4 (LVS): re-run array LVS under pinned klt 0.8.0 so its input binds a committed file (input_verified is null) *(curated)*
- **#287**: Signoff scripts default repo root to parents[2], wrong if relocated deeper than sim/lib/ *(curated)*

## Proposed (Architect / Hermit)

- **#252**: Consolidate duplicated layout-generator helpers (_load, save_options) *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 3 |
| Very important | 0 |
| Important | 3 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 3 |
| Curated | 8 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
