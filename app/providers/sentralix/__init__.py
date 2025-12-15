
from __future__ import annotations

from providers.registry import register_provider
from providers.sentralix.provider import SentralixProvider


def _factory(connection, credentials: dict, token: dict | None):
    return SentralixProvider(connection=connection, credentials=credentials, token=token)


register_provider("sentralix", _factory)
