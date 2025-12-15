from __future__ import annotations

from sqlalchemy.orm import Session

from services.providers_connections_service import ProvidersConnectionsService


class ProviderVectorStoresService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_vector_stores(self, provider_type: str, *, limit: int = 100) -> list[dict]:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.list_vector_stores(limit=limit)

    def list_files(self, provider_type: str, *, limit: int = 100) -> list[dict]:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.list_files(limit=limit)

    def create_vector_store(
        self,
        provider_type: str,
        *,
        name: str | None = None,
        description: str | None = None,
        chunking_strategy: dict | None = None,
        expires_after: dict | None = None,
        file_ids: list[str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.create_vector_store(
            name=name,
            description=description,
            chunking_strategy=chunking_strategy,
            expires_after=expires_after,
            file_ids=file_ids,
            metadata=metadata,
        )

    def retrieve_vector_store(self, provider_type: str, vector_store_id: str) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.retrieve_vector_store(vector_store_id)

    def update_vector_store(
        self,
        provider_type: str,
        vector_store_id: str,
        *,
        name: str | None = None,
        expires_after: dict | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.update_vector_store(
            vector_store_id,
            name=name,
            expires_after=expires_after,
            metadata=metadata,
        )

    def delete_vector_store(self, provider_type: str, vector_store_id: str) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.delete_vector_store(vector_store_id)

    def search_vector_store(
        self,
        provider_type: str,
        vector_store_id: str,
        *,
        query: str | list[str],
        filters: dict | None = None,
        max_num_results: int | None = None,
        ranking_options: dict | None = None,
        rewrite_query: bool | None = None,
    ) -> list[dict]:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.search_vector_store(
            vector_store_id,
            query=query,
            filters=filters,
            max_num_results=max_num_results,
            ranking_options=ranking_options,
            rewrite_query=rewrite_query,
        )

    def attach_file_to_vector_store(
        self,
        provider_type: str,
        vector_store_id: str,
        *,
        file_id: str,
        attributes: dict | None = None,
        chunking_strategy: dict | None = None,
    ) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.attach_file_to_vector_store(
            vector_store_id,
            file_id=file_id,
            attributes=attributes,
            chunking_strategy=chunking_strategy,
        )

    def detach_file_from_vector_store(self, provider_type: str, vector_store_id: str, file_id: str) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.detach_file_from_vector_store(vector_store_id, file_id)

    def list_vector_store_files(
        self,
        provider_type: str,
        vector_store_id: str,
        *,
        limit: int = 100,
        after: str | None = None,
        before: str | None = None,
        order: str | None = None,
        status_filter: str | None = None,
    ) -> list[dict]:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.list_vector_store_files(
            vector_store_id,
            limit=limit,
            after=after,
            before=before,
            order=order,
            status_filter=status_filter,
        )

    def retrieve_vector_store_file(self, provider_type: str, vector_store_id: str, file_id: str) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.retrieve_vector_store_file(vector_store_id, file_id)

    def update_vector_store_file(
        self,
        provider_type: str,
        vector_store_id: str,
        file_id: str,
        *,
        attributes: dict,
    ) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.update_vector_store_file(vector_store_id, file_id, attributes=attributes)

    def retrieve_vector_store_file_content(self, provider_type: str, vector_store_id: str, file_id: str) -> list[dict]:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.retrieve_vector_store_file_content(vector_store_id, file_id)

    def create_vector_store_file_batch(
        self,
        provider_type: str,
        vector_store_id: str,
        *,
        file_ids: list[str] | None = None,
        files: list[dict] | None = None,
        attributes: dict | None = None,
        chunking_strategy: dict | None = None,
    ) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.create_vector_store_file_batch(
            vector_store_id,
            file_ids=file_ids,
            files=files,
            attributes=attributes,
            chunking_strategy=chunking_strategy,
        )

    def retrieve_vector_store_file_batch(self, provider_type: str, vector_store_id: str, batch_id: str) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.retrieve_vector_store_file_batch(vector_store_id, batch_id)

    def cancel_vector_store_file_batch(self, provider_type: str, vector_store_id: str, batch_id: str) -> dict:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.cancel_vector_store_file_batch(vector_store_id, batch_id)

    def list_vector_store_file_batch_files(
        self,
        provider_type: str,
        vector_store_id: str,
        batch_id: str,
        *,
        limit: int = 100,
        after: str | None = None,
        before: str | None = None,
        order: str | None = None,
        status_filter: str | None = None,
    ) -> list[dict]:
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        return provider.list_vector_store_file_batch_files(
            vector_store_id,
            batch_id,
            limit=limit,
            after=after,
            before=before,
            order=order,
            status_filter=status_filter,
        )
