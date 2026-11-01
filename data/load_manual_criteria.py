#!/usr/bin/env python3
"""Manually load pre-extracted criteria for realistic drives.

This script inserts criteria directly into extracted_criteria table
for testing without requiring LLM extraction.

Usage (from project root):
    python data/load_manual_criteria.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from database import crud, init_db
from database.connection import get_db_context

# Pre-extracted criteria for each realistic drive
# Based on the actual notice text in notices.json
DRIVE_CRITERIA = {
    "DRIVE_TECHMAHINDRA": [
        {"criterion_type": "min_10th_pct", "operator": "gte", "value": 50.0, "scope": "ALL"},
        {"criterion_type": "min_12th_pct", "operator": "gte", "value": 50.0, "scope": "ALL"},
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 5.0, "scope": "ALL"},  # 50% = 5.0 CGPA
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "IT", "ECE", "EEE", "CSE(AI&ML)", "AI&ML"], "scope": "ALL"},
    ],
    "DRIVE_KPMG": [
        {"criterion_type": "min_10th_pct", "operator": "gte", "value": 60.0, "scope": "ALL"},
        {"criterion_type": "min_12th_pct", "operator": "gte", "value": 60.0, "scope": "ALL"},
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 6.0, "scope": "ALL"},  # 60% = 6.0 CGPA
        {"criterion_type": "max_backlogs", "operator": "lte", "value": 0, "scope": "ALL"},
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "CSE(AI&ML)", "Cybersecurity"], "scope": "ALL"},
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
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "IT", "CSE(AI&ML)", "Cybersecurity"], "scope": "ALL"},
    ],
    "DRIVE_NVIDIA": [
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 7.8, "scope": "ALL"},
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "ECE", "EEE"], "scope": "ALL"},
    ],
    "DRIVE_OPUS": [
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "IT", "CSE(AI&ML)"], "scope": "ALL"},
    ],
    "DRIVE_IBM": [
        {"criterion_type": "min_cgpa", "operator": "gte", "value": 7.0, "scope": "ALL"},
        {"criterion_type": "max_backlogs", "operator": "lte", "value": 0, "scope": "ALL"},
        {"criterion_type": "allowed_branches", "operator": "in", "value": ["CSE", "IT", "ECE", "EEE"], "scope": "ALL"},
    ],
}


def load_manual_criteria(db) -> int:
    """Insert pre-extracted criteria for each drive."""
    inserted = 0
    timestamp = datetime(2026, 10, 29, 12, 0, 0)
    
    for drive_id, criteria_list in DRIVE_CRITERIA.items():
        # Check if drive exists
        drive = crud.get_drive(db, drive_id)
        if not drive:
            print(f"   ⚠ Drive {drive_id} not found, skipping")
            continue
        
        for criterion_data in criteria_list:
            # JSON-encode the value for storage (single encoding)
            # The value will be stored as JSON string in database
            # and parsed back when loaded
            value_json = json.dumps(criterion_data["value"])
            
            crud.upsert_extracted_criterion(
                db,
                drive_id=drive_id,
                criterion_type=criterion_data["criterion_type"],
                operator=criterion_data["operator"],
                value=value_json,  # This is now: "50.0" not '"50.0"'
                source_id=f"manual_{drive_id}",
                source_type="placement_cell_email",
                authority_rank=2,
                timestamp=timestamp,
                scope=criterion_data.get("scope", "ALL"),
            )
            inserted += 1
    
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
    
    print("=" * 70)
    print("✅ MANUAL CRITERIA LOADED SUCCESSFULLY")
    print("=" * 70)
    print()
    print("📋 Criteria Summary:")
    print(f"  • Tech Mahindra: 50% all levels, CS/IT/EC branches")
    print(f"  • KPMG: 60% all levels, no backlogs, CS/AI/Cyber only")
    print(f"  • Boeing: CGPA 7.0+")
    print(f"  • Morphle: CGPA 6.0+, no backlogs")
    print(f"  • Aptos: Open to all")
    print(f"  • GE Healthcare: 80% aggregate or 8.0 CGPA")
    print(f"  • Ericsson: 60% all levels, no backlogs")
    print(f"  • Schneider: 65% all levels, no backlogs, CS/IT/AI/Cyber")
    print(f"  • NVIDIA: CGPA 7.8+, CS/ECE/EEE")
    print(f"  • Opus: CS/IT/AI branches only")
    print(f"  • IBM: CGPA 7.0+, no backlogs, CS/IT/ECE/EEE")
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
