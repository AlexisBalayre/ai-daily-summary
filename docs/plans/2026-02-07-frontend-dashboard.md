# Frontend Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a React dashboard bundled with FastAPI for browsing articles, summaries, job history, and managing sources with full CRUD + test functionality.

**Architecture:** React + Vite + Tailwind frontend in `frontend/` directory, builds to `ai_daily/static/`. New API endpoints for source CRUD, job details, and system status. FastAPI serves static files as SPA catch-all.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, Headless UI, FastAPI, Pydantic

---

## Phase 1: Backend API Extensions

### Task 1: Add Source CRUD Endpoints

**Files:**
- Modify: `ai_daily/api/routes.py`
- Create: `tests/test_api_sources.py`

**Step 1: Add Pydantic models for source create/update**

In `ai_daily/api/routes.py`, after `SourceResponse` (line ~59), add:

```python
class SourceCreate(BaseModel):
    type: str
    name: str
    config: Optional[dict] = None
    enabled: bool = True


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None
```

**Step 2: Add CRUD endpoints**

After the existing `list_sources` endpoint, add:

```python
@router.get("/sources/{source_id}", response_model=SourceResponse)
def get_source(source_id: int, db: Session = Depends(get_db)):
    """Get a single source by ID."""
    try:
        source = db.get(Source, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        return source
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_source: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(source: SourceCreate, db: Session = Depends(get_db)):
    """Create a new source."""
    try:
        db_source = Source(
            type=source.type,
            name=source.name,
            config=source.config,
            enabled=source.enabled,
        )
        db.add(db_source)
        db.commit()
        db.refresh(db_source)
        return db_source
    except SQLAlchemyError as e:
        logger.error(f"Database error in create_source: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.put("/sources/{source_id}", response_model=SourceResponse)
def update_source(source_id: int, source: SourceUpdate, db: Session = Depends(get_db)):
    """Update an existing source."""
    try:
        db_source = db.get(Source, source_id)
        if not db_source:
            raise HTTPException(status_code=404, detail="Source not found")

        if source.name is not None:
            db_source.name = source.name
        if source.config is not None:
            db_source.config = source.config
        if source.enabled is not None:
            db_source.enabled = source.enabled

        db.commit()
        db.refresh(db_source)
        return db_source
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_source: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    """Delete a source."""
    try:
        db_source = db.get(Source, source_id)
        if not db_source:
            raise HTTPException(status_code=404, detail="Source not found")

        db.delete(db_source)
        db.commit()
        return None
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in delete_source: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.patch("/sources/{source_id}/toggle", response_model=SourceResponse)
def toggle_source(source_id: int, db: Session = Depends(get_db)):
    """Toggle source enabled/disabled."""
    try:
        db_source = db.get(Source, source_id)
        if not db_source:
            raise HTTPException(status_code=404, detail="Source not found")

        db_source.enabled = not db_source.enabled
        db.commit()
        db.refresh(db_source)
        return db_source
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in toggle_source: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
```

**Step 3: Write tests**

Create `tests/test_api_sources.py`:

