"""Tests for lattice.credentials module."""

import json
import os
import stat
from pathlib import Path

import pytest

from lattice import credentials
from lattice.credentials import Credentials


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    monkeypatch.delenv("LATTICE_API_TOKEN", raising=False)
    monkeypatch.delenv("LATTICE_TOKEN", raising=False)
    monkeypatch.delenv("LATTICE_API_URL", raising=False)
    monkeypatch.delenv("LATTICE_WEB_HOSTNAME", raising=False)
    monkeypatch.delenv("LATTICE_CONFIG_DIR", raising=False)
    return str(tmp_path)


class TestCredentials:
    def test_masked_token_short(self):
        c = Credentials(token="abc")
        assert c.masked_token() == "****"

    def test_masked_token_long(self):
        c = Credentials(token="abcdefghij1234567890")
        assert c.masked_token() == "abcd...7890"

    def test_defaults(self):
        c = Credentials(token="x")
        assert c.api_url == "https://api.latticehq.com"
        assert c.web_hostname == "c3.latticehq.com"
        assert c.user == {}


class TestSaveLoad:
    def test_save_creates_file_with_0600(self, tmp_config):
        creds = Credentials(token="secret123", user={"name": "Test"})
        path = credentials.save(creds, tmp_config)
        assert path.exists()
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600

    def test_load_reads_saved_credentials(self, tmp_config):
        creds = Credentials(token="tok", api_url="https://x.com", web_hostname="x.com", user={"id": "1"})
        credentials.save(creds, tmp_config)
        loaded = credentials.load(tmp_config)
        assert loaded is not None
        assert loaded.token == "tok"
        assert loaded.api_url == "https://x.com"
        assert loaded.web_hostname == "x.com"
        assert loaded.user == {"id": "1"}

    def test_load_returns_none_when_no_file(self, tmp_config):
        assert credentials.load(tmp_config) is None

    def test_load_returns_none_on_corrupt_json(self, tmp_config):
        dir_path = Path(tmp_config)
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "credentials.json").write_text("not json{{{")
        assert credentials.load(tmp_config) is None

    def test_load_returns_none_when_no_token_field(self, tmp_config):
        dir_path = Path(tmp_config)
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "credentials.json").write_text(json.dumps({"api_url": "x"}))
        assert credentials.load(tmp_config) is None


class TestEnvOverride:
    def test_env_token_overrides_file(self, tmp_config, monkeypatch):
        creds = Credentials(token="file_token")
        credentials.save(creds, tmp_config)
        monkeypatch.setenv("LATTICE_API_TOKEN", "env_token")
        loaded = credentials.load(tmp_config)
        assert loaded is not None
        assert loaded.token == "env_token"

    def test_lattice_token_env(self, tmp_config, monkeypatch):
        monkeypatch.setenv("LATTICE_TOKEN", "fallback_tok")
        loaded = credentials.load(tmp_config)
        assert loaded is not None
        assert loaded.token == "fallback_tok"

    def test_env_ignores_corrupt_file(self, tmp_config, monkeypatch):
        dir_path = Path(tmp_config)
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "credentials.json").write_text("CORRUPT")
        monkeypatch.setenv("LATTICE_API_TOKEN", "good")
        loaded = credentials.load(tmp_config)
        assert loaded is not None
        assert loaded.token == "good"

    def test_api_url_env(self, tmp_config, monkeypatch):
        monkeypatch.setenv("LATTICE_TOKEN", "t")
        monkeypatch.setenv("LATTICE_API_URL", "https://custom.api")
        loaded = credentials.load(tmp_config)
        assert loaded.api_url == "https://custom.api"

    def test_web_hostname_env(self, tmp_config, monkeypatch):
        monkeypatch.setenv("LATTICE_TOKEN", "t")
        monkeypatch.setenv("LATTICE_WEB_HOSTNAME", "custom.host")
        loaded = credentials.load(tmp_config)
        assert loaded.web_hostname == "custom.host"


class TestClear:
    def test_clear_removes_file(self, tmp_config):
        credentials.save(Credentials(token="x"), tmp_config)
        assert credentials.clear(tmp_config) is True
        assert credentials.load(tmp_config) is None

    def test_clear_returns_false_when_no_file(self, tmp_config):
        assert credentials.clear(tmp_config) is False


class TestConfigDir:
    def test_override_takes_precedence(self):
        assert credentials.config_dir("/custom") == Path("/custom")

    def test_env_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("LATTICE_CONFIG_DIR", "/from/env")
        assert credentials.config_dir() == Path("/from/env")

    def test_default(self, monkeypatch):
        monkeypatch.delenv("LATTICE_CONFIG_DIR", raising=False)
        result = credentials.config_dir()
        assert result == Path.home() / ".config" / "lattice"
