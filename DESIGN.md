# Lattice Automation

> Package lives at `/git/lattice/` (standalone repo).
> SSO login completed via Playwright headed browser or Chrome CDP.
> Session stored at `~/.config/lattice/browser-state.json`.

---

## Status: Working

All milestones achieved:

- [x] Package built at `lattice/` — 64 unit tests passing
- [x] `pip install -e ".[dev,ui]" && playwright install chromium`
- [x] SSO login via headed Playwright or CDP (`--cdp-url http://127.0.0.1:9223`)
- [x] Scrape `/` (root is authenticated home, not `/home`)
- [x] GraphQL capture working (4+ responses per page)
- [x] Read objectives via GraphQL (`viewer.goals.edges`)
- [x] **Write objectives** — posted update via `AddUpdateToGoalMutation`
- [x] **MCP server** — full CRUD: create, list, update, delete objectives
- [x] Async Playwright (required for MCP's async event loop)

---

## Goal

Programmatic Lattice access **without** a Lattice admin API key:

1. Manual SSO in a real browser (Playwright headed or Chrome CDP)
2. Persist Playwright `storage_state`
3. Scrape pages + **capture GraphQL** JSON for automation
4. Parsers → CLI → optional MCP

Secondary (only if admin issues a key): Bearer API against `api.latticehq.com`.

---

## Discovered routes and GraphQL

### Working routes

| Path | Content |
|------|---------|
| `/` | Authenticated home dashboard (NOT `/home` — that 404s) |
| `/goals` | Company-wide objectives (14696 total, paginated) |
| `/goals/explore?ownerEntityIdsFilter=["{userId}"]&statusesFilter=["AllActive"]&viewType=cascade` | Personal objectives filtered by owner |
| `/goals/{entityId}` | Single objective detail page |
| `/grow` | Grow page (loaded successfully) |

### GraphQL operations captured

**Read (from `/goals` page):**
- `viewer.goals.edges[].node` — objective list with: `entityId`, `name`, `priority`, `dueDate`, `status` (green/amber/red/null), `computedProgressAmount`, `owners[].name`, `lastUpdate`, `okrType`, `state`
- `viewer.allGoalsAnalytics.goalStatusBreakdown` — counts by status
- `viewer.user` — current user info (entityId, name, title, email, isAdmin)
- `viewer.company.goalCycles` — available fiscal quarters

**Write (from goal detail page "Update" button):**

```graphql
mutation AddUpdateToGoalMutation($input: AddUpdateToGoalInput!) {
  addUpdateToGoal(input: $input) {
    goal { ... }
    goalUpdate { entityId ... }
  }
}
```

Variables:
```json
{
  "input": {
    "goalId": "<base64 goal ID>",
    "data": {
      "comment": "<update text with \\n<br>\\n for newlines>",
      "status": "green"
    }
  }
}
```

- `goalId` is the base64-encoded relay ID (NOT the entityId UUID)
- Status values: `"green"` (On track), `"amber"` (Progressing), `"red"` (Off track)
- Newlines in comment become `\n<br>\n` in the mutation payload
- Introspection is disabled — mutations must be discovered by UI interaction

### Key IDs

| Entity | Value |
|--------|-------|
| User (Sean Ahn) | `01bfc19d-5192-4939-b03d-d185138ce183` |
| Company (C3 AI) | `293aacd4-f240-4356-8b47-34247c10420f` |
| Socket Firewall objective | `c876f39d-374d-42c7-84e5-d8feec38501c` |

---

## Jira integration

Jira API token at `~/.ssh/jira-jupyer` (Atlassian Cloud basic auth).

```bash
curl -s -u "sean.ahn@c3.ai:$(cat ~/.ssh/jira-jupyer)" \
  -X POST "https://c3energy.atlassian.net/rest/api/3/search/jql" \
  -H "Content-Type: application/json" \
  -d '{"jql": "text ~ \"5077-US7\"", "maxResults": 5}'
```

Linked tickets for the Socket Firewall objective:

| Key | Summary | Assignee |
|-----|---------|----------|
| INFOSEC-6098 | [5077-US7] Configure Cursor and Claude Code clients to route package installs through Socket Firewall | Seung Ahn |
| INFOSEC-8167 | [5077-US7] Deliverable Set A — Local agent client config (Cursor local, Claude Code local) | infosec-jira |
| INFOSEC-8168 | [5077-US7] Deliverable Set B — SaaS mode control assessment (Cursor SaaS, Claude Code SaaS) | infosec-jira |

Note: the old `/rest/api/3/search` endpoint is removed — use `/rest/api/3/search/jql` with POST body.

---

## Automation recipe (what worked)

### Update an objective from Jira data

1. Fetch Jira tickets: `POST /rest/api/3/search/jql` with `{"jql": "..."}`
2. Get ticket details: `GET /rest/api/3/issue/{id}?fields=summary,description,status`
3. Open goal page in Playwright with saved storage state
4. Click "Update" button → select status radio → type comment → click second "Update" button
5. GraphQL mutation fires automatically; update is saved

### CDP login (port 9222 taken by Cursor — use 9223)

```bash
google-chrome --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-lattice --no-first-run &
# Complete SSO in browser, then:
python3 -m lattice ui login --cdp-url http://127.0.0.1:9223
```

---

## Decision log (do not re-litigate)

| Topic | Conclusion |
|-------|------------|
| Official Lattice MCP | None. Community MCPs need API keys. |
| Non-admin API keys | **Impossible** — Admin → Platform → API keys only |
| Web SSO → API access | **No** |
| Cookie as `Authorization: Bearer` | **No** — not a Talent API key |
| narwhalChat Lattice | Exists: GraphQL to `https://c3.latticehq.com/` via `latticeToken` **runtime arg**; token **not in git** |
| Steal token from narwhalChat | **Cannot** |
| Approach | **UI scrape + GraphQL capture** after manual SSO |
| Rejected | Automating IdP login; cookie-as-API-key; DOM as stable public API |

Tenant: `c3.latticehq.com`
Talent API (admin path): `https://api.latticehq.com`
narwhalChat code (reference only): `c3engineering/repo/community/narwhalChat/src/lattice/`

---

## Rebuild spec

Package location: `/git/lattice/` (standalone repo, built 2026-07-24, MCP added 2026-07-25).

```
lattice/
  README.md
  DESIGN.md
  pyproject.toml
  src/lattice/
    __init__.py
    __main__.py
    cli.py
    auth.py
    credentials.py
    client.py
    ui.py
    mcp_server.py
  tests/
    test_credentials.py
    test_client.py
    test_auth.py
    test_ui.py
```

### `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lattice-cli"
version = "0.1.0"
description = "CLI for Lattice — API-key auth and Playwright UI scraping"
requires-python = ">=3.10"
license = { text = "Proprietary" }
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=7.0"]
ui = ["playwright>=1.40"]

[project.scripts]
lattice = "lattice.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/lattice"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

### Constants / config

| Name | Value |
|------|--------|
| Default web host | `c3.latticehq.com` |
| Default API URL | `https://api.latticehq.com` |
| Config dir | `~/.config/lattice` (override: `--config-dir` or `LATTICE_CONFIG_DIR`) |
| API creds file | `credentials.json` mode `0600` |
| UI session file | `browser-state.json` mode `0600` |
| Env API token | `LATTICE_API_TOKEN` or `LATTICE_TOKEN` |
| Env API URL | `LATTICE_API_URL` |
| Env web host | `LATTICE_WEB_HOSTNAME` |

### Module: `credentials.py`

- `@dataclass Credentials(token, api_url, web_hostname, user: dict)`
- `masked_token()`, `config_dir()`, `credentials_path()`, `load()`, `save()`, `clear()`
- `load()`: env token overrides file; corrupt file ignored if env set
- `save()`: write via temp file + `os.replace`, chmod `0600`

### Module: `client.py` (API path; stdlib `urllib`)

- `get_me(api_url, token) -> dict` → `GET {api_url}/v1/me` with `Authorization: Bearer …`
- `LatticeAPIError(status, message)`
- `user_display(user) -> str` — name + email fallbacks (`preferredName`/`firstName`/`lastName`/`workEmail`)

### Module: `auth.py` (API path)

| Command | Behavior |
|---------|----------|
| `login` | Optional webbrowser open to `https://{host}/admin`; `getpass` or `--with-token`; validate `/v1/me`; `save()` |
| `status` | Load creds; refresh via `/v1/me` unless offline; print user |
| `logout` | `clear()` |
| `token` | Print raw token to stdout |

### Module: `ui.py` (primary path; Playwright optional import)

**Login detection:** URL is “still logging in” if host ≠ tenant (e.g. Okta) OR path/host contains any of:
`login`, `signin`, `sign-in`, `sso`, `saml`, `oauth`, `okta`, `auth0`, `openid`, `callback`.

**Authenticated:** on tenant hostname, not a login URL, and context has cookies.

| Command | Behavior |
|---------|----------|
| `ui login` | Launch Chromium **headed** by default; goto `https://{hostname}`; wait up to `--timeout` (default 300s) for auth; `storage_state` → `browser-state.json` |
| `ui login --cdp-url URL` | `chromium.connect_over_cdp`; wait for auth; save storage; **do not** close user Chrome |
| `ui login --headless` | Allowed but usually useless for SSO |
| `ui status` | Report whether `browser-state.json` has cookies |
| `ui logout` | Delete `browser-state.json` |
| `ui scrape [path]` | Load storage state; navigate (path or full URL); `networkidle` + ~1.5s; if redirected to login → error “re-login”; dump outputs |

**Scrape outputs** (dir `--out`, default `./lattice-scrape`):

| File | Content |
|------|---------|
| `scrape.meta.json` | `{url, title}` |
| `scrape.txt` | `page.inner_text("body")` |
| `scrape.graphql.json` | List of `{url, status, body}` for responses whose URL contains `graphql` (unless `--no-graphql`) |
| `scrape.html` | Full HTML if `--html` |
| screenshot | If `--screenshot PATH` |

**Launch error UX:** On Playwright launch failure, print hints:

- `python3 -m playwright install-deps chromium`
- `python3 -m playwright install chromium`
- If no `DISPLAY`/`WAYLAND_DISPLAY`: explain headed SSO impossible; suggest laptop login or `--cdp-url`

**Do not** treat missing Playwright as a hard import at module load — fail with install instructions when UI commands run.

### Module: `cli.py`

```
lattice [--config-dir DIR] [--version]
  auth login [--hostname] [--api-url] [--with-token] [--no-browser]
  auth status [--show-token] [--offline]
  auth logout | token
  ui login [--hostname] [--timeout] [--headless] [--cdp-url]
  ui status | logout
  ui scrape [path] [--hostname] [--out] [--html] [--no-graphql]
             [--screenshot] [--headed] [--print]
```

`__main__.py`: `raise SystemExit(main())`
`__init__.py`: `__version__ = "0.1.0"`

### Tests (no live Lattice / no browser required)

Cover at least:

- credentials save/load/chmod/env override/clear/mask
- `get_me` success + 401 (`urllib` mocked)
- `user_display` variants
- auth login success/fail (mock `get_me`); status/logout/token; CLI login
- `looks_like_login_url` (Okta vs tenant `/home` vs `/login`)
- `session_exists` / `write_scrape_outputs`
- CLI `ui status` → 1 when no session

Target: ~20+ unit tests, `pytest` green offline.

### README (short)

Document: install `[ui]`, `playwright install chromium`, `install-deps`, headed login, CDP login, scrape flags, API auth secondary, never commit secrets/`lattice-scrape/`.

---

## Local SSO recipes (this is the blocker)

### A. Headed Playwright (preferred on laptop)

```bash
cd c3securitytools/lattice
pip install -e ".[dev,ui]"
playwright install chromium
PYTHONPATH=src python3 -m lattice ui login
PYTHONPATH=src python3 -m lattice ui scrape /home --out ./lattice-scrape --html
```

### B. System Chrome + CDP

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-lattice
# SSO to https://c3.latticehq.com in that window, then:
PYTHONPATH=src python3 -m lattice ui login --cdp-url http://127.0.0.1:9222
```

### C. Headless remote (avoid unless necessary)

Remote with no `DISPLAY` **cannot** complete SSO alone. Either run A/B on laptop, or:

```bash
# Laptop Chrome on 9222 + SSO, then:
ssh -R 9222:127.0.0.1:9222 user@remote
# On remote:
lattice ui login --cdp-url http://127.0.0.1:9222
```

### Failures already seen — don’t repeat blindly

- `libxkbcommon.so.0` missing → `playwright install-deps chromium` (fixed Chromium launch)
- `google-chrome: command not found` on remote
- `connect ECONNREFUSED 127.0.0.1:9222` — nothing listening; CDP must point at a live Chrome
- **Port 9222 taken by Cursor** (VS Code server) — use 9223 or another port
- `/home` route 404s — use `/` for authenticated home page
- GraphQL introspection disabled — cannot discover mutations via `__schema`
- Cookies alone via `urllib` get 403 — must execute GraphQL in-browser (CSRF protection)

---

## Next steps

1. [x] ~~Build MCP server with CRUD objectives~~ (done — `lattice.mcp_server`)
2. [x] ~~Discover create/delete mutations~~ (done via UI automation)
3. [ ] Publish to PyPI as `lattice-mcp` for `uvx lattice-mcp` install
   - Rename package in `pyproject.toml` from `lattice-cli` to `lattice-mcp`
   - Add `[project.scripts]` entry: `lattice-mcp = "lattice.mcp_server:mcp.run"`
   - Add `[project.gui-scripts]` or console script for `lattice` CLI
   - Register on PyPI (needs account + API token)
   - Users install with: `uvx lattice-mcp` or `pip install lattice-mcp`
4. [ ] List on [mcp.so](https://mcp.so) and/or [glama.ai/mcp](https://glama.ai/mcp) for discoverability
5. [ ] Push repo to GitHub (e.g. `github.com/sahn/lattice-mcp`)
6. [ ] Build `lattice goals` CLI command (list personal objectives with status)
7. [ ] Scrape more routes: `/updates`, `/feedback`, `/people` — map GraphQL ops
8. [ ] If org later grants API key: prefer REST (`auth` + `/v1/*`) over scrape

---

## Security

- `browser-state.json` ≡ full SSO session — secret, `0600`, never git
- Scrape dumps = HR/org PII — don’t commit `lattice-scrape/`
- Cookies ≠ API keys
- Confirm policy allows personal-SSO automation of Lattice

---

## References

- Lattice API auth: https://developers.lattice.com/reference/authentication
- `GET /v1/me`: https://developers.lattice.com/reference/api_me-1
- narwhalChat Lattice (reference): `c3engineering/repo/community/narwhalChat/src/lattice/`
- Prior remote prototype lived on branch `lattice` in `c3securitytools` — **may not exist locally; rebuild from this doc**
