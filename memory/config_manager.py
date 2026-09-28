import copy
import json
import os
import sys
import threading
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

_CONFIG_LOCK = threading.RLock()
_CONFIG_CACHE: dict | None = None
_CONFIG_SIGNATURE: tuple[int, int] | None = None
_PLUGIN_SETTINGS_REVISION = 0


def _config_signature_unlocked() -> tuple[int, int] | None:
    try:
        stat = CONFIG_FILE.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _read_config_unlocked() -> dict:
    global _CONFIG_CACHE, _CONFIG_SIGNATURE, _PLUGIN_SETTINGS_REVISION
    signature = _config_signature_unlocked()
    if _CONFIG_CACHE is not None and signature == _CONFIG_SIGNATURE:
        return _CONFIG_CACHE

    previous = _CONFIG_CACHE
    data: dict = {}
    observed_signature = signature

    # If an external writer changes the file during the read, retry once. On a
    # second race, retain the pre-read signature so the next getter retries too.
    for _ in range(2):
        observed_signature = signature
        if signature is None:
            data = {}
        else:
            try:
                loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                data = loaded if isinstance(loaded, dict) else {}
            except Exception as e:
                print(f"❌ Failed to load api_keys.json: {e}")
                data = {}

        after_read = _config_signature_unlocked()
        if after_read == observed_signature:
            break
        signature = after_read

    _CONFIG_CACHE = data
    _CONFIG_SIGNATURE = observed_signature
    if previous is not None and _plugin_settings_state(previous) != _plugin_settings_state(data):
        _PLUGIN_SETTINGS_REVISION += 1
    return _CONFIG_CACHE


def _plugin_settings_state(data: dict) -> tuple[object, object]:
    return data.get("plugins_enabled"), data.get("plugin_config")


def _write_config_unlocked(data: dict, previous: dict, *, indent: int = 4) -> None:
    global _CONFIG_CACHE, _CONFIG_SIGNATURE, _PLUGIN_SETTINGS_REVISION
    CONFIG_FILE.write_text(json.dumps(data, indent=indent), encoding="utf-8")
    _CONFIG_CACHE = copy.deepcopy(data)
    _CONFIG_SIGNATURE = _config_signature_unlocked()
    if _plugin_settings_state(previous) != _plugin_settings_state(data):
        _PLUGIN_SETTINGS_REVISION += 1


def _update_config(mutator, *, indent: int = 4) -> None:
    with _CONFIG_LOCK:
        ensure_config_dir()
        previous = _read_config_unlocked()
        data = copy.deepcopy(previous)
        mutator(data)
        _write_config_unlocked(data, previous, indent=indent)


def invalidate_config_cache() -> None:
    """Discard cached config after an out-of-band change to api_keys.json."""
    global _CONFIG_CACHE, _CONFIG_SIGNATURE, _PLUGIN_SETTINGS_REVISION
    with _CONFIG_LOCK:
        _CONFIG_CACHE = None
        _CONFIG_SIGNATURE = None
        _PLUGIN_SETTINGS_REVISION += 1


def get_plugin_settings_revision() -> int:
    """Return the generation used by plugin settings schema caches."""
    with _CONFIG_LOCK:
        _read_config_unlocked()
        return _PLUGIN_SETTINGS_REVISION

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def save_api_keys(gemini_api_key: str) -> None:
    def update(data: dict) -> None:
        data["gemini_api_key"] = gemini_api_key.strip()
        if "os_system" not in data:
            data["os_system"] = "windows" if sys.platform.startswith("win") else ("mac" if sys.platform == "darwin" else "linux")

    _update_config(update, indent=2)

def load_api_keys() -> dict:
    with _CONFIG_LOCK:
        return copy.deepcopy(_read_config_unlocked())

def get_gemini_key() -> str | None:
    cfg = load_api_keys()
    return cfg.get("gemini_api_key") or cfg.get("GEMINI_API_KEY") or cfg.get("api_key") or os.environ.get("GEMINI_API_KEY")

def get_llm_provider() -> str:
    return load_api_keys().get("llm_provider", "gemini").lower()

def get_openrouter_key() -> str | None:
    cfg = load_api_keys()
    return cfg.get("openrouter_api_key") or cfg.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")

def get_openrouter_model() -> str:
    cfg = load_api_keys()
    return cfg.get("openrouter_model") or cfg.get("llm_model") or "anthropic/claude-3.5-sonnet"

def save_openrouter_config(api_key: str, model: str = "anthropic/claude-3.5-sonnet") -> None:
    _patch_config(
        llm_provider="openrouter",
        openrouter_api_key=api_key.strip(),
        openrouter_model=model.strip(),
        llm_model=model.strip(),
    )

def is_configured() -> bool:
    cfg = load_api_keys()
    provider = cfg.get("llm_provider", "gemini").lower()
    if provider in ("ollama", "openai", "lmstudio", "local"):
        return True
    if provider == "openrouter":
        key = get_openrouter_key()
        return bool(key and len(key.strip()) > 5)
    key = get_gemini_key()
    return bool(key and len(key.strip()) > 5)


