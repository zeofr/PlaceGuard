# PlaceGuard Multi-Run Variance Report

N = 3 independent full-suite runs. Each is a complete re-extraction via the real local LLM (`llama3.1:8b`), not a cached replay, so this reflects genuine run-to-run model variance.

## Per-run breakdown (PlaceGuard)

| Run | Accuracy | Macro-F1 | Temporal Acc | Provenance Acc | Unknown Acc | Errors | Mean Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Run 1 | 96.2% | 94.9% | 92.3% | 81.8% | 83.3% | 0 | 49115 ms |
| Run 2 | 95.2% | 94.1% | 92.3% | 81.8% | 83.3% | 0 | 48589 ms |
| Run 3 | 91.3% | 89.8% | 92.3% | 81.8% | 75.0% | 0 | 50986 ms |

## Aggregate (mean +/- sample std across runs) — PlaceGuard

- **Accuracy**: 94.2% (+/- 2.5%)
- **Macro-F1**: 92.9% (+/- 2.7%)
- **Temporal-conflict accuracy**: 92.3% (+/- 0.0%)
- **Provenance accuracy**: 81.8% (+/- 0.0%)
- **UNKNOWN-detection accuracy**: 80.6% (+/- 4.8%)
- **Hard-error cases per run**: 0.0 (+/- 0.0) out of 104
- **Mean per-case latency**: 49563 ms (+/- 1260 ms)

## Per-run breakdown (Baseline A — LLM-only)

| Run | Accuracy | Macro-F1 |
|---|---:|---:|
| Run 1 | 65.4% | 43.1% |
| Run 2 | 67.3% | 45.1% |
| Run 3 | 67.3% | 45.1% |

## Aggregate (mean +/- sample std across runs) — Baseline A (LLM-only)

- **Accuracy**: 66.7% (+/- 1.1%)
- **Macro-F1**: 44.5% (+/- 1.2%)

## Head-to-head (mean accuracy)

PlaceGuard leads Baseline A by **27.6%** mean accuracy (94.2% vs 66.7%).

## Hallucination rate / evidence support (single --with-explanation run)

This run's own eligibility accuracy: 95.2% (single run, not part of the variance average above — explanation generation adds an extra LLM call per case and was run once, not 3x, by explicit scope decision).

- **Total factual claims decomposed**: 401
- **Unsupported claims**: 33
- **Hallucination rate**: 8.2%
- **Evidence support rate**: 91.8%
