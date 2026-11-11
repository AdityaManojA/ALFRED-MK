"""Behavioural tests for core.net.loop_guard.install_transport_guard."""
from __future__ import annotations

import asyncio
import logging

import pytest

from core.net.loop_guard import WINSOCK_CONNRESET, install_transport_guard


class FakeLoop:
    def __init__(self, prev=None):
        self._handler = prev
        self.default_calls = []

    def get_exception_handler(self):
        return self._handler

    def set_exception_handler(self, handler):
        self._handler = handler

    def default_exception_handler(self, ctx):
        self.default_calls.append(ctx)


def _winerr(code):
    exc = ConnectionResetError("reset")
    exc.winerror = code
    return exc


@pytest.mark.parametrize(
    "ctx",
    [
        {"exception": _winerr(WINSOCK_CONNRESET)},
        {"exception": OSError("[WinError 10054] An existing connection was forcibly closed")},
        {"exception": BrokenPipeError("in connection_lost")},
        {"message": "Exception in callback _ProactorBasePipeTransport._call_connection_lost()"},
        {"exception": ValueError("x"), "message": "socket error 10054"},
    ],
)
def test_benign_resets_are_swallowed(ctx):
    prev_calls = []
    loop = FakeLoop(prev=lambda l, c: prev_calls.append(c))
    install_transport_guard(loop)
    loop.get_exception_handler()(loop, ctx)
    assert prev_calls == [] and loop.default_calls == []


@pytest.mark.parametrize(
    "ctx",
    [
        {"exception": _winerr(10061), "message": "connect failed"},
        {"exception": RuntimeError("10054"), "message": "boom"},  # non-OSError text is not inspected
        {"message": "Task was destroyed but it is pending!"},
    ],
)
def test_genuine_errors_go_to_previous_handler(ctx):
    prev_calls = []
    loop = FakeLoop(prev=lambda l, c: prev_calls.append((l, c)))
    install_transport_guard(loop)
    loop.get_exception_handler()(loop, ctx)
    assert prev_calls == [(loop, ctx)]


def test_genuine_errors_fall_back_to_default_handler():
    loop = FakeLoop()
    install_transport_guard(loop)
    ctx = {"exception": KeyError("k"), "message": "oops"}
    loop.get_exception_handler()(loop, ctx)
    assert loop.default_calls == [ctx]


def test_suppression_logged_to_custom_logger(caplog):
    log = logging.getLogger("test.loop_guard")
    loop = FakeLoop()
    install_transport_guard(loop, logger=log)
    with caplog.at_level(logging.DEBUG, logger="test.loop_guard"):
        loop.get_exception_handler()(loop, {"exception": _winerr(WINSOCK_CONNRESET)})
    assert any("suppressed" in r.getMessage() for r in caplog.records)


def test_works_on_real_event_loop():
    loop = asyncio.new_event_loop()
    try:
        seen = []
        loop.set_exception_handler(lambda l, c: seen.append(c["message"]))
        install_transport_guard(loop)
        loop.call_exception_handler({"message": "x _call_connection_lost y"})
        loop.call_exception_handler({"message": "real failure"})
        assert seen == ["real failure"]
    finally:
        loop.close()
