"""Unit tests for tools/reload_config.py.

Verifies that reload_config() reloads every YAML-managed domain (not just core
config) and fails safely when no token is configured.
"""

# pylint: disable=import-error,redefined-outer-name

import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable so `tools` resolves regardless of cwd.
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import reload_config  # noqa: E402


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Run with a clean cwd (no real .env) and a known token/url."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HA_TOKEN", "test-token")
    monkeypatch.setenv("HA_URL", "http://ha.test:8123")
    return tmp_path


def test_reloads_all_domains(isolated_env, monkeypatch):
    """reload_config() POSTs to every service in RELOAD_SERVICES."""
    calls = []

    def fake_post(url, headers=None, timeout=None):
        calls.append(url)
        return FakeResponse(200)

    monkeypatch.setattr(reload_config.requests, "post", fake_post)

    assert reload_config.reload_config() is True

    expected = [
        f"http://ha.test:8123/api/services/{path}"
        for _label, path in reload_config.RELOAD_SERVICES
    ]
    assert calls == expected
    # Guards against regressing to core-config-only reloads.
    assert "automation/reload" in " ".join(calls)
    assert "scene/reload" in " ".join(calls)
    assert "script/reload" in " ".join(calls)


def test_missing_token_fails_without_calling(isolated_env, monkeypatch):
    """With no HA_TOKEN, reload_config() returns False and makes no request."""
    monkeypatch.delenv("HA_TOKEN", raising=False)

    def fail_post(*_args, **_kwargs):
        raise AssertionError("requests.post must not be called without a token")

    monkeypatch.setattr(reload_config.requests, "post", fail_post)

    assert reload_config.reload_config() is False


def test_one_failing_service_fails_overall(isolated_env, monkeypatch):
    """A non-200 from any service makes reload_config() return False."""

    def fake_post(url, headers=None, timeout=None):
        # Fail only the scene reload; others succeed.
        if "scene/reload" in url:
            return FakeResponse(500, "boom")
        return FakeResponse(200)

    monkeypatch.setattr(reload_config.requests, "post", fake_post)

    assert reload_config.reload_config() is False
