"""Credential storage and retrieval for Lattice CLI."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_WEB_HOSTNAME = "c3.latticehq.com"
DEFAULT_API_URL = "https://api.latticehq.com"
CONFIG_DIR_ENV = "LATTICE_CONFIG_DIR"
TOKEN_ENV_VARS = ("LATTICE_API_TOKEN", "LATTICE_TOKEN")
API_URL_ENV = "LATTICE_API_URL"
WEB_HOSTNAME_ENV = "LATTICE_WEB_HOSTNAME"

CREDENTIALS_FILE = "credentials.json"
BROWSER_STATE_FILE = "browser-state.json"


@dataclass
class Credentials:
    token: str
    api_url: str = DEFAULT_API_URL
    web_hostname: str = DEFAULT_WEB_HOSTNAME
    user: dict = field(default_factory=dict)

    def masked_token(self) -> str:
        if len(self.token) <= 8:
            return "****"
        return self.token[:4] + "..." + self.token[-4:]


def config_dir(override: Optional[str] = None) -> Path:
    if override:
        return Path(override)
    env = os.environ.get(CONFIG_DIR_ENV)
    if env:
        return Path(env)
    return Path.home() / ".config" / "lattice"


def credentials_path(config_dir_override: Optional[str] = None) -> Path:
    return config_dir(config_dir_override) / CREDENTIALS_FILE


def browser_state_path(config_dir_override: Optional[str] = None) -> Path:
    return config_dir(config_dir_override) / BROWSER_STATE_FILE


def load(config_dir_override: Optional[str] = None) -> Optional[Credentials]:
    """Load credentials. Env token overrides file; corrupt file ignored if env set."""
    env_token = None
    for var in TOKEN_ENV_VARS:
        val = os.environ.get(var)
        if val:
            env_token = val
            break

    api_url = os.environ.get(API_URL_ENV, DEFAULT_API_URL)
    web_hostname = os.environ.get(WEB_HOSTNAME_ENV, DEFAULT_WEB_HOSTNAME)

    if env_token:
        return Credentials(
            token=env_token,
            api_url=api_url,
            web_hostname=web_hostname,
        )

    path = credentials_path(config_dir_override)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    token = data.get("token")
    if not token:
        return None

    return Credentials(
        token=token,
        api_url=data.get("api_url", api_url),
        web_hostname=data.get("web_hostname", web_hostname),
        user=data.get("user", {}),
    )


def save(creds: Credentials, config_dir_override: Optional[str] = None) -> Path:
    """Atomic save with 0600 permissions."""
    dir_path = config_dir(config_dir_override)
    dir_path.mkdir(parents=True, exist_ok=True)

    data = {
        "token": creds.token,
        "api_url": creds.api_url,
        "web_hostname": creds.web_hostname,
        "user": creds.user,
    }

    dest = dir_path / CREDENTIALS_FILE
    fd, tmp = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    try:
        os.write(fd, json.dumps(data, indent=2).encode())
        os.close(fd)
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, str(dest))
    except BaseException:
        os.close(fd) if not os.get_inheritable(fd) else None
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    return dest


def clear(config_dir_override: Optional[str] = None) -> bool:
    """Remove credentials file. Returns True if file existed."""
    path = credentials_path(config_dir_override)
    if path.exists():
        path.unlink()
        return True
    return False
