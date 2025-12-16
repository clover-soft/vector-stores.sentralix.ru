# Техническое задание (ТЗ)

## 1. Общие сведения

**Название проекта:** `vector-stores.sentralix.ru`

**Назначение:** сервис управления RAG-базами знаний (файлами, индексами и процессом индексации) по единому API-контракту, независимо от провайдера хранения/индексации.

**Провайдеры (планы интеграции):**
- `yandex`
- `openai`
- `sentralix` (локальный движок проекта)

**База данных:** MariaDB

**Технологический стек:** FastAPI + SQLAlchemy + Docker

---

## 2. Цели и зона ответственности сервиса

### 2.1. Цели
- Предоставить единый HTTP API для:
  - управления файлами доменных баз знаний (загрузка/удаление/обновление метаданных);
  - управления индексами (CRUD);
  - связи файлов с индексами;
  - управления процессом индексации у провайдеров (создание/удаление индекса у провайдера, загрузка файлов в индекс, запуск индексации, опрос статусов, синхронизация статусов в БД).

### 2.2. Границы проекта
- Сервис **не является** UI.
- Сервис **не выполняет** бизнес-авторизацию пользователей (если авторизация нужна — применяется внешняя, но сервис должен обеспечить доменную изоляцию на уровне данных и файлов).
- Сервис предоставляет **API-контракт**, по которому внешний бэкенд сможет управлять базами знаний.

---

## 3. Основные сущности и данные

**Правило проекта (важно):** на уровне БД **не используются** `FOREIGN KEY` (и в коде не используется `ForeignKey`).
Связи между таблицами являются логическими (по значениям идентификаторов), а целостность данных обеспечивается сервисным слоем.

### 3.1. Таблица `rag_indexes`
DDL (как источник истины):
- `domain_id` — принадлежность домену.
- `provider_type` — `yandex` / `sentralix` / `openai`.
- `external_id` — идентификатор индекса у провайдера.
- `name` — имя индекса (как в OpenAI vector stores).
- `description` — описание индекса.
- `chunking_strategy` — стратегия чанкинга (OpenAI).
- `expires_after` — политика истечения (OpenAI).
- `file_ids` — список идентификаторов файлов провайдера (OpenAI).
- `metadata` — map с дополнительными метаданными (OpenAI).
- `indexing_status` — `not_indexed | in_progress | done | failed`.
- `indexed_at` — время начала последней попытки индексации.

### 3.2. Таблица `rag_files`
DDL (как источник истины):
- `file_name`, `file_type`, `local_path`, `size_bytes`.
- Внешние идентификаторы и даты загрузки в провайдера фиксируются **только** в таблице `rag_provider_file_uploads`.
- `chunking_strategy` — стратегия чанкинга (OpenAI). Если не задана, используется `auto`.
- `domain_id`.
- `tags` — JSON.
- `notes`.

### 3.3. Таблица `rag_index_files`
DDL (как источник истины):
- `index_id`, `file_id`.
- `include_order` — порядок включения.

### 3.4. Таблица `rag_provider_connections`
DDL (как источник истины):
- `id` — строковый идентификатор провайдера (`provider_type`), PK. Подключения глобальные (без доменной изоляции).
- `base_url` — базовый URL API провайдера (nullable для провайдеров без URL).
- `auth_type` — тип аутентификации (строка).
- `credentials_enc` — зашифрованные учётные данные (JSON).
- `token_enc` — зашифрованное состояние токенов/сессии (JSON).
- `token_expires_at` — срок действия токена/сессии (nullable).
- `is_enabled` — флаг активности.
- `last_healthcheck_at` — время последней проверки доступности.
- `last_error` — последняя диагностическая ошибка.
- `created_at`, `updated_at`.

