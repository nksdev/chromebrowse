"""Tests for session state helpers (filesystem only, no browser)."""

import json
from pathlib import Path

from chromebrowse.session import delete_session, list_sessions


def _write_state(directory: Path, name: str, cookies=None):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.json"
    target.write_text(json.dumps({"cookies": cookies or [], "origins": []}), encoding="utf-8")
    return target


def test_list_sessions_empty(tmp_path):
    assert list_sessions(tmp_path) == []


def test_list_sessions_reports_files(tmp_path):
    _write_state(tmp_path, "alpha")
    _write_state(tmp_path, "beta")
    rows = list_sessions(tmp_path)
    names = [r["name"] for r in rows]
    assert names == ["alpha", "beta"]
    assert all(r["bytes"] > 0 for r in rows)
    assert all("modified" in r for r in rows)


def test_delete_session_existing(tmp_path):
    _write_state(tmp_path, "gone")
    assert delete_session("gone", tmp_path) is True
    assert list_sessions(tmp_path) == []


def test_delete_session_missing(tmp_path):
    assert delete_session("never", tmp_path) is False


def test_delete_session_sanitizes_name(tmp_path):
    _write_state(tmp_path, "weird_name")
    assert delete_session("weird/name", tmp_path) is True


def test_session_fetch_extract_options_are_not_passed_to_navigation():
    # Regression coverage for the kwargs mutation/order bug without launching Chromium.
    from chromebrowse.session import Session

    session = Session(persist=False)
    class FakePage:
        def extract(self, **kwargs):
            return kwargs
    calls = {}
    def fake_open(url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return FakePage()
    session.open = fake_open
    result = session.fetch(
        "https://example.com",
        wait_until="domcontentloaded",
        include_html=True,
        include_links=True,
        include_markdown=True,
    )
    assert calls["url"] == "https://example.com"
    assert calls["kwargs"] == {"wait_until": "domcontentloaded"}
    assert result == {
        "include_html": True,
        "include_links": True,
        "include_markdown": True,
    }
