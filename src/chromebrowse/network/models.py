"""Typed models describing observed browser network activity.

These are *observational* records built from Playwright request/response
objects. They are not a packet capture: the browser API does not expose TLS
details, HTTP/2 frame data, or raw bytes. See ``docs/SECURITY.md`` for the
visibility limits that callers must account for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Header names whose values are replaced before a record is exposed to user
# code, so credentials cannot leak into logs, results, or error reports.
SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        "x-api-key",
        "x-auth-token",
    }
)

REDACTED = "[redacted]"


def redact_headers(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Return a copy of ``headers`` with sensitive values replaced.

    Matching is case-insensitive because HTTP header names are.
    """
    if not headers:
        return {}
    out: Dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            out[key] = REDACTED
        else:
            out[key] = value
    return out


@dataclass
class RequestRecord:
    """A request as seen by the browser at the moment it was issued."""

    url: str
    method: str = "GET"
    resource_type: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    is_navigation_request: bool = False
    frame_url: str = ""
    timestamp: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "resource_type": self.resource_type,
            "headers": dict(self.headers),
            "is_navigation_request": self.is_navigation_request,
            "frame_url": self.frame_url,
            "timestamp": self.timestamp,
        }


@dataclass
class ResponseRecord:
    """A response paired with the request that produced it."""

    url: str
    status: int = 0
    status_text: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    method: str = "GET"
    resource_type: str = ""
    from_service_worker: bool = False
    request_timestamp: float = 0.0
    response_timestamp: float = 0.0

    @property
    def duration_ms(self) -> float:
        """Milliseconds between request issue and response receipt.

        This is wall-clock time as observed by the browser, not server time.
        """
        if not self.request_timestamp or not self.response_timestamp:
            return 0.0
        return max(0.0, (self.response_timestamp - self.request_timestamp) * 1000.0)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "status_text": self.status_text,
            "headers": dict(self.headers),
            "method": self.method,
            "resource_type": self.resource_type,
            "from_service_worker": self.from_service_worker,
            "request_timestamp": self.request_timestamp,
            "response_timestamp": self.response_timestamp,
            "duration_ms": self.duration_ms,
        }


@dataclass
class FailedRequestRecord:
    """A request that failed before a response was produced."""

    url: str
    method: str = "GET"
    resource_type: str = ""
    failure: str = ""
    timestamp: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "resource_type": self.resource_type,
            "failure": self.failure,
            "timestamp": self.timestamp,
        }


@dataclass
class NetworkEvent:
    """One observed network event of any kind.

    ``kind`` is ``"request"``, ``"response"`` or ``"failed"``; exactly one of
    ``request``, ``response`` and ``failed`` is populated accordingly.
    """

    kind: str
    request: Optional[RequestRecord] = None
    response: Optional[ResponseRecord] = None
    failed: Optional[FailedRequestRecord] = None

    @property
    def url(self) -> str:
        if self.request is not None:
            return self.request.url
        if self.response is not None:
            return self.response.url
        if self.failed is not None:
            return self.failed.url
        return ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "request": self.request.as_dict() if self.request else None,
            "response": self.response.as_dict() if self.response else None,
            "failed": self.failed.as_dict() if self.failed else None,
        }
