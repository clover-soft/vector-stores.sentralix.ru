# Решения и изменения

## Решения и изменения

### 2025-12-14: Приведение `rag_indexes` к схеме OpenAI Vector Stores

- Цель: привести структуру индексов к полям OpenAI vector stores для дальнейшей интеграции провайдера `openai`.
- Изменения:
  - В `rag_indexes` добавлены поля: `name`, `description`, `chunking_strategy`, `expires_after`, `file_ids`, `metadata`.
  - Удалены устаревшие поля: `index_type`, `max_chunk_size`, `chunk_overlap`, `provider_ttl_days`.
  - Обновлены модель SQLAlchemy, Pydantic-схемы, сервис и API ручки `/api/v1/indexes`.
  - Добавлена миграция `docs/migrations/0003_update_rag_indexes_for_openai.sql` для обновления существующих БД.

### 2025-12-14: Добавление `chunking_strategy` в `rag_files` (OpenAI)

- Цель: поддержать передачу стратегии чанкинга на уровне файлов, совместимую с OpenAI.
- Изменения:
  - В `rag_files` добавлено поле `chunking_strategy` (JSON, опционально).
  - Обновлены модель SQLAlchemy, Pydantic-схемы, сервис и API ручки `/api/v1/files`.
  - Добавлена миграция `docs/migrations/0004_update_rag_files_for_openai.sql` для обновления существующих БД.

### 2025-12-15: Отказ от FOREIGN KEY (по дизайну проекта)

- Цель: зафиксировать правило проекта — на уровне БД **не используются** внешние ключи.
- Решение:
  - В миграциях и моделях **запрещено** добавлять `FOREIGN KEY` / `ForeignKey`.
  - Связи между таблицами являются логическими (по значениям идентификаторов), целостность обеспечивается сервисным слоем.
- Изменения:
  - Убраны FK-ограничения из миграций `docs/migrations/0002_create_rag_indexes.sql` и `docs/migrations/0006_create_rag_provider_file_uploads.sql`.
  - Убраны `ForeignKey(...)` из моделей `app/models/rag_index_file.py` и `app/models/rag_provider_file_upload.py`.

### 2025-12-16: Синхронизация данных провайдера (vector stores + files) с локальной БД

- Цель: добавить админ-механизм синхронизации баз знаний и файлов провайдера с локальными таблицами (`rag_indexes`, `rag_files`, `rag_index_files`, `rag_provider_file_uploads`).
- Изменения:
  - Добавлена переменная окружения `DEFAULT_DOMAIN_ID` (домен по умолчанию для сущностей, создаваемых при синхронизации).
  - Расширен контракт провайдера (`BaseProvider`) методами Files API: `retrieve_file`, `retrieve_file_content`.
  - Реализован сервис `ProviderSyncService` и админ-эндпоинт `POST /api/v1/admin/providers/{provider_type}/sync`.
  - Добавлен отчёт синхронизации по файлам, включая список несоответствий по байтам (SHA256) без перезаписи локальных файлов.

### 2025-12-16: Внешние идентификаторы файлов только в `rag_provider_file_uploads`

- Цель: убрать дублирование и смешение ответственности между `rag_files` и `rag_provider_file_uploads`.
- Изменения:
  - Из `rag_files` убраны поля `external_file_id`, `external_uploaded_at` (внешние данные хранятся только в `rag_provider_file_uploads`).
  - Обновлены Pydantic-схемы файлов: `FileOut` больше не возвращает `external_file_id`/`external_uploaded_at`.
  - Синхронизация провайдера переведена на сопоставление через `rag_provider_file_uploads` по `(provider_id, external_file_id)`.
  - Добавлена миграция `docs/migrations/0007_update_rag_files_remove_external_provider_fields.sql`.

### 2025-12-17: Payload провайдера сохраняется в `rag_indexes.metadata`, стратегия чанков — на уровне файлов

- Цель:
  - Сохранять детальную информацию о vector store (статус, статистика файлов, сроки жизни, last_active_at и др.) в локальной БД.
  - Учитывать, что `chunking_strategy` применяется к файлам, а не к индексу целиком.
- Изменения:
  - В `ProviderSyncService` полный payload `retrieve_vector_store(...)` сохраняется в `rag_indexes.metadata.provider_payload`.
  - `rag_indexes.indexing_status` устанавливается из `payload.status`.
  - `rag_indexes.indexed_at` устанавливается из `payload.created_at` (timestamp → UTC datetime).
  - Из `rag_indexes` удалено поле `chunking_strategy` (миграция `docs/migrations/0008_drop_rag_indexes_chunking_strategy.sql`).
  - При публикации/прикреплении файлов в vector store `chunking_strategy` передаётся из `rag_files.chunking_strategy`.