Пример DDL (ориентир, совпадает по смыслу с перечнем полей выше):
```sql
CREATE TABLE rag_provider_connections (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
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

Инварианты:
- Подключения глобальные: `domain_id` в этой таблице отсутствует.
- `id` равен `provider_type`.
- В сервисе запрещено выполнять провайдерные операции при `is_enabled = 0`.

### 3.5. Таблица `rag_provider_file_uploads`
DDL (как источник истины):
- `id` — UUID, PK.
- `provider_id` — строковый идентификатор провайдера (логическая ссылка на `rag_provider_connections.id`).
- `local_file_id` — идентификатор локального файла (логическая ссылка на `rag_files.id`).
- `external_file_id` — идентификатор файла у провайдера.
- `external_uploaded_at` — время загрузки у провайдера.
- `content_sha256` — контрольная сумма содержимого, по которой можно определять необходимость повторной загрузки.
- `status` — строковый статус (`pending | uploaded | failed | deleted` и т.п.).
- `last_error` — последняя диагностическая ошибка.
- `raw_provider_json` — сырой ответ/метаданные провайдера (JSON).
- `created_at`, `updated_at`.

Пример DDL (ориентир):
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
  CONSTRAINT uq_rpfu_provider_file UNIQUE (provider_id, local_file_id),
  CONSTRAINT uq_rpfu_provider_external_file UNIQUE (provider_id, external_file_id)
);
```

Инварианты:
- Для пары `(provider_id, local_file_id)` должна существовать максимум одна актуальная запись.
- Для пары `(provider_id, external_file_id)` должна существовать максимум одна актуальная запись.
- `content_sha256` фиксирует содержимое локального файла на момент синхронизации.
- `status` — строковый, без enum на уровне БД.

### 3.6. Доменная изоляция
**Ключевой принцип:** любые операции (файлы, индексы, связи) выполняются строго в рамках `domain_id`.
- Все запросы к API должны содержать `domain_id` (предпочтительно в заголовке, например `X-Domain-Id`, либо в URL/теле; вариант должен быть единым для всех ручек).
- Любые выборки из БД фильтруются по `domain_id`.
- Файловая система изолируется по `domain_id`.

---

## 4. Архитектура и слои

### 4.1. Точка входа
- `main.py` — единая точка входа.

### 4.2. Слой API (ручки)
- Принимает и валидирует запросы.
- Не содержит бизнес-логики доступа к БД напрямую.
- Взаимодействует **исключительно** с сервисами.
- Полностью документируется в Swagger (FastAPI OpenAPI).

### 4.3. Слой Pydantic-схем
- Отдельная папка со схемами запросов/ответов.
- Схемы должны быть согласованы с API-контрактом.

### 4.4. Модели (SQLAlchemy)
- Модели лежат в отдельной папке.
- Отражают DDL (поля/типы/индексы/enum).

### 4.5. Сервисный слой
- Сервисы реализуют CRUD и бизнес-операции.
- Разделение ответственности:
  - сервисы файлов;
  - сервисы индексов;
  - сервис связки индекс↔файл;
  - сервис индексации/оркестрации (pipeline отложенной индексации);
  - сервис провайдеров (выбор интеграции по `provider_type`, фасадный доступ).

### 4.6. Интеграция с провайдерами
- Каждая интеграция — в отдельной папке.
- Каждая интеграция предоставляет **один фасад** (точка входа).
- Все фасады должны реализовывать единый контракт (интерфейс/базовый класс).

### 4.7. Доступ к базе
- Сервисы взаимодействуют с БД через единый класс-провайдер базы данных (например `database.py`).
- Используется SQLAlchemy.

### 4.8. Единый класс логирования
- В проекте должен быть единый класс/модуль логирования.
- Логи пишутся согласно переменным окружения.

---

## 5. Структура проекта (ориентир)

Требование: использовать подготовленную структуру папок.

Ожидаемая структура (может уточняться при реализации):
- `main.py`
- `config.py` (импорт настроек из env)
- `database.py` (инициализация SQLAlchemy, сессии)
- `app/`
  - `api/` (роутеры FastAPI)
  - `schemas/` (Pydantic)
  - `models/` (SQLAlchemy модели)
  - `services/` (бизнес-логика)
  - `utils/` (логгер, вспомогательные утилиты)
  - `providers/` (интеграции)
    - `base.py`
    - `yandex/`
    - `openai/`
    - `sentralix/`
- `docs/`
  - `migrations/` (миграции, по требованию проекта)

---

## 6. Конфигурация и переменные окружения

Принцип: **никакого хардкода**. Все параметры — через env и `config.py`.

Минимальный набор (может расширяться):
- `DATABASE_URI` — строка подключения SQLAlchemy.
- `LOG_LEVEL` — уровень логов.
- `LOG_FORMAT` — формат логов.
- `LOG_FILE` — путь к файлу логов.
- `LOG_TO_CONSOLE` — писать ли в stdout.
- `RUNNING_IN_CONTAINER` — признак запуска в Docker.
- `ALLOW_HOSTS` — список разрешённых хостов/адресов (если используется middleware).

