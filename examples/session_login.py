"""Persistent session example: reuse cookies across separate runs."""

from chromebrowse import Session


def main() -> None:
    # First run: browse and persist state.
    with Session("demo") as s:
        s.open("https://example.com")
        print("First run URL:", s.page.current_url())
        print("Saved state to:", s.save())

    # Second run: state is loaded automatically on start.
    with Session("demo") as s:
        s.open("https://example.com")
        print("Second run cookies:", len(s.cookies()))


if __name__ == "__main__":
    main()
