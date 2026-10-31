#!/usr/bin/env python3
"""PlaceGuard Evaluation Harness — PlaceGuard (proposed system).

Runs every case in data/gold_set.json against the deterministic rule engine
and reports the metrics defined in PlaceGuard_Evaluation_Plan.md §26:

  • Eligibility accuracy
  • Macro-F1 (ELIGIBLE / INELIGIBLE / UNKNOWN)
  • Temporal-conflict accuracy
  • Provenance-reasoning accuracy
  • UNKNOWN-detection accuracy
  • Mean latency per evaluation call

Usage (from project root):
    python eval/run_eval.py

The evaluation harness works *without* an LLM key because it drives the
deterministic rule engine directly from the pre-reconciled gold-set rules.
LLM extraction is tested separately via the integration test suite.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.schemas import (
    Criterion,
    EligibilityStatus,
    Student as StudentSchema,
)
from database import init_db
from database.connection import get_db_context
from database import crud
from rules.eligibility_engine import evaluate_eligibility

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent.parent / "data"
GOLD_SET_FILE = DATA_DIR / "gold_set.json"
STUDENTS_FILE = DATA_DIR / "synthetic_students.json"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    case_id: str
    description: str
    expected: str
    predicted: str
    latency_ms: float
    correct: bool
    temporal_required: bool
    provenance_required: bool
    expected_unknown: bool
    notes: str = ""
    error: str = ""


@dataclass
class EvalReport:
    total: int = 0
    correct: int = 0
    results: list[CaseResult] = field(default_factory=list)

    # Per-class counts for confusion matrix / F1
    tp: dict[str, int] = field(default_factory=lambda: {"ELIGIBLE": 0, "INELIGIBLE": 0, "UNKNOWN": 0})
    fp: dict[str, int] = field(default_factory=lambda: {"ELIGIBLE": 0, "INELIGIBLE": 0, "UNKNOWN": 0})
    fn: dict[str, int] = field(default_factory=lambda: {"ELIGIBLE": 0, "INELIGIBLE": 0, "UNKNOWN": 0})

    temporal_total: int = 0
    temporal_correct: int = 0

    provenance_total: int = 0
    provenance_correct: int = 0

    unknown_total: int = 0
    unknown_correct: int = 0

    latencies_ms: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_students() -> dict[str, StudentSchema]:
    raw = json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))
    return {s["student_id"]: StudentSchema(**s) for s in raw}


def _build_criteria(case: dict[str, Any]) -> list[Criterion]:
    """Build Criterion objects from the gold-set's expected_current_rules."""
    rules: dict[str, dict] = case.get("expected_current_rules", {})
    criteria = []
    for criterion_type, rule in rules.items():
        criteria.append(
            Criterion(
                drive_id=case["drive_id"],
                criterion_type=criterion_type,
                operator=rule["operator"],
                value=rule["value"],
                scope=rule.get("scope", "ALL"),
            )
        )
    return criteria


def _precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return precision, recall, f1


