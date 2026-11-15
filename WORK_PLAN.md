# Work Plan

Prioritized roadmap generated automatically from current GitHub label state by
the Guide role's document maintenance phase. Everything between the markers
below is machine-generated and overwritten wholesale on each update; do not
hand-edit that region.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#349**: config: widen Guide doc-maintenance debounce windows to 6h/12h

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim

## Important

`loom:important`; taken before unlabelled work.

- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS
- **#327**: Commit DRC and LVS reports for the 64 x 128 array the macro is built on
- **#328**: sim: minimum clock pulse bench on the macro-smoke netlist over the 27 corners
- **#329**: sim: dynamic power per read and write access on the macro-smoke netlist, 27 corners
- **#338**: Pin ngspice compatibility mode in deck-mode requests instead of inheriting the executing host's .spiceinit
- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#337**: Adopt sim/lib/repo_root.py at the 5 sites still hand-rolling a fixed-depth repo root

## In Progress

Issues currently being built (`loom:building`).

- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)
- **#327**: Commit DRC and LVS reports for the 64 x 128 array the macro is built on
- **#328**: sim: minimum clock pulse bench on the macro-smoke netlist over the 27 corners
- **#329**: sim: dynamic power per read and write access on the macro-smoke netlist, 27 corners
- **#332**: Remove the duplicated evidence-format CI run and the stale 'nothing has landed yet' scaffolding framing
- **#335**: Remove dead npm script worktree:return — its target was deleted by a Loom resync
- **#338**: Pin ngspice compatibility mode in deck-mode requests instead of inheriting the executing host's .spiceinit
- **#340**: Collapse layout/reports/generate.sh's ten inline python3 -c scrub blocks into one helper, guarded by klt env-provenance scan
- **#342**: Remove the dead spacing_of() stub in layout/macro/generate.py: no callers, and wrong for M1 and vias
- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#264**: feat: store new evidence bytes in the artifact store, commit manifests only
- **#351**: data: measure minimum clock pulse width per corner on the macro bench (#328)
- **#352**: fix: drop dead spacing_of() stub from the macro generator

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#348**: build: remove dead worktree:return npm script entry
- **#349**: config: widen Guide doc-maintenance debounce windows to 6h/12h

## Proposed

Issues carrying `loom:curated`.

- **#206**: Assemble macro-level GDS with ratified pins; macro DRC and LVS *(curated)*
- **#230**: Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim *(curated)*
- **#247**: Assemble the sram_256x32 macro GDS with pins, macro DRC and LVS *(curated)*
- **#262**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact) *(curated)*
- **#285**: T1 item 4 (LVS): re-run array LVS under pinned klt 0.8.0 so its input binds a committed file (input_verified is null) *(curated)*
- **#327**: Commit DRC and LVS reports for the 64 x 128 array the macro is built on *(curated)*
- **#328**: sim: minimum clock pulse bench on the macro-smoke netlist over the 27 corners *(curated)*
- **#329**: sim: dynamic power per read and write access on the macro-smoke netlist, 27 corners *(curated)*
- **#338**: Pin ngspice compatibility mode in deck-mode requests instead of inheriting the executing host's .spiceinit *(curated)*
- **#343**: Set guide.docsMaintenance debounce windows: 64% of merged PRs (75/116 in 30 days) are Guide doc-maintenance *(curated)*
- **#345**: deck_adapter.reduce_report() inlines the RESULT:/RESULT-ERROR: grammar its own module already re-exports *(curated)*

## Proposed (Architect / Hermit)

- **#252**: Consolidate duplicated layout-generator helpers (_load, save_options) *(hermit)*
- **#330**: Split the shared periphery-layout library out of layout/periphery/column/generate.py *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 1 |
| Important | 6 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 10 |
| PRs awaiting review | 3 |
| Approved PRs awaiting merge | 2 |
| Curated | 11 |
| Architect / Hermit proposals | 2 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
