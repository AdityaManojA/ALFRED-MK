"""
tests/test_local_pipeline.py — Unit tests for core/local_pipeline.py (offline STT → LLM → TTS coordinator).

STT/TTS engines and LLM calls are replaced with fakes; no audio device or model is touched.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

import core.local_pipeline as lp


class _FakeSTT:
    def __init__(self, config, transcript="hello alfred"):
        self.config = config
        self.sample_rate = 10
        self.callback = None
        self.listening = False
        self.stt = MagicMock()
        self.stt.transcribe.return_value = transcript

    def set_audio_callback(self, cb):
        self.callback = cb

    def start_listening(self):
        self.listening = True

    def stop_listening(self):
        self.listening = False


class _UI:
    def __init__(self, muted=False):
        self.muted = muted
        self.logs = []
        self.states = []

    def write_log(self, text, overwrite=False):
        self.logs.append(text)

    def set_state(self, state):
        self.states.append(state)


@pytest.fixture
def llm_env(monkeypatch):
    ensure = MagicMock(return_value=True)
    monkeypatch.setattr(lp, "ensure_ollama_running", ensure)
    monkeypatch.setattr(lp, "get_llm_provider", lambda: "ollama")
    monkeypatch.setattr(lp, "get_llm_settings", lambda: ("http://x", "m"))
    return ensure


@pytest.fixture
def coordinator(monkeypatch, llm_env):
    monkeypatch.setattr(lp, "create_local_stt_engine", lambda cfg: _FakeSTT(cfg))
    tts = MagicMock()
    monkeypatch.setattr(lp, "create_local_tts_engine", lambda cfg: tts)
    ui = _UI()
    coord = lp.create_local_pipeline({"stt_engine": "whisper"}, ui)
    coord.llm_manager.generate_response = MagicMock()
    return coord, ui, tts


# ── LocalLLMManager ───────────────────────────────────────────────────────────

def test_llm_manager_warms_ollama_only(monkeypatch, llm_env):
    lp.LocalLLMManager({})
    llm_env.assert_called_once()
    llm_env.reset_mock()
    monkeypatch.setattr(lp, "get_llm_provider", lambda: "openai")
    mgr = lp.LocalLLMManager({})
    llm_env.assert_not_called()
    assert (mgr.url, mgr.model) == ("http://x", "m")


def test_history_is_capped_at_20(llm_env):
    mgr = lp.LocalLLMManager({})
    for i in range(25):
        mgr.add_to_history("user", str(i))
    assert len(mgr.history) == 20
    assert mgr.history[0]["content"] == "5"
    mgr.clear_history()
    assert mgr.history == []


def test_generate_response_streaming(monkeypatch, llm_env):
    mgr = lp.LocalLLMManager({})
    mgr.set_context("SYS", [{"tool": 1}])
    mgr.add_to_history("assistant", "earlier")
    captured = {}

    def stream(messages, tools=None):
        captured.update(messages=messages, tools=tools)
        yield {"type": "sentence", "text": "One."}
        yield {"type": "sentence", "text": ""}
        yield {"type": "sentence", "text": "Two."}
        yield {"type": "done", "content": "One. Two.", "tool_calls": []}
    monkeypatch.setattr(lp, "call_llm_stream", stream)
    chunks = []
    out = asyncio.run(mgr.generate_response("hi", chunks.append))
    assert out == "One. Two."
    assert chunks == ["One.", "Two."]
    assert captured["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "assistant", "content": "earlier"},
        {"role": "user", "content": "hi"},
    ]
    assert captured["tools"] == [{"tool": 1}]
    assert mgr.history[-1] == {"role": "assistant", "content": "One. Two."}


def test_generate_response_handles_tool_calls_with_follow_up(monkeypatch, llm_env):
    mgr = lp.LocalLLMManager({})
    prompts = []
    rounds = iter([
        [{"type": "done", "content": "Checking",
          "tool_calls": [{"function": {"name": "get_time", "arguments": {}}}]}],
        [{"type": "done", "content": "It is noon.", "tool_calls": []}],
    ])

    def stream(messages, tools=None):
        prompts.append(messages[-1]["content"])
        yield from next(rounds)
    monkeypatch.setattr(lp, "call_llm_stream", stream)
    out = asyncio.run(mgr.generate_response("time?", lambda t: None))
    assert out == "It is noon."
    assert prompts[0] == "time?"
    assert "Tool get_time executed" in prompts[1]
    assert prompts[1].startswith("Checking")


def test_generate_response_non_streaming_uses_call_llm(monkeypatch, llm_env):
    mgr = lp.LocalLLMManager({})
    monkeypatch.setattr(lp, "call_llm", lambda messages, tools=None: {"content": "plain", "tool_calls": []})
    assert asyncio.run(mgr.generate_response("hi")) == "plain"
    assert mgr.history[-1]["content"] == "plain"


def test_generate_response_error_is_returned_as_text(monkeypatch, llm_env):
    mgr = lp.LocalLLMManager({})

    def stream(messages, tools=None):
        raise RuntimeError("offline")
        yield  # pragma: no cover
    monkeypatch.setattr(lp, "call_llm_stream", stream)
    assert asyncio.run(mgr.generate_response("hi", lambda t: None)) == "Error generating response: offline"


# ── LocalPipelineCoordinator ──────────────────────────────────────────────────

def test_coordinator_registers_audio_callback(coordinator):
    coord, _, _ = coordinator
    assert coord.stt_manager.callback == coord._audio_callback


def test_audio_callback_respects_running_speaking_and_mute(coordinator):
    coord, ui, _ = coordinator
    coord._audio_callback(b"a")
    assert coord.audio_queue.empty()  # not running
    coord.is_running = True
    coord._audio_callback(b"b")
    coord.is_speaking = True
    coord._audio_callback(b"c")
    coord.is_speaking = False
    ui.muted = True
    coord._audio_callback(b"d")
    assert coord.audio_queue.get_nowait() == b"b"
    assert coord.audio_queue.empty()


def test_log_uses_callback_when_set(coordinator, capsys):
    coord, _, _ = coordinator
    coord._log("printed")
    assert "[LocalPipeline] printed" in capsys.readouterr().out
    logs = []
    coord.set_ui_callbacks(on_log_message=logs.append)
    coord._log("routed")
    assert logs == ["routed"]


def test_start_and_stop_lifecycle(coordinator):
    coord, _, tts = coordinator

    async def scenario():
        coord.start()
        assert coord.is_running and coord.is_listening and coord.stt_manager.listening
        task = coord._processing_task
        coord.start()  # idempotent
        assert coord._processing_task is task
        coord.stop()
        await asyncio.sleep(0)
        return task

    task = asyncio.run(scenario())
    assert task.cancelled() or task.done()
    assert not coord.is_running and not coord.stt_manager.listening
    tts.stop.assert_called_once()
    coord.stop()  # second stop is a no-op
    tts.stop.assert_called_once()


def test_wake_sleep_and_wake_word_gate(coordinator):
    coord, ui, _ = coordinator
    states = []
    woke = MagicMock()
    coord.set_ui_callbacks(on_state_change=states.append, on_wake_word_detected=woke)

    coord.handle_wake_word()
    assert not coord._awake  # wake word disabled
    coord.set_wake_word_enabled(True)
    coord.handle_wake_word()
    assert coord._awake and states == ["LISTENING"] and ui.states == ["LISTENING"]
    woke.assert_called_once()
    coord.handle_wake_word()  # already awake → nothing new
    assert states == ["LISTENING"]

    coord.sleep("idle")
    assert not coord._awake and states[-1] == "SLEEPING"
    assert "SYS: Sleeping — idle." in ui.logs
    coord.wake("button")
    assert coord._awake and "SYS: Awake — button." in ui.logs
    coord.set_wake_word_enabled(False)
    assert not coord._awake and states[-1] == "SLEEPING"


def test_interrupt_clears_queue_and_sets_state(coordinator):
    coord, ui, tts = coordinator
    for b in (b"1", b"2"):
        coord.audio_queue.put(b)
    coord.is_speaking = True
    coord.interrupt()
    assert coord.audio_queue.empty() and not coord.is_speaking
    tts.stop.assert_called_once()
    assert ui.states[-1] == "SLEEPING"
    coord.set_wake_word_enabled(True)
    coord.interrupt()
    assert ui.states[-1] == "LISTENING"


def test_process_utterance_full_flow(coordinator):
    coord, ui, tts = coordinator

    async def fake_generate(prompt, cb):
        cb("Good day.")
        cb("")
        return "Good day."
    coord.llm_manager.generate_response = fake_generate
    pcm = np.array([0, 16384, -32768], dtype=np.int16).tobytes()
    asyncio.run(coord._process_utterance(pcm))

    audio = coord.stt_manager.stt.transcribe.call_args.args[0]
    np.testing.assert_allclose(audio, [0.0, 0.5, -1.0])
    assert ui.logs == ["You: hello alfred", "ALFRED: Good day."]
    tts.speak_sentence.assert_called_once_with("Good day.")
    tts.flush.assert_called_once()
    assert coord.is_processing is False


def test_process_utterance_skips_empty_and_vosk(coordinator):
    coord, ui, tts = coordinator
    coord.stt_manager.stt.transcribe.return_value = "   "
    asyncio.run(coord._process_utterance(b"\x00\x00"))
    coord.stt_manager.config["stt_engine"] = "vosk"
    asyncio.run(coord._process_utterance(b"\x00\x00"))
    assert coord.stt_manager.stt.transcribe.call_count == 1
    coord.llm_manager.generate_response.assert_not_called()
    assert ui.logs == []


def test_process_utterance_guard_and_error(coordinator):
    coord, ui, _ = coordinator
    coord.is_processing = True
    asyncio.run(coord._process_utterance(b"\x00\x00"))
    coord.stt_manager.stt.transcribe.assert_not_called()

    coord.is_processing = False
    coord.stt_manager.stt.transcribe.side_effect = RuntimeError("model gone")
    asyncio.run(coord._process_utterance(b"\x00\x00"))
    assert ui.logs == ["Error: model gone"]
    assert coord.is_processing is False


def test_processing_loop_flushes_after_silence(coordinator):
    coord, _, _ = coordinator
    coord.config["stt_min_silence_chunks"] = 1
    received = []

    async def fake_process(audio):
        received.append(audio)
        coord.is_running = False
    coord._process_utterance = fake_process
    loud = np.full(4, 1000, dtype=np.int16).tobytes()
    silent = np.zeros(4, dtype=np.int16).tobytes()
    for chunk in (loud, silent, silent):
        coord.audio_queue.put(chunk)
    coord.is_running = True

    asyncio.run(asyncio.wait_for(coord._processing_loop(), timeout=5))
    assert received == [loud + silent + silent]


def test_processing_loop_discards_audio_while_muted(coordinator):
    coord, ui, _ = coordinator
    ui.muted = True
    coord.audio_queue.put(b"\x01\x00")
    coord.is_running = True

    async def run():
        task = asyncio.ensure_future(coord._processing_loop())
        await asyncio.sleep(0.05)
        coord.is_running = False
        await asyncio.wait_for(task, timeout=2)
    asyncio.run(run())
    assert coord.audio_queue.qsize() == 1  # never consumed while muted
