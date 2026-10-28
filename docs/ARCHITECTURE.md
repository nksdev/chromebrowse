# Architecture

```
Browser / Page / Element - high-level synchronous API
  +-- extract    pure HTML/JS extraction helpers
  +-- hooks      lifecycle extension points
  +-- network    request/response observation
  +-- crawl      crawler built on Browser/Page
  +-- session    login and storage state
  +-- config     BrowserConfig, Chromium discovery
  +-- exceptions error hierarchy
```

## Principles

1. One browser implementation. The crawler does not touch Playwright
   objects directly, so browser-layer fixes benefit every consumer.
2. Additive extension. New capability arrives as new modules, not as new
   required arguments. No public API was removed.
3. Pure helpers stay pure. extract.py functions take strings and return
   data, so they are testable without a browser.
4. Bounded by default. The network ring buffer has a dropped counter,
   Browser._pages prunes closed wrappers, and CrawlQueue refuses URLs
   past max_pages.

## Rendering and extraction split

EXTRACT_*_JS snippets run inside Chromium and return JSON-serialisable
values. The *_from_raw and parse_* functions turn those into dataclasses
in Python. DOM traversal is JavaScript because that is where the DOM is;
modelling is Python because that is where it is testable.

## Error model

BrowserError is the base. Navigation failures raise NavigationError. A
missing selector raises ElementNotFoundError. The crawler catches
BrowserError per page and records it on the CrawlPage; only launch
failures propagate out of crawl().

## Testing strategy

- Offline tests use fakes and need no Chromium.
- tests/test_live.py needs real Chromium, gated on CHROMEBROWSE_LIVE=1.
- CI runs the offline suite on 3 OS x 4 Python versions, the live suite
  on 3 OS, and a wheel build plus installed-wheel smoke test.
