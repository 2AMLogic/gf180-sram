## Parity comparison (Monte Carlo): `hold-snm`

- Committed sample-set: `sim/hold-snm/mc/samples/20260921-124534-cf5e975.json`
- Determinism-control anchor: `sim/hold-snm/records/20260817-011558-4448966.md`
- Comparison rule: pre-#213 extractor (`e140796^`) `--pair` mode applied to the fleet's own per-sample sweep pairs; tolerance 3e-05 V on the recorded metric `hold_snm_v` (lobes tabulated, not gated)
- Coverage: 5472/5472 units; 9 corners
- Deck bytes asserted: True (all units present-and-equal)
- Seed identity asserted: True (all units derive_seed-equal)

### Corner `ff_-40c_2.97v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 1.835613 | 1.835613 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 0.999014 | 0.999014 | 0.000e+00 | EXACT |
  | hold_snm_v | 0.999014 | 0.999014 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=3.000e-06 V, mean=2.145e-06 V, p50=2.000e-06 V, p95=3.000e-06 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=1.799e-01 V, mean=1.807e-03 V, p50=0.000e+00 V, p95=4.100e-05 V

  **Non-parity findings**:
  - (OPEN) nc sample 6: |delta| 2.030e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 11: |delta| 1.400e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 27: |delta| 3.700e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 28: |delta| 1.799e-01 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 56: |delta| 7.300e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 68: |delta| 1.620e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 95: |delta| 4.100e-05 V exceeds the 3e-05 V tolerance

### Corner `ff_25c_3.30v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 2.031634 | 2.031634 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 1.048587 | 1.048587 | 0.000e+00 | EXACT |
  | hold_snm_v | 1.048587 | 1.048587 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=2.000e-06 V, mean=9.700e-07 V, p50=1.000e-06 V, p95=1.000e-06 V
