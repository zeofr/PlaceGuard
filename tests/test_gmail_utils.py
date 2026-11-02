"""Unit tests for Gmail utility functions.

Tests email parsing, HTML conversion, and query building.
"""

import base64
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from ingestion.gmail.utils import (
    add_label_to_message,
    build_gmail_query,
    decode_body_data,
    extract_email_address,
    extract_message_body,
    get_email_body_text,
    get_or_create_label,
    html_to_text,
    is_email_from_sender,
    parse_email_date,
    parse_gmail_message,
)


class TestDecodeBodyData:
    """Test base64url decoding."""
    
    def test_decode_valid_data(self):
        """Test decoding valid base64url data."""
        text = "Hello, World!"
        encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")
        
        decoded = decode_body_data(encoded)
        
        assert decoded == text
    
    def test_decode_empty_string(self):
        """Test decoding empty string."""
        assert decode_body_data("") == ""
    
    def test_decode_invalid_data(self):
        """Test decoding invalid data returns empty string."""
        assert decode_body_data("invalid!!!") == ""


class TestExtractMessageBody:
    """Test email body extraction."""
    
    def test_extract_plain_text_only(self):
        """Test extracting plain text body."""
        encoded_body = base64.urlsafe_b64encode(b"Plain text").decode()
        payload = {
            "mimeType": "text/plain",
            "body": {"data": encoded_body},
        }
        
        plain, html = extract_message_body(payload)
        
        assert plain == "Plain text"
        assert html == ""
    
    def test_extract_html_only(self):
        """Test extracting HTML body."""
        encoded_body = base64.urlsafe_b64encode(b"<p>HTML</p>").decode()
        payload = {
            "mimeType": "text/html",
            "body": {"data": encoded_body},
        }
        
        plain, html = extract_message_body(payload)
        
        assert plain == ""
        assert html == "<p>HTML</p>"
    
    def test_extract_multipart(self):
        """Test extracting multipart message."""
        plain_encoded = base64.urlsafe_b64encode(b"Plain text").decode()
        html_encoded = base64.urlsafe_b64encode(b"<p>HTML</p>").decode()
        
        payload = {
            "parts": [
                {"mimeType": "text/plain", "body": {"data": plain_encoded}},
                {"mimeType": "text/html", "body": {"data": html_encoded}},
            ]
        }
        
        plain, html = extract_message_body(payload)
        
        assert plain == "Plain text"
        assert html == "<p>HTML</p>"


class TestHtmlToText:
    """Test HTML to plain text conversion."""
    
    def test_simple_html(self):
        """Test converting simple HTML."""
        html = "<p>Hello <b>World</b></p>"
        
        text = html_to_text(html)
        
        assert "Hello" in text
        assert "World" in text
        assert "<p>" not in text
        assert "<b>" not in text
    
    def test_html_with_script(self):
        """Test that script tags are removed."""
        html = "<p>Text</p><script>alert('bad')</script>"
        
        text = html_to_text(html)
        
        assert "Text" in text
        assert "script" not in text.lower()
        assert "alert" not in text
    
    def test_empty_html(self):
        """Test empty HTML returns empty string."""
        assert html_to_text("") == ""
        assert html_to_text(None) == ""


class TestGetEmailBodyText:
    """Test email body text extraction."""
    
    def test_prefer_plain_text(self):
        """Test that plain text is preferred over HTML."""
        plain = "Plain text"
        html = "<p>HTML text</p>"
        
        result = get_email_body_text(plain, html)
        
        assert result == "Plain text"
    
    def test_fallback_to_html(self):
        """Test fallback to HTML when no plain text."""
        result = get_email_body_text("", "<p>HTML</p>")
        
        assert "HTML" in result
        assert "<p>" not in result
    
    def test_both_empty(self):
        """Test both plain and HTML empty."""
        assert get_email_body_text("", "") == ""


class TestParseEmailDate:
    """Test email date parsing."""
    
    def test_parse_valid_date(self):
        """Test parsing valid RFC 2822 date."""
        date_str = "Mon, 26 Oct 2026 10:30:00 +0000"
        
        dt = parse_email_date(date_str)
        
        assert isinstance(dt, datetime)
        assert dt.year == 2026
        assert dt.month == 10
        assert dt.day == 26
    
    def test_parse_invalid_date(self):
        """Test parsing invalid date returns current time."""
        dt = parse_email_date("invalid date")
        
        assert isinstance(dt, datetime)


class TestExtractEmailAddress:
    """Test email address extraction."""
    
    def test_extract_from_angle_brackets(self):
        """Test extracting from 'Name <email>' format."""
        assert extract_email_address("John Doe <john@example.com>") == "john@example.com"
    
    def test_extract_from_parentheses(self):
        """Test extracting from 'Name (email)' format."""
        assert extract_email_address("John Doe (john@example.com)") == "john@example.com"
    
    def test_extract_plain_email(self):
        """Test extracting plain email address."""
        assert extract_email_address("john@example.com") == "john@example.com"
    
    def test_extract_with_quotes(self):
        """Test extracting email with quotes."""
        assert extract_email_address('"john@example.com"') == "john@example.com"
    
    def test_extract_empty(self):
        """Test extracting from empty string."""
        assert extract_email_address("") == ""
    
    def test_extract_no_at_sign(self):
        """Test extracting from string without @ returns original."""
        assert extract_email_address("John Doe") == "John Doe"


