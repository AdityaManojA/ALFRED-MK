"""
tests/test_llm_client.py — Unit tests for core/llm_client.py (Ollama / OpenAI / OpenRouter routing).

All HTTP and subprocess calls are mocked; config is read from a temp api_keys.json.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

import core.llm_client as llm


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    path = tmp_path / "api_keys.json"
    monkeypatch.setattr(llm, "CONFIG_PATH", path)
    for var in ("OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    def write(**values):
        path.write_text(json.dumps(values), encoding="utf-8")
    write()
    return write


class _Resp:
    def __init__(self, data=None, status=200, lines=None, text=""):
        self._data = data or {}
        self.status_code = status
        self._lines = lines or []
        self.text = text

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def iter_lines(self):
        return iter(self._lines)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ── config helpers ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("ollama", "ollama"), ("OpenRouter", "openrouter"), ("lmstudio", "openai"),
    ("jan", "openai"), ("llamacpp", "openai"), ("something", "ollama"),
])
def test_provider_mapping(cfg, raw, expected):
    cfg(llm_provider=raw)
    assert llm.get_llm_provider() == expected


def test_missing_or_corrupt_config_defaults(cfg, tmp_path):
    llm.CONFIG_PATH.write_text("{not json", encoding="utf-8")
    assert llm._load_config() == {}
    assert llm.get_llm_provider() == "ollama"
    assert llm.get_llm_settings() == ("http://localhost:11434", "llama3.2")


def test_settings_strip_trailing_slash(cfg):
    cfg(llm_url="http://host:1234/", llm_model="qwen")
    assert llm.get_llm_settings() == ("http://host:1234", "qwen")


def test_openrouter_settings_fallbacks(cfg):
    cfg(llm_provider="openrouter")
    assert llm.get_llm_settings() == (llm._DEFAULTS["openrouter_url"], llm._DEFAULTS["openrouter_model"])
    cfg(llm_provider="openrouter", llm_url="http://x/v1/", llm_model="m")
    assert llm.get_llm_settings() == ("http://x/v1", "m")


@pytest.mark.parametrize("url,expected", [
    ("http://h:1234", "http://h:1234/v1/chat/completions"),
    ("http://h:1234/", "http://h:1234/v1/chat/completions"),
    ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1/chat/completions"),
])
def test_chat_endpoint(url, expected):
    assert llm._chat_endpoint(url) == expected


def test_headers_per_provider(cfg, monkeypatch):
    cfg(openrouter_api_key="ork", openai_api_key="oak")
    h = llm._get_headers("openrouter")
    assert h["Authorization"] == "Bearer ork"
    assert "HTTP-Referer" in h and "X-Title" in h
    assert llm._get_headers("openai")["Authorization"] == "Bearer oak"
    assert llm._get_headers("ollama") == {"Content-Type": "application/json"}


def test_headers_env_fallback_and_no_key(cfg, monkeypatch):
    assert "Authorization" not in llm._get_headers("openai")
    monkeypatch.setenv("OPENAI_API_KEY", "envkey")
    assert llm._get_headers("openai")["Authorization"] == "Bearer envkey"


# ── call_llm ──────────────────────────────────────────────────────────────────

def test_call_llm_openai_normalises_tool_calls(cfg, monkeypatch):
    cfg(llm_provider="openai", llm_url="http://lm:1234", llm_model="qwen", openai_api_key="k")
    captured = {}

    def post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return _Resp({"choices": [{"message": {
            "content": "  hi  ",
            "tool_calls": [
                {"id": "1", "function": {"name": "f", "arguments": '{"a": 1}'}},
                {"id": "2", "function": {"name": "g", "arguments": "not-json"}},
            ],
        }}]})
    monkeypatch.setattr(llm.requests, "post", post)

    out = llm.call_llm([{"role": "user", "content": "x"}], tools=[{"t": 1}], timeout=7)

    assert captured["url"] == "http://lm:1234/v1/chat/completions"
    assert captured["json"]["model"] == "qwen"
    assert captured["json"]["tool_choice"] == "auto"
    assert captured["json"]["max_tokens"] == 300
    assert captured["headers"]["Authorization"] == "Bearer k"
    assert captured["timeout"] == 7
    assert out["content"] == "hi"
    assert out["tool_calls"][0] == {"id": "1", "function": {"name": "f", "arguments": {"a": 1}}}
    assert out["tool_calls"][1]["function"]["arguments"] == "not-json"


def test_call_llm_openai_error_wrapped(cfg, monkeypatch):
    cfg(llm_provider="openrouter", openrouter_api_key="k")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(status=500))
    with pytest.raises(RuntimeError, match="Openrouter LLM call failed"):
        llm.call_llm([])


def test_call_llm_ollama_payload_and_result(cfg, monkeypatch):
    captured = {}

    def post(url, json=None, timeout=None):
        captured.update(url=url, json=json)
        return _Resp({"message": {"content": " ok ", "tool_calls": [{"function": {"name": "x"}}]}})
    monkeypatch.setattr(llm.requests, "post", post)
    out = llm.call_llm([{"role": "user", "content": "q"}], tools=[{"t": 1}])
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["keep_alive"] == -1
    assert captured["json"]["tools"] == [{"t": 1}]
    assert "tool_choice" not in captured["json"]
    assert out == {"content": "ok", "tool_calls": [{"function": {"name": "x"}}]}


def test_call_llm_ollama_connection_error_retries_after_restart(cfg, monkeypatch):
    responses = [requests.exceptions.ConnectionError("down"), _Resp({"message": {"content": "back"}})]

    def post(*a, **k):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(llm.requests, "post", post)
    restart = MagicMock(return_value=True)
    monkeypatch.setattr(llm, "ensure_ollama_running", restart)
    assert llm.call_llm([])["content"] == "back"
    restart.assert_called_once()


def test_call_llm_ollama_connection_error_without_restart(cfg, monkeypatch):
    def post(*a, **k):
        raise requests.exceptions.ConnectionError("down")
    monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.setattr(llm, "ensure_ollama_running", lambda: False)
    with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
        llm.call_llm([])


@pytest.mark.parametrize("exc,pattern", [
    (requests.exceptions.Timeout("slow"), "timed out"),
    (ValueError("weird"), "LLM call failed: weird"),
])
def test_call_llm_ollama_other_errors(cfg, monkeypatch, exc, pattern):
    def post(*a, **k):
        raise exc
    monkeypatch.setattr(llm.requests, "post", post)
    with pytest.raises(RuntimeError, match=pattern):
        llm.call_llm([])


def test_call_llm_ollama_http_error(cfg, monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(status=503, text="busy"))
    with pytest.raises(RuntimeError, match="Ollama HTTP error: 503"):
        llm.call_llm([])


# ── call_llm_text ─────────────────────────────────────────────────────────────

def test_call_llm_text_ollama_builds_messages(cfg, monkeypatch):
    captured = {}

    def post(url, json=None, timeout=None):
        captured.update(json)
        return _Resp({"message": {"content": " answer "}})
    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.call_llm_text("q", system="sys", model="other") == "answer"
    assert captured["model"] == "other"
    assert captured["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
    assert captured["options"]["num_predict"] == 600


def test_call_llm_text_openai(cfg, monkeypatch):
    cfg(llm_provider="openai")
    captured = {}

    def post(url, json=None, headers=None, timeout=None):
        captured.update(json)
        return _Resp({"choices": [{"message": {"content": "t"}}]})
    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.call_llm_text("q") == "t"
    assert captured["max_tokens"] == 600
    assert captured["messages"] == [{"role": "user", "content": "q"}]


def test_call_llm_text_generic_error(cfg, monkeypatch):
    def post(*a, **k):
        raise ValueError("bad")
    monkeypatch.setattr(llm.requests, "post", post)
    with pytest.raises(RuntimeError, match="LLM text call failed"):
        llm.call_llm_text("q")


# ── streaming ─────────────────────────────────────────────────────────────────

def test_stream_ollama_yields_sentences_then_done(cfg, monkeypatch):
    lines = [
        json.dumps({"message": {"content": "Hello there. How "}}).encode(),
        b"",
        b"garbage",
        json.dumps({"message": {"content": "are you? Pi is 3.5 ok", "tool_calls": [{"id": "t"}]}}).encode(),
        json.dumps({"message": {"content": ""}, "done": True}).encode(),
    ]
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(lines=lines))
    events = list(llm.call_llm_stream([]))
    sentences = [e["text"] for e in events if e["type"] == "sentence"]
    assert sentences == ["Hello there.", "How are you?", "Pi is 3.5 ok"]
    done = events[-1]
    assert done["type"] == "done"
    assert done["content"] == "Hello there. How are you? Pi is 3.5 ok"
    assert done["tool_calls"] == [{"id": "t"}]


def test_stream_ollama_timeout(cfg, monkeypatch):
    def post(*a, **k):
        raise requests.exceptions.Timeout()
    monkeypatch.setattr(llm.requests, "post", post)
    with pytest.raises(RuntimeError, match="Ollama stream timed out"):
        list(llm.call_llm_stream([]))


def test_stream_openai_accumulates_tool_call_fragments(cfg, monkeypatch):
    cfg(llm_provider="openai", llm_url="http://lm:1234/v1")

    def sse(obj):
        return ("data: " + json.dumps(obj)).encode()
    lines = [
        b": keep-alive",
        sse({"choices": [{"delta": {"content": "Sure. "}}]}),
        sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "c1", "function": {"name": "op", "arguments": '{"x"'}}]}}]}),
        sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"name": "en", "arguments": ': 2}'}}]}}]}),
        sse({"choices": [{"delta": {"content": "Done"}, "finish_reason": "tool_calls"}]}),
        sse({"choices": [{"delta": {"content": "IGNORED"}}]}),
    ]
    captured = {}

    def post(url, json=None, headers=None, timeout=None, stream=None):
        captured.update(url=url, payload=json, stream=stream)
        return _Resp(lines=lines)
    monkeypatch.setattr(llm.requests, "post", post)

    events = list(llm.call_llm_stream([], tools=[{"t": 1}]))
    assert captured["url"] == "http://lm:1234/v1/chat/completions"
    assert captured["payload"]["stream"] is True and captured["stream"] is True
    assert [e["text"] for e in events if e["type"] == "sentence"] == ["Sure.", "Done"]
    done = events[-1]
    assert done["content"] == "Sure. Done"
    assert done["tool_calls"] == [{"id": "c1", "function": {"name": "open", "arguments": {"x": 2}}}]


def test_stream_openai_stops_on_done_marker(cfg, monkeypatch):
    cfg(llm_provider="openai")
    lines = [b"data: " + json.dumps({"choices": [{"delta": {"content": "Hi"}}]}).encode(),
             b"data: [DONE]",
             b"data: " + json.dumps({"choices": [{"delta": {"content": "never"}}]}).encode()]
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(lines=lines))
    events = list(llm.call_llm_stream([]))
    assert events[-1] == {"type": "done", "content": "Hi", "tool_calls": []}


def test_stream_openai_connection_error(cfg, monkeypatch):
    cfg(llm_provider="openai")

    def post(*a, **k):
        raise requests.exceptions.ConnectionError()
    monkeypatch.setattr(llm.requests, "post", post)
    with pytest.raises(RuntimeError, match="Cannot reach OpenAI-compatible server"):
        list(llm.call_llm_stream([]))


# ── server management ─────────────────────────────────────────────────────────

def test_ensure_running_openrouter_requires_key(cfg):
    cfg(llm_provider="openrouter")
    assert llm.ensure_ollama_running() is False
    cfg(llm_provider="openrouter", openrouter_api_key="k")
    assert llm.ensure_ollama_running() is True


def test_ensure_running_openai_pings_models(cfg, monkeypatch):
    cfg(llm_provider="openai", llm_url="http://lm:1")
    urls = []
    monkeypatch.setattr(llm.requests, "get", lambda url, **k: urls.append(url) or _Resp(status=200))
    assert llm.ensure_ollama_running() is True
    assert urls == ["http://lm:1/v1/models"]
    monkeypatch.setattr(llm.requests, "get", lambda url, **k: _Resp(status=404))
    assert llm.ensure_ollama_running() is False


def test_ensure_running_ollama_already_up(cfg, monkeypatch):
    monkeypatch.setattr(llm.requests, "get", lambda url, **k: _Resp(status=200))
    popen = MagicMock()
    monkeypatch.setattr(llm.subprocess, "Popen", popen)
    assert llm.ensure_ollama_running() is True
    popen.assert_not_called()


def test_ensure_running_ollama_launches_and_waits(cfg, monkeypatch):
    states = iter([False, False, True])

    def get(url, **k):
        if next(states):
            return _Resp(status=200)
        raise requests.exceptions.ConnectionError()
    monkeypatch.setattr(llm.requests, "get", get)
    popen = MagicMock()
    monkeypatch.setattr(llm.subprocess, "Popen", popen)
    sleeps = []
    monkeypatch.setattr(llm, "time", SimpleNamespace(time=lambda: 0.0, sleep=sleeps.append))
    assert llm.ensure_ollama_running(timeout=30) is True
    assert popen.call_args.args[0] == ["ollama", "serve"]
    assert sleeps == [1.0, 1.0]


def test_ensure_running_ollama_not_installed(cfg, monkeypatch):
    monkeypatch.setattr(llm.requests, "get", lambda *a, **k: _Resp(status=500))

    def popen(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(llm.subprocess, "Popen", popen)
    assert llm.ensure_ollama_running() is False


def test_ensure_running_ollama_times_out(cfg, monkeypatch):
    monkeypatch.setattr(llm.requests, "get", lambda *a, **k: _Resp(status=500))
    monkeypatch.setattr(llm.subprocess, "Popen", MagicMock())
    clock = iter([100.0, 100.0, 200.0])
    monkeypatch.setattr(llm, "time", SimpleNamespace(time=lambda: next(clock), sleep=lambda s: None))
    assert llm.ensure_ollama_running(timeout=15) is False


def test_warmup_openrouter_skips_network(cfg, monkeypatch):
    cfg(llm_provider="openrouter")
    post = MagicMock()
    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.warmup_model("sys") is True
    post.assert_not_called()


def test_warmup_ollama_primes_with_system_prompt(cfg, monkeypatch):
    captured = {}
    monkeypatch.setattr(llm.requests, "post",
                        lambda url, json=None, timeout=None: captured.update(url=url, json=json) or _Resp())
    assert llm.warmup_model("STATIC") is True
    assert captured["url"].endswith("/api/chat")
    assert captured["json"]["messages"][0] == {"role": "system", "content": "STATIC"}
    assert captured["json"]["options"]["num_predict"] == 1


def test_warmup_openai_failure_is_non_fatal(cfg, monkeypatch):
    cfg(llm_provider="openai")
    captured = {}

    def post(url, json=None, headers=None, timeout=None):
        captured.update(json)
        return _Resp(status=500)
    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.warmup_model() is False
    assert captured["max_tokens"] == 1
    assert captured["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.parametrize("model,pulled,expected", [
    ("llama3.2", ["llama3.2:latest"], True),
    ("llama3.2:3b", ["llama3.2"], True),
    ("qwen", ["llama3.2:latest"], False),
    ("qwen", [], False),
])
def test_check_model_available(cfg, monkeypatch, model, pulled, expected):
    cfg(llm_model=model)
    monkeypatch.setattr(llm.requests, "get",
                        lambda *a, **k: _Resp({"models": [{"name": n} for n in pulled]}))
    logs = []
    assert llm.check_model_available(logs.append) is expected
    assert bool(logs) is (not expected)
    if logs:
        assert f"ollama pull {model}" in logs[0]


def test_check_model_available_non_ollama_and_errors(cfg, monkeypatch):
    def get(*a, **k):
        raise requests.exceptions.ConnectionError()
    monkeypatch.setattr(llm.requests, "get", get)
    assert llm.check_model_available() is True  # unreachable Ollama is non-blocking
    cfg(llm_provider="openai")
    assert llm.check_model_available() is True


def test_get_base_dir_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(llm.sys, "frozen", True, raising=False)
    monkeypatch.setattr(llm.sys, "executable", str(tmp_path / "app.exe"))
    assert llm.get_base_dir() == tmp_path
