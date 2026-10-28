"""JavaScript snippets and HTML helpers used for content extraction."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, List

# Extract readable text from a rendered document (runs in the browser).
EXTRACT_TEXT_JS = r"""
() => {
  const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','IFRAME','SVG','CANVAS']);
  const parts = [];
  const walk = (node) => {
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) {
      const t = node.nodeValue;
      if (t && t.trim()) parts.push(t.replace(/\s+/g, ' ').trim());
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
  return parts.join(' ').replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n\n').trim();
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
        # Collapse all runs of whitespace (including newlines) into single spaces.
        raw = re.sub(r"\s+", " ", raw)
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


def html_to_markdown(html: str) -> str:
    """Very small HTML-to-Markdown conversion (headings, links, lists, bold/italic)."""
    if not html:
        return ""
    s = html
    s = re.sub(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>", "", s)
    for level in range(1, 7):
        s = re.sub(rf"(?is)<h{level}[^>]*>(.*?)</h{level}>", lambda m, l=level: "\n" + "#" * l + " " + m.group(1).strip() + "\n", s)
    s = re.sub(r"(?is)<li[^>]*>(.*?)</li>", lambda m: "\n- " + m.group(1).strip(), s)
    s = re.sub(r"(?is)<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", lambda m: f"[{re.sub(r'<[^>]+>', '', m.group(2)).strip()}]({m.group(1)})", s)
    s = re.sub(r"(?is)<(strong|b)[^>]*>(.*?)</\1>", lambda m: f"**{m.group(2).strip()}**", s)
    s = re.sub(r"(?is)<(em|i)[^>]*>(.*?)</\1>", lambda m: f"*{m.group(2).strip()}*", s)
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)</(p|div|section|article|tr|blockquote)>\s*", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# Collect tables with cell spans, captions, and header detection (browser).
EXTRACT_TABLES_JS = r"""
() => {
  const out = [];
  const tables = document.querySelectorAll('table');
  tables.forEach((table, index) => {
    const caption = table.caption ? (table.caption.innerText || '').trim() : '';
    const rows = [];
    const headers = [];
    let columns = 0;
    for (const tr of table.querySelectorAll('tr')) {
      const cells = [];
      for (const cell of tr.querySelectorAll('th,td')) {
        const text = (cell.innerText || cell.textContent || '').replace(/\s+/g, ' ').trim();
        const header = cell.tagName.toUpperCase() === 'TH';
        cells.push({
          text: text,
          header: header,
          colspan: parseInt(cell.getAttribute('colspan') || '1', 10) || 1,
          rowspan: parseInt(cell.getAttribute('rowspan') || '1', 10) || 1,
        });
        if (header && rows.length === 0) headers.push(text);
      }
      if (cells.length) {
        rows.push(cells);
        columns = Math.max(columns, cells.length);
      }
    }
    out.push({ index: index, caption: caption, headers: headers, rows: rows, columns: columns });
  });
  return out;
}
"""

# Collect raw application/ld+json script text (browser).
EXTRACT_JSONLD_JS = r"""
() => {
  const out = [];
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');
  scripts.forEach((script, index) => {
    out.push({ index: index, text: script.textContent || '' });
  });
  return out;
}
"""


def tables_from_raw(raw: Any) -> List[Any]:
    """Build ``Table`` models from raw dicts returned by ``EXTRACT_TABLES_JS``.

    Missing keys are tolerated so a partially-supported browser or an older
    cached page cannot crash extraction.
    """
    from .models import Table, TableCell

    if not raw:
        return []
    tables: List[Table] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        rows: List[List[TableCell]] = []
        for row in entry.get("rows") or []:
            cells: List[TableCell] = []
            for cell in row or []:
                if not isinstance(cell, dict):
                    continue
                cells.append(
                    TableCell(
                        text=str(cell.get("text") or ""),
                        header=bool(cell.get("header")),
                        colspan=int(cell.get("colspan") or 1),
                        rowspan=int(cell.get("rowspan") or 1),
                    )
                )
            rows.append(cells)
        tables.append(
            Table(
                index=int(entry.get("index") or 0),
                caption=str(entry.get("caption") or ""),
                headers=[str(h) for h in (entry.get("headers") or [])],
                rows=rows,
                columns=int(entry.get("columns") or 0),
            )
        )
    return tables


def parse_jsonld(raw: Any) -> List[Any]:
    """Parse raw ``application/ld+json`` blocks into ``JsonLdBlock`` models.

    Each block is parsed independently: one malformed block is recorded with
    ``error`` set and does not discard the page's other structured data.
    Blank blocks are skipped entirely.
    """
    import json as _json

    from .models import JsonLdBlock

    if not raw:
        return []
    blocks: List[JsonLdBlock] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        index = int(entry.get("index") or 0)
        try:
            blocks.append(JsonLdBlock(index=index, data=_json.loads(text)))
        except Exception as exc:
            blocks.append(JsonLdBlock(index=index, data=None, error=str(exc)))
    return blocks
