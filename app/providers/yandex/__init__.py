
from __future__ import annotations

from providers.registry import register_provider
from providers.yandex.provider import YandexProvider


def _factory(connection, credentials: dict, token: dict | None):
    return YandexProvider(connection=connection, credentials=credentials, token=token)


register_provider("yandex", _factory)
