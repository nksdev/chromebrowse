"""Unit tests for the network observation API (no browser required)."""

import pytest

from chromebrowse.network import (
    REDACTED,
    NetworkObserver,
    NetworkEvent,
    RequestRecord,
    ResponseRecord,
    FailedRequestRecord,
    redact_headers,
)


class FakeRequest:
    def __init__(self, url="https://x.test/a", method="GET", resource_type="document", headers=None, nav=False):
        self.url = url
        self.method = method
        self.resource_type = resource_type
        self.headers = headers or {}
        self._nav = nav

    def is_navigation_request(self):
        return self._nav

    @property
    def frame(self):
        return None


class FakeResponse:
    def __init__(self, request, url=None, status=200, headers=None):
        self.request = request
        self.url = url or request.url
        self.status = status
        self.status_text = "OK"
        self.headers = headers or {}
        self.from_service_worker = False


class FakePage:
    """Minimal Playwright-page stand-in that records handler registration."""

    def __init__(self):
        self.handlers = {}

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event, handler):
        self.handlers.get(event, []).remove(handler)

    def emit(self, event, payload):
        for h in list(self.handlers.get(event, [])):
            h(payload)


# ---------------------------------------------------------------- redaction

def test_redact_headers_is_case_insensitive():
    out = redact_headers({"Authorization": "Bearer t", "Cookie": "a=b", "Accept": "*/*"})
    assert out["Authorization"] == REDACTED
    assert out["Cookie"] == REDACTED
    assert out["Accept"] == "*/*"


def test_redact_headers_none():
    assert redact_headers(None) == {}


def test_redact_headers_does_not_mutate_input():
    src = {"authorization": "secret"}
    redact_headers(src)
    assert src["authorization"] == "secret"


# -------------------------------------------------------------- event flow

def test_observer_records_request_and_response():
    page = FakePage()
    obs = NetworkObserver(page).start()
    req = FakeRequest(url="https://x.test/a", method="POST", headers={"authorization": "tok"})
    page.emit("request", req)
    page.emit("response", FakeResponse(req, status=201))

    events = obs.events
    assert [e.kind for e in events] == ["request", "response"]
    assert events[0].request.method == "POST"
    assert events[0].request.headers["authorization"] == REDACTED
    assert events[1].response.status == 201
    assert events[1].response.method == "POST"


def test_observer_records_failed_request():
    page = FakePage()
    obs = NetworkObserver(page).start()
    req = FakeRequest(url="https://x.test/broken")
    req.failure = "net::ERR_CONNECTION_REFUSED"
    page.emit("requestfailed", req)

    failures = obs.failures()
    assert len(failures) == 1
    assert "ERR_CONNECTION_REFUSED" in failures[0].failure


def test_observer_start_is_idempotent():
    page = FakePage()
    obs = NetworkObserver(page)
    obs.start().start()
    assert len(page.handlers["request"]) == 1
    assert len(page.handlers["response"]) == 1


def test_observer_stop_detaches_handlers():
    page = FakePage()
    obs = NetworkObserver(page).start()
    obs.stop()
    assert page.handlers["request"] == []
    page.emit("request", FakeRequest())
    assert obs.events == []


def test_observer_stop_is_idempotent():
    page = FakePage()
    obs = NetworkObserver(page).start()
    obs.stop()
    obs.stop()


def test_observer_stops_on_page_close():
    page = FakePage()
    obs = NetworkObserver(page).start()
    page.emit("close", None)
    assert obs.started is False


# ---------------------------------------------------------------- filtering

def test_filter_by_resource_type():
    page = FakePage()
    obs = NetworkObserver(page, resource_types={"xhr", "fetch"}).start()
    page.emit("request", FakeRequest(url="https://x.test/doc", resource_type="document"))
    page.emit("request", FakeRequest(url="https://x.test/api", resource_type="xhr"))
    assert [e.url for e in obs.events] == ["https://x.test/api"]


def test_filter_by_method():
    page = FakePage()
    obs = NetworkObserver(page, methods={"post"}).start()
    page.emit("request", FakeRequest(url="https://x.test/a", method="GET"))
    page.emit("request", FakeRequest(url="https://x.test/b", method="POST"))
    assert [e.url for e in obs.events] == ["https://x.test/b"]


