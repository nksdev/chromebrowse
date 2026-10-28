"""Extension points for customizing browser behaviour.

The hooks here are deliberately small and additive. They let a developer
plug into the browser lifecycle without subclassing ``Browser`` or
monkey-patching Playwright, which is what keeps the library composable.

Every hook is optional and defaulted to a no-op, so importing this module
changes no existing behaviour.

Example::

    from chromebrowse import Browser
    from chromebrowse.hooks import HookSet

    def log_navigation(page, url, error):
        print("visited" if error is None else "failed", url)

    with Browser() as browser:
        browser.hooks = HookSet(after_navigate=log_navigation)
        browser.open("https://example.com")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

# A navigation hook receives (page, url, error); ``error`` is None on success.
NavigateHook = Callable[[Any, str, Optional[BaseException]], None]
# A page hook receives the freshly created Page.
PageHook = Callable[[Any], None]
# A response hook receives (page, url, status).
ResponseHook = Callable[[Any, str, Optional[int]], None]


def _noop(*_args: Any, **_kwargs: Any) -> None:
    return None


@dataclass
class HookSet:
    """Optional callbacks invoked at defined points in the browser lifecycle.

    Attributes:
        before_navigate: Called before a navigation begins, with ``(page, url)``.
            Raising from this hook aborts the navigation.
        after_navigate: Called after a navigation settles, with
            ``(page, url, error)``. ``error`` is None on success. Exceptions
            from this hook are logged by the caller's policy, never raised.
        on_page_created: Called with each new :class:`Page`.
        on_page_closed: Called with each :class:`Page` as it is closed.
        on_response: Called with ``(page, url, status)`` for the main document.

    Hooks may be added incrementally with :meth:`add`; duplicate callables are
    rejected so re-registering is idempotent.
    """

    before_navigate: Optional[NavigateHook] = None
    after_navigate: Optional[NavigateHook] = None
    on_page_created: Optional[PageHook] = None
    on_page_closed: Optional[PageHook] = None
    on_response: Optional[ResponseHook] = None
    _extra: List[Callable[..., None]] = field(default_factory=list, repr=False)

    def add(self, hook: Callable[..., None]) -> "HookSet":
        """Register a generic ``(event, payload)`` hook.

        Returns ``self`` so calls can be chained. Registering the same
        callable twice is a no-op.
        """
        if hook not in self._extra:
            self._extra.append(hook)
        return self

    def emit(self, event: str, payload: Any = None) -> None:
        """Call every generic hook with ``(event, payload)``.

        Exceptions from hooks are swallowed: an observer must not be able to
        break a browser operation.
        """
        for hook in list(self._extra):
            try:
                hook(event, payload)
            except Exception:
                continue

    # ------------------------------------------------------------- dispatch
    def fire_before_navigate(self, page: Any, url: str) -> None:
        if self.before_navigate is not None:
            self.before_navigate(page, url)
        self.emit("before_navigate", {"page": page, "url": url})

    def fire_after_navigate(self, page: Any, url: str, error: Optional[BaseException]) -> None:
        if self.after_navigate is not None:
            try:
                self.after_navigate(page, url, error)
            except Exception:
                pass
        self.emit("after_navigate", {"page": page, "url": url, "error": error})

    def fire_page_created(self, page: Any) -> None:
        if self.on_page_created is not None:
            try:
                self.on_page_created(page)
            except Exception:
                pass
        self.emit("page_created", page)

    def fire_page_closed(self, page: Any) -> None:
        if self.on_page_closed is not None:
            try:
                self.on_page_closed(page)
            except Exception:
                pass
        self.emit("page_closed", page)

    def fire_response(self, page: Any, url: str, status: Optional[int]) -> None:
        if self.on_response is not None:
            try:
                self.on_response(page, url, status)
            except Exception:
                pass
        self.emit("response", {"page": page, "url": url, "status": status})
