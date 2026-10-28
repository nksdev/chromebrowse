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


def test_auto_install_defaults_on_and_silent():
    cfg = BrowserConfig()
    assert cfg.auto_install is True
    assert cfg.prompt_install is False
    assert cfg.install_dir is None


def test_default_install_dir_is_path():
    from chromebrowse.config import default_install_dir

    d = default_install_dir()
    assert isinstance(d, Path)


def test_install_chromium_rejects_bad_playwright(monkeypatch, tmp_path):
    """A failing installer must raise ChromiumNotFoundError, not leak subprocess errors."""
    import subprocess
    from chromebrowse.config import install_chromium

    class FakeResult:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())
    with pytest.raises(ChromiumNotFoundError):
        install_chromium(tmp_path, quiet=True)


def test_install_chromium_creates_target_dir(monkeypatch, tmp_path):
    import subprocess
    from chromebrowse.config import install_chromium

    class FakeResult:
        returncode = 0

    target = tmp_path / "nested" / "browsers"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())
    # Simulate the installer having produced a real layout.
    exe_path = target / "chromium-9999" / "chrome-linux" / "chrome"
    exe_path.parent.mkdir(parents=True)
    exe_path.write_text("#!/bin/sh\n")
    monkeypatch.setattr("chromebrowse.config.platform.system", lambda: "Linux")
    exe = install_chromium(target, quiet=True)
    assert exe == str(exe_path)
    assert target.is_dir()



def test_public_only_is_opt_in_and_roundtrips():
    default = BrowserConfig()
    assert default.public_only is False

    restricted = BrowserConfig.from_dict({"public_only": True})
    assert restricted.public_only is True
    assert BrowserConfig.from_dict(restricted.as_dict()).public_only is True
