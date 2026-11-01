"""Simple script to process pending WhatsApp messages.

Run this after posting messages to the WhatsApp console to update timelines.
"""

import requests
import sys

WHATSAPP_URL = "http://localhost:8001"
API_URL = "http://localhost:8000"

def process_messages():
    """Process all pending WhatsApp messages."""
    print("=" * 70)
    print("Processing WhatsApp Messages")
    print("=" * 70)
    
    # Check how many messages are pending
    try:
        response = requests.get(f"{WHATSAPP_URL}/messages", timeout=5)
        messages = response.json()
        print(f"\n📱 Found {len(messages)} message(s) in WhatsApp store")
        
        if messages:
            print("\nRecent messages:")
            for msg in messages[-3:]:
                print(f"  - {msg['body'][:60]}...")
    except Exception as e:
        print(f"⚠️  Could not check WhatsApp messages: {e}")
    
    # Process messages
    print(f"\n🔄 Processing messages through ingestion API...")
    
    try:
        response = requests.post(
            f"{API_URL}/ingest/process-whatsapp",
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n✅ Processing complete!")
            print(f"   Messages processed: {result['messages_processed']}")
            print(f"   Facts extracted: {result['total_facts_extracted']}")
            print(f"   Drives updated: {', '.join(result['drives_updated'])}")
            
            if result['details']:
                print(f"\n📋 Details:")
                for detail in result['details']:
                    if detail['status'] == 'success':
                        print(f"   ✅ {detail['company_name']}")
                        print(f"      Drive: {detail['drive_id']}")
                        print(f"      Facts: {detail['facts_extracted']}")
                    elif detail['status'] == 'skipped':
                        print(f"   ⚠️  Skipped: {detail.get('reason', 'Unknown')}")
                    elif detail['status'] == 'error':
                        print(f"   ❌ Error: {detail.get('error', 'Unknown')}")
            
            print(f"\n{'=' * 70}")
            print("✅ Done! Timelines updated.")
            print(f"{'=' * 70}")
            print(f"\n💡 View timelines in frontend:")
            print(f"   1. Login at http://localhost:3000/login")
            print(f"   2. Navigate to company drive pages")
            print(f"\n💬 WhatsApp console: {WHATSAPP_URL}")
            
            return True
        else:
            print(f"\n❌ Processing failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to API at {API_URL}")
        print(f"   Make sure the API server is running:")
        print(f"   python -m uvicorn api.main:app --reload")
        return False
    except requests.exceptions.Timeout:
        print(f"\n⚠️  Request timed out (may still be processing)")
        print(f"   Check API server logs for status")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = process_messages()
    sys.exit(0 if success else 1)
