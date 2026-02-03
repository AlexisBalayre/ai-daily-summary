"""Configuration management using dataclasses."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")) if os.getenv("DB_PORT", "5432").isdigit() else 5432)
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "ai_daily"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def url(self) -> str:
        """Return the synchronous database URL."""
        return f"postgresql://{self.user}:{quote_plus(self.password)}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """Return the asynchronous database URL."""
        return f"postgresql+asyncpg://{self.user}:{quote_plus(self.password)}@{self.host}:{self.port}/{self.name}"


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )


@dataclass
class GmailConfig:
    """Gmail API configuration."""

    client_id: str = field(default_factory=lambda: os.getenv("GMAIL_CLIENT_ID", ""))
    client_secret: str = field(
        default_factory=lambda: os.getenv("GMAIL_CLIENT_SECRET", "")
    )
    project_id: str = field(default_factory=lambda: os.getenv("GMAIL_PROJECT_ID", ""))
    scopes: List[str] = field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ]
    )


@dataclass
class OrchestratorConfig:
    """Orchestrator scheduling and retry configuration."""

    # Cron schedules
    etl_schedule: str = field(
        default_factory=lambda: os.getenv("ETL_SCHEDULE", "0 */4 * * *")
    )
    tts_schedule: str = field(
        default_factory=lambda: os.getenv("TTS_SCHEDULE", "0 9 * * *")
    )
    newsletter_schedule: str = field(
        default_factory=lambda: os.getenv("NEWSLETTER_SCHEDULE", "0 14 * * *")
    )

    # Retry configuration
    retry_max_attempts: int = field(
        default_factory=lambda: int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    )
    retry_base_delay: float = field(
        default_factory=lambda: float(os.getenv("RETRY_BASE_DELAY", "10.0"))
    )
    retry_multiplier: float = field(
        default_factory=lambda: float(os.getenv("RETRY_MULTIPLIER", "3.0"))
    )


@dataclass
class Config:
    """Main application configuration container."""

    # Sub-configurations
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    gmail: GmailConfig = field(default_factory=GmailConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)

    # Paths
    data_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("DATA_DIR", Path(__file__).parent.parent / "data")
        )
    )
    logs_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("LOGS_DIR", Path(__file__).parent.parent / "logs")
        )
    )
    templates_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("TEMPLATES_DIR", Path(__file__).parent.parent / "templates")
        )
    )
    config_file: Path = field(
        default_factory=lambda: Path(
            os.getenv("CONFIG_FILE", Path(__file__).parent.parent / "config.json")
        )
    )

    # Recipients for newsletter
    recipients: List[str] = field(
        default_factory=lambda: [
            r.strip()
            for r in os.getenv("RECIPIENTS", "").split(",")
            if r.strip()
        ]
    )

    def __post_init__(self) -> None:
        """Ensure paths are Path objects and directories exist."""
        self.data_dir = Path(self.data_dir)
        self.logs_dir = Path(self.logs_dir)
        self.templates_dir = Path(self.templates_dir)
        self.config_file = Path(self.config_file)

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


# Global configuration instance
config = Config()
