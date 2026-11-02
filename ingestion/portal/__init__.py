"""Portal (SIS) ingestion module for PlaceGuard.

This module handles ingestion from the Student Information System (SIS) portal,
which provides semi-structured placement event data. The portal typically has
lower authority than email/WhatsApp sources and may contain stale or conflicting
information, making it an ideal test case for temporal+provenance reconciliation.

Authority rank: 4 (lower than placement cell email/WhatsApp, higher than student forwards)
"""

from ingestion.portal.adapter import PortalAdapter
from ingestion.portal.store import PortalStore

__all__ = ["PortalAdapter", "PortalStore"]
