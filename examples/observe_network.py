"""Observe the XHR/fetch traffic a page makes while it loads."""

from chromebrowse import Browser


def main() -> None:
    with Browser() as browser:
        page = browser.new_page()
        observer = page.observe_network(resource_types={"xhr", "fetch"}, max_events=100)
        page.goto("https://example.com", wait_until="networkidle")
        for response in observer.responses():
            print(response.status, response.url, f"{response.duration_ms:.0f} ms")
        print("dropped:", observer.dropped)
        observer.stop()
        page.close()


if __name__ == "__main__":
    main()
