"""Quick test for automatic processing."""
import requests
import time

print("🧪 Testing automatic processing...")
print("\n1. Posting test message...")

response = requests.post(
    "http://localhost:8001/post",
    data={
        "sender_role": "placement_cell",
        "sender_id": "test",
        "body": "IBM minimum CGPA changed to 7.5"
    },
    allow_redirects=False
)

print(f"   Message posted: {response.status_code}")

print("\n2. Waiting 5 seconds for auto-processing...")
for i in range(5, 0, -1):
    print(f"   {i}...", end="\r")
    time.sleep(1)

print("\n\n3. Checking database...")

from database.connection import SessionLocal
from database.models import Fact

db = SessionLocal()
facts = db.query(Fact).filter(
    Fact.drive_id == "DRIVE_IBM"
).order_by(Fact.timestamp.desc()).limit(1).all()

if facts:
    fact = facts[0]
    print(f"✅ Found fact: {fact.criterion_type} {fact.operator} {fact.value}")
    print(f"   Timestamp: {fact.timestamp}")
    
    # Check if it's recent (last 10 seconds)
    from datetime import datetime, timedelta
    if (datetime.now() - fact.timestamp).total_seconds() < 10:
        print("\n🎉 AUTOMATIC PROCESSING IS WORKING!")
    else:
        print("\n⚠️  Fact exists but is old - processing may not be automatic")
else:
    print("❌ No facts found - processing didn't happen")
    print("\nPlease run: python process_whatsapp.py")

db.close()
