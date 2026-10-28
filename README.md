# chromebrowse

[![CI](https://github.com/nksdev/chromebrowse/actions/workflows/ci.yml/badge.svg)](https://github.com/nksdev/chromebrowse/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

**A reusable Chromium browser toolkit for Python — built on Playwright.**

`chromebrowse` gives Python applications a consistent API for opening web pages, running JavaScript-rendered sites, extracting structured content, interacting with page elements, saving browser sessions, observing browser network events, and crawling pages within configured limits. Use it as a Python library or from the command line.

It runs locally on your machine. It does not require a paid scraping API or a separate browser-driver management workflow. On first use, it can download a compatible Chromium browser if one is not already available.

**New here?** Start with the [Quick start](#quick-start). For step-by-step examples, see the [User Guide](docs/USER_GUIDE.md). Before exposing URL browsing through a service, read the [Security Review](docs/SECURITY_REVIEW.md).

---

## Contents

- [What it is](#what-it-is)
- [Quick start](#quick-start)
- [Installation](#installation)
- [Capabilities](#capabilities)
- [Examples](#examples)
- [Command-line interface](#command-line-interface)
- [API overview](#api-overview)
- [Configuration](#configuration)
- [Security and responsible use](#security-and-responsible-use)
- [Documentation](#documentation)
- [Architecture](#architecture)
- [Development and tests](#development-and-tests)
- [Publishing](#publishing)
- [License](#license)

## What it is

`chromebrowse` is a **synchronous Python abstraction over Playwright and Chromium**. It handles common browser tasks behind reusable objects such as `Browser`, `Page`, `Element`, and `Session`, so application code does not have to repeatedly implement browser startup, page extraction, interactions, and session management.

It is useful when you need a real browser engine to work with sites that render content in JavaScript, rather than relying only on a direct HTTP request.

### What you can build with it

- **Browser-based extraction:** collect readable text, Markdown, links, metadata, HTML tables, form values, and JSON-LD data.
- **Browser automation:** click elements, fill fields, select options, wait for page elements, and execute JavaScript in the page.
- **Evidence capture:** save screenshots and PDFs of rendered pages.
- **Reusable login sessions:** persist browser state, including cookies and local storage, for later runs.
- **Network observation:** record filtered request, response, and failed-request metadata with bounded storage and header redaction.
- **Bounded crawling:** follow links with scope rules, depth/page limits, URL normalization, delays, resume support, and cancellation.
- **Integration:** use the same toolkit from ordinary Python code, scripts, command-line workflows, and carefully configured services.

### What it is not

`chromebrowse` is not a packet-capture tool, a full HTTP interception proxy, a distributed high-throughput crawler, or a complete vulnerability scanner. Its network observer records browser-exposed event metadata, not all network traffic or response bodies. Its URL restriction feature is a defense-in-depth measure, not a complete Server-Side Request Forgery (SSRF) boundary. It does not provide a built-in LLM agent, CAPTCHA-solving, or guaranteed anti-bot bypass.

The project builds on Playwright; it does not replace Chromium or the underlying browser automation engine.

## Quick start

### 1. Install the current GitHub version

Until a PyPI release is available, install directly from the repository:

```bash
python -m pip install "git+https://github.com/nksdev/chromebrowse.git"
```

### 2. Open a page and extract content

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")

    print("Title:", page.title)
    print("URL:", page.current_url())
    print(page.text()[:500])

    for link in page.links():
        print(link.text, link.href)
```

The context manager closes the browser when the block exits, including when an exception occurs.

### 3. Verify the installation

```bash
python -m chromebrowse --version
chromebrowse info
```

On first use, Chromium may be downloaded automatically. See [Installation](#installation) for browser setup, custom paths, and offline environments.

## Installation

### Requirements

- Python **3.9 or newer**
- macOS, Windows, or Linux
- Network access on first use if a compatible browser must be downloaded

Install the current repository version:

```bash
python -m pip install "git+https://github.com/nksdev/chromebrowse.git"
```

Once a release is published to PyPI, the package can be installed with:

```bash
python -m pip install chromebrowse
```

### Install Chromium explicitly

For Docker images, build pipelines, or controlled deployments, install the browser before running your application:

```bash
chromebrowse install
chromebrowse install --dir /opt/browsers
chromebrowse install --force
```

The first command uses the default browser cache. The second selects a directory. The third forces a re-download.

By default, the browser cache is stored under `~/.chromebrowse/browsers` in a writable home directory. You can change it with `CHROMEBROWSE_BROWSERS_DIR`.

### Use an existing browser or disable automatic installation

To select a specific Chromium-compatible browser, set `CHROMEBROWSE_CHROMIUM` to its executable path. To prevent automatic browser download:

```python
from chromebrowse import Browser, BrowserConfig

with Browser(BrowserConfig(auto_install=False)) as browser:
    page = browser.open("https://example.com")
    print(page.title)
```

If no compatible browser is found while automatic installation is disabled, startup raises `ChromiumNotFoundError`.

### Air-gapped environments

On a machine with internet access, download the browser into a directory:

```bash
chromebrowse install --dir ./browsers
```

Transfer that directory to the target machine, then point `CHROMEBROWSE_CHROMIUM` at the actual browser executable path printed by the installer. Browser and operating-system dependencies must still be compatible with the target machine.

### Google Colab

Colab runs cells inside an active asyncio event loop, while `chromebrowse` currently uses Playwright's synchronous API. Run the complete browser operation inside a worker thread:

```python
from concurrent.futures import ThreadPoolExecutor
from chromebrowse import Browser

def read_example():
    with Browser() as browser:
        page = browser.open("https://example.com")
        return {
            "title": page.title,
            "url": page.current_url(),
            "text": page.text(),
            "links": [
                {"text": link.text, "href": link.href}
                for link in page.links()
            ],
        }

with ThreadPoolExecutor(max_workers=1) as executor:
    result = executor.submit(read_example).result()

print(result["title"])
print(result["text"])
```

Keep creation, use, and shutdown of a given browser in the same worker thread. This workaround does not turn the synchronous API into an asynchronous API. Colab runtimes are temporary, so download any output files you need to keep.

## Capabilities

| Need | Python API | CLI |
|---|---|---|
| Open and render a page | `browser.open(url)` | `chromebrowse text URL` |
| Extract readable text | `page.text()` | `chromebrowse text URL` |
| Get structured page content | `page.extract()` or `browser.fetch(url)` | `chromebrowse fetch URL --json` |
| Convert a page to Markdown | `page.markdown()` | `chromebrowse fetch URL --markdown` |
| Find links | `page.links()` | `chromebrowse links URL` |
| Extract HTML tables | `page.tables()` | `chromebrowse fetch URL --json` |
| Read form values | `page.form_values()` | `chromebrowse open URL` |
| Click, type, or select | `page.click()`, `page.fill()`, `page.press()` | `chromebrowse open URL --show` |
| Capture a screenshot | `page.snapshot()` | `chromebrowse shot URL out.png` |
| Save a PDF | `page.pdf()` | `chromebrowse pdf URL out.pdf` |
| Execute page JavaScript | `page.evaluate()` | `chromebrowse eval URL "js"` |
| Inspect cookies | `page.cookies()` | `chromebrowse cookies URL` |
| Persist a logged-in session | `Session("name")` | `chromebrowse session ...` |
| Observe request/response metadata | `page.observe_network()` | — |
| Crawl linked pages | `Crawler(...).crawl(url)` | — |

## Examples

### Extract a JavaScript-rendered page

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open(
        "https://news.ycombinator.com",
        wait_until="networkidle",
    )

    for link in page.find_all(".titleline a")[:10]:
        print(link.text(), "->", link.attr("href"))
```

For structured output, use `page.extract()` or `browser.fetch(url)`. The returned content can be converted to a dictionary for JSON serialization.

### Observe browser network activity

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")
    observer = page.observe_network(
        resource_types={"xhr", "fetch"},
        max_events=200,
    )

    page.reload()

    for event in observer.events:
        record = event.request or event.response or event.failed
        method = record.method if record is not None else "?"
        print(event.kind, method, event.url)

    print("Events dropped because the buffer filled:", observer.dropped)
    observer.stop()
```

The observer has a bounded event buffer. Header redaction is enabled by default, but redaction is based on header names; secrets embedded in query strings or other values may still be recorded. See [Network observation](docs/NETWORK.md).

### Crawl pages within a limit

```python
from chromebrowse.crawl import Crawler

crawler = Crawler(
    max_pages=25,
    max_depth=2,
    delay_seconds=0.5,
)
result = crawler.crawl("https://example.com")

print(result.visited, "visited,", result.failed, "failed")
for page in result.pages:
    print(page.status, page.url, len(page.text))
```

The crawler renders each page in Chromium. By default, it stays within the seed host and applies page/depth limits and a delay. You can configure scope, resume output, callbacks, and cancellation. Scope controls are not authorization: only crawl systems you are allowed to access. See [Crawling](docs/CRAWLING.md).

### Reuse a login session

```python
from chromebrowse import Session

with Session("dashboard") as session:
    session.open("https://example.com/login")
    session.page.fill("#username", "YOUR_USERNAME")
    session.page.fill("#password", "YOUR_PASSWORD")
    session.page.click("button[type=submit]")
    session.page.wait_for("#account")
    session.save()

# A later run can reuse the stored browser state.
with Session("dashboard") as session:
    page = session.open("https://example.com/reports")
    print(page.text()[:2000])
```

Replace the placeholder values and selectors with those used by the site. Session files contain authentication material; store them in a protected directory and never commit them to source control. Set `CHROMEBROWSE_STATE_DIR` to change the session-state directory.

### Capture a screenshot or PDF

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")
    page.snapshot("page.png", full_page=True)
    page.pdf("page.pdf")
```

### Use it in an existing Python project

Install `chromebrowse` as a dependency, then import the API where you need it:

```bash
python -m pip install "git+https://github.com/nksdev/chromebrowse.git"
```

For a `requirements.txt` file, add:

```text
chromebrowse @ git+https://github.com/nksdev/chromebrowse.git
```

For `pyproject.toml` before a PyPI release:

```toml
[project]
dependencies = [
    "chromebrowse @ git+https://github.com/nksdev/chromebrowse.git",
]
```

For long-running applications, create and reuse a browser instance rather than launching a new browser for each request. Browser startup consumes time and memory. For a web service that accepts URLs from users, add authentication, rate limiting, quotas, monitoring, and network-level egress restrictions. The [User Guide](docs/USER_GUIDE.md) has a more complete FastAPI integration example and deployment notes.

## Command-line interface

Installing the package also installs the `chromebrowse` command.

### Common commands

```bash
# Diagnostics and browser setup
chromebrowse info
chromebrowse install

# Page content
chromebrowse text https://example.com
chromebrowse fetch https://example.com --json
chromebrowse fetch https://example.com --json --html
chromebrowse fetch https://example.com --markdown
chromebrowse links https://example.com --href-only

# Capture and evaluate
chromebrowse shot https://example.com page.png --full
chromebrowse pdf https://example.com page.pdf
chromebrowse eval https://example.com "document.title"
chromebrowse cookies https://example.com --json

# Persistent sessions
chromebrowse session list
chromebrowse session show mysite --json
chromebrowse session clear mysite
chromebrowse session delete mysite
```

### Interactive browser

Use the REPL to explore a site and discover selectors before writing a script:

```bash
chromebrowse open https://example.com --show
```

The interactive prompt supports commands such as `title`, `links`, `click`, `shot`, `eval`, `goto`, `back`, and `quit`. Run `chromebrowse --help` or the help output for a specific subcommand to see available options.

Common flags include `--show` for a visible browser window, `--no-js` to disable JavaScript, `--timeout MS`, `--wait-until`, `--user-agent`, repeatable `--header K:V`, and `--proxy URL`. Check `chromebrowse COMMAND --help` for exact syntax and supported options.

## API overview

The primary public objects are `Browser`, `Page`, `Element`, and `Session`.

### Browser

```python
from chromebrowse import Browser, BrowserConfig

with Browser(BrowserConfig(headless=True)) as browser:
    page = browser.open("https://example.com")
    blank_page = browser.new_page()

    content = browser.fetch("https://example.com")
    text = browser.text("https://example.com")
    links = browser.links("https://example.com")
    diagnostics = browser.info()
```

Use `with Browser() as browser` to ensure that the browser is closed when the block exits. If you manage lifecycle manually, call `start()` and `close()` as appropriate.

### Page

Common operations include:

```python
page.goto("https://example.com", wait_until="networkidle")

page.title          # title text
page.current_url()  # final URL after redirects
page.status         # HTTP status code

page.text()         # readable text
page.html()         # HTML
page.markdown()     # Markdown
page.links()        # Link objects
page.meta()         # description, Open Graph, canonical, etc.
page.tables()       # HTML tables
page.table("#data") # one table or ElementNotFoundError
page.form_values()  # input/select/textarea values
page.extract()      # structured PageContent

page.find("h1")                  # first matching Element
page.find("h1", required=False)  # None if absent
page.find_all("a")               # matching Elements
page.exists("#cookie-bar")       # True / False

page.click("button.submit")
page.fill("input[name=q]", "python")
page.press("Enter")
page.wait_for("#results")
page.evaluate("document.title")
page.scroll_to_bottom()

page.snapshot("page.png", full_page=True)
page.pdf("page.pdf")
```

### Element

```python
element = page.find("a.next")

element.text()
element.html()
element.attr("href")
element.value()
element.is_visible()

element.click()
element.fill("hello")
element.type_text("slow typing")
element.check()
element.uncheck()
element.select("option-value")
element.hover()
element.scroll_into_view()
element.screenshot("element.png")
element.press("Enter")
```

### Errors

Exceptions inherit from `BrowserError`. Common types include:

- `BrowserLaunchError` — Chromium could not start.
- `ChromiumNotFoundError` — no browser was found and automatic installation is disabled.
- `NavigationError` — navigation failed.
- `ElementNotFoundError` — a required selector did not match.
- `ElementInteractionError` — an element interaction failed.
- `BrowserTimeoutError` — an operation timed out.
- `SessionError` — session-state operation failed.

Catch `BrowserError` to handle the library's common browser exceptions. See the [User Guide](docs/USER_GUIDE.md) for error handling and troubleshooting.

## Configuration

`BrowserConfig` controls startup, browser behavior, timeouts, downloads, and URL restrictions.

```python
from chromebrowse import Browser, BrowserConfig

config = BrowserConfig(
    headless=True,
    viewport_width=1280,
    viewport_height=800,
    locale="en-US",
    timezone="America/New_York",
    java_script_enabled=True,
    block_images=False,
    block_resources=[],       # e.g. ["media", "font"]
    extra_headers={},
    proxy=None,
    default_timeout=30_000,   # milliseconds
    navigation_timeout=45_000,
    slow_mo=0.0,
    user_data_dir=None,
    downloads_path=None,
    auto_install=True,
    prompt_install=False,
    public_only=False,
)

with Browser(config) as browser:
    page = browser.open("https://example.com")
    print(page.title)
```

The API also supports constructing a configuration from a dictionary:

```python
cfg = BrowserConfig.from_dict({
    "headless": False,
    "block_images": True,
})
```

### Environment variables

| Variable | Purpose |
|---|---|
| `CHROMEBROWSE_CHROMIUM` | Path to a specific Chrome/Chromium executable |
| `CHROMEBROWSE_BROWSERS_DIR` | Directory for the managed browser download |
| `CHROMEBROWSE_STATE_DIR` | Directory for saved session state |
| `PLAYWRIGHT_BROWSERS_PATH` | Standard Playwright browser location |

### Browser discovery order

At startup, `chromebrowse` checks the configured executable path, `CHROMEBROWSE_CHROMIUM`, supported browser directories, the project-local `.browsers` directory, Playwright's browser cache, and compatible system browsers. If no compatible browser is found and automatic installation is enabled, it attempts to download one.

Run `chromebrowse info` to inspect the resolved browser and environment.

## Security and responsible use

Browser automation executes remote web content and can access network resources from the machine where it runs. Treat URLs, pages, scripts, browser state, and extracted data as untrusted input.

### Public URL restriction

For applications that browse URLs supplied by untrusted callers, `BrowserConfig(public_only=True)` enables an opt-in URL policy:

```python
from chromebrowse import Browser, BrowserConfig

with Browser(BrowserConfig(public_only=True)) as browser:
    page = browser.open("https://example.com")
    print(page.title)
```

The policy checks URLs and redirects, limits requests to HTTP/HTTPS, and rejects credentials, local host names, and hosts resolving to non-global IP addresses. It is intended as defense in depth and is disabled by default so authorized testing and private-lab workflows remain possible.

**This setting does not guarantee SSRF protection.** DNS may change between validation and connection, and browser routing does not cover every networking mechanism. Services exposed to untrusted callers must also enforce outbound network/firewall policy that blocks internal, loopback, link-local, cloud metadata, and other restricted destinations. Prefer explicit destination allowlists. Add authentication, quotas, rate limits, timeouts, and monitoring as appropriate.

### Additional precautions

- Use the tool only on sites and accounts you are authorized to access.
- Respect applicable law, site terms, and site crawling policies.
- Keep saved session state and cookies out of version control; they may grant account access.
- Do not assume network observation captures every request, response body, WebSocket frame, or cached/service-worker event.
- Network header redaction is name-based. Query-string secrets and other sensitive values may remain in recorded URLs or data.
- Treat page content as untrusted. Calling `page.evaluate()` executes JavaScript in the page and must not be used as a safe sandbox for arbitrary code.
- A crawler's scope and delay settings help control where and how quickly it visits pages; they do not establish authorization.

Read the [Security Review](docs/SECURITY_REVIEW.md) and [Security guide](docs/SECURITY.md) before deploying a browser service.

## Documentation

| Document | Purpose |
|---|---|
| [User Guide](docs/USER_GUIDE.md) | Step-by-step examples, API usage, sessions, configuration, CLI, troubleshooting, and integration |
| [Architecture](docs/ARCHITECTURE.md) | Module relationships, design principles, and testing strategy |
| [Network observation](docs/NETWORK.md) | Event types, filters, bounds, and redaction limitations |
| [Crawling](docs/CRAWLING.md) | Scope, queue limits, URL normalization, resume, failure handling, and cancellation |
| [Security](docs/SECURITY.md) | Authorization, SSRF considerations, and credential handling |
| [Security Review](docs/SECURITY_REVIEW.md) | Deployment risks and recommended mitigations |
| [Changelog](CHANGELOG.md) | Project changes and release notes |
| [Issues](https://github.com/nksdev/chromebrowse/issues) | Bug reports and feature requests |

## Architecture

The project separates the browser API from optional capabilities so the browser lifecycle and page behavior remain reusable:

```text
Browser / Page / Element
    |
    +-- Extraction       readable text, Markdown, links, metadata, tables
    +-- Hooks            lifecycle extension points
    +-- Network           bounded request/response/failure observation
    +-- Crawl             browser-rendered crawl, scope, queue, resume
    +-- Session           persistent browser state
    +-- Configuration     browser discovery, installation, timeouts, policy
    +-- CLI               commands and interactive REPL
    +-- Exceptions        consistent error hierarchy
```

Key design principles:

- **Compose rather than duplicate:** crawling uses the existing browser API.
- **Add features without replacing the core:** optional capabilities live in focused modules.
- **Keep extraction testable:** pure parsing and conversion helpers can be tested separately from browser execution.
- **Bound long-running work:** network observations have a capped buffer, and crawling enforces page/depth limits.
- **Make limitations explicit:** the network observer, crawler, and URL policy document their operating boundaries.

For implementation details, see [Architecture](docs/ARCHITECTURE.md).

## Development and tests

Clone the repository and install the package in editable mode with development dependencies:

```bash
git clone https://github.com/nksdev/chromebrowse.git
cd chromebrowse

python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate

python -m pip install -e ".[dev]"
```

### Run the offline test suite

These tests do not require a live website or a running Chromium browser:

```bash
python -m pytest tests/ --ignore=tests/test_live.py -v
```

### Run the live browser tests

Install Chromium and enable the live tests explicitly:

```bash
chromebrowse install
CHROMEBROWSE_LIVE=1 python -m pytest tests/test_live.py -v
```

Live tests require a browser binary and network access. The CI workflow also runs platform/Python test jobs and a distribution build/install smoke test. Check the current [CI workflow](.github/workflows/ci.yml) for the exact matrix.

Runnable examples are in `examples/`, including:

```bash
python examples/basic_usage.py
python examples/form_interaction.py
python examples/scrape_links.py
python examples/session_login.py
```

## Publishing

The repository includes a GitHub Actions workflow for publishing distributions to PyPI with [Trusted Publishing](https://docs.pypi.org/trusted-publishers/), avoiding a long-lived PyPI API token in repository secrets.

Before publishing, configure the matching PyPI trusted publisher and the repository's `pypi` GitHub Actions environment as described in the workflow. Then create a release using the tag and version intended for that release. Verify the CI results and distribution metadata before publishing.

To build and check distributions locally:

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

For a manual upload, configure credentials according to PyPI's current guidance and test the package on TestPyPI first. See [publish.yml](.github/workflows/publish.yml) and the official [Trusted Publishing documentation](https://docs.pypi.org/trusted-publishers/).

## License

`chromebrowse` is licensed under the [MIT License](LICENSE), allowing use in commercial and closed-source projects subject to the license terms.

It depends on [Playwright for Python](https://playwright.dev/python/) (Apache-2.0). Chromium/browser binaries are not bundled in this repository or in the package; a compatible browser is found locally or downloaded when required.

## Disclaimer

You are responsible for how you use this project. Use it only in ways that comply with applicable law, site terms, account permissions, and other relevant policies.
