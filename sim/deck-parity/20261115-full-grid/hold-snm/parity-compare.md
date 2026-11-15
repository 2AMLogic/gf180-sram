## Parity comparison: `hold-snm`

- Committed record: `sim/hold-snm/records/20260817-011558-4448966.md`
- Comparison rule: pre-#213 extractor (`e140796^`) applied to the fleet's own sweep data; tolerance 3e-05 V on the recorded metric `hold_snm_v` (lobes tabulated, not gated)
- Coverage: 27 corners on both sides
- Deck bytes asserted: True (all units present-and-equal)

| Corner | Metric | Record | Fleet | Delta | Verdict |
|---|---|---|---|---|---|
| `ff_-40c_2.97v` | hold_snm_lobe_low_v | 1.835613 | 1.835627 | 1.400e-05 | WITHIN-TOL |
| `ff_-40c_2.97v` | hold_snm_lobe_high_v | 0.999014 | 0.999016 | 2.000e-06 | WITHIN-TOL |
| `ff_-40c_2.97v` | hold_snm_v | 0.999014 | 0.999016 | 2.000e-06 | WITHIN-TOL |
| `ff_-40c_3.30v` | hold_snm_lobe_low_v | 2.047586 | 2.047596 | 1.000e-05 | WITHIN-TOL |
| `ff_-40c_3.30v` | hold_snm_lobe_high_v | 1.075028 | 1.07503 | 2.000e-06 | WITHIN-TOL |
| `ff_-40c_3.30v` | hold_snm_v | 1.075028 | 1.07503 | 2.000e-06 | WITHIN-TOL |
| `ff_-40c_3.63v` | hold_snm_lobe_low_v | 2.253773 | 2.253778 | 5.000e-06 | WITHIN-TOL |
| `ff_-40c_3.63v` | hold_snm_lobe_high_v | 1.150509 | 1.15051 | 1.000e-06 | WITHIN-TOL |
| `ff_-40c_3.63v` | hold_snm_v | 1.150509 | 1.15051 | 1.000e-06 | WITHIN-TOL |
| `ff_25c_2.97v` | hold_snm_lobe_low_v | 1.828985 | 1.828994 | 9.000e-06 | WITHIN-TOL |
| `ff_25c_2.97v` | hold_snm_lobe_high_v | 0.972353 | 0.972354 | 1.000e-06 | WITHIN-TOL |
| `ff_25c_2.97v` | hold_snm_v | 0.972353 | 0.972354 | 1.000e-06 | WITHIN-TOL |
| `ff_25c_3.30v` | hold_snm_lobe_low_v | 2.031634 | 2.031638 | 4.000e-06 | WITHIN-TOL |
| `ff_25c_3.30v` | hold_snm_lobe_high_v | 1.048587 | 1.048588 | 1.000e-06 | WITHIN-TOL |
| `ff_25c_3.30v` | hold_snm_v | 1.048587 | 1.048588 | 1.000e-06 | WITHIN-TOL |
| `ff_25c_3.63v` | hold_snm_lobe_low_v | 2.227106 | 2.227107 | 1.000e-06 | WITHIN-TOL |
| `ff_25c_3.63v` | hold_snm_lobe_high_v | 1.124406 | 1.124407 | 1.000e-06 | WITHIN-TOL |
| `ff_25c_3.63v` | hold_snm_v | 1.124406 | 1.124407 | 1.000e-06 | WITHIN-TOL |
| `ff_125c_2.97v` | hold_snm_lobe_low_v | 1.792025 | 1.792026 | 1.000e-06 | WITHIN-TOL |
| `ff_125c_2.97v` | hold_snm_lobe_high_v | 0.930461 | 0.930461 | 0.000e+00 | EXACT |
| `ff_125c_2.97v` | hold_snm_v | 0.930461 | 0.930461 | 0.000e+00 | EXACT |
| `ff_125c_3.30v` | hold_snm_lobe_low_v | 1.977898 | 1.977898 | 0.000e+00 | EXACT |
| `ff_125c_3.30v` | hold_snm_lobe_high_v | 1.008552 | 1.008552 | 0.000e+00 | EXACT |
| `ff_125c_3.30v` | hold_snm_v | 1.008552 | 1.008552 | 0.000e+00 | EXACT |
| `ff_125c_3.63v` | hold_snm_lobe_low_v | 2.157022 | 2.157022 | 0.000e+00 | EXACT |
| `ff_125c_3.63v` | hold_snm_lobe_high_v | 1.087062 | 1.087062 | 0.000e+00 | EXACT |
| `ff_125c_3.63v` | hold_snm_v | 1.087062 | 1.087062 | 0.000e+00 | EXACT |
| `tt_-40c_2.97v` | hold_snm_lobe_low_v | 1.818979 | 1.818985 | 6.000e-06 | WITHIN-TOL |
| `tt_-40c_2.97v` | hold_snm_lobe_high_v | 1.055088 | 1.05509 | 2.000e-06 | WITHIN-TOL |
| `tt_-40c_2.97v` | hold_snm_v | 1.055088 | 1.05509 | 2.000e-06 | WITHIN-TOL |
| `tt_-40c_3.30v` | hold_snm_lobe_low_v | 2.037615 | 2.037623 | 8.000e-06 | WITHIN-TOL |
| `tt_-40c_3.30v` | hold_snm_lobe_high_v | 1.134683 | 1.134685 | 2.000e-06 | WITHIN-TOL |
| `tt_-40c_3.30v` | hold_snm_v | 1.134683 | 1.134685 | 2.000e-06 | WITHIN-TOL |
| `tt_-40c_3.63v` | hold_snm_lobe_low_v | 2.252356 | 2.252366 | 1.000e-05 | WITHIN-TOL |
| `tt_-40c_3.63v` | hold_snm_lobe_high_v | 1.213568 | 1.213569 | 1.000e-06 | WITHIN-TOL |
| `tt_-40c_3.63v` | hold_snm_v | 1.213568 | 1.213569 | 1.000e-06 | WITHIN-TOL |
| `tt_25c_2.97v` | hold_snm_lobe_low_v | 1.822534 | 1.822549 | 1.500e-05 | WITHIN-TOL |
| `tt_25c_2.97v` | hold_snm_lobe_high_v | 1.031028 | 1.031032 | 4.000e-06 | WITHIN-TOL |
| `tt_25c_2.97v` | hold_snm_v | 1.031028 | 1.031032 | 4.000e-06 | WITHIN-TOL |
| `tt_25c_3.30v` | hold_snm_lobe_low_v | 2.035532 | 2.035546 | 1.400e-05 | WITHIN-TOL |
| `tt_25c_3.30v` | hold_snm_lobe_high_v | 1.110807 | 1.11081 | 3.000e-06 | WITHIN-TOL |
| `tt_25c_3.30v` | hold_snm_v | 1.110807 | 1.11081 | 3.000e-06 | WITHIN-TOL |
| `tt_25c_3.63v` | hold_snm_lobe_low_v | 2.24311 | 2.243117 | 7.000e-06 | WITHIN-TOL |
| `tt_25c_3.63v` | hold_snm_lobe_high_v | 1.189934 | 1.189935 | 1.000e-06 | WITHIN-TOL |
| `tt_25c_3.63v` | hold_snm_v | 1.189934 | 1.189935 | 1.000e-06 | WITHIN-TOL |
| `tt_125c_2.97v` | hold_snm_lobe_low_v | 1.811042 | 1.81105 | 8.000e-06 | WITHIN-TOL |
| `tt_125c_2.97v` | hold_snm_lobe_high_v | 0.993408 | 0.99341 | 2.000e-06 | WITHIN-TOL |
| `tt_125c_2.97v` | hold_snm_v | 0.993408 | 0.99341 | 2.000e-06 | WITHIN-TOL |
| `tt_125c_3.30v` | hold_snm_lobe_low_v | 2.009862 | 2.009864 | 2.000e-06 | WITHIN-TOL |
| `tt_125c_3.30v` | hold_snm_lobe_high_v | 1.074566 | 1.074568 | 2.000e-06 | WITHIN-TOL |
| `tt_125c_3.30v` | hold_snm_v | 1.074566 | 1.074568 | 2.000e-06 | WITHIN-TOL |
| `tt_125c_3.63v` | hold_snm_lobe_low_v | 2.201823 | 2.201824 | 1.000e-06 | WITHIN-TOL |
| `tt_125c_3.63v` | hold_snm_lobe_high_v | 1.155746 | 1.155746 | 0.000e+00 | EXACT |
| `tt_125c_3.63v` | hold_snm_v | 1.155746 | 1.155746 | 0.000e+00 | EXACT |
| `ss_-40c_2.97v` | hold_snm_lobe_low_v | 1.796057 | 1.796058 | 1.000e-06 | WITHIN-TOL |
| `ss_-40c_2.97v` | hold_snm_lobe_high_v | 1.105024 | 1.105025 | 1.000e-06 | WITHIN-TOL |
| `ss_-40c_2.97v` | hold_snm_v | 1.105024 | 1.105025 | 1.000e-06 | WITHIN-TOL |
| `ss_-40c_3.30v` | hold_snm_lobe_low_v | 2.018994 | 2.018997 | 3.000e-06 | WITHIN-TOL |
| `ss_-40c_3.30v` | hold_snm_lobe_high_v | 1.187215 | 1.187216 | 1.000e-06 | WITHIN-TOL |
| `ss_-40c_3.30v` | hold_snm_v | 1.187215 | 1.187216 | 1.000e-06 | WITHIN-TOL |
| `ss_-40c_3.63v` | hold_snm_lobe_low_v | 2.238914 | 2.238919 | 5.000e-06 | WITHIN-TOL |
| `ss_-40c_3.63v` | hold_snm_lobe_high_v | 1.268808 | 1.268809 | 1.000e-06 | WITHIN-TOL |
| `ss_-40c_3.63v` | hold_snm_v | 1.268808 | 1.268809 | 1.000e-06 | WITHIN-TOL |
| `ss_25c_2.97v` | hold_snm_lobe_low_v | 1.804454 | 1.804459 | 5.000e-06 | WITHIN-TOL |
| `ss_25c_2.97v` | hold_snm_lobe_high_v | 1.082379 | 1.082383 | 4.000e-06 | WITHIN-TOL |
| `ss_25c_2.97v` | hold_snm_v | 1.082379 | 1.082383 | 4.000e-06 | WITHIN-TOL |
| `ss_25c_3.30v` | hold_snm_lobe_low_v | 2.023401 | 2.02341 | 9.000e-06 | WITHIN-TOL |
| `ss_25c_3.30v` | hold_snm_lobe_high_v | 1.165266 | 1.16527 | 4.000e-06 | WITHIN-TOL |
| `ss_25c_3.30v` | hold_snm_v | 1.165266 | 1.16527 | 4.000e-06 | WITHIN-TOL |
| `ss_25c_3.63v` | hold_snm_lobe_low_v | 2.238957 | 2.238968 | 1.100e-05 | WITHIN-TOL |
| `ss_25c_3.63v` | hold_snm_lobe_high_v | 1.247287 | 1.24729 | 3.000e-06 | WITHIN-TOL |
| `ss_25c_3.63v` | hold_snm_v | 1.247287 | 1.24729 | 3.000e-06 | WITHIN-TOL |
| `ss_125c_2.97v` | hold_snm_lobe_low_v | 1.807864 | 1.807884 | 2.000e-05 | WITHIN-TOL |
| `ss_125c_2.97v` | hold_snm_lobe_high_v | 1.048438 | 1.048445 | 7.000e-06 | WITHIN-TOL |
| `ss_125c_2.97v` | hold_snm_v | 1.048438 | 1.048445 | 7.000e-06 | WITHIN-TOL |
| `ss_125c_3.30v` | hold_snm_lobe_low_v | 2.017041 | 2.017055 | 1.400e-05 | WITHIN-TOL |
| `ss_125c_3.30v` | hold_snm_lobe_high_v | 1.132542 | 1.132545 | 3.000e-06 | WITHIN-TOL |
| `ss_125c_3.30v` | hold_snm_v | 1.132542 | 1.132545 | 3.000e-06 | WITHIN-TOL |
| `ss_125c_3.63v` | hold_snm_lobe_low_v | 2.220851 | 2.220857 | 6.000e-06 | WITHIN-TOL |
| `ss_125c_3.63v` | hold_snm_lobe_high_v | 1.216449 | 1.216451 | 2.000e-06 | WITHIN-TOL |
| `ss_125c_3.63v` | hold_snm_v | 1.216449 | 1.216451 | 2.000e-06 | WITHIN-TOL |

**Maximum |delta| per metric**:

- `hold_snm_lobe_high_v`: 7.000e-06 V
- `hold_snm_lobe_low_v`: 2.000e-05 V
- `hold_snm_v`: 7.000e-06 V (gated)

**Corner verdicts**: 27/27 parity; 0 OPEN; 0 MISMATCH. Overall: **parity**.