```python
"""Tests for source API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from ai_daily.api.server import app
from ai_daily.db.models import Source


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_session():
    return MagicMock()


@patch("ai_daily.api.routes.get_db")
def test_create_source(mock_get_db, client, mock_session):
    """POST /sources should create a new source."""
    mock_get_db.return_value = iter([mock_session])

    mock_source = MagicMock()
    mock_source.id = 1
    mock_source.type = "rss"
    mock_source.name = "Test Feed"
    mock_source.config = {"url": "https://example.com/feed"}
    mock_source.enabled = True

    def add_and_set_id(src):
        pass
    mock_session.add.side_effect = add_and_set_id
    mock_session.refresh.side_effect = lambda src: setattr(src, 'id', 1)

    response = client.post("/api/v1/sources", json={
        "type": "rss",
        "name": "Test Feed",
        "config": {"url": "https://example.com/feed"}
    })

    assert response.status_code == 201
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@patch("ai_daily.api.routes.get_db")
def test_delete_source(mock_get_db, client, mock_session):
    """DELETE /sources/{id} should delete a source."""
    mock_get_db.return_value = iter([mock_session])

    mock_source = MagicMock()
    mock_source.id = 1
    mock_session.get.return_value = mock_source

    response = client.delete("/api/v1/sources/1")

    assert response.status_code == 204
    mock_session.delete.assert_called_once_with(mock_source)
    mock_session.commit.assert_called_once()


@patch("ai_daily.api.routes.get_db")
def test_delete_source_not_found(mock_get_db, client, mock_session):
    """DELETE /sources/{id} should return 404 if source not found."""
    mock_get_db.return_value = iter([mock_session])
    mock_session.get.return_value = None

    response = client.delete("/api/v1/sources/999")

    assert response.status_code == 404


@patch("ai_daily.api.routes.get_db")
def test_toggle_source(mock_get_db, client, mock_session):
    """PATCH /sources/{id}/toggle should toggle enabled."""
    mock_get_db.return_value = iter([mock_session])

    mock_source = MagicMock()
    mock_source.id = 1
    mock_source.type = "rss"
    mock_source.name = "Test"
    mock_source.enabled = True
    mock_session.get.return_value = mock_source

    response = client.patch("/api/v1/sources/1/toggle")

    assert response.status_code == 200
    assert mock_source.enabled == False
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_api_sources.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add ai_daily/api/routes.py tests/test_api_sources.py
git commit -m "feat(api): add source CRUD endpoints"
```

---

### Task 2: Add Source Test Endpoint

**Files:**
- Modify: `ai_daily/api/routes.py`

**Step 1: Add test endpoint with preview response model**

After the toggle endpoint, add:

```python
class SourceTestResult(BaseModel):
    success: bool
    message: Optional[str] = None
    preview: Optional[dict] = None


@router.post("/sources/test", response_model=SourceTestResult)
def test_source_config(source: SourceCreate):
    """Test a source configuration without saving."""
    if source.type == "rss":
        return _test_rss_source(source.config)
    elif source.type == "newsletter":
        return _test_newsletter_source(source.config)
    elif source.type == "crawler":
        return _test_crawler_source(source.config)
    else:
        return SourceTestResult(success=False, message=f"Unknown source type: {source.type}")


def _test_rss_source(config: Optional[dict]) -> SourceTestResult:
    """Test RSS feed by parsing it."""
    if not config or not config.get("url"):
        return SourceTestResult(success=False, message="Missing URL in config")

    try:
        import feedparser
        feed = feedparser.parse(config["url"])

        if feed.bozo and not feed.entries:
            return SourceTestResult(
                success=False,
                message=f"Failed to parse feed: {feed.bozo_exception}"
            )

        return SourceTestResult(
            success=True,
            preview={
                "feed_title": feed.feed.get("title", "Unknown"),
                "entry_count": len(feed.entries),
                "sample_titles": [e.get("title", "")[:100] for e in feed.entries[:3]]
            }
        )
    except Exception as e:
        return SourceTestResult(success=False, message=str(e))


def _test_newsletter_source(config: Optional[dict]) -> SourceTestResult:
    """Validate newsletter email config."""
    if not config or not config.get("email"):
        return SourceTestResult(success=False, message="Missing email in config")

    import re
    email = config["email"]
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return SourceTestResult(success=False, message="Invalid email format")

    return SourceTestResult(
        success=True,
        message=f"Email format valid: {email}"
    )


def _test_crawler_source(config: Optional[dict]) -> SourceTestResult:
    """Test crawler by fetching URL and applying selectors."""
    if not config or not config.get("url"):
        return SourceTestResult(success=False, message="Missing URL in config")

    try:
        import requests
        from bs4 import BeautifulSoup

        response = requests.get(config["url"], timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        selectors = config.get("selectors", {})
        items_selector = selectors.get("items", "item")

        items = soup.select(items_selector)

        return SourceTestResult(
            success=True,
            preview={
                "items_found": len(items),
                "sample_titles": [
                    item.select_one(selectors.get("title", "title")).get_text(strip=True)[:100]
                    if item.select_one(selectors.get("title", "title"))
                    else "No title"
                    for item in items[:3]
                ]
            }
        )
    except Exception as e:
        return SourceTestResult(success=False, message=str(e))
```

