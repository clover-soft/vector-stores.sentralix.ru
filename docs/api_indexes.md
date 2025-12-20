# API: CRUD индексов

Базовый URL (включая префикс): `<BASE_URL>/api/v1`

Обязательный заголовок:
```
X-Domain-Id: <domain_id>
```

## Создать индекс
`POST /indexes`

Body (`application/json`, `IndexCreateIn`):
```json
{
  "provider_type": "openai",
  "name": "docs-index",
  "description": "Индекс документации",
  "expires_after": {"ttl_days": 30},
  "file_ids": ["FILE_ID1", "FILE_ID2"],
  "metadata": {"env": "dev"}
}
```

Пример:
```bash
curl -X POST "<BASE_URL>/indexes" \
  -H "X-Domain-Id: demo" \
  -H "Content-Type: application/json" \
  -d '{"provider_type":"openai","name":"docs-index","file_ids":["FILE_ID"]}'
```

Ответ 200 (`IndexOut`):
```json
{
  "id": "uuid",
  "domain_id": "demo",
  "provider_type": "openai",
  "external_id": null,
  "name": "docs-index",
  "description": "Индекс документации",
  "expires_after": {"ttl_days": 30},
  "file_ids": ["FILE_ID"],
  "metadata": {"env": "dev"},
  "indexing_status": "not_indexed",
  "indexed_at": null,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```
Ошибки: 400 (валидация), 401/403, 500.

## Список индексов
`GET /indexes?skip=0&limit=100`

```bash
curl -X GET "<BASE_URL>/indexes?skip=0&limit=20" \
  -H "X-Domain-Id: demo"
```

Ответ 200 (`IndexesListOut`):
```json
{ "items": [ { "id": "uuid", "provider_type": "openai", "name": "docs-index", "indexing_status": "not_indexed", "created_at": "...", "updated_at": "..." } ] }
```

## Получить индекс
`GET /indexes/{index_id}`

```bash
curl -X GET "<BASE_URL>/indexes/INDEX_ID" \
  -H "X-Domain-Id: demo"
```

Ответ 200: объект `IndexOut`. Ошибка 404 если индекс не найден в домене.

## Обновить индекс
`PATCH /indexes/{index_id}`

Body (`application/json`, `IndexPatchIn`):
```json
{
  "provider_type": "openai",
  "name": "new-name",
  "description": "описание",
  "expires_after": {"ttl_days": 60},
  "file_ids": ["FILE_ID"],
  "metadata": {"env": "prod"}
}
```

Пример:
```bash
curl -X PATCH "<BASE_URL>/indexes/INDEX_ID" \
  -H "X-Domain-Id: demo" \
  -H "Content-Type: application/json" \
  -d '{"name":"new-name","metadata":{"env":"prod"}}'
```

Ответ 200: обновлённый `IndexOut`. Ошибка 404 если индекс не найден.

## Удалить индекс
`DELETE /indexes/{index_id}`

```bash
curl -X DELETE "<BASE_URL>/indexes/INDEX_ID" \
  -H "X-Domain-Id: demo"
```

Ответ 200:
```json
{"status": "ok"}
```
Ошибка: 404 если индекс не найден.

## Привязать файл к индексу
`POST /indexes/{index_id}/files/{file_id}`

```bash
curl -X POST "<BASE_URL>/indexes/INDEX_ID/files/FILE_ID" \
  -H "X-Domain-Id: demo"
```

Ответ 200: `{ "status": "ok" }`
Ошибки: 404 (индекс/файл не найден), 409 (файл уже привязан).

## Отвязать файл от индекса
`DELETE /indexes/{index_id}/files/{file_id}`

```bash
curl -X DELETE "<BASE_URL>/indexes/INDEX_ID/files/FILE_ID" \
  -H "X-Domain-Id: demo"
```

Ответ 200: `{ "status": "ok" }`
Ошибка: 404 (связь не найдена).

## Список файлов индекса
`GET /indexes/{index_id}/files`

```bash
curl -X GET "<BASE_URL>/indexes/INDEX_ID/files" \
  -H "X-Domain-Id: demo"
```

Ответ 200 (`IndexFilesListOut`):
```json
{
  "items": [
    {
      "include_order": 0,
      "file": {
        "id": "FILE_ID",
        "file_name": "doc.pdf",
        "file_type": "application/pdf",
        "domain_id": "demo",
        "local_path": "...",
        "size_bytes": 12345,
        "tags": null,
        "notes": null,
        "chunking_strategy": null,
        "created_at": "...",
        "updated_at": "..."
      }
    }
  ]
}
```
Ошибка: 404 если индекс не найден.

## Поиск по индексу
`POST /indexes/{index_id}/search`

Body (`application/json`, `IndexSearchIn`):
```json
{
  "query": "что такое RAG",
  "filters": {"project": "alpha"},
  "max_num_results": 5,
  "ranking_options": {"similarity": "cosine"},
  "rewrite_query": true
}
```

Пример:
```bash
curl -X POST "<BASE_URL>/indexes/INDEX_ID/search" \
  -H "X-Domain-Id: demo" \
  -H "Content-Type: application/json" \
  -d '{"query":"что такое RAG","max_num_results":3}'
```

Ответ 200 (`IndexSearchOut`):
```json
{ "items": [ { "text": "...", "score": 0.89, "metadata": {"file_id": "FILE_ID"} } ] }
```
Ошибки: 404 (индекс не найден), 409 (нет external_id), 400 (валидация), 502 (ошибка провайдера).

## Просмотр файлов индекса у провайдера
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
