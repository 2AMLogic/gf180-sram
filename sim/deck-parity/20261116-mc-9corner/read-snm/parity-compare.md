## Parity comparison (Monte Carlo): `read-snm`

- Committed sample-set: `sim/read-snm/mc/samples/20260921-124232-cf5e975.json`
- Determinism-control anchor: `sim/read-snm/records/20260817-011523-4448966.md`
- Comparison rule: pre-#213 extractor (`e140796^`) `--pair` mode applied to the fleet's own per-sample sweep pairs; tolerance 3e-05 V on the recorded metric `read_snm_v` (lobes tabulated, not gated)
- Coverage: 5472/5472 units; 9 corners
- Deck bytes asserted: True (all units present-and-equal)
- Seed identity asserted: True (all units derive_seed-equal)

### Corner `ff_-40c_2.97v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.781993 | 0.781993 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.346745 | 0.346745 | 0.000e+00 | EXACT |
  | read_snm_v | 0.346745 | 0.346745 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=1.000e-06 V, mean=1.050e-07 V, p50=0.000e+00 V, p95=1.000e-06 V
- Negative control: 94 usable vs committed 6 errored (fleet errored 6); compared in surviving order
  - per-sample |delta| distribution: n=94, max=5.123e-02 V, mean=5.454e-04 V, p50=0.000e+00 V, p95=2.000e-06 V
  - OPEN unit `mc.ff_-40c_2.97v.nc.00030.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_-40c_2.97v.nc.00070.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_-40c_2.97v.nc.00070.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_-40c_2.97v.nc.00080.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_-40c_2.97v.nc.00085.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_-40c_2.97v.nc.00087.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_-40c_2.97v.nc.00089.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_-40c_2.97v nc sample 30`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_-40c_2.97v nc sample 70`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_-40c_2.97v nc sample 70`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_-40c_2.97v nc sample 80`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_-40c_2.97v nc sample 85`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_-40c_2.97v nc sample 87`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_-40c_2.97v nc sample 89`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

  **Non-parity findings**:
  - (OPEN) nc sample 2: |delta| 5.123e-02 V exceeds the 3e-05 V tolerance

### Corner `ff_25c_3.30v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.652703 | 0.652703 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.29104 | 0.29104 | 0.000e+00 | EXACT |
  | read_snm_v | 0.29104 | 0.29104 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 91 usable vs committed 9 errored (fleet errored 9); compared in surviving order
  - per-sample |delta| distribution: n=91, max=1.200e-05 V, mean=2.308e-07 V, p50=0.000e+00 V, p95=1.000e-06 V
  - OPEN unit `mc.ff_25c_3.30v.nc.00011.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_25c_3.30v.nc.00020.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_25c_3.30v.nc.00029.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_25c_3.30v.nc.00039.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_25c_3.30v.nc.00044.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_25c_3.30v.nc.00050.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_25c_3.30v.nc.00061.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_25c_3.30v.nc.00082.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_25c_3.30v.nc.00084.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 11`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 20`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 29`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 39`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 44`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 50`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 61`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 82`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_25c_3.30v nc sample 84`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

