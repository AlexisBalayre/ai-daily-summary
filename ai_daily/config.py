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
    """LLM provider configuration (Google AI Studio)."""

    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "google"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-2.0-flash-lite"))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
    )
    google_api_key: str = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY", "")
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
class TTSConfig:
    """Pocket TTS voice + decoding configuration.

    The decoding knobs curb the model's tendency to hallucinate non-speech
    ("jingles") around the end of an utterance: a higher (less negative)
    eos_threshold stops sooner, frames_after_eos=0 suppresses trailing padding
    the model would otherwise fill with noise, and a lower temp reduces drift.
    """

    voice: str = field(default_factory=lambda: os.getenv("TTS_VOICE", "alba"))
    temp: float = field(default_factory=lambda: float(os.getenv("TTS_TEMP", "0.6")))
    eos_threshold: float = field(
        default_factory=lambda: float(os.getenv("TTS_EOS_THRESHOLD", "-3.0"))
    )
    # Optional noise clamp; unset (None) leaves the model default.
    noise_clamp: Optional[float] = field(
        default_factory=lambda: (
            float(os.environ["TTS_NOISE_CLAMP"]) if os.getenv("TTS_NOISE_CLAMP") else None
        )
    )
    frames_after_eos: int = field(
        default_factory=lambda: int(os.getenv("TTS_FRAMES_AFTER_EOS", "0"))
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
    github_schedule: str = field(
        default_factory=lambda: os.getenv("GITHUB_SCHEDULE", "0 10 * * *")
    )
    leaderboard_schedule: str = field(
        default_factory=lambda: os.getenv("LEADERBOARD_SCHEDULE", "0 7 * * *")
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
    tts: TTSConfig = field(default_factory=TTSConfig)
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

    # Recipients for newsletters (fallback for all)
    recipients: List[str] = field(
        default_factory=lambda: [
            r.strip()
            for r in os.getenv("RECIPIENTS", "").split(",")
            if r.strip()
        ]
    )

    # Per-newsletter recipient lists (fall back to recipients if not set)
    newsletter_recipients: List[str] = field(
        default_factory=lambda: [
            r.strip()
            for r in os.getenv("NEWSLETTER_RECIPIENTS", "").split(",")
            if r.strip()
        ]
    )
    github_recipients: List[str] = field(
        default_factory=lambda: [
            r.strip()
            for r in os.getenv("GITHUB_RECIPIENTS", "").split(",")
            if r.strip()
        ]
    )
    tts_recipients: List[str] = field(
        default_factory=lambda: [
            r.strip()
            for r in os.getenv("TTS_RECIPIENTS", "").split(",")
            if r.strip()
        ]
    )

    def get_newsletter_recipients(self) -> List[str]:
        """Get recipients for AI Daily newsletter (falls back to general recipients)."""
        return self.newsletter_recipients if self.newsletter_recipients else self.recipients

    def get_github_recipients(self) -> List[str]:
        """Get recipients for GitHub newsletter (falls back to general recipients)."""
        return self.github_recipients if self.github_recipients else self.recipients

    def get_tts_recipients(self) -> List[str]:
        """Get recipients for TTS audio briefing (falls back to general recipients)."""
        return self.tts_recipients if self.tts_recipients else self.recipients

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
