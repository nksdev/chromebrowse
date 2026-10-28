"""Tests for configuration and Chromium discovery (no browser launch)."""

import os
from pathlib import Path

import pytest

from chromebrowse.config import (
    BrowserConfig,
    find_chromium,
    platform_info,
    require_chromium,
)
from chromebrowse.exceptions import ChromiumNotFoundError


def test_config_defaults():
    cfg = BrowserConfig()
    assert cfg.headless is True
    assert cfg.viewport_width == 1280
    assert cfg.java_script_enabled is True
    assert cfg.default_timeout > 0


def test_config_context_kwargs_shape():
    cfg = BrowserConfig(locale="fr-FR", block_images=True)
    kw = cfg.context_kwargs()
    assert kw["locale"] == "fr-FR"
    assert kw["viewport"] == {"width": 1280, "height": 800}
    assert "extra_http_headers" not in kw  # None values dropped


def test_config_roundtrip_dict():
    cfg = BrowserConfig(headless=False, viewport_width=800)
    restored = BrowserConfig.from_dict(cfg.as_dict())
    assert restored.headless is False
    assert restored.viewport_width == 800


def test_config_from_dict_ignores_unknown():
    cfg = BrowserConfig.from_dict({"headless": False, "bogus": 1})
    assert cfg.headless is False


def test_extra_headers_in_context():
    cfg = BrowserConfig(extra_headers={"X-Test": "1"})
    assert cfg.context_kwargs()["extra_http_headers"] == {"X-Test": "1"}


def test_platform_info_reports_keys():
    info = platform_info()
    for key in ("python", "platform", "system", "chromium_found"):
        assert key in info


def test_explicit_executable_path_wins(tmp_path):
    fake = tmp_path / "chrome"
    fake.write_text("")
    cfg = BrowserConfig(executable_path=str(fake))
    assert cfg.resolve_executable() == str(fake)


def test_env_executable_override(tmp_path, monkeypatch):
    fake = tmp_path / "chrome-env"
    fake.write_text("")
    monkeypatch.setenv("CHROMEBROWSE_CHROMIUM", str(fake))
    assert find_chromium() == str(fake)


def test_env_executable_missing_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMEBROWSE_CHROMIUM", str(tmp_path / "nope"))
    # Falls through to other discovery; should not raise here.
    result = find_chromium()
    assert result is None or Path(result).is_file()


def test_require_chromium_raises_when_missing(monkeypatch):
    monkeypatch.setattr("chromebrowse.config.find_chromium", lambda: None)
    with pytest.raises(ChromiumNotFoundError):
        require_chromium()


def test_require_chromium_returns_path_when_found(monkeypatch, tmp_path):
    fake = tmp_path / "chrome"
    fake.write_text("")
    monkeypatch.setattr("chromebrowse.config.find_chromium", lambda: str(fake))
    assert require_chromium() == str(fake)
