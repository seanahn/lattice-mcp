"""Tests for lattice.notify module."""

import json
import re
import stat
from pathlib import Path

import pytest

from lattice import notify


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    monkeypatch.delenv("LATTICE_NTFY_TOPIC", raising=False)
    monkeypatch.delenv("LATTICE_NTFY_SERVER", raising=False)
    monkeypatch.delenv("LATTICE_CONFIG_DIR", raising=False)
    return str(tmp_path)


class TestGenerateTopic:
    def test_format(self, monkeypatch):
        monkeypatch.setenv("USER", "alice")
        topic = notify.generate_topic()
        assert re.fullmatch(r"lattice-alice-[a-z0-9]{12}", topic)

    def test_random_suffix_differs(self, monkeypatch):
        monkeypatch.setenv("USER", "alice")
        assert notify.generate_topic() != notify.generate_topic()

    def test_no_user_env(self, monkeypatch):
        monkeypatch.delenv("USER", raising=False)
        monkeypatch.delenv("USERNAME", raising=False)
        assert notify.generate_topic().startswith("lattice-user-")


class TestResolveTopic:
    def test_env_wins(self, tmp_config, monkeypatch):
        notify.save_config({"ntfy_topic": "from-config"}, tmp_config)
        monkeypatch.setenv("LATTICE_NTFY_TOPIC", "from-env")
        assert notify.resolve_topic(tmp_config) == "from-env"

    def test_config_used(self, tmp_config):
        notify.save_config({"ntfy_topic": "from-config"}, tmp_config)
        assert notify.resolve_topic(tmp_config) == "from-config"

    def test_none_without_create(self, tmp_config):
        assert notify.resolve_topic(tmp_config) is None

    def test_create_generates_and_persists(self, tmp_config, monkeypatch):
        monkeypatch.setenv("USER", "bob")
        topic = notify.resolve_topic(tmp_config, create=True)
        assert topic.startswith("lattice-bob-")
        # persisted: second resolve returns the same topic
        assert notify.resolve_topic(tmp_config) == topic

    def test_config_file_permissions(self, tmp_config):
        notify.save_config({"ntfy_topic": "x"}, tmp_config)
        mode = stat.S_IMODE(notify.config_path(tmp_config).stat().st_mode)
        assert mode == 0o600


class TestResolveServer:
    def test_default(self, tmp_config):
        assert notify.resolve_server(tmp_config) == "https://ntfy.sh"

    def test_env_wins(self, tmp_config, monkeypatch):
        monkeypatch.setenv("LATTICE_NTFY_SERVER", "https://ntfy.example.com/")
        assert notify.resolve_server(tmp_config) == "https://ntfy.example.com"

    def test_config_used(self, tmp_config):
        notify.save_config({"ntfy_server": "https://my.ntfy/"}, tmp_config)
        assert notify.resolve_server(tmp_config) == "https://my.ntfy"


class TestSend:
    def test_posts_message(self, tmp_config, monkeypatch):
        notify.save_config({"ntfy_topic": "t0pic"}, tmp_config)
        captured = {}

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["data"] = req.data
            captured["title"] = req.get_header("Title")
            return FakeResp()

        monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
        rc = notify.send("hello", title="Hi", config_dir_override=tmp_config)
        assert rc == 0
        assert captured["url"] == "https://ntfy.sh/t0pic"
        assert captured["data"] == b"hello"
        assert captured["title"] == "Hi"

    def test_first_send_warns_about_generated_topic(
        self, tmp_config, monkeypatch, capsys
    ):
        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(
            notify.urllib.request, "urlopen", lambda req, timeout=None: FakeResp()
        )
        monkeypatch.setenv("USER", "carol")
        assert notify.send("first alert", config_dir_override=tmp_config) == 0
        err = capsys.readouterr().err
        assert "nobody may be subscribed" in err
        # second send: topic exists, no warning
        assert notify.send("second alert", config_dir_override=tmp_config) == 0
        assert "nobody may be subscribed" not in capsys.readouterr().err

    def test_send_failure_returns_1(self, tmp_config, monkeypatch):
        notify.save_config({"ntfy_topic": "t"}, tmp_config)

        def boom(req, timeout=None):
            raise OSError("network down")

        monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
        assert notify.send("hello", config_dir_override=tmp_config) == 1


class TestShow:
    def test_no_topic(self, tmp_config, capsys):
        assert notify.show(tmp_config) == 1

    def test_shows_existing(self, tmp_config, capsys):
        notify.save_config({"ntfy_topic": "mytopic"}, tmp_config)
        assert notify.show(tmp_config) == 0
        out = capsys.readouterr().out
        assert "mytopic" in out
        assert "https://ntfy.sh/mytopic" in out

    def test_show_saves_ascii_qr_file(self, tmp_config):
        pytest.importorskip("qrcode")
        notify.save_config({"ntfy_topic": "mytopic"}, tmp_config)
        assert notify.show(tmp_config) == 0
        txt = notify.config_path(tmp_config).parent / "ntfy-qr.txt"
        assert txt.exists()
        content = txt.read_text()
        assert content.startswith("https://ntfy.sh/mytopic")
        assert "█" in content
