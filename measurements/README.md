# measurements

**[`characterization-report.md`](characterization-report.md)** is the single,
current, aggregated artifact summarizing this macro's measured state: per-
spec-row performance (read SNM, hold SNM, write margin, read/write access
time) across every one of the ratified 27-corner process x temperature x
voltage PVT points (`spec/sram.md`, "Corner set"), plus the Monte Carlo /
mismatch yield evidence (issue #26) over a deliberate 9-corner subset of that
matrix. It exists so a reviewer can read one document to see the macro's full
measured state instead of reconstructing it from individual `sim/` records --
klayout-tools `docs/design-evidence-tiers.md` item 8.

Every number in it cites the exact `sim/` evidence record it rests on; it
invents nothing and runs no simulation itself.

## Regenerating it

```bash
python3 measurements/generate_report.py > measurements/characterization-report.md
```

`measurements/generate_report.py` is a read-only derivation over the
append-only records already committed under `sim/*/records/` and
`sim/*/mc/records/` (the same convention `sim/lib/render_signoff_table.py`
uses for `sim/signoff-summary.md` -- this script reuses that renderer
directly for the full 27-corner detail, so the two documents can never
silently disagree). It must be regenerated (not hand-edited) whenever any of
the source records is superseded by a fresh corner sweep or Monte Carlo
campaign.

## Freshness / staleness check

`characterization-report.md`'s own "Provenance" section names every source
record's ID, git sha, and timestamp it was built from. If a newer record now
exists under `sim/` for any of those claims, the report is stale --
regenerate it with the command above.

This is enforced, not just documented: `scripts/ci/check_evidence_format.py`
(the `evidence-record format` CI job, and `npm run lint` locally) re-renders
the report from whatever records are committed and fails if
`measurements/characterization-report.md` does not match byte-for-byte,
printing the regeneration command. The check is pure Python over the
committed records -- it does not run ngspice and needs no PDK.

## Scope note

This directory is documented elsewhere (`README.md`'s "Repo layout" table) as
holding silicon characterization, populated once this macro tapes out. The
report here is schematic-level pre-silicon evidence (the same testbench-based
verification the rest of `sim/` records), not measured silicon -- it is filed
under `measurements/` per issue #27's own scoping (T1 checklist item 8: "one
aggregated, current artifact summarizing per-spec-row performance across
conditions"). A post-silicon measurement, once it exists, would supersede the
pre-silicon numbers here the same way a post-layout extracted-netlist re-run
would supersede a schematic-level `sim/` record.
