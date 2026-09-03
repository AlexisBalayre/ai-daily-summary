# AI Daily dashboard

React 19 + Vite + Tailwind front end for the AI Daily Summary API.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to http://localhost:8000
npm run lint
npm run build    # writes to ../ai_daily/static, served by `ai-daily serve`
```

Run the API first (`uv run ai-daily serve` from the repo root) so the proxy has something to talk to.
