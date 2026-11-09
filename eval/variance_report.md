# PlaceGuard Multi-Run Variance Report

N = 3 independent full-suite runs. Each is a complete re-extraction via the real local LLM (`llama3.1:8b`), not a cached replay, so this reflects genuine run-to-run model variance.

## Per-run breakdown (PlaceGuard)

| Run | Accuracy | Macro-F1 | Temporal Acc | Provenance Acc | Unknown Acc | Errors | Mean Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Run 1 | 92.0% | 91.7% | 58.3% | 90.0% | 83.3% | 0 | 97736 ms |
| Run 2 | 92.0% | 91.7% | 58.3% | 90.0% | 83.3% | 0 | 96292 ms |
| Run 3 | 92.0% | 91.7% | 58.3% | 90.0% | 83.3% | 0 | 68407 ms |

## Aggregate (mean +/- sample std across runs) — PlaceGuard

- **Accuracy**: 92.0% (+/- 0.0%)
- **Macro-F1**: 91.7% (+/- 0.0%)
- **Temporal-conflict accuracy**: 58.3% (+/- 0.0%)
- **Provenance accuracy**: 90.0% (+/- 0.0%)
- **UNKNOWN-detection accuracy**: 83.3% (+/- 0.0%)
- **Hard-error cases per run**: 0.0 (+/- 0.0) out of 100
- **Mean per-case latency**: 87478 ms (+/- 16532 ms)

## Per-run breakdown (Baseline A — LLM-only)

| Run | Accuracy | Macro-F1 |
|---|---:|---:|
| Run 1 | 67.0% | 45.3% |
| Run 2 | 64.0% | 41.7% |
| Run 3 | 64.0% | 42.2% |

## Aggregate (mean +/- sample std across runs) — Baseline A (LLM-only)

- **Accuracy**: 65.0% (+/- 1.7%)
- **Macro-F1**: 43.1% (+/- 2.0%)

## Head-to-head (mean accuracy)

PlaceGuard leads Baseline A by **27.0%** mean accuracy (92.0% vs 65.0%).

## Hallucination rate / evidence support (single --with-explanation run)

This run's own eligibility accuracy: 88.0% (single run, not part of the variance average above — explanation generation adds an extra LLM call per case and was run once, not 3x, by explicit scope decision).

- **Total factual claims decomposed**: 374
- **Unsupported claims**: 27
- **Hallucination rate**: 7.2%
- **Evidence support rate**: 92.8%
