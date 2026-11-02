"""Test portal (SIS) integration.

Tests the complete portal ingestion pipeline:
- Loading portal data from JSON
- Converting to RawMessage format
- Extracting criteria with LLM
- Reconciliation with email/WhatsApp sources
"""

import json
from pathlib import Path

import pytest

from core.schemas import RawMessage, SourceType
from ingestion.portal.adapter import PortalAdapter
from ingestion.portal.store import PortalStore


class TestPortalStore:
    """Test portal data store functionality."""
    
    def test_load_events(self):
        """Test loading events from portal JSON."""
        store = PortalStore("data/sis_data.json")
        events = store.load_events()
        
        assert len(events) > 0
        assert isinstance(events, list)
        
        # Check first event structure
        first_event = events[0]
        assert "event_id" in first_event
        assert "company_name" in first_event
        assert "eligibility_criteria" in first_event
    
    def test_get_metadata(self):
        """Test getting portal metadata."""
        store = PortalStore("data/sis_data.json")
        metadata = store.get_metadata()
        
        assert isinstance(metadata, dict)
        assert "portal_name" in metadata
        assert metadata["portal_name"] == "MSRIT Student Information System"
    
    def test_get_event_by_id(self):
        """Test retrieving specific event by ID."""
        store = PortalStore("data/sis_data.json")
        event = store.get_event_by_id("SIS_KPMG_001")
        
        assert event is not None
        assert event["company_name"] == "KPMG Global Services"
    
    def test_get_events_by_company(self):
        """Test retrieving events for a specific company."""
        store = PortalStore("data/sis_data.json")
        events = store.get_events_by_company("KPMG Global Services")
        
        assert len(events) > 0
        assert all(e["company_name"] == "KPMG Global Services" for e in events)


class TestPortalAdapter:
    """Test portal adapter functionality."""
    
    def test_adapter_initialization(self):
        """Test adapter can be initialized."""
        adapter = PortalAdapter()
        assert adapter is not None
        assert isinstance(adapter.store, PortalStore)
    
    def test_fetch_returns_raw_messages(self):
        """Test fetch returns list of RawMessage objects."""
        adapter = PortalAdapter()
        messages = adapter.fetch()
        
        assert len(messages) > 0
        assert all(isinstance(msg, RawMessage) for msg in messages)
    
    def test_raw_message_format(self):
        """Test RawMessage format from portal events."""
        adapter = PortalAdapter()
        messages = adapter.fetch()
        
        first_msg = messages[0]
        
        # Check required fields
        assert first_msg.message_id.startswith("portal_")
        assert first_msg.source_type == SourceType.STUDENT_PORTAL
        assert first_msg.sender_id == "sis_portal"
        assert first_msg.timestamp is not None
        assert len(first_msg.body) > 0
        
        # Check body format
        assert "===" in first_msg.body  # Company header
        assert "Eligibility" in first_msg.body
    
    def test_message_body_contains_criteria(self):
        """Test that message body includes eligibility criteria."""
        adapter = PortalAdapter()
        messages = adapter.fetch()
        
        # Find KPMG message
        kpmg_msg = next(m for m in messages if "KPMG" in m.body)
        
        assert "Eligibility Criteria:" in kpmg_msg.body
        assert "60%" in kpmg_msg.body or "CGPA" in kpmg_msg.body
    
    def test_timestamp_parsing(self):
        """Test timestamp parsing from portal events."""
        adapter = PortalAdapter()
        messages = adapter.fetch()
        
        # All messages should have valid timestamps
        for msg in messages:
            assert msg.timestamp is not None
            assert msg.timestamp.year == 2026
    
    def test_get_metadata(self):
        """Test getting metadata through adapter."""
        adapter = PortalAdapter()
        metadata = adapter.get_metadata()
        
        assert "portal_name" in metadata
        assert "portal_version" in metadata


class TestPortalConflicts:
    """Test conflict scenarios between portal and other sources."""
    
    def test_kpmg_deadline_conflict_documented(self):
        """Test KPMG deadline conflict is present in data."""
        store = PortalStore("data/sis_data.json")
        kpmg_event = store.get_event_by_id("SIS_KPMG_001")
        
        assert kpmg_event is not None
        
        # Check conflict is documented in notes
        assert "CONFLICT" in kpmg_event.get("notes", "")
        assert "deadline" in kpmg_event.get("notes", "").lower()
        
        # Portal should have old deadline
        assert kpmg_event["apply_before"] == "2026-10-29T17:30:00"
    
    def test_nvidia_cgpa_conflict_documented(self):
        """Test NVIDIA CGPA conflict is present in data."""
        store = PortalStore("data/sis_data.json")
        nvidia_event = store.get_event_by_id("SIS_NVIDIA_001")
        
        assert nvidia_event is not None
        
        # Check conflict is documented
        assert "CONFLICT" in nvidia_event.get("notes", "")
        assert "7.5" in nvidia_event.get("eligibility_criteria", "")
    
    def test_consistent_events_documented(self):
        """Test some events are marked as consistent."""
        store = PortalStore("data/sis_data.json")
        boeing_event = store.get_event_by_id("SIS_BOEING_001")
        
        assert boeing_event is not None
        assert "CONSISTENT" in boeing_event.get("notes", "")


class TestPortalDataQuality:
    """Test portal data quality and completeness."""
    
    def test_all_events_have_required_fields(self):
        """Test all events have required fields."""
        store = PortalStore("data/sis_data.json")
        events = store.load_events()
        
        required_fields = [
            "event_id",
            "company_name",
            "eligibility_criteria",
            "apply_before",
            "portal_posted_date",
        ]
        
        for event in events:
            for field in required_fields:
                assert field in event, f"Event {event.get('event_id')} missing {field}"
    
    def test_event_ids_are_unique(self):
        """Test all event IDs are unique."""
        store = PortalStore("data/sis_data.json")
        events = store.load_events()
        
        event_ids = [e["event_id"] for e in events]
        assert len(event_ids) == len(set(event_ids)), "Duplicate event IDs found"
    
    def test_company_names_match_notices(self):
        """Test company names are consistent with notices.json."""
        # Load portal events
        portal_store = PortalStore("data/sis_data.json")
        portal_events = portal_store.load_events()
        portal_companies = {e["company_name"] for e in portal_events}
        
        # Load notices
        notices_path = Path("data/notices.json")
        with open(notices_path, "r", encoding="utf-8") as f:
            notices = json.load(f)
        notice_companies = {n["company"] for n in notices}
        
        # Portal should cover most companies from notices
        overlap = portal_companies & notice_companies
        assert len(overlap) >= 5, f"Expected at least 5 matching companies, found {len(overlap)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
