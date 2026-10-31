#!/usr/bin/env python3
"""Load synthetic student and drive data into the database.

Run once to seed the database before running tests or the evaluation harness.

Usage (from project root):
    python data/load_synthetic_data.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from core.schemas import Student as StudentSchema
from database import crud, init_db
from database.connection import get_db_context

DATA_DIR = Path(__file__).parent
STUDENTS_FILE = DATA_DIR / "synthetic_students.json"
NOTICES_FILE  = DATA_DIR / "synthetic_notices.json"


def load_students(db) -> int:
    """Insert synthetic students. Skip if already present."""
    students = json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))
    inserted = 0
    for s in students:
        existing = crud.get_student_by_usn(db, s["usn"])
        if existing:
            continue

        dob_raw = s.get("date_of_birth")
        dob = date.fromisoformat(dob_raw) if dob_raw else None

        crud.create_student(
            db,
            StudentSchema(
                usn=s["usn"],
                name=s["name"],
                date_of_birth=dob,
                cgpa=s.get("cgpa"),
                branch=s.get("branch"),
                backlogs=s.get("backlogs"),
                has_prior_offer=s.get("has_prior_offer"),
                tenth_pct=s.get("tenth_pct"),
                twelfth_pct=s.get("twelfth_pct"),
            ),
        )
        inserted += 1
    return inserted


def load_drives(db) -> int:
    """Create unique drives referenced in synthetic_notices.json."""
    notices = json.loads(NOTICES_FILE.read_text(encoding="utf-8"))
    seen: set[str] = set()
    inserted = 0
    for n in notices:
        drive_id = n["drive_id"]
        if drive_id in seen:
            continue
        seen.add(drive_id)
        if crud.get_drive(db, drive_id):
            continue
        crud.create_drive(db, drive_id=drive_id, company_name=n["company"])
        inserted += 1
    return inserted


def main() -> None:
    print("Initialising database …")
    init_db()

    with get_db_context() as db:
        s = load_students(db)
        d = load_drives(db)
        print(f"  Inserted {s} student(s), {d} drive(s).")

    print("Done — synthetic data loaded.")
    print()
    print("Test login credentials (USN / date_of_birth):")
    students = json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))
    for st in students[:3]:
        print(f"  USN: {st['usn']}  DOB: {st['date_of_birth']}  Name: {st['name']}")
    print()
    print("Next step: run the API server:")
    print("  uvicorn api.main:app --reload --port 8000")


if __name__ == "__main__":
    main()
