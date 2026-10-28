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


def test_load_state_file_restores_cookies_and_local_storage(tmp_path):
    import json
    from chromebrowse.session import Session

    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "sid", "value": "secret", "url": "https://example.com"}],
            "origins": [{
                "origin": "https://example.com",
                "localStorage": [{"name": "theme", "value": "dark"}],
            }],
        }),
        encoding="utf-8",
    )

    class FakeContext:
        def __init__(self):
            self.cookies = None
            self.script = None
        def add_cookies(self, cookies):
            self.cookies = cookies
        def add_init_script(self, script):
            self.script = script

    class FakeBrowser:
        def __init__(self):
            self.context = FakeContext()

    session = Session(persist=False)
    session._browser = FakeBrowser()
    session._load_state_file(state_file)

    assert session.browser.context.cookies[0]["name"] == "sid"
    assert "https://example.com" in session.browser.context.script
    assert "localStorage.setItem" in session.browser.context.script
