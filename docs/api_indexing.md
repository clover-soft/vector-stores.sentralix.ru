# API: запуск индексации и статус

Базовый URL (включая префикс): `<BASE_URL>/api/v1`

Обязательный заголовок:
```
X-Domain-Id: <domain_id>
```

## Публикация (запуск индексации) индекса
`POST /indexes/{index_id}/publish`

Query-параметры:
- `detach_extra` (bool, default `true`) — отсоединять лишние файлы у провайдера
- `force_upload` (bool, default `false`) — форсировать перезаливку файлов
- `dry_run` (bool, default `false`) — только расчёт без фактических действий

Пример:
```bash
curl -X POST "<BASE_URL>/indexes/INDEX_ID/publish?detach_extra=true&force_upload=false&dry_run=false" \
  -H "X-Domain-Id: demo"
```

Ответ 200 (`IndexPublishOut`):
```json
{
  "provider_type": "openai",
  "vector_store_id": "prov-store-id",
  "dry_run": false,
  "created_vector_store": true,
  "will_create_vector_store": false,
  "desired_provider_file_ids": ["prov-file-id"],
  "existing_provider_file_ids": ["prov-file-id"],
  "missing_provider_file_ids": [],
  "extra_provider_file_ids": [],
  "missing_upload_local_file_ids": [],
  "attached_count": 1,
  "detached_count": 0,
  "attach_results": [ {"file_id": "FILE_ID", "status": "attached"} ],
  "errors": []
}
```
Ошибки: 404 (индекс не найден), 400 (валидация), 502 (ошибка провайдера).

## Повторная индексация (без dry-run)
`POST /indexes/{index_id}/reindex`

Query:
- `force_upload` (bool, default `false`)

Пример:
```bash
curl -X POST "<BASE_URL>/indexes/INDEX_ID/reindex?force_upload=true" \
  -H "X-Domain-Id: demo"
```

Ответ 200: тот же формат `IndexPublishOut`.
Ошибки: 404, 400, 502.

## Синхронизировать статус конкретного индекса
`POST /indexes/{index_id}/sync`

Query:
- `force` (bool, default `false`) — обновить статус даже если уже `done`

Пример:
```bash
curl -X POST "<BASE_URL>/indexes/INDEX_ID/sync?force=false" \
  -H "X-Domain-Id: demo"
```

Ответ 200 (`IndexSyncOut`):
```json
{
  "item": {
    "id": "INDEX_ID",
    "provider_type": "openai",
    "external_id": "prov-store-id",
    "name": "docs-index",
    "indexing_status": "in_progress",
    "indexed_at": null,
    "created_at": "...",
    "updated_at": "..."
  },
  "sync_report": {
    "provider_type": "openai",
    "vector_store_id": "prov-store-id",
    "provider_files_count": 10,
    "aggregated_status": "in_progress",
    "forced": false,
    "skipped": false
  }
}
```
Ошибки: 404 (индекс не найден), 409 (нет external_id), 400 (валидация), 502 (ошибка провайдера).

## Синхронизировать статусы всех индексов домена
`POST /indexes/sync`

Query:
- `provider_type` (string, optional) — фильтр провайдера
- `force` (bool, default `false`)

Пример:
```bash
curl -X POST "<BASE_URL>/indexes/sync?provider_type=openai&force=false" \
  -H "X-Domain-Id: demo"
```

Ответ 200 (`IndexesSyncOut`):
```json
{
  "items": [ { "id": "INDEX_ID", "provider_type": "openai", "indexing_status": "done", ... } ],
  "errors": []
}
```
Ошибки: 502 (ошибка провайдера), 400 (валидация входных параметров).

## Статус файлов индекса у провайдера
`GET /indexes/{index_id}/provider-files`

```bash
curl -X GET "<BASE_URL>/indexes/INDEX_ID/provider-files" \
  -H "X-Domain-Id: demo"
```

Ответ 200 (`IndexProviderFilesOut`):
```json
{
  "provider_type": "openai",
  "vector_store_id": "prov-store-id",
  "items": [
    {
      "include_order": 0,
      "file": { "id": "FILE_ID", "file_name": "doc.pdf", ... },
      "provider_upload": {
        "status": "completed",
        "last_error": null,
        "external_file_id": "prov-file-id"
      },
      "provider_vector_store_file": {"status": "completed"}
    }
  ],
  "errors": []
}
```
Ошибки: 404 (индекс не найден), 400 (прочее).
