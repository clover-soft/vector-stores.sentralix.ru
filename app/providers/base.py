from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    @abstractmethod
    def healthcheck(self) -> None:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def retrieve_vector_store(self, vector_store_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_vector_store(
        self,
        vector_store_id: str,
        *,
        name: str | None = None,
        expires_after: dict | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete_vector_store(self, vector_store_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def attach_file_to_vector_store(
        self,
        vector_store_id: str,
        *,
        file_id: str,
        attributes: dict | None = None,
        chunking_strategy: dict | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def retrieve_vector_store_file(self, vector_store_id: str, file_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_vector_store_file(
        self,
        vector_store_id: str,
        file_id: str,
        *,
        attributes: dict,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def detach_file_from_vector_store(self, vector_store_id: str, file_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def retrieve_vector_store_file_content(self, vector_store_id: str, file_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create_vector_store_file_batch(
        self,
        vector_store_id: str,
        *,
        file_ids: list[str] | None = None,
        files: list[dict] | None = None,
        attributes: dict | None = None,
        chunking_strategy: dict | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def retrieve_vector_store_file_batch(self, vector_store_id: str, batch_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def cancel_vector_store_file_batch(self, vector_store_id: str, batch_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def list_vector_stores(self, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_files(self, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def retrieve_file(self, file_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def retrieve_file_content(self, file_id: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def create_file(self, local_path: str, meta: dict | None = None) -> dict[str, Any]:
        raise NotImplementedError
