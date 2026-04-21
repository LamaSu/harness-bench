# Sweep summary — v1-smoke

- **harness**: claude_code_go
- **model**: claude-sonnet-4-6
- **max_samples_per_axis**: 5
- **timeout_per_sample_s**: 600
- **n_axes (planned)**: 9
- **n_rows (observed)**: 20
- **start_iso**: 2026-04-21T18:59:39.680236+00:00
- **end_iso**: 2026-04-21T19:17:40.189151+00:00

## Per-axis stats

| Axis | N | Mean score | Success rate | Error rate | Mean wall (s) | Sum cost ($) |
|------|---|-----------|--------------|-----------|---------------|-------------|
| BS1 | 5 | 0.684 | 0.60 | 0.00 | 138.2 | 0.0000 |
| FM3 | 5 | 0.620 | 0.80 | 0.00 | 13.3 | 0.0000 |
| FM4 | 5 | 0.900 | 0.80 | 0.00 | 22.1 | 0.0000 |
| FM5 | 5 | 0.528 | 0.00 | 0.00 | 29.8 | 0.0000 |

## Aggregate /go Pareto point

- **cost (mean of per-axis mean_cost)**: $0.0
- **cost (total observed across all axes)**: $0.0
- **score (mean of per-axis mean_score)**: 0.683
- **n_axes**: 4

> Cost figures are **best-effort from codeburn delta**; zero means the local codeburn dashboard was not reachable during the run. For the headline cost figure, rely on Anthropic billing reconciliation instead.

## Time-horizon estimate (coarse)

- **Note**: coarse — n=5 per axis; need n>=20 for stable estimate
- **Axes with success_rate >= 0.5**:
    - FM3: 0.80
    - FM4: 0.80
    - BS1: 0.60

## Per-axis success-rate bar

- BS1: ############         0.60
- FM3: ################     0.80
- FM4: ################     0.80
- FM5:                      0.00
