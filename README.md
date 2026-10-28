# chromebrowse

[![CI](https://github.com/nksdev/chromebrowse/actions/workflows/ci.yml/badge.svg)](https://github.com/nksdev/chromebrowse/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

A reusable, self-contained **Chromium browsing engine for Python**.

Give any Python project the ability to reach the internet, navigate sites,
render JavaScript pages, extract content, discover links, interact with
elements, take screenshots, and keep a login session - through a small Python
API or a command-line tool.

No paid APIs. No browser automation code to write yourself. No separate
Chromium install to manage.

---

## Contents

- [Why use this](#why-use-this)
- [Install](#install)
- [Add it to an existing project](#add-it-to-an-existing-project)
- [Five real-world examples](#five-real-world-examples)
- [API reference](#api-reference)
- [Command line](#command-line)
- [Recipes](#recipes)
- [Configuration](#configuration)
- [How Chromium is found](#how-chromium-is-found)
- [Architecture](#architecture)
- [Development](#development)
- [Publishing to PyPI](#publishing-to-pypi)
- [Licensing](#licensing)

---

## Why use this

Most "scrape a website in Python" advice breaks the moment the site renders with
JavaScript. The usual options each have a catch:

| Approach | What goes wrong |
|---|---|
| `requests` + `BeautifulSoup` | Returns an empty shell on React / Vue / Next.js sites |
| Selenium | Needs a driver binary, version matching, and a lot of boilerplate |
| Playwright directly | Excellent, but you rewrite session, extraction, and error handling in every project |
| Hosted scraping APIs | Cost money and send your traffic through a third party |

`chromebrowse` is a thin, opinionated layer over Playwright. The whole stack
stays open source and runs on your own machine, and the boilerplate you would
otherwise rewrite every time is already written.

Everything below is one import away:

| What you want | Python | CLI |
|---|---|---|
| Load a page and run its JavaScript | `browser.open(url)` | `chromebrowse text URL` |
| Read clean text | `page.text()` | `chromebrowse text URL` |
| Get structured data | `page.extract()` | `chromebrowse fetch URL --json` |
| Convert to Markdown | `page.markdown()` | `chromebrowse fetch URL --json` |
| List links | `page.links()` | `chromebrowse links URL` |
| Click, type, select | `page.click()` `page.fill()` | `chromebrowse open URL` |
| Screenshot | `page.snapshot()` | `chromebrowse shot URL out.png` |
| PDF | `page.pdf()` | `chromebrowse pdf URL out.pdf` |
| Run JavaScript | `page.evaluate()` | `chromebrowse eval URL "js"` |
| Read cookies | `page.cookies()` | `chromebrowse cookies URL` |
| Stay logged in | `Session("name")` | `chromebrowse session ...` |

---

## Install

```bash
pip install chromebrowse
```

Verify it works end to end:

```bash
python -c "from chromebrowse import Browser; b=Browser(); print(b.open('https://example.com').title); b.close()"
# Example Domain
```

**Requirements:** Python 3.9 or newer on macOS, Windows, or Linux. No browser
needs to be installed beforehand.

### What happens on first run

The first time you open a page, chromebrowse downloads Chromium for you
(~185 MB, once, into ./.browsers). You will see a progress bar. Every run
after that starts instantly.

### Download Chromium up front instead

Better for Docker images and CI, where you want the download at build time
rather than during the first request:

```bash
chromebrowse install                      # into ./.browsers
chromebrowse install --dir /opt/browsers   # into a specific folder
chromebrowse install --force               # re-download even if present
```

### Air-gapped machines

Download on a connected machine, copy the folder across, then point at the
binary:

```bash
chromebrowse install --dir ./browsers
# copy ./browsers to the target machine, then:
export CHROMEBROWSE_CHROMIUM=/path/to/browsers/chromium-*/chrome-*/chrome
```

### Opting out of the automatic download

```python
from chromebrowse import Browser, BrowserConfig

with Browser(BrowserConfig(auto_install=False)) as b:
    ...
```

You will then get ChromiumNotFoundError if no browser is present.
---

## Add it to an existing project

chromebrowse is an ordinary dependency. Pick whichever file your project already uses:

```bash
# requirements.txt
echo "chromebrowse>=0.1.0" >> requirements.txt

# Poetry
poetry add chromebrowse

# uv
uv add chromebrowse

# pipenv
pipenv install chromebrowse
```

Or in `pyproject.toml`:

```toml
[project]
dependencies = [
    "chromebrowse>=0.1.0",
]
```

Then import it wherever you need a browser:

```python
from chromebrowse import Browser
```

That is the entire integration. There is no server to run, no API key, no
background daemon, and no configuration file required.

> **Important for servers:** create **one** `Browser` when your app starts and
> reuse it for every request. Launching a browser costs ~300 ms and a few
> hundred MB, so doing it per request will not scale.

> **Security warning:** the `/read?url=...` example below enables `BrowserConfig(public_only=True)`, a defense-in-depth URL filter that restricts every browser request to HTTP/HTTPS and rejects non-global destination addresses. It is **not a complete SSRF boundary**: DNS can change between validation and Chromium's connection, and browser traffic can reach destinations through network behaviors outside URL parsing. For a public service, also enforce outbound network/firewall policy that blocks internal, loopback, link-local, metadata, and other restricted ranges; preferably allowlist destinations. The default remains unrestricted so authorized pentests and local labs continue to work.
---

## Five real-world examples

### Example 1 - Scrape a JavaScript-rendered listing

```python
from chromebrowse import Browser

with Browser() as b:
    page = b.open("https://news.ycombinator.com", wait_until="networkidle")

    for link in page.find_all(".titleline a")[:10]:
        print(link.text(), "->", link.attr("href"))
```

### Example 2 - Give a FastAPI service the ability to read a page

The synchronous Playwright API must be used from the thread that created it. This
example confines browser startup, requests, and shutdown to a single worker
thread. That keeps the example thread-safe, but requests are serialized. For
higher concurrency, build this service around Playwright's async API instead.
This is a demonstration, not a complete public-service deployment: add
authentication, rate limiting, request quotas, and operational monitoring before
exposing an endpoint to untrusted callers. `public_only=True` is not a substitute
for those controls or for network-level egress restrictions.

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, HTTPException
from chromebrowse import Browser, BrowserConfig, BrowserError

executor = ThreadPoolExecutor(max_workers=1)
browser = None


def read_page(url: str):
    page = None
    try:
        page = browser.open(url, wait_until="domcontentloaded", timeout=15_000)
        return {"title": page.title, "text": page.text()[:5000]}
    finally:
        if page is not None:
            page.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global browser
    loop = asyncio.get_running_loop()
    try:
        browser = await loop.run_in_executor(
            executor, lambda: Browser(BrowserConfig(public_only=True)).start()
        )
        yield
    finally:
        try:
            if browser is not None:
                await loop.run_in_executor(executor, browser.close)
        finally:
            executor.shutdown(wait=True)


app = FastAPI(lifespan=lifespan)


@app.get("/read")
async def read(url: str):
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(executor, partial(read_page, url))
    except BrowserError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```


### Example 3 - Turn a workflow into a command-line tool

```python
# myscraper/__main__.py
import json
import sys

from chromebrowse import Browser


def main() -> int:
    with Browser() as browser:
        content = browser.fetch(sys.argv[1], include_links=True)
    json.dump(content.as_dict(), sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```bash
python -m myscraper https://example.com > out.json
```

### Example 4 - Process many URLs without one failure killing the batch

```python
from chromebrowse import Browser, BrowserError

urls = ["https://example.com", "https://example.org", "https://example.net"]
results = []

with Browser() as b:
    page = b.new_page()   # reuse one tab for the whole batch

    for url in urls:
        try:
            page.goto(url, wait_until="domcontentloaded")
            results.append({"url": url, "title": page.title, "ok": True})
        except BrowserError as exc:
            results.append({"url": url, "error": str(exc), "ok": False})

print(results)
```

### Example 5 - Log in once, reuse the session forever

```python
from chromebrowse import Session

# Run 1 - log in, then persist cookies + localStorage
with Session("dashboard") as s:
    s.open("https://example.com/login")
    s.page.fill("#username", "me")
    s.page.fill("#password", "secret")
    s.page.click("button[type=submit]")
    s.page.wait_for("#account")
    s.save()

# Run 2 (cron, next day) - already logged in
with Session("dashboard") as s:
    page = s.open("https://example.com/reports")
    page.snapshot("report.png", full_page=True)
    print(page.text()[:2000])
```

Sessions are stored in a writable state directory chosen automatically.
Override it with `CHROMEBROWSE_STATE_DIR`.
---

## API reference

Four classes cover almost everything.

### `Browser` - owns the Chromium process

```python
from chromebrowse import Browser

b = Browser()                 # or Browser(BrowserConfig(...))
b.start()                     # optional; with Browser() does this

page = b.open("https://example.com")  # open a page and navigate
page = b.new_page()                    # blank tab
content = b.fetch("https://example.com")  # one-shot structured extraction
text = b.text("https://example.com")      # one-shot plain text
links = b.links("https://example.com")    # one-shot link list
info = b.info()                            # diagnostics

b.close()
```

Always prefer the context manager (`with Browser() as b:`), which closes
the browser even if your code raises.

### `Page` - one tab

```python
page.goto("https://example.com", wait_until="networkidle")

page.title          # <title> text
page.current_url()  # final URL after redirects
page.status         # HTTP status code

page.text()         # clean, readable text
page.html()         # raw HTML
page.markdown()     # Markdown
page.links()        # list of Link objects
page.meta()         # description, og:*, canonical, ...
page.extract()      # PageContent with all of the above

page.find("h1")     # first matching Element
page.find_all("a")  # list of Elements
page.exists("#cookie-bar")  # True / False

page.click("button.submit")
page.fill("input[name=q]", "python")
page.press("Enter")
page.wait_for("#results")
page.evaluate("document.querySelectorAll('p').length")
page.scroll_to_bottom()

page.snapshot("page.png", full_page=True)
page.pdf("page.pdf")

page.go_back()
page.go_forward()
page.reload()
page.close()
```

### `Element` - a matched DOM node

```python
el = page.find("a.next")

el.text()          # visible text
el.html()          # inner HTML
el.attr("href")   # any attribute
el.value()         # form value
el.is_visible()

el.click()
el.fill("hello")
el.type_text("slow typing")
el.check()
el.uncheck()
el.select("option-value")
el.hover()
el.scroll_into_view()
el.screenshot("element.png")
el.press("Enter")  # keyboard input
```

### `Session` - a browser that remembers

```python
from chromebrowse import Session

with Session("mysite") as s:
    s.open("https://example.com")
    s.page.click("#login")
    s.save()          # persist cookies + localStorage
    s.cookies()       # inspect them

with Session("mysite") as s:
    s.open("https://example.com/dashboard")  # already logged in
```

A `Session` exposes `.browser` and `.page`, so everything above
works inside it.

### Errors

All exceptions inherit from `BrowserError`:

```python
from chromebrowse import (
    BrowserError,            # base class
    BrowserLaunchError,      # Chromium failed to start
    ChromiumNotFoundError,   # no binary, and auto-install is off
    NavigationError,         # the page failed to load
    ElementNotFoundError,    # a selector matched nothing
    ElementInteractionError, # a matched element could not be interacted with
    BrowserTimeoutError,     # a wait timed out
    SessionError,            # session state problem
)
```

Catch `BrowserError` and you cover every failure this library raises.
---

## Command line

Installing the package also installs a `chromebrowse` command.

```bash
chromebrowse info       # what Chromium was found, plus versions
chromebrowse install    # download Chromium up front

chromebrowse text https://example.com
chromebrowse fetch https://example.com --json --links --html --markdown
chromebrowse links https://example.com --href-only
chromebrowse shot https://example.com page.png --full
chromebrowse pdf https://example.com page.pdf
chromebrowse eval https://example.com "document.title"
chromebrowse cookies https://example.com --json

chromebrowse session list
chromebrowse session show mysite --json
chromebrowse session clear mysite
chromebrowse session delete mysite
```

### Interactive browser

A REPL for exploring a site by hand - the fastest way to find the selectors
you need for a script:

```bash
chromebrowse open https://example.com --show
```

```
cb> title
Example Domain
cb> links
Learn more  https://iana.org/help/example-domains
cb> click a
at https://iana.org/help/example-domains
cb> shot here.png
saved here.png
cb> eval document.querySelectorAll("p").length
3
cb> goto https://example.org
at https://example.org/
cb> back
at https://example.com/
cb> quit
```

**Flags on most commands:** `--show` (visible window), `--no-js`,
`--timeout MS`, `--wait-until {load,domcontentloaded,networkidle,commit}`,
`--user-agent`, `--header K:V` (repeatable), `--proxy URL`.
---

## Recipes

**Wait for content that appears after the first paint**

```python
page.goto(url, wait_until="domcontentloaded")
page.wait_for(".results")      # wait for a selector
page.wait_for_load("networkidle")  # or wait for network silence
```

**Save a page as Markdown**

```python
open("page.md", "w").write(page.markdown())
```

**Extract much faster by skipping images**

```python
from chromebrowse import Browser, BrowserConfig

with Browser(BrowserConfig(block_images=True)) as b:
    ...
```

**Use a proxy and custom headers**

```python
cfg = BrowserConfig(
    proxy="http://user:pass@host:8080",
    extra_headers={"Accept-Language": "en-GB"},
)
```

**Watch the browser work (debugging)**

```python
with Browser(BrowserConfig(headless=False, slow_mo=250)) as b:
    ...
```

**Screenshot a single element**

```python
page.snapshot("card.png", selector=".product-card")
```

**Get JSON-safe output**

```python
import json
print(json.dumps(page.extract().as_dict(), indent=2))
```

---

## Configuration

```python
from chromebrowse import Browser, BrowserConfig

config = BrowserConfig(
    headless=True,               # False = visible window
    viewport_width=1280,
    viewport_height=800,
    locale="en-US",
    timezone="America/New_York",
    user_agent=None,             # use Playwright's Chromium-matched default
    java_script_enabled=True,    # False = faster, but no JS rendering
    block_images=False,          # True = much faster extraction
    block_resources=[],          # e.g. ["media", "font"]
    extra_headers={},
    proxy=None,                  # "http://host:port"
    default_timeout=30_000,      # ms
    navigation_timeout=45_000,   # ms
    slow_mo=0.0,                 # ms delay per action, for debugging
    user_data_dir=None,          # set to persist the profile
    downloads_path=None,
    args=[],
    auto_install=True,           # download Chromium if it is missing
    prompt_install=False,        # True = ask before downloading
    public_only=False,           # opt-in HTTP(S)/globally-routable URL filter
    install_dir=None,            # where auto_install puts Chromium
)

with Browser(config) as b:
    ...
```

It can also be built from a dict, which is handy for config files:

```python
cfg = BrowserConfig.from_dict({"headless": False, "block_images": True})
```

**Environment variables:**

| Variable | Purpose |
|---|---|
| `CHROMEBROWSE_CHROMIUM` | Path to a specific Chrome/Chromium binary |
| `CHROMEBROWSE_BROWSERS_DIR` | Where auto-install puts Chromium |
| `CHROMEBROWSE_STATE_DIR` | Where sessions are saved |
| `PLAYWRIGHT_BROWSERS_PATH` | Standard Playwright browser location |

---

### Public URL restriction (server-side defense in depth)

For services that browse URLs supplied by untrusted callers, enable the opt-in
policy:

```python
from chromebrowse import Browser, BrowserConfig

with Browser(BrowserConfig(public_only=True)) as browser:
    page = browser.open("https://example.com")
    print(page.title)
```

The policy checks the initial URL, redirects, and subresource requests; permits
only HTTP/HTTPS; rejects credentials, localhost names, and any host resolving
to a non-global IP address. It is disabled by default to preserve authorized
pentesting and local/private lab workflows.

**This policy alone does not guarantee SSRF protection.** DNS may change between
validation and Chromium's connection, and ordinary Playwright route interception
does not cover every browser networking mechanism (including WebSocket traffic).
Deployments accepting untrusted URLs must also enforce network-level egress
controls and should use an allowlist whenever possible. The `public_only` flag
is not a replacement for firewall or proxy isolation.

## How Chromium is found

At startup, in this order:

1. `executable_path` on your `BrowserConfig`
2. The `CHROMEBROWSE_CHROMIUM` environment variable
3. `CHROMEBROWSE_BROWSERS_DIR` / `PLAYWRIGHT_BROWSERS_PATH`
4. The project-local `./.browsers` folder (where `chromebrowse install` puts it)
5. The Playwright user cache
6. A system Chrome, Chromium, or Edge installation
7. **Otherwise: download automatically** (once, ~185 MB)

To see what it resolved to:

```bash
chromebrowse info
```
---

## Architecture

```
src/chromebrowse/
  __init__.py     public exports
  browser.py      Browser, Page, Element - the engine
  config.py       BrowserConfig, Chromium discovery and install
  extract.py      in-browser JS extractors, HTML to text / Markdown
  models.py       Link, PageContent, Snapshot
  session.py      persistent sessions
  cli.py          argparse CLI and interactive REPL
  exceptions.py   error hierarchy
```

It is layered so you can extend it without touching the core:

- **`Browser`** owns Playwright, the browser process, and the context.
- **`Page`** wraps one tab; all extraction and interaction lives here.
- **`Element`** wraps a Playwright locator with a friendlier API.
- **`Session`** layers persistence on top of `Browser`.
- **`extract.py`** is isolated - swap in your own parser freely.

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest                              # offline regression suite
CHROMEBROWSE_LIVE=1 pytest tests/test_live.py -v   # real browser (6 tests)
```

Runnable examples live in `examples/`:

```bash
python examples/basic_usage.py
python examples/form_interaction.py
python examples/scrape_links.py
python examples/session_login.py
```

---

## Publishing to PyPI

This repository ships `.github/workflows/publish.yml`, configured for PyPI
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) - no API token
is stored anywhere.

### One-time setup (do this first)

1. Go to <https://pypi.org/manage/account/publishing/> and add a **pending
   publisher**:
   - **PyPI Project Name:** `chromebrowse`
   - **Owner:** `nksdev`
   - **Repository name:** `chromebrowse`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
2. In the GitHub repo, create an environment named `pypi` under
   **Settings -> Environments** (no secrets needed).

### Publish a release

1. On GitHub, go to **Releases -> Draft a new release**.
2. Tag it `v0.1.0`, write notes, and click **Publish release**.
3. The workflow builds the wheel and sdist and uploads them to PyPI.

You can also run the **Publish** workflow manually from the Actions tab.

### Manual alternative, with twine

```bash
pip install build twine
python -m build
python -m twine check dist/*

# Test PyPI first - always a good idea
python -m twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ chromebrowse

# Then the real thing
python -m twine upload dist/*
```

After either route, anyone can `pip install chromebrowse` and the PyPI
badge at the top of this README will resolve.

---

## Licensing

chromebrowse is **MIT** licensed - free for commercial and closed-source use.

It depends on [Playwright](https://playwright.dev/python/) (Apache-2.0), which
drives Chromium (BSD-3-Clause). The binary Playwright downloads is "Chrome for
Testing," distributed by Google for testing purposes.

**No browser binary is bundled in this repository or in the PyPI package.** It
is downloaded on demand, which keeps installs small and attribution clean.

## Disclaimer

Respect the terms of service and `robots.txt` of the sites you browse, and
follow applicable law. You are responsible for how you use this tool.

## License

MIT - see [LICENSE](LICENSE).