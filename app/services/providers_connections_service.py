from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from config import get_config
from models.rag_provider_connection import RagProviderConnection
from providers.base import BaseProvider
from providers.registry import ensure_providers_loaded, get_provider_factory
from utils.crypto import decrypt_json, encrypt_json


class ProvidersConnectionsService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._config = get_config()

    def list_connections(self) -> list[RagProviderConnection]:
        return (
            self._db.query(RagProviderConnection)
            .order_by(RagProviderConnection.created_at.desc())
            .all()
        )

    def get_connection(self, provider_type: str) -> RagProviderConnection | None:
        return (
            self._db.query(RagProviderConnection)
            .filter(RagProviderConnection.id == provider_type)
            .one_or_none()
        )

    def upsert_connection(
        self,
        provider_type: str,
        base_url: str | None,
        auth_type: str,
        credentials: dict | None,
        token: dict | None,
        token_expires_at: datetime | None,
        is_enabled: bool,
    ) -> RagProviderConnection:
        conn = self.get_connection(provider_type)
        if conn is None:
            conn = RagProviderConnection(id=provider_type, auth_type=auth_type)
            self._db.add(conn)

        conn.base_url = base_url
        conn.auth_type = auth_type
        conn.is_enabled = is_enabled
        conn.token_expires_at = token_expires_at

        key = self._get_secrets_key()

        if credentials is not None:
            conn.credentials_enc = encrypt_json(credentials, key)

        if token is not None:
            conn.token_enc = encrypt_json(token, key)

        conn.last_error = None

        self._db.commit()
        self._db.refresh(conn)
        return conn

    def patch_connection(
        self,
        provider_type: str,
        base_url: str | None,
        auth_type: str | None,
        credentials: dict | None,
        token: dict | None,
        token_expires_at: datetime | None,
        is_enabled: bool | None,
    ) -> RagProviderConnection | None:
        conn = self.get_connection(provider_type)
        if conn is None:
            return None

        if base_url is not None:
            conn.base_url = base_url

        if auth_type is not None:
            conn.auth_type = auth_type

        if is_enabled is not None:
            conn.is_enabled = is_enabled

        if token_expires_at is not None:
            conn.token_expires_at = token_expires_at

        if credentials is not None or token is not None:
            key = self._get_secrets_key()
            if credentials is not None:
                conn.credentials_enc = encrypt_json(credentials, key)
            if token is not None:
                conn.token_enc = encrypt_json(token, key)

        self._db.commit()
        self._db.refresh(conn)
        return conn

    def delete_connection(self, provider_type: str) -> bool:
        conn = self.get_connection(provider_type)
        if conn is None:
            return False

        self._db.delete(conn)
        self._db.commit()
        return True

    def get_provider(self, provider_type: str) -> BaseProvider:
        conn = self.get_connection(provider_type)
        if conn is None:
            raise ValueError("Подключение провайдера не найдено")

        if not conn.is_enabled:
            raise ValueError("Провайдер отключён")

        if not conn.credentials_enc:
            raise ValueError("Не заданы credentials для провайдера")

        key = self._get_secrets_key()
        credentials = decrypt_json(conn.credentials_enc, key)
        token = decrypt_json(conn.token_enc, key) if conn.token_enc else None

        ensure_providers_loaded()
        factory = get_provider_factory(provider_type)
        if factory is None:
            raise ValueError("Неизвестный provider_type")

        return factory(conn, credentials, token)

    def _get_secrets_key(self) -> str:
        if not self._config.provider_secrets_key:
            raise ValueError("PROVIDER_SECRETS_KEY не задан")
        return self._config.provider_secrets_key
