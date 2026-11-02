"""Centralized configuration management using Pydantic Settings.

All configuration comes from environment variables with validation.
Create a .env file in the project root with required settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "sqlite:///./placeguard_dev.db"  # dev default; set postgresql:// in prod
    database_echo: bool = False  # Set to True for SQL query logging
    
    # LLM Configuration
    llm_provider: str = "ollama"  # ollama | gemini | openai | claude
    
    # Ollama settings (local, free, no rate limits!)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_temperature: float = 0.1
    
    # Gemini settings
    gemini_api_key: str | None = None
    gemini_model: str = "models/gemini-1.5-flash"  # Full model path for LangChain
    gemini_temperature: float = 0.1  # Low temperature for deterministic extraction
    gemini_max_retries: int = 3
    gemini_timeout: int = 30  # seconds
    
    # OpenAI settings (for future use)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    
    # Claude settings (for future use)
    claude_api_key: str | None = None
    claude_model: str = "claude-3-haiku-20240307"
    
    # API Configuration
    jwt_secret: str = "CHANGE_THIS_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 1  # 1-hour session matching student portal convention
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    
    # Application
    debug: bool = False
    log_level: str = "INFO"
    
    # Gmail API Integration
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"
    placement_officer_email: str | None = None  # Email address of placement officer
    gmail_polling_enabled: bool = True  # Enable automatic email polling
    gmail_polling_interval_minutes: int = 60  # Polling interval in minutes (default: 1 hour)
    gmail_processed_label: str = "PlaceGuard/Processed"  # Gmail label for processed emails
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()


def validate_settings() -> None:
    """Validate critical settings are properly configured.
    
    Raises:
        ValueError: If required settings are missing or invalid
    """
    if settings.llm_provider == "ollama":
        # Ollama doesn't require API keys
        pass
    elif settings.llm_provider == "gemini" and not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY must be set when using Gemini provider. "
            "Get your key from https://makersuite.google.com/app/apikey"
        )
    elif settings.llm_provider == "openai" and not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY must be set when using OpenAI provider")
    elif settings.llm_provider == "claude" and not settings.claude_api_key:
        raise ValueError("CLAUDE_API_KEY must be set when using Claude provider")
    
    if not settings.database_url:
        raise ValueError("DATABASE_URL must be set")
