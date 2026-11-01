"""Test WhatsApp message ingestion end-to-end."""

import requests
import time

WHATSAPP_CONSOLE_URL = "http://localhost:8001"
API_URL = "http://localhost:8000"

print("=" * 70)
print("Testing WhatsApp Message Ingestion")
print("=" * 70)

# Step 1: Post a message to mock WhatsApp console
print("\n📱 Step 1: Posting message to mock WhatsApp console...")

message_data = {
    "sender_role": "placement_cell",
    "sender_id": "placement_admin",
    "body": "Tech Mahindra update: minimum CGPA changed to 6.0",
    "is_forwarded": None,
}

try:
    response = requests.post(
        f"{WHATSAPP_CONSOLE_URL}/post",
        data=message_data,
        allow_redirects=False
    )
    
    if response.status_code in [303, 302, 200]:
        print("✅ Message posted successfully")
    else:
        print(f"❌ Failed to post message: {response.status_code}")
        exit(1)
        
except requests.exceptions.ConnectionError:
    print(f"❌ Cannot connect to WhatsApp console at {WHATSAPP_CONSOLE_URL}")
    print("   Start it with: uvicorn ingestion.mock_whatsapp.console:app --reload --port 8001")
    exit(1)

# Small delay
time.sleep(1)

# Step 2: Check messages in WhatsApp console
print("\n📋 Step 2: Checking messages in WhatsApp console...")

time.sleep(0.5)  # Small delay to ensure message is stored

try:
    response = requests.get(f"{WHATSAPP_CONSOLE_URL}/messages")
    messages = response.json()
    print(f"✅ Found {len(messages)} message(s) in WhatsApp store")
    
    if messages:
        latest = messages[-1]
        print(f"   Latest message:")
        print(f"     - Role: {latest['sender_role']}")
        print(f"     - Body: {latest['body']}")
    else:
        print("   ⚠️  No messages found - WhatsApp console may have restarted")
        print("   Posting message again...")
        
        # Post again
        response = requests.post(
            f"{WHATSAPP_CONSOLE_URL}/post",
            data=message_data,
            allow_redirects=False
        )
        time.sleep(0.5)
        
        # Check again
        response = requests.get(f"{WHATSAPP_CONSOLE_URL}/messages")
        messages = response.json()
        print(f"   ✅ Now have {len(messages)} message(s)")
        
except Exception as e:
    print(f"❌ Error checking messages: {e}")
    exit(1)

# Step 3: Process WhatsApp messages through ingestion API
print("\n🔄 Step 3: Processing WhatsApp messages through ingestion API...")

try:
    response = requests.post(
        f"{API_URL}/ingest/process-whatsapp",
        timeout=60
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Processing complete!")
        print(f"   Messages processed: {result['messages_processed']}")
        print(f"   Facts extracted: {result['total_facts_extracted']}")
        print(f"   Drives updated: {', '.join(result['drives_updated'])}")
        
        if result['details']:
            print(f"\n   Details:")
            for detail in result['details']:
                status_icon = "✅" if detail['status'] == 'success' else "⚠️" if detail['status'] == 'skipped' else "❌"
                print(f"     {status_icon} {detail.get('company_name', 'Unknown')}")
                if detail['status'] == 'success':
                    print(f"        Facts: {detail['facts_extracted']}")
                elif detail['status'] == 'skipped':
                    print(f"        Reason: {detail.get('reason', 'Unknown')}")
                elif detail['status'] == 'error':
                    print(f"        Error: {detail.get('error', 'Unknown')}")
    else:
        print(f"❌ Processing failed: {response.status_code}")
        print(f"   Response: {response.text}")
        exit(1)
        
except requests.exceptions.ConnectionError:
    print(f"❌ Cannot connect to API at {API_URL}")
    print("   Start it with: uvicorn api.main:app --reload")
    exit(1)
except Exception as e:
    print(f"❌ Error processing messages: {e}")
    exit(1)

# Step 4: Check if facts were created in database
print("\n🗄️  Step 4: Verifying facts in database...")

try:
    import sys
    sys.path.insert(0, ".")
    
    from database.connection import SessionLocal
    from database.models import Fact
    
    db = SessionLocal()
    
    # Get Tech Mahindra facts
    tm_facts = db.query(Fact).filter(
        Fact.drive_id == "DRIVE_TECHMAHINDRA"
    ).order_by(Fact.timestamp.desc()).limit(5).all()
    
    print(f"✅ Found {len(tm_facts)} recent fact(s) for Tech Mahindra")
    
    if tm_facts:
        latest_fact = tm_facts[0]
        print(f"   Latest fact:")
        print(f"     - Criterion: {latest_fact.criterion_type}")
        print(f"     - Operator: {latest_fact.operator}")
        print(f"     - Value: {latest_fact.value}")
        print(f"     - Source: {latest_fact.source_type}")
        print(f"     - Timestamp: {latest_fact.timestamp}")
    
    db.close()
    
except Exception as e:
    print(f"⚠️  Could not verify database: {e}")

print("\n" + "=" * 70)
print("✅ Test complete!")
print("=" * 70)
print(f"\n📊 View timeline at: http://localhost:3000/drive/DRIVE_TECHMAHINDRA")
print(f"💻 WhatsApp console: {WHATSAPP_CONSOLE_URL}")
print(f"🔧 API docs: {API_URL}/docs")
print("=" * 70)