def test_filter_by_domain_includes_subdomains():
    page = FakePage()
    obs = NetworkObserver(page, domains={"example.com"}).start()
    page.emit("request", FakeRequest(url="https://api.example.com/a"))
    page.emit("request", FakeRequest(url="https://example.com/b"))
    page.emit("request", FakeRequest(url="https://notexample.com/c"))
    urls = [e.url for e in obs.events]
    assert "https://notexample.com/c" not in urls
    assert len(urls) == 2


def test_filter_by_url_pattern():
    page = FakePage()
    obs = NetworkObserver(page, url_pattern=r"/api/").start()
    page.emit("request", FakeRequest(url="https://x.test/api/1"))
    page.emit("request", FakeRequest(url="https://x.test/static/1.js"))
    assert [e.url for e in obs.events] == ["https://x.test/api/1"]


def test_filter_rejects_response_of_filtered_request():
    page = FakePage()
    obs = NetworkObserver(page, resource_types={"xhr"}).start()
    req = FakeRequest(url="https://x.test/img.png", resource_type="image")
    page.emit("request", req)
    page.emit("response", FakeResponse(req))
    assert obs.events == []


# ------------------------------------------------------------- bounded ring

def test_max_events_bounds_history_and_counts_drops():
    page = FakePage()
    obs = NetworkObserver(page, max_events=3).start()
    for i in range(10):
        page.emit("request", FakeRequest(url=f"https://x.test/{i}"))
    assert len(obs.events) == 3
    assert obs.dropped == 7
    assert [e.url for e in obs.events] == [
        "https://x.test/7",
        "https://x.test/8",
        "https://x.test/9",
    ]


def test_max_events_must_be_positive():
    with pytest.raises(ValueError):
        NetworkObserver(FakePage(), max_events=0)


def test_clear_resets_history():
    page = FakePage()
    obs = NetworkObserver(page).start()
    page.emit("request", FakeRequest())
    obs.clear()
    assert obs.events == []
    assert obs.dropped == 0


# ------------------------------------------------------------ callbacks etc

def test_on_event_callback_receives_events():
    page = FakePage()
    seen = []
    obs = NetworkObserver(page, on_event=seen.append).start()
    page.emit("request", FakeRequest(url="https://x.test/a"))
    assert len(seen) == 1
    assert seen[0].kind == "request"
    assert obs.events[0].url == "https://x.test/a"


def test_callback_exception_does_not_break_observer():
    page = FakePage()

    def boom(_event):
        raise RuntimeError("handler bug")

    obs = NetworkObserver(page, on_event=boom).start()
    page.emit("request", FakeRequest(url="https://x.test/a"))
    page.emit("request", FakeRequest(url="https://x.test/b"))
    assert len(obs.events) == 2


def test_malformed_event_does_not_raise():
    page = FakePage()
    obs = NetworkObserver(page).start()

    class Broken:
        @property
        def url(self):
            raise RuntimeError("nope")

    page.emit("request", Broken())
    assert obs.dropped == 1


def test_to_list_is_json_compatible():
    page = FakePage()
    obs = NetworkObserver(page).start()
    req = FakeRequest(headers={"cookie": "s=1"})
    page.emit("request", req)
    page.emit("response", FakeResponse(req))
    data = obs.to_list()
    assert isinstance(data, list)
    assert data[0]["request"]["headers"]["cookie"] == REDACTED
    import json

    json.dumps(data)  # must not raise


def test_response_duration_is_non_negative():
    page = FakePage()
    obs = NetworkObserver(page).start()
    req = FakeRequest()
    page.emit("request", req)
    page.emit("response", FakeResponse(req))
    resp = obs.responses()[0]
    assert resp.duration_ms >= 0.0


# ------------------------------------------------------------------- models

def test_model_as_dict_shapes():
    req = RequestRecord(url="https://x.test", method="GET")
    resp = ResponseRecord(url="https://x.test", status=200)
    fail = FailedRequestRecord(url="https://x.test", failure="boom")
    assert set(req.as_dict()) == {
        "url", "method", "resource_type", "headers",
        "is_navigation_request", "frame_url", "timestamp",
    }
    assert "duration_ms" in resp.as_dict()
    assert fail.as_dict()["failure"] == "boom"
    assert NetworkEvent(kind="request", request=req).url == "https://x.test"
