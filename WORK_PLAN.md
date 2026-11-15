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

- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim

## Important

`loom:important`; taken before unlabelled work.

- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS
- **#326**: Land the macro GDS, pin check and macro DRC report (split from #247; LVS stays there)
- **#327**: Commit DRC and LVS reports for the 64 x 128 array the macro is built on

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#327**: Commit DRC and LVS reports for the 64 x 128 array the macro is built on
- **#329**: sim: dynamic power per read and write access on the macro-smoke netlist, 27 corners

## In Progress

Issues currently being built (`loom:building`).

- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)
- **#326**: Land the macro GDS, pin check and macro DRC report (split from #247; LVS stays there)
- **#331**: Give the ratified 27-corner matrix a single owner: 4 copies, 3 unguarded
- **#332**: Remove the duplicated evidence-format CI run and the stale 'nothing has landed yet' scaffolding framing

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#264**: feat: store new evidence bytes in the artifact store, commit manifests only
- **#333**: refactor(sim): give the ratified corner matrix a single owner in sim/lib
- **#336**: ci: run the evidence-format check once, in its own job only
- **#339**: sim: record the fleet deck-mode parity receipt at tt_25c_3.30v and bound build/reduce to a corner subset

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#325**: docs: roadmap as of 2026-11-13
- **#334**: feat(layout): land the sram_256x32 macro GDS, pin check and macro DRC report

## Proposed

Issues carrying `loom:curated`.

- **#206**: Assemble macro-level GDS with ratified pins; macro DRC and LVS *(curated)*
- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim *(curated)*
- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS *(curated)*
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact) *(curated)*
- **#285**: T1 item 4 (LVS): re-run array LVS under pinned klt 0.8.0 so its input binds a committed file (input_verified is null) *(curated)*
- **#326**: Land the macro GDS, pin check and macro DRC report (split from #247; LVS stays there) *(curated)*
- **#327**: Commit DRC and LVS reports for the 64 x 128 array the macro is built on *(curated)*
- **#328**: sim: minimum clock pulse bench on the macro-smoke netlist over the 27 corners *(curated)*
- **#329**: sim: dynamic power per read and write access on the macro-smoke netlist, 27 corners *(curated)*

## Proposed (Architect / Hermit)

- **#252**: Consolidate duplicated layout-generator helpers (_load, save_options) *(hermit)*
- **#330**: Split the shared periphery-layout library out of layout/periphery/column/generate.py *(hermit)*
- **#335**: Remove dead npm script worktree:return — its target was deleted by a Loom resync *(hermit)*
- **#337**: Adopt sim/lib/repo_root.py at the 5 sites still hand-rolling a fixed-depth repo root *(hermit)*
- **#340**: Collapse layout/reports/generate.sh's ten inline python3 -c scrub blocks into one helper, guarded by klt env-provenance scan *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 3 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 5 |
| PRs awaiting review | 4 |
| Approved PRs awaiting merge | 2 |
| Curated | 9 |
| Architect / Hermit proposals | 5 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
