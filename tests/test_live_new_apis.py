'''Live coverage for the APIs added in this work.

Skipped unless CHROMEBROWSE_LIVE=1. All pages are data: URLs, so no
network access is required.
'''

import os
import urllib.parse

import pytest

LIVE = os.environ.get('CHROMEBROWSE_LIVE') == '1'

pytestmark = pytest.mark.skipif(not LIVE, reason='set CHROMEBROWSE_LIVE=1')


def data_url(html):
    return 'data:text/html;charset=utf-8,' + urllib.parse.quote(html)


TABLE_HTML = (
    '<html><body><table>'
    '<caption>Prices</caption>'
    '<tr><th>Name</th><th>Cost</th></tr>'
    '<tr><td>apple</td><td colspan=2>1</td></tr>'
    '</table></body></html>'
)

JSONLD_HTML = (
    '<html><head>'
    '<script type=application/ld+json>'
    '{"@type": "Article", "name": "x"}'
    '</script>'
    '<script type=application/ld+json>{not json</script>'
    '</head><body>hi</body></html>'
)


@pytest.fixture(scope='module')
def browser():
    from chromebrowse import Browser

    with Browser() as b:
        yield b


def test_tables_returns_models(browser):
    page = browser.open(data_url(TABLE_HTML))
    tables = page.tables()
    assert len(tables) == 1
    assert tables[0].caption == 'Prices'
    assert tables[0].headers == ['Name', 'Cost']
    assert tables[0].rows[1][1].colspan == 2
    assert [c.text for c in tables[0].data_rows[0]] == ['apple', '1']
    page.close()


def test_jsonld_keeps_good_block_after_bad(browser):
    page = browser.open(data_url(JSONLD_HTML))
    blocks = page.jsonld()
    assert len(blocks) == 2
    assert blocks[0].types == ['Article']
    assert blocks[0].error is None
    assert blocks[1].error is not None
    page.close()


def test_hooks_fire_on_navigate(browser):
    from chromebrowse import HookSet

    seen = []
    previous = browser.hooks
    browser.hooks = HookSet(
        after_navigate=lambda page, url, err: seen.append((url, err)),
        on_page_created=lambda page: seen.append(('created', page)),
    )
    try:
        page = browser.open(data_url('<html><body>ok</body></html>'))
        assert any(item[0] == 'created' for item in seen)
        nav = [item for item in seen if item[0] != 'created']
        assert nav
        assert nav[-1][1] is None
        assert nav[-1][0].startswith('data:')
        page.close()
    finally:
        browser.hooks = previous


def test_observe_network_records_document(browser, tmp_path):
    html = tmp_path / 'net.html'
    html.write_text('<html><body>net</body></html>', encoding='utf-8')
    page = browser.new_page()
    observer = page.observe_network(max_events=50)
    page.goto(html.as_uri())
    events = observer.events
    assert events, 'no events recorded'
    assert any(e.url.startswith('file:') for e in events)
    assert any(e.kind == 'request' for e in events)
    assert observer.dropped == 0
    observer.stop()
    observer.stop()
    page.close()
