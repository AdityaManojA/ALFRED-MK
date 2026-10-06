"""
core/streaming/registry.py — Streaming Provider Registry and Selector Loader.

Maintains lazy provider factories so importing the registry never incurs
Playwright or browser driver overhead at boot time.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.streaming.provider import StreamingProvider


_SELECTORS_FILE: Path = Path(__file__).resolve().parent / "selectors.json"
_SELECTORS_CACHE: Optional[dict] = None

ProviderFactory = Callable[[], StreamingProvider]


def get_selectors_config() -> dict:
    """Load selectors JSON from disk with caching."""
    global _SELECTORS_CACHE
    if _SELECTORS_CACHE is None:
        try:
            if _SELECTORS_FILE.exists():
                _SELECTORS_CACHE = json.loads(_SELECTORS_FILE.read_text(encoding="utf-8"))
            else:
                _SELECTORS_CACHE = {}
        except Exception:
            _SELECTORS_CACHE = {}
    return _SELECTORS_CACHE


def get_selector(provider_id: str, state_or_feature: str, element: Optional[str] = None) -> dict:
    """
    Retrieve primary and fallback selectors for a provider and element.
    Returns: {"primary": str, "fallbacks": list[str]}
    """
    cfg = get_selectors_config().get(provider_id.lower(), {})
    node = cfg.get(state_or_feature, {})
    if element and isinstance(node, dict):
        node = node.get(element, {})

    if isinstance(node, dict) and "primary" in node:
        return {
            "primary": node.get("primary", ""),
            "fallbacks": node.get("fallbacks", []),
        }
    return {"primary": "", "fallbacks": []}


class ProviderRegistry:
    """Lazy registry for streaming providers."""

    def __init__(self) -> None:
        self._factories: Dict[str, ProviderFactory] = {}
        self._instances: Dict[str, StreamingProvider] = {}

    def register(self, provider_id: str, factory: ProviderFactory) -> None:
        """Register a lazy provider factory function."""
        self._factories[provider_id.lower().strip()] = factory

    def get(self, provider_id: str) -> Optional[StreamingProvider]:
        """Resolve a provider instance by ID, instantiating it lazily."""
        pid = provider_id.lower().strip()
        if pid in self._instances:
            return self._instances[pid]

        if pid in self._factories:
            instance = self._factories[pid]()
            self._instances[pid] = instance
            return instance

        return None

    def list_available_providers(self) -> List[str]:
        """Return all registered provider identifiers."""
        return list(self._factories.keys())

    def reset(self) -> None:
        """Clear cached provider instances."""
        self._instances.clear()


# Global module singleton
_REGISTRY: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Return the global ProviderRegistry instance."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ProviderRegistry()
        # Default lazy registrations
        _register_defaults(_REGISTRY)
    return _REGISTRY


def _register_defaults(reg: ProviderRegistry) -> None:
    """Register built-in providers with lazy loader thunks."""
    def _netflix_factory() -> StreamingProvider:
        from core.streaming.providers.netflix import NetflixProvider
        return NetflixProvider()

    def _crunchyroll_factory() -> StreamingProvider:
        from core.streaming.providers.crunchyroll import CrunchyrollProvider
        return CrunchyrollProvider()

    reg.register("netflix", _netflix_factory)
    reg.register("crunchyroll", _crunchyroll_factory)
