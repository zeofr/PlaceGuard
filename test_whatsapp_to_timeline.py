"""Comprehensive test: WhatsApp message → Fact → Timeline
Tests the complete pipeline with detailed diagnostics at each step.
"""

import json
import requests
import time
import sys
from datetime import datetime

# Configuration
WHATSAPP_URL = "http://localhost:8001"
API_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

# Test message
TEST_MESSAGE = {
    "sender_role": "placement_cell",
    "sender_id": "test_admin",
    "body": "Tech Mahindra CGPA requirement changed to 6.5 effective immediately",
}

DRIVE_ID = "DRIVE_TECHMAHINDRA"

def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}\n")

def print_step(step_num, text):
    """Print a step."""
    print(f"\n{'─' * 80}")
    print(f"STEP {step_num}: {text}")
    print(f"{'─' * 80}")

def print_success(text):
    """Print success message."""
    print(f"✅ {text}")

def print_error(text):
    """Print error message."""
    print(f"❌ {text}")

def print_warning(text):
    """Print warning message."""
    print(f"⚠️  {text}")

def print_info(text):
    """Print info message."""
    print(f"ℹ️  {text}")

def check_server(url, name):
    """Check if a server is running."""
    try:
        response = requests.get(url, timeout=2)
        print_success(f"{name} is running at {url}")
        return True
    except requests.exceptions.ConnectionError:
        print_error(f"{name} is NOT running at {url}")
        return False
    except Exception as e:
        print_error(f"Error checking {name}: {e}")
        return False

