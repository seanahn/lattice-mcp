# Lattice MCP Server

Automates Lattice HR objectives (create, update, delete, list) via browser session replay. No API key required — authenticates through SSO and persists the session for headless Playwright reuse.

## Prerequisites

- Python 3.10+
- Chrome/Chromium (for SSO login)
- A display environment (local machine or X-forwarded) for initial login

## Installation

```bash
pip install lattice-mcp
playwright install chromium
```


## Authentication

The server uses a saved Playwright browser session (`~/.config/lattice/browser-state.json`). You must log in once via SSO to create it.

### Option A: Local machine with a display

```bash
lattice ui login --hostname <your-company>.latticehq.com
```

A Chromium window opens — complete your SSO login. The window closes automatically once authenticated and the session is saved. The session is reusable until it expires on Lattice's side (typically days to weeks).

### Option B: Headless server (attach to running Chrome)

```bash
# On a machine with a display, start Chrome with remote debugging:
google-chrome --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-lattice --no-first-run &

# Complete SSO in that browser, then capture the session:
lattice ui login --cdp-url http://127.0.0.1:9223
```

### Session expiry

If tools return "Session expired", re-run `lattice ui login`.

## Configuration

All configuration is via environment variables — no code changes needed to point at your own Lattice tenant:

| Variable | Purpose | Default |
|----------|---------|---------|
| `LATTICE_WEB_HOSTNAME` | Your Lattice tenant, e.g. `acme.latticehq.com` | `c3.latticehq.com` |
| `LATTICE_USER_ENTITY_ID` | Your Lattice user entity UUID — the default owner for `lattice_objectives` | unset (tools require an explicit `owner_id`) |
| `LATTICE_CONFIG_DIR` | Where credentials and the browser session are stored | `~/.config/lattice` |

`lattice ui login` also accepts `--hostname` directly (takes precedence over the env var). The hostname is **not** saved with the session — the MCP server re-reads `LATTICE_WEB_HOSTNAME` on every call, so set it wherever the server is launched (see below).

To find your user entity ID: open any Lattice page filtered to your objectives and copy the UUID from the URL (`ownerEntityIdsFilter=...`), or inspect a GraphQL response in your browser's devtools.

## MCP Server Setup (Claude Code)

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "lattice": {
      "command": "lattice-mcp",
      "env": {
        "LATTICE_WEB_HOSTNAME": "<your-company>.latticehq.com",
        "LATTICE_USER_ENTITY_ID": "<your-user-entity-uuid>"
      }
    }
  }
}
```

Restart Claude Code to load the server. The tools appear as `lattice_*` in your session.

## Available Tools

| Tool | Description |
|------|-------------|
| `lattice_session_status` | Check if the browser session is active |
| `lattice_objectives` | List active objectives for a user (defaults to you) |
| `lattice_create_objective` | Create a new objective (title, optional priority/due date) |
| `lattice_update_objective` | Post a status update + comment to an objective |
| `lattice_delete_objective` | Delete an objective by entityId |
| `lattice_scrape` | Scrape any Lattice page and return visible text |

### Example usage (via Claude Code)

```
> list my lattice objectives
> create a lattice objective titled "Ship feature X"
> update objective <entityId> status green comment "Merged PR, deploying tomorrow"
> delete objective <entityId>
```

### Multi-server workflow (with Jira MCP)

If you also have a Jira MCP server in your session, you can chain them:

```
> fetch PLAT-0000 and PLAT-0001 from jira, then create lattice objectives from their summaries
```

Claude calls the Jira server to get ticket details, then calls `lattice_create_objective` for each — no glue code needed.

## How It Works

1. Tools launch headless Chromium with the saved session cookies
2. Navigate to the relevant Lattice page
3. Interact with the UI (fill forms, click buttons) via Playwright
4. GraphQL mutations fire as a side-effect of the UI interaction
5. Cloudflare passes because the session includes valid clearance cookies

There is no direct API access — Lattice does not issue API keys to non-admins. See `DESIGN.md` for the full decision log.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No browser session" | Run `lattice ui login` |
| "Session expired" | Re-run `lattice ui login` |
| Cloudflare blocks (403) | Session stale — re-login to get fresh `cf_clearance` cookies |
| Tool times out | Lattice page may be slow; try again |
| Create succeeds but objective not visible | Check the "All time" filter on `/goals` — it may default to current quarter |
