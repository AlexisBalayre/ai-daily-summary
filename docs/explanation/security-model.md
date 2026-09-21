# Security Model

The trust, auth, secrets, and input-handling model for this project. The **`security-reviewer`**
subagent checks diffs against this file, so keep it concrete and reviewable. State each rule as an
obligation a reviewer can verify in a diff.

The deployment model is a single operator running their own instance, with their own Gmail
account, on loopback or a private network (e.g. Tailscale).

## Trust boundaries

| Boundary | Untrusted side | Guarded by |
| :------- | :------------- | :--------- |
| REST API (`ai_daily/api/`) | Anyone who can reach port 8000 | Loopback bind by default; `require_api_token` on every mutating route; CORS off unless `CORS_ORIGINS` |
| Outbound fetch of operator-supplied URLs | Source configs (RSS/crawler URLs) | `ensure_public_http_url` (`ai_daily/etl/urlcheck.py`) on the source-test endpoint |
| Ingested content -> LLM | Newsletter bodies, feeds, crawled pages | Gmail sender whitelist; content treated as data in prompts |
| LLM / ingested content -> email HTML | Article titles, URLs, summaries | `html.escape` and `safe_href` (`ai_daily/outputs/html_utils.py`) |
| MCP server (`scripts/aidaily_mcp.py`) | MCP clients | Loopback-only host/origin allowlist unless `MCP_PUBLIC_HOST` is set |

## Authentication

- Single shared bearer token: `API_TOKEN`. When set, mutating routes (sources, whitelist, job triggers, chat) require `Authorization: Bearer <token>`, compared with `hmac.compare_digest`. When unset, the check is skipped.
- Every new mutating route (`POST`/`PUT`/`PATCH`/`DELETE`) and every route that spends LLM quota MUST carry `dependencies=[Depends(require_api_token)]`. Reviewers grep new `@router.` decorators for it.
- Reads are unauthenticated by design.
- The MCP server has no authentication; it relies on its host allowlist.

## Authorization

Single operator, no roles: holding `API_TOKEN` grants every write. There are no per-user resources.

## Secrets handling

- Secrets come from the environment through `ai_daily/config.py` only (`GOOGLE_API_KEY`, `API_TOKEN`, DB password, Gmail paths); never inlined or read with ad hoc `os.getenv` at a call site outside config.
- `.env`, `token.json`, `credentials.json` / `client_secret*.json` and `config.json` are gitignored and must never be committed; gitleaks runs in CI as a backstop.
- `token.json` holds a Gmail refresh token with **read + send** scopes; it is written with mode `0600` (`ai_daily/etl/extractors/gmail.py`). Any new write path for it keeps that mode.
- Do not widen the Gmail OAuth scopes beyond `gmail.readonly` + `gmail.send`.
- The DB password is URL-encoded (`quote_plus`) into the connection URL.

## Input validation

- Request bodies and query parameters are validated by Pydantic models / FastAPI parameters at the route boundary.
- `LIKE` search input goes through `escape_like_wildcards`; queries use SQLAlchemy expressions, never string-interpolated SQL.
- Any outbound request to a URL taken from API input calls `ensure_public_http_url` first (http/https only; every resolved address must be global), and does not follow redirects (`allow_redirects=False`).
- Previews of arbitrary pages cap the bytes read (the crawler source test reads at most 2 MB).
- List endpoints carry a bounded limit.

## Output and data protection

- Sensitive data: the Gmail token, `API_TOKEN`, `GOOGLE_API_KEY`, the recipient list and sender whitelist, and newsletter bodies (the operator's mail).
- Responses use Pydantic response models; no raw ORM entity is returned.
- Logs never contain tokens, keys, or email bodies.
- HTML emails escape every interpolated value; hrefs go through `safe_href`. Any raw-HTML escape hatch requires sanitization.
- The dashboard stores `API_TOKEN` in browser localStorage.

## Abuse controls

- Failure emails are rate limited to one per job per hour.
- No request rate limiting on the API; exposure beyond loopback is expected to sit behind an authenticating proxy or a private network.

## Open questions

- The scheduled RSS and crawler extractors fetch source URLs without calling `ensure_public_http_url`; only the source-test endpoint does. Sources can only be created with `API_TOKEN` (or via CLI/seed), but whether create/update should validate the URL too is undecided.
- `ensure_public_http_url` resolves DNS separately from the fetch, so DNS rebinding between check and fetch is not covered.
- Ingested content is fed to Gemini, including the chat endpoint's tool loop; there is no explicit prompt-injection mitigation beyond the tools being read-only.

## Known accepted risks

| Risk | Why accepted | Revisit when |
| :--- | :----------- | :----------- |
| Reads are unauthenticated | Single-operator, loopback-bound deployment; the dashboard stays frictionless | The API is exposed beyond a private network |
| `API_TOKEN` unset means writes are open | Keeps local development frictionless; Compose binds to `127.0.0.1` | Same as above |
| MCP server unauthenticated | Loopback or Tailscale only | `MCP_PUBLIC_HOST` points at a public name |
