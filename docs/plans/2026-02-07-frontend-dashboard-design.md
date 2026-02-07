# Frontend Dashboard Design

**Date:** 2026-02-07
**Status:** Approved

## Problem

No way to browse articles, view summaries, or manage sources without using CLI commands or direct database access.

**Goal:** A React dashboard bundled with FastAPI for browsing data and managing sources.

## Design

### Technology Stack

- **React** with TypeScript
- **Tailwind CSS** + Headless UI for styling
- **Vite** for build tooling
- **Bundled with FastAPI** - single deployment

### Architecture

```
ai_daily/
├── api/
│   ├── server.py          # FastAPI app + static file serving
│   └── routes/
│       ├── articles.py     # existing
│       ├── sources.py      # NEW - CRUD for sources
│       └── jobs.py         # NEW - job history
├── static/                  # Built React assets
│   ├── index.html
│   └── assets/
└── ...

frontend/                    # React source
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Articles.tsx
│   │   ├── Sources.tsx
│   │   └── Jobs.tsx
│   ├── components/
│   └── App.tsx
├── package.json
└── vite.config.ts
```

### Pages

**Dashboard (Home)**
- System status: database connection, last ETL run, next scheduled runs
- Quick stats: total articles, articles today, active sources count
- Recent activity: last 5 job runs with status indicators

**Articles**
- Paginated table: title, source, topic, date, link
- Filters: date range, source, topic
- Search: full-text search on title/content
- Click row to expand and see full content

**Summaries**
- List of daily summaries with date and article count
- Click to view full newsletter HTML preview
- Status: sent/pending

**Sources**
- Table: name, type (rss/newsletter/github/crawler), enabled toggle, last run, article count
- Actions: edit, delete, test
- Add new source modal with type-specific form fields
- Test button: validates URL, shows preview of extracted content

**Jobs**
- Job run history table: job name, status, started, duration, metrics
- Filter by status (success/failed/running)
- Click to see error details for failed jobs

### API Endpoints

**Existing (keep as-is):**
- `GET /articles`, `GET /articles/{id}`, `GET /articles/search`
- `GET /summaries`, `GET /summaries/{id}`, `GET /summaries/latest`

**New endpoints:**

```
Sources:
  GET    /api/sources              - list all sources
  POST   /api/sources              - create source
  GET    /api/sources/{id}         - get single source
  PUT    /api/sources/{id}         - update source
  DELETE /api/sources/{id}         - delete source
  PATCH  /api/sources/{id}/toggle  - enable/disable
  POST   /api/sources/{id}/test    - test source, return preview

Jobs:
  GET    /api/jobs                 - list job runs (paginated, filterable)
  GET    /api/jobs/{id}            - job details with error message

Dashboard:
  GET    /api/status               - system health, stats, next scheduled runs
```

### Source Testing

**Test endpoint (`POST /api/sources/{id}/test`):**

| Source Type | Test Behavior |
|-------------|---------------|
| RSS | Fetch/parse feed, return entry count + 3 sample titles |
| Newsletter | Validate email format |
| Crawler | Fetch URL, apply selectors, return match count + samples |

**Response format:**
```json
{
  "success": true,
  "preview": {
    "feed_title": "Wired AI",
    "entry_count": 20,
    "sample_titles": ["Article 1", "Article 2", "Article 3"]
  }
}
```

Test button available in add/edit modal. User can save even if test fails.

### Build & Development

**Development:**
```bash
# Terminal 1: FastAPI backend
uv run ai-daily serve

# Terminal 2: React dev server
cd frontend && npm run dev
```

Vite proxies `/api/*` to FastAPI during development.

**Production build:**
```bash
cd frontend && npm run build  # Outputs to ai_daily/static/
```

**FastAPI static serving:**
```python
from fastapi.staticfiles import StaticFiles

# API routes first
app.include_router(sources_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")

# Static files last (SPA catch-all)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

**Docker:** Add `npm run build` to Dockerfile, copy static files.

### Authentication

None. Local/trusted network only.

## Implementation Tasks

1. Add new API routes (sources CRUD, jobs, status)
2. Set up React project with Vite + Tailwind
3. Implement Dashboard page
4. Implement Articles page
5. Implement Sources page with test functionality
6. Implement Summaries page
7. Implement Jobs page
8. Configure static file serving in FastAPI
9. Update Dockerfile for frontend build
