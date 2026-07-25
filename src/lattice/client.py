"""Lattice API client (stdlib urllib only)."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional


class LatticeAPIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"HTTP {status}: {message}")


def get_me(api_url: str, token: str) -> dict:
    """GET {api_url}/v1/me with Bearer auth."""
    url = f"{api_url.rstrip('/')}/v1/me"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()
        except Exception:
            pass
        raise LatticeAPIError(e.code, body or e.reason) from e


def user_display(user: Optional[dict]) -> str:
    """Human-readable name + email from a /v1/me user dict."""
    if not user:
        return "(unknown)"

    name_parts = []
    preferred = user.get("preferredName")
    if preferred:
        name_parts.append(preferred)
    else:
        first = user.get("firstName", "")
        last = user.get("lastName", "")
        if first or last:
            name_parts.append(f"{first} {last}".strip())

    email = user.get("workEmail") or user.get("email", "")
    if name_parts and email:
        return f"{' '.join(name_parts)} <{email}>"
    if name_parts:
        return " ".join(name_parts)
    if email:
        return email
    return "(unknown)"
