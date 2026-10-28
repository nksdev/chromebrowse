"""Tests for dependency-free HTML extraction helpers."""

from chromebrowse.extract import html_to_markdown, html_to_text


def test_html_to_text_strips_tags_and_scripts():
    html = """
    <html><head><title>t</title><style>.a{color:red}</style></head>
    <body>
      <h1>Hello</h1>
      <script>var x = 1;</script>
      <p>World <b>bold</b> text.</p>
      <ul><li>one</li><li>two</li></ul>
    </body></html>
    """
    text = html_to_text(html)
    assert "Hello" in text
    assert "World" in text
    assert "bold" in text
    assert "one" in text
    assert "two" in text
    assert "var x" not in text
    assert "color:red" not in text
    assert "<p>" not in text


def test_html_to_text_empty():
    assert html_to_text("") == ""


def test_html_to_text_collapses_whitespace():
    assert html_to_text("<p>a   b\n\n\tc</p>") == "a b c"


def test_html_to_markdown_headings_and_links():
    md = html_to_markdown('<h2>Title</h2><p>See <a href="https://x.test">link</a></p>')
    assert "## Title" in md
    assert "[link](https://x.test)" in md


def test_html_to_markdown_lists_and_emphasis():
    md = html_to_markdown("<ul><li>a</li></ul><p><strong>B</strong> and <em>I</em></p>")
    assert "- a" in md
    assert "**B**" in md
    assert "*I*" in md


def test_html_to_markdown_empty():
    assert html_to_markdown("") == ""
