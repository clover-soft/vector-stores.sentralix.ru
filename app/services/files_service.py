from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from config import get_config
from models.rag_file import RagFile
from models.rag_index import RagIndex
from models.rag_index_file import RagIndexFile


class FilesService:
    def __init__(self, db: Session, domain_id: str) -> None:
        self._db = db
        self._domain_id = domain_id
        self._config = get_config()

    def _make_file_path_for_domain(self, domain_id: str, file_id: str, file_name: str) -> Path:
        safe_name = Path(file_name).name
        return (
            Path(self._config.files_root)
            / domain_id
            / file_id
            / "original"
            / safe_name
        )

    def _make_file_path(self, file_id: str, file_name: str) -> Path:
        return self._make_file_path_for_domain(self._domain_id, file_id, file_name)

    def _get_file_dir_from_local_path(self, local_path: str) -> Path:
        path = Path(local_path)
        return path.parent.parent

    def create_file(
        self,
        upload: UploadFile,
        file_type: str | None,
        tags: dict | list | None,
        notes: str | None,
        chunking_strategy: dict | None,
    ) -> RagFile:
        file_id = str(uuid4())

        original_name = upload.filename or "file"
        safe_name = Path(original_name).name
        detected_type = file_type or upload.content_type or "application/octet-stream"

        path = self._make_file_path(file_id=file_id, file_name=safe_name)
        os.makedirs(path.parent, exist_ok=True)

        size_bytes = 0
        try:
            with open(path, "wb") as f:
                while True:
                    chunk = upload.file.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    size_bytes += len(chunk)
        finally:
            upload.file.close()

        rag_file = RagFile(
            id=file_id,
            domain_id=self._domain_id,
            file_name=safe_name,
            file_type=detected_type,
            local_path=str(path),
            size_bytes=size_bytes,
            chunking_strategy=chunking_strategy,
            tags=tags,
            notes=notes,
        )

        self._db.add(rag_file)
        self._db.commit()
        self._db.refresh(rag_file)
        return rag_file

    def list_files(self, skip: int = 0, limit: int = 100) -> list[RagFile]:
        return (
            self._db.query(RagFile)
            .filter(RagFile.domain_id == self._domain_id)
            .order_by(RagFile.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_file(self, file_id: str) -> RagFile | None:
        return (
            self._db.query(RagFile)
            .filter(RagFile.domain_id == self._domain_id)
            .filter(RagFile.id == file_id)
            .one_or_none()
        )

    def update_file(
        self,
        file_id: str,
        file_name: str | None,
        tags: dict | list | None,
        notes: str | None,
    ) -> RagFile | None:
        rag_file = self.get_file(file_id)
        if rag_file is None:
            return None

        if file_name is not None:
            new_name = Path(file_name).name
            old_path = Path(rag_file.local_path)
            new_path = self._make_file_path(file_id=rag_file.id, file_name=new_name)

            if new_path != old_path:
                os.makedirs(new_path.parent, exist_ok=True)
                if old_path.exists():
                    old_path.replace(new_path)
                else:
                    raise FileNotFoundError("Файл не найден на диске")

                rag_file.local_path = str(new_path)

            rag_file.file_name = new_name

        if tags is not None:
            rag_file.tags = tags

        if notes is not None:
            rag_file.notes = notes

        self._db.commit()
        self._db.refresh(rag_file)
        return rag_file

    def delete_file(self, file_id: str) -> bool:
        rag_file = self.get_file(file_id)
        if rag_file is None:
            return False

        file_dir = self._get_file_dir_from_local_path(rag_file.local_path)
        files_root = Path(self._config.files_root).resolve()
        try:
            resolved_dir = file_dir.resolve()
            if resolved_dir == files_root or files_root not in resolved_dir.parents:
                raise RuntimeError("Попытка удалить путь вне FILES_ROOT")

            if file_dir.exists():
                shutil.rmtree(file_dir, ignore_errors=True)
        except Exception:
            pass

        self._db.delete(rag_file)
        self._db.commit()
        return True

    def change_domain(self, file_id: str, new_domain_id: str) -> tuple[RagFile, dict]:
        new_domain_id = (new_domain_id or "").strip()
        if not new_domain_id:
            raise ValueError("new_domain_id обязателен")

        rag_file = self.get_file(file_id)
        if rag_file is None:
            raise ValueError("Файл не найден")

        old_domain_id = rag_file.domain_id
        if new_domain_id == old_domain_id:
            return rag_file, {
                "old_domain_id": old_domain_id,
                "new_domain_id": new_domain_id,
                "moved_on_disk": False,
                "detached_index_links": 0,
                "indexes_file_ids_updated": 0,
            }

        files_root = Path(self._config.files_root).resolve()

        old_dir = self._get_file_dir_from_local_path(rag_file.local_path)
        moved_on_disk = False
        dest_dir = (Path(self._config.files_root) / new_domain_id / rag_file.id).resolve()
        if dest_dir.exists():
            raise ValueError("Целевая директория файла уже существует")

        if old_dir.exists():
            resolved_old_dir = old_dir.resolve()
            if resolved_old_dir == files_root or files_root not in resolved_old_dir.parents:
                raise ValueError("Попытка переместить путь вне FILES_ROOT")

            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_dir), str(dest_dir))
            moved_on_disk = True

        new_path = self._make_file_path_for_domain(new_domain_id, rag_file.id, rag_file.file_name)
        detached_index_links = 0
        indexes_file_ids_updated = 0
        try:
            rag_file.domain_id = new_domain_id
            rag_file.local_path = str(new_path)

            index_ids = [
                row[0]
                for row in self._db.query(RagIndex.id)
                .filter(RagIndex.domain_id == old_domain_id)
                .all()
            ]
            if index_ids:
                detached_index_links = (
                    self._db.query(RagIndexFile)
                    .filter(RagIndexFile.file_id == rag_file.id)
                    .filter(RagIndexFile.index_id.in_(index_ids))
                    .delete(synchronize_session=False)
                )

            indexes = (
                self._db.query(RagIndex)
                .filter(RagIndex.domain_id == old_domain_id)
                .filter(RagIndex.file_ids.isnot(None))
                .all()
            )
            for idx in indexes:
                if not isinstance(idx.file_ids, list):
                    continue
                if rag_file.id not in idx.file_ids:
                    continue
                idx.file_ids = [x for x in idx.file_ids if x != rag_file.id]
                indexes_file_ids_updated += 1

            self._db.commit()
            self._db.refresh(rag_file)
        except Exception:
            self._db.rollback()
            if moved_on_disk:
                try:
                    rollback_dir = (Path(self._config.files_root) / old_domain_id / rag_file.id).resolve()
                    rollback_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dest_dir), str(rollback_dir))
                except Exception:
                    pass
            raise

        return rag_file, {
            "old_domain_id": old_domain_id,
            "new_domain_id": new_domain_id,
            "moved_on_disk": moved_on_disk,
            "detached_index_links": int(detached_index_links or 0),
            "indexes_file_ids_updated": indexes_file_ids_updated,
        }


def parse_tags(tags: str | None) -> dict | list | None:
    if tags is None or tags.strip() == "":
        return None

    value = json.loads(tags)
    if not isinstance(value, (dict, list)):
        raise ValueError("tags должен быть JSON-объектом или JSON-массивом")

    return value


def parse_chunking_strategy(chunking_strategy: str | None) -> dict | None:
    if chunking_strategy is None or chunking_strategy.strip() == "":
        return None

    value = json.loads(chunking_strategy)
    if not isinstance(value, dict):
        raise ValueError("chunking_strategy должен быть JSON-объектом")

    return value
