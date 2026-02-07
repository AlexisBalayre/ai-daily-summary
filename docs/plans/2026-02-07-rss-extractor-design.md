# RSS Extractor Design

**Date:** 2026-02-07
**Status:** Approved

## Problem

Adding RSS feeds currently requires the generic `CrawlerExtractor` with manual selector configuration for each feed. This is unnecessary friction since RSS and Atom are standardized formats.

**Goal:** A dedicated RSS ETL that works for any feed with just a URL.

## Design

### New Source Type: `rss`

Minimal configuration - just the feed URL:

```python
Source(
    type="rss",
    name="Wired AI",
    config={"url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    enabled=True
)
```

### File Structure

```
ai_daily/etl/extractors/
├── base.py           # existing
├── gmail.py          # existing
├── github.py         # existing
├── crawler.py        # existing (keep for HTML scraping)
└── rss.py            # NEW - dedicated RSS extractor
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `feedparser` | Parse RSS 2.0 and Atom feeds automatically |
| `trafilatura` | Extract full article content from any page |

### RSSExtractor Implementation

```python
class RSSExtractor(BaseExtractor):
    FETCH_DELAY = 0.5          # Seconds between article fetches
    MAX_ARTICLES_PER_FEED = 25  # Cap per feed per run
    FETCH_TIMEOUT = 15          # Article fetch timeout

    @property
    def supported_types(self) -> List[str]:
        return ["rss"]

    async def extract(self, source: Source) -> List[RawContent]:
        url = source.config.get("url")

        # 1. Parse the feed (auto-detects RSS 2.0 vs Atom)
        feed = feedparser.parse(url)

        # 2. Process each entry
        results = []
        for entry in feed.entries[:self.MAX_ARTICLES_PER_FEED]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published_parsed")
            author = entry.get("author", "")

            # 3. Fetch full article content
            content = trafilatura.fetch_and_extract(link)

            # 4. Fallback to feed summary if extraction fails
            if not content:
                content = entry.get("summary", title)

            results.append(RawContent(
                external_id=md5(link),
                title=title,
                content=content,
                url=link,
                author=author,
                published_at=published,
                source_name=source.name,
            ))

            await asyncio.sleep(self.FETCH_DELAY)

        return results
```

### Rate Limiting & Error Handling

- **0.5s delay** between article fetches to avoid overwhelming target sites
- **25 article cap** per feed per run
- **15s timeout** for individual article fetches
- Individual failures don't stop feed processing (log warning, continue)
- Trafilatura failures fall back to feed summary
- Feed parse failures log error and return empty list

### Pipeline Integration

Update `ETLPipeline` extractor mapping:

```python
EXTRACTORS = {
    "newsletter": GmailExtractor,
    "github": GitHubExtractor,
    "crawler": CrawlerExtractor,
    "rss": RSSExtractor,
}
```

### CLI Integration

New streamlined command:

```bash
ai-daily source add-rss "Wired AI" "https://www.wired.com/feed/tag/ai/latest/rss"
```

New run target:

```bash
ai-daily run rss      # Run only RSS sources
ai-daily run all      # Includes RSS alongside other sources
```

## Initial Feeds

```bash
ai-daily source add-rss "Computerworld" "https://www.computerworld.com/feed/"
ai-daily source add-rss "MIT Technology Review" "https://www.technologyreview.com/feed/"
ai-daily source add-rss "Wired AI" "https://www.wired.com/feed/tag/ai/latest/rss"
ai-daily source add-rss "Ars Technica Tech Lab" "https://feeds.arstechnica.com/arstechnica/technology-lab"
ai-daily source add-rss "TechRadar" "https://www.techradar.com/feeds.xml"
ai-daily source add-rss "TechRadar News" "https://www.techradar.com/feeds/articletype/news"
ai-daily source add-rss "The Verge" "https://www.theverge.com/rss/index.xml"
```

Note: TechRadar has two feeds that may overlap. Existing deduplication should handle this.

## Implementation Tasks

1. Add `feedparser` and `trafilatura` to dependencies
2. Create `ai_daily/etl/extractors/rss.py` with `RSSExtractor`
3. Register `rss` type in `ETLPipeline.EXTRACTORS`
4. Add `source add-rss` CLI command
5. Add `run rss` CLI target
6. Add initial feeds
7. Test with one feed, then all seven
