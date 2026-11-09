#!/usr/bin/env python3
"""Generate a blind verification worksheet from data/gold_set.json.

For a stratified sample of gold-set cases (covering every category), this
writes ONLY the raw inputs a human would need to independently derive the
expected answer by hand:
  - the student's raw profile (data/students.json)
  - every raw notice/WhatsApp/portal message in that case's notices_in_scope,
    in chronological order, exactly as the real pipeline would see it

It deliberately OMITS everything from gold_set.json that encodes or hints at
the answer: expected_current_rules, expected_eligibility, expected_unknown,
temporal_reasoning_required, provenance_reasoning_required, category,
description, and notes. Only case_id, drive_id, and student_id are kept (as
bare identifiers, not answers) so results can be cross-referenced afterward.

Usage (from project root):
    python -m eval.generate_verification_worksheet
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from eval.run_eval import _load_source_index, _load_students, DATA_DIR  # noqa: E402

GOLD_SET_FILE = DATA_DIR / "gold_set.json"
OUTPUT_FILE = Path(__file__).parent.parent / "gold_set_verification.md"

SAMPLE_PER_CATEGORY = 3  # capped at however many exist in a small category
RANDOM_SEED = 42


def _pick_stratified_sample(gold_cases: list[dict]) -> list[dict]:
    by_category: dict[str, list[dict]] = {}
    for c in gold_cases:
        by_category.setdefault(c.get("category", ""), []).append(c)

    rng = random.Random(RANDOM_SEED)
    sample = []
    for category, cases in sorted(by_category.items()):
        k = min(SAMPLE_PER_CATEGORY, len(cases))
        sample.extend(rng.sample(cases, k))
    # Stable order for the worksheet: by case_id
    sample.sort(key=lambda c: c["case_id"])
    return sample


def _format_student(student) -> str:
    lines = [
        f"- USN: `{student.usn}`",
        f"- Name: {student.name}",
        f"- Date of birth: {student.date_of_birth}",
        f"- CGPA: {student.cgpa if student.cgpa is not None else '**(not on record)**'}",
        f"- Branch: {student.branch if student.branch is not None else '**(not on record)**'}",
        f"- Backlogs: {student.backlogs if student.backlogs is not None else '**(not on record)**'}",
        f"- Has prior offer: {student.has_prior_offer if student.has_prior_offer is not None else '**(not on record)**'}",
        f"- 10th percentage: {student.tenth_pct if student.tenth_pct is not None else '**(not on record)**'}",
        f"- 12th percentage: {student.twelfth_pct if student.twelfth_pct is not None else '**(not on record)**'}",
    ]
    return "\n".join(lines)


def _format_message(source_id: str, item: dict) -> str:
    return (
        f"**[{item['timestamp']}] {item['source_type']}** (source_id: `{source_id}`)\n\n"
        f"> {item['text'].replace(chr(10), chr(10) + '> ')}\n"
    )


def _format_expected_answer(case: dict) -> str:
    lines = [f"**Eligibility:** {case.get('expected_eligibility', '(not set)')}"]
    lines.append(f"**Expected UNKNOWN case:** {case.get('expected_unknown', False)}")
    lines.append(f"**Category:** {case.get('category', '(none)')}")
    lines.append(f"**Temporal reasoning required:** {case.get('temporal_reasoning_required', False)}")
    lines.append(f"**Provenance reasoning required:** {case.get('provenance_reasoning_required', False)}")

    expected_rules = case.get("expected_current_rules", {})
    lines.append("\n**Expected current rules (the reconciled winner per criterion):**")
    if not expected_rules:
        lines.append("- *(none — no criteria are asserted for this drive/case)*")
    else:
        for criterion_type, rule in expected_rules.items():
            value = rule.get("value")
            operator = rule.get("operator")
            source = rule.get("authoritative_source")
            lines.append(f"- `{criterion_type}` {operator} `{value}` — authoritative source: `{source}`")

    if case.get("description"):
        lines.append(f"\n**Description:** {case['description']}")
    if case.get("notes"):
        lines.append(f"\n**Notes:** {case['notes']}")

    return "\n".join(lines) + "\n"


def main() -> None:
    gold_cases = json.loads(GOLD_SET_FILE.read_text(encoding="utf-8"))
    students = _load_students()
    source_index = _load_source_index()

    sample = _pick_stratified_sample(gold_cases)

    lines = []
    lines.append("# Gold Set Verification Worksheet\n")
    lines.append(
        f"A stratified random sample of **{len(sample)}** cases out of the full "
        f"{len(gold_cases)}-case `data/gold_set.json`, covering every category "
        f"(random seed {RANDOM_SEED}, up to {SAMPLE_PER_CATEGORY} per category).\n"
    )
    lines.append(
        "**Purpose**: independently derive the expected eligibility for each case below, "
        "using ONLY the student profile and raw messages shown — not the gold set's own "
        "`expected_*` fields, not the database, not `rules/evaluators/*.py` or "
        "`reconciliation/temporal_provenance_engine.py`. Apply only the stated rules: "
        "higher authority rank wins regardless of recency; among same-rank sources, an "
        "explicit correction (or otherwise the latest timestamp) wins; CGPA/percentage "
        "thresholds are minimums; backlog limits are maximums; branch lists are exact-match; "
        "any criterion with no stated rule is simply not checked; missing student data for a "
        "checked criterion means UNKNOWN unless something else already fails outright.\n"
    )
    lines.append(
        "Each case below shows the raw input (student profile + messages) followed by "
        "`data/gold_set.json`'s own expected answer and reasoning for that case. To do a "
        "**blind** pass, work out your own ELIGIBLE / INELIGIBLE / UNKNOWN answer from the "
        "raw input before reading the \"Expected answer\" section, then compare.\n"
    )
    lines.append("---\n")

    for case in sample:
        case_id = case["case_id"]
        drive_id = case["drive_id"]
        student_id = case["student_id"]
        notices_in_scope = case.get("notices_in_scope", [])

        lines.append(f"## {case_id}\n")
        lines.append(f"**Drive:** `{drive_id}`  |  **Student:** `{student_id}`\n")

        student = students.get(student_id)
        lines.append("### Student profile\n")
        if student is None:
            lines.append(f"**(no student record found for `{student_id}`)**\n")
        else:
            lines.append(_format_student(student) + "\n")

        lines.append("### Messages (chronological order)\n")
        if not notices_in_scope:
            lines.append("**(no messages in scope for this case)**\n")
        else:
            items = []
            for source_id in notices_in_scope:
                item = source_index.get(source_id)
                if item is None:
                    items.append((source_id, None))
                else:
                    items.append((source_id, item))
            items.sort(key=lambda si: si[1]["timestamp"] if si[1] else "")
            for i, (source_id, item) in enumerate(items, 1):
                if item is None:
                    lines.append(f"{i}. **(source `{source_id}` not found)**\n")
                else:
                    lines.append(f"{i}. {_format_message(source_id, item)}")

        lines.append("### Expected answer (from `data/gold_set.json`)\n")
        lines.append(_format_expected_answer(case))

        lines.append("\n---\n")

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(sample)} cases to {OUTPUT_FILE}")
    by_category: dict[str, int] = {}
    for c in sample:
        by_category[c.get("category", "")] = by_category.get(c.get("category", ""), 0) + 1
    print("Sample composition:", by_category)


if __name__ == "__main__":
    main()