# ---------------------------------------------------------------------------
# Core evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation() -> EvalReport:
    students = _load_students()
    gold_cases: list[dict] = json.loads(GOLD_SET_FILE.read_text(encoding="utf-8"))

    report = EvalReport()

    for case in gold_cases:
        case_id = case["case_id"]
        student_id = case["student_id"]
        expected = case["expected_eligibility"]
        temporal_req = case.get("temporal_reasoning_required", False)
        provenance_req = case.get("provenance_reasoning_required", False)
        expected_unknown = case.get("expected_unknown", False)

        student = students.get(student_id)
        if student is None:
            result = CaseResult(
                case_id=case_id,
                description=case.get("description", ""),
                expected=expected,
                predicted="ERROR",
                latency_ms=0.0,
                correct=False,
                temporal_required=temporal_req,
                provenance_required=provenance_req,
                expected_unknown=expected_unknown,
                error=f"Student {student_id} not found in synthetic_students.json",
            )
            report.results.append(result)
            report.total += 1
            continue

        criteria = _build_criteria(case)

        try:
            t0 = time.perf_counter()
            eligibility_result = evaluate_eligibility(student, criteria)
            latency_ms = (time.perf_counter() - t0) * 1000

            predicted = eligibility_result.status.value
        except Exception as exc:
            result = CaseResult(
                case_id=case_id,
                description=case.get("description", ""),
                expected=expected,
                predicted="ERROR",
                latency_ms=0.0,
                correct=False,
                temporal_required=temporal_req,
                provenance_required=provenance_req,
                expected_unknown=expected_unknown,
                error=str(exc),
            )
            report.results.append(result)
            report.total += 1
            continue

        correct = predicted == expected

        # Update confusion matrix
        classes = ["ELIGIBLE", "INELIGIBLE", "UNKNOWN"]
        for cls in classes:
            if expected == cls and predicted == cls:
                report.tp[cls] += 1
            elif predicted == cls and expected != cls:
                report.fp[cls] += 1
            elif expected == cls and predicted != cls:
                report.fn[cls] += 1

        # Temporal accuracy tracking
        if temporal_req:
            report.temporal_total += 1
            if correct:
                report.temporal_correct += 1

        # Provenance accuracy tracking
        if provenance_req:
            report.provenance_total += 1
            if correct:
                report.provenance_correct += 1

        # UNKNOWN detection tracking
        if expected_unknown:
            report.unknown_total += 1
            if predicted == "UNKNOWN":
                report.unknown_correct += 1

        report.latencies_ms.append(latency_ms)
        report.total += 1
        if correct:
            report.correct += 1

        report.results.append(
            CaseResult(
                case_id=case_id,
                description=case.get("description", ""),
                expected=expected,
                predicted=predicted,
                latency_ms=latency_ms,
                correct=correct,
                temporal_required=temporal_req,
                provenance_required=provenance_req,
                expected_unknown=expected_unknown,
                notes=case.get("notes", ""),
            )
        )

    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(report: EvalReport) -> None:
    SEP = "=" * 65

    print(SEP)
    print("  PlaceGuard — Evaluation Report")
    print(SEP)

    # ── Per-case results ────────────────────────────────────────────────────
    print("\nCase-by-case results:\n")
    print(f"{'Case':<12} {'Expected':<12} {'Predicted':<12} {'Latency':>9}  {'Pass'}")
    print("-" * 55)
    for r in report.results:
        tick = "✓" if r.correct else "✗"
        lat = f"{r.latency_ms:.2f} ms" if r.latency_ms else "  ERROR"
        print(f"{r.case_id:<12} {r.expected:<12} {r.predicted:<12} {lat:>9}  {tick}")
        if r.error:
            print(f"  └─ ERROR: {r.error}")

    # ── Accuracy ────────────────────────────────────────────────────────────
    accuracy = report.correct / report.total if report.total else 0.0
    print(f"\n{'─'*55}")
    print(f"  Eligibility accuracy : {report.correct}/{report.total} = {accuracy:.1%}")

    # ── Per-class precision / recall / F1 ───────────────────────────────────
    print("\n  Per-class metrics:\n")
    print(f"  {'Class':<12} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print(f"  {'─'*42}")
    f1_scores = []
    for cls in ["ELIGIBLE", "INELIGIBLE", "UNKNOWN"]:
        p, r, f1 = _precision_recall_f1(
            report.tp[cls], report.fp[cls], report.fn[cls]
        )
        f1_scores.append(f1)
        print(f"  {cls:<12} {p:>10.2%} {r:>8.2%} {f1:>8.2%}")
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    print(f"\n  Macro-F1             : {macro_f1:.2%}")

    # ── Sub-category accuracies ─────────────────────────────────────────────
    print(f"\n  Sub-category accuracies:\n")
    def _pct(num: int, den: int) -> str:
        return f"{num}/{den} = {num/den:.1%}" if den else "N/A"

    print(f"  Temporal-conflict    : {_pct(report.temporal_correct,  report.temporal_total)}")
    print(f"  Provenance-reasoning : {_pct(report.provenance_correct, report.provenance_total)}")
    print(f"  UNKNOWN detection    : {_pct(report.unknown_correct,    report.unknown_total)}")

    # ── Latency ─────────────────────────────────────────────────────────────
    if report.latencies_ms:
        mean_lat = sum(report.latencies_ms) / len(report.latencies_ms)
        sorted_lat = sorted(report.latencies_ms)
        p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)
        p95_lat = sorted_lat[p95_idx]
        print(f"\n  Rule-engine latency  : mean={mean_lat:.2f} ms  P95={p95_lat:.2f} ms")

    # ── Confusion matrix ────────────────────────────────────────────────────
    print(f"\n  3×3 Confusion matrix (rows=actual, cols=predicted):\n")
    classes = ["ELIGIBLE", "INELIGIBLE", "UNKNOWN"]
    # Build full matrix from TP/FP/FN
    matrix: dict[str, dict[str, int]] = {c: {cc: 0 for cc in classes} for c in classes}
    for r in report.results:
        if r.predicted in classes and r.expected in classes:
            matrix[r.expected][r.predicted] += 1
    header = f"  {'':>12}" + "".join(f"{c:>12}" for c in classes)
    print(header)
    for row_cls in classes:
        row_vals = "".join(f"{matrix[row_cls][col_cls]:>12}" for col_cls in classes)
        print(f"  {row_cls:>12}{row_vals}")

    print(f"\n{SEP}")

    # ── Failures ────────────────────────────────────────────────────────────
    failures = [r for r in report.results if not r.correct and not r.error]
    if failures:
        print("\n  Failed cases:\n")
        for r in failures:
            print(f"  [{r.case_id}] {r.description}")
            print(f"    Expected: {r.expected}  |  Predicted: {r.predicted}")
            print(f"    Notes   : {r.notes}")
    else:
        print("\n  All cases passed ✓")

    print(SEP)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Initialising database …")
    init_db()

    print("Running evaluation …\n")
    report = run_evaluation()
    print_report(report)
