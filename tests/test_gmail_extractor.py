"""Tests for the Gmail newsletter extractor (no OAuth, no network)."""

import base64
import json
from datetime import UTC, timedelta
from unittest.mock import MagicMock, patch

import pytest

from ai_daily.config import config
from ai_daily.db.models import Source
from ai_daily.etl.extractors.gmail import GmailExtractor


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


@pytest.fixture
def extractor():
    with patch.object(GmailExtractor, "_authenticate", return_value=MagicMock()):
        yield GmailExtractor()


@pytest.fixture
def source():
    src = MagicMock(spec=Source)
    src.id = 1
    src.name = "Newsletters"
    src.config = {"whitelist": ["news@example.com"], "days_back": 2}
    return src


@pytest.fixture
def no_config_file(monkeypatch, tmp_path):
    """Point both config file paths at non-existent locations."""
    monkeypatch.setattr(config, "config_file", tmp_path / "config.json")
    monkeypatch.setattr(config, "config_example_file", tmp_path / "config.example.json")
    return tmp_path


def test_parse_email_date_keeps_explicit_offset(extractor):
    parsed = extractor._parse_email_date("Mon, 02 Feb 2026 10:30:00 +0200")
    assert parsed.utcoffset() == timedelta(hours=2)
    assert parsed.astimezone(UTC).hour == 8


def test_parse_email_date_assumes_utc_without_offset(extractor):
    parsed = extractor._parse_email_date("Mon, 02 Feb 2026 10:30:00")
    assert parsed.tzinfo is UTC
    assert parsed.hour == 10


def test_parse_email_date_strips_utc_suffix(extractor):
    parsed = extractor._parse_email_date("Mon, 02 Feb 2026 10:30:00 +0000 (UTC)")
    assert parsed is not None
    assert parsed.utcoffset() == timedelta(0)


def test_parse_email_date_returns_none_for_garbage(extractor):
    assert extractor._parse_email_date("not a date") is None
    assert extractor._parse_email_date("") is None


@pytest.mark.parametrize(
    ("sender", "expected"),
    [
        ("Some Newsletter <news@example.com>", "news@example.com"),
        ("news@example.com", "news@example.com"),
        ("  bare@example.com  ", "bare@example.com"),
    ],
)
def test_extract_sender_email(extractor, sender, expected):
    assert extractor._extract_sender_email(sender) == expected


def test_extract_email_body_prefers_plain_text_part(extractor):
    payload = {
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<b>html</b>")}},
            {"mimeType": "text/plain", "body": {"data": _b64("plain text")}},
        ]
    }
    assert extractor._extract_email_body(payload) == "plain text"


def test_extract_email_body_falls_back_to_top_level_body(extractor):
    payload = {"body": {"data": _b64("top level body")}}
    assert extractor._extract_email_body(payload) == "top level body"


def test_extract_email_body_empty_when_no_data(extractor):
    assert extractor._extract_email_body({"parts": [{"mimeType": "text/html"}]}) == ""
    assert extractor._extract_email_body({"body": {}}) == ""


def test_whitelist_config_file_wins_over_source_config(extractor, source, no_config_file):
    (no_config_file / "config.json").write_text(json.dumps({"whitelist": ["file@example.com"]}))
    assert extractor._load_whitelist(source) == {"file@example.com"}


def test_whitelist_falls_back_to_source_when_file_lacks_key(extractor, source, no_config_file):
    (no_config_file / "config.json").write_text(json.dumps({"sources": []}))
    assert extractor._load_whitelist(source) == {"news@example.com"}


def test_whitelist_empty_when_nothing_configured(extractor, source, no_config_file):
    source.config = {}
    assert extractor._load_whitelist(source) == set()


def _message(msg_id: str, sender: str, body: str, subject: str = "Subject") -> dict:
    return {
        "id": msg_id,
        "snippet": body[:20],
        "payload": {
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 02 Feb 2026 10:30:00 +0000"},
            ],
            "parts": [{"mimeType": "text/plain", "body": {"data": _b64(body)}}],
        },
    }


def _wire_service(service: MagicMock, messages: dict[str, dict]) -> MagicMock:
    """Make service.users().messages().list/get return canned Gmail payloads."""
    messages_api = service.users.return_value.messages.return_value
    messages_api.list.return_value.execute.return_value = {
        "messages": [{"id": msg_id} for msg_id in messages]
    }
    messages_api.get.side_effect = lambda userId, id, format: MagicMock(
        execute=MagicMock(return_value=messages[id])
    )
    return messages_api


async def test_extract_yields_only_whitelisted_senders(extractor, source, no_config_file):
    _wire_service(
        extractor.service,
        {
            "m1": _message("m1", "Newsletter <news@example.com>", "Hello there", "Issue 1"),
            "m2": _message("m2", "Spam <spam@example.com>", "Buy now"),
        },
    )

    items = await extractor.extract(source)

    assert [i.external_id for i in items] == ["m1"]
    assert items[0].title == "Issue 1"
    assert items[0].content == "Hello there"
    assert items[0].source_name == "news@example.com"
    assert items[0].author == "Newsletter <news@example.com>"
    assert items[0].published_at.tzinfo is not None
    assert items[0].metadata["gmail_id"] == "m1"


async def test_extract_skips_messages_without_body(extractor, source, no_config_file):
    empty = _message("m1", "news@example.com", "")
    empty["payload"]["parts"][0]["body"] = {}
    _wire_service(extractor.service, {"m1": empty})

    assert await extractor.extract(source) == []


async def test_extract_returns_empty_when_no_messages(extractor, source, no_config_file):
    messages_api = extractor.service.users.return_value.messages.return_value
    messages_api.list.return_value.execute.return_value = {}

    assert await extractor.extract(source) == []
    messages_api.get.assert_not_called()


async def test_extract_does_not_refetch_processed_ids(extractor, source, no_config_file):
    messages_api = _wire_service(
        extractor.service, {"m1": _message("m1", "news@example.com", "Body")}
    )

    first = await extractor.extract(source)
    second = await extractor.extract(source)

    assert len(first) == 1
    assert second == []
    assert messages_api.get.call_count == 1


def test_get_external_id_uses_gmail_message_id(extractor):
    from ai_daily.etl.types import RawContent

    item = RawContent(external_id="abc", title="t", content="c")
    assert extractor.get_external_id(item) == "abc"
