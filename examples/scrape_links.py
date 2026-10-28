"""Discover and filter links from a page, exporting to JSON."""

import json
import sys
from urllib.parse import urlparse

from chromebrowse import Browser


def main(url: str = "https://example.com") -> None:
    with Browser() as browser:
        page = browser.open(url, wait_until="networkidle")
        links = page.links()

    # Keep only external links, de-duplicated, with readable labels.
    host = urlparse(url).netloc
    seen = set()
    rows = []
    for link in links:
        if link.href in seen:
            continue
        seen.add(link.href)
        if urlparse(link.href).netloc == host:
            continue
        rows.append({"text": link.text, "href": link.href})

    print(json.dumps(rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