### Corner `ff_125c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.472848 | 0.472848 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.214599 | 0.214599 | 0.000e+00 | EXACT |
  | read_snm_v | 0.214599 | 0.214599 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=1.000e-06 V, mean=5.000e-09 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 96 usable vs committed 4 errored (fleet errored 4); compared in surviving order
  - per-sample |delta| distribution: n=96, max=1.000e-05 V, mean=2.708e-07 V, p50=0.000e+00 V, p95=1.000e-06 V
  - OPEN unit `mc.ff_125c_2.97v.nc.00043.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_125c_2.97v.nc.00068.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_125c_2.97v.nc.00096.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ff_125c_2.97v.nc.00097.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 43`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 68`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 96`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 97`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

### Corner `tt_-40c_3.63v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.984568 | 0.984568 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.45802 | 0.45802 | 0.000e+00 | EXACT |
  | read_snm_v | 0.45802 | 0.45802 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=1.000e-06 V, mean=4.000e-08 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 92 usable vs committed 8 errored (fleet errored 8); compared in surviving order
  - per-sample |delta| distribution: n=92, max=3.000e-06 V, mean=2.717e-07 V, p50=0.000e+00 V, p95=2.000e-06 V
  - OPEN unit `mc.tt_-40c_3.63v.nc.00004.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_-40c_3.63v.nc.00031.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_-40c_3.63v.nc.00047.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_-40c_3.63v.nc.00053.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_-40c_3.63v.nc.00054.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_-40c_3.63v.nc.00085.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_-40c_3.63v.nc.00091.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_-40c_3.63v.nc.00099.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 4`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 31`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 47`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 53`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 54`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 85`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 91`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_-40c_3.63v nc sample 99`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

### Corner `tt_25c_3.30v` -- OPEN

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.857685 | 0.857685 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.381267 | 0.381267 | 0.000e+00 | EXACT |
  | read_snm_v | 0.381267 | 0.381267 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=1.000e-06 V, mean=5.500e-08 V, p50=0.000e+00 V, p95=1.000e-06 V
- Negative control: 99 usable vs committed 1 errored (fleet errored 1); compared in surviving order
  - per-sample |delta| distribution: n=99, max=2.155e-02 V, mean=2.178e-04 V, p50=0.000e+00 V, p95=1.000e-06 V
  - OPEN unit `mc.tt_25c_3.30v.nc.00089.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_25c_3.30v nc sample 89`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

  **Non-parity findings**:
  - (OPEN) nc sample 22: |delta| 2.155e-02 V exceeds the 3e-05 V tolerance

### Corner `tt_125c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.692016 | 0.692016 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.295443 | 0.295443 | 0.000e+00 | EXACT |
  | read_snm_v | 0.295443 | 0.295443 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=1.000e-06 V, mean=1.000e-08 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 96 usable vs committed 4 errored (fleet errored 4); compared in surviving order
  - per-sample |delta| distribution: n=96, max=3.000e-06 V, mean=1.979e-07 V, p50=0.000e+00 V, p95=1.000e-06 V
  - OPEN unit `mc.tt_125c_2.97v.nc.00051.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_125c_2.97v.nc.00074.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_125c_2.97v.nc.00094.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.tt_125c_2.97v.nc.00098.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_125c_2.97v nc sample 51`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_125c_2.97v nc sample 74`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_125c_2.97v nc sample 94`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `tt_125c_2.97v nc sample 98`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

### Corner `ss_-40c_3.63v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 1.144814 | 1.144814 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.56375 | 0.56375 | 0.000e+00 | EXACT |
  | read_snm_v | 0.56375 | 0.56375 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=2.000e-06 V, mean=2.850e-07 V, p50=0.000e+00 V, p95=1.000e-06 V
- Negative control: 97 usable vs committed 3 errored (fleet errored 3); compared in surviving order
  - per-sample |delta| distribution: n=97, max=1.000e-05 V, mean=4.639e-07 V, p50=0.000e+00 V, p95=2.000e-06 V
  - OPEN unit `mc.ss_-40c_3.63v.nc.00011.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_-40c_3.63v.nc.00056.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_-40c_3.63v.nc.00082.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_-40c_3.63v nc sample 11`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_-40c_3.63v nc sample 56`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_-40c_3.63v nc sample 82`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

### Corner `ss_25c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.984053 | 0.984053 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.475538 | 0.475538 | 0.000e+00 | EXACT |
  | read_snm_v | 0.475538 | 0.475538 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=1.000e-06 V, mean=2.600e-07 V, p50=0.000e+00 V, p95=1.000e-06 V
- Negative control: 93 usable vs committed 7 errored (fleet errored 7); compared in surviving order
  - per-sample |delta| distribution: n=93, max=7.000e-06 V, mean=7.204e-07 V, p50=0.000e+00 V, p95=5.000e-06 V
  - OPEN unit `mc.ss_25c_2.97v.nc.00005.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_25c_2.97v.nc.00006.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_25c_2.97v.nc.00010.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_25c_2.97v.nc.00019.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_25c_2.97v.nc.00069.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_25c_2.97v.nc.00085.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_25c_2.97v.nc.00092.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 5`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 6`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 10`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 19`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 69`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 85`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 92`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

### Corner `ss_125c_3.63v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | read_snm_lobe_low_v | 0.906729 | 0.906729 | 0.000e+00 | EXACT |
  | read_snm_lobe_high_v | 0.40862 | 0.40862 | 0.000e+00 | EXACT |
  | read_snm_v | 0.40862 | 0.40862 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=1.000e-06 V, mean=1.000e-08 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 95 usable vs committed 5 errored (fleet errored 5); compared in surviving order
  - per-sample |delta| distribution: n=95, max=7.000e-06 V, mean=1.895e-07 V, p50=0.000e+00 V, p95=1.000e-06 V
  - OPEN unit `mc.ss_125c_3.63v.nc.00002.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_125c_3.63v.nc.00026.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_125c_3.63v.nc.00038.R`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_125c_3.63v.nc.00044.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `mc.ss_125c_3.63v.nc.00068.L`: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 2`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 26`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 38`: R: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 44`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 68`: L: declared outputs missing: ['read_snm_sweep.txt'] (never counted as parity)

**Overall: OPEN** -- 7/9 corners at parity.
