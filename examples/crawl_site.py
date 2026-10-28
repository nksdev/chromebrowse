"""Crawl a small site and print a summary of each page."""

from chromebrowse.crawl import Crawler


def main() -> None:
    result = Crawler(max_pages=10, max_depth=2, delay_seconds=0.5).crawl(
        "https://example.com"
    )
    print(f"visited={result.visited} failed={result.failed} in {result.elapsed_ms:.0f} ms")
    for page in result.pages:
        state = "ok" if page.ok else f"error: {page.error}"
        print(f"  [{page.depth}] {page.status} {page.url} ({len(page.text)} chars, {state})")
    print("skipped:", result.as_dict()["skipped_offscope"], "offscope")


if __name__ == "__main__":
    main()
