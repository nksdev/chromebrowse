"""Network observation API for chromebrowse.

Public surface::

    from chromebrowse.network import NetworkObserver, NetworkEvent

    observer = NetworkObserver(page._pw_page, domains={"example.com"})
    observer.start()
    ...
    observer.stop()

Most callers should use :meth:`chromebrowse.Page.observe_network` instead of
constructing an observer directly; it wires the page/context lifecycle for
them.
"""

from __future__ import annotations

from .models import (
    REDACTED,
    SENSITIVE_HEADERS,
    FailedRequestRecord,
    NetworkEvent,
    RequestRecord,
    ResponseRecord,
    redact_headers,
)
from .observer import NetworkObserver

__all__ = [
    "NetworkObserver",
    "NetworkEvent",
    "RequestRecord",
    "ResponseRecord",
    "FailedRequestRecord",
    "redact_headers",
    "SENSITIVE_HEADERS",
    "REDACTED",
]
