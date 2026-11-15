## Parity comparison: `read-access`

- Committed record: `sim/access-time/records/20260817-011948-4448966.md`
- Comparison rule: exact float equality on every metric in the record row
- Coverage: 27 corners on both sides
- Deck bytes asserted: True (all units present-and-equal)

| Corner | Metric | Record | Fleet | Delta | Verdict |
|---|---|---|---|---|---|
| `ff_-40c_2.97v` | read_access_time_s | 1.40945e-10 | 1.40945e-10 | 0.000e+00 | EXACT |
| `ff_-40c_3.30v` | read_access_time_s | 1.17907e-10 | 1.17907e-10 | 0.000e+00 | EXACT |
| `ff_-40c_3.63v` | read_access_time_s | 1.03569e-10 | 1.03569e-10 | 0.000e+00 | EXACT |
| `ff_25c_2.97v` | read_access_time_s | 1.47853e-10 | 1.47853e-10 | 0.000e+00 | EXACT |
| `ff_25c_3.30v` | read_access_time_s | 1.26101e-10 | 1.26101e-10 | 0.000e+00 | EXACT |
| `ff_25c_3.63v` | read_access_time_s | 1.11953e-10 | 1.11953e-10 | 0.000e+00 | EXACT |
| `ff_125c_2.97v` | read_access_time_s | 1.5703e-10 | 1.5703e-10 | 0.000e+00 | EXACT |
| `ff_125c_3.30v` | read_access_time_s | 1.37607e-10 | 1.37607e-10 | 0.000e+00 | EXACT |
| `ff_125c_3.63v` | read_access_time_s | 1.23889e-10 | 1.23889e-10 | 0.000e+00 | EXACT |
| `tt_-40c_2.97v` | read_access_time_s | 2.08985e-10 | 2.08985e-10 | 0.000e+00 | EXACT |
| `tt_-40c_3.30v` | read_access_time_s | 1.61165e-10 | 1.61165e-10 | 0.000e+00 | EXACT |
| `tt_-40c_3.63v` | read_access_time_s | 1.34291e-10 | 1.34291e-10 | 0.000e+00 | EXACT |
| `tt_25c_2.97v` | read_access_time_s | 2.12295e-10 | 2.12295e-10 | 0.000e+00 | EXACT |
| `tt_25c_3.30v` | read_access_time_s | 1.70142e-10 | 1.70142e-10 | 0.000e+00 | EXACT |
| `tt_25c_3.63v` | read_access_time_s | 1.44853e-10 | 1.44853e-10 | 0.000e+00 | EXACT |
| `tt_125c_2.97v` | read_access_time_s | 2.18195e-10 | 2.18195e-10 | 0.000e+00 | EXACT |
| `tt_125c_3.30v` | read_access_time_s | 1.82935e-10 | 1.82935e-10 | 0.000e+00 | EXACT |
| `tt_125c_3.63v` | read_access_time_s | 1.59475e-10 | 1.59475e-10 | 0.000e+00 | EXACT |
| `ss_-40c_2.97v` | read_access_time_s | 3.57176e-10 | 3.57176e-10 | 0.000e+00 | EXACT |
| `ss_-40c_3.30v` | read_access_time_s | 2.40389e-10 | 2.40389e-10 | 0.000e+00 | EXACT |
| `ss_-40c_3.63v` | read_access_time_s | 1.85324e-10 | 1.85324e-10 | 0.000e+00 | EXACT |
| `ss_25c_2.97v` | read_access_time_s | 3.35812e-10 | 3.35812e-10 | 0.000e+00 | EXACT |
| `ss_25c_3.30v` | read_access_time_s | 2.45853e-10 | 2.45853e-10 | 0.000e+00 | EXACT |
| `ss_25c_3.63v` | read_access_time_s | 1.97169e-10 | 1.97169e-10 | 0.000e+00 | EXACT |
| `ss_125c_2.97v` | read_access_time_s | 3.2326e-10 | 3.2326e-10 | 0.000e+00 | EXACT |
| `ss_125c_3.30v` | read_access_time_s | 2.55254e-10 | 2.55254e-10 | 0.000e+00 | EXACT |
| `ss_125c_3.63v` | read_access_time_s | 2.13463e-10 | 2.13463e-10 | 0.000e+00 | EXACT |

**Maximum |delta| per metric**:

- `read_access_time_s`: 0.000e+00 V (gated)

**Corner verdicts**: 27/27 parity; 0 OPEN; 0 MISMATCH. Overall: **parity**.
