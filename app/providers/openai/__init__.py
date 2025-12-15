from __future__ import annotations

from providers.openai.provider import OpenAIProvider
from providers.registry import register_provider


def _factory(connection, credentials: dict, token: dict | None):
    return OpenAIProvider(connection=connection, credentials=credentials, token=token)


register_provider("openai", _factory)
