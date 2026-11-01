"""Test script for mock WhatsApp and Email adapters."""

import sys
sys.path.insert(0, "d:\\PLACEGUARD-ZAID\\PlaceGuard")

from ingestion.mock_email.adapter import MockEmailAdapter
from ingestion.mock_whatsapp.adapter import MockWhatsAppAdapter

print("=" * 60)
print("TESTING MOCK EMAIL ADAPTER")
print("=" * 60)

email_adapter = MockEmailAdapter()
email_messages = email_adapter.fetch()

print(f"\nFound {len(email_messages)} email messages:\n")

for msg in email_messages:
    print(f"📧 Message ID: {msg.message_id}")
    print(f"   Source Type: {msg.source_type.value}")
    print(f"   Sender: {msg.sender_id} ({msg.sender_role.value})")
    print(f"   Timestamp: {msg.timestamp}")
    print(f"   Forwarded: {msg.is_forwarded}")
    print(f"   Body preview: {msg.body[:100]}...")
    print()

print("=" * 60)
print("TESTING MOCK WHATSAPP ADAPTER")
print("=" * 60)

whatsapp_adapter = MockWhatsAppAdapter()
whatsapp_messages = whatsapp_adapter.fetch()

print(f"\nFound {len(whatsapp_messages)} WhatsApp messages:\n")

if whatsapp_messages:
    for msg in whatsapp_messages:
        print(f"💬 Message ID: {msg.message_id}")
        print(f"   Source Type: {msg.source_type.value}")
        print(f"   Sender: {msg.sender_id} ({msg.sender_role.value})")
        print(f"   Timestamp: {msg.timestamp}")
        print(f"   Forwarded: {msg.is_forwarded}")
        print(f"   Body: {msg.body}")
        print()
else:
    print("No WhatsApp messages yet. Start the WhatsApp console and post some:")
    print("  uvicorn ingestion.mock_whatsapp.console:app --reload --port 8001")
    print("  Then visit http://localhost:8001")

print("=" * 60)
print("TESTING COMPLETE")
print("=" * 60)
