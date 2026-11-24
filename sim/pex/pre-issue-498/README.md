# sim/pex/pre-issue-498 -- frozen schema-1 PEX report baseline

Per `CLAUDE.md`'s "`sim/` results are append-only evidence" rule, this
directory is a byte-for-byte snapshot of
`sim/pex/access-time/reports/` **as it stood immediately before issue
#498's regeneration**, taken right before that re-run overwrote the live
paths with klt 0.8.0 output. It follows the same convention as
`sim/pex/pre-issue-103/` (see that directory's own `README.md` for the
rationale): `klt pex` writes to a single fixed path, so a straight re-run
would silently replace the only copy of the prior evidence with no in-tree
trace beyond `git log`.

Unlike the pre-issue-103 snapshot, the underlying layout did **not**
change: the bitcell GDS is the same post-#103 revision
(`sha256:53d2b7aa3539199214bd85386c23b1929f1fa7c8950379476c4ba70ec4fcd4ae`)
the live reports already pinned. What changed is the **evidence shape**:
the archived reports were written by the pre-0.8.0 `klt pex` (report
schema 1), whose `reference_netlist`/`testbenches[].schematic_netlist`
fields were plain strings and whose model-library reference reached this
host's env-expanded `$PDK_ROOT/$PDK/...` path. klt 0.8.0 (report schema 2,
klayout-tools#1261) emits the DUT references in the committable
`{path, scope: "repo"}` shape and takes the model library PDK-relative
(`models.pdk` + variant-relative `models.lib`), which is also the only
shape the batch fleet accepts (issue #497's `models_lib_pdk_unresolved`
refusal). Issue #498 regenerated both benches so the committed evidence
matches what the pinned generator actually emits; the schema-1 bytes it
replaced are preserved here.

## What's here

| File | Original path | sha256 (first 16) |
| --- | --- | --- |
| `access-time/reports/read-access-time.pex.json` | `sim/pex/access-time/reports/read-access-time.pex.json` | `27e6fd50ca1dddeb` |
| `access-time/reports/write-access-time.pex.json` | `sim/pex/access-time/reports/write-access-time.pex.json` | `e4650abaa79a855d` |
| `access-time/reports/klt-pex-artifacts/**` | `sim/pex/access-time/reports/klt-pex-artifacts/**` | raw `klt pex` request/netlist artifacts backing the two reports above |

Both archived reports: `schema_version 1`, `status: pass`, 27/27 corners,
`reference_netlist` the plain string
`sim/pex/access-time/dut/bitcell_6t_subckt.spice`. Nothing under this
`pre-issue-498/` directory is ever meant to be edited or regenerated -- it
is a fixed historical snapshot, not a `generate.sh` output.
