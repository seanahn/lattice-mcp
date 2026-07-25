"""API-key authentication commands (login, status, logout, token)."""

from __future__ import annotations

import getpass
import sys
import webbrowser
from typing import Optional

from lattice import credentials
from lattice.client import get_me, user_display, LatticeAPIError


def login(
    token: Optional[str] = None,
    hostname: Optional[str] = None,
    api_url: Optional[str] = None,
    no_browser: bool = False,
    config_dir: Optional[str] = None,
) -> int:
    """Authenticate with an API token. Returns 0 on success, 1 on failure."""
    host = hostname or credentials.DEFAULT_WEB_HOSTNAME
    url = api_url or credentials.DEFAULT_API_URL

    if not no_browser:
        try:
            webbrowser.open(f"https://{host}/admin")
        except Exception:
            pass

    if not token:
        token = getpass.getpass("Paste API token: ").strip()

    if not token:
        print("No token provided.", file=sys.stderr)
        return 1

    try:
        user = get_me(url, token)
    except LatticeAPIError as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1

    creds = credentials.Credentials(
        token=token,
        api_url=url,
        web_hostname=host,
        user=user,
    )
    credentials.save(creds, config_dir)
    print(f"Logged in as {user_display(user)}")
    return 0


def status(
    show_token: bool = False,
    offline: bool = False,
    config_dir: Optional[str] = None,
) -> int:
    """Show current auth status. Returns 0 if authenticated, 1 otherwise."""
    creds = credentials.load(config_dir)
    if not creds:
        print("Not authenticated.", file=sys.stderr)
        return 1

    if not offline:
        try:
            user = get_me(creds.api_url, creds.token)
            creds.user = user
            credentials.save(creds, config_dir)
        except LatticeAPIError as e:
            print(f"Token invalid or expired: {e}", file=sys.stderr)
            return 1

    display = user_display(creds.user)
    print(f"Authenticated: {display}")
    if show_token:
        print(f"Token: {creds.masked_token()}")
    return 0


def logout(config_dir: Optional[str] = None) -> int:
    """Remove stored credentials."""
    removed = credentials.clear(config_dir)
    if removed:
        print("Logged out.")
    else:
        print("No credentials to remove.")
    return 0


def token(config_dir: Optional[str] = None) -> int:
    """Print raw token to stdout."""
    creds = credentials.load(config_dir)
    if not creds:
        print("Not authenticated.", file=sys.stderr)
        return 1
    print(creds.token)
    return 0
