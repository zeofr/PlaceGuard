#!/usr/bin/env python3
"""Load student and drive data based on actual MSRIT placement communications.

Run once to seed the database with realistic data for testing/demo.

Usage (from project root):
    python data/load_data.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from core.schemas import Student as StudentSchema
from database import crud, init_db
from database.connection import get_db_context
from database.vector_indexing import reindex_all_facts
from data.load_notices_via_llm import load_notices_via_llm

DATA_DIR = Path(__file__).parent
STUDENTS_FILE = DATA_DIR / "students.json"
NOTICES_FILE  = DATA_DIR / "notices.json"


def load_students(db) -> int:
    """Insert students. Skip if already present."""
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
    """Create unique drives referenced in notices.json."""
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
    print("=" * 70)
    print("LOADING DATASET (Based on Actual MSRIT Placement Data)")
    print("=" * 70)
    print()
    print("Initialising database …")
    init_db()

    with get_db_context() as db:
        s = load_students(db)
        d = load_drives(db)
        print(f"  ✓ Inserted {s} student(s)")
        print(f"  ✓ Inserted {d} drive(s)")
        print()

        print("Extracting criteria from notices via the real LLM pipeline...")
        notice_stats = load_notices_via_llm(db)
        print(f"  ✓ Processed {notice_stats['processed']} source(s), "
              f"skipped {notice_stats['skipped']} already-ingested, "
              f"extracted {notice_stats['facts']} fact(s) across {len(notice_stats['drives'])} drive(s)")
        print()

        print("Indexing extracted facts into the vector store...")
        indexed = reindex_all_facts(db)
        print(f"  ✓ Indexed {indexed} notice(s) into the vector store")
        print()

    print("=" * 70)
    print("✅ DATA LOADED SUCCESSFULLY")
    print("=" * 70)
    print()
    print("📊 Dataset includes:")
    print("  • Students with diverse profiles (CSE, AI&ML, Cybersecurity, IT, ECE, etc.)")
    print("  • All companies/drives referenced in data/notices.json")
    print("  • Criteria extracted live via the LLM (Ollama by default) from the real")
    print("    notice/WhatsApp text, not hardcoded — includes registration links,")
    print("    deadline conflicts, and branch-list corrections where present")
    print()
    print("🔐 Test login credentials (USN / date_of_birth):")
    students = json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))
    for st in students[:5]:
        cgpa_str = f"CGPA: {st['cgpa']}" if st['cgpa'] else "CGPA: NULL"
        print(f"  USN: {st['usn']:<15} DOB: {st['date_of_birth']}  {st['name']:<20} ({cgpa_str}, {st['branch']})")
    print()
    print("🚀 Next steps:")
    print("  1. Start the API server:")
    print("     python -m uvicorn api.main:app --reload --port 8000")
    print()
    print("  2. Start the frontend:")
    print("     cd frontend")
    print("     npm run dev")
    print()
    print("  3. Open http://localhost:3000 and login with any USN above")
    print()
    print("💡 Note: criteria extraction above used LLM_PROVIDER from .env (Ollama by")
    print("   default — see STARTUP.md). Switch to Gemini/OpenAI/Claude there if preferred.")
    print()


if __name__ == "__main__":
    main()
