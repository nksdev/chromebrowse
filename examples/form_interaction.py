"""Interact with a real form: fill fields, submit, read the result."""

from chromebrowse import Browser


def main() -> None:
    with Browser() as browser:
        page = browser.open("https://www.selenium.dev/selenium/web/web-form.html")
        print("Form page:", page.title)

        page.fill("input[name='my-text']", "chromebrowse")
        page.click("button[type='submit']")
        page.wait_for("#message")

        print("Result:", page.find("#message").text())
        print("Final URL:", page.current_url())


if __name__ == "__main__":
    main()
