"""Tests for lattice.ui module (no browser required)."""

import json
from pathlib import Path

import pytest

from lattice.ui import (
    looks_like_login_url,
    is_authenticated,
    session_exists,
    write_scrape_outputs,
)


class TestLooksLikeLoginUrl:
    @pytest.mark.parametrize("url", [
        "https://c3.okta.com/app/lattice/sso",
        "https://auth0.com/authorize",
        "https://c3.latticehq.com/login",
        "https://c3.latticehq.com/signin",
        "https://c3.latticehq.com/sign-in",
        "https://accounts.google.com/oauth/v2/auth",
        "https://sso.c3.ai/saml/login",
    ])
    def test_login_urls(self, url):
        assert looks_like_login_url(url, "c3.latticehq.com") is True

    @pytest.mark.parametrize("url", [
        "https://c3.latticehq.com/home",
        "https://c3.latticehq.com/",
        "https://c3.latticehq.com/goals",
        "https://c3.latticehq.com/people/123",
    ])
    def test_non_login_urls(self, url):
        assert looks_like_login_url(url, "c3.latticehq.com") is False

    def test_different_host_without_indicators(self):
        assert looks_like_login_url("https://cdn.example.com/script.js", "c3.latticehq.com") is False


class TestIsAuthenticated:
    def test_on_tenant_with_cookies(self):
        assert is_authenticated("https://c3.latticehq.com/home", "c3.latticehq.com", True) is True

    def test_on_tenant_no_cookies(self):
        assert is_authenticated("https://c3.latticehq.com/home", "c3.latticehq.com", False) is False

    def test_on_login_page(self):
        assert is_authenticated("https://c3.latticehq.com/login", "c3.latticehq.com", True) is False

    def test_different_host(self):
        assert is_authenticated("https://okta.com/app", "c3.latticehq.com", True) is False


class TestSessionExists:
    def test_no_file(self, tmp_path):
        assert session_exists(str(tmp_path)) is False

    def test_empty_cookies(self, tmp_path):
        state = {"cookies": [], "origins": []}
        (tmp_path / "browser-state.json").write_text(json.dumps(state))
        assert session_exists(str(tmp_path)) is False

    def test_has_cookies(self, tmp_path):
        state = {"cookies": [{"name": "sid", "value": "abc"}], "origins": []}
        (tmp_path / "browser-state.json").write_text(json.dumps(state))
        assert session_exists(str(tmp_path)) is True

    def test_corrupt_json(self, tmp_path):
        (tmp_path / "browser-state.json").write_text("NOT JSON")
        assert session_exists(str(tmp_path)) is False


class TestWriteScrapeOutputs:
    def test_creates_files(self, tmp_path):
        out = tmp_path / "scrape-out"
        gql = [{"url": "https://c3.latticehq.com/graphql", "status": 200, "body": {"data": {}}}]
        write_scrape_outputs(out, "https://c3.latticehq.com/home", "Home", "Hello World", gql, html="<html></html>")

        assert (out / "scrape.meta.json").exists()
        assert (out / "scrape.txt").read_text() == "Hello World"
        assert (out / "scrape.graphql.json").exists()
        assert (out / "scrape.html").read_text() == "<html></html>"

        meta = json.loads((out / "scrape.meta.json").read_text())
        assert meta["url"] == "https://c3.latticehq.com/home"
        assert meta["title"] == "Home"

        gql_data = json.loads((out / "scrape.graphql.json").read_text())
        assert len(gql_data) == 1
        assert gql_data[0]["status"] == 200

    def test_no_html(self, tmp_path):
        out = tmp_path / "no-html"
        write_scrape_outputs(out, "u", "t", "text", [])
        assert not (out / "scrape.html").exists()


class TestCLIUiStatus:
    def test_no_session_returns_1(self, tmp_path):
        from lattice.cli import main
        rc = main(["--config-dir", str(tmp_path), "ui", "status"])
        assert rc == 1

    def test_with_session_returns_0(self, tmp_path):
        from lattice.cli import main
        state = {"cookies": [{"name": "s", "value": "v"}], "origins": []}
        (tmp_path / "browser-state.json").write_text(json.dumps(state))
        rc = main(["--config-dir", str(tmp_path), "ui", "status"])
        assert rc == 0