class TestIsEmailFromSender:
    """Test sender verification."""
    
    def test_match_plain_email(self):
        """Test matching plain email addresses."""
        assert is_email_from_sender(
            "test@example.com",
            "test@example.com",
        ) is True
    
    def test_match_with_name(self):
        """Test matching email with name."""
        assert is_email_from_sender(
            "Test User <test@example.com>",
            "test@example.com",
        ) is True
    
    def test_case_insensitive(self):
        """Test matching is case insensitive."""
        assert is_email_from_sender(
            "TEST@EXAMPLE.COM",
            "test@example.com",
        ) is True
    
    def test_no_match(self):
        """Test non-matching emails."""
        assert is_email_from_sender(
            "other@example.com",
            "test@example.com",
        ) is False


class TestBuildGmailQuery:
    """Test Gmail query string building."""
    
    def test_build_with_sender(self):
        """Test query with sender filter."""
        query = build_gmail_query(sender_email="test@example.com")
        
        assert "from:test@example.com" in query
    
    def test_build_with_unread(self):
        """Test query with unread filter."""
        query = build_gmail_query(is_unread=True)
        
        assert "is:unread" in query
    
    def test_build_with_after_date(self):
        """Test query with date filter."""
        query = build_gmail_query(after_date="2026/10/26")
        
        assert "after:2026/10/26" in query
    
    def test_build_with_label(self):
        """Test query with label filter."""
        query = build_gmail_query(has_label="Important")
        
        assert "label:Important" in query
    
    def test_build_without_label(self):
        """Test query excluding label."""
        query = build_gmail_query(not_has_label="Processed")
        
        assert "-label:Processed" in query
    
    def test_build_complex_query(self):
        """Test building complex query."""
        query = build_gmail_query(
            sender_email="test@example.com",
            after_date="2026/10/26",
            is_unread=True,
        )
        
        assert "from:test@example.com" in query
        assert "after:2026/10/26" in query
        assert "is:unread" in query


class TestGetOrCreateLabel:
    """Test Gmail label operations."""
    
    def test_get_existing_label(self):
        """Test getting existing label."""
        mock_service = Mock()
        mock_service.users().labels().list().execute.return_value = {
            "labels": [
                {"id": "label_123", "name": "PlaceGuard/Processed"},
                {"id": "label_456", "name": "Other"},
            ]
        }
        
        label_id = get_or_create_label(mock_service, "PlaceGuard/Processed")
        
        assert label_id == "label_123"
        mock_service.users().labels().create.assert_not_called()
    
    def test_create_new_label(self):
        """Test creating new label."""
        mock_service = Mock()
        mock_service.users().labels().list().execute.return_value = {"labels": []}
        mock_service.users().labels().create().execute.return_value = {
            "id": "label_new",
            "name": "PlaceGuard/Processed",
        }
        
        label_id = get_or_create_label(mock_service, "PlaceGuard/Processed")
        
        assert label_id == "label_new"
        # Check that create was called with correct parameters
        mock_service.users().labels().create.assert_called_with(
            userId="me",
            body={
                "name": "PlaceGuard/Processed",
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
    
    def test_create_label_failure(self):
        """Test label creation failure returns None."""
        mock_service = Mock()
        mock_service.users().labels().list.side_effect = Exception("API error")
        
        label_id = get_or_create_label(mock_service, "Test")
        
        assert label_id is None


class TestAddLabelToMessage:
    """Test adding label to message."""
    
    def test_add_label_success(self):
        """Test successful label addition."""
        mock_service = Mock()
        mock_service.users().messages().modify().execute.return_value = {}
        
        result = add_label_to_message(mock_service, "msg_123", "label_456")
        
        assert result is True
        # Check that modify was called with correct parameters
        mock_service.users().messages().modify.assert_called_with(
            userId="me",
            id="msg_123",
            body={"addLabelIds": ["label_456"]},
        )
    
    def test_add_label_failure(self):
        """Test label addition failure."""
        mock_service = Mock()
        mock_service.users().messages().modify.side_effect = Exception("API error")
        
        result = add_label_to_message(mock_service, "msg_123", "label_456")
        
        assert result is False


class TestParseGmailMessage:
    """Test Gmail message parsing."""
    
    def test_parse_simple_message(self):
        """Test parsing simple Gmail message."""
        plain_encoded = base64.urlsafe_b64encode(b"Test body").decode()
        
        message = {
            "id": "msg_123",
            "threadId": "thread_456",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "test@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Mon, 26 Oct 2026 10:00:00 +0000"},
                ],
                "mimeType": "text/plain",
                "body": {"data": plain_encoded},
            },
        }
        
        parsed = parse_gmail_message(message)
        
        assert parsed["message_id"] == "msg_123"
        assert parsed["subject"] == "Test Subject"
        assert parsed["from"] == "test@example.com"
        assert parsed["to"] == "recipient@example.com"
        assert parsed["body_plain"] == "Test body"
        assert "INBOX" in parsed["labels"]
