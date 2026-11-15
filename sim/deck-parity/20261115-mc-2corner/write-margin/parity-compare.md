## Parity comparison (Monte Carlo): `write-margin`

- Committed sample-set: `sim/write-margin/mc/samples/20260921-124804-cf5e975.json`
- Determinism-control anchor: `sim/write-margin/records/20260817-105029-ce56f59.md`
- Comparison rule: exact float equality on every sample, in index order
- Coverage: 608/608 units; 2 corners
- Deck bytes asserted: True (all units present-and-equal)
- Seed identity asserted: True (all units derive_seed-equal)

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

**Overall: parity** -- 2/2 corners at parity.
