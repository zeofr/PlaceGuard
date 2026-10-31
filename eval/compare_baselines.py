#!/usr/bin/env python3
"""Compare evaluation results across all systems.

Reads result JSON files produced by run_eval.py and baseline_llm_only.py and
prints the comparison table from PlaceGuard_Evaluation_Plan.md §21.

Usage (from project root):
    python eval/compare_baselines.py

Run each evaluation script first:
    python eval/run_eval.py          > eval/placeguard_results.json   (edit run_eval to save)
    python eval/baseline_llm_only.py                                  (saves automatically)
"""

from __future__ import annotations

import json
from pathlib import Path

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


def main() -> None:
    systems = [
        ("LLM-only (A)",       "baseline_llm_only_results.json"),
        ("PlaceGuard",         "placeguard_results.json"),
    ]

    print("\nPlaceGuard — Baseline Comparison Table")
    print("=" * 70)
    print(f"  {'System':<22} {'Accuracy':>10} {'Macro-F1':>10} {'Mean Latency':>14}")
    print(f"  {'─'*60}")

    for label, filename in systems:
        data = _load(filename)
        if data is None:
            print(f"  {label:<22} {'(no results file)'}")
            continue
        acc = _accuracy(data)
        mf1 = _macro_f1(data)
        lat = _mean_latency(data)
        print(f"  {label:<22} {acc:>10.1%} {mf1:>10.1%} {lat:>14}")

    print("=" * 70)
    print("\nNote: run each eval script to populate results files.")


if __name__ == "__main__":
    main()
