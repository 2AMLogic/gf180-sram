## Parity comparison (Monte Carlo): `write-margin`

- Committed sample-set: `sim/write-margin/mc/samples/20260921-124804-cf5e975.json`
- Determinism-control anchor: `sim/write-margin/records/20260817-105029-ce56f59.md`
- Comparison rule: exact float equality on every sample, in index order
- Coverage: 2736/2736 units; 9 corners
- Deck bytes asserted: True (all units present-and-equal)
- Seed identity asserted: True (all units derive_seed-equal)

### Corner `ff_-40c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 1.69546 | 1.69546 | 0.000e+00 | EXACT |
  | write_vdd_v | 2.97 | 2.97 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V

### Corner `ff_25c_3.30v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 1.87075 | 1.87075 | 0.000e+00 | EXACT |
  | write_vdd_v | 3.3 | 3.3 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 99 usable vs committed 1 errored (fleet errored 1); compared in surviving order
  - per-sample |delta| distribution: n=99, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
  - OPEN unit `ff_25c_3.30v nc sample 65`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)

### Corner `ff_125c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 1.64053 | 1.64053 | 0.000e+00 | EXACT |
  | write_vdd_v | 2.97 | 2.97 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 98 usable vs committed 2 errored (fleet errored 2); compared in surviving order
  - per-sample |delta| distribution: n=98, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
  - OPEN unit `ff_125c_2.97v nc sample 0`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ff_125c_2.97v nc sample 24`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)

### Corner `tt_-40c_3.63v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 2.13271 | 2.13271 | 0.000e+00 | EXACT |
  | write_vdd_v | 3.63 | 3.63 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V

### Corner `tt_25c_3.30v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 1.91003 | 1.91003 | 0.000e+00 | EXACT |
  | write_vdd_v | 3.3 | 3.3 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 94 usable vs committed 6 errored (fleet errored 6); compared in surviving order
  - per-sample |delta| distribution: n=94, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
  - OPEN unit `tt_25c_3.30v nc sample 13`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `tt_25c_3.30v nc sample 21`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `tt_25c_3.30v nc sample 54`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `tt_25c_3.30v nc sample 68`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `tt_25c_3.30v nc sample 72`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `tt_25c_3.30v nc sample 98`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)

### Corner `tt_125c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 1.67751 | 1.67751 | 0.000e+00 | EXACT |
  | write_vdd_v | 2.97 | 2.97 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 97 usable vs committed 3 errored (fleet errored 3); compared in surviving order
  - per-sample |delta| distribution: n=97, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
  - OPEN unit `tt_125c_2.97v nc sample 20`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `tt_125c_2.97v nc sample 40`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `tt_125c_2.97v nc sample 53`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)

### Corner `ss_-40c_3.63v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 2.17259 | 2.17259 | 0.000e+00 | EXACT |
  | write_vdd_v | 3.63 | 3.63 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V

### Corner `ss_25c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 1.74241 | 1.74241 | 0.000e+00 | EXACT |
  | write_vdd_v | 2.97 | 2.97 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 96 usable vs committed 4 errored (fleet errored 4); compared in surviving order
  - per-sample |delta| distribution: n=96, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
  - OPEN unit `ss_25c_2.97v nc sample 36`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 80`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 94`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_25c_2.97v nc sample 96`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)

### Corner `ss_125c_3.63v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | write_trip_voltage_v | 2.10967 | 2.10967 | 0.000e+00 | EXACT |
  | write_vdd_v | 3.63 | 3.63 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 81 usable vs committed 19 errored (fleet errored 19); compared in surviving order
  - per-sample |delta| distribution: n=81, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
  - OPEN unit `ss_125c_3.63v nc sample 2`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 4`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 5`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 11`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 14`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 19`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 20`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 22`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 26`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 28`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 44`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 52`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 57`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 59`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 73`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 77`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 87`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 89`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)
  - OPEN unit `ss_125c_3.63v nc sample 98`: RESULT-ERROR: write_trip_voltage -- write succeeded even with no bit-line differential (VWRITE = VDD) (never counted as parity)

**Overall: parity** -- 9/9 corners at parity.
