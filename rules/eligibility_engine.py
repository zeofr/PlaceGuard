"""Deterministic eligibility rule engine (DESIGN.md 1, 3.4).

No LLM call happens anywhere in this module. Every criterion is evaluated independently
(no short-circuiting), then aggregated by priority: any FAIL -> INELIGIBLE, else any
UNKNOWN -> UNKNOWN, else ELIGIBLE. A confirmed failure is always conclusive; missing data
is never silently treated as a pass.
"""

from __future__ import annotations

from core.schemas import Criterion, EligibilityResult, EligibilityStatus, Status, Student
from rules.evaluators import get_evaluator, registered_types

# Criterion types that carry metadata extracted from a notice (e.g. the
# registration form URL) rather than an eligibility rule. They have no
# evaluator and must never reach the rule engine — they still go through
# the same extraction/reconciliation pipeline as every other criterion type
# (so authority + recency resolve conflicting links the same way), callers
# just read them back directly instead of evaluating them here.
METADATA_ONLY_CRITERION_TYPES = {"registration_link"}


def evaluate_eligibility(student: Student, criteria: list[Criterion]) -> EligibilityResult:
    known_types = set(registered_types())
    evaluable: list[Criterion] = []
    for c in criteria:
        if c.criterion_type in METADATA_ONLY_CRITERION_TYPES:
            continue
        if c.criterion_type not in known_types:
            # Extraction can invent a criterion type we've never seen (a new
            # synonym, a field this system doesn't track, etc.). Treating this
            # as "no opinion" rather than crashing the whole eligibility check
            # matches how METADATA_ONLY_CRITERION_TYPES is already handled above.
            print(
                f"WARNING: No evaluator registered for criterion_type={c.criterion_type!r} "
                f"- skipping (not counted toward eligibility)."
            )
            continue
        evaluable.append(c)
    criteria = evaluable
    results = [get_evaluator(criterion.criterion_type)(criterion, student) for criterion in criteria]

    statuses = {result.status for result in results}
    if Status.FAIL in statuses:
        overall = EligibilityStatus.INELIGIBLE
    elif Status.UNKNOWN in statuses:
        overall = EligibilityStatus.UNKNOWN
    else:
        overall = EligibilityStatus.ELIGIBLE

    drive_id = criteria[0].drive_id if criteria else "UNKNOWN_DRIVE"
    return EligibilityResult(
        student_id=student.student_id,
        drive_id=drive_id,
        status=overall,
        criterion_results=results,
    )
