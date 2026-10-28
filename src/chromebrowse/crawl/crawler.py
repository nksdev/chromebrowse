"""Browser-rendered breadth-first crawler composing the ``Browser`` API.

Design constraints
------------------
- **Composes, never reimplements.** The crawler opens pages through
  :class:`chromebrowse.Browser` and uses ``Page.links`` / ``Page.extract``.
  It does not touch Playwright objects directly, so every reliability fix in
  the browser layer benefits the crawler for free.
- **Browser-render only.** This ships the JavaScript-heavy path. An
  HTTP-first fast path was considered and explicitly deferred; see
  ``docs/CRAWLING.md`` for the rationale and the trade-off.
- **Bounded by construction.** ``max_pages`` and ``max_depth`` are enforced
  by the queue, and the frontier is deduplicated on *normalized* URLs.
- **Polite by default.** Same-domain scope unless overridden, a minimum
  delay between requests to the same host, and no automatic ``robots.txt``
  fetching (the caller owns that policy).

Example::

    from chromebrowse.crawl import Crawler

    result = Crawler(max_pages=25, max_depth=2).crawl("https://example.com")
    for page in result.pages:
        print(page.status, page.url, len(page.text))
    print(result.as_dict()["visited"], "pages")
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from ..browser import Browser, Page
from ..config import BrowserConfig
from ..exceptions import BrowserError
from .models import CrawlPage, CrawlResult
from .queue import CrawlQueue
from .scope import CrawlScope, host_of, normalize_url

ProgressCallback = Callable[[CrawlPage, "CrawlResult"], None]


class Crawler:
    """Breadth-first crawler that renders each page in Chromium.

    Args:
        max_pages: Hard cap on the number of unique URLs enqueued. Must be > 0.
        max_depth: Maximum link depth. Seed URLs are depth 0.
        scope: Which URLs may be visited. Defaults to same-domain-on-seed.
        delay_seconds: Minimum wall-clock delay between page loads. This is a
            single-crawler delay, not a global rate limiter.
        wait_until: Playwright load state to wait for before extracting.
        timeout_ms: Per-navigation timeout. Falls back to the browser config.
        browser: A pre-started :class:`Browser` to reuse. When given, the
            crawler does **not** close it; the caller owns the lifecycle.
        config: :class:`BrowserConfig` used when the crawler owns a browser.
        on_page: Optional callback invoked after each page is processed.
        resume_path: Optional JSONL file. Visited URLs are appended as each
            page completes, and the same file is read at start-up so an
            interrupted crawl can continue without re-fetching.
    """

    def __init__(
        self,
        max_pages: int = 50,
        max_depth: int = 2,
        scope: Optional[CrawlScope] = None,
        delay_seconds: float = 0.0,
        wait_until: str = "load",
        timeout_ms: Optional[float] = None,
        browser: Optional[Browser] = None,
        config: Optional[BrowserConfig] = None,
        on_page: Optional[ProgressCallback] = None,
        resume_path: Optional[Union[str, Path]] = None,
    ) -> None:
        if delay_seconds < 0:
            raise ValueError(f"delay_seconds must be >= 0, got {delay_seconds!r}")
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.scope = scope or CrawlScope()
        self.delay_seconds = delay_seconds
        self.wait_until = wait_until
        self.timeout_ms = timeout_ms
        self._browser = browser
        self._owns_browser = browser is None
        self._config = config
        self.on_page = on_page
        self.resume_path = Path(resume_path) if resume_path else None
        self._cancelled = False
        self._resumed: set = set()

    # ------------------------------------------------------------- public API
    def cancel(self) -> None:
        """Request a graceful stop after the current page finishes."""
        self._cancelled = True

    def crawl(self, start_urls: Union[str, List[str]]) -> CrawlResult:
        """Crawl from ``start_urls`` and return a structured result.

        A failure on one page is recorded in the result and does not abort the
        run, except for browser-level failures (launch crashed), which
        propagate as :class:`BrowserError`.
        """
        seeds = [start_urls] if isinstance(start_urls, str) else list(start_urls)
        if not seeds:
            raise ValueError("crawl() requires at least one start URL")

        result = CrawlResult()
        started = time.perf_counter()
        self._cancelled = False

        queue = CrawlQueue(max_pages=self.max_pages, max_depth=self.max_depth)
        scope = self.scope.with_seed(seeds[0])
        # Previously completed URLs come from the JSONL resume file; they are
        # skipped during traversal but still counted as duplicates.
        self._resumed = self._read_resume()

        for url in seeds:
            self._enqueue(queue, result, scope, url, depth=0, parent=None)

        browser = self._browser or Browser(self._config)
        opened_here = self._browser is None
        if opened_here:
            browser.start()

        page: Optional[Page] = None
        last_request_at = 0.0
        try:
            page = browser.new_page()
            while not self._cancelled:
                item = queue.pop()
                if item is None:
                    break

                if self.delay_seconds and last_request_at:
                    remaining = self.delay_seconds - (time.perf_counter() - last_request_at)
                    if remaining > 0:
                        time.sleep(remaining)

                record = self._visit(page, item.url, item.depth, result, queue, scope)
                last_request_at = time.perf_counter()
                result.pages.append(record)
                if record.ok:
                    result.visited += 1
                else:
                    result.failed += 1
                self._write_resume(record)

                if self.on_page is not None:
                    try:
                        self.on_page(record, result)
                    except Exception:  # callback must never break the crawl
                        pass
        finally:
            if page is not None:
                page.close()
            if opened_here:
                browser.close()

        result.cancelled = self._cancelled
        result.elapsed_ms = (time.perf_counter() - started) * 1000
        return result

    # -------------------------------------------------------------- internals
    def _visit(
        self,
        page: Page,
        url: str,
        depth: int,
        result: CrawlResult,
        queue: CrawlQueue,
        scope: CrawlScope,
    ) -> CrawlPage:
        record = CrawlPage(url=url, depth=depth)
        started = time.perf_counter()
        try:
            page.goto(url, wait_until=self.wait_until, timeout=self.timeout_ms)  # type: ignore[arg-type]
            record.final_url = page.current_url()
            record.status = page.status
            record.title = page.title
            record.text = page.text()
        except BrowserError as exc:
            record.error = str(exc)
            result.errors.append(f"{url}: {exc}")
        except Exception as exc:  # unexpected: record, never abort the crawl
            record.error = f"unexpected error: {exc}"
            result.errors.append(f"{url}: unexpected error: {exc}")

        record.elapsed_ms = (time.perf_counter() - started) * 1000
        if not record.ok:
            return record

        # Always attempt to enqueue every discovered link and let the queue
        # classify the outcome. Guarding on ``depth < self.max_depth`` here
        # would make the queue's own depth check unreachable and leave
        # ``skipped_depth`` permanently zero.
        for link in self._safe_links(page):
            outcome = self._enqueue(
                queue, result, scope, link, depth=depth + 1, parent=url
            )
            record.links_found += 1
            if outcome == "ok":
                record.links_enqueued += 1
        return record

    @staticmethod
    def _safe_links(page: Page) -> List[str]:
        try:
            return [link.href for link in page.links() if link.href]
        except Exception:
            return []

    def _enqueue(
        self,
        queue: CrawlQueue,
        result: CrawlResult,
        scope: CrawlScope,
        raw_url: str,
        depth: int,
        parent: Optional[str],
    ) -> str:
        try:
            url = normalize_url(raw_url)
        except ValueError:
            result.skipped_offscope += 1
            return "offscope"
        if self._resumed and url in self._resumed:
            result.skipped_duplicate += 1
            return "duplicate"
        if not scope.allows(url):
            result.skipped_offscope += 1
            return "offscope"
        outcome = queue.push(url, depth, parent=parent)
        if outcome == "duplicate":
            result.skipped_duplicate += 1
        elif outcome == "depth":
            result.skipped_depth += 1
        elif outcome == "limit":
            result.skipped_limit += 1
        return outcome

    # ---------------------------------------------------------------- resume
    def _read_resume(self) -> set:
        if self.resume_path is None or not self.resume_path.is_file():
            return set()
        seen = set()
        try:
            for line in self.resume_path.read_text("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                url = row.get("url")
                if url:
                    seen.add(url)
        except OSError:
            return set()
        return seen

    def _write_resume(self, record: CrawlPage) -> None:
        if self.resume_path is None:
            return
        try:
            self.resume_path.parent.mkdir(parents=True, exist_ok=True)
            with self.resume_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")
        except OSError:
            # Resume is a convenience, never a reason to fail a crawl.
            pass
