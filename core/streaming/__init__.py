"""
core/streaming package — Multi-provider streaming subsystem (Netflix, Crunchyroll).
"""
from core.streaming.discovery import (
    discover_installed_browsers,
    discover_netflix_native_app,
    discover_crunchyroll_native_app,
)
from core.streaming.preferences import (
    CRUNCHYROLL_DEFAULT_AUDIO,
    forget_preferred_surface,
    format_surface_choice_prompt,
    get_audio_preference,
    get_preferred_surface,
    resolve_surface,
    set_audio_preference,
    set_preferred_surface,
)
from core.streaming.provider import (
    CapabilityClass,
    ProfileCard,
    ProviderState,
    Readiness,
    Result,
    StreamingProvider,
    Surface,
    SurfaceKind,
    Title,
)
from core.streaming.registry import (
    ProviderRegistry,
    get_provider_registry,
    get_selector,
    get_selectors_config,
)

__all__ = [
    "CRUNCHYROLL_DEFAULT_AUDIO",
    "CapabilityClass",
    "ProfileCard",
    "ProviderRegistry",
    "ProviderState",
    "Readiness",
    "Result",
    "StreamingProvider",
    "Surface",
    "SurfaceKind",
    "Title",
    "discover_crunchyroll_native_app",
    "discover_installed_browsers",
    "discover_netflix_native_app",
    "forget_preferred_surface",
    "format_surface_choice_prompt",
    "get_audio_preference",
    "get_preferred_surface",
    "get_provider_registry",
    "get_selector",
    "get_selectors_config",
    "resolve_surface",
    "set_audio_preference",
    "set_preferred_surface",
]
