#!/usr/bin/env python3
"""Test that WhatsApp message processing doesn't create duplicates."""

from __future__ import annotations

import sys

sys.path.insert(0, "d:\\PLACEGUARD-ZAID\\PlaceGuard")

from database.connection import get_db
from database.models import Fact
from ingestion.mock_whatsapp import store
from core.schemas import SenderRole

print("=" * 70)
print("TESTING MESSAGE DEDUPLICATION")
print("=" * 70)
print()

# Add a test message
print("1. Adding test message to WhatsApp store...")
msg = store.add_message(
    sender_id="placement@msrit.edu",
    sender_role=SenderRole.PLACEMENT_CELL,
    body="Amazon is hiring! CGPA 8.0+ required, CSE and ECE only, no backlogs allowed. Deadline: Nov 15, 2026.",
    is_forwarded=False,
)
print(f"   ✓ Message ID: {msg.message_id}")
print()

# Check facts before processing
db = next(get_db())
facts_before = db.query(Fact).filter(Fact.source_id == msg.message_id).count()
print(f"2. Facts with this message_id before processing: {facts_before}")
print()

# Process messages (this will be done via API in real usage)
print("3. Processing messages via /ingest/process-whatsapp...")
print("   (Simulating API call)")
print()

import requests

try:
    response = requests.post("http://localhost:8000/ingest/process-whatsapp", timeout=60)
    if response.status_code == 200:
        result = response.json()
        print(f"   ✓ Success!")
        print(f"     Messages processed: {result['messages_processed']}")
        print(f"     Facts extracted: {result['total_facts_extracted']}")
        print()
        
        # Check facts after first processing
        facts_after_1 = db.query(Fact).filter(Fact.source_id == msg.message_id).count()
        print(f"4. Facts with this message_id after 1st processing: {facts_after_1}")
        print()
        
        # Process again (should skip)
        print("5. Processing messages AGAIN (should skip duplicates)...")
        response2 = requests.post("http://localhost:8000/ingest/process-whatsapp", timeout=60)
        if response2.status_code == 200:
            result2 = response2.json()
            print(f"   ✓ Success!")
            print(f"     Messages processed: {result2['messages_processed']}")
            print(f"     Facts extracted: {result2['total_facts_extracted']}")
            print()
            
            # Check facts after second processing
            facts_after_2 = db.query(Fact).filter(Fact.source_id == msg.message_id).count()
            print(f"6. Facts with this message_id after 2nd processing: {facts_after_2}")
            print()
            
            # Verify no duplicates
            if facts_after_1 == facts_after_2:
                print("=" * 70)
                print("✅ DEDUPLICATION WORKING!")
                print("=" * 70)
                print(f"\n   Same message processed twice:")
                print(f"   • 1st run: {facts_after_1} facts created")
                print(f"   • 2nd run: 0 new facts (skipped duplicate)")
                print(f"   • Total: {facts_after_2} facts (no duplicates)")
            else:
                print("=" * 70)
                print("❌ DEDUPLICATION FAILED!")
                print("=" * 70)
                print(f"\n   Duplicates created:")
                print(f"   • 1st run: {facts_after_1} facts")
                print(f"   • 2nd run: {facts_after_2 - facts_after_1} new facts")
                print(f"   • Total: {facts_after_2} facts (should be {facts_after_1})")
                sys.exit(1)
        else:
            print(f"   ❌ 2nd processing failed: {response2.status_code}")
            print(f"      {response2.text}")
            sys.exit(1)
    else:
        print(f"   ❌ Processing failed: {response.status_code}")
        print(f"      {response.text}")
        sys.exit(1)

except requests.exceptions.ConnectionError:
    print("   ❌ Cannot connect to API at http://localhost:8000")
    print("      Make sure the backend is running:")
    print("      python -m uvicorn api.main:app --reload --port 8000")
    sys.exit(1)

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print()
print("🧹 Cleanup: Message remains in WhatsApp store (in-memory only)")
print("   Restart WhatsApp console to clear or use store.clear()")
