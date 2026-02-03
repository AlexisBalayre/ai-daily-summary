"""Shared types for ETL pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawContent:
    """Raw content extracted from a source before transformation."""

    external_id: str
    title: str
    content: str
    url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    source_name: str = ""
    metadata: dict = field(default_factory=dict)
