# PlaceGuard Evaluation — Trimmed Validation Run

**Status: validation pass only, not the final experiment.** This run used a 30-case
subset of the full 100-case `data/gold_set.json` (selected to touch every one of the
13 most structurally-interesting drives — the 7 fictional drives with real cross-source
conflicts, plus NVIDIA, KPMG, APTOS, BOEING, GE, HALCYON — covering all 3 ingestion
channels, every category, and both temporal and provenance reasoning) to validate that
the rewritten pipeline works end-to-end against the real local LLM (Ollama `llama3.1:8b`)
before committing to the much slower full 100-case / 45-unique-source run.

Run date: 2026-11-04. LLM provider: `ollama` (`llama3.1:8b`, local, `LLM_PROVIDER=ollama` in `.env`).

## Headline comparison (`eval/compare_baselines.py`)

| System | Accuracy | Macro-F1 | Hallucination | Temporal | Provenance | P95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| LLM-only (Baseline A) | 53.3% | 38.9% | N/A | N/A | N/A | 1,290 ms |
| **PlaceGuard** | **100.0%** | **100.0%** | N/A* | 8/8 = 100.0% | 8/9 = 88.9% | 58,573 ms |

*Hallucination rate requires `python -m eval.run_eval --with-explanation` (not run here — needs an
extra LLM call per case to generate and decompose explanations, would roughly double runtime).

## PlaceGuard detail (`eval/run_eval.py`, 30 cases)

- **Eligibility accuracy: 30/30 = 100%** (confusion matrix: 14 ELIGIBLE, 8 INELIGIBLE, 8 UNKNOWN, zero off-diagonal errors)
- **Per-class precision/recall/F1: 100% across ELIGIBLE, INELIGIBLE, UNKNOWN**
- **Temporal-conflict accuracy: 8/8 = 100%** — every case requiring temporal reasoning (deadline
  extensions, CGPA corrections, branch-list corrections) resolved to the value the real
  `reconcile_facts()` algorithm says is current.
- **Provenance accuracy: 8/9 = 88.9%** — one miss: `CASE_024` (`DRIVE_NIMBUSWORKS`,
  the outdated/forwarded-notice test). The final eligibility verdict was still correct
  (INELIGIBLE, matching ground truth) and the *value* reconciliation picked was right, but the
  reconciled `allowed_branches` fact was attributed to a different same-rank source than the gold
  set's `authoritative_source` — i.e. the LLM extraction didn't flag that specific restatement as a
  correction the same way the authored ground truth assumed. Worth a closer look in the full run,
  but it did not affect the eligibility decision.
- **Latency**: reconciliation and rule-engine stages are sub-millisecond (as expected for
  deterministic code); essentially all latency is local LLM extraction
  (mean 38.1s/case, P95 58.6s/case) — a function of running `llama3.1:8b` on local hardware, not of
  the architecture itself.
- **Accuracy by channel**: email-only 11/11 = 100%, mixed-channel 19/19 = 100%.

## Baseline A — LLM-only (`eval/baseline_llm_only.py`, same 30 cases)

**16/30 = 53.3% accuracy, Macro-F1 38.9%.** Failure pattern: the LLM-only baseline defaults to
ELIGIBLE whenever it can't confidently resolve a conflict, and systematically fails to produce
UNKNOWN even when information is genuinely missing (every UNKNOWN gold case was misclassified as
ELIGIBLE or INELIGIBLE) and fails most conflict/outdated-notice cases (`CASE_016`, `CASE_024`,
`CASE_032`, `CASE_062` — all cases requiring picking the authoritative source over a conflicting or
outdated one). This is exactly what H1/H2/H3 predict: a bare LLM, with no deterministic rule engine
and no temporal/provenance reasoning, cannot reliably reproduce the right answer on conflicting or
incomplete information — and it also cannot be trusted to abstain (say UNKNOWN) rather than guess.

## Retrieval — Recall@K (`eval/eval_retrieval.py`, same 30 cases)

| Recall@3 | Recall@5 | Recall@10 |
|---:|---:|---:|
| 100.0% | 100.0% | 100.0% |

Expected: the drive_id metadata filter alone narrows each query to a handful of candidate sources,
so recall is saturated. Recall@K is more informative on the full 100-case set where some drives have
more sources competing for the top-K slots.

## What this validates

- The full pipeline (raw text → LLM extraction → reconciliation → deterministic rule engine) runs
  correctly against a real local LLM, not just the deterministic components in isolation.
- The gold set's `expected_current_rules`, `expected_eligibility`, and `authoritative_source` values
  are self-consistent with the actual `reconcile_facts()` / `evaluate_eligibility()` implementations
  (not hand-typed guesses — see `data/gold_set.json`'s generation notes).
- A real, measurable gap between PlaceGuard and a bare LLM baseline exists and matches the
  project's research hypotheses.

## What's still outstanding

1. **Full 100-case run** — this was a 30-case subset chosen for speed (local Ollama inference is
   the bottleneck: ~38s mean per unique source extracted). The full run touches all 45 unique
   sources across all 22 drives; expect roughly 45 × ~35–60s ≈ 25–45 minutes for `run_eval.py` alone,
   plus ~100 × ~1s for `baseline_llm_only.py` (fast — one call per case, not per source).
2. **`--with-explanation` pass** — not run; needed for the Hallucination Rate / Evidence Support
   Rate metrics (§8/§9 of the plan).
3. **`CASE_024` provenance mismatch** — worth a manual look at the raw extraction output once the
   full run is available, to see whether it's a one-off LLM extraction quirk or a pattern worth
   tightening the extraction prompt for.
4. Load/throughput testing (§18) and the full §21 table with Standard RAG / RAG+DB rows are out of
   scope per the user's decision this session (Baseline A + PlaceGuard only).

## How to reproduce / extend

```bash
# Full 100-case run (slow — see latency note above)
python -m eval.run_eval
python -m eval.baseline_llm_only
python -m eval.eval_retrieval
python -m eval.compare_baselines

# Trimmed subset used for this validation pass
python -m eval.run_eval --cases CASE_001,CASE_004,CASE_006,...
```
