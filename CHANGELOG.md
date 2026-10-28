# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `chromebrowse.network`: bounded, filterable network observation.
  `Page.observe_network()` returns a `NetworkObserver` backed by a ring
  buffer with `dropped` accounting. Filters by resource type, HTTP method,
  domain (subdomain-aware) and URL regex. Sensitive headers are redacted by
  default, case-insensitively.
- `chromebrowse.crawl`: a composable, browser-rendered crawler.
  URL normalization and deduplication, `CrawlScope` policy, a bounded
  `CrawlQueue`, structured `CrawlPage`/`CrawlResult` models, JSONL resume,
  cancellation, and per-request delay. Page failures are recorded and never
  abort a run.
- Structured extraction: `Page.tables()` and `Page.jsonld()`, with `Table`,
  `TableCell` and `JsonLdBlock` models. Table cells keep `colspan`/
  `rowspan`; JSON-LD blocks are parsed independently so one malformed block
  cannot discard the rest.
- `chromebrowse.hooks`: a `HookSet` wired into the browser lifecycle
  (`before_navigate`, `after_navigate`, `on_page_created`, `on_page_closed`,
  `on_response`, plus generic `(event, payload)` hooks).
- `docs/SECURITY.md`, `docs/CRAWLING.md`, `docs/USER_GUIDE.md`,
  `docs/ARCHITECTURE.md`, `docs/NETWORK.md`.
- Benchmarks for the CPU-bound extraction and crawl helpers.
- CI wheel build plus an installed-wheel smoke test.

### Fixed

- `BrowserConfig` validation: invalid viewport, timeout and `slow_mo` values
  now raise at construction with actionable messages instead of failing
  later inside Playwright. `config.py` was also missing the `Union` import
  used in a type annotation (a latent `NameError` under
  `from __future__ import annotations`).
- `Browser.load_state()` restored cookies but silently dropped the
  `origins`/localStorage section of a Playwright storage state, logging
  users out of token-based sessions. It now restores both, sharing the
  logic with `Session`.
- `Page.extract(include_markdown=True)` produced plain text instead of
  markdown because it called `html_to_text`.
- `Browser._pages` grew without bound: closed pages are now pruned in
  `new_page()`.
- `Page.close()` is now safe to call repeatedly and after browser shutdown.

### Changed

- `Page.snapshot` / `Page.screenshot` unchanged; no public API was removed.

## [0.1.0]

Initial public release: `Browser`, `Page`, `Element`, `Session`,
`BrowserConfig`, extraction helpers, and a CLI.
