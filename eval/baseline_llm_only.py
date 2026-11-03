#!/usr/bin/env python3
"""Baseline A — LLM-only eligibility evaluation.

Sends the raw notice/WhatsApp/portal text (all channels in `notices_in_scope`)
plus the student profile directly to the LLM and asks it to decide
ELIGIBLE / INELIGIBLE / UNKNOWN without any retrieval, reconciliation, or
deterministic rule engine. Implements Baseline A from
PlaceGuard_Evaluation_Plan.md §4.

Usage (from project root):
    python eval/baseline_llm_only.py

Requires a valid LLM API key in .env (GEMINI_API_KEY / OPENAI_API_KEY / CLAUDE_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from extraction.llm_client import get_llm_client

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent.parent / "data"
GOLD_SET_FILE = DATA_DIR / "gold_set.json"
STUDENTS_FILE = DATA_DIR / "students.json"

SYSTEM_PROMPT = """You are an eligibility decision engine for college placement drives.

You will be given:
1. A student's profile (CGPA, branch, backlogs, prior offer, 10th%, 12th%)
2. One or more raw messages about the drive (emails, WhatsApp messages, or portal records,
   in no particular order, possibly conflicting or outdated)

Your task: decide whether this student is eligible for the drive, using your own judgement
about which message is current and authoritative.

Reply with ONLY one of these three words (no explanation):
ELIGIBLE
INELIGIBLE
UNKNOWN

Use UNKNOWN only when you genuinely cannot determine eligibility from the information given.
"""


def build_prompt(student: dict, items: list[dict]) -> str:
    notice_texts = "\n\n---\n\n".join(
        f"[{item['source_type'].upper()} | {item['timestamp']} | id={source_id}]\n{item['text']}"
        for source_id, item in items
    )
    return f"""STUDENT PROFILE:
{json.dumps(student, indent=2)}

MESSAGES ABOUT THIS DRIVE:
{notice_texts}

Based on the above, is this student ELIGIBLE, INELIGIBLE, or UNKNOWN?"""


def run_baseline(case_ids: set[str] | None = None, limit: int | None = None) -> None:
    from eval.run_eval import _load_source_index  # local import avoids a cycle at module load

    students_raw = json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))
    students = {s["usn"]: s for s in students_raw}

    source_index = _load_source_index()
    gold_cases = json.loads(GOLD_SET_FILE.read_text(encoding="utf-8"))
    if case_ids:
        gold_cases = [c for c in gold_cases if c["case_id"] in case_ids]
    if limit:
        gold_cases = gold_cases[:limit]

    try:
        llm = get_llm_client()
    except ValueError as e:
        print(f"Cannot initialise LLM client: {e}")
        print("Set the correct API key in your .env file.")
        return

    total = correct = 0
    results = []

    print(f"{'Case':<10} {'Expected':<12} {'Predicted':<12} {'Latency':>9}  {'Pass'}")
    print("-" * 55)

    for case in gold_cases:
        case_id = case["case_id"]
        student_id = case["student_id"]
        expected = case["expected_eligibility"]
        in_scope = case.get("notices_in_scope", [])

        student = students.get(student_id)
        if student is None:
            print(f"{case_id:<10} {'?':<12} {'ERROR':<12} {'':>9}  x  (student not found)")
            total += 1
            continue

        items = [(sid, source_index[sid]) for sid in in_scope if sid in source_index]

        prompt = build_prompt(student, items)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

        try:
            t0 = time.perf_counter()
            response = llm.generate(full_prompt, temperature=0.0)
            latency_ms = (time.perf_counter() - t0) * 1000

            predicted = "UNKNOWN"
            for token in response.strip().split():
                token_upper = token.strip(".,!?").upper()
                if token_upper in ("ELIGIBLE", "INELIGIBLE", "UNKNOWN"):
                    predicted = token_upper
                    break
        except Exception as exc:
            print(f"{case_id:<10} {expected:<12} {'ERROR':<12} {'':>9}  x  ({exc})")
            total += 1
            results.append({"case_id": case_id, "expected": expected, "predicted": "ERROR", "error": str(exc)})
            continue

        correct_flag = predicted == expected
        tick = "v" if correct_flag else "x"
        lat = f"{latency_ms:.0f} ms"
        print(f"{case_id:<10} {expected:<12} {predicted:<12} {lat:>9}  {tick}")

        total += 1
        if correct_flag:
            correct += 1
        results.append({
            "case_id": case_id,
            "expected": expected,
            "predicted": predicted,
            "correct": correct_flag,
            "latency_ms": round(latency_ms, 2),
        })

    accuracy = correct / total if total else 0.0
    print(f"\nBaseline A (LLM-only) accuracy: {correct}/{total} = {accuracy:.1%}")

    out_file = Path(__file__).parent / "baseline_llm_only_results.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=str, default=None, help="Comma-separated case_ids to run.")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N cases.")
    args = parser.parse_args()
    case_ids = set(args.cases.split(",")) if args.cases else None
    run_baseline(case_ids=case_ids, limit=args.limit)
