"""Offline tests for the extension-point hooks."""

from __future__ import annotations

from chromebrowse.hooks import HookSet


# ------------------------------------------------------------- generic hooks


def test_empty_hookset_is_inert():
    hooks = HookSet()
    hooks.emit("anything", {"x": 1})  # must not raise
    hooks.fire_page_created(object())
    hooks.fire_page_closed(object())
    hooks.fire_after_navigate(object(), "https://a/", None)
    hooks.fire_response(object(), "https://a/", 200)


def test_add_registers_generic_hook_once():
    hooks = HookSet()
    seen = []

    def record(event, payload):
        seen.append(event)

    hooks.add(record)
    hooks.add(record)  # idempotent
    hooks.emit("a")
    assert seen == ["a"]


def test_add_returns_self_for_chaining():
    hooks = HookSet()
    assert hooks.add(lambda e, p: None) is hooks


def test_generic_hook_receives_payload():
    hooks = HookSet()
    seen = []
    hooks.add(lambda event, payload: seen.append((event, payload)))
    hooks.emit("ping", {"n": 1})
    assert seen == [("ping", {"n": 1})]


def test_generic_hook_exception_is_swallowed():
    hooks = HookSet()
    calls = []

    def bad(event, payload):
        raise RuntimeError("boom")

    def good(event, payload):
        calls.append(event)

    hooks.add(bad).add(good)
    hooks.emit("x")
    assert calls == ["x"]


# ------------------------------------------------------------ named hooks


def test_before_navigate_can_abort():
    hooks = HookSet(before_navigate=lambda page, url: (_ for _ in ()).throw(RuntimeError("stop")))
    try:
        hooks.fire_before_navigate(object(), "https://a/")
    except RuntimeError:
        pass
    else:
        raise AssertionError("before_navigate should propagate")


def test_after_navigate_receives_error():
    seen = []
    hooks = HookSet(after_navigate=lambda page, url, error: seen.append((url, error)))
    hooks.fire_after_navigate(object(), "https://a/", ValueError("x"))
    assert seen[0][0] == "https://a/"
    assert isinstance(seen[0][1], ValueError)


def test_after_navigate_exception_is_swallowed():
    def bad(page, url, error):
        raise RuntimeError("boom")

    HookSet(after_navigate=bad).fire_after_navigate(object(), "https://a/", None)


def test_page_created_and_closed_hooks_fire():
    created, closed = [], []
    hooks = HookSet(
        on_page_created=lambda page: created.append(page),
        on_page_closed=lambda page: closed.append(page),
    )
    page = object()
    hooks.fire_page_created(page)
    hooks.fire_page_closed(page)
    assert created == [page] and closed == [page]


def test_response_hook_receives_status():
    seen = []
    hooks = HookSet(on_response=lambda page, url, status: seen.append((url, status)))
    hooks.fire_response(object(), "https://a/", 404)
    assert seen == [("https://a/", 404)]


def test_named_hook_exceptions_do_not_escape():
    def bad(*_args):
        raise RuntimeError("boom")

    hooks = HookSet(on_page_created=bad, on_page_closed=bad, on_response=bad)
    page = object()
    hooks.fire_page_created(page)
    hooks.fire_page_closed(page)
    hooks.fire_response(page, "https://a/", 200)


def test_generic_hooks_fire_for_named_events():
    events = []
    hooks = HookSet()
    hooks.add(lambda event, payload: events.append(event))
    hooks.fire_page_created(object())
    hooks.fire_page_closed(object())
    hooks.fire_after_navigate(object(), "https://a/", None)
    hooks.fire_response(object(), "https://a/", 200)
    assert events == ["page_created", "page_closed", "after_navigate", "response"]
