"""Evaluator for 'allowed_branches' criterion type.

The LLM extraction prompt uses 'allowed_branches' as the canonical criterion_type
for branch restrictions (e.g. "CSE/ISE only").  This evaluator handles that key
so the registry never raises a KeyError when the extraction stage produces it.

Note: the older 'branch' evaluator (branch.py) handles the same logic under the
key 'branch' — this module is a second registration under the LLM-preferred key.
Both keys resolve to the same evaluation logic.
"""

from __future__ import annotations

from core.schemas import Criterion, CriterionResult, Status, Student
from rules.evaluators.registry import register


@register("allowed_branches")
def evaluate_allowed_branches(criterion: Criterion, student: Student) -> CriterionResult:
    """Evaluate branch restriction expressed as an 'in' list.

    Criterion value is expected to be a list of allowed branch codes,
    e.g. ["CSE", "ISE"] or a comma-separated string "CSE,ISE".
    """
    if student.branch is None:
        return CriterionResult(
            criterion=criterion,
            status=Status.UNKNOWN,
            student_value=None,
            message="Student branch is not on record.",
        )

    # Normalise value: accept both list and comma-separated string
    raw = criterion.value
    student_branch = student.branch.strip().upper()

    if isinstance(raw, str) and raw.strip().upper() == "ALL":
        allowed = "ALL"
        passed = True
    else:
        if isinstance(raw, list):
            allowed = [b.strip().upper() for b in raw]
        elif isinstance(raw, str):
            allowed = [b.strip().upper() for b in raw.split(",")]
        else:
            allowed = [str(raw).upper()]
        passed = student_branch in allowed

    return CriterionResult(
        criterion=criterion,
        status=Status.PASS if passed else Status.FAIL,
        student_value=student.branch,
        message=(
            f"Branch {student.branch} is "
            f"{'' if passed else 'not '}one of the allowed branches {allowed}."
        ),
    )
