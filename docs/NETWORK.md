# Network observation

`Page.observe_network()` attaches a `NetworkObserver` and records
request, response and failure events.

```python
observer = page.observe_network(
    resource_types={"xhr", "fetch"},
    methods={"POST"},
    domains={"api.example.com"},
    max_events=200,
)
page.goto("https://example.com")
print(observer.responses())
print(observer.dropped)
observer.stop()
```

## Bounds

Events live in a bounded deque. When it is full the oldest event is
discarded and `dropped` increments, so "nothing happened" is
distinguishable from "recording stopped".

## Filters

`resource_types`, `methods`, `domains` (subdomain-aware) and
`url_pattern`. Filters combine with AND.

## Redaction

`redact=True` by default. Values of `authorization`, `cookie`,
`set-cookie`, `proxy-authorization`, `x-api-key`, `x-auth-token` become
`[redacted]`, matched case-insensitively. Name-based only: a token in a
query string is not detected.
