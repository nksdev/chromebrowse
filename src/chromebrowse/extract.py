"""JavaScript snippets and HTML helpers used for content extraction."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import List

# Extract readable text from a rendered document (runs in the browser).
EXTRACT_TEXT_JS = r"""
() => {
  const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','IFRAME','SVG','CANVAS']);
  const parts = [];
  const walk = (node) => {
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) {
      const t = node.nodeValue;
      if (t && t.trim()) parts.push(t.replace(/\s+/g, ' '));
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const tag = node.tagName.toUpperCase();
    if (SKIP.has(tag)) return;
    const style = window.getComputedStyle ? window.getComputedStyle(node) : null;
    if (style && (style.display === 'none' || style.visibility === 'hidden')) return;
    const isBlock = /^(P|DIV|SECTION|ARTICLE|HEADER|FOOTER|LI|UL|OL|H[1-6]|TR|BR|TABLE|PRE|BLOCKQUOTE)$/.test(tag);
    if (isBlock) parts.push('\n');
    for (const child of node.childNodes) walk(child);
    if (isBlock) parts.push('\n');
  };
  walk(document.body || document.documentElement);
  return parts.join('').replace(/[ \t]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}
"""

# Collect anchors with their metadata (runs in the browser).
EXTRACT_LINKS_JS = r"""
() => {
  const out = [];
  const anchors = document.querySelectorAll('a[href]');
  for (const a of anchors) {
    const href = a.getAttribute('href') || '';
    if (!href || href.startsWith('javascript:')) continue;
    out.push({
      href: href,
      text: (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim(),
      title: a.getAttribute('title') || '',
      rel: a.getAttribute('rel') || '',
      target: a.getAttribute('target') || '',
    });
  }
  return out;
}
"""

# Collect <meta> tags and common head metadata (runs in the browser).
EXTRACT_META_JS = r"""
() => {
  const meta = {};
  for (const m of document.querySelectorAll('meta')) {
    const key = m.getAttribute('name') || m.getAttribute('property') || m.getAttribute('http-equiv');
    const val = m.getAttribute('content');
    if (key && val !== null) meta[key] = val;
  }
  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical && canonical.href) meta['canonical'] = canonical.href;
  if (document.title) meta['title'] = document.title;
  return meta;
}
"""

_BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "footer", "li", "ul", "ol",
    "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "pre", "blockquote",
    "br", "hr", "form", "nav", "aside", "main", "figure", "figcaption",
}
_SKIP_TAGS = {"script", "style", "noscript", "template", "iframe", "svg", "canvas", "head"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.parts.append(text)
            self.parts.append(" ")

    def get_text(self) -> str:
        raw = "".join(self.parts)
        # Collapse horizontal whitespace but preserve paragraph/list boundaries.
        raw = re.sub(r"[ \t\f\v]+", " ", raw)
        raw = re.sub(r" *\n *", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    """Convert raw HTML to readable plain text without external dependencies."""
    if not html:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html).strip()
    return parser.get_text()


class _MarkdownExtractor(HTMLParser):
    """Small dependency-free HTML-to-Markdown converter."""

    _SKIP = {"script", "style", "noscript", "template", "iframe", "svg", "canvas", "head"}
    _BLOCK = {
        "address", "article", "aside", "div", "dl", "fieldset", "figcaption",
        "figure", "footer", "form", "header", "main", "nav", "p", "section",
        "table", "ul", "ol",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.skip_depth = 0
        self.pre_depth = 0
        self.lists: List[dict] = []
        self.wrappers = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        if tag in self._SKIP:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self._BLOCK:
            self.parts.append("\n\n")
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "hr":
            self.parts.append("\n\n---\n\n")
        elif tag == "pre":
            self.pre_depth += 1
            self.parts.append("\n\n" + chr(96) * 3 + "\n")
        elif tag == "code" and not self.pre_depth:
            self.wrappers.append((tag, len(self.parts), chr(96), chr(96)))
        elif tag in {"strong", "b"}:
            self.wrappers.append((tag, len(self.parts), "**", "**"))
        elif tag in {"em", "i"}:
            self.wrappers.append((tag, len(self.parts), "*", "*"))
        elif tag == "a" and attrs.get("href"):
            self.wrappers.append((tag, len(self.parts), "[", "](" + attrs["href"] + ")"))
        elif tag == "img":
            src = attrs.get("src", "")
            alt = attrs.get("alt", "")
            if src:
                self.parts.append(f"![{alt}]({src})")
        elif tag in {"ul", "ol"}:
            self.lists.append({"type": tag, "count": 0})
        elif tag == "li":
            if self.lists and self.lists[-1]["type"] == "ol":
                self.lists[-1]["count"] += 1
                self.parts.append(f"\n{self.lists[-1]['count']}. ")
            else:
                self.parts.append("\n- ")
        elif tag == "blockquote":
            self.parts.append("\n\n> ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._SKIP:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"a", "strong", "b", "em", "i", "code"}:
            for index in range(len(self.wrappers) - 1, -1, -1):
                wrapper_tag, start, prefix, suffix = self.wrappers[index]
                if wrapper_tag == tag:
                    inner = "".join(self.parts[start:])
                    del self.parts[start:]
                    self.parts.append(prefix + inner + suffix if inner else "")
                    del self.wrappers[index]
                    break
        elif tag == "pre":
            self.pre_depth = max(0, self.pre_depth - 1)
            self.parts.append("\n" + chr(96) * 3 + "\n\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n\n")
        elif tag == "li" or tag == "tr":
            self.parts.append("\n")
        elif tag in {"ul", "ol"}:
            if self.lists:
                self.lists.pop()
            self.parts.append("\n\n")
        elif tag in self._BLOCK or tag == "blockquote":
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        self.parts.append(data if self.pre_depth else re.sub(r"\s+", " ", data))


def html_to_markdown(html: str) -> str:
    """Convert HTML to approximate Markdown without external dependencies.

    Handles headings, paragraphs, links, ordered/unordered lists, emphasis,
    inline/preformatted code, horizontal rules, images, and HTML entities. It is
    intentionally not a full CommonMark implementation.
    """
    if not html:
        return ""
    parser = _MarkdownExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", "", html).strip()
    return "".join(parser.parts).strip()
