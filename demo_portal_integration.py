#!/usr/bin/env python3
"""Demo script showing portal integration and conflict resolution.

This script demonstrates:
1. Loading portal events
2. Converting to RawMessage format
3. How conflicts would be resolved with email/WhatsApp data
"""

from ingestion.portal.adapter import PortalAdapter
from ingestion.portal.store import PortalStore


def main():
    print("=" * 80)
    print("PLACEGUARD PORTAL (SIS) INTEGRATION DEMO")
    print("=" * 80)
    print()
    
    # Initialize portal adapter
    print("[*] Initializing Portal Adapter...")
    adapter = PortalAdapter()
    print("   [OK] Adapter initialized")
    print()
    
    # Get metadata
    print("[*] Portal Metadata:")
    metadata = adapter.get_metadata()
    print(f"   Portal Name: {metadata.get('portal_name')}")
    print(f"   Version: {metadata.get('portal_version')}")
    print(f"   Last Sync: {metadata.get('portal_last_sync')}")
    print(f"   Sync Frequency: {metadata.get('sync_frequency')}")
    print()
    
    # Fetch portal events
    print("[*] Fetching Portal Events...")
    messages = adapter.fetch()
    print(f"   [OK] Fetched {len(messages)} placement events")
    print()
    
    # Show event summary
    print("[*] Event Summary:")
    print(f"   {'Company':<30} {'Status':<15} {'Authority Rank'}")
    print("   " + "-" * 70)
    
    for msg in messages:
        # Extract company name from body
        company_line = msg.body.split("\n")[0]
        company = company_line.replace("=", "").strip()
        
        # Extract status from body
        status = "UNKNOWN"
        for line in msg.body.split("\n"):
            if line.startswith("Status:"):
                status = line.split(":")[1].strip()
                break
        
        print(f"   {company:<30} {status:<15} {4}")  # Portal always rank 4
    
    print()
    
    # Show detailed view of a few events
    print("=" * 80)
    print("DETAILED EVENT VIEWS")
    print("=" * 80)
    print()
    
    # Show KPMG (conflict example)
    print("[1] Example 1: KPMG Global Services (DEADLINE CONFLICT)")
    print("-" * 80)
    kpmg_msg = next(m for m in messages if "KPMG" in m.body)
    print(f"Message ID: {kpmg_msg.message_id}")
    print(f"Source Type: {kpmg_msg.source_type.value}")
    print(f"Authority Rank: 4 (Portal)")
    print(f"Timestamp: {kpmg_msg.timestamp}")
    print()
    print("Message Body (first 500 chars):")
    print(kpmg_msg.body[:500])
    print("...")
    print()
    print("[!] CONFLICT NOTE:")
    print("   Portal shows deadline: 5:30 PM (old)")
    print("   WhatsApp updated to: 12:00 noon")
    print("   --> WhatsApp wins (rank 2 > rank 4)")
    print()
    
    # Show NVIDIA (conflict example)
    print("[2] Example 2: NVIDIA (CGPA CONFLICT)")
    print("-" * 80)
    nvidia_msg = next(m for m in messages if "NVIDIA" in m.body)
    print(f"Message ID: {nvidia_msg.message_id}")
    print(f"Source Type: {nvidia_msg.source_type.value}")
    print(f"Authority Rank: 4 (Portal)")
    print(f"Timestamp: {nvidia_msg.timestamp}")
    print()
    print("Eligibility snippet:")
    for line in nvidia_msg.body.split("\n"):
        if "Eligibility" in line or "CGPA" in line or "7." in line:
            print(f"   {line}")
    print()
    print("[!] CONFLICT NOTE:")
    print("   Portal shows: CGPA 7.5 (old)")
    print("   Email says: CGPA 7.8 (corrected)")
    print("   --> Email wins (rank 2 > rank 4)")
    print()
    
    # Show Boeing (consistent example)
    print("[3] Example 3: Boeing India (CONSISTENT)")
    print("-" * 80)
    boeing_msg = next(m for m in messages if "Boeing" in m.body)
    print(f"Message ID: {boeing_msg.message_id}")
    print(f"Source Type: {boeing_msg.source_type.value}")
    print(f"Authority Rank: 4 (Portal)")
    print(f"Timestamp: {boeing_msg.timestamp}")
    print()
    print("Eligibility snippet:")
    for line in boeing_msg.body.split("\n"):
        if "Eligibility" in line or "CGPA" in line or "7." in line:
            print(f"   {line}")
    print()
    print("[OK] CONSISTENT:")
    print("   Portal data matches email notice")
    print("   No conflicts to resolve")
    print()
    
    # Explain authority hierarchy
    print("=" * 80)
    print("AUTHORITY HIERARCHY & RECONCILIATION")
    print("=" * 80)
    print()
    print("When conflicts occur, PlaceGuard uses this authority ranking:")
    print()
    print("   1. Official Company PDF        (rank 1) <- Highest authority")
    print("   2. Placement Cell Email        (rank 2)")
    print("   3. Placement Cell WhatsApp     (rank 2)")
    print("   4. Coordinator WhatsApp        (rank 3)")
    print("   5. ==> Student Portal (SIS)    (rank 4) <- YOU ARE HERE")
    print("   6. Student WhatsApp Forward    (rank 5) <- Lowest authority")
    print()
    print("Reconciliation Rules:")
    print("   • Higher authority ALWAYS wins in conflicts")
    print("   • Among same authority, latest timestamp wins")
    print("   • Explicit corrections (is_correction=True) override")
    print("   • Lower authority fills coverage gaps (new criteria)")
    print()
    
    # Next steps
    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("To load portal data into database:")
    print("   python data/load_portal_data.py")
    print()
    print("To test reconciliation:")
    print("   1. Load portal data (above)")
    print("   2. Load email/WhatsApp data: python data/load_data.py")
    print("   3. Check reconciliation results in database")
    print()
    print("To view in API:")
    print("   1. Start API: python -m uvicorn api.main:app --reload")
    print("   2. Sync portal: POST http://localhost:8000/ingest/sync-portal")
    print()
    print("To view in frontend:")
    print("   1. cd frontend")
    print("   2. npm run dev")
    print("   3. Open http://localhost:3000")
    print()


if __name__ == "__main__":
    main()
