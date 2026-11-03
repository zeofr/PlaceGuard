"""Gmail adapter implementing SourceAdapter interface for PlaceGuard.

Fetches emails from Gmail API and converts them to RawMessage objects
for processing through the standard ingestion pipeline.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from googleapiclient.errors import HttpError

from config import settings
from core.schemas import RawMessage, SenderRole, SourceType
from ingestion.adapters.base import SourceAdapter
from ingestion.gmail.auth import GmailAuthenticator, GmailAuthenticationError
from ingestion.gmail.utils import (
    create_message_id_from_gmail_id,
    extract_email_address,
    get_header_value,
    parse_email_body,
    parse_gmail_date,
)


class GmailAdapterError(Exception):
    """Raised when Gmail adapter operations fail."""
    pass


class GmailAdapter(SourceAdapter):
    """Gmail adapter for fetching placement emails.
    
    Implements SourceAdapter interface to fetch emails from Gmail,
    filtering by placement officer sender and converting to RawMessage format.
    """
    
    def __init__(
        self,
        authenticator: GmailAuthenticator | None = None,
        placement_officer_email: str | None = None,
        max_results: int = 100,
        days_back: int = 1,
    ):
        """Initialize Gmail adapter.
        
        Args:
            authenticator: Gmail authenticator (creates new one if None)
            placement_officer_email: Email address to filter by (uses config if None)
            max_results: Maximum number of emails to fetch per request
            days_back: How many days back to search for emails (default: 1 day)
        """
        self.authenticator = authenticator or GmailAuthenticator()
        self.placement_officer_email = (
            placement_officer_email or settings.placement_officer_email
        )
        self.max_results = max_results
        self.days_back = days_back
        
        if not self.placement_officer_email:
            raise GmailAdapterError(
                "Placement officer email not configured. "
                "Set PLACEMENT_OFFICER_EMAIL in .env file."
            )
        
        self._service = None
    
    @property
    def service(self):
        """Get Gmail API service (lazy initialization).
        
        Returns:
            Authenticated Gmail service
            
        Raises:
            GmailAdapterError: If authentication fails
        """
        if self._service is None:
            try:
                self._service = self.authenticator.get_gmail_service()
            except GmailAuthenticationError as e:
                raise GmailAdapterError(f"Gmail authentication failed: {e}") from e
        
        return self._service
    
    def fetch(self, only_unread: bool = True) -> list[RawMessage]:
        """Fetch emails from placement officer.
        
        Implements SourceAdapter.fetch() interface.
        
        Args:
            only_unread: If True, only fetch unread emails (default: True)
            
        Returns:
            List of RawMessage objects
            
        Raises:
            GmailAdapterError: If fetching emails fails
        """
        try:
            # Build query to filter emails
            query = self._build_query(only_unread)
            
            # List messages matching query
            message_ids = self._list_messages(query)
            
            if not message_ids:
                return []
            
            # Fetch full message details
            messages = []
            for msg_id in message_ids:
                try:
                    raw_message = self._fetch_and_convert_message(msg_id)
                    if raw_message:
                        messages.append(raw_message)
                except Exception as e:
                    # Log error but continue with other messages
                    print(f"Warning: Failed to fetch message {msg_id}: {e}")
                    continue

            # Gmail's "after:" query is date-granularity only (no time of day),
            # so it can over-fetch by up to a day depending on when this runs
            # (see _build_query). Enforce the precise window here.
            if self.days_back > 0:
                cutoff = datetime.utcnow() - timedelta(days=self.days_back)
                messages = [m for m in messages if m.timestamp >= cutoff]

            return messages
        
        except HttpError as e:
            raise GmailAdapterError(
                f"Gmail API error: {e.status_code} - {e.reason}"
            ) from e
        
        except Exception as e:
            raise GmailAdapterError(f"Failed to fetch Gmail messages: {e}") from e
    
    def _build_query(self, only_unread: bool) -> str:
        """Build Gmail search query.
        
        Args:
            only_unread: Whether to filter for unread messages
            
        Returns:
            Gmail query string
        """
        # Base query: filter by sender
        query_parts = [f"from:{self.placement_officer_email}"]
        
        # Add unread filter if requested
        if only_unread:
            query_parts.append("is:unread")
        
        # Add date filter (last N days). Gmail's "after:" only takes a date
        # (no time of day), so it can't express an exact N-day-ago instant -
        # querying the exact cutoff date would risk UNDER-fetching (e.g. running
        # at 9am would exclude today's early-morning mail from "yesterday's"
        # bucket). Widen by one extra day here; fetch() enforces the precise
        # cutoff afterwards against each message's actual timestamp.
        if self.days_back > 0:
            # Gmail uses YYYY/MM/DD format for dates
            query_cutoff_date = datetime.utcnow() - timedelta(days=self.days_back + 1)
            date_str = query_cutoff_date.strftime("%Y/%m/%d")
            query_parts.append(f"after:{date_str}")
        
        return " ".join(query_parts)
    
    def _list_messages(self, query: str) -> list[str]:
        """List message IDs matching query.
        
        Args:
            query: Gmail search query
            
        Returns:
            List of Gmail message IDs
        """
        try:
            response = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=self.max_results,
            ).execute()
            
            messages = response.get("messages", [])
            return [msg["id"] for msg in messages]
        
        except HttpError as e:
            if e.status_code == 404:
                # No messages found
                return []
            raise
    
    def _fetch_and_convert_message(self, message_id: str) -> RawMessage | None:
        """Fetch full message details and convert to RawMessage.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            RawMessage object or None if conversion fails
        """
        # Fetch full message
        message = self.service.users().messages().get(
            userId="me",
            id=message_id,
            format="full",  # Get full message with headers and body
        ).execute()
        
        # Extract headers
        headers = message.get("payload", {}).get("headers", [])
        
        from_header = get_header_value(headers, "From") or ""
        subject = get_header_value(headers, "Subject") or ""
        date_str = get_header_value(headers, "Date") or ""
        
        # Extract sender email
        sender_email = extract_email_address(from_header)
        
        # Verify sender matches placement officer
        if sender_email.lower() != self.placement_officer_email.lower():
            # Skip messages not from placement officer
            # (shouldn't happen due to query filter, but double-check)
            return None
        
        # Parse timestamp
        timestamp = parse_gmail_date(date_str)
        
        # Extract body
        payload = message.get("payload", {})
        body = parse_email_body(payload)
        
        # Include subject in body for context
        full_body = f"Subject: {subject}\n\n{body}"
        
        # Create unique message ID
        msg_id = create_message_id_from_gmail_id(message_id, sender_email)
        
        # Determine if forwarded (heuristic - check for "Fwd:" in subject)
        is_forwarded = subject.lower().startswith("fwd:") or "forwarded" in subject.lower()
        
        # Create RawMessage
        raw_message = RawMessage(
            message_id=msg_id,
            source_type=SourceType.PLACEMENT_CELL_EMAIL,
            sender_id=sender_email,
            sender_role=SenderRole.PLACEMENT_CELL,
            timestamp=timestamp,
            body=full_body,
            message_type="email",
            is_forwarded=is_forwarded,
        )
        
        return raw_message
    
    def mark_as_read(self, message_id: str) -> None:
        """Mark a Gmail message as read.
        
        Args:
            message_id: Gmail message ID (not our internal message_id)
        """
        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
        
        except HttpError as e:
            print(f"Warning: Could not mark message {message_id} as read: {e}")
    
    def add_label(self, message_id: str, label_name: str) -> None:
        """Add a label to a Gmail message.
        
        Creates the label if it doesn't exist.
        
        Args:
            message_id: Gmail message ID (not our internal message_id)
            label_name: Label name (e.g., "PlaceGuard/Processed")
        """
        try:
            # Get or create label ID
            label_id = self._get_or_create_label(label_name)
            
            # Add label to message
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_id]},
            ).execute()
        
        except HttpError as e:
            print(f"Warning: Could not add label to message {message_id}: {e}")
    
    def _get_or_create_label(self, label_name: str) -> str:
        """Get label ID by name, creating it if it doesn't exist.
        
        Args:
            label_name: Label name (supports nested labels with '/')
            
        Returns:
            Gmail label ID
        """
        # List existing labels
        try:
            response = self.service.users().labels().list(userId="me").execute()
            labels = response.get("labels", [])
            
            # Check if label exists
            for label in labels:
                if label["name"] == label_name:
                    return label["id"]
            
            # Label doesn't exist - create it
            label_object = {
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            }
            
            created_label = self.service.users().labels().create(
                userId="me",
                body=label_object,
            ).execute()
            
            return created_label["id"]
        
        except HttpError as e:
            print(f"Warning: Could not get/create label {label_name}: {e}")
            # Return dummy ID to prevent errors
            return "INBOX"
    
    def extract_gmail_id_from_message_id(self, message_id: str) -> str | None:
        """Extract Gmail message ID from our internal message_id.
        
        Our format: gmail_{gmail_id}_{sender_email}
        
        Args:
            message_id: Our internal message ID
            
        Returns:
            Gmail message ID or None if not a Gmail message
        """
        if not message_id.startswith("gmail_"):
            return None
        
        # Extract gmail_id from format: gmail_{gmail_id}_{sender_email}
        parts = message_id.split("_", 2)
        if len(parts) >= 2:
            return parts[1]
        
        return None
