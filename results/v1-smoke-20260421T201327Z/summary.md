# Sweep summary — v1-smoke

- **harness**: claude_code_go
- **model**: claude-sonnet-4-6
- **max_samples_per_axis**: 5
- **timeout_per_sample_s**: 600
- **n_axes (planned)**: 9
- **n_rows (observed)**: 45
- **start_iso**: 2026-04-21T20:13:27.316967+00:00
- **end_iso**: 2026-04-21T21:02:36.593720+00:00

## Per-axis stats

| Axis | N | Mean score | Success rate | Error rate | Mean wall (s) | Sum cost ($) |
|------|---|-----------|--------------|-----------|---------------|-------------|
| BS1 | 5 | 0.225 | 0.20 | 0.00 | 153.8 | 1.4702 |
| FM3 | 5 | 0.629 | 0.60 | 0.00 | 16.9 | 0.3935 |
| FM4 | 5 | 0.400 | 0.40 | 0.00 | 22.5 | 0.4921 |
| FM5 | 5 | 0.324 | 0.00 | 0.00 | 31.8 | 0.4526 |
| M1 | 5 | 0.280 | 0.20 | 0.00 | 17.7 | 0.6569 |
| M2 | 5 | 0.000 | 0.00 | 0.00 | 211.5 | 2.1171 |
| M3 | 5 | 0.220 | 0.20 | 0.00 | 25.1 | 0.7552 |
| M4 | 5 | 0.093 | 0.00 | 0.00 | 95.8 | 0.9352 |
| M5 | 5 | 1.000 | 1.00 | 0.00 | 14.5 | 1.5501 |

## Aggregate /go Pareto point

- **cost (mean of per-axis mean_cost)**: $0.196
- **cost (total observed across all axes)**: $1.7644
- **score (mean of per-axis mean_score)**: 0.352
- **n_axes**: 9

> Cost figures are **best-effort from codeburn delta**; zero means the local codeburn dashboard was not reachable during the run. For the headline cost figure, rely on Anthropic billing reconciliation instead.

## Time-horizon estimate (coarse)

- **Note**: coarse — n=5 per axis; need n>=20 for stable estimate
- **Axes with success_rate >= 0.5**:
    - M5: 1.00
    - FM3: 0.60

## Per-axis success-rate bar

- BS1: ####                 0.20
- FM3: ############         0.60
- FM4: ########             0.40
- FM5:                      0.00
- M1: ####                 0.20
- M2:                      0.00
- M3: ####                 0.20
- M4:                      0.00
- M5: #################### 1.00