def get_assistant_name() -> str:
    """Return the configured assistant name, or 'Alfred' if not set."""
    return load_api_keys().get("assistant_name", "Alfred") or "Alfred"


def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    _patch_config(
        assistant_name=assistant_name.strip() or "Alfred",
        user_name=user_name.strip(),
    )


# ── Assistant voice ──────────────────────────────────────────────────────────
# Gemini Live prebuilt voices. Names are proper nouns — identical in every
# language, so this list is safe to show verbatim in any locale.
AVAILABLE_VOICES = ["Charon", "Puck", "Kore", "Fenrir", "Aoede"]
DEFAULT_VOICE    = "Charon"


def get_voice() -> str:
    """Return the configured Live voice, falling back to the default if unset
    or if the stored value is not a voice we recognise."""
    v = load_api_keys().get("voice_name", DEFAULT_VOICE) or DEFAULT_VOICE
    return v if v in AVAILABLE_VOICES else DEFAULT_VOICE


def save_voice(voice_name: str) -> None:
    """Persist the chosen Live voice. Unknown names collapse to the default so a
    bad value can never reach the API and break the session."""
    v = (voice_name or "").strip()
    _patch_config(voice_name=v if v in AVAILABLE_VOICES else DEFAULT_VOICE)


def get_wake_word_enabled() -> bool:
    """Whether local wake-word gating is on (assistant sleeps until 'Hey Alfred')."""
    return load_api_keys().get("wake_word_enabled", False)


def save_wake_word_enabled(enabled: bool) -> None:
    _patch_config(wake_word_enabled=bool(enabled))


def get_push_to_talk_enabled() -> bool:
    """Hold-a-key-to-speak. When on, the mic is closed unless the chord is held."""
    return load_api_keys().get("push_to_talk_enabled", False)


def save_push_to_talk_enabled(enabled: bool) -> None:
    _save_flag("push_to_talk_enabled", enabled)


HUD_STYLES = ("reactive",)


def get_hud_style() -> str:
    """The speech-reactive globe is the only supported HUD."""
    return "reactive"


def save_hud_style(style: str) -> None:
    """Preserve the compatibility API while coercing every value to Reactive."""
    _save_flag("hud_style", "reactive")


# ── Live-session tuning ──────────────────────────────────────────────────────
# Everything here is optional and has a working default, so an untouched
# config behaves exactly like a configured one. Each value is also a way out:
# if a future model dislikes one of these, set it back and nothing else changes.

def get_thinking_enabled() -> bool:
    """Whether the Live model may spend tokens thinking before it answers.

    Off by default. A voice assistant is judged on how fast it starts talking,
    and the reasoning that actually needs deliberation in this app is delegated
    to the planning tools, which run on a separate non-Live model.
    """
    return bool(load_api_keys().get("thinking_enabled", False))


def save_thinking_enabled(enabled: bool) -> None:
    _save_flag("thinking_enabled", enabled)


def get_turn_tuning() -> dict:
    """How eagerly the server decides you have stopped speaking.

    OFF by default, and that default was earned. Cutting turns shorter looks
    like a free speed win and is not: proactive audio has to judge whether an
    utterance was even addressed to the assistant, and a turn clipped early
    gives it less to judge, so it stays quiet — and the reply to your first
    sentence only arrives once your second one has given it enough context.
    That reads as the assistant being a turn behind, which is far worse than
    the fraction of a second the tuning saves.

    Turn it on with "turn_tuning": {"enabled": true} if your own microphone and
    speaking pace suit it. `silence_ms` is the one that is felt: the pause the
    server sits through before accepting your turn is over.
    """
    cfg = load_api_keys().get("turn_tuning")
    cfg = cfg if isinstance(cfg, dict) else {}

    def _int(key, default, lo, hi):
        try:
            return max(lo, min(hi, int(cfg.get(key, default))))
        except (TypeError, ValueError):
            return default

    return {
        "enabled":    bool(cfg.get("enabled", False)),
        "silence_ms": _int("silence_ms", 550, 200, 3000),
        "prefix_ms":  _int("prefix_ms", 150, 0, 1000),
        # "high" = quicker to decide speech has ended.
        "end_sensitivity":   str(cfg.get("end_sensitivity", "high")).lower(),
        "start_sensitivity": str(cfg.get("start_sensitivity", "default")).lower(),
    }


def save_turn_tuning(values: dict) -> None:
    def update(data: dict) -> None:
        cur = data.get("turn_tuning")
        cur = dict(cur) if isinstance(cur, dict) else {}
        cur.update(values or {})
        data["turn_tuning"] = cur

    _update_config(update)


def get_proactive_audio_enabled() -> bool:
    """Whether the model gets to decide an utterance was not aimed at it and
    stay quiet.

    On by default — it is what stops the assistant answering the room. But it
    is also the first thing to switch off if replies ever seem to arrive a turn
    late: what looks like lag is usually the model having judged your previous
    sentence as not addressed to it, and only changing its mind once the next
    one arrives.
    """
    return bool(load_api_keys().get("proactive_audio", True))


