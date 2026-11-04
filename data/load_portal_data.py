#!/usr/bin/env python3
"""Load portal (SIS) data into PlaceGuard database.

This script ingests placement events from the Student Information System portal,
extracts eligibility criteria, and stores them in the database. The portal data
is processed through the same pipeline as email/WhatsApp sources.

Portal authority rank: 4 (lower than email/WhatsApp, higher than student forwards)

Usage (from project root):
    python data/load_portal_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db
from database.connection import get_db_context
from database.crud import create_drive, get_drive, get_fact_by_source
from extraction.llm_client import get_llm_client
from extraction.notice_extractor import extract_criteria_from_notice
from ingestion.portal.adapter import PortalAdapter
from reconciliation.temporal_provenance_engine import reconcile_facts_for_drive


def normalize_drive_id(company_name: str) -> str:
    """Generate drive_id from company name.
    
    Args:
        company_name: Full company name
        
    Returns:
        Drive ID in format DRIVE_COMPANYNAME
    """
    # Remove special characters and spaces, uppercase
    normalized = company_name.upper()
    normalized = normalized.replace(" ", "")
    normalized = "".join(c for c in normalized if c.isalnum())
    
    return f"DRIVE_{normalized}"


def load_portal_data(use_llm: bool = False) -> dict:
    """Load portal data and process through ingestion pipeline.
    
    Args:
        use_llm: If True, use LLM to extract criteria. If False, skip extraction.
                 (Set to False to load portal events without requiring API key)
    
    Returns:
        Dict with counts of processed items
    """
    print("=" * 70)
    print("LOADING PORTAL (SIS) DATA")
    print("=" * 70)
    print()
    
    # Initialize adapter
    portal_adapter = PortalAdapter()
    
    # Get portal metadata
    metadata = portal_adapter.get_metadata()
    if metadata:
        print(f"Portal: {metadata.get('portal_name', 'Unknown')}")
        print(f"Version: {metadata.get('portal_version', 'Unknown')}")
        print(f"Last Sync: {metadata.get('portal_last_sync', 'Unknown')}")
        print()
    
    # Fetch portal events as RawMessages
    print("📊 Fetching portal events...")
    messages = portal_adapter.fetch()
    print(f"   Found {len(messages)} placement events in portal")
    print()
    
    if not messages:
        print("⚠️  No portal events found!")
        return {"messages": 0, "drives": 0, "facts": 0, "reconciled_drives": 0}
    
    # Initialize database
    init_db()
    
    stats = {
        "messages": len(messages),
        "drives_created": 0,
        "facts_extracted": 0,
        "messages_processed": 0,
        "messages_skipped": 0,
        "reconciled_drives": 0,
    }
    
    drives_affected = set()
    
    with get_db_context() as db:
        # Initialize LLM client if needed
        llm_client = get_llm_client() if use_llm else None
        
        if not use_llm:
            print("⚠️  LLM extraction disabled. Events will be loaded without criteria extraction.")
            print("   To enable extraction, run with use_llm=True and set GEMINI_API_KEY in .env")
            print()
        
        print("🔄 Processing portal events...")
        print()
        
        for i, msg in enumerate(messages, 1):
            # Extract company name from message
            # Format: "=== Company Name ==="
            company_line = msg.body.split("\n")[0]
            company_name = company_line.replace("=", "").strip()
            
            # Generate drive_id
            drive_id = normalize_drive_id(company_name)
            
            # Check if already processed
            existing_facts = get_fact_by_source(db, msg.message_id)
            if existing_facts:
                print(f"   [{i}/{len(messages)}] ⏭️  {company_name}: Already processed (skipping)")
                stats["messages_skipped"] += 1
                continue
            
            # Ensure drive exists
            drive = get_drive(db, drive_id)
            if not drive:
                drive = create_drive(db, drive_id=drive_id, company_name=company_name)
                stats["drives_created"] += 1
            
            # Extract criteria if LLM is enabled
            if use_llm:
                try:
                    facts = extract_criteria_from_notice(
                        notice_text=msg.body,
                        source_id=msg.message_id,
                        source_type=msg.source_type,
                        timestamp=msg.timestamp,
                        drive_id=drive_id,
                        llm_client=llm_client,
                    )
                    
                    # Store facts
                    for fact in facts:
                        db.add(fact)
                    db.commit()
                    
                    stats["facts_extracted"] += len(facts)
                    drives_affected.add(drive_id)
                    
                    print(f"   [{i}/{len(messages)}] ✅ {company_name}: {len(facts)} criteria extracted")
                    
                except Exception as e:
                    print(f"   [{i}/{len(messages)}] ❌ {company_name}: Error - {e}")
                    continue
            else:
                print(f"   [{i}/{len(messages)}] ⏭️  {company_name}: Loaded (no extraction)")
            
            stats["messages_processed"] += 1
        
        print()
        
        # Run reconciliation for affected drives
        if drives_affected and use_llm:
            print("🔄 Running reconciliation for affected drives...")
            for drive_id in drives_affected:
                reconcile_facts_for_drive(db, drive_id, persist=True)
                stats["reconciled_drives"] += 1
            print(f"   ✅ Reconciled {stats['reconciled_drives']} drives")
            print()
    
    return stats


def main() -> None:
    """Main entry point."""
    # Try the LLM provider actually configured in .env (LLM_PROVIDER — Ollama,
    # Gemini, OpenAI, or Claude), not just a hardcoded Gemini-key check, so
    # local Ollama users get real extraction too instead of silently skipping it.
    try:
        get_llm_client()
        use_llm = True
    except ValueError as e:
        print(f"⚠️  LLM client unavailable ({e})")
        print("   Portal events will be loaded WITHOUT criteria extraction.")
        print()
        use_llm = False

    stats = load_portal_data(use_llm=use_llm)
    
    print("=" * 70)
    print("✅ PORTAL DATA LOADING COMPLETE")
    print("=" * 70)
    print()
    print(f"📊 Statistics:")
    print(f"   • Portal events: {stats['messages']}")
    print(f"   • Drives created: {stats['drives_created']}")
    print(f"   • Messages processed: {stats['messages_processed']}")
    print(f"   • Messages skipped: {stats['messages_skipped']}")
    
    if use_llm:
        print(f"   • Facts extracted: {stats['facts_extracted']}")
        print(f"   • Drives reconciled: {stats['reconciled_drives']}")
    
    print()
    print("💡 Next steps:")
    print("   1. Compare portal data with email/WhatsApp:")
    print("      python -c \"from reconciliation.temporal_provenance_engine import *\"")
    print()
    print("   2. Test reconciliation scenarios:")
    print("      - KPMG deadline conflict (portal vs WhatsApp)")
    print("      - NVIDIA CGPA conflict (portal 7.5 vs email 7.8)")
    print()
    print("   3. View in frontend:")
    print("      cd frontend && npm run dev")
    print("      Open http://localhost:3000")
    print()


if __name__ == "__main__":
    main()
