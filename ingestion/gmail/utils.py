"""Utility functions for Gmail email parsing and processing."""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

from bs4 import BeautifulSoup


def parse_email_body(payload: dict[str, Any]) -> str:
    """Extract plain text body from Gmail message payload.
    
    Gmail messages can have various structures:
    - Simple text/plain messages
    - Multipart messages with text/plain and text/html parts
    - Nested multipart structures
    
    This function extracts the plain text content, falling back to
    converting HTML to text if only HTML is available.
    
    Args:
        payload: Gmail message payload dict
        
    Returns:
        Extracted plain text body
    """
    body = ""
    
    # Check if message has parts (multipart)
    if "parts" in payload:
        body = _parse_multipart(payload["parts"])
    else:
        # Single part message
        body = _decode_body_data(payload.get("body", {}).get("data", ""))
    
    # Clean up the extracted text
    body = _clean_text(body)
    
    return body


def _parse_multipart(parts: list[dict[str, Any]]) -> str:
    """Recursively parse multipart email structure.
    
    Prefers text/plain over text/html. If only HTML is available,
    converts it to plain text.
    
    Args:
        parts: List of message parts
        
    Returns:
        Extracted text body
    """
    text_body = ""
    html_body = ""
    
    for part in parts:
        mime_type = part.get("mimeType", "")
        
        # Recursively handle nested multipart
        if "parts" in part:
            nested_body = _parse_multipart(part["parts"])
            if nested_body:
                text_body = nested_body
        
        elif mime_type == "text/plain":
            # Plain text - preferred format
            data = part.get("body", {}).get("data", "")
            text_body = _decode_body_data(data)
            if text_body:
                break  # Found plain text, use it
        
        elif mime_type == "text/html":
            # HTML - fallback if no plain text
            data = part.get("body", {}).get("data", "")
            html_body = _decode_body_data(data)
    
    # Prefer plain text, fallback to HTML converted to text
    if text_body:
        return text_body
    elif html_body:
        return _html_to_text(html_body)
    else:
        return ""


def _decode_body_data(data: str) -> str:
    """Decode base64url-encoded body data.
    
    Args:
        data: Base64url-encoded string
        
    Returns:
        Decoded UTF-8 string
    """
    if not data:
        return ""
    
    try:
        # Gmail uses base64url encoding (RFC 4648)
        # Python's base64.urlsafe_b64decode handles this
        decoded_bytes = base64.urlsafe_b64decode(data)
        return decoded_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _html_to_text(html: str) -> str:
    """Convert HTML email to plain text.
    
    Uses BeautifulSoup to parse HTML and extract text content,
    preserving some structure like line breaks.
    
    Args:
        html: HTML string
        
    Returns:
        Plain text representation
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean up whitespace
        text = soup.get_text(separator="\n")
        return text
    
    except Exception:
        # If parsing fails, return HTML as-is (better than nothing)
        return html


def _clean_text(text: str) -> str:
    """Clean up extracted text body.
    
    Removes excessive whitespace, normalizes line breaks, and
    removes common email artifacts.
    
    Args:
        text: Raw extracted text
        
    Returns:
        Cleaned text
    """
    # Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    
    # Remove leading/trailing whitespace from entire text
    text = text.strip()
    
    return text


def get_header_value(headers: list[dict[str, str]], name: str) -> str | None:
    """Extract a header value from Gmail message headers.
    
    Args:
        headers: List of header dicts with 'name' and 'value' keys
        name: Header name to find (case-insensitive)
        
    Returns:
        Header value if found, None otherwise
    """
    name_lower = name.lower()
    for header in headers:
        if header.get("name", "").lower() == name_lower:
            return header.get("value")
    return None


def parse_gmail_date(date_str: str) -> datetime:
    """Parse Gmail date string to datetime.
    
    Gmail provides dates in RFC 2822 format like:
    "Mon, 21 Nov 2024 14:30:45 +0530"
    
    Args:
        date_str: Date string from Gmail
        
    Returns:
        Parsed datetime (timezone-naive UTC)
    """
    from email.utils import parsedate_to_datetime
    
    try:
        # Parse RFC 2822 date (e.g. "+0530") and actually convert to UTC
        # before dropping tzinfo - stripping it directly would keep the
        # local wall-clock time, silently mislabeling it as UTC.
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            # No offset in the header (rare) - already effectively naive.
            return dt
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    except Exception:
        # Fallback to current time if parsing fails
        return datetime.utcnow()


def extract_email_address(from_header: str) -> str:
    """Extract email address from From header.
    
    From headers can be in various formats:
    - "John Doe <john@example.com>"
    - "john@example.com"
    - "<john@example.com>"
    
    Args:
        from_header: From header value
        
    Returns:
        Extracted email address (lowercase)
    """
    # Try to extract email from angle brackets
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    
    # No angle brackets - assume entire string is email
    return from_header.strip().lower()


def create_message_id_from_gmail_id(gmail_id: str, sender: str) -> str:
    """Create a unique message ID for tracking.
    
    Combines Gmail message ID with sender email to create a unique
    identifier for the facts table.
    
    Args:
        gmail_id: Gmail message ID
        sender: Sender email address
        
    Returns:
        Unique message ID
    """
    return f"gmail_{gmail_id}_{sender.replace('@', '_at_')}"


def matches_sender(email_address: str, target_email: str) -> bool:
    """Check if email address matches target (case-insensitive).
    
    Args:
        email_address: Email address to check
        target_email: Target email address
        
    Returns:
        True if emails match
    """
    return email_address.lower().strip() == target_email.lower().strip()
