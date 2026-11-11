"""Behavioural tests for actions.quick_translate (LLM client and deep-translator stubbed)."""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

import actions.quick_translate as qt
from actions.quick_translate import quick_translate_action


@pytest.mark.parametrize(
    "raw, expected",
    [("fr", "French"), (" ZH ", "Chinese (Simplified)"),
     ("Spanish", "Spanish"), ("klingon", "Klingon"), ("old norse", "Old Norse")],
)
def test_resolve_language(raw, expected):
    assert qt._resolve_language(raw) == expected


def _llm_module(generate):
    mod = types.ModuleType("core.llm_client")
    client = MagicMock()
    client.generate.side_effect = generate
    mod.LLMClient = MagicMock(return_value=client)
    return mod, client


def test_translate_via_llm_builds_prompt_and_strips():
    mod, client = _llm_module(lambda prompt: "  Bonjour  ")
    with patch.dict(sys.modules, {"core.llm_client": mod}):
        assert qt._translate_via_llm("Hello", "French", "English") == "Bonjour"
    prompt = client.generate.call_args.args[0]
    assert prompt.startswith("Translate the following text from English to French.")
    assert prompt.endswith("\n\nHello")


def test_translate_via_llm_without_source_and_on_error():
    mod, client = _llm_module(lambda prompt: "")
    with patch.dict(sys.modules, {"core.llm_client": mod}):
        assert qt._translate_via_llm("Hi", "German", "") is None
    assert " from " not in client.generate.call_args.args[0].split(".")[0]
    mod, _ = _llm_module(RuntimeError("no key"))
    with patch.dict(sys.modules, {"core.llm_client": mod}):
        assert qt._translate_via_llm("Hi", "German", "") is None


@pytest.mark.parametrize(
    "lang, target",
    # deep-translator accepts lower-case language names. The old code sent the
    # first two letters, which gave invalid codes such as "sp" and "ge".
    [("Spanish", "spanish"), ("German", "german"), ("Chinese (Simplified)", "chinese (simplified)")],
)
def test_translate_via_googletrans_passes_language_name(lang, target):
    mod = types.ModuleType("deep_translator")
    mod.GoogleTranslator = MagicMock()
    mod.GoogleTranslator.return_value.translate.return_value = "Hola"
    with patch.dict(sys.modules, {"deep_translator": mod}):
        assert qt._translate_via_googletrans("Hello", lang) == "Hola"
    mod.GoogleTranslator.assert_called_once_with(source="auto", target=target)


def test_translate_via_googletrans_missing_library():
    with patch.dict(sys.modules, {"deep_translator": None}):
        assert qt._translate_via_googletrans("Hello", "Spanish") is None


def test_action_requires_text():
    assert quick_translate_action({"text": "  "}) == "Please provide the text to translate."


def test_action_uses_llm_result_and_aliases():
    with patch.object(qt, "_translate_via_llm", return_value="Hallo") as llm, \
         patch.object(qt, "_translate_via_googletrans") as gt:
        out = quick_translate_action({"text": "Hello", "to": "de", "from": "en"})
    assert out == "Translation to German (from English):\nHallo"
    llm.assert_called_once_with("Hello", "German", "English")
    gt.assert_not_called()


def test_action_defaults_to_english_and_falls_back():
    with patch.object(qt, "_translate_via_llm", return_value=None), \
         patch.object(qt, "_translate_via_googletrans", return_value="Hello") as gt:
        out = quick_translate_action({"text": "Bonjour"})
    assert out == "Translation to English:\nHello"
    gt.assert_called_once_with("Bonjour", "English")


def test_action_reports_unavailable():
    with patch.object(qt, "_translate_via_llm", return_value=None), \
         patch.object(qt, "_translate_via_googletrans", return_value=None):
        out = quick_translate_action({"text": "x", "target_lang": "ja"})
    assert out.startswith("Translation to Japanese is unavailable at the moment.")
