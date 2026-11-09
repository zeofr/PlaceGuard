#!/usr/bin/env python3
"""PlaceGuard Evaluation Harness — PlaceGuard (proposed system).

Runs every case in data/gold_set.json through the REAL end-to-end pipeline:

    raw notice/message/portal text --> LLM extraction --> reconciliation
    --> deterministic rule engine --> (optional) LLM explanation

and reports the metrics defined in PlaceGuard_Evaluation_Plan.md §26:

  • Eligibility accuracy, confusion matrix, Macro-F1
  • Temporal-conflict accuracy
  • Provenance accuracy
  • UNKNOWN-detection accuracy
  • Hallucination rate (only with --with-explanation)
  • Mean / P95 latency per pipeline stage

Nothing here writes to the live database or the live Chroma store — Facts are
built in-memory and reconciled with the pure `reconcile_facts()` function.

Usage (from project root):
    python eval/run_eval.py
    python eval/run_eval.py --with-explanation   # also measures hallucination rate (slow, needs LLM)
"""

from __future__ import annotations

import argparse
import json
import sys
import time

# Windows consoles often default to a legacy codepage that can't encode the
# ✓/✗ symbols used in the report below; force UTF-8 so this runs anywhere.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

from core.schemas import Criterion, SourceType, Student as StudentSchema
from database.models import Fact as FactModel
from explanation.generator import generate_explanation_with_citations
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_with_confidence
from ingestion.portal.adapter import PortalAdapter
from reconciliation.temporal_provenance_engine import RuleKey, reconcile_facts
from rules.eligibility_engine import evaluate_eligibility

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent.parent / "data"
GOLD_SET_FILE = DATA_DIR / "gold_set.json"
STUDENTS_FILE = DATA_DIR / "students.json"
NOTICES_FILE = DATA_DIR / "notices.json"
WHATSAPP_FILE = DATA_DIR / "whatsapp_messages.json"
SIS_FILE = DATA_DIR / "sis_data.json"

RESULTS_FILE = Path(__file__).parent / "placeguard_results.json"

_portal_adapter = PortalAdapter()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    case_id: str
    description: str
    drive_id: str
    student_id: str
    expected: str
    predicted: str
    correct: bool
    category: str
    channel: str
    temporal_required: bool
    temporal_correct: bool | None
    provenance_required: bool
    provenance_correct: bool | None
    expected_unknown: bool
    extraction_latency_ms: float
    reconciliation_latency_ms: float
    rule_engine_latency_ms: float
    explanation_latency_ms: float
    total_latency_ms: float
    unsupported_claims: int = 0
    total_claims: int = 0
    notes: str = ""
    error: str = ""


@dataclass
class EvalReport:
    total: int = 0
    correct: int = 0
    results: list[CaseResult] = field(default_factory=list)

    tp: dict[str, int] = field(default_factory=lambda: {"ELIGIBLE": 0, "INELIGIBLE": 0, "UNKNOWN": 0})
    fp: dict[str, int] = field(default_factory=lambda: {"ELIGIBLE": 0, "INELIGIBLE": 0, "UNKNOWN": 0})
    fn: dict[str, int] = field(default_factory=lambda: {"ELIGIBLE": 0, "INELIGIBLE": 0, "UNKNOWN": 0})

    temporal_total: int = 0
    temporal_correct: int = 0

    provenance_total: int = 0
    provenance_correct: int = 0

    unknown_total: int = 0
    unknown_correct: int = 0

    unsupported_claims: int = 0
    total_claims: int = 0

    latencies_by_stage: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )


# ---------------------------------------------------------------------------
# Source resolution — build an in-memory index of every notice/message/portal
# event keyed by the `source_id` referenced by gold_set.json's notices_in_scope.
# ---------------------------------------------------------------------------

