"""Helpers for building email HTML from untrusted article data."""

from html import escape
from urllib.parse import urlparse


def safe_href(url: str | None) -> str:
    """Escaped URL for an href, or "#" unless it is an http(s) link.

    Article URLs come from crawled pages and feeds; `javascript:` or `data:`
    schemes must never reach a mail client.
    """
    if not url:
        return "#"
    if urlparse(url).scheme not in {"http", "https"}:
        return "#"
    return escape(url)
