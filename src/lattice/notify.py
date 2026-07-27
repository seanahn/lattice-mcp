"""ntfy push notifications — per-user topic, config- and env-overridable.

Resolution order for the topic: LATTICE_NTFY_TOPIC env var, then
"ntfy_topic" in <config_dir>/config.json, then (when created on demand)
a generated "lattice-<user>-<random12>" topic persisted to config.json.
The random suffix is the secret — on public ntfy servers the topic name
is the only access control.
"""

from __future__ import annotations

import json
import os
import secrets
import string
import sys
import urllib.request
from pathlib import Path
from typing import Optional

from lattice.credentials import config_dir

NTFY_TOPIC_ENV = "LATTICE_NTFY_TOPIC"
NTFY_SERVER_ENV = "LATTICE_NTFY_SERVER"
DEFAULT_NTFY_SERVER = "https://ntfy.sh"


def config_path(config_dir_override: Optional[str] = None) -> Path:
    return config_dir(config_dir_override) / "config.json"


def load_config(config_dir_override: Optional[str] = None) -> dict:
    p = config_path(config_dir_override)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_config(cfg: dict, config_dir_override: Optional[str] = None) -> Path:
    p = config_path(config_dir_override)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2) + "\n")
    os.chmod(str(p), 0o600)
    return p


def generate_topic() -> str:
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "user"
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(12))
    return f"lattice-{user}-{suffix}"


def resolve_topic(
    config_dir_override: Optional[str] = None, create: bool = False
) -> Optional[str]:
    env = os.environ.get(NTFY_TOPIC_ENV)
    if env:
        return env
    cfg = load_config(config_dir_override)
    topic = cfg.get("ntfy_topic")
    if topic:
        return str(topic)
    if create:
        topic = generate_topic()
        cfg["ntfy_topic"] = topic
        save_config(cfg, config_dir_override)
        return topic
    return None


def resolve_server(config_dir_override: Optional[str] = None) -> str:
    env = os.environ.get(NTFY_SERVER_ENV)
    if env:
        return env.rstrip("/")
    cfg = load_config(config_dir_override)
    return str(cfg.get("ntfy_server", DEFAULT_NTFY_SERVER)).rstrip("/")


def send(
    message: str,
    title: Optional[str] = None,
    config_dir_override: Optional[str] = None,
) -> int:
    existing = resolve_topic(config_dir_override)
    topic = existing or resolve_topic(config_dir_override, create=True)
    if existing is None:
        print(
            f"Warning: generated new notification topic '{topic}' — nobody may be "
            "subscribed to it yet. Run 'lattice notify --show' and subscribe your "
            "phone, or this and future alerts will go unseen.",
            file=sys.stderr,
        )
    server = resolve_server(config_dir_override)
    req = urllib.request.Request(
        f"{server}/{topic}", data=message.encode("utf-8"), method="POST"
    )
    if title:
        req.add_header("Title", title)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if 200 <= resp.status < 300:
                return 0
            print(f"ntfy returned HTTP {resp.status}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Failed to send notification: {e}", file=sys.stderr)
        return 1


def save_qr_txt(url: str, config_dir_override: Optional[str] = None) -> Optional[Path]:
    """Save the ASCII QR to a text file next to the config; returns the path.

    Plain text renders scannable in any editor's monospace view — the
    reliable fallback when the terminal QR is truncated or mangled
    (e.g. agent-mediated setup, where tool output gets summarized).
    """
    try:
        import io

        import qrcode
    except ImportError:
        return None
    try:
        qr = qrcode.QRCode(border=2)
        qr.add_data(url)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
        path = config_dir(config_dir_override) / "ntfy-qr.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{url}\n\n{buf.getvalue()}")
        return path
    except Exception:
        return None


def _print_qr(url: str) -> None:
    try:
        import qrcode
    except ImportError:
        print("  (for a scannable QR code: pip install qrcode)")
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    needed = qr.modules_count + 4
    try:
        cols = os.get_terminal_size().columns
    except OSError:
        cols = 80
    if cols < needed:
        print("  (terminal too narrow for QR — use the URL above)")
        return
    qr.print_ascii(invert=True)


def show(config_dir_override: Optional[str] = None, create: bool = False) -> int:
    topic = resolve_topic(config_dir_override, create=create)
    if not topic:
        print(
            "No notification topic configured. Run: lattice notify --setup",
            file=sys.stderr,
        )
        return 1
    server = resolve_server(config_dir_override)
    url = f"{server}/{topic}"
    source = (
        f"env ${NTFY_TOPIC_ENV}"
        if os.environ.get(NTFY_TOPIC_ENV)
        else str(config_path(config_dir_override))
    )
    print(f"Notification topic: {topic}")
    print(f"  Source: {source}")
    print(f"  Web:    {url}")
    print("  Phone:  ntfy app → + → enter the topic name, or scan:")
    _print_qr(url)
    qr_path = save_qr_txt(url, config_dir_override)
    if qr_path:
        print(f"  QR file:  {qr_path}  (open + scan if the QR above doesn't render)")
    print(
        "  Agents: relay the topic name and Web URL above to the user verbatim —"
        " ASCII QR codes don't survive summarization."
    )
    return 0