**Step 2: Run all tests**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 3: Commit**

```bash
git add ai_daily/api/routes.py
git commit -m "feat(api): add source test endpoint"
```

---

### Task 3: Add Status Endpoint

**Files:**
- Modify: `ai_daily/api/routes.py`

**Step 1: Add status endpoint**

Add after the test endpoint:

```python
class SystemStatus(BaseModel):
    database: str
    total_articles: int
    articles_today: int
    active_sources: int
    last_job: Optional[dict] = None
    next_runs: Optional[dict] = None


@router.get("/status", response_model=SystemStatus)
def get_status(db: Session = Depends(get_db)):
    """Get system status and stats."""
    from datetime import timedelta
    from croniter import croniter
    from ai_daily.config import config

    try:
        # Count articles
        total_articles = db.execute(select(func.count(Article.id))).scalar() or 0

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        articles_today = db.execute(
            select(func.count(Article.id)).where(Article.published_at >= today_start)
        ).scalar() or 0

        # Count active sources
        active_sources = db.execute(
            select(func.count(Source.id)).where(Source.enabled == True)
        ).scalar() or 0

        # Last job
        last_job_obj = db.execute(
            select(JobRun).order_by(JobRun.started_at.desc()).limit(1)
        ).scalar_one_or_none()

        last_job = None
        if last_job_obj:
            last_job = {
                "name": last_job_obj.job_name,
                "status": last_job_obj.status,
                "started_at": last_job_obj.started_at.isoformat() if last_job_obj.started_at else None
            }

        # Next scheduled runs
        now = datetime.utcnow()
        schedules = {
            "etl": config.orchestrator.etl_schedule,
            "newsletter": config.orchestrator.newsletter_schedule,
        }
        next_runs = {}
        for job_name, cron_expr in schedules.items():
            try:
                cron = croniter(cron_expr, now)
                next_runs[job_name] = cron.get_next(datetime).isoformat()
            except Exception:
                pass

        return SystemStatus(
            database="connected",
            total_articles=total_articles,
            articles_today=articles_today,
            active_sources=active_sources,
            last_job=last_job,
            next_runs=next_runs if next_runs else None
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_status: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
```

**Step 2: Add func import at top of file**

Add to imports at top of `routes.py`:

```python
from sqlalchemy import func, or_, select
```

**Step 3: Run tests**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 4: Commit**

```bash
git add ai_daily/api/routes.py
git commit -m "feat(api): add system status endpoint"
```

---

### Task 4: Add Summaries List Endpoint

**Files:**
- Modify: `ai_daily/api/routes.py`

**Step 1: Add summaries list endpoint**

After the existing `get_summary` endpoint, add:

```python
@router.get("/summaries", response_model=List[SummaryResponse])
def list_summaries(
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List daily summaries."""
    try:
        stmt = select(DailySummary).order_by(DailySummary.date.desc()).offset(offset).limit(limit)
        return db.execute(stmt).scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_summaries: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
```

**Step 2: Commit**

```bash
git add ai_daily/api/routes.py
git commit -m "feat(api): add summaries list endpoint"
```

---

## Phase 2: Frontend Setup

### Task 5: Initialize React Project

**Files:**
- Create: `frontend/` directory with Vite + React + TypeScript

**Step 1: Create frontend directory and initialize Vite project**

Run from worktree root:

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer @headlessui/react
npx tailwindcss init -p
```

**Step 2: Configure Tailwind**

Replace `frontend/tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

**Step 3: Add Tailwind to CSS**

