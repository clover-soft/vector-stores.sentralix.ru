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