Провайдеры:
- `PROVIDER_SECRETS_KEY` — ключ шифрования для секретов и токенов, хранимых в БД (`rag_provider_connections.credentials_enc`, `rag_provider_connections.token_enc`).

---

## 7. Docker и окружение

### 7.1. Запуск
- Сервис запускается в Docker.
- В контейнер пробрасываются volume:
  - `/app` — код
  - `/var/log` — логи
  - `/files` — хранилище файлов

### 7.2. Хранилище файлов
- Все файлы хранятся в `/files` внутри Docker.
- Для каждого домена — отдельная подпапка:
  - `/files/<domain_id>/...`

Рекомендация по структуре хранения:
- `/files/<domain_id>/<rag_file_id>/original/<file_name>`

Требования:
- При загрузке вычисляется `size_bytes`.
- В БД хранится `local_path` (абсолютный путь в контейнере либо путь относительно `/files`, фиксируется единообразно).

---

## 8. API-контракт (черновой, для детализации)

**Базовый префикс:** `/api/v1`

**Доменная идентификация:**
- обязательно передаётся `domain_id` (например заголовок `X-Domain-Id`).

### 8.1. Service health
- `GET /health`
  - Проверка, что сервис поднят.
  - Возвращает статус и версию.

### 8.2. CRUD файлов
- `POST /files` (multipart upload)
  - загрузка файла в `/files/<domain_id>/...`
  - создание записи `rag_files`
  - опционально: `chunking_strategy` (JSON-объект, передаётся как строка в multipart)
- `GET /files`
  - список файлов домена
- `GET /files/{file_id}`
  - получение метаданных
- `GET /files/{file_id}/download`
  - скачивание
- `PATCH /files/{file_id}`
  - изменение `tags`, `notes`, `chunking_strategy` (опционально `file_name` если допускается)
- `DELETE /files/{file_id}`
  - удаление записи и физического файла

### 8.3. CRUD индексов
- `POST /indexes`
  - создание локального индекса (в БД)
- `GET /indexes`
  - список индексов домена
- `GET /indexes/{index_id}`
  - детали индекса
- `PATCH /indexes/{index_id}`
  - изменение параметров (включая `name`, `description`, `chunking_strategy`, `expires_after`, `file_ids`, `metadata`)
- `DELETE /indexes/{index_id}`
  - удаление локального индекса

### 8.4. Связь файл ↔ индекс
- `POST /indexes/{index_id}/files/{file_id}`
  - привязка файла к индексу (создание `rag_index_files`)
- `DELETE /indexes/{index_id}/files/{file_id}`
  - отвязка
- `GET /indexes/{index_id}/files`
  - список файлов, включённых в индекс

### 8.5. Провайдерные операции (проверка состояния)
- Провайдеры выбираются по строковому `provider_type` (без enum).
- Базовый набор админ-ручек мониторинга (без доменной изоляции, отдельный Swagger-раздел):
  - `GET /admin/providers/connections`
  - `GET /admin/providers/connections/{provider_type}`
  - `POST /admin/providers/connections/{provider_type}`
  - `PATCH /admin/providers/connections/{provider_type}`
  - `DELETE /admin/providers/connections/{provider_type}`
  - `GET /admin/providers/{provider_type}/health`
  - `GET /admin/providers/{provider_type}/vector-stores`
  - `GET /admin/providers/{provider_type}/files`
  - CRUD для `rag_provider_file_uploads` в админ-разделе (плюс автосоздание записи при upload файла в провайдер).

Логика (обязательные сценарии):
- Подключения (`rag_provider_connections`):
  - `POST/PATCH /admin/providers/connections/{provider_type}` сохраняет конфигурацию провайдера в БД.
  - Секреты и токены хранятся в полях `credentials_enc`/`token_enc` в зашифрованном виде.
  - `GET /admin/providers/{provider_type}/health`:
    - читает подключение из БД,
    - пытается создать клиента провайдера,
    - делает «лёгкий» запрос (например list) или проверку токена,
    - записывает `last_healthcheck_at`, при ошибке — `last_error`.
