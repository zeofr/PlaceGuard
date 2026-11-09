#!/usr/bin/env python3
"""Aggregate multiple eval/run_eval.py (+ baseline_llm_only.py) runs into a
mean +/- std variance report, plus the hallucination/evidence-support numbers
from a single --with-explanation run.

Reads the raw per-case result JSON files saved by each run (same shape
eval/run_eval.py::save_results() and eval/baseline_llm_only.py write), so it
recomputes every aggregate metric from case-level data rather than scraping
printed report text.

Usage (from project root), after the runs have been produced into
eval/variance_runs/ (see run_variance_suite.sh / this session's commands):
    python -m eval.compute_variance
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from eval.run_eval import _mean_p95, _precision_recall_f1  # noqa: E402

VARIANCE_DIR = Path(__file__).parent / "variance_runs"
REPORT_FILE = Path(__file__).parent / "variance_report.md"

CLASSES = ("ELIGIBLE", "INELIGIBLE", "UNKNOWN")


def _load(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metrics_from_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    correct = sum(1 for c in cases if c["correct"])
    accuracy = correct / total if total else 0.0

    tp = {c: 0 for c in CLASSES}
    fp = {c: 0 for c in CLASSES}
    fn = {c: 0 for c in CLASSES}
    for c in cases:
        expected, predicted = c["expected"], c["predicted"]
        for cls in CLASSES:
            if expected == cls and predicted == cls:
                tp[cls] += 1
            elif predicted == cls and expected != cls:
                fp[cls] += 1
            elif expected == cls and predicted != cls:
                fn[cls] += 1

    f1_scores = []
    per_class = {}
    for cls in CLASSES:
        p, r, f1 = _precision_recall_f1(tp[cls], fp[cls], fn[cls])
        per_class[cls] = {"precision": p, "recall": r, "f1": f1}
        f1_scores.append(f1)
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    temporal_cases = [c for c in cases if c.get("temporal_required")]
    temporal_correct = sum(1 for c in temporal_cases if c.get("temporal_correct"))
    temporal_acc = temporal_correct / len(temporal_cases) if temporal_cases else None

    provenance_cases = [c for c in cases if c.get("provenance_required")]
    provenance_correct = sum(1 for c in provenance_cases if c.get("provenance_correct"))
    provenance_acc = provenance_correct / len(provenance_cases) if provenance_cases else None

    unknown_cases = [c for c in cases if c.get("expected_unknown")]
    unknown_correct = sum(1 for c in unknown_cases if c["predicted"] == "UNKNOWN")
    unknown_acc = unknown_correct / len(unknown_cases) if unknown_cases else None

    latencies = [c["latency_ms"] for c in cases if c.get("latency_ms")]
    mean_lat, p95_lat = _mean_p95(latencies)

    error_count = sum(1 for c in cases if c.get("error"))

    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "temporal_accuracy": temporal_acc,
        "provenance_accuracy": provenance_acc,
        "unknown_accuracy": unknown_acc,
        "mean_latency_ms": mean_lat,
        "p95_latency_ms": p95_lat,
        "error_count": error_count,
    }


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


def _fmt_pct(mean: float, std: float) -> str:
    return f"{mean:.1%} (+/- {std:.1%})"


def _aggregate(run_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    acc_mean, acc_std = _mean_std([m["accuracy"] for m in run_metrics])
    f1_mean, f1_std = _mean_std([m["macro_f1"] for m in run_metrics])

    temporal_vals = [m["temporal_accuracy"] for m in run_metrics if m["temporal_accuracy"] is not None]
    provenance_vals = [m["provenance_accuracy"] for m in run_metrics if m["provenance_accuracy"] is not None]
    unknown_vals = [m["unknown_accuracy"] for m in run_metrics if m["unknown_accuracy"] is not None]
    error_vals = [m["error_count"] for m in run_metrics]
    lat_mean_vals = [m["mean_latency_ms"] for m in run_metrics]

    return {
        "accuracy_mean": acc_mean, "accuracy_std": acc_std,
        "macro_f1_mean": f1_mean, "macro_f1_std": f1_std,
        "temporal_mean_std": _mean_std(temporal_vals) if temporal_vals else (None, None),
        "provenance_mean_std": _mean_std(provenance_vals) if provenance_vals else (None, None),
        "unknown_mean_std": _mean_std(unknown_vals) if unknown_vals else (None, None),
        "error_count_mean_std": _mean_std(error_vals),
        "mean_latency_mean_std": _mean_std(lat_mean_vals),
    }


def main() -> None:
    run_files = sorted(VARIANCE_DIR.glob("placeguard_results_run*.json"))
    baseline_files = sorted(VARIANCE_DIR.glob("baseline_llm_only_results_run*.json"))

    if not run_files:
        print(f"No run files found in {VARIANCE_DIR} - run the variance suite first.")
        return

    print(f"Found {len(run_files)} PlaceGuard run(s), {len(baseline_files)} baseline run(s)\n")

    pg_run_metrics = [_metrics_from_cases(_load(f)) for f in run_files]
    bl_run_metrics = [_metrics_from_cases(_load(f)) for f in baseline_files] if baseline_files else []

    pg_agg = _aggregate(pg_run_metrics)
    bl_agg = _aggregate(bl_run_metrics) if bl_run_metrics else None

    lines = []
    lines.append("# PlaceGuard Multi-Run Variance Report\n")
    lines.append(f"N = {len(run_files)} independent full-suite runs. "
                  f"Each is a complete re-extraction via the real local LLM (`llama3.1:8b`), "
                  f"not a cached replay, so this reflects genuine run-to-run model variance.\n")

    lines.append("## Per-run breakdown (PlaceGuard)\n")
    lines.append("| Run | Accuracy | Macro-F1 | Temporal Acc | Provenance Acc | Unknown Acc | Errors | Mean Latency |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for i, m in enumerate(pg_run_metrics, 1):
        t = f"{m['temporal_accuracy']:.1%}" if m["temporal_accuracy"] is not None else "N/A"
        p = f"{m['provenance_accuracy']:.1%}" if m["provenance_accuracy"] is not None else "N/A"
        u = f"{m['unknown_accuracy']:.1%}" if m["unknown_accuracy"] is not None else "N/A"
        lines.append(
            f"| Run {i} | {m['accuracy']:.1%} | {m['macro_f1']:.1%} | {t} | {p} | {u} | "
            f"{m['error_count']} | {m['mean_latency_ms']:.0f} ms |"
        )

    lines.append("\n## Aggregate (mean +/- sample std across runs) — PlaceGuard\n")
    lines.append(f"- **Accuracy**: {_fmt_pct(pg_agg['accuracy_mean'], pg_agg['accuracy_std'])}")
    lines.append(f"- **Macro-F1**: {_fmt_pct(pg_agg['macro_f1_mean'], pg_agg['macro_f1_std'])}")
    t_mean, t_std = pg_agg["temporal_mean_std"]
    if t_mean is not None:
        lines.append(f"- **Temporal-conflict accuracy**: {_fmt_pct(t_mean, t_std)}")
    p_mean, p_std = pg_agg["provenance_mean_std"]
    if p_mean is not None:
        lines.append(f"- **Provenance accuracy**: {_fmt_pct(p_mean, p_std)}")
    u_mean, u_std = pg_agg["unknown_mean_std"]
    if u_mean is not None:
        lines.append(f"- **UNKNOWN-detection accuracy**: {_fmt_pct(u_mean, u_std)}")
    e_mean, e_std = pg_agg["error_count_mean_std"]
    lines.append(f"- **Hard-error cases per run**: {e_mean:.1f} (+/- {e_std:.1f}) out of {pg_run_metrics[0]['total']}")
    lat_mean, lat_std = pg_agg["mean_latency_mean_std"]
    lines.append(f"- **Mean per-case latency**: {lat_mean:.0f} ms (+/- {lat_std:.0f} ms)")

    if bl_agg:
        lines.append("\n## Per-run breakdown (Baseline A — LLM-only)\n")
        lines.append("| Run | Accuracy | Macro-F1 |")
        lines.append("|---|---:|---:|")
        for i, m in enumerate(bl_run_metrics, 1):
            lines.append(f"| Run {i} | {m['accuracy']:.1%} | {m['macro_f1']:.1%} |")

        lines.append("\n## Aggregate (mean +/- sample std across runs) — Baseline A (LLM-only)\n")
        lines.append(f"- **Accuracy**: {_fmt_pct(bl_agg['accuracy_mean'], bl_agg['accuracy_std'])}")
        lines.append(f"- **Macro-F1**: {_fmt_pct(bl_agg['macro_f1_mean'], bl_agg['macro_f1_std'])}")

        lines.append("\n## Head-to-head (mean accuracy)\n")
        gap = pg_agg["accuracy_mean"] - bl_agg["accuracy_mean"]
        lines.append(f"PlaceGuard leads Baseline A by **{gap:.1%}** mean accuracy "
                      f"({pg_agg['accuracy_mean']:.1%} vs {bl_agg['accuracy_mean']:.1%}).")

    # Hallucination rate from the single --with-explanation run, if present
    explanation_file = VARIANCE_DIR / "placeguard_results_explanation.json"
    if explanation_file.exists():
        exp_cases = _load(explanation_file)
        total_claims = sum(c.get("total_claims", 0) for c in exp_cases)
        unsupported = sum(c.get("unsupported_claims", 0) for c in exp_cases)
        exp_metrics = _metrics_from_cases(exp_cases)
        lines.append("\n## Hallucination rate / evidence support (single --with-explanation run)\n")
        lines.append(f"This run's own eligibility accuracy: {exp_metrics['accuracy']:.1%} "
                      f"(single run, not part of the variance average above — explanation generation "
                      f"adds an extra LLM call per case and was run once, not {len(run_files)}x, by "
                      f"explicit scope decision).\n")
        if total_claims:
            halluc_rate = unsupported / total_claims
            lines.append(f"- **Total factual claims decomposed**: {total_claims}")
            lines.append(f"- **Unsupported claims**: {unsupported}")
            lines.append(f"- **Hallucination rate**: {halluc_rate:.1%}")
            lines.append(f"- **Evidence support rate**: {1 - halluc_rate:.1%}")
        else:
            lines.append("- No claims were decomposed (0 total_claims) — see caveat below.")

    report = "\n".join(lines) + "\n"
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWritten to {REPORT_FILE}")


if __name__ == "__main__":
    main()
