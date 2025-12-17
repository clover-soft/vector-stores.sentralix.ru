### Шаг 5: Провайдер Yandex (OpenAI-compat) + полный контракт Vector Stores API через `openai`
- Цель: 
  - Реализовать провайдера `yandex`, который выполняет **все операции** OpenAI Vector Stores API через Python-библиотеку `openai` в режиме совместимости Яндекса.
  - Обеспечить доступ ко всем операциям Vector Stores через единый **сервисный слой проекта**, который выбирает провайдера по `provider_type` и проксирует вызовы.
  - Сделать контракт пригодным для использования:
    - эндпоинтами проекта;
    - другими сервисами проекта (внутренние вызовы, пайплайны).

- Действия: 
  
  #### 1) Конфигурация и совместимость Yandex OpenAI
  - Провайдер имеет `provider_type = "yandex"`.
  - Провайдер работает через `openai` Python SDK (клиент `openai.OpenAI`).
  - Для Vector Stores API у Яндекса используется базовый endpoint:
    - `https://rest-assistant.api.cloud.yandex.net/v1`
  - Аутентификация:
    - `api_key` — API-ключ сервисного аккаунта.
    - `project` — идентификатор каталога (folder_id), в котором создан сервисный аккаунт.
  - Источник данных для подключения:
    - `rag_provider_connections` (глобальная таблица).
    - `credentials_enc` (расшифровывается в сервисном слое).
    - `base_url` может задаваться в `rag_provider_connections.base_url` (приоритет) или в `credentials.base_url`.

  **Требование проекта:** на уровне БД не используем `FOREIGN KEY`, связи только логические.

  #### 2) Контракт провайдера (расширение `BaseProvider`)
  Контракт `BaseProvider` расширен до полного набора операций OpenAI Vector Stores API.

  Минимально требуемые группы методов:

  **A. Vector stores** (`client.vector_stores.*`)
  - `vector_stores_create(...)`
  - `vector_stores_list(...)`
  - `vector_stores_retrieve(vector_store_id, ...)`
  - `vector_stores_update(vector_store_id, ...)` (modify)
  - `vector_stores_delete(vector_store_id, ...)`
  - `vector_stores_search(vector_store_id, query, ...)`

  **B. Vector store files (attach/detach/list + content + update attrs)** (`client.vector_stores.files.*`)
  - `vector_store_files_create(vector_store_id, file_id, ...)` (attach)
  - `vector_store_files_list(vector_store_id, ...)`
  - `vector_store_files_retrieve(vector_store_id, file_id, ...)`
  - `vector_store_files_update(vector_store_id, file_id, attributes, ...)`
  - `vector_store_files_delete(vector_store_id, file_id, ...)` (detach)
  - `vector_store_files_content(vector_store_id, file_id, ...)`

  **C. Vector store file batches** (`client.vector_stores.file_batches.*`)
  - `vector_store_file_batches_create(vector_store_id, file_ids/files, ...)`
  - `vector_store_file_batches_retrieve(vector_store_id, batch_id, ...)`
  - `vector_store_file_batches_cancel(vector_store_id, batch_id, ...)`
  - `vector_store_file_batches_list_files(vector_store_id, batch_id, ...)`

  Примечания:
  - SDK `openai` содержит дополнительные helper-методы (`create_and_poll`, `upload_and_poll` и т.п.). Их можно использовать внутри реализации, но контракт проекта должен покрывать **основные операции API** (см. списки выше).
  - Формат входов/выходов на уровне сервиса проекта — `dict`/`list[dict]` (как и сейчас в `OpenAIProvider`), без жёстких Pydantic-моделей на этом шаге.

  #### 3) Реализация `providers/yandex/`
  - Добавить `providers/yandex/provider.py` с классом `YandexProvider`, реализующим расширенный `BaseProvider`.
  - В `providers/yandex/__init__.py` зарегистрировать фабрику через `register_provider("yandex", ...)`.
  - Создание клиента:
    - `OpenAI(api_key=<api_key>, base_url=<base_url>, project=<folder_id>)`
  - В `healthcheck()` использовать лёгкий вызов, не требующий больших ресурсов (например `client.models.list()`), либо другой доступный метод, который стабильно поддержан Яндексом.

  #### 4) Сервисный слой: единый фасад для Vector Stores операций
  Требование: внешние слои **не должны** напрямую создавать клиентов `openai` или обращаться к классам провайдеров.

  Нужно реализовать сервис (предлагаемое имя): `ProviderVectorStoresService`.
  
  Вход:
  - `db: Session`
  - `provider_type: str`

  Ответственность:
  - Получать провайдера через `ProvidersConnectionsService.get_provider(provider_type)`.
  - Проксировать все операции Vector Stores API (см. п.2).
  - Привести ответы к `dict`/`list[dict]`.
  - Единообразно обрабатывать ошибки:
    - логирование;
    - формирование понятного `last_error` при необходимости (если операция связана с сущностями в БД);
    - преобразование исключений в ошибки уровня API (если сервис вызывается из роутеров).

  #### 5) Интеграция с существующими сервисами и данными
  - `rag_indexes.external_id` трактуется как `vector_store_id` у провайдера.
  - Привязка файлов к индексу:
    - локальная истина: `rag_index_files`.
    - на провайдере: `vector_store_files_create/delete`.
  - Семантика `external_file_id` для `yandex`:
    - В `rag_provider_file_uploads.external_file_id` хранится `vector_store.file.id` (объект `vector_store.file`).
    - Это значение используется как идентификатор для операций `vector_stores.files.retrieve/delete/content`.
    - Получение байтов из Files API (`/v1/files/{file_id}/content`) может быть недоступно (например `404`), поэтому пайплайны не должны на это полагаться.

  #### 6) Требования к эндпоинтам
  На этом шаге требуется обеспечить доступ к операциям через сервисный слой.

  Минимально:
  - Админ-ручки мониторинга провайдера должны уметь работать с новыми операциями через `ProviderVectorStoresService`.
  - Внутренние вызовы (пайплайны/другие сервисы) должны использовать `ProviderVectorStoresService` напрямую.

  #### 7) Набор сценариев (обязательные)
  **Сценарий A: CRUD vector store у Яндекса**
  - Создание (`create`), чтение (`retrieve`), изменение (`update`), удаление (`delete`), список (`list`).

  **Сценарий B: Поиск по vector store**
  - `search(vector_store_id, query, filters, ranking_options, max_num_results, rewrite_query)`.

  **Сценарий C: Привязка/отвязка файлов**
  - attach: `vector_store_files_create`.
  - detach: `vector_store_files_delete`.
  - list/retrieve/update attrs.
  - получение `content` (если поддержано).

  **Сценарий D: Batch-операции**
  - создание батча + получение статуса + отмена + листинг файлов батча.

  #### 8) Инварианты и ошибки
  - Нельзя выполнять провайдерные операции при `rag_provider_connections.is_enabled = 0`.
  - Если `credentials` невалидны/не хватает полей — ошибка должна быть явной и диагностичной.
  - Все ошибки взаимодействия с провайдером должны логироваться.
  - Для методов, которые окажутся не поддержаны Яндексом в режиме совместимости, требуется:
    - явная фиксация в `last_error`/логах;
    - возврат корректной ошибки в API (например 501/502 в зависимости от причины).

- Ожидаемый результат: 
  - В проекте есть реализация `YandexProvider`, работающая через `openai` SDK и endpoint Яндекса.
  - Реализован сервисный фасад `ProviderVectorStoresService`, покрывающий полный контракт Vector Stores API.
  - Эндпоинты/другие сервисы проекта используют только сервисный слой и указывают `provider_type`.

- Критерии готовности (Definition of Done):  
  - `providers/yandex` зарегистрирован в реестре и выбирается по `provider_type="yandex"`.
  - Контракт провайдера расширен и покрывает операции Vector Stores API:
    - `vector_stores.*`
    - `vector_stores.files.*`
    - `vector_stores.file_batches.*`
  - Все операции доступны через `ProviderVectorStoresService` и возвращают `dict`/`list[dict]`.
  - Ошибки обрабатываются единообразно и диагностично.

- Выполнено: да
