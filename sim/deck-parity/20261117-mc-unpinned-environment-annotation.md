# Annotation: the 2026-09-21 MC sample-sets were taken under the unpinned ngspice environment

- **What this is**: a sidecar note required by the operator ruling on #389
  (2026-11-17, option `a`) and recorded in
  [`spec/environment-pin-decision.md`](../../spec/environment-pin-decision.md).
  It changes nothing: every file named below is committed append-only
  evidence and is left byte-identical.
- **The fact**: these three Monte Carlo sample-sets were generated before
  #338/#346 staged the pinned run-directory `.spiceinit`, so they were taken
  under the executing host's ambient (**unpinned**) ngspice environment. The
  20261116 deck-parity receipt
  ([`20261116-mc-9corner.md`](20261116-mc-9corner.md)) established this by a
  committed local A/B — same host, same `ngspice 47`, same deck bytes, same
  seeds, only `.spiceinit` differing — which reproduces these sample-sets
  exactly unpinned and moves their SNM negative-control *surviving values*
  under the pin. All 5,400 mismatch samples agree across both environments
  within the 30 uV gate; the delta is confined to a minority of known-bad
  negative-control draws.
- **Status under the ruling**: kept (append-only), annotated by this note,
  and **re-qualified under the pinned `hs a` environment as new
  `Supersedes` records** — tracked as issue #272. Until that re-run lands,
  they stand as valid negative-control and mismatch evidence taken under the
  unpinned environment.

Annotated files:

- [`sim/read-snm/mc/samples/20260921-124232-cf5e975.json`](../read-snm/mc/samples/20260921-124232-cf5e975.json)
- [`sim/hold-snm/mc/samples/20260921-124534-cf5e975.json`](../hold-snm/mc/samples/20260921-124534-cf5e975.json)
- [`sim/write-margin/mc/samples/20260921-124804-cf5e975.json`](../write-margin/mc/samples/20260921-124804-cf5e975.json)
