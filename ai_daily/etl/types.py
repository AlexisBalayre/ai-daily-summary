"""Shared types for ETL pipeline."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawContent:
    """Raw content extracted from a source before transformation."""

    external_id: str
    title: str
    content: str
    url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    source_name: str = ""
    metadata: dict = field(default_factory=dict)
