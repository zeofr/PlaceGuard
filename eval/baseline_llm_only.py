#!/usr/bin/env python3
"""Baseline A — LLM-only eligibility evaluation.

Sends the raw placement notice text + student profile directly to the LLM and
asks it to decide ELIGIBLE / INELIGIBLE / UNKNOWN without any deterministic rule
engine. Implements Baseline A from PlaceGuard_Evaluation_Plan.md §4.

Usage (from project root):
    python eval/baseline_llm_only.py

Requires a valid LLM API key in .env (GEMINI_API_KEY / OPENAI_API_KEY / CLAUDE_API_KEY).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from extraction.llm_client import get_llm_client

DATA_DIR = Path(__file__).parent.parent / "data"
GOLD_SET_FILE = DATA_DIR / "gold_set.json"
STUDENTS_FILE = DATA_DIR / "synthetic_students.json"
NOTICES_FILE = DATA_DIR / "synthetic_notices.json"

SYSTEM_PROMPT = """You are an eligibility decision engine for college placement drives.

You will be given:
1. A student's profile (CGPA, branch, backlogs, prior offer, 10th%, 12th%)
2. One or more placement notices about the drive

Your task: decide whether this student is eligible for the drive.

Reply with ONLY one of these three words (no explanation):
ELIGIBLE
INELIGIBLE
UNKNOWN

Use UNKNOWN only when you genuinely cannot determine eligibility from the information given.
"""


def build_prompt(student: dict, notices: list[dict]) -> str:
    notice_texts = "\n\n---\n\n".join(
        f"[{n['source_type'].upper()} | {n['timestamp']}]\n{n['text']}"
        for n in notices
    )
    return f"""STUDENT PROFILE:
{json.dumps(student, indent=2)}

PLACEMENT NOTICES:
{notice_texts}

Based on the above, is this student ELIGIBLE, INELIGIBLE, or UNKNOWN?"""


def run_baseline() -> None:
    students_raw = json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))
    students = {s["student_id"]: s for s in students_raw}

    notices_raw = json.loads(NOTICES_FILE.read_text(encoding="utf-8"))
    # Group notices by drive_id
    notices_by_drive: dict[str, list[dict]] = {}
    for n in notices_raw:
        notices_by_drive.setdefault(n["drive_id"], []).append(n)

    gold_cases = json.loads(GOLD_SET_FILE.read_text(encoding="utf-8"))

    try:
        llm = get_llm_client()
    except ValueError as e:
        print(f"Cannot initialise LLM client: {e}")
        print("Set the correct API key in your .env file.")
        return

    total = correct = 0
    results = []

    print(f"{'Case':<12} {'Expected':<12} {'Predicted':<12} {'Latency':>9}  {'Pass'}")
    print("-" * 55)

    for case in gold_cases:
        case_id = case["case_id"]
        student_id = case["student_id"]
        drive_id = case["drive_id"]
        expected = case["expected_eligibility"]
        in_scope = set(case.get("notices_in_scope", []))

        student = students.get(student_id)
        if student is None:
            print(f"{case_id:<12} {'?':<12} {'ERROR':<12} {'':>9}  ✗  (student not found)")
            total += 1
            continue

        notices = [
            n for n in notices_by_drive.get(drive_id, [])
            if n["notice_id"] in in_scope
        ]

        prompt = build_prompt(student, notices)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

        try:
            t0 = time.perf_counter()
            response = llm.generate(full_prompt, temperature=0.0)
            latency_ms = (time.perf_counter() - t0) * 1000

            # Extract the verdict — first word that matches one of the three states
            predicted = "UNKNOWN"
            for token in response.strip().split():
                token_upper = token.strip(".,!?").upper()
                if token_upper in ("ELIGIBLE", "INELIGIBLE", "UNKNOWN"):
                    predicted = token_upper
                    break
        except Exception as exc:
            print(f"{case_id:<12} {expected:<12} {'ERROR':<12} {'':>9}  ✗  ({exc})")
            total += 1
            results.append({"case_id": case_id, "expected": expected, "predicted": "ERROR", "error": str(exc)})
            continue

        correct_flag = predicted == expected
        tick = "✓" if correct_flag else "✗"
        lat = f"{latency_ms:.0f} ms"
        print(f"{case_id:<12} {expected:<12} {predicted:<12} {lat:>9}  {tick}")

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

    # Save results for comparison
    out_file = Path(__file__).parent / "baseline_llm_only_results.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to {out_file}")


if __name__ == "__main__":
    run_baseline()
