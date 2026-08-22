# sim/pex/pre-issue-103 -- frozen pre-#103 PEX baseline

Per `CLAUDE.md`'s "`sim/` results are append-only evidence" rule, this
directory is a byte-for-byte snapshot of the `klt extract`/`klt pex`-derived
files under `sim/pex/` **as they stood immediately before issue #106's
re-run**, taken right before that re-run overwrote their live paths with
post-issue-#103 results.

Unlike `sim/<experiment>/records/<record-id>.md` (the `sim/lib/run_corner_sweep.sh`
convention used elsewhere in this repo, including `sim/pex/write-margin/`'s
own `corners/`/`records/`/`netlist-snapshots/`/`delta/` subtrees), the three
files preserved here were never minted with a per-run record ID -- `klt
extract --parasitics` and `klt pex` both write to a single fixed path
(`sim/pex/generate.sh`, `sim/pex/access-time/generate.sh`,
`sim/pex/write-margin/dut/generate.sh`), so a straight re-run would silently
overwrite the only copy of the pre-#103 geometry's parasitics with no
in-tree trace beyond `git log`. This directory makes that prior evidence
directly readable in the working tree, not just recoverable via history.

## What's here (originally committed by PR #96 / #99, issue #23 / #95)

| File | Original path | `provenance.input.content_hash` |
| --- | --- | --- |
| `extract-report.json` | `sim/pex/extract-report.json` | `sha256:6b90b7d615bb2528eef026ab1ab4778855d2d91b056351ac6872e89323179b3a` |
| `extracted-netlist/sram_bitcell_6t.spice` | `sim/pex/extracted-netlist/sram_bitcell_6t.spice` | (netlist derived from the report above) |
| `access-time/reports/read-access-time.pex.json` | `sim/pex/access-time/reports/read-access-time.pex.json` | same `6b90b7d6...` bitcell GDS |
| `access-time/reports/write-access-time.pex.json` | `sim/pex/access-time/reports/write-access-time.pex.json` | same `6b90b7d6...` bitcell GDS |
| `access-time/reports/klt-pex-artifacts/**` | `sim/pex/access-time/reports/klt-pex-artifacts/**` | raw `klt pex` request/netlist artifacts backing the two reports above |
| `write-margin/dut/extract-report.json` | `sim/pex/write-margin/dut/extract-report.json` | `sha256:6b90b7d615bb2528eef026ab1ab4778855d2d91b056351ac6872e89323179b3a` |
| `write-margin/dut/extracted-netlist.spice` | `sim/pex/write-margin/dut/extracted-netlist.spice` | `--pdk`-bound netlist derived from the report above |

`6b90b7d6...` is the sha256 of `layout/bitcell/sram_bitcell_6t.gds` **before**
issue #103's fix to `layout/bitcell/generate.py` (`CO_ENC_M1` 0.03 -> 0.07,
plus the row-pitch/implant/Nwell margin changes it required) -- see
`sim/pex/README.md`'s (now-historical) "Freshness" section for the full
account of what changed and why.

`sim/pex/write-margin/corners/`, `records/`, `netlist-snapshots/`, and
`delta/` are **not** duplicated here: those already follow the record-ID
convention above and are inherently append-only, so issue #106's re-run
added new, separately timestamped records there without touching the
pre-#103 ones. Nothing under this `pre-issue-103/` directory is ever meant
to be edited or regenerated -- it is a fixed historical snapshot, not a
`generate.sh` output.
