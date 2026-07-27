"""MCP server exposing Lattice tools."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from lattice.credentials import (
    browser_state_path,
    config_dir,
    DEFAULT_WEB_HOSTNAME,
    WEB_HOSTNAME_ENV,
)
from lattice.ui import (
    looks_like_login_url,
    is_authenticated,
    session_exists,
)

mcp = FastMCP(
    "Lattice",
    instructions="Lattice HR automation — objectives, updates, scraping",
)

# --- Helpers ---

CHROMIUM_MISSING = (
    "Chromium browser not found. Run: playwright install chromium"
)


async def _launch_browser(p):
    try:
        return await p.chromium.launch(headless=True)
    except Exception as e:
        if "executable doesn't exist" in str(e).lower() or "browsertype.launch" in str(e).lower():
            raise RuntimeError(CHROMIUM_MISSING) from e
        raise


async def _save_session(context) -> None:
    """Write refreshed cookies back to disk so activity extends the stored session.

    Servers rotate/extend session cookies via Set-Cookie during a visit;
    without this write-back the stored state keeps the original cookies and
    ages toward expiry no matter how often the tools are used.
    """
    try:
        state_path = browser_state_path()
        storage = await context.storage_state()
        state_path.write_text(json.dumps(storage, indent=2))
        os.chmod(str(state_path), 0o600)
    except Exception:
        pass  # never fail the calling tool over a keepalive write


async def _scrape_page_graphql(path: str) -> tuple[str, list[dict]]:
    """Scrape a Lattice page and return (page_text, graphql_responses)."""
    from playwright.async_api import async_playwright

    state_file = str(browser_state_path())
    if not Path(state_file).exists():
        raise RuntimeError("No browser session. Call the lattice_ui_login tool (or run 'lattice ui login') first.")

    host = os.environ.get(WEB_HOSTNAME_ENV, DEFAULT_WEB_HOSTNAME)

    if path.startswith("http"):
        target_url = path
    else:
        target_url = f"https://{host}{path}"

    graphql_responses: list[dict] = []

    async with async_playwright() as p:
        browser = await _launch_browser(p)
        context = await browser.new_context(storage_state=state_file)

        async def on_response(response):
            if "graphql" in response.url and "latticehq.com" in response.url:
                try:
                    body = await response.json()
                    graphql_responses.append({
                        "url": response.url,
                        "status": response.status,
                        "body": body,
                    })
                except Exception:
                    pass

        context.on("response", on_response)
        page = await context.new_page()
        await page.goto(target_url, wait_until="networkidle")
        await asyncio.sleep(1.5)

        current_url = page.url
        if looks_like_login_url(current_url, host):
            await browser.close()
            raise RuntimeError("Session expired. Call the lattice_ui_login tool (or run 'lattice ui login') to re-authenticate.")

        text = await page.inner_text("body")
        await _save_session(context)
        await browser.close()

    return text, graphql_responses


# --- Lattice Tools ---

USER_ENTITY_ID_ENV = "LATTICE_USER_ENTITY_ID"
USER_ENTITY_ID = os.environ.get(USER_ENTITY_ID_ENV, "")


@mcp.tool()
async def lattice_session_status() -> str:
    """Check if Lattice browser session is active."""
    if session_exists():
        return "Session active."
    return "No session. Call the lattice_ui_login tool, or run: lattice ui login --cdp-url http://127.0.0.1:9223 (after starting Chrome with --remote-debugging-port=9223)"


@mcp.tool()
async def lattice_ui_login(timeout: int = 240) -> str:
    """Open a browser window for SSO login to create or refresh the Lattice session.

    Call this when other tools return "Session expired" or "No browser
    session". Tries a silent headless refresh first (succeeds with no user
    interaction while the stored IdP session cookies are still valid). If
    that fails, falls back to opening a Chromium window on the user's
    display — tell the user first: they must complete the SSO login in it.
    Blocks until login finishes or `timeout` seconds elapse.
    """
    # Silent headless refresh: reuses stored IdP cookies, no interaction.
    if Path(str(browser_state_path())).exists():
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "lattice",
            "ui",
            "login",
            "--headless",
            "--timeout",
            "90",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=150)
            if proc.returncode == 0:
                return "Session refreshed silently — no user interaction was needed."
        except asyncio.TimeoutError:
            proc.kill()

    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return (
            "Error: no display available — cannot open a login window. "
            "Ask the user to run 'lattice ui login --cdp-url ...' manually "
            "(see README for headless options)."
        )

    # ui_login() uses sync Playwright and prints to stdout, so run the CLI
    # as a subprocess to keep the MCP stdio channel clean.
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "lattice",
        "ui",
        "login",
        "--timeout",
        str(timeout),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 60)
    except asyncio.TimeoutError:
        proc.kill()
        return "Error: timed out waiting for SSO completion."

    text = out.decode(errors="replace").strip()
    if proc.returncode == 0:
        return (
            "Login successful — session saved. Retry the previous operation.\n"
            + _notify_subscription_info()
        )
    return f"Login failed (exit {proc.returncode}): {text[-500:]}"


def _notify_subscription_info() -> str:
    """Topic/URL/QR-file info to relay after a manual login."""
    from lattice import notify

    topic = notify.resolve_topic(create=True)
    server = notify.resolve_server()
    url = f"{server}/{topic}"
    qr_path = notify.save_qr_txt(url)
    lines = [
        f"Phone alerts topic: {topic}",
        f"Subscribe: {url}",
    ]
    if qr_path:
        lines.append(
            f"Scannable QR: {qr_path} — display it to the user verbatim "
            f"(e.g. cat that file; do not summarize it)."
        )
    lines.append(
        "Relay the topic name and Subscribe URL to the user verbatim so they "
        "can add it in the ntfy app."
    )
    return "\n".join(lines)


@mcp.tool()
async def lattice_notify(message: str, title: str = "") -> str:
    """Send a push notification to the user's phone via ntfy.

    Uses the per-user topic from LATTICE_NTFY_TOPIC or the config file
    (generated on first use). Use for alerts and completion notices,
    especially in scheduled/headless runs where the user isn't watching.
    """
    from lattice import notify

    existing = notify.resolve_topic()
    rc = await asyncio.to_thread(notify.send, message, title or None)
    if rc != 0:
        return "Error: failed to send notification (see server log for details)."
    if existing is None:
        topic = notify.resolve_topic()
        return (
            f"Notification sent, but the topic '{topic}' was just generated — "
            "nobody may be subscribed to it yet. Show the user the subscription "
            "info: topic name, URL (run 'lattice notify --show'), so they can "
            "subscribe in the ntfy app."
        )
    return "Notification sent."


@mcp.tool()
async def lattice_objectives(owner_id: str = USER_ENTITY_ID) -> str:
    """List Lattice objectives for a user (defaults to $LATTICE_USER_ENTITY_ID).

    Returns objectives with title, status, progress, due date, and priority.
    """
    if not owner_id:
        return (
            "Error: no owner_id given and LATTICE_USER_ENTITY_ID is not set. "
            "Pass owner_id or set the environment variable."
        )
    filter_path = (
        f'/goals/explore?ownerEntityIdsFilter=%5B%22{owner_id}%22%5D'
        f'&statusesFilter=%5B%22AllActive%22%5D&viewType=cascade'
    )

    _text, gql_responses = await _scrape_page_graphql(filter_path)

    objectives = []
    seen_ids = set()
    for r in gql_responses:
        body = r.get("body", {})
        if not isinstance(body, dict):
            continue
        viewer = body.get("data", {}).get("viewer", {})
        goals = viewer.get("goals", {})
        edges = goals.get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            if node.get("name") and node.get("entityId") not in seen_ids:
                seen_ids.add(node.get("entityId"))
                progress = node.get("computedProgressAmount")
                objectives.append({
                    "entityId": node.get("entityId"),
                    "title": node.get("name"),
                    "priority": f"P{node.get('priority')}" if node.get("priority") else None,
                    "status": node.get("status") or "no update",
                    "progress": f"{int(progress * 100)}%" if progress else "0%",
                    "dueDate": node.get("dueDate"),
                    "owners": [o.get("name") for o in node.get("owners", [])],
                })

    if not objectives:
        return "No active objectives found for this user."

    return json.dumps(objectives, indent=2)


@mcp.tool()
async def lattice_update_objective(
    goal_entity_id: str,
    comment: str,
    status: str = "green",
) -> str:
    """Post an update to a Lattice objective.

    Args:
        goal_entity_id: UUID of the objective (entityId)
        comment: Update text to post
        status: "green" (On track), "amber" (Progressing), or "red" (Off track)
    """
    from playwright.async_api import async_playwright

    state_file = str(browser_state_path())
    if not Path(state_file).exists():
        return "Error: No browser session. Call the lattice_ui_login tool (or run 'lattice ui login') first."

    host = os.environ.get(WEB_HOSTNAME_ENV, DEFAULT_WEB_HOSTNAME)
    goal_url = f"https://{host}/goals/{goal_entity_id}"

    status_index = {"green": 0, "amber": 1, "red": 2, "complete": 3, "incomplete": 4}
    idx = status_index.get(status, 0)

    requests_log: list[dict] = []

    async with async_playwright() as p:
        browser = await _launch_browser(p)
        context = await browser.new_context(storage_state=state_file)

        def on_request(request):
            if "graphql" in request.url and request.method == "POST":
                try:
                    requests_log.append(json.loads(request.post_data))
                except Exception:
                    pass

        page = await context.new_page()
        page.on("request", on_request)

        await page.goto(goal_url, wait_until="networkidle")
        await asyncio.sleep(2)

        if looks_like_login_url(page.url, host):
            await browser.close()
            return "Error: Session expired. Call the lattice_ui_login tool (or run 'lattice ui login') to re-authenticate."

        # Click first visible "Update" button to open the form
        update_buttons = [
            b
            for b in await page.query_selector_all("button:has-text('Update')")
            if await b.is_visible()
        ]
        if not update_buttons:
            await browser.close()
            return "Error: Could not find Update button on goal page."
        await update_buttons[0].click()
        await asyncio.sleep(2)

        # Select status radio
        radios = await page.query_selector_all("[role='radio']")
        if radios and idx < len(radios):
            await radios[idx].click()
            await asyncio.sleep(0.5)

        # Type comment (first visible textbox)
        textbox = None
        for t in await page.query_selector_all(
            "[contenteditable='true'], [role='textbox'], textarea"
        ):
            if await t.is_visible():
                textbox = t
                break
        if textbox:
            await textbox.click()
            await asyncio.sleep(0.2)
            await page.keyboard.type(comment, delay=2)
            await asyncio.sleep(0.5)

        # Clear logs before submit
        requests_log.clear()

        # Click submit (last visible "Update" button)
        update_buttons = [
            b
            for b in await page.query_selector_all("button:has-text('Update')")
            if await b.is_visible()
        ]
        if len(update_buttons) >= 2:
            await update_buttons[-1].click()
        else:
            await browser.close()
            return "Error: Could not find submit button."

        await asyncio.sleep(4)
        await _save_session(context)
        await browser.close()

    if requests_log:
        return f"Update posted successfully. Status: {status}, comment length: {len(comment)} chars."
    return "Warning: Update button clicked but no GraphQL request detected. Check Lattice to verify."


@mcp.tool()
async def lattice_create_objective(
    title: str,
    due_date: str = "",
    priority: str = "P1",
) -> str:
    """Create a new Lattice objective.

    Args:
        title: Objective title text
        due_date: Due date in YYYY-MM-DD format (optional)
        priority: "P1", "P2", or "P3" (default P1)
    """
    from playwright.async_api import async_playwright

    state_file = str(browser_state_path())
    if not Path(state_file).exists():
        return "Error: No browser session. Call the lattice_ui_login tool (or run 'lattice ui login') first."

    host = os.environ.get(WEB_HOSTNAME_ENV, DEFAULT_WEB_HOSTNAME)
    create_url = f"https://{host}/goals/create/objective"

    async with async_playwright() as p:
        browser = await _launch_browser(p)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        await page.goto(create_url, wait_until="networkidle")
        await asyncio.sleep(2)

        if looks_like_login_url(page.url, host):
            await browser.close()
            return "Error: Session expired. Call the lattice_ui_login tool (or run 'lattice ui login') to re-authenticate."

        # Fill title using keyboard.type() to trigger React onChange
        title_input = await page.query_selector("#name")
        if not title_input:
            title_input = await page.query_selector("form input[type='text']")
        if title_input:
            await title_input.click()
            await asyncio.sleep(0.2)
            await page.keyboard.type(title, delay=10)
            await asyncio.sleep(0.5)
        else:
            await browser.close()
            return "Error: Could not find title input on create objective form."

        # Submit via JS click (Playwright .click() doesn't trigger React form submit)
        submitted = await page.evaluate("""() => {
            const btn = document.querySelector('button[type="submit"]');
            if (btn && !btn.disabled) { btn.click(); return true; }
            return false;
        }""")
        if not submitted:
            await browser.close()
            return "Error: Could not find or click Publish objective button."

        await asyncio.sleep(5)
        await _save_session(context)
        await browser.close()

    return f"Objective created: \"{title}\""


@mcp.tool()
async def lattice_delete_objective(goal_entity_id: str) -> str:
    """Delete a Lattice objective.

    Args:
        goal_entity_id: UUID of the objective (entityId) to delete
    """
    from playwright.async_api import async_playwright

    state_file = str(browser_state_path())
    if not Path(state_file).exists():
        return "Error: No browser session. Call the lattice_ui_login tool (or run 'lattice ui login') first."

    host = os.environ.get(WEB_HOSTNAME_ENV, DEFAULT_WEB_HOSTNAME)
    goal_url = f"https://{host}/goals/{goal_entity_id}"

    async with async_playwright() as p:
        browser = await _launch_browser(p)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        await page.goto(goal_url, wait_until="networkidle")
        await asyncio.sleep(2)

        if looks_like_login_url(page.url, host):
            await browser.close()
            return "Error: Session expired. Call the lattice_ui_login tool (or run 'lattice ui login') to re-authenticate."

        # Click overflow/kebab menu button
        overflow_btn = await page.query_selector("button:has-text('Overflow Icon')")
        if not overflow_btn:
            await browser.close()
            return "Error: Could not find overflow menu on goal page."

        await overflow_btn.click()
        await asyncio.sleep(1)

        # Click "Delete" in the dropdown menu
        delete_btn = await page.query_selector("button:has-text('Trash IconDelete')")
        if not delete_btn:
            delete_btn = await page.query_selector("button:has-text('Delete')")
        if not delete_btn:
            await browser.close()
            return "Error: Could not find Delete option in menu."

        await delete_btn.click()
        await asyncio.sleep(2)

        # Confirm deletion — button text is "Delete N Objectives"
        confirm_btn = await page.query_selector("button:has-text('Delete 1 Objectives')")
        if not confirm_btn:
            confirm_btn = await page.query_selector("button:has-text('Delete')")
        if confirm_btn:
            await confirm_btn.click()
            await asyncio.sleep(3)

        # Check if navigated away (success indicator)
        url_after = page.url
        await _save_session(context)
        await browser.close()

    if goal_entity_id not in url_after:
        return f"Objective {goal_entity_id} deleted successfully."
    return "Warning: Delete attempted but page did not navigate away. Check Lattice to verify."


@mcp.tool()
async def lattice_scrape(path: str = "/") -> str:
    """Scrape any Lattice page and return the visible text.

    Args:
        path: URL path (e.g. "/goals", "/grow") or full URL
    """
    text, _gql = await _scrape_page_graphql(path)
    if len(text) > 10000:
        text = text[:10000] + "\n\n... (truncated)"
    return text


def run():
    mcp.run()


if __name__ == "__main__":
    run()
