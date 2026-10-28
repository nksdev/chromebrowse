"""Regression tests for browser page-wrapper lifecycle."""

from chromebrowse.browser import Browser, Page


class FakePlaywrightPage:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_page_close_removes_wrapper_from_browser_registry():
    browser = Browser()
    playwright_page = FakePlaywrightPage()
    page = Page(browser, playwright_page)
    browser._pages.append(page)

    page.close()

    assert playwright_page.closed is True
    assert page not in browser._pages


def test_page_close_is_idempotent():
    browser = Browser()
    playwright_page = FakePlaywrightPage()
    page = Page(browser, playwright_page)
    browser._pages.append(page)

    page.close()
    page.close()

    assert page not in browser._pages
    assert browser._pages == []
