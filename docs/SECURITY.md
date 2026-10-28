# Security and responsible use

chromebrowse drives a real Chromium browser. That makes it powerful, and it
means the security model is mostly *your* responsibility. This page is
explicit about what the library does and does not protect you from.

## Scope is not authorization

`CrawlScope` and `allow_domains` limit which URLs a crawl will visit. They
are **focus and blast-radius controls**, not authorization. Nothing in them
establishes that a site permits crawling, that the content is licensed for
reuse, or that your use complies with any law or terms of service.

## `public_only` / scope is not SSRF protection

If you accept URLs from untrusted users, scope filtering does **not** make
the request safe. Chromium will happily connect to:

- `http://127.0.0.1:...` and `http://localhost:...`
- link-local and metadata endpoints (for example `169.254.169.254`)
- private RFC1918 ranges reachable from the host

A hostname allow-list does not help either: DNS can resolve an allowed name
to a private address, and redirects can move you there after the check.

If you need SSRF protection you must add it yourself, at the network layer:
resolve the host, reject private and link-local addresses, re-check after
every redirect, and run the browser in a network namespace with no route to
internal services. Do not rely on this library for that.

## Network observation redacts by default

`Page.observe_network()` builds a `NetworkObserver` with `redact=True`.
Headers named in `SENSITIVE_HEADERS` (`authorization`, `cookie`,
`set-cookie`, `proxy-authorization`, `x-api-key`, `x-auth-token`) have their
values replaced with `[redacted]`. Header matching is case-insensitive.

Redaction is header-name based. It cannot know about a token passed in a
query string or a custom header with an unusual name. Treat observed events
as sensitive data and keep them out of logs you do not control.

## Storage state files contain credentials

`Browser.save_state()` writes cookies and localStorage. Those are live
session credentials. `Session` restricts the file to `0600` on a best-effort
basis, but the file is still plaintext on disk. Do not commit it, and do not
place it in a shared directory.

## Rendered content is untrusted input

Everything you extract — text, HTML, markdown, tables, JSON-LD — came from a
remote page. It is attacker-controlled until proven otherwise:

- Do not pass extracted HTML into an HTML sink without sanitizing it.
- Do not `eval` or otherwise execute extracted script text.
- Do not use extracted strings as shell arguments or file paths.
- JSON-LD is parsed with `json.loads` and never executed, but the resulting
  values are still untrusted data.

## Resource use

A crawl runs one Chromium page at a time. Bound it deliberately: set
`max_pages` and `max_depth`, and set `delay_seconds` so you do not hammer a
host. A run without limits can consume unbounded time and memory.

## Reporting a vulnerability

Open a private security advisory on the repository rather than a public
issue.
