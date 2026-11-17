# Decision record: future sim campaigns standardize on the pinned `hs a` ngspice environment

**Status**: Decided — operator ruling (rjwalters, 2026-11-17, attended
`/fleet:decide` round 20261116-r15, q88, option `a`); filed here per
`CLAUDE.md`'s "spec changes go through `spec/` with a decision record" and
ratified into the tree via PR approval (2AMLogic/2am#357 standing policy)
**Resolves**: #389 (the evidence-environment decision gating blocker 3
(cutover) of #230; the Monte Carlo re-run itself is #272's, not this
record's)
**Evidence**: PR #386's receipt
[`sim/deck-parity/20261116-mc-9corner.md`](../sim/deck-parity/20261116-mc-9corner.md)
(a committed local A/B — same host, same `ngspice 47`, same deck bytes, same
seeds, only `.spiceinit` differing)

## Question

The repo's committed evidence was taken under **two different ngspice
environments**. The 2026-08 deterministic records carry
`Note: Compatibility modes selected: hs a` and reproduce exactly under the
post-#338/#346 pinned run-directory `.spiceinit` (108/108 determinism-control
samples, delta 0.0 V). The 2026-09-21 Monte Carlo sample-sets reproduce
exactly under the *unpinned* environment, and the pin moves their SNM
negative-control surviving values off them (e.g. `hold-snm` @
`tt_25c_3.30v` nc 68: 0.166776 committed/unpinned vs 0.095418 pinned).
Neither family is wrong, but no single generator environment reproduces both
at once. Which environment do future sim campaigns — deterministic and
Monte Carlo — standardize on?

## Answer

**Option (a): the pinned deterministic `hs a` environment.** Every new
campaign, deterministic and Monte Carlo, runs under the staged
`.spiceinit` pin (#338/#346), so the measurement environment is a property
of the repo rather than of whichever host executes it. The pin is what makes
deck-mode fleet runs reproduce the deterministic records exactly; standard
on it, and the deterministic corpus needs no change.

### Declined options

- **(b) The unpinned environment** — declined. It reproduces the September
  MC sample-sets only by inheriting the executing host's ambient
  `~/.spiceinit`; adopting it would undo #338/#346's premise and make every
  new record irreproducible on any host whose `.spiceinit` differs.
- **(c) Environment per record family** — declined. It freezes two
  environments permanently, makes determinism-control anchors (which tie MC
  samples to deterministic records) ambiguous about which environment they
  assert, and leaves every future campaign a choice this record exists to
  remove.

## What happens to each committed record family

- **The 2026-08 deterministic records**: unchanged. They already carry
  `hs a` compatibility modes and reproduce exactly under the pin; they are
  the environment's reference corpus.
- **The 2026-09-21 MC sample-sets**
  (`sim/{read-snm,hold-snm,write-margin}/mc/samples/20260921-*.json`):
  **kept, append-only, and annotated** as unpinned-environment evidence —
  see the sidecar note
  [`sim/deck-parity/20261117-mc-unpinned-environment-annotation.md`](../sim/deck-parity/20261117-mc-unpinned-environment-annotation.md).
  No file, record, raw log or yield report under `sim/*/mc/` is edited.
  They are **re-qualified under the pin as new `Supersedes` records**, which
  issue #272 already tracks; that re-run is #272's scope, not this record's.
  Until then they remain valid evidence of which draws fail and of
  pinned-vs-unpinned agreement on the mismatch samples (all 5,400 within
  the 30 uV gate).

## What this record does not change

- **Nothing under `sim/*/mc/`** — no sample-set, record, raw log or yield
  report is edited, superseded in place, or deleted. The annotation is a
  sidecar; re-qualification happens as *new* records under #272.
- **The pin itself** (#338/#346 `.spiceinit` content, transport, seed
  derivation) and the corner set and tolerances.
- **The cutover schedule** (#230): this closes blocker 3's gate (a); the
  switch itself — retiring `run_corner_sweep.sh`/the MC pool — is #230's
  increment, and its retirement PR should cite the 2026-11-15 and
  2026-11-16 receipts plus this record.
- **The August deterministic corpus** — no change, per the Answer above.

## Ratification mechanism

The operator ruling cited above is the decision; per 2AMLogic/2am#357
standing policy this record is drafted for the operator's PR approval, which
files the ruling in the tree. It reflects the ruling and the 20261116
receipt's evidence, not a judgement this agent makes unilaterally.
