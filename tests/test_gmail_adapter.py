"""Unit tests for Gmail adapter.

Tests email fetching, parsing, and label management.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch
import pytest

from core.schemas import RawMessage, SenderRole, SourceType
from ingestion.gmail.adapter import GmailAdapter, get_gmail_adapter


class TestGmailAdapter:
    """Test Gmail adapter functionality."""
    
    def test_init(self):
        """Test adapter initialization."""
        mock_auth = Mock()
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="placement@college.edu",
            max_results=50,
            only_unread=False,
        )
        
        assert adapter.authenticator == mock_auth
        assert adapter.placement_officer_email == "placement@college.edu"
        assert adapter.max_results == 50
        assert adapter.only_unread is False
        assert adapter._service is None
    
    @patch("ingestion.gmail.adapter.build")
    def test_get_service_creates_service(self, mock_build):
        """Test Gmail service creation."""
        mock_auth = Mock()
        mock_creds = Mock()
        mock_auth.get_credentials.return_value = mock_creds
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="test@test.com",
        )
        
        service = adapter._get_service()
        
        assert service == mock_service
        mock_auth.get_credentials.assert_called_once()
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
    
    @patch("ingestion.gmail.adapter.build")
    @patch("ingestion.gmail.adapter.build_gmail_query")
    def test_fetch_no_emails(self, mock_query, mock_build):
        """Test fetching when no emails match criteria."""
        mock_auth = Mock()
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock Gmail API service
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Mock empty response
        mock_service.users().messages().list().execute.return_value = {"messages": []}
        
        mock_query.return_value = "from:test@test.com"
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="test@test.com",
        )
        
        messages = adapter.fetch()
        
        assert messages == []
        mock_query.assert_called_once()
    
    @patch("ingestion.gmail.adapter.build")
    @patch("ingestion.gmail.adapter.build_gmail_query")
    @patch("ingestion.gmail.adapter.parse_gmail_message")
    @patch("ingestion.gmail.adapter.is_email_from_sender")
    @patch("ingestion.gmail.adapter.get_email_body_text")
    def test_fetch_emails_success(
        self,
        mock_get_body,
        mock_is_from_sender,
        mock_parse,
        mock_query,
        mock_build,
    ):
        """Test successful email fetching."""
        mock_auth = Mock()
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock Gmail API service
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Mock email list response
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg_001"}]
        }
        
        # Mock get message response
        mock_message_data = {
            "id": "msg_001",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Placement <placement@college.edu>"},
                    {"name": "Subject", "value": "Test Notice"},
                    {"name": "Date", "value": "Mon, 26 Oct 2026 10:00:00 +0000"},
                ]
            },
        }
        mock_service.users().messages().get().execute.return_value = mock_message_data
        
        # Mock parsing functions
        mock_parse.return_value = {
            "message_id": "msg_001",
            "from": "Placement <placement@college.edu>",
            "subject": "Test Notice",
            "date": datetime(2026, 10, 26, 10, 0, 0),
            "body_plain": "Test body",
            "body_html": "",
        }
        mock_is_from_sender.return_value = True
        mock_get_body.return_value = "Test body"
        mock_query.return_value = "from:placement@college.edu"
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="placement@college.edu",
        )
        
        messages = adapter.fetch()
        
        assert len(messages) == 1
        assert isinstance(messages[0], RawMessage)
        assert messages[0].message_id == "msg_001"
        assert messages[0].source_type == SourceType.PLACEMENT_CELL_EMAIL
        assert messages[0].sender_role == SenderRole.PLACEMENT_CELL
        assert "Test Notice" in messages[0].body
    
    @patch("ingestion.gmail.adapter.build")
    @patch("ingestion.gmail.adapter.build_gmail_query")
    @patch("ingestion.gmail.adapter.parse_gmail_message")
    @patch("ingestion.gmail.adapter.is_email_from_sender")
    def test_fetch_skips_non_placement_officer_emails(
        self,
        mock_is_from_sender,
        mock_parse,
        mock_query,
        mock_build,
    ):
        """Test that emails not from placement officer are skipped."""
        mock_auth = Mock()
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock Gmail API service
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Mock email list response
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg_001"}]
        }
        
        # Mock get message response
        mock_message_data = {"id": "msg_001", "payload": {"headers": []}}
        mock_service.users().messages().get().execute.return_value = mock_message_data
        
        # Mock parsing to return different sender
        mock_parse.return_value = {
            "message_id": "msg_001",
            "from": "other@college.edu",
            "subject": "Test",
            "date": datetime(2026, 10, 26, 10, 0, 0),
            "body_plain": "Test",
            "body_html": "",
        }
        mock_is_from_sender.return_value = False
        mock_query.return_value = "from:placement@college.edu"
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="placement@college.edu",
        )
        
        messages = adapter.fetch()
        
        # Should skip the email
        assert len(messages) == 0
    
    @patch("ingestion.gmail.adapter.build")
    @patch("ingestion.gmail.adapter.get_or_create_label")
    @patch("ingestion.gmail.adapter.add_label_to_message")
    def test_mark_as_processed(
        self,
        mock_add_label,
        mock_get_label,
        mock_build,
    ):
        """Test marking emails as processed."""
        mock_auth = Mock()
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock Gmail API service
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Mock label operations
        mock_get_label.return_value = "label_123"
        mock_add_label.return_value = True
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="test@test.com",
        )
        
        count = adapter.mark_as_processed(["msg_001", "msg_002"])
        
        assert count == 2
        mock_get_label.assert_called_once()
        assert mock_add_label.call_count == 2
    
    @patch("ingestion.gmail.adapter.build")
    def test_mark_as_read(self, mock_build):
        """Test marking emails as read."""
        mock_auth = Mock()
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock Gmail API service
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Mock modify response
        mock_service.users().messages().modify().execute.return_value = {}
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="test@test.com",
        )
        
        count = adapter.mark_as_read(["msg_001"])
        
        assert count == 1
        # Check that modify was called with correct parameters
        mock_service.users().messages().modify.assert_called_with(
            userId="me",
            id="msg_001",
            body={"removeLabelIds": ["UNREAD"]},
        )
    
    def test_mark_as_processed_empty_list(self):
        """Test marking empty list returns 0."""
        mock_auth = Mock()
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="test@test.com",
        )
        
        count = adapter.mark_as_processed([])
        
        assert count == 0
    
    def test_mark_as_read_empty_list(self):
        """Test marking empty list as read returns 0."""
        mock_auth = Mock()
        
        adapter = GmailAdapter(
            authenticator=mock_auth,
            placement_officer_email="test@test.com",
        )
        
        count = adapter.mark_as_read([])
        
        assert count == 0


class TestGetGmailAdapter:
    """Test Gmail adapter factory function."""
    
    @patch("config.settings")
    @patch("ingestion.gmail.auth.get_gmail_authenticator")
    def test_factory_with_defaults(self, mock_get_auth, mock_settings):
        """Test factory function uses config defaults."""
        mock_settings.placement_officer_email = "placement@college.edu"
        mock_auth = Mock()
        mock_get_auth.return_value = mock_auth
        
        adapter = get_gmail_adapter()
        
        assert isinstance(adapter, GmailAdapter)
        assert adapter.placement_officer_email == "placement@college.edu"
        mock_get_auth.assert_called_once()
    
    @patch("config.settings")
    @patch("ingestion.gmail.auth.get_gmail_authenticator")
    def test_factory_with_overrides(self, mock_get_auth, mock_settings):
        """Test factory function with overrides."""
        mock_settings.placement_officer_email = "default@college.edu"
        custom_auth = Mock()
        
        adapter = get_gmail_adapter(
            authenticator=custom_auth,
            placement_officer_email="custom@college.edu",
        )
        
        assert adapter.authenticator == custom_auth
        assert adapter.placement_officer_email == "custom@college.edu"
        mock_get_auth.assert_not_called()
    
    @patch("config.settings")
    def test_factory_raises_without_email(self, mock_settings):
        """Test factory raises error if placement officer email not configured."""
        mock_settings.placement_officer_email = None
        
        with pytest.raises(ValueError) as exc_info:
            get_gmail_adapter()
        
        assert "PLACEMENT_OFFICER_EMAIL" in str(exc_info.value)
