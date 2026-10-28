"""Tests for session state helpers (filesystem only, no browser)."""

import json
import pytest
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



def test_start_fails_and_preserves_corrupt_state_file(tmp_path, monkeypatch):
    import pytest
    from chromebrowse import session as session_module
    from chromebrowse.exceptions import SessionError

    state_file = tmp_path / "broken.json"
    state_file.write_text("{not-json", encoding="utf-8")
    instances = []

    class FakeBrowser:
        def __init__(self, config):
            self.closed = False
            instances.append(self)

        def start(self):
            return self

        def close(self):
            self.closed = True

    monkeypatch.setattr(session_module, "Browser", FakeBrowser)
    s = session_module.Session("broken", state_dir=tmp_path, persist=True)

    with pytest.raises(SessionError):
        s.start()

    assert state_file.exists()
    assert instances[0].closed is True
    assert s._browser is None



def test_clear_does_not_recreate_state_file_on_close(tmp_path):
    from chromebrowse.session import Session

    state_file = tmp_path / "demo.json"
    state_file.write_text('{"cookies": [], "origins": []}', encoding="utf-8")

    class FakePage:
        def __init__(self):
            self.cleared = False

        def evaluate(self, script):
            self.cleared = "localStorage.clear" in script and "sessionStorage.clear" in script

    class FakeContext:
        def __init__(self):
            self.pages = [FakePage()]
            self.cookies_cleared = False

        def clear_cookies(self):
            self.cookies_cleared = True

    class FakeBrowser:
        def __init__(self):
            self.context = FakeContext()
            self.closed = False

        def close(self):
            self.closed = True

    s = Session("demo", state_dir=tmp_path, persist=True)
    fake_browser = FakeBrowser()
    s._browser = fake_browser

    s.clear()

    assert not state_file.exists()
    assert fake_browser.context.cookies_cleared is True
    assert fake_browser.context.pages[0].cleared is True

    s.close()

    assert fake_browser.closed is True
    assert not state_file.exists()



def test_session_start_resets_browser_after_launch_failure(tmp_path, monkeypatch):
    from chromebrowse import session as session_module

    class BrokenBrowser:
        def __init__(self, config):
            self.closed = False

        def start(self):
            raise RuntimeError("launch failed")

        def close(self):
            self.closed = True

    instances = []
    def factory(config):
        instance = BrokenBrowser(config)
        instances.append(instance)
        return instance

    monkeypatch.setattr(session_module, "Browser", factory)
    session = session_module.Session("broken-launch", state_dir=tmp_path)

    with pytest.raises(RuntimeError, match="launch failed"):
        session.start()

    assert session._browser is None
    assert instances[0].closed is True



def test_session_close_resets_state_when_browser_close_raises(monkeypatch):
    from chromebrowse.session import Session

    class BrokenCloseBrowser:
        def close(self):
            raise RuntimeError("close failed")

    session = Session(persist=False)
    session._browser = BrokenCloseBrowser()
    session._page = object()

    with pytest.raises(RuntimeError, match="close failed"):
        session.close()

    assert session._browser is None
    assert session._page is None
    assert session._skip_save_on_close is False
