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
lattice ui login [--hostname <your-company>.latticehq.com]
```

If `--hostname` is omitted, it falls back to the `LATTICE_WEB_HOSTNAME` environment variable (see [Configuration](#configuration)).

A Chromium window opens — complete your SSO login. The window closes automatically once authenticated and the session is saved. The session is reusable until it expires on Lattice's side (typically days to weeks).

### Option B: Headless server (attach to running Chrome)

```bash
# On a machine with a display, start Chrome with remote debugging:
google-chrome --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-lattice --no-first-run &

# Complete SSO in that browser, then capture the session:
lattice ui login --cdp-url http://127.0.0.1:9223
```

### Option C: Silent headless re-login (after first login)

```bash
lattice ui login --headless
```

Reuses the stored browser state: even if the Lattice session has expired, the saved IdP session cookies (e.g. Microsoft Entra) usually allow the SSO to complete silently — no window, no password, no MFA. Works until the IdP's own session expires (often weeks), then fall back to Option A/B. Whether the silent hop is permitted depends on your IdP tenant's conditional-access policies.

### Session expiry

If tools return "Session expired", re-run `lattice ui login` — or let the agent call the `lattice_ui_login` MCP tool, which tries the silent headless refresh first and only opens a login window if that fails (you complete the SSO yourself).

## Configuration

All configuration is via environment variables — no code changes needed to point at your own Lattice tenant:

| Variable | Purpose | Default |
|----------|---------|---------|
| `LATTICE_WEB_HOSTNAME` | Your Lattice tenant, e.g. `acme.latticehq.com` | `c3.latticehq.com` |
| `LATTICE_USER_ENTITY_ID` | Your Lattice user entity UUID — the default owner for `lattice_objectives` | unset (tools require an explicit `owner_id`) |
| `LATTICE_CONFIG_DIR` | Where credentials and the browser session are stored | `~/.config/lattice` |

`lattice ui login` also accepts `--hostname` directly (takes precedence over the env var). The hostname is **not** saved with the session — the MCP server re-reads `LATTICE_WEB_HOSTNAME` on every call, so set it wherever the server is launched (see below).

To find your user entity ID: open any Lattice page filtered to your objectives and copy the UUID from the URL (`ownerEntityIdsFilter=...`), or inspect a GraphQL response in your browser's devtools.

## Notifications (ntfy)

Cron jobs and agents can push alerts to your phone via [ntfy](https://ntfy.sh):

```bash
lattice notify --setup          # generate your personal topic + show subscribe info (QR)
lattice notify --test           # send a test push
lattice notify "message" --title "optional title"
lattice notify --show           # re-print topic / URL / QR anytime
```

The first use generates a per-user topic like `lattice-<user>-<random12>` and stores it in `~/.config/lattice/config.json`. **The random suffix is the secret** — on public ntfy servers the topic name is the only access control, so don't shorten it or share it.

A successful manual `lattice ui login` shows the subscription info (topic, URL, QR) automatically, so new users see it at onboarding without a separate step. The ASCII QR is also saved to `~/.config/lattice/ntfy-qr.txt` for when the terminal output isn't usable (e.g. agent-mediated setup — open the file in any editor and scan it). If a send auto-generates a topic (nothing configured yet), it prints a warning that nobody is subscribed.

Overrides (env beats config file):

| | env | config.json key | default |
|---|---|---|---|
| Topic | `LATTICE_NTFY_TOPIC` | `ntfy_topic` | generated on first use |
| Server | `LATTICE_NTFY_SERVER` | `ntfy_server` | `https://ntfy.sh` |

Install the `qr` extra (`pip install lattice-mcp[qr]`) for a scannable terminal QR code during setup:

