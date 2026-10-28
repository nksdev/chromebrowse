"""Live browser integration tests.

These launch real Chromium and hit the network, so they are skipped unless
``CHROMEBROWSE_LIVE=1`` is set::

    CHROMEBROWSE_LIVE=1 python -m pytest tests/test_live.py -v
"""

import os

import pytest

LIVE = os.environ.get("CHROMEBROWSE_LIVE") == "1"

pytestmark = pytest.mark.skipif(not LIVE, reason="set CHROMEBROWSE_LIVE=1 to run live browser tests")


@pytest.fixture(scope="module")
def browser():
    from chromebrowse import Browser

    with Browser() as b:
        yield b


def test_open_and_extract(browser):
    page = browser.open("https://example.com")
    assert page.status == 200
    assert "Example" in page.title
    text = page.text()
    assert len(text) > 20
    assert "<p>" not in text


def test_links(browser):
    page = browser.open("https://example.com")
    links = page.links()
    assert links
    assert all(l.href.startswith("http") for l in links)


def test_javascript_execution(browser):
    page = browser.open("https://example.com")
    assert page.evaluate("1 + 1") == 2
    assert page.evaluate("document.title") == page.title


def test_screenshot_bytes(browser):
    page = browser.open("https://example.com")
    snap = page.snapshot(full_page=False)
    assert snap.data is not None
    assert snap.data[:4] == b"\x89PNG"


def test_fetch_returns_content(browser):
    content = browser.fetch("https://example.com", include_links=True)
    assert content.status == 200
    assert content.title
    assert content.text
    assert content.links


def test_meta_extraction(browser):
    page = browser.open("https://example.com")
    meta = page.meta()
    assert isinstance(meta, dict)
    assert "viewport" in meta or "title" in meta
