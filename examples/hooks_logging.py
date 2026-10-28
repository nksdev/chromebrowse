"""Log every navigation using the extension-point hooks."""

from chromebrowse import Browser, HookSet


def main() -> None:
    def after_navigate(page, url, error):
        print("ok  " if error is None else "fail", url)

    with Browser() as browser:
        browser.hooks = HookSet(after_navigate=after_navigate)
        browser.open("https://example.com")
        browser.open("https://example.org")


if __name__ == "__main__":
    main()
