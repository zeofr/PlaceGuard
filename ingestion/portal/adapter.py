"""Portal adapter for PlaceGuard ingestion pipeline.

Implements the SourceAdapter interface for SIS (Student Information System) portal data.
The portal provides semi-structured placement events but often has stale or conflicting
information compared to real-time email/WhatsApp updates.

Authority Rank: 4 (Portal < Email/WhatsApp < Official PDF, but > Student forwards)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.schemas import RawMessage, SenderRole, SourceType
from ingestion.adapters.base import SourceAdapter
from ingestion.portal.store import PortalStore


class PortalAdapter(SourceAdapter):
    """Portal source adapter using JSON file storage for testing.
    
    Reads placement events from the Student Information System portal data file.
    In production, this would connect to an actual portal API/scraper.
    
    Authority rank: 4 (lower than placement cell communications, but authoritative
    for basic event information like dates, company names, LPA).
    """
    
    def __init__(self, store_path: str | None = None):
        """Initialize portal adapter.
        
        Args:
            store_path: Optional path to portal JSON file
        """
        self.store = PortalStore(store_path) if store_path else PortalStore()
    
    def fetch(self) -> list[RawMessage]:
        """Fetch all portal events and convert to RawMessage format.
        
        Returns:
            List of RawMessage objects representing portal events
        """
        events = self.store.load_events()
        raw_messages = []
        
        for event in events:
            try:
                raw_message = self._event_to_raw_message(event)
                raw_messages.append(raw_message)
            except (KeyError, ValueError) as e:
                # Skip malformed events
                event_id = event.get("event_id", "unknown")
                print(f"Warning: Skipping malformed portal event {event_id}: {e}")
                continue
        
        return raw_messages
    
    def _event_to_raw_message(self, event: dict[str, Any]) -> RawMessage:
        """Convert portal event dict to RawMessage.
        
        Args:
            event: Portal event dict from sis_data.json
        
        Returns:
            RawMessage object
            
        Raises:
            KeyError: If required fields are missing
            ValueError: If data is malformed
        """
        # Required fields
        event_id = event["event_id"]
        company_name = event["company_name"]
        
        # Parse portal timestamp (when event was posted/updated)
        portal_timestamp_str = event.get(
            "portal_last_updated",
            event.get("portal_posted_date")
        )
        
        if not portal_timestamp_str:
            raise ValueError(f"Event {event_id} missing portal timestamp")
        
        portal_timestamp = self._parse_timestamp(portal_timestamp_str)
        
        # Build message body from portal event data
        # This simulates what would be scraped from an HTML portal page
        body = self._build_message_body(event)
        
        # Create unique message ID for portal events
        message_id = f"portal_{event_id}"
        
        return RawMessage(
            message_id=message_id,
            source_type=SourceType.STUDENT_PORTAL,
            sender_id="sis_portal",
            sender_role=SenderRole.COORDINATOR,  # Portal maintained by placement office
            timestamp=portal_timestamp,
            body=body,
            message_type="portal_event",
            is_forwarded=False,
        )
    
    def _build_message_body(self, event: dict[str, Any]) -> str:
        """Build message body text from portal event data.
        
        Converts structured portal event into a text format that resembles
        what the LLM extraction would see from a scraped portal page.
        
        Args:
            event: Portal event dict
            
        Returns:
            Formatted message body text
        """
        lines = []
        
        # Header
        lines.append(f"=== {event['company_name']} ===")
        lines.append("")
        
        # Job details
        if event.get("job_title"):
            lines.append(f"Position: {event['job_title']}")
        
        if event.get("role_designation"):
            lines.append(f"Role: {event['role_designation']}")
        
        if event.get("employment_type"):
            lines.append(f"Type: {event['employment_type']}")
        
        if event.get("lpa"):
            lpa_value = float(event['lpa']) / 100000
            lines.append(f"Package: {lpa_value:.1f} LPA")
        
        lines.append("")
        
        # Eligibility criteria (the most important part for extraction)
        if event.get("eligibility_criteria"):
            lines.append("Eligibility Criteria:")
            lines.append(event["eligibility_criteria"])
            lines.append("")
        
        # Deadlines
        if event.get("apply_before"):
            apply_before_str = event["apply_before"]
            try:
                apply_dt = self._parse_timestamp(apply_before_str)
                lines.append(f"Application Deadline: {apply_dt.strftime('%d-%m-%Y %I:%M %p')}")
            except ValueError:
                lines.append(f"Application Deadline: {apply_before_str}")
        
        if event.get("event_date"):
            event_date_str = event["event_date"]
            try:
                event_dt = self._parse_timestamp(event_date_str)
                lines.append(f"Event Date: {event_dt.strftime('%d-%m-%Y')}")
            except ValueError:
                lines.append(f"Event Date: {event_date_str}")
        
        lines.append("")
        
        # Additional details
        if event.get("work_mode"):
            lines.append(f"Work Mode: {event['work_mode']}")
        
        if event.get("bond_agreement") and event["bond_agreement"] != "NA":
            lines.append(f"Bond: {event['bond_agreement']}")
        
        if event.get("preferred_skills"):
            skills = event["preferred_skills"]
            if isinstance(skills, list):
                lines.append(f"Preferred Skills: {', '.join(skills)}")
            else:
                lines.append(f"Preferred Skills: {skills}")
        
        lines.append("")
        
        # Portal metadata
        lines.append(f"Status: {event.get('registration_status', 'UNKNOWN')}")
        lines.append(f"Posted: {event.get('time_since_posted', 'Unknown')}")
        
        # Add notes if present (for debugging/testing)
        if event.get("notes"):
            lines.append("")
            lines.append(f"[PORTAL NOTE: {event['notes']}]")
        
        return "\n".join(lines)
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse ISO timestamp string.
        
        Args:
            timestamp_str: ISO 8601 timestamp string
            
        Returns:
            datetime object
            
        Raises:
            ValueError: If timestamp format is invalid
        """
        # Handle both with and without timezone
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str.replace("Z", "+00:00")
        
        try:
            # Try ISO format with timezone
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            # Try ISO format without timezone
            return datetime.fromisoformat(timestamp_str)
    
    def get_metadata(self) -> dict[str, Any]:
        """Get portal metadata.
        
        Returns:
            Portal metadata dict (sync time, version, etc.)
        """
        return self.store.get_metadata()
