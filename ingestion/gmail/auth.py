"""Gmail OAuth 2.0 authentication for PlaceGuard.

Handles the OAuth flow for Gmail API access:
- Initial browser-based authentication
- Token storage and automatic refresh
- Credential validation
"""

from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import settings


# Gmail API scopes required for PlaceGuard
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",  # Read email messages
    "https://www.googleapis.com/auth/gmail.modify",     # Add/remove labels
]


class GmailAuthenticationError(Exception):
    """Raised when Gmail authentication fails."""
    pass


class GmailAuthenticator:
    """Handles Gmail OAuth 2.0 authentication and token management."""
    
    def __init__(
        self,
        credentials_path: str | None = None,
        token_path: str | None = None,
    ):
        """Initialize Gmail authenticator.
        
        Args:
            credentials_path: Path to OAuth credentials JSON file (from Google Cloud Console)
            token_path: Path to store/load OAuth tokens
        """
        self.credentials_path = credentials_path or settings.gmail_credentials_path
        self.token_path = token_path or settings.gmail_token_path
        self._credentials: Credentials | None = None
    
    def authenticate(self) -> Credentials:
        """Authenticate with Gmail API using OAuth 2.0.
        
        If valid tokens exist, they are loaded. Otherwise, initiates the OAuth flow
        which opens a browser for user consent. Tokens are automatically refreshed
        when expired.
        
        Returns:
            Valid Gmail API credentials
            
        Raises:
            GmailAuthenticationError: If authentication fails
        """
        if self._credentials and self._credentials.valid:
            return self._credentials
        
        creds = None
        
        # Load existing tokens if available
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                # Token file corrupted or invalid - will re-authenticate
                print(f"Warning: Could not load token file: {e}")
                creds = None
        
        # Refresh expired tokens or initiate new OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Token expired but can be refreshed
                try:
                    creds.refresh(Request())
                except Exception as e:
                    raise GmailAuthenticationError(
                        f"Failed to refresh Gmail token. Delete {self.token_path} "
                        f"and re-authenticate. Error: {e}"
                    ) from e
            else:
                # No valid credentials - initiate OAuth flow
                creds = self._run_oauth_flow()
            
            # Save tokens for future use
            self._save_credentials(creds)
        
        self._credentials = creds
        return creds
    
    def _run_oauth_flow(self) -> Credentials:
        """Run the OAuth 2.0 authorization flow.
        
        Opens a browser window for user consent.
        
        Returns:
            Valid credentials after user authorization
            
        Raises:
            GmailAuthenticationError: If credentials file is missing or OAuth flow fails
        """
        if not os.path.exists(self.credentials_path):
            raise GmailAuthenticationError(
                f"Gmail credentials file not found: {self.credentials_path}\n"
                f"Please download OAuth credentials from Google Cloud Console.\n"
                f"See docs/GMAIL_SETUP.md for instructions."
            )
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path,
                SCOPES,
            )
            # Run local server to receive OAuth callback
            # This will open a browser window for user to authorize
            creds = flow.run_local_server(port=0)
            return creds
        
        except Exception as e:
            raise GmailAuthenticationError(
                f"OAuth flow failed: {e}\n"
                f"Ensure:\n"
                f"1. Gmail API is enabled in Google Cloud Console\n"
                f"2. OAuth consent screen is configured\n"
                f"3. You have internet connection\n"
                f"See docs/GMAIL_SETUP.md for setup instructions."
            ) from e
    
    def _save_credentials(self, creds: Credentials) -> None:
        """Save credentials to token file for future use.
        
        Args:
            creds: Credentials to save
        """
        try:
            # Ensure directory exists
            token_dir = Path(self.token_path).parent
            token_dir.mkdir(parents=True, exist_ok=True)
            
            # Save credentials
            with open(self.token_path, "w") as token_file:
                token_file.write(creds.to_json())
            
            print(f"Gmail credentials saved to {self.token_path}")
        
        except Exception as e:
            print(f"Warning: Could not save credentials to {self.token_path}: {e}")
            # Non-fatal - authentication still works, just won't persist
    
    def get_gmail_service(self):
        """Get authenticated Gmail API service.
        
        Returns:
            Gmail API service object (googleapiclient.discovery.Resource)
            
        Raises:
            GmailAuthenticationError: If authentication fails
        """
        creds = self.authenticate()
        
        try:
            service = build("gmail", "v1", credentials=creds)
            return service
        
        except Exception as e:
            raise GmailAuthenticationError(
                f"Failed to build Gmail API service: {e}"
            ) from e
    
    def revoke_credentials(self) -> None:
        """Revoke current credentials and delete token file.
        
        Useful for testing or if credentials are compromised.
        """
        if os.path.exists(self.token_path):
            try:
                os.remove(self.token_path)
                print(f"Removed token file: {self.token_path}")
            except Exception as e:
                print(f"Warning: Could not remove token file: {e}")
        
        self._credentials = None
    
    def is_authenticated(self) -> bool:
        """Check if valid credentials are available.
        
        Returns:
            True if authenticated with valid credentials, False otherwise
        """
        try:
            creds = self.authenticate()
            return creds is not None and creds.valid
        except GmailAuthenticationError:
            return False


def get_gmail_service():
    """Convenience function to get authenticated Gmail API service.
    
    Returns:
        Gmail API service object
        
    Raises:
        GmailAuthenticationError: If authentication fails
    """
    authenticator = GmailAuthenticator()
    return authenticator.get_gmail_service()
