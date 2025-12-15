from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from models.rag_file import RagFile
from models.rag_provider_file_upload import RagProviderFileUpload
from services.providers_connections_service import ProvidersConnectionsService


class ProviderFileUploadsService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_uploads(self, provider_type: str, skip: int = 0, limit: int = 100) -> list[RagProviderFileUpload]:
        return (
            self._db.query(RagProviderFileUpload)
            .filter(RagProviderFileUpload.provider_id == provider_type)
            .order_by(RagProviderFileUpload.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_upload(self, provider_type: str, upload_id: str) -> RagProviderFileUpload | None:
        return (
            self._db.query(RagProviderFileUpload)
            .filter(RagProviderFileUpload.provider_id == provider_type)
            .filter(RagProviderFileUpload.id == upload_id)
            .one_or_none()
        )

    def get_or_sync(
        self,
        provider_type: str,
        local_file_id: str,
        force: bool = False,
        meta: dict | None = None,
    ) -> RagProviderFileUpload:
        rag_file = self._get_local_file(local_file_id)
        sha256 = self._calc_sha256(Path(rag_file.local_path))

        upload = (
            self._db.query(RagProviderFileUpload)
            .filter(RagProviderFileUpload.provider_id == provider_type)
            .filter(RagProviderFileUpload.local_file_id == local_file_id)
            .one_or_none()
        )

        if (
            upload is not None
            and not force
            and upload.status == "uploaded"
            and upload.content_sha256 == sha256
            and upload.external_file_id
        ):
            return upload

        if upload is None:
            upload = RagProviderFileUpload(
                id=str(uuid4()),
                provider_id=provider_type,
                local_file_id=local_file_id,
                status="pending",
                content_sha256=sha256,
            )
            self._db.add(upload)
        else:
            upload.status = "pending"
            upload.content_sha256 = sha256
            upload.last_error = None

        self._db.commit()
        self._db.refresh(upload)

        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)

        try:
            created = provider.create_file(local_path=rag_file.local_path, meta=meta)
            external_file_id = created.get("id") or created.get("file_id")
            if not external_file_id:
                raise ValueError("Провайдер не вернул идентификатор файла")

            upload.external_file_id = str(external_file_id)
            upload.external_uploaded_at = datetime.utcnow()
            upload.raw_provider_json = created
            upload.status = "uploaded"
            upload.last_error = None

            self._db.commit()
            self._db.refresh(upload)
            return upload
        except Exception as e:
            upload.status = "failed"
            upload.last_error = str(e)
            self._db.commit()
            self._db.refresh(upload)
            raise

    def patch_upload(
        self,
        provider_type: str,
        upload_id: str,
        status: str | None,
        last_error: str | None,
    ) -> RagProviderFileUpload | None:
        upload = self.get_upload(provider_type=provider_type, upload_id=upload_id)
        if upload is None:
            return None

        if status is not None:
            upload.status = status

        if last_error is not None:
            upload.last_error = last_error

        self._db.commit()
        self._db.refresh(upload)
        return upload

    def delete_upload(self, provider_type: str, upload_id: str) -> bool:
        upload = self.get_upload(provider_type=provider_type, upload_id=upload_id)
        if upload is None:
            return False

        self._db.delete(upload)
        self._db.commit()
        return True

    def _get_local_file(self, file_id: str) -> RagFile:
        rag_file = self._db.query(RagFile).filter(RagFile.id == file_id).one_or_none()
        if rag_file is None:
            raise ValueError("Локальный файл не найден")
        return rag_file

    def _calc_sha256(self, path: Path) -> str:
        if not path.exists() or not path.is_file():
            raise ValueError("Файл отсутствует на диске")

        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
