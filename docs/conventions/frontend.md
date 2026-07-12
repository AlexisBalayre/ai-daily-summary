# Frontend Conventions (`frontend/`)

React + Tailwind CSS dashboard. Built assets are emitted to `ai_daily/static/` and served by FastAPI —
**never hand-edit the built output** (the `protect-generated` hook blocks it); edit source under
`frontend/` and rebuild.

## Build

- `cd frontend && npm install && npm run build`.
- The build writes into `ai_daily/static/`; that directory is git-ignored and generated.

## Components

- Function components + hooks; no class components.
- Keep components small and typed. Colocate a component with its styles/tests.
- Data fetching goes through the FastAPI endpoints — don't hardcode data or reach around the API.

## Styling

- Tailwind utility classes; avoid ad-hoc inline styles and one-off global CSS.
- Keep the visual language consistent with the existing dashboard (spacing scale, color tokens).

## State & data

- Local UI state in hooks; server state fetched from the API and cached at the fetch layer.
- Don't duplicate business logic that already lives in the backend — the dashboard renders, it doesn't
  re-implement enrichment or ranking.
