# Crawling

`chromebrowse.crawl` is a small, composable crawler built **on top of** the
existing browser layer. It opens every page in Chromium, so it works on
JavaScript-heavy sites that a plain HTTP fetcher cannot see.

```python
from chromebrowse.crawl import Crawler

result = Crawler(max_pages=25, max_depth=2, delay_seconds=0.5).crawl(
    "https://example.com"
)
print(result.visited, "visited,", result.failed, "failed")
for page in result.pages:
    print(page.status, page.url, len(page.text))
```

## Scope

By default only the seed host is in scope. Widen it deliberately:

```python
from chromebrowse.crawl import Crawler, CrawlScope

scope = CrawlScope(
    allow_domains={"example.com"},
    same_domain_only=False,
    deny_pattern=r"/logout",
)
result = Crawler(max_pages=100, scope=scope).crawl("https://example.com")
```

Scope is a **safety and focus** control. It is not an authorization
mechanism, and it does not establish that a site permits crawling.

## Limits

| Option | Meaning |
|---|---|
| `max_pages` | Hard cap on unique URLs enqueued. Must be > 0. |
| `max_depth` | Seed = depth 0. Links from the seed = depth 1. |
| `delay_seconds` | Minimum gap between page loads in one crawler. |
| `wait_until` | Playwright load state before extraction. Default `load`. |
| `timeout_ms` | Per-navigation timeout; falls back to browser config. |

Deduplication is on a **normalized** URL: scheme and host lowercased,
default ports dropped, fragments removed, common tracking parameters
(`utm_*`, `fbclid`, `gclid`, ...) stripped, query parameters sorted.

## Failure handling

A page that fails to load is recorded with `error` set and `ok == False`.
It increments `CrawlResult.failed` and never aborts the run. Browser-level
failures (Chromium could not launch) propagate as `BrowserError`.

## Resume

Pass `resume_path` to append each completed page as one JSONL row:

```python
result = Crawler(resume_path="crawl.jsonl").crawl("https://example.com")
```

A re-run reads the same file and skips URLs already present. Corrupt lines
are ignored rather than failing the crawl.

## Cancellation

```python
crawler = Crawler(max_pages=1000)
crawler.cancel()  # from another thread, or from on_page
```

The current page always finishes; the loop stops before the next one.
`result.cancelled` reports whether cancellation took effect.

## Deliberately not implemented

- **HTTP-first fast path.** Fetching with `httpx` and only falling back to
  Chromium would be far faster for static sites, but it adds a dependency
  and a second code path that must independently handle redirects, cookies,
  and encoding. Deferred rather than half-built.
- **Concurrency.** One page, one sequence. Concurrency multiplies Chromium
  memory and complicates politeness guarantees.
- **`robots.txt` retrieval.** The crawler does not fetch or interpret it.
  Callers are responsible for respecting it.
- **Sitemap / `<link rel=next>` pagination heuristics.**
