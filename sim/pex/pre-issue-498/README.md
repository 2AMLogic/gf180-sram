# sim/pex/pre-issue-498 -- frozen schema-1 PEX report baseline

Per `CLAUDE.md`'s "`sim/` results are append-only evidence" rule, this
directory is a byte-for-byte snapshot of
`sim/pex/access-time/reports/` **as it stood immediately before issue
#498's regeneration**, taken right before that re-run overwrote the live
paths with klt 0.9.0 output. It follows the same convention as
`sim/pex/pre-issue-103/` (see that directory's own `README.md` for the
rationale): `klt pex` writes to a single fixed path, so a straight re-run
would silently replace the only copy of the prior evidence with no in-tree
trace beyond `git log`.

Unlike the pre-issue-103 snapshot, the underlying layout did **not**
change: the bitcell GDS is the same post-#103 revision
(`sha256:53d2b7aa3539199214bd85386c23b1929f1fa7c8950379476c4ba70ec4fcd4ae`)
the live reports already pinned. Two things changed between these archived
files (`provenance.klt_version: "0.2.0"`, minted in issue #106) and the
live reports that replaced them:

1. **Report envelope and request shape (schema 1 -> schema 2).** The
   archived reports were written by `klt 0.2.0` (report schema 1), whose
   `reference_netlist`/`testbenches[].schematic_netlist` fields were plain
   strings and whose model-library reference reached this host's
   env-expanded `$PDK_ROOT/$PDK/...` path. Since klt 0.8.0 (report
   schema 2, klayout-tools#1261), `klt pex` emits the DUT references in the
   committable `{path, scope: "repo"}` shape and takes the model library
   PDK-relative (`models.pdk` + variant-relative `models.lib`), which is
   also the only shape the batch fleet accepts (issue #497's
   `models_lib_pdk_unresolved` refusal). Because the Spot batch fleet
   runner image runs klt 0.9.0 and its runner-side major.minor gate refuses
   the repo's pinned 0.8.0 client (exit 87, klayout-tools#7857), issue #498
   ran the 27-corner regeneration under the released
   `klayout-tools==0.9.0` wheel; signoff grading in `signoff/regenerate.sh`
   and CI remains pinned to `klayout-tools==0.8.0`.
2. **Extracted series R and substrate DC tie (`klt 0.2.0` -> `0.8.0`/`0.9.0`).**
   Between `klt 0.2.0` and `0.8.0` (verified identical between `0.8.0` and
   `0.9.0` at `tt/3.300V/25C`), `klt extract --deck gf180mcu --parasitics`
   scaled the 10 `Q`/`QB` star resistors by x0.700 and the 2 `WL` star
   resistors by x0.837 (capacitances unchanged) and added `.GLOBAL vsubs` +
   `Rvsubs_dctie vsubs 0 1e+12`, nudging `extracted_value` and `delta_pct`
   slightly at all 27 corners while keeping `schematic_value` and all 27/27
   `pass` verdicts unchanged -- see `sim/pex/README.md` § "Freshness:
   regenerated under report schema 2 (issue #498)" for the full numbers.

The schema-1 bytes that run replaced are preserved here verbatim.

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