Replace `frontend/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**Step 4: Configure Vite proxy for development**

Replace `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../ai_daily/static',
    emptyOutDir: true,
  },
})
```

**Step 5: Test frontend dev server**

Run: `cd frontend && npm run dev`

Expected: Opens browser to localhost:5173 with React app

**Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): initialize React + Vite + Tailwind project"
```

---

### Task 6: Create Layout and Router

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/Articles.tsx`
- Create: `frontend/src/pages/Sources.tsx`
- Create: `frontend/src/pages/Jobs.tsx`

**Step 1: Install React Router**

```bash
cd frontend && npm install react-router-dom
```

**Step 2: Create Layout component**

Create `frontend/src/components/Layout.tsx`:

```tsx
import { Link, Outlet, useLocation } from 'react-router-dom'

const navigation = [
  { name: 'Dashboard', href: '/' },
  { name: 'Articles', href: '/articles' },
  { name: 'Sources', href: '/sources' },
  { name: 'Jobs', href: '/jobs' },
]

export default function Layout() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow">
        <div className="mx-auto max-w-7xl px-4">
          <div className="flex h-16 justify-between">
            <div className="flex">
              <div className="flex flex-shrink-0 items-center">
                <span className="text-xl font-bold text-gray-900">AI Daily</span>
              </div>
              <div className="ml-10 flex space-x-8">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium ${
                      location.pathname === item.href
                        ? 'border-indigo-500 text-gray-900'
                        : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </nav>
      <main className="py-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
```

**Step 3: Create placeholder pages**

Create `frontend/src/pages/Dashboard.tsx`:

```tsx
export default function Dashboard() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      <p className="mt-2 text-gray-600">System overview coming soon.</p>
    </div>
  )
}
```

Create `frontend/src/pages/Articles.tsx`:

```tsx
export default function Articles() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Articles</h1>
      <p className="mt-2 text-gray-600">Article list coming soon.</p>
    </div>
  )
}
```

Create `frontend/src/pages/Sources.tsx`:

```tsx
export default function Sources() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Sources</h1>
      <p className="mt-2 text-gray-600">Source management coming soon.</p>
    </div>
  )
}
```

Create `frontend/src/pages/Jobs.tsx`:

```tsx
export default function Jobs() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
      <p className="mt-2 text-gray-600">Job history coming soon.</p>
    </div>
  )
}
```

**Step 4: Update App.tsx with router**

Replace `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Articles from './pages/Articles'
import Sources from './pages/Sources'
import Jobs from './pages/Jobs'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="articles" element={<Articles />} />
          <Route path="sources" element={<Sources />} />
          <Route path="jobs" element={<Jobs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
```

**Step 5: Verify dev server works with routing**

Run: `cd frontend && npm run dev`

Expected: Can navigate between pages using nav links

**Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): add layout and page routing"
```

---

### Task 7: Create API Client

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/types.ts`

**Step 1: Create types**

Create `frontend/src/api/types.ts`:

```typescript
export interface Article {
  id: number
  title: string
  content: string
  url?: string
  topic?: string
  published_at?: string
  source_name?: string
}

export interface Source {
  id: number
  type: string
  name: string
  config?: Record<string, unknown>
  enabled: boolean
}

export interface SourceCreate {
  type: string
  name: string
  config?: Record<string, unknown>
  enabled?: boolean
}

export interface Job {
  id: number
  job_name: string
  started_at: string
  finished_at?: string
  status?: string
  metrics?: Record<string, unknown>
  error_message?: string
}

export interface Summary {
  date: string
  summary_text?: string
  key_facts?: unknown
}

export interface SystemStatus {
  database: string
  total_articles: number
  articles_today: number
  active_sources: number
  last_job?: {
    name: string
    status: string
    started_at: string
  }
  next_runs?: Record<string, string>
}

export interface SourceTestResult {
  success: boolean
  message?: string
  preview?: {
    feed_title?: string
    entry_count?: number
    sample_titles?: string[]
    items_found?: number
  }
}
```

**Step 2: Create API client**

Create `frontend/src/api/client.ts`:

```typescript
import type { Article, Source, SourceCreate, Job, Summary, SystemStatus, SourceTestResult } from './types'

const API_BASE = '/api/v1'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json()
}

