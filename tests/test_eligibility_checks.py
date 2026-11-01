#!/usr/bin/env python3
"""Test eligibility checks after fixing encoding issues."""

from __future__ import annotations

import sys

sys.path.insert(0, "d:\\PLACEGUARD-ZAID\\PlaceGuard")

from database.connection import get_db
from database.crud import get_current_criteria, get_student
from rules.eligibility_engine import evaluate_eligibility

# Test student
TEST_USN = "1MS22CS001"

# Test drives
TEST_DRIVES = [
    "DRIVE_NVIDIA",      # CGPA 7.8+, CS/ECE/EEE
    "DRIVE_KPMG",        # 60% all levels, no backlogs, specific branches
    "DRIVE_TECHMAHINDRA",# 50% all levels, broader branches
    "DRIVE_IBM",         # CGPA 7.0+, no backlogs
    "DRIVE_APTOS",       # CGPA 7, no backlogs
]

def test_eligibility():
    """Test eligibility checks."""
    db = next(get_db())
    
    # Get student
    student_db = get_student(db, TEST_USN)
    if not student_db:
        print(f"❌ Student {TEST_USN} not found")
        return
    
    print("=" * 70)
    print(f"TESTING ELIGIBILITY FOR {TEST_USN}")
    print("=" * 70)
    print()
    print(f"Student: {student_db.name}")
    print(f"Branch: {student_db.branch}")
    print(f"CGPA: {student_db.cgpa}")
    print(f"10th: {student_db.tenth_pct}%")
    print(f"12th: {student_db.twelfth_pct}%")
    print(f"Backlogs: {student_db.backlogs}")
    print()
    
    # Convert to schema
    from core.schemas import Student
    student = Student(
        usn=student_db.usn,
        name=student_db.name,
        branch=student_db.branch,
        cgpa=student_db.cgpa,
        tenth_pct=student_db.tenth_pct,
        twelfth_pct=student_db.twelfth_pct,
        backlogs=student_db.backlogs,
        has_prior_offer=student_db.has_prior_offer,
    )
    
    print("=" * 70)
    print("ELIGIBILITY RESULTS")
    print("=" * 70)
    print()
    
    for drive_id in TEST_DRIVES:
        print(f"📋 {drive_id}")
        
        # Get criteria
        criteria_db = get_current_criteria(db, drive_id)
        
        if not criteria_db:
            print("   ⚠ No criteria found")
            print()
            continue
        
        # Convert to Criterion objects (parse JSON values)
        import json
        from core.schemas import Criterion
        criteria = [
            Criterion(
                drive_id=c.drive_id,
                criterion_type=c.criterion_type,
                operator=c.operator,
                value=json.loads(c.value),  # Parse JSON string to actual type
                scope=c.scope,
            )
            for c in criteria_db
        ]
        
        print(f"   Criteria: {len(criteria)} rules")
        for c in criteria:
            print(f"     • {c.criterion_type} {c.operator} {c.value!r}")
        
        # Check eligibility
        try:
            result = evaluate_eligibility(student, criteria)
            
            if result.status == "ELIGIBLE":
                print(f"   ✅ ELIGIBLE")
            else:
                print(f"   ❌ {result.status}")
                print(f"   Reasons:")
                for cr in result.criterion_results:
                    if cr.status != "PASS":
                        print(f"     • {cr.message}")
        
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        
        print()
    
    print("=" * 70)
    print("✅ ALL TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_eligibility()
