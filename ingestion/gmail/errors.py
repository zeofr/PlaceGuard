"""Custom exception classes for Gmail integration.

Provides specific error types for different failure scenarios
to enable better error handling and user messaging.
"""

from __future__ import annotations


class GmailIntegrationError(Exception):
    """Base exception for all Gmail integration errors."""
    
    def __init__(self, message: str, details: dict | None = None):
        """Initialize error with message and optional details.
        
        Args:
            message: Human-readable error message
            details: Optional dict with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """String representation of error."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class GmailAuthenticationError(GmailIntegrationError):
    """Raised when Gmail OAuth authentication fails.
    
    Common causes:
    - Missing or invalid credentials.json
    - Expired or revoked access token
    - OAuth consent not completed
    - Gmail API not enabled
    """
    pass


class GmailAPIError(GmailIntegrationError):
    """Raised when Gmail API requests fail.
    
    Common causes:
    - Network connectivity issues
    - API quota exceeded
    - Invalid API request parameters
    - Gmail service temporarily unavailable
    """
    pass


class GmailQuotaExceededError(GmailAPIError):
    """Raised when Gmail API quota is exceeded.
    
    Free tier: 1 billion quota units/day
    Reading emails = 5 units each
    """
    
    def __init__(self, message: str = "Gmail API quota exceeded", **kwargs):
        """Initialize quota exceeded error."""
        super().__init__(message, **kwargs)


class EmailParsingError(GmailIntegrationError):
    """Raised when email content cannot be parsed.
    
    Common causes:
    - Malformed email structure
    - Unsupported encoding
    - Missing required headers
    """
    pass


class EmailClassificationError(GmailIntegrationError):
    """Raised when LLM email classification fails.
    
    Common causes:
    - LLM service unavailable
    - Invalid response format from LLM
    - Timeout during classification
    """
    pass


class DriveExtractionError(GmailIntegrationError):
    """Raised when company/drive information cannot be extracted.
    
    Common causes:
    - Email doesn't mention a company name
    - Ambiguous company references
    - LLM extraction failure
    """
    pass


class LabelOperationError(GmailIntegrationError):
    """Raised when Gmail label operations fail.
    
    Common causes:
    - Insufficient permissions
    - Label name conflicts
    - Network errors
    """
    pass


def handle_gmail_api_error(error: Exception) -> GmailIntegrationError:
    """Convert various Gmail API errors to our custom exceptions.
    
    Args:
        error: Original exception from Gmail API
        
    Returns:
        GmailIntegrationError with appropriate type and message
    """
    error_str = str(error).lower()
    
    # Check for quota errors
    if "quota" in error_str or "rate" in error_str:
        return GmailQuotaExceededError(
            "Gmail API quota exceeded. Try again later or increase quota.",
            details={"original_error": str(error)}
        )
    
    # Check for authentication errors
    if any(keyword in error_str for keyword in ["invalid_grant", "unauthorized", "credentials", "token"]):
        return GmailAuthenticationError(
            "Gmail authentication failed. Delete token.json and re-authenticate.",
            details={"original_error": str(error)}
        )
    
    # Check for network errors
    if any(keyword in error_str for keyword in ["connection", "timeout", "network"]):
        return GmailAPIError(
            "Network error accessing Gmail API. Check internet connection.",
            details={"original_error": str(error)}
        )
    
    # Generic API error
    return GmailAPIError(
        f"Gmail API error: {str(error)}",
        details={"original_error": str(error)}
    )


def get_user_friendly_message(error: Exception) -> str:
    """Get a user-friendly error message for display.
    
    Args:
        error: Exception to convert
        
    Returns:
        User-friendly error message
    """
    if isinstance(error, GmailAuthenticationError):
        return (
            "Gmail authentication failed. Please check:\n"
            "1. credentials.json file exists in project root\n"
            "2. Gmail API is enabled in Google Cloud Console\n"
            "3. OAuth consent screen is configured\n"
            "Try deleting token.json and re-authenticating."
        )
    
    elif isinstance(error, GmailQuotaExceededError):
        return (
            "Gmail API quota exceeded. Free tier allows 1 billion units/day.\n"
            "Consider:\n"
            "1. Reducing polling frequency\n"
            "2. Processing fewer emails per sync\n"
            "3. Upgrading to paid tier"
        )
    
    elif isinstance(error, EmailClassificationError):
        return (
            "Email classification failed. Check:\n"
            "1. LLM service is running and accessible\n"
            "2. API key is valid (for Gemini/OpenAI/Claude)\n"
            "3. Ollama is running (for local LLM)"
        )
    
    elif isinstance(error, GmailAPIError):
        return (
            "Gmail API error. Check:\n"
            "1. Internet connection is stable\n"
            "2. Gmail service is not down\n"
            "3. API request parameters are valid"
        )
    
    else:
        return f"Unexpected error: {str(error)}"