def _load_source_index() -> dict[str, dict[str, Any]]:
    notices = json.loads(NOTICES_FILE.read_text(encoding="utf-8"))
    whatsapp = json.loads(WHATSAPP_FILE.read_text(encoding="utf-8"))
    sis = json.loads(SIS_FILE.read_text(encoding="utf-8"))["placement_events"]

    index: dict[str, dict[str, Any]] = {}
    company_to_drive: dict[str, str] = {}

    for item in notices + whatsapp:
        entry = {
            "drive_id": item["drive_id"],
            "source_type": item["source_type"],
            "timestamp": item["timestamp"],
            "channel": "email" if item["source_type"] in (
                "placement_cell_email", "official_company_pdf",
            ) else "whatsapp",
        }
        # Image-backed sources (OCR test cases) carry "image_path" instead of "text" —
        # the actual text is only known once extract_with_confidence() is about to run,
        # via a real OCR call in _build_extraction_cache() below.
        if "image_path" in item:
            entry["kind"] = "image"
            entry["image_path"] = item["image_path"]
        else:
            entry["kind"] = "text"
            entry["text"] = item["text"]
        index[item["source_id"]] = entry
        company_to_drive[item["company"].strip().upper()] = item["drive_id"]

    for event in sis:
        source_id = f"portal_{event['event_id']}"
        timestamp = event.get("portal_last_updated") or event.get("portal_posted_date")
        text = _portal_adapter._build_message_body(event)
        # Map to the SAME drive_id the email/WhatsApp channels use for this company
        # (production's load_portal_data.py derives its own drive_id from company_name,
        # which would NOT match — the gold set needs cross-channel reconciliation to
        # land on one shared drive_id, so look it up by company name instead).
        drive_id = company_to_drive.get(event["company_name"].strip().upper())
        if drive_id is None:
            raise ValueError(
                f"No matching drive_id found for SIS company '{event['company_name']}' "
                f"(event {event['event_id']}) — add a notices.json entry for this company first."
            )
        index[source_id] = {
            "kind": "portal",
            "drive_id": drive_id,
            "source_type": SourceType.STUDENT_PORTAL.value,
            "timestamp": timestamp,
            "text": text,
            "channel": "sis",
        }

    return index


def _load_students() -> dict[str, StudentSchema]:
    raw = json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))
    return {s["usn"]: StudentSchema(**s) for s in raw}


# ---------------------------------------------------------------------------
# Extraction cache — each source_id is extracted via the LLM at most once,
# no matter how many gold-set cases reference it.
# ---------------------------------------------------------------------------

