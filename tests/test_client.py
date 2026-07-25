"""Tests for lattice.client module."""

import json
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from io import BytesIO

import pytest

from lattice.client import get_me, user_display, LatticeAPIError


class TestGetMe:
    def test_success(self):
        user_data = {"firstName": "Jane", "lastName": "Doe", "workEmail": "jane@c3.ai"}
        response = MagicMock()
        response.read.return_value = json.dumps(user_data).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=response) as mock_open:
            result = get_me("https://api.latticehq.com", "tok123")

        assert result == user_data
        req = mock_open.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer tok123"
        assert "/v1/me" in req.full_url

    def test_401_raises(self):
        error = HTTPError(
            url="https://api.latticehq.com/v1/me",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(b"invalid token"),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(LatticeAPIError) as exc_info:
                get_me("https://api.latticehq.com", "bad")
            assert exc_info.value.status == 401

    def test_trailing_slash_stripped(self):
        response = MagicMock()
        response.read.return_value = b"{}"
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=response) as mock_open:
            get_me("https://api.latticehq.com/", "t")

        req = mock_open.call_args[0][0]
        assert req.full_url == "https://api.latticehq.com/v1/me"


class TestUserDisplay:
    def test_preferred_name_and_email(self):
        user = {"preferredName": "Jay", "workEmail": "jay@c3.ai"}
        assert user_display(user) == "Jay <jay@c3.ai>"

    def test_first_last_email(self):
        user = {"firstName": "Jane", "lastName": "Doe", "workEmail": "jd@c3.ai"}
        assert user_display(user) == "Jane Doe <jd@c3.ai>"

    def test_only_email(self):
        user = {"workEmail": "x@y.com"}
        assert user_display(user) == "x@y.com"

    def test_only_name(self):
        user = {"firstName": "Solo"}
        assert user_display(user) == "Solo"

    def test_empty_dict(self):
        assert user_display({}) == "(unknown)"

    def test_none(self):
        assert user_display(None) == "(unknown)"

    def test_fallback_email(self):
        user = {"email": "fallback@x.com"}
        assert user_display(user) == "fallback@x.com"
