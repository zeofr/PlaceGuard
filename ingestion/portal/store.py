"""Portal data store for reading SIS JSON data.

Handles loading and parsing the portal JSON file that simulates
Student Information System placement event data.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class PortalStore:
    """Store for portal (SIS) placement event data."""
    
    def __init__(self, store_path: str | Path = "data/sis_data.json"):
        """Initialize portal store.
        
        Args:
            store_path: Path to SIS data JSON file
        """
        self.store_path = Path(store_path)
        
        if not self.store_path.exists():
            raise FileNotFoundError(
                f"Portal data file not found: {self.store_path}. "
                f"Expected SIS data at {self.store_path.absolute()}"
            )
    
    def load_events(self) -> list[dict[str, Any]]:
        """Load all placement events from portal JSON.
        
        Returns:
            List of placement event dicts
            
        Raises:
            ValueError: If JSON is malformed
        """
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Validate structure
            if not isinstance(data, dict):
                raise ValueError("Portal data must be a JSON object")
            
            if "placement_events" not in data:
                raise ValueError("Portal data must have 'placement_events' key")
            
            events = data["placement_events"]
            
            if not isinstance(events, list):
                raise ValueError("'placement_events' must be a list")
            
            return events
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in portal data: {e}") from e
    
    def get_metadata(self) -> dict[str, Any]:
        """Get portal metadata (sync info, version, etc.).
        
        Returns:
            Portal metadata dict
        """
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return data.get("portal_metadata", {})
            
        except (json.JSONDecodeError, IOError):
            return {}
    
    def get_event_by_id(self, event_id: str) -> dict[str, Any] | None:
        """Get a specific event by ID.
        
        Args:
            event_id: Portal event ID
            
        Returns:
            Event dict or None if not found
        """
        events = self.load_events()
        
        for event in events:
            if event.get("event_id") == event_id:
                return event
        
        return None
    
    def get_events_by_company(self, company_name: str) -> list[dict[str, Any]]:
        """Get all events for a specific company.
        
        Args:
            company_name: Company name (case-insensitive)
            
        Returns:
            List of event dicts
        """
        events = self.load_events()
        company_lower = company_name.lower()
        
        return [
            event for event in events
            if event.get("company_name", "").lower() == company_lower
        ]