```
$ lattice notify --show

  Topic:  lattice-example-abc123xyz789
  URL:    https://ntfy.sh/lattice-example-abc123xyz789

  █▀▀▀▀▀▀▀████▀▀▀██▀▀▀▀▀█▀▀██▀▀▀▀▀▀▀█
  █ █▀▀▀█ █▀▄▀▄█ ▄ █ ▀█▄█▄▀▄█ █▀▀▀█ █
  █ █   █ █ █ ▄ ▀▄ ▄█▀▄▄ ▄▄ █ █   █ █
  █ ▀▀▀▀▀ █ ▄▀▄ █ ▄ ▄ █ █▀█▀█ ▀▀▀▀▀ █
  █▀█▀▀▀▀▀█▄█ █▄▀▀ ▀▀███▄ ▀ █▀▀▀▀▀███
  █ ▄█ ▄ ▀▄  ▀█ ██▀ █ ▄▄ █▄▄█ ▄▀▄ ▀▄█
  █▄▄█▄█▀▀   ▀▄ █▄▄▄█▀█▄ ▄▀▄▀██  ▄▄██
  █ ▄▀ ▄ ▀ █ ▀ ▀▀ ▄▄██▀▄▀▄▄   █▀█▄ ▄█
  █▀██▀ ▀▀▀▄▄  █▄ █▄▀▀  ▄█▀▄ ▄ ▀▄▄█▀█
  █▄█▀▄ ▄▀ ▀  █▄▄▀▀  ▄▄▄█▀▄▀█  ▀▄ ▀▄█
  █▀█▄ ▄▀▀ ▄▄▀█ █  ▀▄▄█ ▀▀▄█ █▄  ▄ ▀█
  █ █▄ ▀ ▀ ▀▄▀  ▄█ ▀▄▄█▀█▀▄▄   ▀▀▄▀▄█
  █ █▀ ▀ ▀▀▄▄▄  ▀█ █▀██▀▄ ▄▀▀  ▀▀▄▀▀█
  █▀▀▀▀▀▀▀█▄▀▄█  ▄▀▄█ ▄  █▀ █▀█ █ █▄█
  █ █▀▀▀█ █ ▀███▄ ▄██▀██ ▄▄ ▀▀▀  ▄ ██
  █ █   █ █  ▄▄█▀█▄▄██▀▄▀ ▀  ▀▀▄▀ █▄█
  █ ▀▀▀▀▀ █▀ ██  ▀█ ▀█ ▄▄▀▄▀█ ▀▄▀▄▀██
  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀

  Scan with your phone to subscribe in the ntfy app.
```

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
| `lattice_ui_login` | Open a browser window for SSO login (requires a display; the user completes the login) |
| `lattice_notify` | Send a push notification to the user via ntfy |
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

## Scheduled Automation (cron)

You can run headless Claude on a schedule to automate recurring Lattice tasks — e.g. posting weekly objective updates sourced from Jira tickets every Friday.

### Prerequisites

- Claude Code CLI installed and authenticated on the machine
- `lattice-mcp` installed (`pipx install lattice-mcp[qr]` + `playwright install chromium`)
- Initial login done once: `lattice ui login`
- ntfy set up: `lattice notify --setup` (scan QR on your phone)
- Your project's `.mcp.json` includes the `lattice` server (and `jira` if you want cross-referencing)

### Example: weekly objective update from Jira

1. Write a prompt file (e.g. `~/.config/lattice/weekly-update.md`):

```markdown
Post my weekly Lattice objective updates (it's Friday).

1. Call lattice_objectives to list my active objectives.
2. For each objective, call lattice_scrape on /goals/<entityId> to read its current state.
3. Fetch my in-progress Jira tickets with jira_search (assignee = currentUser(), status = "In Progress").
4. For each objective, compose a brief status comment (2-4 sentences) referencing relevant Jira progress.
5. Post each comment with lattice_update_objective, keeping the current status color.
6. Call lattice_notify with a summary of what was posted.
7. If any tool returns "Session expired": do NOT attempt login (nobody may be at the machine).
   Instead call lattice_notify with "Lattice weekly update FAILED — session expired. Run: lattice ui login"
   and stop.
```

2. Add a cron entry (`crontab -e`):

```
47 7 * * 5 cd /path/to/your/project && claude -p "$(cat ~/.config/lattice/weekly-update.md)" --allowedTools "mcp__lattice__*,mcp__jira__*" >> ~/lattice-weekly.log 2>&1
```

- `cd /path/to/your/project` — must contain the `.mcp.json` that registers lattice (and jira)
- `--allowedTools` — restricts Claude to only MCP tools (no shell access needed)
- Friday 7:47 AM — adjust to run before your company's bot checks for updates

### Session maintenance

The Lattice session expires after hours/days, but **silent headless re-login** recovers it automatically whenever you (or an agent) next use a lattice tool interactively. The stored IdP cookies (e.g. Microsoft Entra, ~90-day rolling window) allow SSO to complete without interaction.

As long as you use Lattice at least once every ~80 days (the weekly cron counts — any interactive session triggers a re-login if needed), the chain stays warm indefinitely. If the IdP session eventually expires, you'll get an ntfy alert telling you to run `lattice ui login` once.

### Without Jira

Drop the Jira steps from the prompt and `mcp__jira__*` from `--allowedTools`. The agent will just continue the narrative from the existing objective notes:

```
47 7 * * 5 cd /path/to/your/project && claude -p "$(cat ~/.config/lattice/weekly-update.md)" --allowedTools "mcp__lattice__*" >> ~/lattice-weekly.log 2>&1
```

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
