"""Drive timeline routes — time-series view of company updates.

Every ingested notice produces one or more Facts (immutable, append-only).
This endpoint exposes those facts in chronological order so students can see
exactly how a drive's requirements evolved: what changed, when, and from which
source.  The current (reconciled) state is shown at the top; the full history
below it.
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.routes.auth import get_current_student
from database.connection import get_db
from database.crud import get_current_criteria, get_drive, get_drive_timeline
from database.models import Student
from rules.eligibility_engine import METADATA_ONLY_CRITERION_TYPES

router = APIRouter(prefix="/timeline", tags=["timeline"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TimelineEvent(BaseModel):
    """One extracted fact in the drive's history."""

    fact_id: int
    criterion_type: str
    operator: str
    value: str          # raw JSON-serialised value from the Fact table
    scope: str
    source_type: str
    source_id: str
    authority_rank: int
    timestamp: datetime
    is_correction: bool
    supersedes_ref: str | None
    raw_notice_snippet: str | None  # first 300 chars of the original notice

    class Config:
        from_attributes = True


class CurrentCriterion(BaseModel):
    """Reconciled (current authoritative) criterion for a drive."""

    criterion_type: str
    operator: str
    value: str
    scope: str
    source_type: str
    authority_rank: int
    timestamp: datetime

    class Config:
        from_attributes = True


class DriveTimelineResponse(BaseModel):
    drive_id: str
    company_name: str
    status: str
    deadline: datetime | None
    registration_link: str | None   # only populated for eligible students
    current_criteria: list[CurrentCriterion]
    timeline: list[TimelineEvent]
    total_events: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOURCE_LABEL: dict[str, str] = {
    "official_company_pdf": "Official Company PDF",
    "placement_cell_whatsapp": "Placement Cell WhatsApp",
    "placement_cell_email": "Placement Cell Email",
    "coordinator_whatsapp": "Coordinator WhatsApp",
    "student_portal": "Student Portal",
    "student_whatsapp": "Student WhatsApp",
}


def _snippet(text: str | None, max_len: int = 300) -> str | None:
    if not text:
        return None
    return text[:max_len] + ("…" if len(text) > max_len else "")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/{drive_id}", response_model=DriveTimelineResponse)
def get_drive_timeline_view(
    drive_id: str,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    """Return the full update history for a placement drive.

    - ``current_criteria`` — the reconciled, authoritative requirements right now
    - ``timeline`` — every fact extracted from every source, oldest first,
      each tagged with its source type, authority rank, and whether it was
      marked as a correction

    The ``registration_link`` field is only populated if the requesting student
    is already registered (i.e. was confirmed eligible and clicked register).
    Call ``POST /eligibility/check`` to get the link when eligible.
    """
    drive = get_drive(db, drive_id)
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")

    # Current reconciled criteria (metadata like registration_link is excluded
    # from this "requirements" list — it's surfaced separately below)
    criteria_db = get_current_criteria(db, drive_id)
    current = [
        CurrentCriterion.model_validate(c)
        for c in criteria_db
        if c.criterion_type not in METADATA_ONLY_CRITERION_TYPES
    ]

    # Full chronological fact log
    facts = get_drive_timeline(db, drive_id)
    events: list[TimelineEvent] = []
    for f in facts:
        events.append(
            TimelineEvent(
                fact_id=f.id,
                criterion_type=f.criterion_type,
                operator=f.operator,
                value=f.value,
                scope=f.scope,
                source_type=_SOURCE_LABEL.get(f.source_type, f.source_type),
                source_id=f.source_id,
                authority_rank=f.authority_rank,
                timestamp=f.timestamp,
                is_correction=f.is_correction,
                supersedes_ref=f.supersedes_ref,
                raw_notice_snippet=_snippet(f.raw_notice_text),
            )
        )

    # Only reveal the registration link if the student has already registered.
    # The link itself comes from the same reconciled criteria as everything
    # else (criterion_type="registration_link"), not a separately-set field.
    from database.crud import get_registration
    reg = get_registration(db, student.usn, drive_id)
    reg_link = None
    if reg:
        link_criterion = next(
            (c for c in criteria_db if c.criterion_type == "registration_link"), None
        )
        if link_criterion:
            reg_link = json.loads(link_criterion.value)

    return DriveTimelineResponse(
        drive_id=drive.drive_id,
        company_name=drive.company_name,
        status=drive.status,
        deadline=drive.deadline,
        registration_link=reg_link,
        current_criteria=current,
        timeline=events,
        total_events=len(events),
    )
