# chromebrowse

[![CI](https://github.com/your-org/chromebrowse/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/chromebrowse/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

A reusable, self-contained **Chromium-based browsing engine for Python**.

Give any Python project the ability to access the internet, navigate websites,
render JavaScript-driven pages, extract content, discover links, interact with
elements, capture screenshots, and persist browsing sessions — through a small
API or a command-line interface. No paid APIs. No browser code to write.


from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")
    print(page.title)
    print(page.text()[:500])
    page.screenshot("example.png")


---

## Features

| Capability | API | CLI |
|---|---|---|
| Render JavaScript-driven pages | `Browser.open()` | `chromebrowse text URL` |
| Extract clean text | `Page.text()` | `chromebrowse text URL` |
| Structured content (text/html/markdown/links/meta) | `Page.extract()` / `Browser.fetch()` | `chromebrowse fetch URL --json` |
| Discover links | `Page.links()` | `chromebrowse links URL` |
| Interact with elements | `Page.click/fill/select/hover` | `chromebrowse open URL` (REPL) |
| Screenshots | `Page.snapshot()` | `chromebrowse shot URL out.png` |
| PDF rendering | `Page.pdf()` | `chromebrowse pdf URL out.pdf` |
| Run JavaScript | `Page.evaluate()` | `chromebrowse eval URL "script"` |
| Persistent sessions / cookies | `Session` | `chromebrowse session ...` |
| Diagnostics | `Browser.info()` | `chromebrowse info` |

## Requirements

- Python 3.9+
- macOS, Windows, or Linux
- Chromium (downloaded automatically — see [Install](#install))

## Install


pip install chromebrowse


Then download the Chromium browser once:


chromebrowse install


This places Chromium in `./.browsers` (or `--dir PATH`) so the package is
fully self-contained and never depends on a system browser.

### How Chromium is located

At runtime `chromebrowse` searches, in order:

1. `CHROMEBROWSE_CHROMIUM` environment variable
2. Project-local `.browsers/` directory (from `chromebrowse install`)
3. `PLAYWRIGHT_BROWSERS_PATH`
4. The standard Playwright user cache
5. A system Chrome / Chromium / Edge installation

Check what it found with:


chromebrowse info


## Quick start (Python)


from chromebrowse import Browser

with Browser() as b:
    page = b.open("https://news.ycombinator.com", wait_until="networkidle")

    print(page.title)
    print(page.status)

    # Clean text (JS-rendered content included)
    print(page.text()[:1000])

    # Structured extraction
    content = page.extract(include_html=True, include_links=True)
    for link in content.links[:10]:
        print(link.text, "->", link.href)


### Element interaction


from chromebrowse import Browser

with Browser() as b:
    page = b.open("https://www.selenium.dev/selenium/web/web-form.html")

    page.fill("input[name='my-text']", "chromebrowse")
    page.click("button[type='submit']")
    page.wait_for("#message")

    print(page.find("#message").text())


### Screenshots and PDFs


with Browser() as b:
    page = b.open("https://example.com")

    page.snapshot("full.png", full_page=True)
    page.snapshot("element.png", selector="h1")
    page.snapshot("small.jpg", full_page=False, image_type="jpeg", quality=80)
    page.pdf("page.pdf")

    # Or capture into memory
    snap = page.snapshot(full_page=False)
    open("mem.png", "wb").write(snap.data)


### Persistent sessions


from chromebrowse import Session

with Session("mysite") as s:
    s.open("https://example.com/login")
    s.page.fill("#user", "me")
    s.page.fill("#pass", "secret")
    s.page.click("button[type=submit]")
    s.save()  # cookies + localStorage persisted

# Later run: state is restored automatically
with Session("mysite") as s:
    s.open("https://example.com/dashboard")


Session state lives in a writable directory chosen automatically, or set
`CHROMEBROWSE_STATE_DIR` to control it.

### Configuration


from chromebrowse import Browser, BrowserConfig

config = BrowserConfig(
    headless=False,            # visible window
    viewport_width=1920,
    viewport_height=1080,
    locale="en-GB",
    block_images=True,         # faster extraction
    extra_headers={"Accept-Language": "en"},
    navigation_timeout=60_000,
)

with Browser(config) as b:
    ...


## Command line


chromebrowse info
chromebrowse install

chromebrowse text https://example.com
chromebrowse fetch https://example.com --json --links --html
chromebrowse links https://example.com --href-only
chromebrowse shot https://example.com page.png --full
chromebrowse pdf https://example.com page.pdf
chromebrowse eval https://example.com "document.title"
chromebrowse cookies https://example.com --json

chromebrowse session list
chromebrowse session show mysite --json
chromebrowse session clear mysite
chromebrowse session delete mysite


### Interactive browser


chromebrowse open https://example.com



cb> title
Example Domain
cb> links
Learn more	https://iana.org/help/example-domains
cb> shot home.png
saved home.png
cb> goto https://example.org
at https://example.org/
cb> quit


Common flags available on most commands: `--show` (headful), `--no-js`,
`--timeout MS`, `--wait-until {load,domcontentloaded,networkidle,commit}`,
`--user-agent`, `--header K:V` (repeatable), `--proxy URL`.

## Architecture


src/chromebrowse/
├── __init__.py     public exports
├── browser.py      Browser, Page, Element (engine)
├── cli.py          argparse CLI + interactive REPL
├── config.py       BrowserConfig + cross-platform Chromium discovery
├── extract.py      in-browser JS extractors + HTML→text/Markdown
├── models.py       Link, PageContent, Snapshot dataclasses
├── session.py      persistent sessions, state registry
└── exceptions.py   error hierarchy


The design is layered so you can extend it without touching the engine:

- **`Browser`** owns the Playwright instance, browser, and context.
- **`Page`** wraps one tab and exposes extraction/interaction.
- **`Element`** wraps a locator with a friendly API.
- **`Session`** adds persistence on top of `Browser`.
- **`extract.py`** isolates parsing logic so you can swap in your own.

## Development


python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium

pytest                                        # offline tests
CHROMEBROWSE_LIVE=1 pytest tests/test_live.py -v   # real browser tests


## Notes on Chromium and licensing

`chromebrowse` is MIT licensed. It drives Chromium through
[Playwright](https://playwright.dev/python/) (Apache-2.0). Chromium itself is
open source under BSD-3-Clause; the prebuilt binary that Playwright downloads
("Chrome for Testing") is distributed by Google for automation and testing.

`chromebrowse` does **not** bundle any browser binary. Run
`chromebrowse install` to fetch one locally. That keeps this repository small
and keeps attribution clean.

## Disclaimer

Respect the terms of service and `robots.txt` of sites you browse, and follow
applicable laws. You are responsible for how you use this tool.

## License

MIT — see [LICENSE](LICENSE).
