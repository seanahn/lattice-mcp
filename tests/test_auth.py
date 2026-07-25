"""Tests for lattice.auth module."""

from unittest.mock import patch, MagicMock

import pytest

from lattice import auth, credentials
from lattice.credentials import Credentials
from lattice.client import LatticeAPIError


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    monkeypatch.delenv("LATTICE_API_TOKEN", raising=False)
    monkeypatch.delenv("LATTICE_TOKEN", raising=False)
    monkeypatch.delenv("LATTICE_CONFIG_DIR", raising=False)
    return str(tmp_path)


class TestLogin:
    def test_success(self, tmp_config):
        user = {"firstName": "A", "workEmail": "a@b.com"}
        with patch("lattice.auth.get_me", return_value=user):
            with patch("webbrowser.open"):
                rc = auth.login(token="tok", config_dir=tmp_config)
        assert rc == 0
        loaded = credentials.load(tmp_config)
        assert loaded.token == "tok"
        assert loaded.user == user

    def test_failure_invalid_token(self, tmp_config):
        with patch("lattice.auth.get_me", side_effect=LatticeAPIError(401, "bad")):
            with patch("webbrowser.open"):
                rc = auth.login(token="bad", config_dir=tmp_config)
        assert rc == 1
        assert credentials.load(tmp_config) is None

    def test_empty_token(self, tmp_config):
        with patch("getpass.getpass", return_value=""):
            with patch("webbrowser.open"):
                rc = auth.login(config_dir=tmp_config, no_browser=True)
        assert rc == 1


class TestStatus:
    def test_authenticated(self, tmp_config):
        user = {"firstName": "B", "workEmail": "b@c.com"}
        credentials.save(Credentials(token="t", user=user), tmp_config)
        with patch("lattice.auth.get_me", return_value=user):
            rc = auth.status(config_dir=tmp_config)
        assert rc == 0

    def test_not_authenticated(self, tmp_config):
        rc = auth.status(config_dir=tmp_config)
        assert rc == 1

    def test_offline_mode(self, tmp_config):
        credentials.save(Credentials(token="t", user={"firstName": "Off"}), tmp_config)
        rc = auth.status(offline=True, config_dir=tmp_config)
        assert rc == 0

    def test_expired_token(self, tmp_config):
        credentials.save(Credentials(token="t"), tmp_config)
        with patch("lattice.auth.get_me", side_effect=LatticeAPIError(401, "expired")):
            rc = auth.status(config_dir=tmp_config)
        assert rc == 1


class TestLogout:
    def test_logout_removes(self, tmp_config):
        credentials.save(Credentials(token="t"), tmp_config)
        rc = auth.logout(tmp_config)
        assert rc == 0
        assert credentials.load(tmp_config) is None

    def test_logout_no_creds(self, tmp_config):
        rc = auth.logout(tmp_config)
        assert rc == 0


class TestToken:
    def test_prints_token(self, tmp_config, capsys):
        credentials.save(Credentials(token="secret"), tmp_config)
        rc = auth.token(tmp_config)
        assert rc == 0
        assert capsys.readouterr().out.strip() == "secret"

    def test_no_creds(self, tmp_config):
        rc = auth.token(tmp_config)
        assert rc == 1


class TestCLILogin:
    def test_cli_auth_login(self, tmp_config):
        from lattice.cli import main
        user = {"firstName": "CLI", "workEmail": "cli@x.com"}
        with patch("lattice.auth.get_me", return_value=user):
            with patch("webbrowser.open"):
                rc = main(["--config-dir", tmp_config, "auth", "login", "--with-token", "clitoken", "--no-browser"])
        assert rc == 0
        loaded = credentials.load(tmp_config)
        assert loaded.token == "clitoken"
