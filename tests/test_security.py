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
