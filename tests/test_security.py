"""Tests for the opt-in public URL policy."""

import socket

import pytest

from chromebrowse.security import PublicURLRejected, validate_public_url


def _resolved(*addresses):
    return lambda host, port, type=socket.SOCK_STREAM: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
        for address in addresses
    ]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/html,hello",
        "ftp://example.com/file",
        "http://localhost/admin",
        "https://service.localhost/",
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://user:pass@example.com/",
        "https:///missing-host",
    ],
)
def test_public_policy_rejects_unsafe_url_forms(url):
    with pytest.raises(PublicURLRejected):
        validate_public_url(url, resolver=_resolved("8.8.8.8"))


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "fe80::1",
        "224.0.0.1",
        "192.0.2.1",
    ],
)
def test_public_policy_rejects_non_global_resolved_addresses(address):
    with pytest.raises(PublicURLRejected):
        validate_public_url("https://example.com/", resolver=_resolved(address))


def test_public_policy_rejects_mixed_public_and_private_dns_answers():
    with pytest.raises(PublicURLRejected):
        validate_public_url(
            "https://example.com/",
            resolver=_resolved("8.8.8.8", "192.168.1.10"),
        )


def test_public_policy_allows_public_http_and_https():
    validate_public_url("https://example.com/", resolver=_resolved("93.184.216.34"))
    validate_public_url("http://example.com:8080/path", resolver=_resolved("93.184.216.34"))


def test_public_policy_rejects_unresolvable_host():
    def fail(*args, **kwargs):
        raise socket.gaierror("not found")

    with pytest.raises(PublicURLRejected, match="safely resolved"):
        validate_public_url("https://does-not-resolve.invalid/", resolver=fail)



def test_router_aborts_a_request_rejected_by_public_policy(monkeypatch):
    from chromebrowse.browser import _request_router

    class FakeRoute:
        def __init__(self):
            self.aborted = None
            self.continued = False

        def abort(self, reason=None):
            self.aborted = reason

        def continue_(self):
            self.continued = True

    class FakeRequest:
        url = "http://127.0.0.1/admin"
        resource_type = "document"

    def reject(_url):
        raise PublicURLRejected("private address")

    monkeypatch.setattr("chromebrowse.security.validate_public_url", reject)
    route = FakeRoute()
    _request_router(
        route, FakeRequest(), public_only=True, block_images=False, blocked_types=set()
    )
    assert route.aborted == "blockedbyclient"
    assert route.continued is False


def test_public_only_rejects_file_navigation_before_playwright(monkeypatch):
    from chromebrowse.browser import Browser, Page
    from chromebrowse.config import BrowserConfig
    from chromebrowse.exceptions import NavigationError

    class FakePage:
        called = False

        def goto(self, *args, **kwargs):
            self.called = True

    browser = Browser(BrowserConfig(public_only=True))
    browser.config.executable_path = "unused"
    browser._started = True
    fake_page = FakePage()
    page = Page(browser, fake_page)

    with pytest.raises(NavigationError):
        browser._navigate(page, "file:///etc/passwd")

    assert fake_page.called is False



@pytest.mark.parametrize(
    "resource_type,block_images,blocked_types,expected_abort",
    [
        ("image", True, {"font"}, True),
        ("font", True, {"font"}, True),
        ("script", True, {"font"}, False),
    ],
)
def test_request_router_combines_resource_blocking(
    resource_type, block_images, blocked_types, expected_abort
):
    from chromebrowse.browser import _request_router

    class FakeRoute:
        def __init__(self):
            self.aborted = False
            self.continued = False

        def abort(self, reason=None):
            self.aborted = True

        def continue_(self):
            self.continued = True

    class FakeRequest:
        url = "https://example.com/asset"
        def __init__(self, kind):
            self.resource_type = kind

    route = FakeRoute()
    _request_router(
        route,
        FakeRequest(resource_type),
        public_only=False,
        block_images=block_images,
        blocked_types=blocked_types,
    )

    assert route.aborted is expected_abort
    assert route.continued is (not expected_abort)