def _build_extraction_cache(
    source_index: dict[str, dict[str, Any]],
    source_ids: set[str],
    llm_client,
) -> tuple[dict[str, list[FactModel]], dict[str, float]]:
    cache: dict[str, list[FactModel]] = {}
    latency: dict[str, float] = {}

    for source_id in sorted(source_ids):
        item = source_index.get(source_id)
        if item is None:
            cache[source_id] = []
            latency[source_id] = 0.0
            continue

        t0 = time.perf_counter()
        try:
            if item.get("kind") == "image":
                # Real OCR call, not pre-transcribed text — this is the whole point of
                # an OCR-sourced eval case (see extraction/ocr_client.py).
                from extraction.ocr_client import extract_text_from_image
                image_bytes = (Path(__file__).parent.parent / item["image_path"]).read_bytes()
                notice_text = extract_text_from_image(image_bytes)
            else:
                notice_text = item["text"]
            facts, _low_conf = extract_with_confidence(
                notice_text=notice_text,
                source_id=source_id,
                source_type=SourceType(item["source_type"]),
                timestamp=date_parser.parse(item["timestamp"]),
                drive_id=item["drive_id"],
                llm_client=llm_client,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced per-case below
            facts = []
            print(f"  [extraction error] {source_id}: {exc}")
        latency[source_id] = (time.perf_counter() - t0) * 1000
        cache[source_id] = facts

    return cache, latency


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _normalize_value(value: Any) -> Any:
    if isinstance(value, list):
        return set(str(v).strip().upper() for v in value)
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if isinstance(value, bool):
        return value
    return str(value).strip().upper()


def _values_equal(a: Any, b: Any) -> bool:
    return _normalize_value(a) == _normalize_value(b)


def _rules_comparison(
    reconciled: dict[RuleKey, FactModel],
    drive_id: str,
    expected_rules: dict[str, dict[str, Any]],
) -> tuple[bool, bool]:
    """Returns (value_match, provenance_match) across all expected criteria."""
    if not expected_rules:
        return True, True

    value_match = True
    provenance_match = True

    for criterion_type, expected in expected_rules.items():
        key = RuleKey(drive_id=drive_id, criterion_type=criterion_type, scope="ALL")
        winner = reconciled.get(key)
        if winner is None:
            value_match = False
            provenance_match = False
            continue

        try:
            winner_value = json.loads(winner.value)
        except (json.JSONDecodeError, TypeError):
            winner_value = winner.value

        # Note: criterion_type evaluators (rules/evaluators/*.py) hardcode their own
        # comparison semantics (e.g. max_backlogs is always "<=", allowed_branches is
        # always "in") and ignore Criterion.operator entirely, so the operator string
        # is documentation only here — grading compares the VALUE the engine actually
        # acts on, not the operator label the LLM happened to choose for it.
        if not _values_equal(winner_value, expected["value"]):
            value_match = False
        if winner.source_id != expected.get("authoritative_source"):
            provenance_match = False

    return value_match, provenance_match


def _build_criteria_from_reconciled(
    drive_id: str, reconciled: dict[RuleKey, FactModel]
) -> list[Criterion]:
    criteria = []
    for key, fact in reconciled.items():
        if key.drive_id != drive_id:
            continue
        if key.criterion_type == "deadline":
            # Deadlines compare against date.today() at evaluation time (see
            # rules/evaluators/deadline.py), so they are neither reproducible nor
            # assertable in a benchmark — the gold set never scores on them (per
            # PlaceGuard_Evaluation_Plan.md's own convention), so skip them here too.
            continue
        try:
            value = json.loads(fact.value)
        except (json.JSONDecodeError, TypeError):
            value = fact.value
        criteria.append(
            Criterion(
                drive_id=drive_id,
                criterion_type=key.criterion_type,
                operator=fact.operator,
                value=value,
                scope=key.scope,
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


def _case_channel(source_index: dict[str, dict[str, Any]], notices_in_scope: list[str]) -> str:
    channels = {source_index[s]["channel"] for s in notices_in_scope if s in source_index}
    if not channels:
        return "unknown"
    if len(channels) > 1:
        return "mixed"
    return next(iter(channels))


# ---------------------------------------------------------------------------
# Hallucination-rate claim checking (optional, --with-explanation)
# ---------------------------------------------------------------------------

CLAIM_EXTRACTION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["criterion_type", "claimed_value"],
        "properties": {
            "criterion_type": {"type": "string"},
            "claimed_value": {"type": ["string", "number"]},
        },
    },
}


def _decompose_claims(explanation: str, llm_client) -> list[dict[str, Any]]:
    prompt = f"""Decompose the following eligibility explanation into a JSON array of factual
claims. Each claim should name the criterion_type it refers to (one of: min_cgpa, max_backlogs,
allowed_branches, min_10th_pct, min_12th_pct, no_prior_offer) and the value that was claimed for
it (e.g. a number, branch name, or true/false).

EXPLANATION:
{explanation}

Return ONLY a JSON array of objects with keys "criterion_type" and "claimed_value".
"""
    try:
        data = llm_client.generate_structured(prompt=prompt, schema=CLAIM_EXTRACTION_SCHEMA, temperature=0.0)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("claims", data.get("items", []))
    return data if isinstance(data, list) else []


def _check_claims_supported(claims: list[dict[str, Any]], result) -> tuple[int, int]:
    evidence_types = {r.criterion.criterion_type for r in result.criterion_results}
    total = len(claims)
    unsupported = sum(1 for c in claims if c.get("criterion_type") not in evidence_types)
    return unsupported, total


# ---------------------------------------------------------------------------
# Core evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation(
    with_explanation: bool = False,
    case_ids: set[str] | None = None,
    limit: int | None = None,
) -> EvalReport:
    students = _load_students()
    gold_cases: list[dict] = json.loads(GOLD_SET_FILE.read_text(encoding="utf-8"))
    if case_ids:
        gold_cases = [c for c in gold_cases if c["case_id"] in case_ids]
    if limit:
        gold_cases = gold_cases[:limit]
    source_index = _load_source_index()

    all_source_ids: set[str] = set()
    for case in gold_cases:
        all_source_ids.update(case.get("notices_in_scope", []))

    print(f"Extracting facts for {len(all_source_ids)} unique sources (cached per source_id)...")
    llm_client = get_llm_client()
    extraction_cache, extraction_latency_by_source = _build_extraction_cache(
        source_index, all_source_ids, llm_client
    )

    explanation_generator = None
    if with_explanation:
        from explanation.generator import ExplanationGenerator
        explanation_generator = ExplanationGenerator(llm_client)

    report = EvalReport()

    for case in gold_cases:
        case_id = case["case_id"]
        student_id = case["student_id"]
        drive_id = case["drive_id"]
        expected = case["expected_eligibility"]
        expected_rules = case.get("expected_current_rules", {})
        notices_in_scope = case.get("notices_in_scope", [])
        temporal_req = case.get("temporal_reasoning_required", False)
        provenance_req = case.get("provenance_reasoning_required", False)
        expected_unknown = case.get("expected_unknown", False)
        category = case.get("category", "")
        channel = _case_channel(source_index, notices_in_scope)

        student = students.get(student_id)
        if student is None:
            report.results.append(CaseResult(
                case_id=case_id, description=case.get("description", ""), drive_id=drive_id,
                student_id=student_id, expected=expected, predicted="ERROR", correct=False,
                category=category, channel=channel, temporal_required=temporal_req,
                temporal_correct=None, provenance_required=provenance_req, provenance_correct=None,
                expected_unknown=expected_unknown, extraction_latency_ms=0.0,
                reconciliation_latency_ms=0.0, rule_engine_latency_ms=0.0, explanation_latency_ms=0.0,
                total_latency_ms=0.0, error=f"Student {student_id} not found in students.json",
            ))
            report.total += 1
            continue

        try:
            extraction_latency_ms = sum(
                extraction_latency_by_source.get(sid, 0.0) for sid in notices_in_scope
            )
            facts: list[FactModel] = []
            for sid in notices_in_scope:
                facts.extend(extraction_cache.get(sid, []))

            t0 = time.perf_counter()
            reconciled = reconcile_facts(facts)
            reconciliation_latency_ms = (time.perf_counter() - t0) * 1000

            value_match, provenance_match = _rules_comparison(reconciled, drive_id, expected_rules)

            criteria = _build_criteria_from_reconciled(drive_id, reconciled)

            t0 = time.perf_counter()
            result = evaluate_eligibility(student, criteria) if criteria else evaluate_eligibility(
                student, []
            )
            rule_engine_latency_ms = (time.perf_counter() - t0) * 1000
            predicted = result.status.value

            explanation_latency_ms = 0.0
            unsupported_claims = total_claims = 0
            if with_explanation and explanation_generator is not None:
                t0 = time.perf_counter()
                exp = explanation_generator.generate(result)
                claims = _decompose_claims(exp, llm_client)
                unsupported_claims, total_claims = _check_claims_supported(claims, result)
                explanation_latency_ms = (time.perf_counter() - t0) * 1000

        except Exception as exc:  # noqa: BLE001
            report.results.append(CaseResult(
                case_id=case_id, description=case.get("description", ""), drive_id=drive_id,
                student_id=student_id, expected=expected, predicted="ERROR", correct=False,
                category=category, channel=channel, temporal_required=temporal_req,
                temporal_correct=None, provenance_required=provenance_req, provenance_correct=None,
                expected_unknown=expected_unknown, extraction_latency_ms=0.0,
                reconciliation_latency_ms=0.0, rule_engine_latency_ms=0.0, explanation_latency_ms=0.0,
                total_latency_ms=0.0, error=str(exc),
            ))
            report.total += 1
            continue

        correct = predicted == expected
        total_latency_ms = (
            extraction_latency_ms + reconciliation_latency_ms + rule_engine_latency_ms + explanation_latency_ms
        )

        for cls in ("ELIGIBLE", "INELIGIBLE", "UNKNOWN"):
            if expected == cls and predicted == cls:
                report.tp[cls] += 1
            elif predicted == cls and expected != cls:
                report.fp[cls] += 1
            elif expected == cls and predicted != cls:
                report.fn[cls] += 1

        temporal_correct = None
        if temporal_req:
            temporal_correct = value_match
            report.temporal_total += 1
            if temporal_correct:
                report.temporal_correct += 1

        provenance_correct = None
        if provenance_req:
            provenance_correct = provenance_match
            report.provenance_total += 1
            if provenance_correct:
                report.provenance_correct += 1

        if expected_unknown:
            report.unknown_total += 1
            if predicted == "UNKNOWN":
                report.unknown_correct += 1

        report.unsupported_claims += unsupported_claims
        report.total_claims += total_claims

        for stage, lat in (
            ("extraction", extraction_latency_ms),
            ("reconciliation", reconciliation_latency_ms),
            ("rule_engine", rule_engine_latency_ms),
            ("explanation", explanation_latency_ms),
            ("total", total_latency_ms),
        ):
            report.latencies_by_stage[stage].append(lat)

        report.total += 1
        if correct:
            report.correct += 1

        report.results.append(CaseResult(
            case_id=case_id, description=case.get("description", ""), drive_id=drive_id,
            student_id=student_id, expected=expected, predicted=predicted, correct=correct,
            category=category, channel=channel, temporal_required=temporal_req,
            temporal_correct=temporal_correct, provenance_required=provenance_req,
            provenance_correct=provenance_correct, expected_unknown=expected_unknown,
            extraction_latency_ms=extraction_latency_ms,
            reconciliation_latency_ms=reconciliation_latency_ms,
            rule_engine_latency_ms=rule_engine_latency_ms,
            explanation_latency_ms=explanation_latency_ms, total_latency_ms=total_latency_ms,
            unsupported_claims=unsupported_claims, total_claims=total_claims,
            notes=case.get("notes", ""),
        ))

    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _pct(num: int, den: int) -> str:
    return f"{num}/{den} = {num/den:.1%}" if den else "N/A"