export const api = {
  // Status
  getStatus: () => fetchJSON<SystemStatus>(`${API_BASE}/status`),

  // Articles
  getArticles: (params?: { q?: string; topic?: string; limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.q) searchParams.set('q', params.q)
    if (params?.topic) searchParams.set('topic', params.topic)
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    const query = searchParams.toString()
    return fetchJSON<Article[]>(`${API_BASE}/articles${query ? `?${query}` : ''}`)
  },

  getArticle: (id: number) => fetchJSON<Article>(`${API_BASE}/articles/${id}`),

  // Sources
  getSources: () => fetchJSON<Source[]>(`${API_BASE}/sources`),

  getSource: (id: number) => fetchJSON<Source>(`${API_BASE}/sources/${id}`),

  createSource: (source: SourceCreate) =>
    fetchJSON<Source>(`${API_BASE}/sources`, {
      method: 'POST',
      body: JSON.stringify(source),
    }),

  updateSource: (id: number, source: Partial<SourceCreate>) =>
    fetchJSON<Source>(`${API_BASE}/sources/${id}`, {
      method: 'PUT',
      body: JSON.stringify(source),
    }),

  deleteSource: (id: number) =>
    fetchJSON<void>(`${API_BASE}/sources/${id}`, { method: 'DELETE' }),

  toggleSource: (id: number) =>
    fetchJSON<Source>(`${API_BASE}/sources/${id}/toggle`, { method: 'PATCH' }),

  testSource: (source: SourceCreate) =>
    fetchJSON<SourceTestResult>(`${API_BASE}/sources/test`, {
      method: 'POST',
      body: JSON.stringify(source),
    }),

  // Jobs
  getJobs: (limit?: number) => {
    const query = limit ? `?limit=${limit}` : ''
    return fetchJSON<Job[]>(`${API_BASE}/jobs${query}`)
  },

  // Summaries
  getSummaries: (params?: { limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    const query = searchParams.toString()
    return fetchJSON<Summary[]>(`${API_BASE}/summaries${query ? `?${query}` : ''}`)
  },
}
```

**Step 3: Commit**

```bash
git add frontend/src/api/
git commit -m "feat(frontend): add API client and types"
```

---

### Task 8: Implement Dashboard Page

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

**Step 1: Implement Dashboard with status display**

Replace `frontend/src/pages/Dashboard.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { SystemStatus, Job } from '../api/types'

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [recentJobs, setRecentJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        const [statusData, jobsData] = await Promise.all([
          api.getStatus(),
          api.getJobs(5),
        ])
        setStatus(statusData)
        setRecentJobs(jobsData)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) return <div className="text-gray-500">Loading...</div>
  if (error) return <div className="text-red-500">Error: {error}</div>
  if (!status) return null

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-4">
        <StatCard title="Database" value={status.database} />
        <StatCard title="Total Articles" value={status.total_articles.toString()} />
        <StatCard title="Articles Today" value={status.articles_today.toString()} />
        <StatCard title="Active Sources" value={status.active_sources.toString()} />
      </div>

      {/* Last Job */}
      {status.last_job && (
        <div className="bg-white shadow rounded-lg p-4">
          <h2 className="text-lg font-medium text-gray-900 mb-2">Last Job</h2>
          <p className="text-gray-600">
            <span className="font-medium">{status.last_job.name}</span>
            {' - '}
            <span className={status.last_job.status === 'success' ? 'text-green-600' : 'text-red-600'}>
              {status.last_job.status}
            </span>
            {' at '}
            {new Date(status.last_job.started_at).toLocaleString()}
          </p>
        </div>
      )}

      {/* Recent Jobs */}
      <div className="bg-white shadow rounded-lg p-4">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Jobs</h2>
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Job</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Status</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">Started</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {recentJobs.map((job) => (
              <tr key={job.id}>
                <td className="px-4 py-2 text-sm text-gray-900">{job.job_name}</td>
                <td className="px-4 py-2 text-sm">
                  <span className={`px-2 py-1 rounded text-xs ${
                    job.status === 'success' ? 'bg-green-100 text-green-800' :
                    job.status === 'failed' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {job.status || 'running'}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-500">
                  {new Date(job.started_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function StatCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="bg-white shadow rounded-lg p-4">
      <p className="text-sm font-medium text-gray-500">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(frontend): implement Dashboard page"
```

---

### Task 9: Implement Articles Page

**Files:**
- Modify: `frontend/src/pages/Articles.tsx`

**Step 1: Implement Articles with search and pagination**

Replace `frontend/src/pages/Articles.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Article } from '../api/types'

export default function Articles() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const limit = 20

  useEffect(() => {
    async function fetchArticles() {
      setLoading(true)
      try {
        const data = await api.getArticles({ q: search || undefined, limit, offset })
        setArticles(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchArticles()
  }, [search, offset])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setOffset(0)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Articles</h1>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search..."
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
          <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700">
            Search
          </button>
        </form>
      </div>

      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-500">Error: {error}</div>}

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Title</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Source</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Topic</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {articles.map((article) => (
              <>
                <tr
                  key={article.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExpandedId(expandedId === article.id ? null : article.id)}
                >
                  <td className="px-4 py-3 text-sm text-gray-900">{article.title}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{article.source_name || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{article.topic || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {article.published_at ? new Date(article.published_at).toLocaleDateString() : '-'}
                  </td>
                </tr>
                {expandedId === article.id && (
                  <tr key={`${article.id}-content`}>
                    <td colSpan={4} className="px-4 py-4 bg-gray-50">
                      <p className="text-sm text-gray-700 whitespace-pre-wrap">{article.content}</p>
                      {article.url && (
                        <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 text-sm hover:underline mt-2 block">
                          Read more
                        </a>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center">
        <button
          onClick={() => setOffset(Math.max(0, offset - limit))}
          disabled={offset === 0}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-sm text-gray-500">Showing {offset + 1} - {offset + articles.length}</span>
        <button
          onClick={() => setOffset(offset + limit)}
          disabled={articles.length < limit}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Articles.tsx
git commit -m "feat(frontend): implement Articles page with search"
```

---

### Task 10: Implement Sources Page

**Files:**
- Modify: `frontend/src/pages/Sources.tsx`
- Create: `frontend/src/components/SourceModal.tsx`

**Step 1: Create SourceModal component**

Create `frontend/src/components/SourceModal.tsx`:

```tsx
import { useState } from 'react'
import { Dialog } from '@headlessui/react'
import { api } from '../api/client'
import type { Source, SourceCreate, SourceTestResult } from '../api/types'

interface Props {
  source?: Source
  onClose: () => void
  onSave: () => void
}

export default function SourceModal({ source, onClose, onSave }: Props) {
  const [type, setType] = useState(source?.type || 'rss')
  const [name, setName] = useState(source?.name || '')
  const [config, setConfig] = useState(JSON.stringify(source?.config || {}, null, 2))
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<SourceTestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    setError(null)
    try {
      const configObj = JSON.parse(config)
      const result = await api.testSource({ type, name, config: configObj })
      setTestResult(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Test failed')
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const configObj = JSON.parse(config)
      const data: SourceCreate = { type, name, config: configObj }
      if (source) {
        await api.updateSource(source.id, data)
      } else {
        await api.createSource(data)
      }
      onSave()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/30" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className="bg-white rounded-lg p-6 w-full max-w-md">
          <Dialog.Title className="text-lg font-medium text-gray-900 mb-4">
            {source ? 'Edit Source' : 'Add Source'}
          </Dialog.Title>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                disabled={!!source}
                className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="rss">RSS</option>
                <option value="newsletter">Newsletter</option>
                <option value="crawler">Crawler</option>
                <option value="github">GitHub</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Config (JSON)</label>
              <textarea
                value={config}
                onChange={(e) => setConfig(e.target.value)}
                rows={5}
                className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono"
              />
            </div>

            {testResult && (
              <div className={`p-3 rounded text-sm ${testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
                {testResult.success ? 'Test passed!' : testResult.message}
                {testResult.preview && (
                  <pre className="mt-2 text-xs">{JSON.stringify(testResult.preview, null, 2)}</pre>
                )}
              </div>
            )}

            {error && <div className="text-red-600 text-sm">{error}</div>}
          </div>

          <div className="mt-6 flex justify-between">
            <button
              onClick={handleTest}
              disabled={testing}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
            >
              {testing ? 'Testing...' : 'Test'}
            </button>
            <div className="flex gap-2">
              <button onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-md text-sm">
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </Dialog.Panel>
      </div>
    </Dialog>
  )
}
```

**Step 2: Implement Sources page**

Replace `frontend/src/pages/Sources.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Source } from '../api/types'
import SourceModal from '../components/SourceModal'

