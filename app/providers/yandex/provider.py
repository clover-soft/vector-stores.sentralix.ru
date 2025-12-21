from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI
from openai import NotFoundError

from models.rag_provider_connection import RagProviderConnection
from providers.base import BaseProvider
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_YANDEX_BASE_URL = "https://rest-assistant.api.cloud.yandex.net/v1"


class YandexProvider(BaseProvider):
    def __init__(
        self,
        connection: RagProviderConnection,
        credentials: dict,
        token: dict | None,
    ) -> None:
        self._connection = connection
        self._credentials = credentials
        self._token = token

        api_key = credentials.get("api_key")
        if not api_key or not isinstance(api_key, str):
            raise ValueError("Для провайдера yandex требуется credentials.api_key")

        project = credentials.get("project")
        if not project or not isinstance(project, str):
            raise ValueError("Для провайдера yandex требуется credentials.project (folder_id)")

        base_url = connection.base_url or credentials.get("base_url") or _DEFAULT_YANDEX_BASE_URL

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            project=project,
        )

    def _dump(self, obj: Any) -> dict[str, Any]:
        if obj is None:
            return {}
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return obj
        return dict(obj)

    def _dump_page(self, page: Any) -> list[dict[str, Any]]:
        items = getattr(page, "data", None)
        if not items:
            return []
        return [self._dump(i) for i in items]

    def healthcheck(self) -> None:
        try:
            _ = self._client.vector_stores.list(limit=1)
            return
        except NotFoundError:
            pass

        _ = self._client.models.list()

    def create_vector_store(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        chunking_strategy: dict | None = None,
        expires_after: dict | None = None,
        file_ids: list[str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if name is not None:
            kwargs["name"] = name
        if description is not None:
            kwargs["description"] = description
        if chunking_strategy is not None:
            kwargs["chunking_strategy"] = chunking_strategy
        if expires_after is not None:
            kwargs["expires_after"] = expires_after
        if file_ids is not None:
            kwargs["file_ids"] = file_ids
        if metadata is not None:
            kwargs["metadata"] = metadata

        created = self._client.vector_stores.create(**kwargs)
        return self._dump(created)

    def retrieve_vector_store(self, vector_store_id: str) -> dict[str, Any]:
        vs = self._client.vector_stores.retrieve(vector_store_id)
        return self._dump(vs)

    def update_vector_store(
        self,
        vector_store_id: str,
        *,
        name: str | None = None,
        expires_after: dict | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if name is not None:
            kwargs["name"] = name
        if expires_after is not None:
            kwargs["expires_after"] = expires_after
        if metadata is not None:
            kwargs["metadata"] = metadata

        vs = self._client.vector_stores.update(vector_store_id, **kwargs)
        return self._dump(vs)

    def delete_vector_store(self, vector_store_id: str) -> dict[str, Any]:
        deleted = self._client.vector_stores.delete(vector_store_id)
        return self._dump(deleted)

    def search_vector_store(
        self,
        vector_store_id: str,
        *,
        query: str | list[str],
        filters: dict | None = None,
        max_num_results: int | None = None,
        ranking_options: dict | None = None,
        rewrite_query: bool | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"query": query}
        if filters is not None:
            kwargs["filters"] = filters
        if max_num_results is not None:
            kwargs["max_num_results"] = max_num_results
        if ranking_options is not None:
            kwargs["ranking_options"] = ranking_options
        if rewrite_query is not None:
            kwargs["rewrite_query"] = rewrite_query

        page = self._client.vector_stores.search(vector_store_id, **kwargs)
        return self._dump_page(page)

    def attach_file_to_vector_store(
        self,
        vector_store_id: str,
        file_id: str,
        attributes: dict[str, Any] | None = None,
        chunking_strategy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        logger.info(f"attach_file_to_vector_store called: vector_store_id={vector_store_id}, file_id={file_id}")
        logger.info(f"attributes: {attributes}, chunking_strategy: {chunking_strategy}")
        
        kwargs: dict[str, Any] = {"file_id": file_id}
        if attributes is not None:
            kwargs["attributes"] = attributes
        # Yandex API не поддерживает chunking_strategy в attach_file_to_vector_store
        # chunking_strategy используется только при загрузке файла в create_file

        logger.info(f"Calling vector_stores.files.create with kwargs: {kwargs}")
        try:
            created = self._client.vector_stores.files.create(vector_store_id, **kwargs)
            logger.info(f"Successfully attached file: {created}")
            
            # Yandex API не позволяет проверять статус файла во время обработки
            # Возвращает 404 при попытке retrieve файла со статусом 'in_progress'
            # Поэтому просто возвращаем результат прикрепления без ожидания
            
            return self._dump(created)
        except Exception as e:
            logger.error(f"Error attaching file to vector store: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            # Попробуем получить тело ответа если есть
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response body: {e.response.text}")
            # Попробуем получить статус код и заголовки
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                logger.error(f"Response status code: {e.response.status_code}")
            if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                logger.error(f"Response headers: {e.response.headers}")
            # Для 500 ошибок добавим дополнительную информацию
            if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 500:
                logger.error("500 Internal Server Error - possible Yandex API issue")
                logger.error("Request data that caused the error:")
                logger.error(f"  vector_store_id: {vector_store_id}")
                logger.error(f"  file_id: {file_id}")
                logger.error(f"  attributes: {attributes}")
                logger.error(f"  chunking_strategy: {chunking_strategy}")
            raise

    def retrieve_vector_store_file(self, vector_store_id: str, file_id: str) -> dict[str, Any]:
        item = self._client.vector_stores.files.retrieve(file_id, vector_store_id=vector_store_id)
        return self._dump(item)

    def update_vector_store_file(
        self,
        vector_store_id: str,
        file_id: str,
        *,
        attributes: dict,
    ) -> dict[str, Any]:
        item = self._client.vector_stores.files.update(
            file_id,
            vector_store_id=vector_store_id,
            attributes=attributes,
        )
        return self._dump(item)

    def detach_file_from_vector_store(self, vector_store_id: str, file_id: str) -> dict[str, Any]:
        deleted = self._client.vector_stores.files.delete(file_id, vector_store_id=vector_store_id)
        return self._dump(deleted)

    def list_vector_store_files(
        self,
        vector_store_id: str,
        *,
        limit: int = 100,
        after: str | None = None,
        before: str | None = None,
        order: str | None = None,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"limit": limit}
        if after is not None:
            kwargs["after"] = after
        if before is not None:
            kwargs["before"] = before
        if order is not None:
            kwargs["order"] = order
        if status_filter is not None:
            kwargs["filter"] = status_filter

        page = self._client.vector_stores.files.list(vector_store_id, **kwargs)
        return self._dump_page(page)

    def retrieve_vector_store_file_content(self, vector_store_id: str, file_id: str) -> list[dict[str, Any]]:
        page = self._client.vector_stores.files.content(file_id, vector_store_id=vector_store_id)
        return self._dump_page(page)

    def create_vector_store_file_batch(
        self,
        vector_store_id: str,
        *,
        file_ids: list[str] | None = None,
        files: list[dict] | None = None,
        attributes: dict | None = None,
        chunking_strategy: dict | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if file_ids is not None:
            kwargs["file_ids"] = file_ids
        if files is not None:
            kwargs["files"] = files
        if attributes is not None:
            kwargs["attributes"] = attributes
        if chunking_strategy is not None:
            kwargs["chunking_strategy"] = chunking_strategy

        batch = self._client.vector_stores.file_batches.create(vector_store_id, **kwargs)
        return self._dump(batch)

    def retrieve_vector_store_file_batch(self, vector_store_id: str, batch_id: str) -> dict[str, Any]:
        batch = self._client.vector_stores.file_batches.retrieve(batch_id, vector_store_id=vector_store_id)
        return self._dump(batch)

    def cancel_vector_store_file_batch(self, vector_store_id: str, batch_id: str) -> dict[str, Any]:
        batch = self._client.vector_stores.file_batches.cancel(batch_id, vector_store_id=vector_store_id)
        return self._dump(batch)

    def list_vector_store_file_batch_files(
        self,
        vector_store_id: str,
        batch_id: str,
        *,
        limit: int = 100,
        after: str | None = None,
        before: str | None = None,
        order: str | None = None,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"limit": limit}
        if after is not None:
            kwargs["after"] = after
        if before is not None:
            kwargs["before"] = before
        if order is not None:
            kwargs["order"] = order
        if status_filter is not None:
            kwargs["filter"] = status_filter

        page = self._client.vector_stores.file_batches.list_files(
            batch_id,
            vector_store_id=vector_store_id,
            **kwargs,
        )
        return self._dump_page(page)

    def list_vector_stores(self, limit: int = 100) -> list[dict[str, Any]]:
        page = self._client.vector_stores.list(limit=limit)
        return self._dump_page(page)

    def list_files(self, limit: int = 100) -> list[dict[str, Any]]:
        page = self._client.files.list(limit=limit)
        return self._dump_page(page)

    def retrieve_file(self, file_id: str) -> dict[str, Any]:
        item = self._client.files.retrieve(file_id, extra_headers={"OpenAI-Beta": "assistants=v2"})
        return self._dump(item)

    def retrieve_file_content(self, file_id: str) -> bytes:
        resp = self._client.files.content(file_id, extra_headers={"OpenAI-Beta": "assistants=v2"})
        if isinstance(resp, (bytes, bytearray)):
            return bytes(resp)
        if hasattr(resp, "read"):
            data = resp.read()
            if isinstance(data, str):
                return data.encode("utf-8")
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
        if hasattr(resp, "content"):
            data = getattr(resp, "content")
            if isinstance(data, str):
                return data.encode("utf-8")
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
        if isinstance(resp, str):
            return resp.encode("utf-8")
        raise ValueError("Не удалось прочитать контент файла от провайдера")

    def create_file(self, local_path: str, meta: dict | None = None) -> dict[str, Any]:
        # Карта соответствия расширений файлов к разрешенным MIME типам Yandex
        extension_to_mime = {
            '.json': 'application/json',
            '.jsonl': 'application/jsonlines',
            '.doc': 'application/msword',
            '.pdf': 'application/pdf',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.tex': 'application/x-latex',
            '.xhtml': 'application/xhtml+xml',
            '.csv': 'text/csv',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.xml': 'text/xml',
            '.rtf': 'application/rtf',
        }
        
        # Определяем MIME тип по расширению файла
        file_ext = Path(local_path).suffix.lower()
        mime_type = extension_to_mime.get(file_ext, 'text/plain')  # fallback to text/plain
        
        with open(local_path, "rb") as f:
            created = self._client.files.create(
                file=(Path(local_path).name, f, mime_type), 
                purpose="fine-tune"
            )

        data = self._dump(created)
        if meta:
            data["meta"] = meta
        return data
