"""Tests for browser storage-state restoration without launching Chromium."""

import json

import pytest

from chromebrowse.browser import Browser
from chromebrowse.exceptions import SessionError


class FakeContext:
    def __init__(self):
        self.cookies = None
        self.script = None

    def add_cookies(self, cookies):
        self.cookies = cookies

    def add_init_script(self, script):
        self.script = script


def _browser_with_fake_context():
    browser = Browser()
    browser._started = True
    browser._context = FakeContext()
    return browser


def test_load_state_restores_cookies_and_local_storage(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({
            "cookies": [{"name": "sid", "value": "abc", "url": "https://example.com"}],
            "origins": [{
                "origin": "https://example.com",
                "localStorage": [{"name": "theme", "value": "dark"}],
            }],
        }),
        encoding="utf-8",
    )
    browser = _browser_with_fake_context()

    browser.load_state(state_file)

    assert browser.context.cookies[0]["name"] == "sid"
    assert "https://example.com" in browser.context.script
    assert "localStorage.setItem" in browser.context.script


@pytest.mark.parametrize("state", [[], {"cookies": {}}, {"origins": {}}])
def test_load_state_rejects_invalid_shapes(tmp_path, state):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    browser = _browser_with_fake_context()

    with pytest.raises(SessionError):
        browser.load_state(state_file)