- Upload локального файла в провайдера (`rag_provider_file_uploads`):
  - При любой операции, требующей `external_file_id`, сервис сначала обеспечивает наличие/актуальность `rag_provider_file_uploads`.
  - Алгоритм идемпотентности:
    - вычислить `sha256` локального файла,
    - выполнить upsert записи по `(provider_id, local_file_id)`:
      - если записи нет: создать со `status=pending`, `content_sha256=<sha>`,
      - если запись есть и `status=uploaded` и `content_sha256` совпадает: повторную загрузку не выполнять,
      - если `content_sha256` изменился: обновить `content_sha256`, поставить `status=pending` и выполнить повторную загрузку.
    - после успешной загрузки заполнить `external_file_id`, `external_uploaded_at`, `status=uploaded`, `raw_provider_json`.
    - при ошибке заполнить `status=failed`, `last_error`.

---

## 9. Единый контракт провайдера

### 9.1. Требование
Интеграции провайдеров должны иметь единый контракт, реализованный как базовый класс/интерфейс (например `BaseRagProvider`).

### 9.2. Минимальные методы контракта (ориентир)
- Vector stores:
  - `create_vector_store(payload) -> ProviderVectorStore`
  - `list_vector_stores(...) -> list[ProviderVectorStore]`
  - `retrieve_vector_store(external_id: str) -> ProviderVectorStore`
  - `modify_vector_store(external_id: str, payload) -> ProviderVectorStore`
  - `delete_vector_store(external_id: str) -> None`
  - `search_vector_store(external_id: str, query_payload) -> ProviderVectorStoreSearchResult`
- Files:
  - `create_file(local_path: str, meta) -> ProviderFile`
  - `list_files(...) -> list[ProviderFile]`
  - `retrieve_file(external_file_id: str) -> ProviderFile`
  - `retrieve_file_content(external_file_id: str) -> bytes | str`
  - `update_file(external_file_id: str, payload) -> ProviderFile`
  - `delete_file(external_file_id: str) -> None`
- Vector store ↔ files:
  - `attach_file_to_vector_store(external_vector_store_id: str, external_file_id: str) -> ProviderVectorStoreFileBinding`
  - `detach_file_from_vector_store(external_vector_store_id: str, external_file_id: str) -> None`
  - `list_vector_store_files(external_vector_store_id: str) -> list[ProviderVectorStoreFileBinding]`

Примечание: конкретная реализация зависит от возможностей провайдера. Если провайдер не поддерживает отдельную «загрузку файла», допускается схема, когда файл прикрепляется напрямую из `local_path`.

---

## 10. Отложенная индексация (pipeline)

### 10.1. Назначение
Обеспечить асинхронный процесс подготовки индекса у провайдера и запуска индексации на основе файлов, привязанных к индексу.

### 10.2. Сценарий (обязательные шаги)
1. Создание индекса у провайдера.
2. Получение `external_id` и сохранение его в `rag_indexes.external_id`.
3. Подгрузка/прикрепление файлов к индексу (по `rag_index_files`).
4. Запуск индексации.
5. Проверка статуса индексации (polling).
6. Обновление `rag_indexes.indexing_status` и `indexed_at` в локальной базе.
7. Удаление индекса у провайдера (при удалении локального индекса или по TTL/явному запросу).

### 10.3. Статусы
Статус в локальной БД должен соответствовать enum:
- `not_indexed`
- `in_progress`
- `done`
- `failed`

### 10.4. Технические требования к реализации
- Процесс должен быть идемпотентным на уровне API (повторный вызов не должен ломать состояние).
- Все операции должны логироваться (с `request_id`, если используется).
- Ошибки провайдера должны приводить к обновлению `indexing_status = failed` и сохранению диагностической информации в логах.

---

## 11. Документирование Swagger

Требования:
- Все ручки должны иметь:
  - описание;
  - примеры;
  - коды ответов;
  - схемы ошибок.
- Для ошибок рекомендуется единый формат ответа (например `error_code`, `message`, `details`, `request_id`).

---

## 12. Миграции

Требование проекта: миграции хранятся в папке `docs/`.

Предлагаемая структура:
- `docs/migrations/` — миграции (например Alembic), либо SQL-скрипты

Правила:
- DDL в ТЗ является источником истины.
- При реализации миграций — обеспечить воспроизводимость развёртывания.

---

## 13. Пошаговая реализация (этапы)

