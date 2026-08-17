# Work Plan

Prioritized roadmap generated automatically from current GitHub label state by
the Guide role's document maintenance phase. Everything between the markers
below is machine-generated and overwritten wholesale on each update; do not
hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Urgent

Issues flagged as highest priority (`loom:urgent`).

_None._

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#24**: Ship the ratified 9-corner spec testbenches (T1 item 9)
- **#22**: Produce the SRAM macro layout / GDS (T1 item 2)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#44**: Guard-decision review: git clean -fd ask fired on scoped worktree cleanup, propose keep-flagged *(curated)*
- **#24**: Ship the ratified 9-corner spec testbenches (T1 item 9) *(curated)*
- **#23**: Run DRC, LVS, and post-layout PEX verification on the SRAM macro (T1 items 3, 4, 7) *(curated)*
- **#22**: Produce the SRAM macro layout / GDS (T1 item 2) *(curated)*

## Proposed (Architect / Hermit)

- **#10**: Lay out the 6T bitcell as a tileable cell, DRC- and LVS-clean standalone and tiled *(architect)*
- **#9**: Draw and size the 6T bitcell, and measure read SNM, hold SNM, write margin and access time across the ratified nine corners *(architect)*
- **#8**: Survey gf180mcu's design rules for SRAM-specific allowances, and run the open DRC deck against the foundry's own bitcell *(architect)*
- **#7**: Spec gap: the write-margin criterion cites a timing target that does not exist, and signoff as ratified cannot reach T1 *(architect)*
- **#6**: Bootstrap the sim harness, PDK environment, and evidence CI from gf180-bandgap *(architect)*

## Epics

_None._

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Urgent | 0 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 4 |
| Architect / Hermit proposals | 5 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