export default function Sources() {
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSource, setEditingSource] = useState<Source | undefined>()

  const fetchSources = async () => {
    try {
      const data = await api.getSources()
      setSources(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  const handleToggle = async (source: Source) => {
    try {
      await api.toggleSource(source.id)
      fetchSources()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to toggle')
    }
  }

  const handleDelete = async (source: Source) => {
    if (!confirm(`Delete source "${source.name}"?`)) return
    try {
      await api.deleteSource(source.id)
      fetchSources()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete')
    }
  }

  const handleEdit = (source: Source) => {
    setEditingSource(source)
    setModalOpen(true)
  }

  const handleAdd = () => {
    setEditingSource(undefined)
    setModalOpen(true)
  }

  const handleModalClose = () => {
    setModalOpen(false)
    setEditingSource(undefined)
  }

  const handleModalSave = () => {
    setModalOpen(false)
    setEditingSource(undefined)
    fetchSources()
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Sources</h1>
        <button
          onClick={handleAdd}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
        >
          Add Source
        </button>
      </div>

      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-500">Error: {error}</div>}

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Name</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Type</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Enabled</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {sources.map((source) => (
              <tr key={source.id}>
                <td className="px-4 py-3 text-sm text-gray-900">{source.name}</td>
                <td className="px-4 py-3 text-sm text-gray-500">{source.type}</td>
                <td className="px-4 py-3 text-sm">
                  <button
                    onClick={() => handleToggle(source)}
                    className={`px-2 py-1 rounded text-xs ${
                      source.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {source.enabled ? 'Enabled' : 'Disabled'}
                  </button>
                </td>
                <td className="px-4 py-3 text-sm text-right space-x-2">
                  <button
                    onClick={() => handleEdit(source)}
                    className="text-indigo-600 hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(source)}
                    className="text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <SourceModal
          source={editingSource}
          onClose={handleModalClose}
          onSave={handleModalSave}
        />
      )}
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/pages/Sources.tsx frontend/src/components/SourceModal.tsx
git commit -m "feat(frontend): implement Sources page with CRUD modal"
```

---

### Task 11: Implement Jobs Page

**Files:**
- Modify: `frontend/src/pages/Jobs.tsx`

**Step 1: Implement Jobs page**

Replace `frontend/src/pages/Jobs.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Job } from '../api/types'

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  useEffect(() => {
    async function fetchJobs() {
      try {
        const data = await api.getJobs(50)
        setJobs(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    fetchJobs()
  }, [])

  if (loading) return <div className="text-gray-500">Loading...</div>
  if (error) return <div className="text-red-500">Error: {error}</div>

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Job History</h1>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Job</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Started</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {jobs.map((job) => {
              const duration = job.finished_at && job.started_at
                ? Math.round((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)
                : null

              return (
                <>
                  <tr
                    key={job.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => setExpandedId(expandedId === job.id ? null : job.id)}
                  >
                    <td className="px-4 py-3 text-sm text-gray-900">{job.job_name}</td>
                    <td className="px-4 py-3 text-sm">
                      <span className={`px-2 py-1 rounded text-xs ${
                        job.status === 'success' ? 'bg-green-100 text-green-800' :
                        job.status === 'failed' ? 'bg-red-100 text-red-800' :
                        'bg-yellow-100 text-yellow-800'
                      }`}>
                        {job.status || 'running'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(job.started_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {duration !== null ? `${duration}s` : '-'}
                    </td>
                  </tr>
                  {expandedId === job.id && (
                    <tr key={`${job.id}-details`}>
                      <td colSpan={4} className="px-4 py-4 bg-gray-50">
                        {job.metrics && (
                          <div className="mb-2">
                            <span className="font-medium text-sm text-gray-700">Metrics: </span>
                            <span className="text-sm text-gray-600">{JSON.stringify(job.metrics)}</span>
                          </div>
                        )}
                        {job.error_message && (
                          <div className="text-sm text-red-600">
                            <span className="font-medium">Error: </span>
                            {job.error_message}
                          </div>
                        )}
                        {!job.metrics && !job.error_message && (
                          <span className="text-sm text-gray-500">No additional details</span>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Jobs.tsx
git commit -m "feat(frontend): implement Jobs page"
```

---

## Phase 3: Integration

### Task 12: Configure Static File Serving

**Files:**
- Modify: `ai_daily/api/server.py`

**Step 1: Add static file serving**

Replace `ai_daily/api/server.py`:

```python
"""FastAPI server configuration."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ai_daily.api.routes import router

app = FastAPI(
    title="AI Daily Summary API",
    description="API for the AI news aggregation platform",
    version="0.2.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Static files serving for frontend
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    # SPA fallback - serve index.html for all non-API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"error": "Frontend not built"}
```

**Step 2: Commit**

```bash
git add ai_daily/api/server.py
git commit -m "feat(api): add static file serving for frontend"
```

---

### Task 13: Build Frontend

**Step 1: Build production assets**

```bash
cd frontend && npm run build
```

Expected: Creates `ai_daily/static/` directory with built assets

**Step 2: Verify build output**

Run: `ls -la ai_daily/static/`

Expected: Shows `index.html` and `assets/` directory

**Step 3: Add static to gitignore**

Add to `.gitignore`:

```
ai_daily/static/
```

**Step 4: Commit gitignore update**

```bash
git add .gitignore
git commit -m "chore: ignore built frontend assets"
```

---

### Task 14: Update Dockerfile

**Files:**
- Modify: `Dockerfile`

**Step 1: Add frontend build to Dockerfile**

Read current Dockerfile and add Node.js build step before Python section. Add after the existing content or integrate as needed:

```dockerfile
# Frontend build stage
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ... existing Python build ...
# Copy frontend assets
COPY --from=frontend-builder /frontend/../ai_daily/static /app/ai_daily/static
```

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "build: add frontend build to Dockerfile"
```

---

### Task 15: Final Integration Test

**Step 1: Start backend**

```bash
uv run ai-daily serve
```

**Step 2: In another terminal, build and test frontend**

```bash
cd frontend && npm run build
```

**Step 3: Access http://localhost:8000**

Expected: Frontend loads, can navigate pages, API calls work

**Step 4: Run all tests**

```bash
uv run pytest -v
```

Expected: All tests PASS

---

## Summary

| Task | Description | Commits |
|------|-------------|---------|
| 1 | Source CRUD endpoints | 1 |
| 2 | Source test endpoint | 1 |
| 3 | Status endpoint | 1 |
| 4 | Summaries list endpoint | 1 |
| 5 | Initialize React project | 1 |
| 6 | Layout and routing | 1 |
| 7 | API client | 1 |
| 8 | Dashboard page | 1 |
| 9 | Articles page | 1 |
| 10 | Sources page | 1 |
| 11 | Jobs page | 1 |
| 12 | Static file serving | 1 |
| 13 | Build frontend | 1 |
| 14 | Update Dockerfile | 1 |
| 15 | Integration test | 0 |

**Total: 14 commits**
