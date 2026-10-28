"""chromebrowse - a reusable Chromium-based browsing engine for Python.

Quick start::

    from chromebrowse import Browser

    with Browser() as browser:
        page = browser.open("https://example.com")
        print(page.title)
        print(page.text()[:200])
        page.screenshot("example.png")
"""

from __future__ import annotations

from .browser import Browser, Page, Element
from .config import BrowserConfig
from .exceptions import (
    BrowserError,
    BrowserLaunchError,
    ChromiumNotFoundError,
    ElementNotFoundError,
    NavigationError,
    TimeoutError as BrowserTimeoutError,
)
from .models import Link, PageContent, Snapshot
from .session import Session
from . import extract

__all__ = [
    "Browser",
    "Page",
    "Element",
    "BrowserConfig",
    "Session",
    "BrowserError",
    "BrowserLaunchError",
    "ChromiumNotFoundError",
    "ElementNotFoundError",
    "NavigationError",
    "BrowserTimeoutError",
    "Link",
    "PageContent",
    "Snapshot",
    "extract",
    "__version__",
]

__version__ = "0.1.0"