def _mean_p95(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    sorted_vals = sorted(values)
    p95_idx = max(0, int(len(sorted_vals) * 0.95) - 1)
    return mean, sorted_vals[p95_idx]


def print_report(report: EvalReport) -> None:
    SEP = "=" * 70

    print(SEP)
    print("  PlaceGuard — Evaluation Report (real pipeline)")
    print(SEP)

    print("\nCase-by-case results:\n")
    print(f"{'Case':<10} {'Expected':<12} {'Predicted':<12} {'Channel':<10} {'Lat':>9}  {'Pass'}")
    print("-" * 65)
    for r in report.results:
        tick = "✓" if r.correct else "✗"
        lat = f"{r.total_latency_ms:.0f} ms" if r.total_latency_ms else "ERROR"
        print(f"{r.case_id:<10} {r.expected:<12} {r.predicted:<12} {r.channel:<10} {lat:>9}  {tick}")
        if r.error:
            print(f"  └─ ERROR: {r.error}")

    accuracy = report.correct / report.total if report.total else 0.0
    print(f"\n{'─'*65}")
    print(f"  Eligibility accuracy : {report.correct}/{report.total} = {accuracy:.1%}")

    print("\n  Per-class metrics:\n")
    print(f"  {'Class':<12} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    f1_scores = []
    for cls in ("ELIGIBLE", "INELIGIBLE", "UNKNOWN"):
        p, r, f1 = _precision_recall_f1(report.tp[cls], report.fp[cls], report.fn[cls])
        f1_scores.append(f1)
        print(f"  {cls:<12} {p:>10.2%} {r:>8.2%} {f1:>8.2%}")
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    print(f"\n  Macro-F1             : {macro_f1:.2%}")

    print("\n  Sub-category accuracies:\n")
    print(f"  Temporal-conflict    : {_pct(report.temporal_correct, report.temporal_total)}")
    print(f"  Provenance-reasoning : {_pct(report.provenance_correct, report.provenance_total)}")
    print(f"  UNKNOWN detection    : {_pct(report.unknown_correct, report.unknown_total)}")

    if report.total_claims:
        halluc_rate = report.unsupported_claims / report.total_claims
        print(f"\n  Hallucination rate   : {report.unsupported_claims}/{report.total_claims} = {halluc_rate:.1%}")
        evidence_rate = 1 - halluc_rate
        print(f"  Evidence support rate: {evidence_rate:.1%}")

    print("\n  Latency by stage (mean / P95):\n")
    for stage in ("extraction", "reconciliation", "rule_engine", "explanation", "total"):
        mean, p95 = _mean_p95(report.latencies_by_stage.get(stage, []))
        print(f"  {stage:<16} mean={mean:8.2f} ms   P95={p95:8.2f} ms")

    print("\n  Accuracy by source channel:\n")
    by_channel: dict[str, list[CaseResult]] = defaultdict(list)
    for r in report.results:
        by_channel[r.channel].append(r)
    for channel, rows in sorted(by_channel.items()):
        correct = sum(1 for r in rows if r.correct)
        print(f"  {channel:<10} {correct}/{len(rows)} = {correct/len(rows):.1%}")

    print(f"\n  3×3 Confusion matrix (rows=actual, cols=predicted):\n")
    classes = ["ELIGIBLE", "INELIGIBLE", "UNKNOWN"]
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

    failures = [r for r in report.results if not r.correct and not r.error]
    if failures:
        print(f"\n  Failed cases ({len(failures)}):\n")
        for r in failures:
            print(f"  [{r.case_id}] {r.description}")
            print(f"    Expected: {r.expected}  |  Predicted: {r.predicted}  |  Notes: {r.notes}")
    else:
        print("\n  All cases passed ✓")

    print(SEP)


def save_results(report: EvalReport) -> None:
    payload = [
        {
            "case_id": r.case_id,
            "drive_id": r.drive_id,
            "student_id": r.student_id,
            "expected": r.expected,
            "predicted": r.predicted,
            "correct": r.correct,
            "category": r.category,
            "channel": r.channel,
            "temporal_required": r.temporal_required,
            "temporal_correct": r.temporal_correct,
            "provenance_required": r.provenance_required,
            "provenance_correct": r.provenance_correct,
            "expected_unknown": r.expected_unknown,
            "latency_ms": round(r.total_latency_ms, 2),
            "extraction_latency_ms": round(r.extraction_latency_ms, 2),
            "reconciliation_latency_ms": round(r.reconciliation_latency_ms, 2),
            "rule_engine_latency_ms": round(r.rule_engine_latency_ms, 2),
            "explanation_latency_ms": round(r.explanation_latency_ms, 2),
            "unsupported_claims": r.unsupported_claims,
            "total_claims": r.total_claims,
            "error": r.error,
        }
        for r in report.results
    ]
    RESULTS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nResults saved to {RESULTS_FILE}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-explanation", action="store_true",
        help="Also generate LLM explanations and measure hallucination rate (slower).",
    )
    parser.add_argument(
        "--cases", type=str, default=None,
        help="Comma-separated case_ids to run instead of the full gold set (e.g. CASE_001,CASE_024).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only run the first N cases of the gold set (applied after --cases, if both given).",
    )
    args = parser.parse_args()

    case_ids = set(args.cases.split(",")) if args.cases else None

    print("Running evaluation against the real pipeline (no DB/Chroma writes)...\n")
    report = run_evaluation(with_explanation=args.with_explanation, case_ids=case_ids, limit=args.limit)
    print_report(report)
    save_results(report)
