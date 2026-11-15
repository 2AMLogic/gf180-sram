## Parity comparison: `read-snm`

- Committed record: `sim/read-snm/records/20260817-011523-4448966.md`
- Comparison rule: pre-#213 extractor (`e140796^`) applied to the fleet's own sweep data; tolerance 3e-05 V on the recorded metric `read_snm_v` (lobes tabulated, not gated)
- Coverage: 27 corners on both sides
- Deck bytes asserted: True (all units present-and-equal)

| Corner | Metric | Record | Fleet | Delta | Verdict |
|---|---|---|---|---|---|
| `ff_-40c_2.97v` | read_snm_lobe_low_v | 0.781993 | 0.781993 | 0.000e+00 | EXACT |
| `ff_-40c_2.97v` | read_snm_lobe_high_v | 0.346745 | 0.346745 | 0.000e+00 | EXACT |
| `ff_-40c_2.97v` | read_snm_v | 0.346745 | 0.346745 | 0.000e+00 | EXACT |
| `ff_-40c_3.30v` | read_snm_lobe_low_v | 0.78755 | 0.78755 | 0.000e+00 | EXACT |
| `ff_-40c_3.30v` | read_snm_lobe_high_v | 0.348079 | 0.348079 | 0.000e+00 | EXACT |
| `ff_-40c_3.30v` | read_snm_v | 0.348079 | 0.348079 | 0.000e+00 | EXACT |
| `ff_-40c_3.63v` | read_snm_lobe_low_v | 0.784559 | 0.784559 | 0.000e+00 | EXACT |
| `ff_-40c_3.63v` | read_snm_lobe_high_v | 0.378868 | 0.378868 | 0.000e+00 | EXACT |
| `ff_-40c_3.63v` | read_snm_v | 0.378868 | 0.378868 | 0.000e+00 | EXACT |
| `ff_25c_2.97v` | read_snm_lobe_low_v | 0.660028 | 0.660028 | 0.000e+00 | EXACT |
| `ff_25c_2.97v` | read_snm_lobe_high_v | 0.279259 | 0.279259 | 0.000e+00 | EXACT |
| `ff_25c_2.97v` | read_snm_v | 0.279259 | 0.279259 | 0.000e+00 | EXACT |
| `ff_25c_3.30v` | read_snm_lobe_low_v | 0.652703 | 0.652703 | 0.000e+00 | EXACT |
| `ff_25c_3.30v` | read_snm_lobe_high_v | 0.29104 | 0.29104 | 0.000e+00 | EXACT |
| `ff_25c_3.30v` | read_snm_v | 0.29104 | 0.29104 | 0.000e+00 | EXACT |
| `ff_25c_3.63v` | read_snm_lobe_low_v | 0.640587 | 0.640587 | 0.000e+00 | EXACT |
| `ff_25c_3.63v` | read_snm_lobe_high_v | 0.322552 | 0.322552 | 0.000e+00 | EXACT |
| `ff_25c_3.63v` | read_snm_v | 0.322552 | 0.322552 | 0.000e+00 | EXACT |
| `ff_125c_2.97v` | read_snm_lobe_low_v | 0.472848 | 0.472848 | 0.000e+00 | EXACT |
| `ff_125c_2.97v` | read_snm_lobe_high_v | 0.214599 | 0.214599 | 0.000e+00 | EXACT |
| `ff_125c_2.97v` | read_snm_v | 0.214599 | 0.214599 | 0.000e+00 | EXACT |
| `ff_125c_3.30v` | read_snm_lobe_low_v | 0.455824 | 0.455824 | 0.000e+00 | EXACT |
| `ff_125c_3.30v` | read_snm_lobe_high_v | 0.237829 | 0.237829 | 0.000e+00 | EXACT |
| `ff_125c_3.30v` | read_snm_v | 0.237829 | 0.237829 | 0.000e+00 | EXACT |
| `ff_125c_3.63v` | read_snm_lobe_low_v | 0.440354 | 0.440354 | 0.000e+00 | EXACT |
| `ff_125c_3.63v` | read_snm_lobe_high_v | 0.265005 | 0.265005 | 0.000e+00 | EXACT |
| `ff_125c_3.63v` | read_snm_v | 0.265005 | 0.265005 | 0.000e+00 | EXACT |
| `tt_-40c_2.97v` | read_snm_lobe_low_v | 0.934968 | 0.934967 | -1.000e-06 | WITHIN-TOL |
| `tt_-40c_2.97v` | read_snm_lobe_high_v | 0.443117 | 0.443117 | 0.000e+00 | EXACT |
| `tt_-40c_2.97v` | read_snm_v | 0.443117 | 0.443117 | 0.000e+00 | EXACT |
| `tt_-40c_3.30v` | read_snm_lobe_low_v | 0.965074 | 0.965072 | -2.000e-06 | WITHIN-TOL |
| `tt_-40c_3.30v` | read_snm_lobe_high_v | 0.450044 | 0.450044 | 0.000e+00 | EXACT |
| `tt_-40c_3.30v` | read_snm_v | 0.450044 | 0.450044 | 0.000e+00 | EXACT |
| `tt_-40c_3.63v` | read_snm_lobe_low_v | 0.984568 | 0.984568 | 0.000e+00 | EXACT |
| `tt_-40c_3.63v` | read_snm_lobe_high_v | 0.45802 | 0.45802 | 0.000e+00 | EXACT |
| `tt_-40c_3.63v` | read_snm_v | 0.45802 | 0.45802 | 0.000e+00 | EXACT |
| `tt_25c_2.97v` | read_snm_lobe_low_v | 0.842689 | 0.842689 | 0.000e+00 | EXACT |
| `tt_25c_2.97v` | read_snm_lobe_high_v | 0.377941 | 0.377941 | 0.000e+00 | EXACT |
| `tt_25c_2.97v` | read_snm_v | 0.377941 | 0.377941 | 0.000e+00 | EXACT |
| `tt_25c_3.30v` | read_snm_lobe_low_v | 0.857685 | 0.857683 | -2.000e-06 | WITHIN-TOL |
| `tt_25c_3.30v` | read_snm_lobe_high_v | 0.381267 | 0.381267 | 0.000e+00 | EXACT |
| `tt_25c_3.30v` | read_snm_v | 0.381267 | 0.381267 | 0.000e+00 | EXACT |
| `tt_25c_3.63v` | read_snm_lobe_low_v | 0.865131 | 0.865131 | 0.000e+00 | EXACT |
| `tt_25c_3.63v` | read_snm_lobe_high_v | 0.385058 | 0.385058 | 0.000e+00 | EXACT |
| `tt_25c_3.63v` | read_snm_v | 0.385058 | 0.385058 | 0.000e+00 | EXACT |
| `tt_125c_2.97v` | read_snm_lobe_low_v | 0.692016 | 0.692016 | 0.000e+00 | EXACT |
| `tt_125c_2.97v` | read_snm_lobe_high_v | 0.295443 | 0.295443 | 0.000e+00 | EXACT |
| `tt_125c_2.97v` | read_snm_v | 0.295443 | 0.295443 | 0.000e+00 | EXACT |
| `tt_125c_3.30v` | read_snm_lobe_low_v | 0.692196 | 0.692196 | 0.000e+00 | EXACT |
| `tt_125c_3.30v` | read_snm_lobe_high_v | 0.296711 | 0.296711 | 0.000e+00 | EXACT |
| `tt_125c_3.30v` | read_snm_v | 0.296711 | 0.296711 | 0.000e+00 | EXACT |
| `tt_125c_3.63v` | read_snm_lobe_low_v | 0.690133 | 0.690133 | 0.000e+00 | EXACT |
| `tt_125c_3.63v` | read_snm_lobe_high_v | 0.318427 | 0.318427 | 0.000e+00 | EXACT |
| `tt_125c_3.63v` | read_snm_v | 0.318427 | 0.318427 | 0.000e+00 | EXACT |
| `ss_-40c_2.97v` | read_snm_lobe_low_v | 1.052778 | 1.052778 | 0.000e+00 | EXACT |
| `ss_-40c_2.97v` | read_snm_lobe_high_v | 0.540536 | 0.540537 | 1.000e-06 | WITHIN-TOL |
| `ss_-40c_2.97v` | read_snm_v | 0.540536 | 0.540537 | 1.000e-06 | WITHIN-TOL |
| `ss_-40c_3.30v` | read_snm_lobe_low_v | 1.103049 | 1.103049 | 0.000e+00 | EXACT |
| `ss_-40c_3.30v` | read_snm_lobe_high_v | 0.55084 | 0.55084 | 0.000e+00 | EXACT |
| `ss_-40c_3.30v` | read_snm_v | 0.55084 | 0.55084 | 0.000e+00 | EXACT |
| `ss_-40c_3.63v` | read_snm_lobe_low_v | 1.144814 | 1.144814 | 0.000e+00 | EXACT |
| `ss_-40c_3.63v` | read_snm_lobe_high_v | 0.56375 | 0.56375 | 0.000e+00 | EXACT |
| `ss_-40c_3.63v` | read_snm_v | 0.56375 | 0.56375 | 0.000e+00 | EXACT |
| `ss_25c_2.97v` | read_snm_lobe_low_v | 0.984053 | 0.984053 | 0.000e+00 | EXACT |
| `ss_25c_2.97v` | read_snm_lobe_high_v | 0.475538 | 0.475538 | 0.000e+00 | EXACT |
| `ss_25c_2.97v` | read_snm_v | 0.475538 | 0.475538 | 0.000e+00 | EXACT |
| `ss_25c_3.30v` | read_snm_lobe_low_v | 1.021938 | 1.021938 | 0.000e+00 | EXACT |
| `ss_25c_3.30v` | read_snm_lobe_high_v | 0.483481 | 0.483481 | 0.000e+00 | EXACT |
| `ss_25c_3.30v` | read_snm_v | 0.483481 | 0.483481 | 0.000e+00 | EXACT |
| `ss_25c_3.63v` | read_snm_lobe_low_v | 1.051086 | 1.051086 | 0.000e+00 | EXACT |
| `ss_25c_3.63v` | read_snm_lobe_high_v | 0.493503 | 0.493503 | 0.000e+00 | EXACT |
| `ss_25c_3.63v` | read_snm_v | 0.493503 | 0.493503 | 0.000e+00 | EXACT |
| `ss_125c_2.97v` | read_snm_lobe_low_v | 0.870873 | 0.870873 | 0.000e+00 | EXACT |
| `ss_125c_2.97v` | read_snm_lobe_high_v | 0.394239 | 0.394239 | 0.000e+00 | EXACT |
| `ss_125c_2.97v` | read_snm_v | 0.394239 | 0.394239 | 0.000e+00 | EXACT |
| `ss_125c_3.30v` | read_snm_lobe_low_v | 0.891352 | 0.891352 | 0.000e+00 | EXACT |
| `ss_125c_3.30v` | read_snm_lobe_high_v | 0.40076 | 0.40076 | 0.000e+00 | EXACT |
| `ss_125c_3.30v` | read_snm_v | 0.40076 | 0.40076 | 0.000e+00 | EXACT |
| `ss_125c_3.63v` | read_snm_lobe_low_v | 0.906729 | 0.906729 | 0.000e+00 | EXACT |
| `ss_125c_3.63v` | read_snm_lobe_high_v | 0.40862 | 0.40862 | 0.000e+00 | EXACT |
| `ss_125c_3.63v` | read_snm_v | 0.40862 | 0.40862 | 0.000e+00 | EXACT |

**Maximum |delta| per metric**:

- `read_snm_lobe_high_v`: 1.000e-06 V
- `read_snm_lobe_low_v`: 2.000e-06 V
- `read_snm_v`: 1.000e-06 V (gated)

**Corner verdicts**: 27/27 parity; 0 OPEN; 0 MISMATCH. Overall: **parity**.
