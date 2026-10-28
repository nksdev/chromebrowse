# chromebrowse User Guide

A practical guide to using `chromebrowse` as a reusable browser engine inside Python applications.

- [What it does](#what-it-does)
- [What it does not do](#what-it-does-not-do)
- [Install](#install)
- [Use it in any Python project](#use-it-in-any-python-project)
- [Capabilities and examples](#capabilities-and-examples)
- [Configuration](#configuration)
- [Keep a login session](#keep-a-login-session)
- [Use it from the command line](#use-it-from-the-command-line)
- [Integrate it into a web service](#integrate-it-into-a-web-service)
- [Errors and troubleshooting](#errors-and-troubleshooting)
- [Security and responsible use](#security-and-responsible-use)
- [Development and tests](#development-and-tests)

## What it does

`chromebrowse` is a Python library and command-line tool built on Playwright and Chromium. It gives another Python project a reusable way to open and render web pages, including JavaScript-driven pages, then inspect or interact with the rendered result.

Typical uses include:

- Extracting readable text, links, metadata, tables, and form values from pages.
- Capturing screenshots or PDFs of rendered pages.
- Clicking controls, filling forms, waiting for elements, and running page JavaScript.
- Reusing cookies and local storage through saved browser sessions.
- Automating repeatable browser workflows.
- Returning page content as structured Python objects or JSON from a CLI.
- Configuring browser behavior such as headless mode, timeouts, headers, proxy settings, viewport, locale, and blocked resources.

It is a convenience layer over Playwright, not a replacement for the browser engine.

## What it does not do

`chromebrowse` does not automatically provide a full web crawler, search engine, CAPTCHA solver, anti-bot bypass, proxy service, task scheduler, data warehouse, or an AI agent. Your application must define which sites to visit, what information to collect, and how to store or use results.

It does not guarantee that a website permits automated access or that every site will render identically. Login flows, bot checks, network failures, and site changes may require application-specific handling.

## Install

Use Python 3.9 or newer. Until a PyPI release is published, install from GitHub:

```bash
python -m pip install "git+https://github.com/nksdev/chromebrowse.git"
```

Install Chromium before running your first workflow if you prefer to prepare the browser explicitly:

```bash
python -m chromebrowse install
python -m chromebrowse --version
python -m chromebrowse info
```

The package can download Chromium automatically on first use when automatic installation is enabled. The browser binary is not bundled inside the Python package, so the first launch may require a browser download and network access.

## Use it in any Python project

Install the dependency in the same virtual environment as your application. Then import the public API where you need browser functionality.

For a `requirements.txt` file before PyPI publication:

```text
chromebrowse @ git+https://github.com/nksdev/chromebrowse.git
```

For a `pyproject.toml` project:

```toml
[project]
dependencies = [
    "chromebrowse @ git+https://github.com/nksdev/chromebrowse.git",
]
```

### Smallest working example

Create `read_page.py`:

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")
    print("Title:", page.title)
    print(page.text())
```

Run it:

```bash
python read_page.py
```

The `with Browser() as browser` context manager closes the browser when the block finishes, including when an exception occurs. Prefer this lifecycle pattern for scripts and short tasks.

### Return structured data

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")
    result = page.extract(
        include_markdown=True,
        include_links=True,
    )

    data = result.as_dict()
    print(data["title"])
    print(data["text"])
    print(data["markdown"])
    print(data["links"])
```

Use the resulting dictionary with your own JSON files, database layer, API response, or analysis pipeline. Your project is responsible for data validation, persistence, retries, and any business logic.

## Capabilities and examples

### 1. Render JavaScript-driven pages

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open(
        "https://example.com",
        wait_until="domcontentloaded",
    )
    page.wait_for("main")
    print(page.title)
    print(page.text())
```

Supported navigation wait states are `load`, `domcontentloaded`, `networkidle`, and `commit`. Choose the one appropriate for the target site; `networkidle` may be unsuitable for pages that maintain persistent network connections.

### 2. Extract links, metadata, and tables

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")

    links = [
        {"text": link.text, "url": link.href}
        for link in page.links()
    ]
    metadata = page.meta()
    tables = page.tables()

    print(links)
    print(metadata)
    print(tables)
```

For one table, use `page.table("table")`. Table extraction returns dictionaries containing headers, rows, and records. Check the target site's markup and validate the result before relying on it for critical data.

### 3. Find elements and interact with forms

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")

    if page.exists("input[name='q']"):
        page.fill("input[name='q']", "Python browser automation")
        page.press("Enter")
        page.wait_for("main")

    heading = page.find("h1", required=False)
    if heading is not None:
        print(heading.text())
```

The API supports CSS selectors through methods such as `find`, `find_all`, `exists`, `click`, `fill`, and `wait_for`. An element wrapper also supports actions such as `check`, `uncheck`, `select`, `hover`, `press`, and `scroll_into_view`.

Selectors are specific to each website and may need updating when the site's HTML changes.

### 4. Save screenshots or PDFs

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")
    page.snapshot("page.png", full_page=True)
    page.pdf("page.pdf")
```

To capture one element, use `page.snapshot("card.png", selector=".card")`. Screenshot output can also be returned as bytes by calling `page.snapshot()` without a path and inspecting the returned `Snapshot` object's `data` field.

### 5. Run JavaScript in the page

```python
from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")
    title = page.evaluate("document.title")
    paragraph_count = page.evaluate("document.querySelectorAll('p').length")
    print(title, paragraph_count)
```

Only run scripts you trust. JavaScript executes in the context of the loaded page and can interact with the page's data and state.

### 6. Batch several URLs

```python
from chromebrowse import Browser, BrowserError

urls = [
    "https://example.com",
    "https://example.org",
    "https://example.net",
]

results = []
with Browser() as browser:
    page = browser.new_page()
    for url in urls:
        try:
            page.goto(url, wait_until="domcontentloaded")
            results.append({
                "url": page.current_url(),
                "title": page.title,
                "text": page.text()[:2000],
                "ok": True,
            })
        except BrowserError as exc:
            results.append({"url": url, "error": str(exc), "ok": False})

print(results)
```

This simple loop reuses one tab. For production workloads, add appropriate timeouts, rate limits, retries, logging, and failure handling. Respect the target sites' policies and capacity.

## Configuration

Pass a `BrowserConfig` to control browser behavior:

```python
from chromebrowse import Browser, BrowserConfig

config = BrowserConfig(
    headless=True,
    viewport_width=1280,
    viewport_height=800,
    locale="en-US",
    timezone="UTC",
    block_images=True,
    default_timeout=30_000,
    navigation_timeout=45_000,
    auto_install=True,
)

with Browser(config) as browser:
    page = browser.open("https://example.com")
    print(page.title)
```

Common settings include:

| Setting | Purpose |
|---|---|
| `headless` | Run without a visible browser window when true. |
| `viewport_width`, `viewport_height` | Set the browser viewport dimensions. |
| `java_script_enabled` | Enable or disable page JavaScript. |
| `block_images` | Block image requests when they are not needed. |
| `block_resources` | Block selected resource types, such as media or fonts. |
| `default_timeout` | Default timeout for browser actions, in milliseconds. |
| `navigation_timeout` | Default navigation timeout, in milliseconds. |
| `user_agent` | Override the browser User-Agent. |
| `extra_headers` | Set extra HTTP headers. |
| `proxy` | Configure a proxy server URL. |
| `user_data_dir` | Use a persistent browser profile directory. |
| `executable_path` | Point to a specific browser executable. |
| `auto_install` | Permit automatic Chromium installation if needed. |
| `public_only` | Enable the opt-in public-URL filtering policy; this is not complete SSRF protection. |

Configuration can also be created from a dictionary with `BrowserConfig.from_dict(...)`. See the main [README](../README.md#configuration) and the `BrowserConfig` source for the full set of supported options.

## Keep a login session

Use `Session` to persist supported browser storage state, including cookies and local storage, between runs.

```python
from chromebrowse import Session

# First run: complete the site's authorized login flow, then save state.
with Session("my-dashboard") as session:
    session.open("https://example.com/login")
    # Add the site's own login steps here.
    session.save()

# Later run: reopen a page using the saved session.
with Session("my-dashboard") as session:
    page = session.open("https://example.com/dashboard")
    print(page.title)
```

The example deliberately leaves site-specific authentication steps to your application. Some sites also require session storage, device verification, or renewed authentication; a saved browser state does not guarantee a permanent login.

Treat session files as credentials: restrict file permissions, do not commit them to Git, do not print cookie values in logs, and do not share them.

The default state directory can be overridden with `CHROMEBROWSE_STATE_DIR`.

## Use it from the command line

The CLI is useful for manual checks, shell scripts, and quick debugging:

```bash
# Diagnostics and browser installation
chromebrowse info
chromebrowse install

# Read rendered text
chromebrowse text https://example.com

# Structured JSON (text, Markdown, links, and metadata)
chromebrowse fetch https://example.com --json

# List links
chromebrowse links https://example.com --json

# Screenshot or PDF
chromebrowse shot https://example.com page.png --full
chromebrowse pdf https://example.com page.pdf

# Evaluate a JavaScript expression
chromebrowse eval https://example.com "document.title"

# Explore interactively
chromebrowse open https://example.com --show
```

Run `chromebrowse --help` or `chromebrowse COMMAND --help` for available options.

## Integrate it into a web service

A web service can call chromebrowse from a route, background worker, or job queue. However, the library currently uses Playwright's **synchronous** API. Do not create a browser on one thread and operate or close it on another. In async frameworks such as FastAPI, keep browser operations on a dedicated worker thread or use an architecture designed around Playwright's async API.

For a public service that accepts user-supplied URLs, also add authentication, quotas, timeouts, rate limits, logging, and network egress restrictions. See [Security and responsible use](#security-and-responsible-use) before exposing browsing functionality to untrusted callers.

For substantial concurrent workloads, benchmark a bounded worker pool or queue rather than launching a new browser for every request. Browser processes consume memory and CPU.

## Errors and troubleshooting

The public API exposes `BrowserError` and more specific exceptions, including `BrowserLaunchError`, `ChromiumNotFoundError`, `NavigationError`, `ElementNotFoundError`, `ElementInteractionError`, and `BrowserTimeoutError`.

```python
from chromebrowse import Browser, BrowserError

try:
    with Browser() as browser:
        page = browser.open("https://example.com", timeout=15_000)
        print(page.title)
except BrowserError as exc:
    print(f"Browser operation failed: {exc}")
```

Useful checks:

- **Chromium not found:** run `chromebrowse install` or configure an available browser executable.
- **Importing the wrong checkout during development:** install the cloned project with `python -m pip install -e ".[dev]"` and inspect `python -c "import chromebrowse; print(chromebrowse.__file__)"`.
- **A selector is not found:** verify the selector against the rendered page and wait for the relevant element.
- **Navigation times out:** choose an appropriate `wait_until`, set a realistic timeout, and check network connectivity.
- **A live test is skipped:** the integration suite requires `CHROMEBROWSE_LIVE=1` and network/browser access.

## Security and responsible use

A browser can access network destinations and interact with logged-in websites. Treat URLs, page content, downloads, cookies, and storage state as untrusted or sensitive inputs.

- Only automate sites and accounts you are authorized to access.
- Follow site terms, applicable law, and rate limits.
- Do not expose an unrestricted URL-fetching endpoint to the public.
- `public_only=True` is defense in depth, **not a complete SSRF boundary**. DNS changes, redirects, and browser networking behavior can create gaps in URL-level filtering. Enforce outbound restrictions at the network or proxy layer and allowlist destinations where practical.
- Keep credentials and saved session state out of source control and logs.
- Validate extracted content before using it in security-sensitive or business-critical decisions.
- Do not treat page text or scripts from a website as trusted instructions for your own application.

## Development and tests

From a cloned repository:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
python -m pip install -e ".[dev]"

# Offline regression tests
python -m pytest tests/ --ignore=tests/test_live.py -v

# Live browser integration tests (network access required)
chromebrowse install
CHROMEBROWSE_LIVE=1 python -m pytest tests/test_live.py -v
```

The live tests are skipped by default. For the latest installation commands, examples, API reference, architecture, and publishing notes, see the [main README](../README.md).


## Network observation, structured data, and crawling

The core browser API remains backward compatible: `page.tables()` returns dictionaries with headers, rows, and records. For typed table models that preserve cell metadata such as `colspan` and `rowspan`, use `page.structured_tables()`.

```python
from chromebrowse import Browser, HookSet
from chromebrowse.crawl import Crawler

with Browser() as browser:
    browser.hooks = HookSet(
        after_navigate=lambda page, url, error: print(url, error)
    )
    page = browser.open("https://example.com")

    # Structured tables and JSON-LD
    for table in page.structured_tables():
        print(table.headers, [cell.text for cell in table.data_rows[0]])
    for block in page.jsonld():
        print(block.types, block.error)

    # Observe browser-level request/response events (not packet capture)
    observer = page.observe_network(resource_types={"xhr", "fetch"})
    page.reload()
    for response in observer.responses():
        print(response.status, response.url)
    observer.stop()

# Optional sequential browser-rendered crawl
result = Crawler(max_pages=20, max_depth=2, delay_seconds=0.5).crawl(
    "https://example.com"
)
print(result.visited, result.failed, result.skipped_offscope)
```

The network observer has bounded event storage and redacts sensitive headers by default. It does not provide full packet capture, HAR export, or WebSocket event coverage. The crawler is sequential, browser-rendered, and bounded by its configured scope and limits; crawl scope is not authorization and is not an SSRF boundary.

See [Network observation](NETWORK.md), [Crawler behavior](CRAWLING.md), [Architecture](ARCHITECTURE.md), and [Security guidance](SECURITY.md) for the module-specific API and limitations.
