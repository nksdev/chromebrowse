# User guide

Task-oriented walkthrough. For module internals see ARCHITECTURE.md.

## Open a page

from chromebrowse import Browser

with Browser() as browser:
    page = browser.open("https://example.com")
    print(page.status, page.title)
    print(page.text()[:200])

Browser and Page are both context managers. Closing a page twice is safe.

## Extract content

content = page.extract(include_html=True, include_markdown=True, include_links=True)
print(content.text)
for link in content.links[:5]:
    print(link.href, link.text)

## Structured data

for table in page.tables():
    print(table.headers, len(table.data_rows))
for block in page.jsonld():
    print(block.types, block.error)

Table cells keep colspan and rowspan. JSON-LD blocks are parsed one at a
time, so a malformed block records its error instead of discarding the
rest of the page data.

## Interact

page.fill("#email", "me@example.com")
page.click("button[type=submit]")
page.wait_for("h1")

page.find(sel) raises ElementNotFoundError when nothing matches.
page.exists(sel) returns a bool and never raises.

## Observe network traffic

See NETWORK.md. Headers are redacted by default.

## Crawl

See CRAWLING.md. The crawler is sequential and browser-rendered only.

## Hooks

from chromebrowse import Browser, HookSet

with Browser() as browser:
    browser.hooks = HookSet(after_navigate=lambda p, u, e: print(u, e))
    browser.open("https://example.com")

before_navigate is the only hook allowed to abort by raising.

## Limits worth knowing

- html_to_markdown is regex-based and approximate.
- Scope is not authorization and not SSRF protection. See SECURITY.md.
