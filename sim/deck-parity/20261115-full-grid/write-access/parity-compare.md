## Parity comparison: `write-access`

- Committed record: `sim/access-time/records/20260817-012005-4448966.md`
- Comparison rule: exact float equality on every metric in the record row
- Coverage: 27 corners on both sides
- Deck bytes asserted: True (all units present-and-equal)

| Corner | Metric | Record | Fleet | Delta | Verdict |
|---|---|---|---|---|---|
| `ff_-40c_2.97v` | write_access_time_s | 4.7116e-11 | 4.7116e-11 | 0.000e+00 | EXACT |
| `ff_-40c_3.30v` | write_access_time_s | 4.46049e-11 | 4.46049e-11 | 0.000e+00 | EXACT |
| `ff_-40c_3.63v` | write_access_time_s | 4.24594e-11 | 4.24594e-11 | 0.000e+00 | EXACT |
| `ff_25c_2.97v` | write_access_time_s | 5.05193e-11 | 5.05193e-11 | 0.000e+00 | EXACT |
| `ff_25c_3.30v` | write_access_time_s | 4.78495e-11 | 4.78495e-11 | 0.000e+00 | EXACT |
| `ff_25c_3.63v` | write_access_time_s | 4.56126e-11 | 4.56126e-11 | 0.000e+00 | EXACT |
| `ff_125c_2.97v` | write_access_time_s | 5.72457e-11 | 5.72457e-11 | 0.000e+00 | EXACT |
| `ff_125c_3.30v` | write_access_time_s | 5.39284e-11 | 5.39284e-11 | 0.000e+00 | EXACT |
| `ff_125c_3.63v` | write_access_time_s | 5.15212e-11 | 5.15212e-11 | 0.000e+00 | EXACT |
| `tt_-40c_2.97v` | write_access_time_s | 5.57706e-11 | 5.57706e-11 | 0.000e+00 | EXACT |
| `tt_-40c_3.30v` | write_access_time_s | 5.21982e-11 | 5.21982e-11 | 0.000e+00 | EXACT |
| `tt_-40c_3.63v` | write_access_time_s | 4.94228e-11 | 4.94228e-11 | 0.000e+00 | EXACT |
| `tt_25c_2.97v` | write_access_time_s | 6.07379e-11 | 6.07379e-11 | 0.000e+00 | EXACT |
| `tt_25c_3.30v` | write_access_time_s | 5.67636e-11 | 5.67636e-11 | 0.000e+00 | EXACT |
| `tt_25c_3.63v` | write_access_time_s | 5.35678e-11 | 5.35678e-11 | 0.000e+00 | EXACT |
| `tt_125c_2.97v` | write_access_time_s | 6.93536e-11 | 6.93536e-11 | 0.000e+00 | EXACT |
| `tt_125c_3.30v` | write_access_time_s | 6.47822e-11 | 6.47822e-11 | 0.000e+00 | EXACT |
| `tt_125c_3.63v` | write_access_time_s | 6.12799e-11 | 6.12799e-11 | 0.000e+00 | EXACT |
| `ss_-40c_2.97v` | write_access_time_s | 6.71457e-11 | 6.71457e-11 | 0.000e+00 | EXACT |
| `ss_-40c_3.30v` | write_access_time_s | 6.25045e-11 | 6.25045e-11 | 0.000e+00 | EXACT |
| `ss_-40c_3.63v` | write_access_time_s | 5.88804e-11 | 5.88804e-11 | 0.000e+00 | EXACT |
| `ss_25c_2.97v` | write_access_time_s | 7.36367e-11 | 7.36367e-11 | 0.000e+00 | EXACT |
| `ss_25c_3.30v` | write_access_time_s | 6.83046e-11 | 6.83046e-11 | 0.000e+00 | EXACT |
| `ss_25c_3.63v` | write_access_time_s | 6.42155e-11 | 6.42155e-11 | 0.000e+00 | EXACT |
| `ss_125c_2.97v` | write_access_time_s | 8.49307e-11 | 8.49307e-11 | 0.000e+00 | EXACT |
| `ss_125c_3.30v` | write_access_time_s | 7.8579e-11 | 7.8579e-11 | 0.000e+00 | EXACT |
| `ss_125c_3.63v` | write_access_time_s | 7.37515e-11 | 7.37515e-11 | 0.000e+00 | EXACT |

**Maximum |delta| per metric**:

- `write_access_time_s`: 0.000e+00 V (gated)

**Corner verdicts**: 27/27 parity; 0 OPEN; 0 MISMATCH. Overall: **parity**.
