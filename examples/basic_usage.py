"""Basic chromebrowse usage: open a page, read it, screenshot it."""

from chromebrowse import Browser


def main() -> None:
    with Browser() as browser:
        page = browser.open("https://example.com")

        print("URL:", page.current_url())
        print("Status:", page.status)
        print("Title:", page.title)
        print("Load time: %.0f ms" % page.elapsed_ms)
        print()
        print(page.text()[:400])

        snap = page.snapshot("example.png", full_page=True)
        print("\nSaved screenshot to", snap.path)


if __name__ == "__main__":
    main()
