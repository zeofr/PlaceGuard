"""Evaluator for deadline criterion type.

A deadline criterion checks if the current date is before or equal to the registration deadline.
"""

from __future__ import annotations

from datetime import date, datetime

from dateutil import parser as date_parser

from core.schemas import Criterion, CriterionResult, Status, Student
from rules.evaluators.registry import register


@register("deadline")
def evaluate_deadline(criterion: Criterion, student: Student) -> CriterionResult:
    """Check if current date is before or at the registration deadline.
    
    The criterion value should be a date string (YYYY-MM-DD format) or date object.
    If the deadline has passed, the student cannot register (FAIL).
    If the deadline is today or in the future, registration is still open (PASS).
    """
    deadline_value = criterion.value
    
    # Parse the deadline if it's a string. Extraction normalizes deadlines to
    # either "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS" (notice_extractor.py's
    # normalize_deadline_value) depending on whether a time was mentioned, so
    # this must accept both.
    if isinstance(deadline_value, str):
        try:
            deadline_date = date_parser.parse(deadline_value).date()
        except (ValueError, TypeError):
            return CriterionResult(
                criterion=criterion,
                status=Status.UNKNOWN,
                student_value=None,
                message=f"Invalid deadline format: {deadline_value}. Expected YYYY-MM-DD.",
            )
    elif isinstance(deadline_value, date):
        deadline_date = deadline_value
    elif isinstance(deadline_value, datetime):
        deadline_date = deadline_value.date()
    else:
        return CriterionResult(
            criterion=criterion,
            status=Status.UNKNOWN,
            student_value=None,
            message=f"Unsupported deadline type: {type(deadline_value).__name__}",
        )
    
    # Get current date
    today = date.today()
    
    # Check if deadline has passed
    # operator should be "lte" meaning current_date <= deadline
    deadline_passed = today > deadline_date
    
    return CriterionResult(
        criterion=criterion,
        status=Status.FAIL if deadline_passed else Status.PASS,
        student_value=today.isoformat(),
        message=(
            f"Registration deadline is {deadline_date.isoformat()}. "
            f"{'Deadline has passed' if deadline_passed else 'Registration is still open'}."
        ),
    )
