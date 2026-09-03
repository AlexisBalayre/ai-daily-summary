"""Tests for newsletter/GitHub HTML rendering and the daily summary generator."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_daily.config import config
from ai_daily.outputs import summary_generator as summary_module
from ai_daily.outputs.github_newsletter import GitHubNewsletterOutput
from ai_daily.outputs.newsletter import NewsletterOutput
from ai_daily.outputs.summary_generator import SummaryGenerator
from tests.conftest import SqliteArticle, SqliteDailySummary

FIXED_NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW.astimezone(tz) if tz else FIXED_NOW.replace(tzinfo=None)


def article(title="Title", topic="", summary="A summary.", url="https://example.com/a", **kw):
    return SimpleNamespace(
        title=title,
        topic=topic,
        summary=summary,
        content=kw.pop("content", ""),
        url=url,
        source=SimpleNamespace(name=kw.pop("source_name", "Src")),
        **kw,
    )


@pytest.fixture
def gemini(monkeypatch):
    """No real Gemini client: SummaryGenerator() must be constructible offline."""
    fake_client = MagicMock()
    fake_client.aio.models.generate_content = AsyncMock()
    monkeypatch.setattr(summary_module.genai, "Client", MagicMock(return_value=fake_client))
    return fake_client


@pytest.fixture
def newsletter(gemini):
    with patch("ai_daily.outputs.newsletter.datetime", FixedDatetime):
        yield NewsletterOutput(gmail_service=MagicMock())


def test_generate_html_escapes_and_fills_placeholders(newsletter, monkeypatch):
    monkeypatch.setattr(config, "brand", "Brand & Co")
    summary = SimpleNamespace(key_facts=["Fact <one>", "Fact two"])
    articles = [article(title="<script>x</script>", summary="Long & short", topic="research")]

    html = newsletter.generate_html(summary, articles)

    assert "{{" not in html
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "Long &amp; short" in html
    assert "<li>Fact &lt;one&gt;</li>" in html
    assert "Brand &amp; Co" in html
    assert "September 03, 2026" in html
    assert "2026" in html


def test_generate_html_groups_by_topic_and_hides_empty_categories(newsletter):
    articles = [
        article(title="Paper", topic="Research breakthrough"),
        article(title="Lib", topic="new tool"),
        article(title="Deal", topic=None),
    ]
    html = newsletter.generate_html(SimpleNamespace(key_facts=None), articles)

    assert "AI Research and Advances</h3>" in html
    assert "AI Products, Tools, and Repositories</h3>" in html
    assert "Industry News and Trends</h3>" in html
    assert "Data Science Techniques and Tips</h3>" not in html
    assert html.index("Paper") < html.index("Lib") < html.index("Deal")


def test_generate_html_truncates_long_excerpts(newsletter):
    html = newsletter.generate_html(SimpleNamespace(key_facts=[]), [article(summary="x" * 300)])
    assert "x" * 280 + "..." in html
    assert "x" * 281 not in html


def test_release_radar_empty_and_capped(newsletter):
    assert newsletter._render_release_radar([]) == ""

    releases = [article(title=f"Model {i} <v>") for i in range(newsletter.RADAR_MAX_ITEMS + 1)]
    html = newsletter.generate_html(SimpleNamespace(key_facts=[]), [], releases)

    assert "Released in the last 24h" in html
    assert "Model 0 &lt;v&gt;" in html
    assert f"Model {newsletter.RADAR_MAX_ITEMS}" not in html


def test_plaintext_lists_sections_titles_and_urls(newsletter):
    text = newsletter._build_plaintext(
        [article(title="Deal", url="https://example.com/deal")],
        [article(title="Rel", url="https://example.com/rel")],
    )
    assert "RELEASED IN THE LAST 24H\n- Rel\n  https://example.com/rel" in text
    assert "INDUSTRY NEWS AND TRENDS\n- Deal\n  https://example.com/deal" in text


def test_build_message_attaches_audio_only_when_present(newsletter, tmp_path):
    plain = newsletter._build_message("S", "to@example.com", "<p>h</p>", "t", None)
    assert plain.get_content_type() == "multipart/alternative"

    wav = tmp_path / "briefing.wav"
    wav.write_bytes(b"RIFF")
    mixed = newsletter._build_message("S", "to@example.com", "<p>h</p>", "t", wav)
    assert mixed.get_content_type() == "multipart/mixed"
    assert [p.get_content_type() for p in mixed.get_payload()] == [
        "multipart/alternative",
        "audio/wav",
    ]


async def test_select_top_articles_uses_llm_choice_and_falls_back(newsletter, gemini):
    articles = [article(title=f"A{i}") for i in range(12)]
    gemini.aio.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps({"selected": [11, 0, 99, "bad"]})
    )
    assert [a.title for a in await newsletter._select_top_articles(articles)] == ["A11", "A0"]

    gemini.aio.models.generate_content.side_effect = RuntimeError("boom")
    fallback = await newsletter._select_top_articles(articles)
    assert [a.title for a in fallback] == [f"A{i}" for i in range(10)]

    few = articles[:3]
    assert await newsletter._select_top_articles(few) is few


def test_send_release_alert_sends_once_per_recipient(newsletter):
    send = newsletter.gmail_service.users.return_value.messages.return_value.send
    assert newsletter.send_release_alert([]) is False

    ok = newsletter.send_release_alert([article(title="New <model>")], ["a@x.io", "b@x.io"])

    assert ok is True
    assert send.call_count == 2
    assert send.call_args.kwargs["userId"] == "me"


def test_github_repos_html_parses_metadata_and_escapes():
    output = GitHubNewsletterOutput()
    repo = article(
        title="org/<repo>",
        content="Does <things>\nLanguage: Python\nStars: 1,234\nForks: 56",
        url="https://github.com/org/repo",
    )

    html = output._generate_repos_html([repo])

    assert "org/&lt;repo&gt;" in html
    assert "Does &lt;things&gt;" in html
    assert "Python" in html and "1,234 stars" in html and "56 forks" in html
    assert "#01" in html


def test_github_html_handles_empty_list_and_caps_at_fifteen(monkeypatch):
    monkeypatch.setattr(config, "brand", "Brand & Co")
    output = GitHubNewsletterOutput()

    empty = output.generate_html([])
    assert "No trending repositories today." in empty
    assert "Brand &amp; Co" in empty
    assert "{{" not in empty

    many = output._generate_repos_html([article(title=f"r{i}", content="d") for i in range(20)])
    assert "#15" in many and "#16" not in many


@pytest.fixture
def generator(gemini):
    with (
        patch.object(summary_module, "DailySummary", SqliteDailySummary),
        patch.object(summary_module, "Article", SqliteArticle),
    ):
        yield SummaryGenerator()


def _add_article(session, minutes_ago=0, **kw):
    row = SqliteArticle(
        source_id=1,
        title=kw.pop("title", "T"),
        content="c",
        is_ai_related=True,
        is_duplicate=False,
        ingested_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        **kw,
    )
    session.add(row)
    session.commit()
    return row


def test_fallback_summary_records_error_and_article_ids(generator, session):
    a = _add_article(session)
    summary = generator._create_fallback_summary(session, FIXED_NOW.date(), [a], "LLM down.")

    assert summary.summary_text == "Summary generation failed: LLM down."
    assert summary.key_facts == []
    assert summary.article_ids == [a.id]
    assert session.get(SqliteDailySummary, summary.id) is not None


async def test_generate_reuses_cached_summary_without_new_articles(generator, gemini, session):
    today = datetime.now(UTC).date()
    _add_article(session, minutes_ago=30)
    cached = SqliteDailySummary(
        date=datetime.combine(today, datetime.min.time(), tzinfo=UTC),
        summary_text="cached",
        key_facts=["k"],
        article_ids=[],
    )
    session.add(cached)
    session.commit()

    result = await generator.generate(session, today)

    assert result.summary_text == "cached"
    gemini.aio.models.generate_content.assert_not_called()


async def test_generate_regenerates_when_newer_articles_exist(generator, gemini, session):
    today = datetime.now(UTC).date()
    stale = SqliteDailySummary(
        date=datetime.combine(today, datetime.min.time(), tzinfo=UTC),
        summary_text="stale",
        key_facts=[],
        article_ids=[],
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    session.add(stale)
    session.commit()
    _add_article(session, title="Fresh")
    gemini.aio.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps({"summary": "fresh text", "key_facts": ["f1"]})
    )

    result = await generator.generate(session, today)

    assert result.summary_text == "fresh text"
    assert result.key_facts == ["f1"]
    assert session.query(SqliteDailySummary).count() == 1


async def test_generate_records_no_articles_summary(generator, gemini, session):
    result = await generator.generate(session, datetime.now(UTC).date())
    assert result.summary_text == "No articles for today."
    gemini.aio.models.generate_content.assert_not_called()


@pytest.mark.parametrize(
    ("llm_text", "expected"),
    [("not json", "Failed to parse LLM response."), ("", "LLM returned empty response.")],
)
async def test_generate_falls_back_on_bad_llm_output(
    generator, gemini, session, llm_text, expected
):
    _add_article(session)
    gemini.aio.models.generate_content.return_value = SimpleNamespace(text=llm_text)

    result = await generator.generate(session, datetime.now(UTC).date())

    assert result.summary_text == f"Summary generation failed: {expected}"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/a?b=1&c=2", "https://example.com/a?b=1&amp;c=2"),
        ("http://example.com/", "http://example.com/"),
        ("javascript:alert(1)", "#"),
        ("data:text/html;base64,AAAA", "#"),
        ("", "#"),
        (None, "#"),
    ],
)
def test_safe_href_only_links_http(url, expected):
    from ai_daily.outputs.html_utils import safe_href

    assert safe_href(url) == expected
