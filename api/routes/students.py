"""Student management routes (admin use — read-only for students via /auth/me)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.schemas import Student as StudentSchema
from database.connection import get_db
from database.crud import (
    create_student,
    get_student,
    get_students,
    search_students,
)

router = APIRouter(prefix="/students", tags=["students"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class StudentCreateRequest(BaseModel):
    """Admin-facing request to add a student record."""

    usn: str
    name: str
    date_of_birth: date
    cgpa: float | None = None
    branch: str | None = None
    backlogs: int | None = None
    has_prior_offer: bool | None = None
    tenth_pct: float | None = None
    twelfth_pct: float | None = None


class StudentResponse(BaseModel):
    """Public student profile (no date_of_birth exposed in list/get)."""

    usn: str
    student_id: str
    name: str
    branch: str | None
    cgpa: float | None
    backlogs: int | None
    has_prior_offer: bool | None
    tenth_pct: float | None
    twelfth_pct: float | None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=StudentResponse, status_code=201)
async def create_student_endpoint(
    request: StudentCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new student record (admin operation).

    In production this would be an admin-only route.
    For now it is open so synthetic data can be loaded via HTTP as well.
    """
    existing = get_student(db, request.usn)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Student with USN {request.usn} already exists.",
        )

    student_schema = StudentSchema(**request.model_dump())
    student = create_student(db, student_schema)
    return StudentResponse.model_validate(student)


@router.get("", response_model=list[StudentResponse])
async def list_students(
    branch: str | None = None,
    min_cgpa: float | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List students with optional filters."""
    if branch or min_cgpa is not None:
        students = search_students(db, branch=branch, min_cgpa=min_cgpa)
    else:
        students = get_students(db, skip=skip, limit=limit)

    return [StudentResponse.model_validate(s) for s in students]


@router.get("/{usn}", response_model=StudentResponse)
async def get_student_endpoint(
    usn: str,
    db: Session = Depends(get_db),
):
    """Get a student by USN."""
    student = get_student(db, usn)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return StudentResponse.model_validate(student)
