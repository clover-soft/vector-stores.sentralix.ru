# API: файлы доменных баз знаний

Базовый URL (включая префикс): `<BASE_URL>/api/v1`

Обязательный заголовок домена для всех ручек:

```
X-Domain-Id: <domain_id>
```

## Загрузка файла
`POST /files`

multipart/form-data поля:
- `file` (file, required)
- `file_type` (string, optional) — MIME, если нужно переопределить
- `tags` (string, optional) — JSON-объект или массив строк/объектов
- `notes` (string, optional)
- `chunking_strategy` (string, optional) — JSON, напр. `{ "max_chunk_size": 2000 }`

Пример:
```bash
curl -X POST "<BASE_URL>/files" \
  -H "X-Domain-Id: demo" \
  -F "file=@/path/doc.pdf" \
  -F "file_type=application/pdf" \
  -F "tags={\"project\":\"alpha\"}" \
  -F "notes=Оригинал ТЗ" \
  -F "chunking_strategy={\"max_chunk_size\":2000}"
```

Успешный ответ 200 (`FileOut`):
```json
{
  "id": "uuid",
  "domain_id": "demo",
  "file_name": "doc.pdf",
  "file_type": "application/pdf",
  "local_path": "/files/demo/<id>/original/doc.pdf",
  "size_bytes": 12345,
  "tags": {"project": "alpha"},
  "notes": "Оригинал ТЗ",
  "chunking_strategy": {"max_chunk_size": 2000},
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```
Ошибки: 400 (невалидные поля), 401/403 (авторизация, если настроена), 500 (внутренние).

## Список файлов
`GET /files?skip=0&limit=100`

Пример:
```bash
curl -X GET "<BASE_URL>/files?skip=0&limit=20" \
  -H "X-Domain-Id: demo"
```

Ответ 200 (`FilesListOut`):
```json
{
  "items": [ { "id": "uuid", "file_name": "doc.pdf", "file_type": "application/pdf", "domain_id": "demo", "local_path": "...", "size_bytes": 12345, "tags": null, "notes": null, "chunking_strategy": null, "created_at": "...", "updated_at": "..." } ]
}
```

## Получить метаданные файла
`GET /files/{file_id}`

```bash
curl -X GET "<BASE_URL>/files/FILE_ID" \
  -H "X-Domain-Id: demo"
```

Ответ 200: объект `FileOut`. Ошибки: 404 если нет файла в домене.

## Скачать файл
`GET /files/{file_id}/download`

Возвращает бинарный файл. Ошибки: 404 (нет записи или файла на диске).

## Обновить метаданные файла
`PATCH /files/{file_id}`

Body (`application/json`, `FilePatchIn`):
```json
{
  "file_name": "new.pdf",
  "tags": ["tag1", "tag2"],
  "notes": "описание",
  "chunking_strategy": {"max_chunk_size": 1500}
}
```

Пример:
```bash
curl -X PATCH "<BASE_URL>/files/FILE_ID" \
  -H "X-Domain-Id: demo" \
  -H "Content-Type: application/json" \
  -d '{"file_name":"new.pdf","tags":["tag1"],"notes":"описание"}'
```

Ответ 200: обновлённый `FileOut`. Ошибки: 404, 400 (файл не найден на диске при переименовании).

## Удалить файл
`DELETE /files/{file_id}`

```bash
curl -X DELETE "<BASE_URL>/files/FILE_ID" \
  -H "X-Domain-Id: demo"
```

Ответ 200:
```json
{"status": "ok"}
```
Ошибка: 404 если файла нет.

## Перенос файла в другой домен
`POST /files/{file_id}/change-domain`

Body (`application/json`, `FileChangeDomainIn`):
```json
{ "new_domain_id": "demo-2" }
```

Ответ 200 (`FileChangeDomainOut`):
```json
{
  "file": { "id": "...", "domain_id": "demo-2", "file_name": "doc.pdf", ... },
  "old_domain_id": "demo",
  "new_domain_id": "demo-2",
  "moved_on_disk": true,
  "detached_index_links": 1,
  "indexes_file_ids_updated": 1
}
```
Ошибки: 400 (нет new_domain_id или конфликт путей), 404 (файл не найден).

## Создать/получить загрузку в провайдера
`POST /files/{file_id}/provider-uploads/{provider_type}`

Query: `force` (bool, optional, default false)

Body (`application/json`, optional):
```json
{ "meta": {"source": "crm"} }
```

Пример:
```bash
curl -X POST "<BASE_URL>/files/FILE_ID/provider-uploads/openai?force=false" \
  -H "X-Domain-Id: demo" \
  -H "Content-Type: application/json" \
  -d '{"meta": {"source": "crm"}}'
```

Ответ 200 (`FileProviderUploadOut`):
```json
{
  "id": "upload-uuid",
  "provider_id": "openai",
  "local_file_id": "FILE_ID",
  "external_file_id": "prov-file-id",
  "external_uploaded_at": "2024-01-01T12:00:00Z",
  "content_sha256": "...",
  "status": "completed",
  "last_error": null,
  "raw_provider_json": {"raw": "..."},
  "created_at": "...",
  "updated_at": "..."
}
```
Ошибки: 400 (валидация/конфликт), 404 (файл не найден), 502 (ошибка провайдера).

## Список загрузок файла по провайдерам
`GET /files/{file_id}/provider-uploads?provider_type=<optional>`

```bash
curl -X GET "<BASE_URL>/files/FILE_ID/provider-uploads?provider_type=openai" \
  -H "X-Domain-Id: demo"
```

Ответ 200 (`FileProviderUploadsListOut`):
```json
{
  "items": [
    {
      "id": "upload-uuid",
      "provider_id": "openai",
      "local_file_id": "FILE_ID",
      "external_file_id": "prov-file-id",
      "external_uploaded_at": "2024-01-01T12:00:00Z",
      "content_sha256": "...",
      "status": "completed",
      "last_error": null,
      "raw_provider_json": {"raw": "..."},
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```
Ошибки: 404 если локальный файл не найден.
