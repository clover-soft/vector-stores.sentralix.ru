### Шаг 6: Синхронизация баз знаний провайдера с локальной БД
- Цель:
  - Реализовать админ-ручку, которая по `provider_type` синхронизирует уже существующие **Vector Stores** у провайдера с локальными сущностями:
    - `rag_indexes` (базы знаний проекта)
    - `rag_files` (локальные файлы проекта)
    - `rag_index_files` (связь файл ↔ база знаний)
    - `rag_provider_file_uploads` (связь локальный файл ↔ внешний файл у провайдера)
  - Обеспечить корректный маппинг:
    - `provider_vector_store.id` → `rag_indexes.external_id`
  - Обработать расхождения между провайдером и локальной БД:
    - если у провайдера **нет** vector store, который есть локально — локальный `rag_indexes` остаётся, но `external_id` обнуляется и удаляются связанные записи `rag_provider_file_uploads` для файлов этой базы знаний.

- Действия:

  #### 1) Переменные окружения
  - Добавить переменную окружения:
    - `DEFAULT_DOMAIN_ID` — домен по умолчанию для сущностей, которые создаются при синхронизации.
  - Значение по умолчанию: `0`.

  #### 2) API админки
  - Добавить эндпоинт:
    - `POST /api/v1/admin/providers/{provider_type}/sync`
  - Вход:
    - `provider_type: str` (path)
  - Выход (минимально):
    - количество созданных/обновлённых/отвязанных сущностей:
      - `indexes_created`, `indexes_updated`, `indexes_detached`
      - `files_created`, `files_kept`
      - `index_files_created`, `index_files_deleted`
      - `provider_uploads_created`, `provider_uploads_deleted`
      - `file_results: list[object]` (статусы синхронизации по каждому файлу)
      - `files_byte_mismatches: list[object]` (список файлов, где `sha256(local)` != `sha256(provider)`)
      - `errors: list[str]`

  #### 3) Источник истины и общий принцип
  - Источник истины для списка баз знаний и состава файлов **во время синхронизации** — провайдер.
  - Локальная БД приводит своё состояние к провайдеру, но:
    - локальные `rag_indexes` **не удаляются автоматически**.

  #### 4) Синхронизация списка баз знаний (rag_indexes)
  - Получить список vector stores у провайдера через сервисный слой:
    - `ProviderVectorStoresService.list_vector_stores(provider_type=..., limit=...)`
  - Для каждого объекта провайдера `vs`:
    - найти локальный индекс:
      - `RagIndex.provider_type == provider_type` AND `RagIndex.external_id == vs["id"]`
    - если найден:
      - обновить поля (по возможности):
        - `name`, `description`, `expires_after`, `chunking_strategy`, `metadata`.
    - если не найден:
      - создать новый `RagIndex`:
        - `id = uuid4()`
        - `domain_id = DEFAULT_DOMAIN_ID`
        - `provider_type = provider_type`
        - `external_id = vs["id"]`
        - остальные поля заполнить из `vs`.

  #### 5) Синхронизация “локально есть, у провайдера нет”
  - Для всех локальных `RagIndex` по `provider_type` с `external_id IS NOT NULL`:
    - если `external_id` отсутствует в списке `provider_vector_store_ids`:
      - установить `external_id = NULL`.
      - удалить записи `rag_provider_file_uploads` по файлам этой базы знаний:
        - получить `RagIndexFile` по `index_id` → список `file_id`.
        - удалить `RagProviderFileUpload` где:
          - `provider_id == provider_type` AND `local_file_id IN (<file_ids>)`.
      - локальные `RagIndexFile` и `RagFile` **не удалять**.

  #### 6) Синхронизация файлов баз знаний (rag_files + rag_index_files)
  Для каждого актуального vector store у провайдера (`vs_id`):

  - Получить список файлов, прикреплённых к vector store:
    - `ProviderVectorStoresService.list_vector_store_files(provider_type, vector_store_id=vs_id, ...)`

  - Для каждого элемента (минимально содержит `file_id`):

    **6.1) Обеспечить наличие локального RagFile**
    - Поискать локальный файл по внешнему id:
      - `RagFile.external_file_id == file_id`.
    - Если найден:
      - локальный файл **не изменять** (не перезаписывать байты, даже если отличаются от провайдера)
      - посчитать `sha256` локального файла и `sha256` файла у провайдера
      - если `sha256` не совпадает — вернуть файл в списке `files_byte_mismatches`
    - Если не найден — создать локальный файл в режиме “import from provider”:
      - скачать контент файла у провайдера (`retrieve_file_content`) и сохранить в `FILES_ROOT` (по стандартной локальной структуре хранения файлов)
      - определить:
        - `size_bytes` по длине контента
        - `file_name` (если доступно через `retrieve_file`, иначе использовать `file_id`)
        - `file_type` (по расширению `file_name`, иначе `application/octet-stream`)
      - создать `RagFile`:
        - `id = uuid4()`
        - `domain_id = DEFAULT_DOMAIN_ID`
        - `local_path = <путь сохранения>`
        - `external_file_id = file_id`
        - `external_uploaded_at` (если доступно)

    **6.2) Обеспечить наличие связи RagIndexFile**
    - Найти `RagIndex` по `provider_type` и `external_id == vs_id`.
    - Создать (если нет) `RagIndexFile(index_id=<rag_index.id>, file_id=<rag_file.id>, include_order=<по порядку выдачи>)`.

    **6.3) Обеспечить наличие RagProviderFileUpload**
    - Проверить наличие записи `RagProviderFileUpload` для пары:
      - `provider_id == provider_type` AND `local_file_id == rag_file.id`.
    - Если нет — создать запись:
      - `external_file_id = file_id`
      - `status = "uploaded"` (или отдельный статус `"synced"`)
      - `content_sha256` вычислить:
        - либо по скачанному контенту (если файл создавался на шаге 6.1)
        - либо по локальному файлу на диске (если `RagFile` уже существовал).
      - `raw_provider_json` заполнить данными `retrieve_file(file_id)` если доступно.

  - (Опционально, если нужно строгое соответствие провайдеру):
    - если в `rag_index_files` есть файлы, которых нет у провайдера в `vector_store_files_list` — удалить связь `rag_index_files`.
    - при удалении связи НЕ удалять `rag_files`.

  #### 7) Инварианты и требования
  - Нельзя выполнять синхронизацию, если `rag_provider_connections.is_enabled = 0`.
  - На уровне БД не используем `FOREIGN KEY`, связи только логические.
  - Любые ошибки синхронизации должны:
    - логироваться
    - возвращаться в ответе эндпоинта в `errors`.

- Ожидаемый результат:
  - Админ-ручка позволяет привести локальную БД к состоянию провайдера по выбранному `provider_type`.
  - Для vector store у провайдера создаются/обновляются локальные `rag_indexes`.
  - Состав файлов базы знаний синхронизируется через `rag_files`, `rag_index_files`, `rag_provider_file_uploads`.

- Критерии готовности (Definition of Done):
  - Реализован эндпоинт `POST /api/v1/admin/providers/{provider_type}/sync`.
  - Добавлен `DEFAULT_DOMAIN_ID` в конфигурацию (по умолчанию `0`).
  - При расхождении “локально есть, у провайдера нет”:
    - `rag_indexes.external_id` обнуляется
    - удаляются `rag_provider_file_uploads` для файлов этого индекса
    - локальный индекс остаётся.
  - Синхронизация создаёт отсутствующие сущности и связи без использования FK.

- Выполнено: нет
