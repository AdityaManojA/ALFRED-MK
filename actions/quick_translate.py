# quick_translate.py
"""
Translate text to a target language using the Gemini model already
powering Alfred — no additional API key or library required.

Falls back to a lightweight deep-translator (googletrans) if the
LLM client is unavailable, and fails gracefully with a clear message
if neither is usable.
"""
from __future__ import annotations

import re
from typing import Optional

# Language aliases → full name for the prompt
_ALIASES: dict[str, str] = {
    "en": "English",
    "english": "English",
    "fr": "French",
    "french": "French",
    "de": "German",
    "german": "German",
    "es": "Spanish",
    "spanish": "Spanish",
    "it": "Italian",
    "italian": "Italian",
    "pt": "Portuguese",
    "portuguese": "Portuguese",
    "ru": "Russian",
    "russian": "Russian",
    "ja": "Japanese",
    "japanese": "Japanese",
    "zh": "Chinese (Simplified)",
    "chinese": "Chinese (Simplified)",
    "ko": "Korean",
    "korean": "Korean",
    "ar": "Arabic",
    "arabic": "Arabic",
    "hi": "Hindi",
    "hindi": "Hindi",
    "tr": "Turkish",
    "turkish": "Turkish",
    "nl": "Dutch",
    "dutch": "Dutch",
    "pl": "Polish",
    "polish": "Polish",
    "sv": "Swedish",
    "swedish": "Swedish",
    "ta": "Tamil",
    "tamil": "Tamil",
    "te": "Telugu",
    "telugu": "Telugu",
}


def _resolve_language(raw: str) -> str:
    """Return the full language name from a code or common alias."""
    key = raw.strip().lower()
    return _ALIASES.get(key, raw.strip().title())


def _translate_via_llm(text: str, target_lang: str, source_lang: str) -> Optional[str]:
    """Use the project's LLM client (Gemini) to perform the translation."""
    try:
        from core.llm_client import LLMClient  # type: ignore[import]
        client = LLMClient()
        source_clause = f" from {source_lang}" if source_lang else ""
        prompt = (
            f"Translate the following text{source_clause} to {target_lang}. "
            "Return ONLY the translation — no explanation, no quotation marks, no preamble.\n\n"
            f"{text}"
        )
        result = client.generate(prompt)
        return result.strip() if result else None
    except Exception:
        return None


def _translate_via_googletrans(text: str, target_lang: str) -> Optional[str]:
    """Fallback: use deep-translator if installed."""
    try:
        from deep_translator import GoogleTranslator  # type: ignore[import]
        translated = GoogleTranslator(source="auto", target=target_lang[:2].lower()).translate(text)
        return translated
    except Exception:
        return None


# ── Action handler ────────────────────────────────────────────────────────────

def quick_translate_action(parameters: dict, **kwargs) -> str:
    text = str(parameters.get("text", "")).strip()
    if not text:
        return "Please provide the text to translate."

    raw_target = str(parameters.get("target_lang", parameters.get("to", "English"))).strip()
    raw_source = str(parameters.get("source_lang", parameters.get("from", ""))).strip()

    target_lang = _resolve_language(raw_target)
    source_lang = _resolve_language(raw_source) if raw_source else ""

    # Try LLM first (already authenticated, highest quality)
    result = _translate_via_llm(text, target_lang, source_lang)

    # Fallback to deep-translator
    if not result:
        result = _translate_via_googletrans(text, target_lang)

    if not result:
        return (
            f"Translation to {target_lang} is unavailable at the moment. "
            "Ensure the LLM client is configured or run: pip install deep-translator"
        )

    source_note = f" (from {source_lang})" if source_lang else ""
    return f"Translation to {target_lang}{source_note}:\n{result}"


# ── Tool declaration ──────────────────────────────────────────────────────────
TOOL = {
    "name": "quick_translate",
    "description": (
        "Translate text to any language. Uses Gemini for high-quality translation "
        "with no extra setup. Supports language names ('French') or codes ('fr')."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "text": {
                "type": "STRING",
                "description": "The text to translate.",
            },
            "target_lang": {
                "type": "STRING",
                "description": (
                    "Target language — full name ('French') or ISO code ('fr'). "
                    "Defaults to English."
                ),
            },
            "source_lang": {
                "type": "STRING",
                "description": (
                    "Source language (optional). Auto-detected if omitted."
                ),
            },
        },
        "required": ["text", "target_lang"],
    },
    "handler": quick_translate_action,
}