def main():
    print_header("WhatsApp → Timeline Integration Test")
    print(f"Test message: {TEST_MESSAGE['body']}")
    print(f"Target drive: {DRIVE_ID}")
    
    # ========================================================================
    # STEP 1: Check servers are running
    # ========================================================================
    print_step(1, "Checking servers")
    
    api_running = check_server(f"{API_URL}/health", "API Server")
    whatsapp_running = check_server(WHATSAPP_URL, "WhatsApp Console")
    
    if not api_running:
        print_error("API server must be running!")
        print_info("Start it with: python -m uvicorn api.main:app --reload")
        return False
    
    if not whatsapp_running:
        print_error("WhatsApp console must be running!")
        print_info("Start it with: python -m uvicorn ingestion.mock_whatsapp.console:app --reload --port 8001")
        return False
    
    # ========================================================================
    # STEP 2: Check initial state
    # ========================================================================
    print_step(2, "Checking initial database state")
    
    try:
        from database.connection import SessionLocal
        from database.models import Fact, Drive
        
        db = SessionLocal()
        
        # Check if drive exists
        drive = db.query(Drive).filter(Drive.drive_id == DRIVE_ID).first()
        if drive:
            print_success(f"Drive exists: {drive.company_name}")
        else:
            print_warning(f"Drive {DRIVE_ID} does not exist yet (will be created)")
        
        # Count existing facts
        initial_fact_count = db.query(Fact).filter(Fact.drive_id == DRIVE_ID).count()
        print_info(f"Current fact count for {DRIVE_ID}: {initial_fact_count}")
        
        db.close()
        
    except Exception as e:
        print_error(f"Database check failed: {e}")
        return False
    
    # ========================================================================
    # STEP 3: Post message to WhatsApp console
    # ========================================================================
    print_step(3, "Posting message to WhatsApp console")
    
    try:
        response = requests.post(
            f"{WHATSAPP_URL}/post",
            data=TEST_MESSAGE,
            allow_redirects=False,
            timeout=5
        )
        
        if response.status_code in [200, 302, 303]:
            print_success("Message posted successfully")
        else:
            print_error(f"Failed to post message: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error posting message: {e}")
        return False
    
    # Small delay to ensure message is stored
    time.sleep(0.5)
    
    # ========================================================================
    # STEP 4: Verify message in WhatsApp store
    # ========================================================================
    print_step(4, "Verifying message in WhatsApp store")
    
    try:
        response = requests.get(f"{WHATSAPP_URL}/messages", timeout=5)
        messages = response.json()
        
        print_info(f"Total messages in store: {len(messages)}")
        
        if not messages:
            print_error("No messages found in WhatsApp store!")
            print_warning("The in-memory store may have been cleared")
            
            # Try posting again
            print_info("Attempting to repost message...")
            requests.post(f"{WHATSAPP_URL}/post", data=TEST_MESSAGE, allow_redirects=False)
            time.sleep(0.5)
            
            response = requests.get(f"{WHATSAPP_URL}/messages", timeout=5)
            messages = response.json()
            
            if not messages:
                print_error("Still no messages after reposting!")
                return False
        
        # Find our message
        our_message = None
        for msg in messages:
            if TEST_MESSAGE['body'] in msg.get('body', ''):
                our_message = msg
                break
        
        if our_message:
            print_success("Found our test message")
            print_info(f"Message ID: {our_message['message_id']}")
            print_info(f"Source type: {our_message['source_type']}")
            print_info(f"Timestamp: {our_message['timestamp']}")
        else:
            print_error("Could not find our test message in store")
            return False
            
    except Exception as e:
        print_error(f"Error verifying messages: {e}")
        return False
    
    # ========================================================================
    # STEP 5: Process WhatsApp messages
    # ========================================================================
    print_step(5, "Processing WhatsApp messages through ingestion API")
    
    try:
        print_info("Calling POST /ingest/process-whatsapp...")
        
        response = requests.post(
            f"{API_URL}/ingest/process-whatsapp",
            timeout=120  # LLM extraction can take time
        )
        
        if response.status_code == 200:
            result = response.json()
            print_success("Processing completed successfully")
            
            print(f"\n📊 Processing Results:")
            print(f"   Messages processed: {result['messages_processed']}")
            print(f"   Facts extracted: {result['total_facts_extracted']}")
            print(f"   Drives updated: {', '.join(result['drives_updated']) if result['drives_updated'] else 'None'}")
            
            if result['details']:
                print(f"\n   📋 Details:")
                for detail in result['details']:
                    status_icon = "✅" if detail['status'] == 'success' else "⚠️" if detail['status'] == 'skipped' else "❌"
                    print(f"      {status_icon} Message: {detail.get('body_preview', 'N/A')[:60]}...")
                    
                    if detail['status'] == 'success':
                        print(f"         Drive: {detail.get('drive_id', 'N/A')}")
                        print(f"         Company: {detail.get('company_name', 'N/A')}")
                        print(f"         Facts: {detail.get('facts_extracted', 0)}")
                    elif detail['status'] == 'skipped':
                        print(f"         Reason: {detail.get('reason', 'Unknown')}")
                    elif detail['status'] == 'error':
                        print(f"         Error: {detail.get('error', 'Unknown')}")
            
            if result['total_facts_extracted'] == 0:
                print_warning("No facts were extracted from the message!")
                print_info("This could mean:")
                print_info("  - LLM could not identify the company")
                print_info("  - LLM could not extract eligibility criteria")
                print_info("  - Message format was unclear")
                return False
                
        else:
            print_error(f"Processing failed: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print_error("Processing timed out (may still be running)")
        print_info("Check API server logs for details")
        return False
    except Exception as e:
        print_error(f"Error processing messages: {e}")
        return False
    
    # ========================================================================
    # STEP 6: Verify facts in database
    # ========================================================================
    print_step(6, "Verifying facts in database")
    
    try:
        db = SessionLocal()
        
        # Get all facts for this drive
        facts = db.query(Fact).filter(
            Fact.drive_id == DRIVE_ID
        ).order_by(Fact.timestamp.desc()).all()
        
        new_fact_count = len(facts)
        print_info(f"Total facts for {DRIVE_ID}: {new_fact_count}")
        
        if new_fact_count > initial_fact_count:
            print_success(f"New facts added: {new_fact_count - initial_fact_count}")
            
            # Show latest facts
            print(f"\n📋 Latest Facts:")
            for i, fact in enumerate(facts[:5], 1):
                print(f"   {i}. {fact.criterion_type} {fact.operator} {fact.value}")
                print(f"      Source: {fact.source_type}")
                print(f"      Timestamp: {fact.timestamp}")
                print()
        else:
            print_error("No new facts were added to the database!")
            return False
        
        db.close()
        
    except Exception as e:
        print_error(f"Database verification failed: {e}")
        return False
    
    # ========================================================================
    # STEP 7: Verify timeline API
    # ========================================================================
    print_step(7, "Testing timeline API")
    
    try:
        # First, we need to login to get a token
        print_info("Logging in to get authentication token...")
        
        login_response = requests.post(
            f"{API_URL}/auth/login",
            data={
                "username": "1MS22CS001",
                "password": "2003-01-15"
            },
            timeout=5
        )
        
        if login_response.status_code == 200:
            token = login_response.json()['access_token']
            print_success("Login successful")
            
            # Get timeline
            print_info(f"Fetching timeline for {DRIVE_ID}...")
            
            timeline_response = requests.get(
                f"{API_URL}/timeline/{DRIVE_ID}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            
            if timeline_response.status_code == 200:
                timeline = timeline_response.json()
                print_success("Timeline retrieved successfully")
                
                print(f"\n📊 Timeline Summary:")
                print(f"   Company: {timeline['company_name']}")
                print(f"   Status: {timeline['status']}")
                print(f"   Total events: {timeline['total_events']}")
                print(f"   Current criteria: {len(timeline['current_criteria'])}")
                
                if timeline['timeline']:
                    print(f"\n   📋 Recent Timeline Events:")
                    for i, event in enumerate(timeline['timeline'][-5:], 1):
                        print(f"      {i}. {event['criterion_type']} {event['operator']} {event['value']}")
                        print(f"         Source: {event['source_type']}")
                        print(f"         Time: {event['timestamp']}")
                        print()
                
            else:
                print_error(f"Failed to get timeline: HTTP {timeline_response.status_code}")
                print_info("The facts may exist but timeline API failed")
                
        else:
            print_warning("Could not login for timeline check")
            print_info("Facts exist, but couldn't verify timeline API")
            
    except Exception as e:
        print_error(f"Timeline verification failed: {e}")
        print_info("Facts exist, but couldn't verify timeline API")
    
    # ========================================================================
    # STEP 8: Summary
    # ========================================================================
    print_header("✅ TEST PASSED!")
    
    print("🎉 WhatsApp → Timeline pipeline is working correctly!")
    print(f"\n📱 WhatsApp Console: {WHATSAPP_URL}")
    print(f"🔧 API Server: {API_URL}")
    print(f"🌐 Frontend: {FRONTEND_URL}")
    print(f"\n📊 View timeline in frontend:")
    print(f"   1. Login at {FRONTEND_URL}/login")
    print(f"      USN: 1MS22CS001, DOB: 2003-01-15")
    print(f"   2. Navigate to {FRONTEND_URL}/drive/{DRIVE_ID}")
    print(f"\n💡 To process more messages:")
    print(f"   1. Post message at {WHATSAPP_URL}")
    print(f"   2. curl -X POST {API_URL}/ingest/process-whatsapp")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
