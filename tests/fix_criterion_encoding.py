#!/usr/bin/env python3
"""Fix double-encoded criterion values in database.

This script finds criteria with double JSON encoding and fixes them.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "d:\\PLACEGUARD-ZAID\\PlaceGuard")

from database.connection import get_db
from database.models import ExtractedCriterion


def fix_double_encoding():
    """Find and fix double-encoded values."""
    db = next(get_db())
    
    criteria = db.query(ExtractedCriterion).filter(
        ExtractedCriterion.is_current == True
    ).all()
    
    fixed_count = 0
    
    print("=" * 70)
    print("FIXING DOUBLE-ENCODED CRITERION VALUES")
    print("=" * 70)
    print()
    
    for criterion in criteria:
        try:
            # Try to parse the value
            parsed = json.loads(criterion.value)
            
            # Check if it's still a string after parsing (double-encoded)
            if isinstance(parsed, str):
                # Try parsing again
                try:
                    double_parsed = json.loads(parsed)
                    print(f"❌ {criterion.drive_id} / {criterion.criterion_type}")
                    print(f"   Before: {criterion.value!r} → {parsed!r}")
                    
                    # Fix it by encoding once
                    criterion.value = json.dumps(double_parsed)
                    print(f"   After:  {criterion.value!r} → {double_parsed!r}")
                    print()
                    fixed_count += 1
                except (json.JSONDecodeError, ValueError):
                    # It's a legitimately string value, not double-encoded
                    pass
        except json.JSONDecodeError:
            print(f"⚠ Warning: Could not parse {criterion.drive_id} / {criterion.criterion_type}: {criterion.value!r}")
            print()
    
    if fixed_count > 0:
        db.commit()
        print("=" * 70)
        print(f"✅ Fixed {fixed_count} double-encoded values")
        print("=" * 70)
    else:
        print("=" * 70)
        print("✅ No double-encoded values found")
        print("=" * 70)
    
    # Verify all values now parse correctly
    print()
    print("Verifying all current criteria:")
    print()
    
    criteria = db.query(ExtractedCriterion).filter(
        ExtractedCriterion.is_current == True
    ).all()
    
    errors = []
    for criterion in criteria:
        try:
            parsed = json.loads(criterion.value)
            # Show type
            print(f"✓ {criterion.drive_id:25s} {criterion.criterion_type:20s} → {type(parsed).__name__:8s} {parsed!r}")
        except Exception as e:
            errors.append((criterion, e))
            print(f"✗ {criterion.drive_id:25s} {criterion.criterion_type:20s} → ERROR: {e}")
    
    print()
    if errors:
        print(f"⚠ {len(errors)} criteria still have parsing errors")
        return False
    else:
        print(f"✅ All {len(criteria)} criteria parse correctly!")
        return True


if __name__ == "__main__":
    success = fix_double_encoding()
    sys.exit(0 if success else 1)
