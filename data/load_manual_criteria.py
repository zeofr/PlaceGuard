#!/usr/bin/env python3
"""Manually load pre-extracted criteria for realistic drives.

This script stands in for a real source (the SIS portal integration isn't
available yet) exactly like ingestion/portal/adapter.py does for the portal
channel: it inserts real, auditable Facts and runs them through the same
reconciliation used by WhatsApp/email/portal ingestion, rather than writing
ExtractedCriterion directly. That keeps this seed data indistinguishable
from real data to the rest of the pipeline (vector indexing included), so
swapping this stand-in for the real portal later requires no pipeline change.

Usage (from project root):
    python data/load_manual_criteria.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from database import crud, init_db
from database.connection import get_db_context
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive

# Pre-extracted criteria for each realistic drive
# Based on the actual notice text in notices.json
DRIVE_CRITERIA = {
    "DRIVE_TECHMAHINDRA": [
        {"criterion_type": "min_10th_pct", "operator": "gte", "value": 50.0, "scope": "ALL"},
        {"criterion_type": "min_12th_pct", "operator": "gte", "value": 50.0, "scope": "ALL"},
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 5.0, "scope": "ALL"},  # 50% = 5.0 CGPA
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "ISE", "ECE", "CSE(AI&ML)"], "scope": "ALL"},
    ],
    "DRIVE_KPMG": [
        {"criterion_type": "min_10th_pct", "operator": "gte", "value": 60.0, "scope": "ALL"},
        {"criterion_type": "min_12th_pct", "operator": "gte", "value": 60.0, "scope": "ALL"},
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 6.0, "scope": "ALL"},  # 60% = 6.0 CGPA
        {"criterion_type": "max_backlogs", "operator": "lte", "value": 0, "scope": "ALL"},
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "ISE", "CSE(AI&ML)", "Cybersecurity"], "scope": "ALL"},
    ],
    "DRIVE_BOEING": [
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 7.0, "scope": "ALL"},
    ],
    "DRIVE_MORPHLE": [
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 6.0, "scope": "ALL"},
        {"criterion_type": "max_backlogs", "operator": "lte", "value": 0, "scope": "ALL"},
    ],
    "DRIVE_APTOS": [
        # No specific criteria mentioned in notice - open to all
    ],
    "DRIVE_GE": [
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 8.0, "scope": "ALL"},  # 80% or 8 CGPA
    ],
    "DRIVE_ERICSSON": [
        {"criterion_type": "min_10th_pct", "operator": "gte", "value": 60.0, "scope": "ALL"},
        {"criterion_type": "min_12th_pct", "operator": "gte", "value": 60.0, "scope": "ALL"},
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 6.0, "scope": "ALL"},  # 60% = 6.0 CGPA
        {"criterion_type": "max_backlogs", "operator": "lte", "value": 0, "scope": "ALL"},
    ],
    "DRIVE_SCHNEIDER": [
        {"criterion_type": "min_10th_pct", "operator": "gte", "value": 65.0, "scope": "ALL"},
        {"criterion_type": "min_12th_pct", "operator": "gte", "value": 65.0, "scope": "ALL"},
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 6.5, "scope": "ALL"},  # 65% = 6.5 CGPA
        {"criterion_type": "max_backlogs", "operator": "lte", "value": 0, "scope": "ALL"},
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "ISE", "CSE(AI&ML)", "Cybersecurity"], "scope": "ALL"},
    ],
    "DRIVE_NVIDIA": [
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 7.8, "scope": "ALL"},
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "ISE", "ECE"], "scope": "ALL"},
    ],
    "DRIVE_OPUS": [
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "ISE", "CSE(AI&ML)"], "scope": "ALL"},
    ],
    "DRIVE_IBM": [
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 7.0, "scope": "ALL"},
        {"criterion_type": "max_backlogs", "operator": "lte", "value": 0, "scope": "ALL"},
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "ISE", "ECE"], "scope": "ALL"},
    ],
}


def load_manual_criteria(db) -> int:
    """Insert pre-extracted criteria for each drive as real Facts, then reconcile.

    Each criterion becomes its own append-only Fact (unique source_id, so it's
    individually indexable into the vector store — a shared source_id across a
    drive's criteria would mean only one gets embedded). ExtractedCriterion is
    then derived by the same reconciliation real ingestion uses, never written
    directly.
    """
    inserted = 0
    timestamp = datetime(2026, 10, 29, 12, 0, 0)
    drives_seeded: list[str] = []

    for drive_id, criteria_list in DRIVE_CRITERIA.items():
        # Check if drive exists
        drive = crud.get_drive(db, drive_id)
        if not drive:
            print(f"   ⚠ Drive {drive_id} not found, skipping")
            continue

        for criterion_data in criteria_list:
            source_id = f"manual_{drive_id}_{criterion_data['criterion_type']}"

            # Facts are append-only; skip if this seed fact already exists
            # (keeps re-running this script safe, same as real ingestion does).
            if crud.get_fact_by_source(db, source_id):
                continue

            # JSON-encode the value for storage (single encoding)
            # The value will be stored as JSON string in database
            # and parsed back when loaded
            value_json = json.dumps(criterion_data["value"])

            crud.insert_fact(
                db,
                source_id=source_id,
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=timestamp,
                drive_id=drive_id,
                criterion_type=criterion_data["criterion_type"],
                operator=criterion_data["operator"],
                value=value_json,  # This is now: "50.0" not '"50.0"'
                scope=criterion_data.get("scope", "ALL"),
            )
            inserted += 1

        if criteria_list:
            drives_seeded.append(drive_id)

    # Derive ExtractedCriterion the same way real ingestion does.
    for drive_id in drives_seeded:
        reconcile_facts_for_drive(db, drive_id, persist=True)

    return inserted


def main() -> None:
    print("=" * 70)
    print("LOADING MANUAL CRITERIA (Pre-extracted for Testing)")
    print("=" * 70)
    print()
    print("This script inserts pre-extracted eligibility criteria")
    print("so you can test the system without requiring Gemini API.")
    print()
    
    init_db()

    with get_db_context() as db:
        c = load_manual_criteria(db)
        print(f"  ✓ Inserted {c} criteria across {len(DRIVE_CRITERIA)} drives")
        print()

        from database.vector_indexing import reindex_all_facts
        print("Indexing into the vector store...")
        reindex_all_facts(db)
        print()

    print("=" * 70)
    print("✅ MANUAL CRITERIA LOADED SUCCESSFULLY")
    print("=" * 70)
    print()
    print("📋 Criteria Summary:")
    print(f"  • Tech Mahindra: 50% all levels, CSE/ISE/ECE/AI&ML branches")
    print(f"  • KPMG: 60% all levels, no backlogs, CS Allied branches only")
    print(f"  • Boeing: CGPA 7.0+")
    print(f"  • Morphle: CGPA 6.0+, no backlogs")
    print(f"  • Aptos: Open to all")
    print(f"  • GE Healthcare: 80% aggregate or 8.0 CGPA")
    print(f"  • Ericsson: 60% all levels, no backlogs")
    print(f"  • Schneider: 65% all levels, no backlogs, CS Allied branches")
    print(f"  • NVIDIA: CGPA 7.8+, CSE/ISE/ECE")
    print(f"  • Opus: CSE/ISE/AI&ML branches only")
    print(f"  • IBM: CGPA 7.0+, no backlogs, CSE/ISE/ECE")
    print()
    print("🔐 Now you can login and check eligibility!")
    print("   Test with USN: 1MS22CS001 / DOB: 2003-01-15")
    print()
    print("💡 To enable full LLM extraction in the future:")
    print("   1. Get Gemini API key: https://makersuite.google.com/app/apikey")
    print("   2. Update .env: GEMINI_API_KEY=your_key_here")
    print("   3. Use /ingest/notice endpoint to extract from raw text")
    print()


if __name__ == "__main__":
    main()
