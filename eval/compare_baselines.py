#!/usr/bin/env python3
"""Compare evaluation results across all in-scope systems.

Reads result JSON files produced by run_eval.py and baseline_llm_only.py and
prints the §21 comparison table from PlaceGuard_Evaluation_Plan.md for the
two systems currently in scope (Baseline A: LLM-only, and PlaceGuard).
Standard RAG and RAG+Student DB rows are omitted entirely (not "TBD") since
those systems don't exist in this prototype.

Usage (from project root):
    python eval/compare_baselines.py

Run each evaluation script first:
    python eval/baseline_llm_only.py
    python eval/run_eval.py
    python eval/eval_retrieval.py   (optional, for the Recall@5 column)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EVAL_DIR = Path(__file__).parent


def _load(filename: str) -> list[dict] | None:
    p = EVAL_DIR / filename
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _accuracy(results: list[dict]) -> float:
    if not results:
        return 0.0
    correct = sum(1 for r in results if r.get("correct") or r.get("predicted") == r.get("expected"))
    return correct / len(results)


def _f1(results: list[dict], cls: str) -> float:
    tp = sum(1 for r in results if r.get("expected") == cls and r.get("predicted") == cls)
    fp = sum(1 for r in results if r.get("predicted") == cls and r.get("expected") != cls)
    fn = sum(1 for r in results if r.get("expected") == cls and r.get("predicted") != cls)
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * p * r / (p + r) if (p + r) else 0.0


def _macro_f1(results: list[dict]) -> float:
    scores = [_f1(results, cls) for cls in ("ELIGIBLE", "INELIGIBLE", "UNKNOWN")]
    return sum(scores) / len(scores)


def _mean_latency(results: list[dict]) -> str:
    lats = [r["latency_ms"] for r in results if "latency_ms" in r]
    return f"{sum(lats)/len(lats):.1f} ms" if lats else "N/A"


def _p95_latency(results: list[dict]) -> str:
    lats = sorted(r["latency_ms"] for r in results if "latency_ms" in r)
    if not lats:
        return "N/A"
    idx = max(0, int(len(lats) * 0.95) - 1)
    return f"{lats[idx]:.1f} ms"


def _sub_accuracy(results: list[dict], required_field: str, correct_field: str) -> str:
    rows = [r for r in results if r.get(required_field)]
    if not rows:
        return "N/A"
    correct = sum(1 for r in rows if r.get(correct_field))
    return f"{correct}/{len(rows)} = {correct/len(rows):.1%}"


def _hallucination_rate(results: list[dict]) -> str:
    total_claims = sum(r.get("total_claims", 0) for r in results)
    if not total_claims:
        return "N/A"
    unsupported = sum(r.get("unsupported_claims", 0) for r in results)
    return f"{unsupported/total_claims:.1%}"


def main() -> None:
    llm_only = _load("baseline_llm_only_results.json")
    placeguard = _load("placeguard_results.json")

    print("\nPlaceGuard — Baseline Comparison Table")
    print("=" * 100)
    header = (
        f"  {'System':<16} {'Accuracy':>9} {'Macro-F1':>9} {'Halluc.':>9} "
        f"{'Temporal':>12} {'Provenance':>12} {'P95 Latency':>12}"
    )
    print(header)
    print(f"  {'-'*96}")

    if llm_only is not None:
        print(
            f"  {'LLM-only (A)':<16} {_accuracy(llm_only):>9.1%} {_macro_f1(llm_only):>9.1%} "
            f"{'N/A':>9} {'N/A':>12} {'N/A':>12} {_p95_latency(llm_only):>12}"
        )
    else:
        print(f"  {'LLM-only (A)':<16} (no results file — run eval/baseline_llm_only.py first)")

    if placeguard is not None:
        print(
            f"  {'PlaceGuard':<16} {_accuracy(placeguard):>9.1%} {_macro_f1(placeguard):>9.1%} "
            f"{_hallucination_rate(placeguard):>9} "
            f"{_sub_accuracy(placeguard, 'temporal_required', 'temporal_correct'):>12} "
            f"{_sub_accuracy(placeguard, 'provenance_required', 'provenance_correct'):>12} "
            f"{_p95_latency(placeguard):>12}"
        )
    else:
        print(f"  {'PlaceGuard':<16} (no results file — run eval/run_eval.py first)")

    print("=" * 100)
    print(
        "\nNote: Standard RAG and RAG+Student DB rows are intentionally omitted — "
        "those baselines are out of scope for this prototype (see PlaceGuard_Evaluation_Plan.md §4)."
    )
    print("Run eval/eval_retrieval.py separately for Recall@K (not case-level, so not in this table).")


if __name__ == "__main__":
    main()