### Этап 1: Каркас FastAPI + Docker + логирование
- **Цель:** поднять сервис в Docker, получить `/health`, убедиться, что логи пишутся.
- **Действия:**
  - добавить `main.py` с FastAPI приложением;
  - подключить единый логгер;
  - добавить конфиг `config.py` и чтение env;
  - реализовать `GET /health`;
  - убедиться, что контейнер стартует с текущим `Dockerfile`.
- **Ожидаемый результат:** сервис доступен, Swagger открывается, health отвечает.
- **Definition of Done:**
  - `docker-compose up` поднимает сервис без ошибок;
  - `GET /health` возвращает `200`;
  - в `/var/log` пишутся логи согласно env.

### Этап 2: CRUD файлов (доменные файлы)
- **Цель:** управлять файлами базы знаний, хранить их в `/files/<domain_id>/...`.
- **Действия:**
  - SQLAlchemy модель `rag_files` + сервис CRUD;
  - API ручки загрузки/чтения/обновления/удаления;
  - сохранение файлов в `/files` с доменной изоляцией;
  - валидация `file_type`, размер, корректное заполнение `size_bytes`.
- **Ожидаемый результат:** внешний бэкенд может полностью управлять файлами домена.
- **Definition of Done:**
  - загрузка создаёт запись в БД и файл на диске;
  - удаление удаляет запись и файл;
  - список и получение метаданных фильтруются по `domain_id`.

### Этап 3: CRUD индексов + связь индекс↔файл
- **Цель:** управлять индексами и привязкой файлов.
- **Действия:**
  - SQLAlchemy модель `rag_indexes` + CRUD сервис;
  - SQLAlchemy модель `rag_index_files` + сервис связей;
  - API ручки CRUD индексов;
  - API ручки привязки/отвязки файлов к индексу.
- **Ожидаемый результат:** индекс и его состав (набор файлов) управляются в локальной БД.
- **Definition of Done:**
  - связи индекс↔файл корректно создаются/удаляются;
  - все операции доменно изолированы;
  - Swagger задокументирован.

### Этап 4: Интеграции провайдеров (проверка текущих индексов)
- **Цель:** реализовать слой провайдеров и возможность проверять состояние у провайдера.
- **Действия:**
  - создать базовый контракт провайдера;
  - реализовать фасады `yandex`, `openai`, `sentralix`;
  - сервис-роутер провайдеров (выбор по `provider_type`);
  - хранение конфигураций/секретов провайдеров в БД (`rag_provider_connections`, шифрование ключом из env);
  - учёт загрузок файлов в провайдера (`rag_provider_file_uploads`, CRUD и автосоздание при upload);
  - админ-ручки мониторинга провайдеров (Swagger-раздел для админки).
- **Ожидаемый результат:** сервис умеет ходить в провайдера и возвращать список индексов.
- **Definition of Done:**
  - единый контракт реализован всеми провайдерами;
  - провайдер выбирается по строковому `provider_type`;
  - конфиг провайдеров хранится в БД, секреты и токены зашифрованы;
  - ошибки провайдера корректно обрабатываются и логируются.

### Этап 5: Отложенная индексация (полный цикл)
- **Цель:** автоматизировать создание индекса у провайдера и индексацию файлов.
- **Действия:**
  - сервис оркестрации индексации:
    - создать индекс у провайдера → сохранить `external_id`;
    - прикрепить файлы к индексу;
    - запустить индексацию;
    - опрашивать статус;
    - обновлять `indexing_status` в `rag_indexes`;
    - удалять индекс у провайдера по запросу/удалению локального индекса.
  - API ручки для запуска индексации и просмотра статуса (формат уточняется при реализации).
- **Ожидаемый результат:** один вызов API запускает процесс, дальше статус можно получать из БД.
- **Definition of Done:**
  - `external_id` проставляется автоматически;
  - `indexing_status` переходит по стадиям и соответствует реальности у провайдера;
  - при ошибках ставится `failed`, есть диагностические логи;
  - доменная изоляция соблюдена.

---

## 14. Критерии приёмки (общие)
- API стабильно работает в Docker.
- Нет хардкода конфигурации — всё через env + `config.py`.
- Все операции доменно изолированы.
- Хранение файлов соответствует требованиям `/files/<domain_id>/...`.
- Swagger подробно документирован.
- Слой провайдеров реализован как единый контракт.
- Отложенная индексация обновляет статусы в локальной БД.
