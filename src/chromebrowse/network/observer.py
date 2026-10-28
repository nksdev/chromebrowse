"""Bounded, filterable observation of browser network activity.

``NetworkObserver`` attaches Playwright event handlers to a page (or a
whole browser context) and records structured, redacted ``NetworkEvent``
objects. It is deliberately bounded: events are stored in a ring buffer of
``max_events`` entries, so a long-lived page cannot exhaust memory.

This is not a packet capture or an interception proxy. Playwright exposes
request/response metadata, not transport bytes, and some traffic (service
workers, cached responses, WebSocket frames) is only partially visible.
See ``docs/NETWORK.md`` for the precise limits.
"""

from __future__ import annotations

import re
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Pattern, Sequence, Union

from .models import (
    FailedRequestRecord,
    NetworkEvent,
    RequestRecord,
    ResponseRecord,
    redact_headers,
)

EventCallback = Callable[[NetworkEvent], None]


class NetworkObserver:
    """Observe requests, responses and failures for one page or context.

    Handlers are attached on :meth:`start` (or by :meth:`Page.observe_network`)
    and detached by :meth:`stop`. Calling :meth:`start` twice is a no-op, so
    duplicate event registration cannot occur.

    Example::

        with browser.open("https://example.com") as page:
            observer = page.observe_network(resource_types={"xhr", "fetch"})
            page.click("#load-more")
            for event in observer.events:
                print(event.kind, event.url)
            observer.stop()
    """

    def __init__(
        self,
        target: Any,
        *,
        resource_types: Optional[Iterable[str]] = None,
        methods: Optional[Iterable[str]] = None,
        domains: Optional[Iterable[str]] = None,
        url_pattern: Optional[Union[str, Pattern[str]]] = None,
        max_events: int = 500,
        redact: bool = True,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        if max_events <= 0:
            raise ValueError(f"max_events must be > 0, got {max_events!r}")
        self._target = target
        self._resource_types = {t.lower() for t in resource_types} if resource_types else None
        self._methods = {m.upper() for m in methods} if methods else None
        self._domains = {d.lower().lstrip(".") for d in domains} if domains else None
        if isinstance(url_pattern, str):
            self._url_re: Optional[Pattern[str]] = re.compile(url_pattern)
        else:
            self._url_re = url_pattern
        self._max_events = max_events
        self._redact = redact
        self._on_event = on_event

        self._events: Deque[NetworkEvent] = deque(maxlen=max_events)
        self._requests: Dict[Any, RequestRecord] = {}
        self._started = False
        self.dropped = 0

    # ------------------------------------------------------------- lifecycle
    def start(self) -> "NetworkObserver":
        """Attach handlers. Idempotent."""
        if self._started:
            return self
        self._target.on("request", self._handle_request)
        self._target.on("response", self._handle_response)
        self._target.on("requestfailed", self._handle_failed)
        try:
            self._target.on("close", self._handle_close)
        except Exception:  # pragma: no cover - some mocks do not support it
            pass
        self._started = True
        return self

    def stop(self) -> None:
        """Detach handlers. Idempotent and safe after the page closed."""
        if not self._started:
            return
        for event, handler in (
            ("request", self._handle_request),
            ("response", self._handle_response),
            ("requestfailed", self._handle_failed),
        ):
            try:
                self._target.remove_listener(event, handler)
            except Exception:
                pass
        self._started = False
        self._requests.clear()

    def _handle_close(self, *_args: Any) -> None:
        self.stop()

    @property
    def started(self) -> bool:
        return self._started

    # ------------------------------------------------------------- accessors
    @property
    def events(self) -> List[NetworkEvent]:
        """Snapshot of retained events, oldest first."""
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()
        self._requests.clear()
        self.dropped = 0

    def requests(self) -> List[RequestRecord]:
        return [e.request for e in self._events if e.request is not None]

    def responses(self) -> List[ResponseRecord]:
        return [e.response for e in self._events if e.response is not None]

    def failures(self) -> List[FailedRequestRecord]:
        return [e.failed for e in self._events if e.failed is not None]

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.as_dict() for e in self._events]

    # -------------------------------------------------------------- filtering
    def _matches(self, url: str, method: str, resource_type: str) -> bool:
        if self._resource_types is not None and resource_type.lower() not in self._resource_types:
            return False
        if self._methods is not None and method.upper() not in self._methods:
            return False
        if self._domains is not None:
            host = _host_of(url)
            if not any(host == d or host.endswith("." + d) for d in self._domains):
                return False
        if self._url_re is not None and not self._url_re.search(url):
            return False
        return True

    # --------------------------------------------------------------- handlers
    def _handle_request(self, request: Any) -> None:
        try:
            url = request.url
            method = request.method
            resource_type = getattr(request, "resource_type", "") or ""
            if not self._matches(url, method, resource_type):
                return
            record = RequestRecord(
                url=url,
                method=method,
                resource_type=resource_type,
                headers=self._headers(getattr(request, "headers", {}) or {}),
                is_navigation_request=bool(getattr(request, "is_navigation_request", lambda: False)()),
                frame_url=_frame_url(request),
                timestamp=time.time(),
            )
            self._requests[id(request)] = record
            self._emit(NetworkEvent(kind="request", request=record))
        except Exception:
            # A malformed event must never break the caller's page.
            self.dropped += 1

    def _handle_response(self, response: Any) -> None:
        try:
            request = getattr(response, "request", None)
            req_record = self._requests.pop(id(request), None) if request is not None else None
            url = response.url
            method = getattr(request, "method", "GET") if request is not None else "GET"
            resource_type = getattr(request, "resource_type", "") if request is not None else ""
            if not self._matches(url, method, resource_type):
                return
            record = ResponseRecord(
                url=url,
                status=int(getattr(response, "status", 0) or 0),
                status_text=getattr(response, "status_text", "") or "",
                headers=self._headers(getattr(response, "headers", {}) or {}),
                method=method,
                resource_type=resource_type,
                from_service_worker=bool(getattr(response, "from_service_worker", False)),
                request_timestamp=req_record.timestamp if req_record else 0.0,
                response_timestamp=time.time(),
            )
            self._emit(NetworkEvent(kind="response", response=record))
        except Exception:
            self.dropped += 1

    def _handle_failed(self, request: Any) -> None:
        try:
            url = request.url
            method = request.method
            resource_type = getattr(request, "resource_type", "") or ""
            self._requests.pop(id(request), None)
            if not self._matches(url, method, resource_type):
                return
            failure = getattr(request, "failure", None)
            if callable(failure):
                failure = failure()
            record = FailedRequestRecord(
                url=url,
                method=method,
                resource_type=resource_type,
                failure=str(failure or "unknown"),
                timestamp=time.time(),
            )
            self._emit(NetworkEvent(kind="failed", failed=record))
        except Exception:
            self.dropped += 1

    # ---------------------------------------------------------------- helpers
    def _headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        return redact_headers(headers) if self._redact else dict(headers)

    def _emit(self, event: NetworkEvent) -> None:
        if len(self._events) == self._max_events:
            self.dropped += 1
        self._events.append(event)
        if self._on_event is not None:
            try:
                self._on_event(event)
            except Exception:
                pass


def _host_of(url: str) -> str:
    try:
        from urllib.parse import urlsplit

        return (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""


def _frame_url(request: Any) -> str:
    try:
        frame = request.frame
        return frame.url if frame is not None else ""
    except Exception:
        return ""
