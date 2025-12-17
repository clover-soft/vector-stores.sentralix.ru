### Шаг 4: Слой провайдеров (yandex/openai/sentralix) + проверка индексов
 - Цель: 
   - Реализовать слой интеграций с провайдерами и единый контракт фасада (совместимый с OpenAI Vector Stores + Files).
   - Перенести конфигурацию провайдеров в БД (глобально, без доменной изоляции).
   - Добавить админ-мониторинг провайдеров (отдельный Swagger-раздел) и базовые CRUD-операции для админ-управления.
 - Действия: 
   - `provider_type` — строковый идентификатор провайдера (без enum), по этому ключу выбирается нужный класс из папки `providers/`.
   - Добавить хранение подключений к провайдерам в БД:
     - Таблица `rag_provider_connections`:
       - `id` = `provider_type` (строка, PK). Ровно одно подключение на каждый `provider_type`.
       - Секреты/учётные данные и динамические токены хранятся в зашифрованном виде (шифрование ключом из env).
   - Добавить учёт загрузок локальных файлов в провайдера:
     - Таблица `rag_provider_file_uploads` (CRUD нужен).
     - Запись в `rag_provider_file_uploads` автоматически создаётся при загрузке файла в провайдера.
     - Внешние идентификаторы и даты загрузки файлов в провайдера фиксируются в `rag_provider_file_uploads`.
   - Добавить общий контракт провайдера (интерфейс/базовый класс), который реализуют все провайдеры, с методами в стиле OpenAI:
     - Vector stores: `create/list/retrieve/modify/delete/search`.
     - Files: `create/list/retrieve/retrieve_content/update/delete`.
     - Vector store ↔ files: `attach/detach/list`.
   - Создать интеграции в отдельных папках:
     - `providers/yandex/`
     - `providers/openai/`
     - `providers/sentralix/`
   - Реализовать сервис-роутер/фабрику выбора провайдера по `provider_type`.
   - Реализовать админ-ручки мониторинга провайдеров (отдельный Swagger tag/раздел), например:
     - `GET /api/v1/admin/providers/connections` — список подключений.
     - `GET /api/v1/admin/providers/connections/{provider_type}` — получить подключение.
     - `POST /api/v1/admin/providers/connections/{provider_type}` — создать/пересоздать подключение.
     - `PATCH /api/v1/admin/providers/connections/{provider_type}` — обновить подключение.
     - `DELETE /api/v1/admin/providers/connections/{provider_type}` — удалить подключение.
     - `GET /api/v1/admin/providers/{provider_type}/health` — проверка доступности/валидности подключения.
     - `GET /api/v1/admin/providers/{provider_type}/vector-stores` — список vector stores у провайдера.
     - `GET /api/v1/admin/providers/{provider_type}/files` — список файлов у провайдера.
     - `GET /api/v1/admin/providers/{provider_type}/file-uploads` — CRUD/мониторинг `rag_provider_file_uploads`.
   - Обработку ошибок провайдера сделать единообразной (логирование + корректные HTTP ответы) и сохранять диагностику в полях `last_error` таблиц.

  #### Модель данных (DDL, источник истины)

  **Важно:** данные подключений провайдеров *не доменно-изолированы*. Это глобальные настройки инстанса сервиса.

  **Таблица `rag_provider_connections`**
  ```sql
  CREATE TABLE rag_provider_connections (
    id VARCHAR(64) NOT NULL PRIMARY KEY, -- provider_type
    base_url VARCHAR(1024) NULL,
    auth_type VARCHAR(32) NOT NULL,
    credentials_enc JSON NULL,
    token_enc JSON NULL,
    token_expires_at DATETIME NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT 1,
    last_healthcheck_at DATETIME NULL,
    last_error TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  );
  ```

  - `id` = `provider_type` (например `openai`, `yandex`, `sentralix`).
  - `auth_type` — строка (например `api_key`, `oauth`, `service_account`, `none`).
  - `credentials_enc` — зашифрованный JSON со статическими секретами/учётными данными.
  - `token_enc` — зашифрованный JSON с динамическим состоянием (refresh token, access token и т.п.).
  - `token_expires_at` — время истечения динамического токена, если применимо.

  **Таблица `rag_provider_file_uploads`**
  ```sql
  CREATE TABLE rag_provider_file_uploads (
    id CHAR(36) NOT NULL PRIMARY KEY,
    provider_id VARCHAR(64) NOT NULL,
    local_file_id CHAR(36) NOT NULL,
    external_file_id VARCHAR(255) NULL,
    external_uploaded_at DATETIME NULL,
    content_sha256 CHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    last_error TEXT NULL,
    raw_provider_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_rpfu_provider_file UNIQUE (provider_id, local_file_id)
  );
  ```

  - `content_sha256` — sha256 содержимого локального файла на момент синхронизации.
  - `external_file_id` — внешний идентификатор у провайдера:
    - для большинства провайдеров это `file_id` из Files API;
    - для `provider_id="yandex"` это `vector_store.file.id` (объект прикрепления файла к vector store).
  - `status` — строковый статус. Базовые статусы:
    - `pending` — создана запись, загрузка ещё не выполнена.
    - `uploaded` — файл успешно загружен/создан у провайдера.
    - `failed` — загрузка завершилась ошибкой.
    - `deleted` — файл у провайдера удалён (если поддерживается), запись сохранена для аудита/диагностики.
  - Уникальность `(provider_id, local_file_id)` означает: *один актуальный маппинг локального файла на провайдер для конкретного провайдера*.

  #### Шифрование секретов и токенов

  - Ключ шифрования берётся из env (например `PROVIDER_SECRETS_KEY`).
  - В БД храним только `credentials_enc`/`token_enc`.
  - Дешифрование выполняется только в сервисном слое при создании клиента провайдера.
  - Ошибки дешифрования/невалидный ключ должны отражаться в `rag_provider_connections.last_error` и в админ-ручке `health`.

  #### Реестр провайдеров и выбор реализации

  - `provider_type` — строковый ключ.
  - Реестр/фабрика провайдеров:
    - вход: `provider_type`
    - выход: класс/инстанс провайдера из `providers/<provider_type>/...`
  - Если `provider_type` неизвестен — возвращаем 404 (или 400) с понятной ошибкой.

  #### Логика и сценарии (обязательные)

  **Сценарий A: создание/обновление подключения (админ)**
  - Админ вызывает `POST/PATCH /admin/providers/connections/{provider_type}`.
  - Сервис:
    - валидирует payload (например `base_url`, `auth_type`, `credentials`),
    - шифрует `credentials` и сохраняет в `rag_provider_connections.credentials_enc`,
    - сбрасывает `last_error`,
    - включает/выключает провайдера через `is_enabled`.

  **Сценарий B: healthcheck (админ)**
  - Админ вызывает `GET /admin/providers/{provider_type}/health`.
  - Сервис:
    - читает `rag_provider_connections`,
    - пытается создать клиента провайдера,
    - выполняет лёгкий запрос к провайдеру (например list) или проверку токена,
    - пишет `last_healthcheck_at`,
    - при ошибке пишет `last_error`.

  **Сценарий C: upload локального файла в провайдера (автосоздание записи)**
  - При операции «загрузить файл в провайдера» (внутренняя операция провайдерного слоя, а также будет использована в пайплайне индексации) сервис обязан:
    - вычислить `sha256` локального файла,
    - сделать upsert записи в `rag_provider_file_uploads` по ключу `(provider_id, local_file_id)`:
      - если записи нет: создать со `status=pending`, `content_sha256=<sha>`,
      - если запись есть и `status=uploaded` и `content_sha256` совпадает: повторную загрузку не выполнять (идемпотентность),
      - если `content_sha256` изменился: обновить `content_sha256`, поставить `status=pending` и перезагрузить.
    - вызвать `provider.files.create(...)` (или эквивалент) и получить `external_file_id`,
    - обновить запись: `external_file_id`, `external_uploaded_at`, `status=uploaded`, `raw_provider_json`.
    - при ошибке: `status=failed`, `last_error`.

  Примечание для `yandex`:
  - `external_file_id` фиксируется как `vector_store.file.id` (идентификатор объекта прикрепления), а не как Files API `file_id`.

  **Сценарий D: привязка файла к vector store у провайдера**
  - Для привязки файла к удалённому vector store:
    - сначала обеспечить наличие `external_file_id` через сценарий C,
    - затем вызвать `provider.vector_stores.files.attach(...)`.
  - Источник истины о составе индекса в сервисе — `rag_index_files`, а на провайдере — соответствующая операция attach/detach.

  #### Инварианты и требования к ошибкам

  - Нельзя выполнять провайдерные операции, если `rag_provider_connections.is_enabled = 0`.
  - Любая ошибка провайдера должна:
    - логироваться,
    - попадать в `last_error` соответствующей сущности (`rag_provider_connections` или `rag_provider_file_uploads`).
  - Повторные вызовы upload должны быть идемпотентны по `content_sha256`.
 - Ожидаемый результат: 
   - Сервис умеет обращаться к провайдерам по единому контракту, а конфигурация/состояние подключений хранится в БД.
   - В Swagger доступен отдельный админ-раздел мониторинга, позволяющий видеть состояние подключений, список vector stores и файлов.
 - Критерии готовности (Definition of Done):  
   - Все провайдеры реализуют единый контракт (vector stores + files + attach/detach + batches).
   - `provider_type` является строковым ключом, а выбор класса провайдера выполняется через фабрику/реестр.
   - Конфигурация провайдеров хранится в БД (`rag_provider_connections`), секреты зашифрованы ключом из env.
   - Таблица `rag_provider_file_uploads` реализована с CRUD, записи создаются автоматически при upload в провайдера.
   - Админ-ручки мониторинга работают и корректно обрабатывают ошибки.
   - Swagger документирован (описания, примеры, коды ответов).
   - Добавлены провайдеры yandex и sentralix, реализован сервис-фасад.
 - Выполнено: да
