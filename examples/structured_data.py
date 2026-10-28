"""Extract tables and JSON-LD structured data from a page."""

from chromebrowse import Browser


def main() -> None:
    with Browser() as browser:
        page = browser.open("https://example.com")
        for table in page.tables():
            print("table", table.index, table.headers, f"{len(table.data_rows)} data rows")
        for block in page.jsonld():
            if block.error:
                print("bad JSON-LD block", block.index, block.error)
            else:
                print("JSON-LD", block.types)


if __name__ == "__main__":
    main()