- Negative control: 99 usable vs committed 1 errored (fleet errored 1); compared in surviving order
  - per-sample |delta| distribution: n=99, max=3.290e-04 V, mean=6.768e-06 V, p50=0.000e+00 V, p95=2.900e-05 V
  - OPEN unit `mc.ff_25c_3.30v.nc.00011.R`: declared outputs missing: ['hold_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 11`: R: declared outputs missing: ['hold_snm_sweep.txt'] (never counted as parity)

  **Non-parity findings**:
  - (OPEN) nc sample 7: |delta| 5.300e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 18: |delta| 3.600e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 32: |delta| 5.000e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 77: |delta| 3.290e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 92: |delta| 3.900e-05 V exceeds the 3e-05 V tolerance

### Corner `ff_125c_2.97v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 1.792025 | 1.792025 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 0.930461 | 0.930461 | 0.000e+00 | EXACT |
  | hold_snm_v | 0.930461 | 0.930461 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=1.000e-06 V, mean=6.650e-07 V, p50=1.000e-06 V, p95=1.000e-06 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=1.576e-02 V, mean=1.661e-04 V, p50=1.000e-06 V, p95=5.300e-05 V

  **Non-parity findings**:
  - (OPEN) nc sample 1: |delta| 5.300e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 16: |delta| 1.576e-02 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 22: |delta| 8.300e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 41: |delta| 3.100e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 47: |delta| 5.700e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 48: |delta| 3.700e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 51: |delta| 1.010e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 70: |delta| 1.280e-04 V exceeds the 3e-05 V tolerance

### Corner `tt_-40c_3.63v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 2.252356 | 2.252356 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 1.213568 | 1.213568 | 0.000e+00 | EXACT |
  | hold_snm_v | 1.213568 | 1.213568 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=2.000e-06 V, mean=1.265e-06 V, p50=1.000e-06 V, p95=2.000e-06 V
- Negative control: 99 usable vs committed 1 errored (fleet errored 1); compared in surviving order
  - per-sample |delta| distribution: n=99, max=2.864e-01 V, mean=2.952e-03 V, p50=0.000e+00 V, p95=7.400e-05 V
  - OPEN unit `mc.tt_-40c_3.63v.nc.00054.L`: declared outputs missing: ['hold_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 54`: L: declared outputs missing: ['hold_snm_sweep.txt'] (never counted as parity)

  **Non-parity findings**:
  - (OPEN) nc sample 4: |delta| 5.600e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 7: |delta| 9.200e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 17: |delta| 6.500e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 20: |delta| 6.900e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 34: |delta| 3.800e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 62: |delta| 2.864e-01 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 63: |delta| 7.400e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 67: |delta| 5.500e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 71: |delta| 1.860e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 72: |delta| 3.500e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 73: |delta| 4.800e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 76: |delta| 1.210e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 94: |delta| 4.997e-03 V exceeds the 3e-05 V tolerance

### Corner `tt_25c_3.30v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 2.035532 | 2.035532 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 1.110807 | 1.110807 | 0.000e+00 | EXACT |
  | hold_snm_v | 1.110807 | 1.110807 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=3.000e-06 V, mean=2.285e-06 V, p50=2.000e-06 V, p95=3.000e-06 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=7.136e-02 V, mean=7.195e-04 V, p50=0.000e+00 V, p95=4.500e-05 V

  **Non-parity findings**:
  - (OPEN) nc sample 1: |delta| 4.500e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 44: |delta| 7.300e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 68: |delta| 7.136e-02 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 71: |delta| 1.230e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 73: |delta| 6.600e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 75: |delta| 8.400e-05 V exceeds the 3e-05 V tolerance

### Corner `tt_125c_2.97v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 1.811042 | 1.811042 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 0.993408 | 0.993408 | 0.000e+00 | EXACT |
  | hold_snm_v | 0.993408 | 0.993408 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=3.000e-06 V, mean=2.125e-06 V, p50=2.000e-06 V, p95=3.000e-06 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=4.080e-04 V, mean=1.372e-05 V, p50=1.000e-06 V, p95=5.600e-05 V

  **Non-parity findings**:
  - (OPEN) nc sample 10: |delta| 5.200e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 13: |delta| 5.600e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 15: |delta| 9.000e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 34: |delta| 4.700e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 39: |delta| 1.520e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 41: |delta| 4.500e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 44: |delta| 9.000e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 70: |delta| 1.280e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 75: |delta| 4.080e-04 V exceeds the 3e-05 V tolerance

### Corner `ss_-40c_3.63v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 2.238914 | 2.238914 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 1.268808 | 1.268808 | 0.000e+00 | EXACT |
  | hold_snm_v | 1.268808 | 1.268808 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=2.000e-06 V, mean=1.255e-06 V, p50=1.000e-06 V, p95=2.000e-06 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=1.820e-04 V, mean=5.130e-06 V, p50=0.000e+00 V, p95=2.000e-05 V

  **Non-parity findings**:
  - (OPEN) nc sample 23: |delta| 7.800e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 59: |delta| 1.820e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 68: |delta| 4.300e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 97: |delta| 6.500e-05 V exceeds the 3e-05 V tolerance

### Corner `ss_25c_2.97v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 1.804454 | 1.804454 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 1.082379 | 1.082379 | 0.000e+00 | EXACT |
  | hold_snm_v | 1.082379 | 1.082379 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=6.000e-06 V, mean=3.995e-06 V, p50=4.000e-06 V, p95=5.000e-06 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=2.460e-04 V, mean=8.270e-06 V, p50=0.000e+00 V, p95=4.000e-05 V

  **Non-parity findings**:
  - (OPEN) nc sample 12: |delta| 1.210e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 14: |delta| 3.200e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 15: |delta| 4.700e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 40: |delta| 2.460e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 47: |delta| 4.000e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 95: |delta| 9.200e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 96: |delta| 4.100e-05 V exceeds the 3e-05 V tolerance

### Corner `ss_125c_3.63v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 2.220851 | 2.220851 | 0.000e+00 | EXACT |
  | hold_snm_lobe_high_v | 1.216449 | 1.216449 | 0.000e+00 | EXACT |
  | hold_snm_v | 1.216449 | 1.216449 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=3.000e-06 V, mean=1.630e-06 V, p50=2.000e-06 V, p95=2.000e-06 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=1.850e-04 V, mean=6.810e-06 V, p50=0.000e+00 V, p95=3.800e-05 V

  **Non-parity findings**:
  - (OPEN) nc sample 29: |delta| 3.800e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 42: |delta| 5.100e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 44: |delta| 7.100e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 48: |delta| 1.850e-04 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 89: |delta| 4.800e-05 V exceeds the 3e-05 V tolerance
  - (OPEN) nc sample 94: |delta| 4.700e-05 V exceeds the 3e-05 V tolerance

**Overall: OPEN** -- 0/9 corners at parity.
