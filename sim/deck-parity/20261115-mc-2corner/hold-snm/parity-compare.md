## Parity comparison (Monte Carlo): `hold-snm`

- Committed sample-set: `sim/hold-snm/mc/samples/20260921-124534-cf5e975.json`
- Determinism-control anchor: `sim/hold-snm/records/20260817-011558-4448966.md`
- Comparison rule: pre-#213 extractor (`e140796^`) `--pair` mode applied to the fleet's own per-sample sweep pairs; tolerance 3e-05 V on the recorded metric `hold_snm_v` (lobes tabulated, not gated)
- Coverage: 1216/1216 units; 2 corners
- Deck bytes asserted: True (all units present-and-equal)
- Seed identity asserted: True (all units derive_seed-equal)

### Corner `tt_25c_3.30v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 2.035532 | 2.035546 | 1.400e-05 | WITHIN-TOL |
  | hold_snm_lobe_high_v | 1.110807 | 1.11081 | 3.000e-06 | WITHIN-TOL |
  | hold_snm_v | 1.110807 | 1.11081 | 3.000e-06 | WITHIN-TOL |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V

### Corner `ff_125c_2.97v` -- parity

- Determinism control: 4/4 usable; anchored against the committed deterministic record:

  | Metric | Record | Ctrl | Delta | Verdict |
  |---|---|---|---|---|
  | hold_snm_lobe_low_v | 1.792025 | 1.792026 | 1.000e-06 | WITHIN-TOL |
  | hold_snm_lobe_high_v | 0.930461 | 0.930461 | 0.000e+00 | EXACT |
  | hold_snm_v | 0.930461 | 0.930461 | 0.000e+00 | EXACT |
- Mismatch batch: 200/200 compared, 0 OPEN
  - per-sample |delta| distribution: n=200, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V
- Negative control: 100 usable vs committed 0 errored (fleet errored 0); compared in surviving order
  - per-sample |delta| distribution: n=100, max=0.000e+00 V, mean=0.000e+00 V, p50=0.000e+00 V, p95=0.000e+00 V

**Overall: parity** -- 2/2 corners at parity.
