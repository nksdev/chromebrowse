"""Synchronous browsing engine built on Playwright + Chromium."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from .config import BrowserConfig, platform_info, require_chromium
from .exceptions import (
    BrowserLaunchError,
    ChromiumNotFoundError,
    ElementInteractionError,
    ElementNotFoundError,
    NavigationError,
    SessionError,
    TimeoutError as BrowserTimeoutError,
)
from .models import Link, PageContent, Snapshot
from .extract import EXTRACT_LINKS_JS, EXTRACT_TEXT_JS, EXTRACT_META_JS, html_to_text, html_to_markdown

Selector = str
LoadState = str  # "load" | "domcontentloaded" | "networkidle" | "commit"


class Element:
    """Wrapper around a Playwright locator with a friendlier API."""

    def __init__(self, page: "Page", selector: str, index: int = 0):
        self._page = page
        self._selector = selector
        self._index = index

    @property
    def _locator(self):
        return self._page._pw_page.locator(self._selector).nth(self._index)

    @property
    def selector(self) -> str:
        return self._selector

    def text(self) -> str:
        return (self._locator.inner_text() or "").strip()

    def html(self) -> str:
        return self._locator.inner_html()

    def attr(self, name: str) -> Optional[str]:
        return self._locator.get_attribute(name)

    def value(self) -> Optional[str]:
        return self._locator.input_value() if self._exists() else None

    def is_visible(self) -> bool:
        try:
            return self._locator.is_visible()
        except Exception:
            return False

    def _exists(self) -> bool:
        try:
            return self._locator.count() > 0
        except Exception:
            return False

    def click(self, timeout: Optional[float] = None) -> "Page":
        try:
            self._locator.click(timeout=self._page._timeout if timeout is None else timeout)
        except Exception as exc:
            if exc.__class__.__name__ == "TimeoutError":
                raise BrowserTimeoutError(f"timed out clicking {self._selector!r}: {exc}") from exc
            raise ElementInteractionError(f"cannot click {self._selector!r}: {exc}") from exc
        return self._page

    def fill(self, value: str, timeout: Optional[float] = None) -> "Page":
        try:
            self._locator.fill(value, timeout=self._page._timeout if timeout is None else timeout)
        except Exception as exc:
            if exc.__class__.__name__ == "TimeoutError":
                raise BrowserTimeoutError(f"timed out filling {self._selector!r}: {exc}") from exc
            raise ElementInteractionError(f"cannot fill {self._selector!r}: {exc}") from exc
        return self._page

    def type_text(self, value: str, delay: float = 0.0) -> "Page":
        self._locator.type(value, delay=delay)
        return self._page

    def press(self, key: str) -> "Page":
        self._locator.press(key)
        return self._page

    def check(self) -> "Page":
        self._locator.check()
        return self._page

    def uncheck(self) -> "Page":
        self._locator.uncheck()
        return self._page

    def select(self, *values: str) -> "Page":
        self._locator.select_option(list(values))
        return self._page

    def hover(self) -> "Page":
        self._locator.hover()
        return self._page

    def scroll_into_view(self) -> "Page":
        self._locator.scroll_into_view_if_needed()
        return self._page

    def screenshot(self, path: Union[str, Path]) -> "Element":
        self._locator.screenshot(path=str(path))
        return self

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Element {self._selector!r} #{self._index}>"


class Page:
    """A rendered page with extraction and interaction helpers."""

    def __init__(self, browser: "Browser", pw_page, url: str = "", status: Optional[int] = None, elapsed_ms: float = 0.0):
        self._browser = browser
        self._pw_page = pw_page
        self.url = url
        self.status = status
        self.elapsed_ms = elapsed_ms
        self._timeout = browser.config.default_timeout

    # ------------------------------------------------------------------ info
    @property
    def title(self) -> str:
        try:
            return self._pw_page.title()
        except Exception:
            return ""

    def current_url(self) -> str:
        try:
            return self._pw_page.url
        except Exception:
            return self.url

    def content(self) -> str:
        return self._pw_page.content()

    def text(self) -> str:
        return self._pw_page.evaluate(EXTRACT_TEXT_JS) or ""

    def html(self) -> str:
        return self.content()

    def markdown(self) -> str:
        """Return a Markdown approximation of the rendered page HTML."""
        return html_to_markdown(self.content())

    def links(self, absolute: bool = True) -> List[Link]:
        raw = self._pw_page.evaluate(EXTRACT_LINKS_JS) or []
        out: List[Link] = []
        base = self.current_url()
        for item in raw:
            href = item.get("href") or ""
            if not href:
                continue
            if absolute:
                try:
                    from urllib.parse import urljoin
                    href = urljoin(base, href)
                except Exception:
                    pass
            out.append(Link(href=href, text=item.get("text", ""), title=item.get("title", ""), rel=item.get("rel", ""), target=item.get("target", "")))
        return out

    def meta(self) -> Dict[str, str]:
        return self._pw_page.evaluate(EXTRACT_META_JS) or {}

    def snapshot(
        self,
        path: Optional[Union[str, Path]] = None,
        full_page: bool = True,
        selector: Optional[str] = None,
        image_type: str = "png",
        quality: Optional[int] = None,
    ) -> Snapshot:
        kwargs: Dict[str, Any] = {"full_page": full_page, "type": image_type}
        if quality is not None and image_type in ("jpeg", "webp"):
            kwargs["quality"] = quality
        target = self._pw_page.locator(selector).first if selector else self._pw_page
        if path:
            target.screenshot(path=str(path), **kwargs)
            return Snapshot(path=str(path), full_page=full_page)
        data = target.screenshot(**kwargs)
        return Snapshot(data=data, full_page=full_page)

    # alias
    screenshot = snapshot

    def pdf(self, path: Union[str, Path]) -> str:
        self._pw_page.pdf(path=str(path))
        return str(path)

    # ------------------------------------------------------------- extraction
    def extract(
        self,
        include_html: bool = False,
        include_markdown: bool = False,
        include_links: bool = False,
    ) -> PageContent:
        content = PageContent(
            url=self.current_url(),
            title=self.title,
            text=self.text(),
            status=self.status,
            elapsed_ms=self.elapsed_ms,
        )
        if include_html:
            content.html = self.content()
        if include_markdown:
            content.markdown = html_to_markdown(content.html or self.content())
        if include_links:
            content.links = self.links()
        try:
            content.meta = self.meta()
            content.lang = self._pw_page.evaluate("() => document.documentElement.lang || ''") or ""
        except Exception:
            pass
        return content

    # ------------------------------------------------------------ interaction
    def find(self, selector: str, index: int = 0) -> Element:
        el = Element(self, selector, index)
        if not el._exists():
            raise ElementNotFoundError(f"no element matches {selector!r}")
        return el

    def find_all(self, selector: str) -> List[Element]:
        try:
            n = self._pw_page.locator(selector).count()
        except Exception:
            n = 0
        return [Element(self, selector, i) for i in range(n)]

    def exists(self, selector: str) -> bool:
        try:
            return self._pw_page.locator(selector).count() > 0
        except Exception:
            return False

    def click(self, selector: str, timeout: Optional[float] = None) -> "Page":
        return self.find(selector).click(timeout)

    def fill(self, selector: str, value: str, timeout: Optional[float] = None) -> "Page":
        return self.find(selector).fill(value, timeout)

    def wait_for(self, selector: str, state: str = "visible", timeout: Optional[float] = None) -> "Page":
        try:
            self._pw_page.wait_for_selector(selector, state=state, timeout=self._timeout if timeout is None else timeout)
        except Exception as exc:
            raise BrowserTimeoutError(f"timeout waiting for {selector!r} ({state}): {exc}") from exc
        return self

    def wait_for_load(self, state: LoadState = "load", timeout: Optional[float] = None) -> "Page":
        try:
            self._pw_page.wait_for_load_state(state, timeout=self._timeout if timeout is None else timeout)
        except Exception as exc:
            raise BrowserTimeoutError(f"timeout waiting for load state {state!r}: {exc}") from exc
        return self

    def wait_for_timeout(self, ms: float) -> "Page":
        self._pw_page.wait_for_timeout(ms)
        return self

    def sleep(self, seconds: float) -> "Page":
        return self.wait_for_timeout(seconds * 1000.0)

    def scroll_to_bottom(self, steps: int = 8, pause_ms: float = 250.0) -> "Page":
        for _ in range(max(1, steps)):
            self._pw_page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            self._pw_page.wait_for_timeout(pause_ms)
        self._pw_page.evaluate("window.scrollTo(0, 0)")
        return self

    def evaluate(self, script: str, arg: Any = None) -> Any:
        return self._pw_page.evaluate(script, arg) if arg is not None else self._pw_page.evaluate(script)

    def press(self, key: str) -> "Page":
        self._pw_page.keyboard.press(key)
        return self

    def go_back(self) -> "Page":
        self._pw_page.go_back()
        return self.refresh_info()

    def go_forward(self) -> "Page":
        self._pw_page.go_forward()
        return self.refresh_info()

    def reload(self) -> "Page":
        start = time.perf_counter()
        self._pw_page.reload(wait_until="load", timeout=self._browser.config.navigation_timeout)
        self.elapsed_ms = (time.perf_counter() - start) * 1000
        self.url = self.current_url()
        return self

    def goto(self, url: str, wait_until: LoadState = "load", timeout: Optional[float] = None) -> "Page":
        return self._browser._navigate(self, url, wait_until=wait_until, timeout=timeout)

    def refresh_info(self) -> "Page":
        self.url = self.current_url()
        return self

    def set_timeout(self, ms: float) -> "Page":
        self._timeout = ms
        self._pw_page.set_default_timeout(ms)
        return self

    def cookies(self) -> List[Dict[str, Any]]:
        return self._browser._context.cookies()

    def set_cookies(self, cookies: Sequence[Dict[str, Any]]) -> "Page":
        self._browser._context.add_cookies(list(cookies))
        return self

    def storage_state(self, path: Union[str, Path]) -> str:
        self._browser._context.storage_state(path=str(path))
        return str(path)

    def close(self) -> None:
        """Close this tab and release its wrapper from the owning browser."""
        try:
            self._pw_page.close()
        except Exception:
            pass
        finally:
            self._browser._forget_page(self)

    def __enter__(self) -> "Page":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Page url={self.current_url()!r} title={self.title!r}>"


class Browser:
    """High level Chromium browser.

    Usage::

        from chromebrowse import Browser

        with Browser() as b:
            page = b.open("https://example.com")
            print(page.title)
            print(page.text()[:500])
    """

    def __init__(self, config: Optional[BrowserConfig] = None, **kwargs: Any):
        if config is None:
            config = BrowserConfig(**kwargs)
        elif kwargs:
            data = config.as_dict()
            data.update(kwargs)
            config = BrowserConfig.from_dict(data)
        self.config = config
        self._pw = None
        self._browser = None
        self._context = None
        self._pages: List[Page] = []
        self._started = False

    # -------------------------------------------------------------- lifecycle
    def start(self) -> "Browser":
        if self._started:
            return self
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover
            raise BrowserLaunchError(f"playwright is not installed: {exc}") from exc

        # Make sure Playwright can find a browser when using a project-local install.
        import os
        from .config import _playwright_browsers_dirs
        if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
            for d in _playwright_browsers_dirs():
                if any(d.glob("chromium-*")):
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(d)
                    break

        self._ensure_chromium()
        try:
            self._pw = sync_playwright().start()
            launch_kwargs = self.config.to_launch_kwargs()
            if self.config.user_data_dir:
                self._context = self._pw.chromium.launch_persistent_context(
                    self.config.user_data_dir, **launch_kwargs, **self.config.context_kwargs()
                )
                self._browser = None
            else:
                self._browser = self._pw.chromium.launch(**launch_kwargs)
                self._context = self._browser.new_context(**self.config.context_kwargs())
            self._context.set_default_timeout(self.config.default_timeout)
            self._context.set_default_navigation_timeout(self.config.navigation_timeout)
            if self.config.public_only:
                blocked = set(self.config.block_resources)
                self._context.route(
                    "**/*",
                    lambda route, req: _request_router(
                        route,
                        req,
                        public_only=True,
                        block_images=self.config.block_images,
                        blocked_types=blocked,
                    ),
                )
            elif self.config.block_images:
                self._context.route("**/*", _block_images_router)
            elif self.config.block_resources:
                blocked = set(self.config.block_resources)
                self._context.route("**/*", lambda route, req: _block_types_router(route, req, blocked))
        except Exception as exc:
            self._safe_stop()
            raise BrowserLaunchError(f"failed to launch Chromium: {exc}") from exc
        self._started = True
        return self

    def _ensure_chromium(self) -> None:
        """Make sure a Chromium binary exists, optionally downloading it."""
        from .config import (
            find_chromium,
            install_chromium,
            default_install_dir,
            require_chromium,
        )

        if self.config.executable_path or find_chromium():
            return

        if not self.config.auto_install:
            require_chromium()  # raises with actionable message
            return

        target = self.config.install_dir or default_install_dir()

        if self.config.prompt_install:
            import sys

            interactive = sys.stdin.isatty() and sys.stdout.isatty()
            if interactive:
                answer = input(
                    f"Chromium is not installed. Download it now to {target}? "
                    f"(~150 MB) [Y/n] "
                ).strip().lower()
                if answer and not answer.startswith("y"):
                    raise ChromiumNotFoundError(
                        "Chromium download declined. Run 'chromebrowse install' when ready."
                    )

        exe = install_chromium(target, quiet=False)
        self.config.executable_path = exe

    def _safe_stop(self) -> None:
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._context = None
        self._browser = None
        self._pw = None
        self._started = False

    def _forget_page(self, page: Page) -> None:
        """Remove a closed page wrapper from the browser's registry."""
        try:
            self._pages.remove(page)
        except ValueError:
            # Closing a page more than once is safe.
            pass

    def close(self) -> None:
        for p in list(self._pages):
            p.close()
        self._pages.clear()
        self._safe_stop()

    def stop(self) -> None:
        self.close()

    def __enter__(self) -> "Browser":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ pages
    @property
    def context(self):
        if not self._started:
            self.start()
        return self._context

    def new_page(self) -> Page:
        if not self._started:
            self.start()
        assert self._context is not None
        pw_page = self._context.new_page()
        page = Page(self, pw_page)
        self._pages.append(page)
        # Keep the registry correct even if the tab is closed outside this
        # wrapper (for example through a page-close button or Playwright API).
        try:
            pw_page.on("close", lambda: self._forget_page(page))
        except Exception:
            # Test doubles and alternate Playwright-compatible implementations
            # may not expose event hooks; Page.close() still deregisters itself.
            pass
        return page

    def open(
        self,
        url: str,
        wait_until: LoadState = "load",
        timeout: Optional[float] = None,
        page: Optional[Page] = None,
    ) -> Page:
        if not self._started:
            self.start()
        created_page = page is None
        target_page = page if page is not None else self.new_page()
        try:
            return self._navigate(
                target_page, url, wait_until=wait_until, timeout=timeout
            )
        except Exception:
            # One-shot calls create their own page. Do not leak it when
            # navigation fails, but preserve caller-owned pages for recovery.
            if created_page:
                target_page.close()
            raise

    navigate = open

    def _navigate(self, page: Page, url: str, wait_until: LoadState = "load", timeout: Optional[float] = None) -> Page:
        if not url.startswith(("http://", "https://", "file://", "about:", "data:")):
            if url.startswith("//"):
                url = "https:" + url
            else:
                url = "https://" + url
        start = time.perf_counter()
        try:
            if self.config.public_only:
                from .security import validate_public_url

                validate_public_url(url)
            response = page._pw_page.goto(
                url,
                wait_until=wait_until,
                timeout=self.config.navigation_timeout if timeout is None else timeout,
            )
        except Exception as exc:
            raise NavigationError(f"failed to open {url!r}: {exc}") from exc
        page.elapsed_ms = (time.perf_counter() - start) * 1000
        page.url = page.current_url()
        page.status = getattr(response, "status", None) if response is not None else None
        return page

    def fetch(
        self,
        url: str,
        wait_until: LoadState = "networkidle",
        timeout: Optional[float] = None,
        include_html: bool = False,
        include_links: bool = False,
        include_markdown: bool = False,
    ) -> PageContent:
        page = self.open(url, wait_until=wait_until, timeout=timeout)
        try:
            return page.extract(
                include_html=include_html,
                include_links=include_links,
                include_markdown=include_markdown,
            )
        finally:
            page.close()

    def text(self, url: str, **kwargs: Any) -> str:
        return self.fetch(url, **kwargs).text

    def links(self, url: str, **kwargs: Any) -> List[Link]:
        page = self.open(url, **kwargs)
        try:
            return page.links()
        finally:
            page.close()

    def screenshot(self, url: str, path: Union[str, Path], full_page: bool = True, **kwargs: Any) -> Snapshot:
        page = self.open(url, **kwargs)
        try:
            return page.snapshot(path=path, full_page=full_page)
        finally:
            page.close()

    # ------------------------------------------------------------- sessions
    def save_state(self, path: Union[str, Path]) -> str:
        self.context.storage_state(path=str(path))
        return str(path)

    def load_state(self, path: Union[str, Path]) -> None:
        """Load cookies and localStorage from a Playwright storage-state file.

        Call this before navigating to the origins whose localStorage should be
        restored; Playwright init scripts run before each page's site scripts.
        """
        if not self._started:
            self.start()
        state_path = Path(path)
        if not state_path.is_file():
            raise SessionError(f"storage state not found: {state_path}")
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("storage state must be a JSON object")
            cookies = data.get("cookies", [])
            origins = data.get("origins", [])
            if not isinstance(cookies, list):
                raise ValueError("'cookies' must be a list")
            if not isinstance(origins, list):
                raise ValueError("'origins' must be a list")
        except Exception as exc:
            raise SessionError(f"invalid storage state: {exc}") from exc

        if cookies:
            try:
                self._context.add_cookies(cookies)
            except Exception as exc:
                raise SessionError(f"cannot apply cookies: {exc}") from exc

        stores = {}
        for entry in origins:
            if not isinstance(entry, dict):
                continue
            origin = entry.get("origin")
            items = entry.get("localStorage") or []
            if isinstance(origin, str) and isinstance(items, list):
                stores[origin] = {
                    str(item["name"]): str(item.get("value", ""))
                    for item in items
                    if isinstance(item, dict) and "name" in item
                }
        if stores:
            payload = json.dumps(stores, ensure_ascii=True)
            script = (
                "(() => { const stores = " + payload + "; "
                "const values = stores[window.location.origin]; "
                "if (values) { for (const [key, value] of Object.entries(values)) "
                "{ try { window.localStorage.setItem(key, value); } catch (_) {} } } })();"
            )
            try:
                self._context.add_init_script(script=script)
            except Exception as exc:
                raise SessionError(f"cannot restore localStorage: {exc}") from exc

    @staticmethod
    def info() -> Dict[str, Any]:
        return platform_info()


# --------------------------------------------------------------------- routes
def _block_images_router(route, request) -> None:  # pragma: no cover - browser side
    if request.resource_type == "image":
        route.abort()
    else:
        route.continue_()


def _block_types_router(route, request, blocked) -> None:  # pragma: no cover - browser side
    if request.resource_type in blocked:
        route.abort()
    else:
        route.continue_()

def _request_router(route, request, *, public_only: bool, block_images: bool, blocked_types) -> None:
    """Apply URL and resource policies in one route handler.

    Playwright runs the most recently registered route first, so combining
    these checks avoids one policy accidentally bypassing another.
    """
    if public_only:
        from .security import PublicURLRejected, validate_public_url

        try:
            validate_public_url(request.url)
        except PublicURLRejected:
            route.abort("blockedbyclient")
            return

    if block_images and request.resource_type == "image":
        route.abort()
    elif request.resource_type in blocked_types:
        route.abort()
    else:
        route.continue_()
