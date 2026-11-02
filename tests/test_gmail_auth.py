"""Unit tests for Gmail API authentication.

Tests OAuth flow, token management, and credential validation.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import tempfile
import json

import pytest

from ingestion.gmail.auth import GmailAuthenticator, SCOPES


class TestGmailAuthenticator:
    """Test Gmail authentication functionality."""
    
    def test_init(self):
        """Test authenticator initialization."""
        auth = GmailAuthenticator(
            credentials_path="test_creds.json",
            token_path="test_token.json",
        )
        
        assert auth.credentials_path == Path("test_creds.json")
        assert auth.token_path == Path("test_token.json")
        assert auth._credentials is None
    
    def test_scopes_defined(self):
        """Test that required Gmail API scopes are defined."""
        assert "gmail.readonly" in SCOPES[0]
        assert "gmail.modify" in SCOPES[1]
        assert "gmail.labels" in SCOPES[2]
        assert len(SCOPES) == 3
    
    @patch("ingestion.gmail.auth.Credentials")
    def test_get_credentials_loads_existing_valid_token(self, mock_creds_class):
        """Test loading existing valid token from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            creds_path = Path(tmpdir) / "creds.json"
            
            # Create dummy token file
            token_path.write_text('{"token": "dummy"}')
            
            # Mock credentials as valid
            mock_creds = Mock()
            mock_creds.valid = True
            mock_creds.to_json.return_value = '{"token": "dummy"}'  # Add to_json mock
            mock_creds_class.from_authorized_user_file.return_value = mock_creds
            
            auth = GmailAuthenticator(
                credentials_path=creds_path,
                token_path=token_path,
            )
            
            creds = auth.get_credentials()
            
            assert creds == mock_creds
            assert creds.valid
            mock_creds_class.from_authorized_user_file.assert_called_once_with(
                str(token_path),
                SCOPES,
            )
    
    @patch("ingestion.gmail.auth.Request")
    @patch("ingestion.gmail.auth.Credentials")
    def test_get_credentials_refreshes_expired_token(
        self,
        mock_creds_class,
        mock_request,
    ):
        """Test automatic refresh of expired token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            creds_path = Path(tmpdir) / "creds.json"
            
            # Create dummy token file
            token_path.write_text('{"token": "dummy"}')
            
            # Mock credentials as expired but with refresh token
            mock_creds = Mock()
            mock_creds.valid = False
            mock_creds.expired = True
            mock_creds.refresh_token = "refresh_token_abc"
            mock_creds.to_json.return_value = '{"refreshed": "token"}'
            mock_creds_class.from_authorized_user_file.return_value = mock_creds
            
            # After refresh, make valid
            def refresh_side_effect(request):
                mock_creds.valid = True
                mock_creds.expired = False
            
            mock_creds.refresh.side_effect = refresh_side_effect
            
            auth = GmailAuthenticator(
                credentials_path=creds_path,
                token_path=token_path,
            )
            
            creds = auth.get_credentials()
            
            assert creds == mock_creds
            mock_creds.refresh.assert_called_once()
    
    @patch("ingestion.gmail.auth.InstalledAppFlow")
    def test_run_oauth_flow_missing_credentials(self, mock_flow):
        """Test OAuth flow fails when credentials.json missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            creds_path = Path(tmpdir) / "missing_creds.json"
            token_path = Path(tmpdir) / "token.json"
            
            auth = GmailAuthenticator(
                credentials_path=creds_path,
                token_path=token_path,
            )
            
            with pytest.raises(FileNotFoundError) as exc_info:
                auth._run_oauth_flow()
            
            assert "credentials file not found" in str(exc_info.value).lower()
            assert "GMAIL_SETUP.md" in str(exc_info.value)
    
    @patch("ingestion.gmail.auth.InstalledAppFlow")
    def test_run_oauth_flow_success(self, mock_flow_class):
        """Test successful OAuth flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            creds_path = Path(tmpdir) / "creds.json"
            token_path = Path(tmpdir) / "token.json"
            
            # Create dummy credentials file
            creds_data = {
                "installed": {
                    "client_id": "test_client_id",
                    "client_secret": "test_secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
            creds_path.write_text(json.dumps(creds_data))
            
            # Mock OAuth flow
            mock_flow = Mock()
            mock_creds = Mock()
            mock_creds.to_json.return_value = '{"access_token": "test_token"}'
            mock_flow.run_local_server.return_value = mock_creds
            mock_flow_class.from_client_secrets_file.return_value = mock_flow
            
            auth = GmailAuthenticator(
                credentials_path=creds_path,
                token_path=token_path,
            )
            
            creds = auth._run_oauth_flow()
            
            assert creds == mock_creds
            assert token_path.exists()
            mock_flow.run_local_server.assert_called_once()
    
    def test_is_authenticated_true_when_valid(self):
        """Test is_authenticated returns True for valid credentials."""
        auth = GmailAuthenticator()
        
        mock_creds = Mock()
        mock_creds.valid = True
        auth._credentials = mock_creds
        
        assert auth.is_authenticated() is True
    
    def test_is_authenticated_false_when_invalid(self):
        """Test is_authenticated returns False for invalid credentials."""
        with tempfile.TemporaryDirectory() as tmpdir:
            creds_path = Path(tmpdir) / "creds.json"
            token_path = Path(tmpdir) / "token.json"
            
            auth = GmailAuthenticator(
                credentials_path=creds_path,
                token_path=token_path,
            )
            
            # No token file exists
            assert auth.is_authenticated() is False
    
    def test_revoke_token_deletes_file(self):
        """Test token revocation deletes token file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_path.write_text('{"token": "test"}')
            
            auth = GmailAuthenticator(
                credentials_path=Path(tmpdir) / "creds.json",
                token_path=token_path,
            )
            auth._credentials = Mock()
            
            assert token_path.exists()
            
            auth.revoke_token()
            
            assert not token_path.exists()
            assert auth._credentials is None
    
    def test_validate_credentials_file_valid(self):
        """Test validation of valid credentials file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            creds_path = Path(tmpdir) / "creds.json"
            
            creds_data = {
                "installed": {
                    "client_id": "test_client_id.apps.googleusercontent.com",
                    "project_id": "test-project",
                    "client_secret": "test_secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
            creds_path.write_text(json.dumps(creds_data))
            
            result = GmailAuthenticator.validate_credentials_file(creds_path)
            
            assert result["valid"] is True
            assert result["client_id"] == "test_client_id.apps.googleusercontent.com"
            assert result["project_id"] == "test-project"
    
    def test_validate_credentials_file_missing(self):
        """Test validation fails for missing file."""
        with pytest.raises(FileNotFoundError):
            GmailAuthenticator.validate_credentials_file("nonexistent.json")
    
    def test_validate_credentials_file_invalid_json(self):
        """Test validation fails for invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            creds_path = Path(tmpdir) / "invalid.json"
            creds_path.write_text("{invalid json")
            
            with pytest.raises(ValueError) as exc_info:
                GmailAuthenticator.validate_credentials_file(creds_path)
            
            assert "invalid json" in str(exc_info.value).lower()
    
    def test_validate_credentials_file_missing_fields(self):
        """Test validation fails for missing required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            creds_path = Path(tmpdir) / "incomplete.json"
            
            # Missing client_secret
            creds_data = {
                "installed": {
                    "client_id": "test_id",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
            creds_path.write_text(json.dumps(creds_data))
            
            with pytest.raises(ValueError) as exc_info:
                GmailAuthenticator.validate_credentials_file(creds_path)
            
            assert "missing required fields" in str(exc_info.value).lower()
            assert "client_secret" in str(exc_info.value)
