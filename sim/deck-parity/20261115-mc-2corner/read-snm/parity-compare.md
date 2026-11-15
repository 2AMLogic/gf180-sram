## Parity comparison (Monte Carlo): `read-snm`

- Committed sample-set: `sim/read-snm/mc/samples/20260921-124232-cf5e975.json`
- Determinism-control anchor: `sim/read-snm/records/20260817-011523-4448966.md`
- Comparison rule: pre-#213 extractor (`e140796^`) `--pair` mode applied to the fleet's own per-sample sweep pairs; tolerance 3e-05 V on the recorded metric `read_snm_v` (lobes tabulated, not gated)
- Coverage: 1216/1216 units; 2 corners
- Deck bytes asserted: True (all units present-and-equal)
- Seed identity asserted: True (all units derive_seed-equal)

### Corner `tt_25c_3.30v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.857685 | 0.857683 | -2.000e-06 | WITHIN-TOL |
  | read_snm_lobe_high_v | 0.381267 | 0.381267 | 0.000e+00 | EXACT |
  | read_snm_v | 0.381267 | 0.381267 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 99 usable vs committed 1 errored (fleet errored 1); compared in surviving order
  - per-sample |delta| distribution: n=99, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
  - OPEN unit `mc.tt_25c_3.30v.nc.00089.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_25c_3.30v nc sample 89`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

### Corner `ff_125c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.472848 | 0.472848 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.214599 | 0.214599 | 0.000e+00 | EXACT |
  | read_snm_v | 0.214599 | 0.214599 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 96 usable vs committed 4 errored (fleet errored 4); compared in surviving order
  - per-sample |delta| distribution: n=96, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
  - OPEN unit `mc.ff_125c_2.97v.nc.00043.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_125c_2.97v.nc.00068.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_125c_2.97v.nc.00096.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_125c_2.97v.nc.00097.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 43`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 68`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 96`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 97`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

**Overall: parity** -- 2/2 corners at parity.
