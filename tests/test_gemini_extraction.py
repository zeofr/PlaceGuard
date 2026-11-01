#!/usr/bin/env python3
"""Test Gemini API extraction with a real notice."""

import json
from datetime import datetime
from pathlib import Path

from core.schemas import SourceType
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_criteria_from_notice

# Load a notice from our realistic data
DATA_DIR = Path(__file__).parent / "data"
notices = json.loads((DATA_DIR / "notices.json").read_text(encoding="utf-8"))

# Test with KPMG notice (has clear criteria)
kpmg_notice = next(n for n in notices if n["drive_id"] == "DRIVE_KPMG")

print("=" * 70)
print("TESTING GEMINI API EXTRACTION")
print("=" * 70)
print()
print(f"Company: {kpmg_notice['company']}")
print(f"Drive ID: {kpmg_notice['drive_id']}")
print()
print("Notice Text:")
print("-" * 70)
print(kpmg_notice['text'])
print("-" * 70)
print()

# Initialize Gemini client
print("Initializing Gemini client...")
try:
    llm_client = get_llm_client("gemini")
    print("✅ Gemini client initialized successfully!")
    print()
except Exception as e:
    print(f"❌ Failed to initialize Gemini client: {e}")
    print()
    print("Check your .env file:")
    print("  1. GEMINI_API_KEY should be set")
    print("  2. Get key from: https://makersuite.google.com/app/apikey")
    exit(1)

# Extract criteria
print("Extracting criteria with Gemini...")
print()
try:
    facts = extract_criteria_from_notice(
        notice_text=kpmg_notice['text'],
        source_id=kpmg_notice['source_id'],
        source_type=SourceType(kpmg_notice['source_type']),
        timestamp=datetime.fromisoformat(kpmg_notice['timestamp']),
        drive_id=kpmg_notice['drive_id'],
        llm_client=llm_client,
    )
    
    print(f"✅ Extraction successful! Found {len(facts)} criteria:")
    print()
    
    for i, fact in enumerate(facts, 1):
        parsed_value = json.loads(fact.value)
        print(f"{i}. {fact.criterion_type}")
        print(f"   Operator: {fact.operator}")
        print(f"   Value: {parsed_value}")
        print(f"   Scope: {fact.scope}")
        if hasattr(fact, 'extraction_confidence'):
            print(f"   Confidence: {fact.extraction_confidence}")
        if hasattr(fact, 'extraction_notes') and fact.extraction_notes:
            print(f"   Notes: {fact.extraction_notes}")
        print()
    
    print("=" * 70)
    print("✅ GEMINI EXTRACTION TEST PASSED!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. The extraction is working!")
    print("  2. Use /ingest/notice API endpoint to extract from raw notices")
    print("  3. Test with other notices from notices.json")
    print()

except Exception as e:
    print(f"❌ Extraction failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
