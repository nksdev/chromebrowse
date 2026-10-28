"""Exception hierarchy for chromebrowse."""

from __future__ import annotations


class BrowserError(Exception):
    """Base class for all chromebrowse errors."""


class BrowserLaunchError(BrowserError):
    """Raised when the Chromium process cannot be launched."""


class ChromiumNotFoundError(BrowserLaunchError):
    """Raised when no usable Chromium binary can be located."""


class NavigationError(BrowserError):
    """Raised when navigating to a URL fails."""


class ElementNotFoundError(BrowserError):
    """Raised when a selector matches no element."""


class TimeoutError(BrowserError):
    """Raised when an operation exceeds its time budget."""


class SessionError(BrowserError):
    """Raised for invalid browser session state."""
