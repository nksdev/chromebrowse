"""Micro-benchmarks for the pure-Python hot paths.

These measure CPU-bound helpers only; they need no browser. Browser timings
are inherently machine- and network-dependent, so they are not asserted here.

Run with::

    python benchmarks/bench_extract.py
"""

from __future__ import annotations

import json
import timeit

from chromebrowse.crawl import CrawlScope, normalize_url
from chromebrowse.extract import (
    html_to_markdown,
    html_to_text,
    parse_jsonld,
    tables_from_raw,
)

HTML = "<html><body>" + "".join(
    f"<h2>Section {i}</h2><p>Paragraph <b>bold</b> and <i>italic</i> text.</p>"
    f"<ul><li>one</li><li>two</li></ul><a href='/p/{i}'>link</a>"
    for i in range(50)
) + "</body></html>"

URLS = [f"https://Example.COM:443/p/{i}?utm_source=x&b=2&a=1#frag" for i in range(100)]

RAW_TABLES = [
    {
        "index": 0,
        "caption": "c",
        "headers": ["a", "b"],
        "columns": 2,
        "rows": [[{"text": "a", "header": True}, {"text": "b", "header": True}]]
        + [
            [{"text": str(i), "header": False}, {"text": str(i * 2), "header": False}]
            for i in range(20)
        ],
    }
]

RAW_JSONLD = [
    {"index": i, "text": json.dumps({"@type": "Article", "name": f"n{i}"})}
    for i in range(20)
]


def bench(label, fn, number=1000):
    elapsed = timeit.timeit(fn, number=number)
    per_call = (elapsed / number) * 1_000_000
    print(f"{label:<24} {per_call:9.2f} us/call  ({number} calls)")
    return per_call


def main() -> None:
    print(f"HTML sample: {len(HTML)} bytes")
    print()
    bench("html_to_text", lambda: html_to_text(HTML), 200)
    bench("html_to_markdown", lambda: html_to_markdown(HTML), 200)
    bench("normalize_url x100", lambda: [normalize_url(u) for u in URLS], 200)
    scope = CrawlScope().with_seed("https://example.com/")
    bench("CrawlScope.allows x100", lambda: [scope.allows(u) for u in URLS], 200)
    bench("tables_from_raw", lambda: tables_from_raw(RAW_TABLES), 2000)
    bench("parse_jsonld", lambda: parse_jsonld(RAW_JSONLD), 2000)


if __name__ == "__main__":
    main()
