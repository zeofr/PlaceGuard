"""Ingest KPMG notices to create timeline demonstration."""

import json
import time
import requests

# Load notices
with open('data/notices.json', 'r') as f:
    all_notices = json.load(f)

# Filter KPMG notices
kpmg_notices = [n for n in all_notices if 'KPMG' in n['company']]
print(f"Found {len(kpmg_notices)} KPMG notices to ingest\n")

# Sort by timestamp to ingest in order
kpmg_notices.sort(key=lambda x: x['timestamp'])

# Base URL
BASE_URL = "http://localhost:8000"

# Ingest each notice
for i, notice in enumerate(kpmg_notices, 1):
    print(f"\n{'='*60}")
    print(f"Ingesting notice {i}/{len(kpmg_notices)}: {notice['notice_id']}")
    print(f"Timestamp: {notice['timestamp']}")
    print(f"Source: {notice['source_type']}")
    print(f"{'='*60}")
    
    payload = {
        "notice_text": notice['text'],
        "drive_id": notice['drive_id'],
        "drive_name": notice['company'],
        "source_type": notice['source_type'],
        "source_id": notice['source_id'],
        "timestamp": notice['timestamp']
    }
    
    try:
        response = requests.post(f"{BASE_URL}/ingest/notice", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS")
            print(f"  Facts extracted: {result.get('facts_extracted', 0)}")
            if 'criteria_extracted' in result:
                print(f"  Criteria:")
                for criterion in result['criteria_extracted']:
                    print(f"    - {criterion['criterion_type']} {criterion['operator']} {criterion['value']}")
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            print(f"  Response: {response.text}")
    
    except requests.exceptions.ConnectionError:
        print(f"❌ FAILED: Cannot connect to API server at {BASE_URL}")
        print(f"   Make sure the server is running with: uvicorn api.main:app --reload")
        break
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Small delay between ingestions
    if i < len(kpmg_notices):
        time.sleep(1)

print(f"\n{'='*60}")
print("✅ Ingestion complete!")
print(f"\n📊 View timeline at: http://localhost:3000/drive/DRIVE_KPMG")
print(f"📊 Or via API: {BASE_URL}/timeline/DRIVE_KPMG")
print(f"{'='*60}")