def save_proactive_audio_enabled(enabled: bool) -> None:
    _save_flag("proactive_audio", enabled)


MEDIA_RESOLUTIONS = ("default", "low", "medium", "high")


def get_media_resolution() -> str:
    """How finely the model tokenises the screenshots and camera frames it is
    sent. 'medium' keeps on-screen text readable at a fraction of the tokens a
    full-resolution frame costs; 'low' is cheaper still but starts losing small
    text, which is most of what screen captures are for."""
    v = str(load_api_keys().get("media_resolution", "medium")).strip().lower()
    return v if v in MEDIA_RESOLUTIONS else "medium"


def save_media_resolution(value: str) -> None:
    v = str(value or "").strip().lower()
    _save_flag("media_resolution", v if v in MEDIA_RESOLUTIONS else "medium")


def _save_flag(key: str, value) -> None:
    """Read-modify-write one key without disturbing the rest of the config."""
    _patch_config(**{key: bool(value) if isinstance(value, bool) else value})


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def save_brief_enabled(enabled: bool) -> None:
    _patch_config(morning_brief_enabled=enabled)


# ── Audio devices ────────────────────────────────────────────────────────────
# Stored as device NAMES, not sounddevice indices. Indices shift every time a
# USB device is plugged in or removed, so a saved index silently starts pointing
# at a different microphone. The empty string means "system default", which is
# both the factory setting and what an unresolvable saved device falls back to —
# so unplugging a headset degrades to the built-in speakers instead of crashing.

def _patch_config(**fields) -> None:
    """Read-modify-write one or more keys in api_keys.json.

    Every setter in this file open-coded this. Collapsing it here means a new
    setting is one line, and there is one place where a corrupt config file is
    handled instead of nine."""
    _update_config(lambda data: data.update(fields))


def get_input_device() -> str:
    """Microphone device name, or '' for the system default."""
    return (load_api_keys().get("input_device", "") or "").strip()


def save_input_device(name: str) -> None:
    _patch_config(input_device=(name or "").strip())


def get_output_device() -> str:
    """Speaker device name, or '' for the system default."""
    return (load_api_keys().get("output_device", "") or "").strip()


def save_output_device(name: str) -> None:
    _patch_config(output_device=(name or "").strip())


def get_plugin_enabled(plugin_name: str) -> bool:
    """All installed and compatible plugins are automatically enabled (opt-out retired)."""
    return True


def migrate_legacy_plugin_settings() -> None:
    """Safely retire legacy disabled-plugin flags without deleting unrelated user configuration."""
    def update(data: dict) -> None:
        if "plugins_enabled" in data:
            data.pop("plugins_enabled", None)

    _update_config(update)


# ── Per-plugin settings ("tokens" / connection details) ───────────────────────
# Generic store so a plugin can declare its own config fields (PLUGIN_SETTINGS)
# and the settings UI renders + persists them WITHOUT any core edit — keeping the
# drop-in model intact. Values live under plugin_config[<namespace>][<key>].
# A namespace defaults to the plugin name, but a suite of plugins (e.g. the
# several printer plugins) can share ONE namespace.
def get_plugin_config(namespace: str) -> dict:
    """All stored values for a namespace (empty dict if none set yet)."""
    cfg = load_api_keys().get("plugin_config")
    val = cfg.get(namespace) if isinstance(cfg, dict) else None
    return dict(val) if isinstance(val, dict) else {}


def get_plugin_setting(namespace: str, key: str, default=None):
    """A single value from a namespace, or `default` if unset."""
    return get_plugin_config(namespace).get(key, default)


def save_plugin_config(namespace: str, values: dict) -> None:
    """Merge `values` into a namespace's stored config (read-modify-write, like
    every other helper here). Only the provided keys are touched."""
    def update(data: dict) -> None:
        pc = data.get("plugin_config")
        if not isinstance(pc, dict):
            pc = {}
        cur = pc.get(namespace)
        if not isinstance(cur, dict):
            cur = {}
        cur.update(values)
        pc[namespace] = cur
        data["plugin_config"] = pc

    _update_config(update)


def save_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    """Legacy helper maintained for backward compatibility; eligible plugins are active by default."""
    def update(data: dict) -> None:
        plugins_cfg = data.get("plugins_enabled")
        if not isinstance(plugins_cfg, dict):
            plugins_cfg = {}
        plugins_cfg[plugin_name] = enabled
        data["plugins_enabled"] = plugins_cfg

    _update_config(update)


def get_app_icon() -> str:
    """Return the configured app icon filename or path, or '' if default."""
    cfg = load_api_keys()
    return cfg.get("app_icon", "") or ""


def save_app_icon(icon_name_or_path: str) -> None:
    """Save the chosen app icon setting to config."""
    try:
        _patch_config(app_icon=icon_name_or_path.strip())
    except Exception as e:
        print(f"❌ Failed to save app_icon: {e}")
