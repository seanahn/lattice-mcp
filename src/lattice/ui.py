"""Playwright-based UI scraping commands (ui login, status, logout, scrape)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from lattice.credentials import (
    browser_state_path,
    config_dir,
    DEFAULT_WEB_HOSTNAME,
    WEB_HOSTNAME_ENV,
)

LOGIN_INDICATORS = (
    "login", "signin", "sign-in", "sso", "saml",
    "oauth", "okta", "auth0", "openid", "callback",
)


def _get_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        print(
            "Playwright is not installed. Install with:\n"
            "  pip install 'lattice-cli[ui]'\n"
            "  python3 -m playwright install chromium\n"
            "  python3 -m playwright install-deps chromium",
            file=sys.stderr,
        )
        return None


def looks_like_login_url(url: str, tenant_hostname: str) -> bool:
    """True if URL appears to be a login/SSO page rather than the authenticated app."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path.lower()
    full = (host + path).lower()

    if host and host != tenant_hostname:
        for indicator in LOGIN_INDICATORS:
            if indicator in host:
                return True

    for indicator in LOGIN_INDICATORS:
        if indicator in path:
            return True

    return False


def is_authenticated(url: str, tenant_hostname: str, has_cookies: bool) -> bool:
    """True if we appear to be on the authenticated tenant."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host != tenant_hostname:
        return False
    if looks_like_login_url(url, tenant_hostname):
        return False
    return has_cookies


def session_exists(config_dir_override: Optional[str] = None) -> bool:
    """Check if a browser state file exists with cookies."""
    path = browser_state_path(config_dir_override)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        cookies = data.get("cookies", [])
        return len(cookies) > 0
    except (json.JSONDecodeError, OSError):
        return False


def ui_login(
    hostname: Optional[str] = None,
    timeout: int = 300,
    headless: bool = False,
    cdp_url: Optional[str] = None,
    config_dir_override: Optional[str] = None,
) -> int:
    """Launch browser for SSO login, save storage state."""
    sync_playwright = _get_playwright()
    if not sync_playwright:
        return 1

    host = hostname or os.environ.get(WEB_HOSTNAME_ENV, DEFAULT_WEB_HOSTNAME)
    target_url = f"https://{host}"

    if not headless and not cdp_url:
        display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        if not display:
            print(
                "No DISPLAY or WAYLAND_DISPLAY set — headed SSO impossible.\n"
                "Options:\n"
                "  - Run on a machine with a display\n"
                "  - Use --cdp-url to attach to a remote Chrome\n"
                "  - Use SSH reverse tunnel: ssh -R 9222:127.0.0.1:9222 user@remote",
                file=sys.stderr,
            )
            return 1

    state_path = browser_state_path(config_dir_override)

    with sync_playwright() as p:
        try:
            if cdp_url:
                browser = p.chromium.connect_over_cdp(cdp_url)
            else:
                browser = p.chromium.launch(headless=headless)
        except Exception as e:
            print(
                f"Browser launch failed: {e}\n\n"
                "Try:\n"
                "  python3 -m playwright install-deps chromium\n"
                "  python3 -m playwright install chromium",
                file=sys.stderr,
            )
            return 1

        if cdp_url:
            contexts = browser.contexts
            context = contexts[0] if contexts else browser.new_context()
            pages = context.pages
            page = pages[0] if pages else context.new_page()
            page.goto(target_url)
        else:
            context = browser.new_context()
            page = context.new_page()
            page.goto(target_url)

        print(f"Waiting up to {timeout}s for SSO completion on {host}...")

        deadline = time.time() + timeout
        while time.time() < deadline:
            current_url = page.url
            cookies = context.cookies()
            if is_authenticated(current_url, host, len(cookies) > 0):
                break
            time.sleep(1)
        else:
            print("Timeout waiting for authentication.", file=sys.stderr)
            if not cdp_url:
                browser.close()
            return 1

        storage = context.storage_state()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(storage, indent=2))
        os.chmod(str(state_path), 0o600)

        print(f"Session saved to {state_path}")

        if not cdp_url:
            browser.close()

    return 0


def ui_status(config_dir_override: Optional[str] = None) -> int:
    """Report whether a browser session file exists with cookies."""
    if session_exists(config_dir_override):
        print("Browser session: active")
        return 0
    print("Browser session: none", file=sys.stderr)
    return 1


def ui_logout(config_dir_override: Optional[str] = None) -> int:
    """Delete browser state file."""
    path = browser_state_path(config_dir_override)
    if path.exists():
        path.unlink()
        print("Browser session removed.")
    else:
        print("No browser session to remove.")
    return 0


def write_scrape_outputs(
    out_dir: Path,
    url: str,
    title: str,
    text: str,
    graphql_responses: list,
    html: Optional[str] = None,
) -> None:
    """Write scrape output files."""
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {"url": url, "title": title}
    (out_dir / "scrape.meta.json").write_text(json.dumps(meta, indent=2))
    (out_dir / "scrape.txt").write_text(text)
    (out_dir / "scrape.graphql.json").write_text(json.dumps(graphql_responses, indent=2))

    if html is not None:
        (out_dir / "scrape.html").write_text(html)


def ui_scrape(
    path: str = "/home",
    hostname: Optional[str] = None,
    out_dir: str = "./lattice-scrape",
    capture_html: bool = False,
    no_graphql: bool = False,
    screenshot: Optional[str] = None,
    headed: bool = False,
    print_text: bool = False,
    config_dir_override: Optional[str] = None,
) -> int:
    """Load storage state, navigate, capture page content and GraphQL."""
    sync_playwright = _get_playwright()
    if not sync_playwright:
        return 1

    host = hostname or os.environ.get(WEB_HOSTNAME_ENV, DEFAULT_WEB_HOSTNAME)
    state_file = browser_state_path(config_dir_override)

    if not state_file.exists():
        print("No browser session. Run 'lattice ui login' first.", file=sys.stderr)
        return 1

    if path.startswith("http://") or path.startswith("https://"):
        target_url = path
    else:
        target_url = f"https://{host}{path}"

    graphql_responses: list = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(storage_state=str(state_file))

        if not no_graphql:
            def on_response(response):
                if "graphql" in response.url:
                    try:
                        body = response.json()
                    except Exception:
                        body = None
                    graphql_responses.append({
                        "url": response.url,
                        "status": response.status,
                        "body": body,
                    })
            context.on("response", on_response) # type: ignore[arg-type]

        page = context.new_page()
        page.goto(target_url, wait_until="networkidle")
        time.sleep(1.5)

        current_url = page.url
        if looks_like_login_url(current_url, host):
            print(
                "Redirected to login page — session may be expired. "
                "Run 'lattice ui login' again.",
                file=sys.stderr,
            )
            browser.close()
            return 1

        title = page.title()
        text = page.inner_text("body")
        html_content = page.content() if capture_html else None

        if screenshot:
            page.screenshot(path=screenshot)

        # Write refreshed cookies back so each scrape extends the stored session
        try:
            storage = context.storage_state()
            state_file.write_text(json.dumps(storage, indent=2))
            os.chmod(str(state_file), 0o600)
        except Exception:
            pass

        browser.close()

    out_path = Path(out_dir)
    write_scrape_outputs(out_path, current_url, title, text, graphql_responses, html_content)

    if print_text:
        print(text)

    print(f"Scrape complete → {out_path}/")
    return 0
