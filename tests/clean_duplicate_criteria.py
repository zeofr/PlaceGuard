#!/usr/bin/env python3
"""Remove duplicate and incorrectly typed criteria."""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "d:\\PLACEGUARD-ZAID\\PlaceGuard")

from database.connection import get_db
from database.models import ExtractedCriterion


def clean_duplicates():
    """Remove duplicate and wrong criteria."""
    db = next(get_db())
    
    print("=" * 70)
    print("CLEANING DUPLICATE AND INCORRECT CRITERIA")
    print("=" * 70)
    print()
    
    # Find and remove wrong criterion types
    wrong_types = ["min_tenth_pct", "min_twelfth_pct", "deadline"]
    
    for wrong_type in wrong_types:
        criteria = db.query(ExtractedCriterion).filter(
            ExtractedCriterion.criterion_type == wrong_type
        ).all()
        
        for criterion in criteria:
            print(f"🗑 Removing {criterion.drive_id} / {criterion.criterion_type} (unregistered)")
            db.delete(criterion)
    
    # Fix KPMG allowed_branches (should be list, not string)
    kpmg_branches = db.query(ExtractedCriterion).filter(
        ExtractedCriterion.drive_id == "DRIVE_KPMG",
        ExtractedCriterion.criterion_type == "allowed_branches"
    ).first()
    
    if kpmg_branches:
        parsed = json.loads(kpmg_branches.value)
        if isinstance(parsed, str):
            print(f"🔧 Fixing KPMG allowed_branches from string to list")
            print(f"   Before: {parsed!r}")
            # Convert string to list
            branches = [b.strip() for b in parsed.split(",")]
            kpmg_branches.value = json.dumps(branches)
            parsed_new = json.loads(kpmg_branches.value)
            print(f"   After: {parsed_new!r}")
    
    db.commit()
    
    print()
    print("=" * 70)
    print("✅ CLEANUP COMPLETE")
    print("=" * 70)
    print()
    
    # Show remaining criteria
    criteria = db.query(ExtractedCriterion).filter(
        ExtractedCriterion.is_current == True
    ).order_by(ExtractedCriterion.drive_id, ExtractedCriterion.criterion_type).all()
    
    print(f"Remaining criteria ({len(criteria)}):")
    print()
    
    current_drive = None
    for criterion in criteria:
        if criterion.drive_id != current_drive:
            current_drive = criterion.drive_id
            print(f"\n{criterion.drive_id}:")
        
        parsed = json.loads(criterion.value)
        print(f"  • {criterion.criterion_type:20s} = {parsed!r}")


if __name__ == "__main__":
    clean_duplicates()
