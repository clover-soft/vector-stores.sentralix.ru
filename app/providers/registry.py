from __future__ import annotations

from typing import Callable

from models.rag_provider_connection import RagProviderConnection
from providers.base import BaseProvider

ProviderFactory = Callable[[RagProviderConnection, dict, dict | None], BaseProvider]


_registry: dict[str, ProviderFactory] = {}
_loaded: bool = False


def register_provider(provider_type: str, factory: ProviderFactory) -> None:
    _registry[provider_type] = factory


def get_provider_factory(provider_type: str) -> ProviderFactory | None:
    return _registry.get(provider_type)


def ensure_providers_loaded() -> None:
    global _loaded
    if _loaded:
        return

    try:
        import providers.openai  # noqa: F401
    except Exception:
        pass

    try:
        import providers.sentralix  # noqa: F401
    except Exception:
        pass

    try:
        import providers.yandex  # noqa: F401
    except Exception:
        pass

    _loaded = True
