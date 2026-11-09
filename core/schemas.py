"""Shared Pydantic contracts used across ingestion, rules, and (later) extraction/reconciliation.

See DESIGN.md sections 3 and 6. Every stage of the pipeline reads/writes these types rather than
ad-hoc dicts, so new criteria, sources, or evaluators are additive instead of requiring edits here.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator
import re


class SenderRole(str, Enum):
    PLACEMENT_CELL = "placement_cell"
    COORDINATOR = "coordinator"
    STUDENT = "student"


class SourceType(str, Enum):
    """Maps to the authority ranking in DESIGN.md 3.1. Lower rank number = higher authority."""

    OFFICIAL_COMPANY_PDF = "official_company_pdf"
    PLACEMENT_CELL_WHATSAPP = "placement_cell_whatsapp"
    PLACEMENT_CELL_EMAIL = "placement_cell_email"
    COORDINATOR_WHATSAPP = "coordinator_whatsapp"
    STUDENT_PORTAL = "student_portal"
    STUDENT_WHATSAPP = "student_whatsapp"


SOURCE_AUTHORITY_RANK: dict[SourceType, int] = {
    SourceType.OFFICIAL_COMPANY_PDF: 1,
    SourceType.PLACEMENT_CELL_WHATSAPP: 2,
    SourceType.PLACEMENT_CELL_EMAIL: 2,
    SourceType.COORDINATOR_WHATSAPP: 3,
    SourceType.STUDENT_PORTAL: 4,
    SourceType.STUDENT_WHATSAPP: 5,
}


class RawMessage(BaseModel):
    """Normalized shape every SourceAdapter.fetch() must return, regardless of channel."""

    message_id: str
    source_type: SourceType
    sender_id: str
    sender_role: SenderRole
    timestamp: datetime
    body: str
    message_type: str = "text"  # "text" | "image", set in store.add_message
    is_forwarded: bool = False
    image_id: str | None = None  # resolvable via the WhatsApp console's GET /media/{image_id}


class Student(BaseModel):
    """Student profile used throughout the pipeline.

    usn is the canonical identifier and login credential.
    student_id is kept for backward-compat — defaults to usn if not supplied.
    """

    usn: str
    name: str
    date_of_birth: date | None = None

    # Backward-compat alias — callers that pass student_id still work
    student_id: str | None = None

    cgpa: float | None = None
    branch: str | None = None
    backlogs: int | None = None
    has_prior_offer: bool | None = None
    tenth_pct: float | None = None
    twelfth_pct: float | None = None

    @field_validator("usn")
    @classmethod
    def validate_usn(cls, v: str) -> str:
        """Validate USN format: 1MS<YY><BRANCH><NUMBER>  e.g. 1MS22CS042"""
        pattern = r"^1MS\d{2}[A-Z]{2,4}\d{2,4}$"
        if not re.match(pattern, v.upper()):
            raise ValueError(
                f"Invalid USN format '{v}'. "
                "Expected format: 1MS<YY><BRANCH><NUMBER>  e.g. 1MS22CS042"
            )
        return v.upper()

    def model_post_init(self, __context: Any) -> None:
        # Ensure student_id always has a value (for components that use it)
        if self.student_id is None:
            object.__setattr__(self, "student_id", self.usn)


class Criterion(BaseModel):
    """One structured, extracted eligibility requirement.

    (drive_id, criterion_type, scope) is the rule-key from DESIGN.md 3.3 — two criteria with the
    same key are considered the same rule for reconciliation purposes.
    """

    drive_id: str
    criterion_type: str
    operator: str  # "gte" | "lte" | "eq" | "in" | "not_in"
    value: Any
    scope: str = "ALL"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


class CriterionResult(BaseModel):
    criterion: Criterion
    status: Status
    student_value: Any = None
    message: str


class EligibilityResult(BaseModel):
    student_id: str
    drive_id: str
    status: EligibilityStatus
    criterion_results: list[CriterionResult]
