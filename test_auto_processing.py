"""Test automatic processing when WhatsApp messages are posted."""

import requests
import time

WHATSAPP_URL = "http://localhost:8001"
API_URL = "http://localhost:8000"

print("=" * 70)
print("Testing Automatic WhatsApp Message Processing")
print("=" * 70)

# Check initial state
print("\n1️⃣ Checking initial database state...")
from database.connection import SessionLocal
from database.models import Fact

db = SessionLocal()
initial_count = db.query(Fact).filter(Fact.drive_id == "DRIVE_KPMG").count()
print(f"   Current KPMG facts: {initial_count}")
db.close()

# Post a message
print("\n2️⃣ Posting message to WhatsApp console...")
test_message = {
    "sender_role": "placement_cell",
    "sender_id": "test_admin",
    "body": "KPMG deadline extended to 8:00 PM today",
}

try:
    response = requests.post(
        f"{WHATSAPP_URL}/post",
        data=test_message,
        allow_redirects=False,
        timeout=5
    )
    
    if response.status_code in [200, 302, 303]:
        print(f"   ✅ Message posted: {test_message['body']}")
    else:
        print(f"   ❌ Failed to post: HTTP {response.status_code}")
        exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

# Wait for automatic processing
print("\n3️⃣ Waiting for automatic processing...")
print("   (Background task should trigger within a few seconds)")

for i in range(10):
    time.sleep(1)
    
    # Check if new facts were created
    db = SessionLocal()
    current_count = db.query(Fact).filter(Fact.drive_id == "DRIVE_KPMG").count()
    db.close()
    
    if current_count > initial_count:
        print(f"   ✅ New fact detected after {i+1} seconds!")
        break
    
    print(f"   ⏳ Waiting... ({i+1}s)", end="\r")
else:
    print("\n   ⚠️  No new facts detected after 10 seconds")
    print("   Checking if processing happened...")

# Check final state
print("\n4️⃣ Checking final database state...")
db = SessionLocal()
final_count = db.query(Fact).filter(Fact.drive_id == "DRIVE_KPMG").count()

if final_count > initial_count:
    print(f"   ✅ SUCCESS! Facts increased: {initial_count} → {final_count}")
    
    # Show the new fact
    latest_facts = db.query(Fact).filter(
        Fact.drive_id == "DRIVE_KPMG"
    ).order_by(Fact.timestamp.desc()).limit(1).all()
    
    if latest_facts:
        fact = latest_facts[0]
        print(f"\n   📋 Latest fact:")
        print(f"      Criterion: {fact.criterion_type} {fact.operator} {fact.value}")
        print(f"      Source: {fact.source_type}")
        print(f"      Time: {fact.timestamp}")
    
    print("\n" + "=" * 70)
    print("✅ AUTOMATIC PROCESSING IS WORKING!")
    print("=" * 70)
    print("\n🎉 Messages are now automatically processed when posted!")
    print("📱 Just post to WhatsApp console and the timeline updates!")
    print(f"🌐 View timeline at: http://localhost:3000/drive/DRIVE_KPMG")
    
else:
    print(f"   ⚠️  No new facts created (still {final_count})")
    print("\n   Possible reasons:")
    print("   1. LLM could not extract criteria from the message")
    print("   2. Processing is taking longer than expected")
    print("   3. API server might not be running")
    print("\n   Check WhatsApp console terminal for processing logs")

db.close()

print("\n" + "=" * 70)
