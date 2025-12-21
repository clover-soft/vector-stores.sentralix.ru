from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
from uuid import uuid4
import logging

from sqlalchemy.orm import Session

from models.rag_file import RagFile
from models.rag_provider_file_upload import RagProviderFileUpload
from services.providers_connections_service import ProvidersConnectionsService

logger = logging.getLogger(__name__)


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

    def list_file_uploads(self, *, local_file_id: str, provider_type: str | None = None) -> list[RagProviderFileUpload]:
        q = self._db.query(RagProviderFileUpload).filter(RagProviderFileUpload.local_file_id == local_file_id)
        if provider_type is not None:
            q = q.filter(RagProviderFileUpload.provider_id == provider_type)

        return q.order_by(RagProviderFileUpload.created_at.desc()).all()

    def get_or_sync(
        self,
        provider_type: str,
        local_file_id: str,
        force: bool = False,
        meta: dict | None = None,
    ) -> RagProviderFileUpload:
        logger.info(f"get_or_sync called: provider_type={provider_type}, local_file_id={local_file_id}, force={force}")
        
        rag_file = self._get_local_file(local_file_id)
        logger.info(f"Got local file: {rag_file.file_name}, path: {rag_file.local_path}")
        
        sha256 = self._calc_sha256(Path(rag_file.local_path))
        logger.info(f"Calculated SHA256: {sha256}")

        upload = (
            self._db.query(RagProviderFileUpload)
            .filter(RagProviderFileUpload.provider_id == provider_type)
            .filter(RagProviderFileUpload.local_file_id == local_file_id)
            .one_or_none()
        )

        logger.info(f"Existing upload found: {upload is not None}")

        if (
            upload is not None
            and not force
            and upload.status == "uploaded"
            and upload.content_sha256 == sha256
            and upload.external_file_id
        ):
            logger.info("Returning existing upload")
            return upload

        logger.info("Creating/updating upload record")
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

        logger.info("Getting provider...")
        provider = ProvidersConnectionsService(db=self._db).get_provider(provider_type)
        logger.info(f"Got provider: {type(provider).__name__}")

        try:
            logger.info(f"Calling provider.create_file for {rag_file.local_path}")
            created = provider.create_file(local_path=rag_file.local_path, meta=meta)
            logger.info(f"Provider response: {created}")
            
            external_file_id = created.get("id") or created.get("file_id")
            if not external_file_id:
                raise ValueError("Провайдер не вернул идентификатор файла")

            logger.info(f"Got external_file_id: {external_file_id}")
            upload.external_file_id = str(external_file_id)
            upload.external_uploaded_at = datetime.utcnow()
            upload.raw_provider_json = created
            upload.status = "uploaded"
            upload.last_error = None

            self._db.commit()
            self._db.refresh(upload)
            return upload
        except Exception as e:
            logger.error(f"Error in provider.create_file: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
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
