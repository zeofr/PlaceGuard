"""Gmail API integration for PlaceGuard.

This package provides Gmail email ingestion with:
- OAuth 2.0 authentication
- Email fetching and parsing
- LLM-based email classification
- Background polling service
"""

from ingestion.gmail.adapter import GmailAdapter
from ingestion.gmail.auth import GmailAuthenticator

__all__ = ["GmailAdapter", "GmailAuthenticator"]
