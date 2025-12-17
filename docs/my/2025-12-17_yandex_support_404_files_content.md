# Обращение в техподдержку Яндекс Cloud

## Тема
`404 Not Found` при запросе содержимого файла: `GET https://rest-assistant.api.cloud.yandex.net/v1/files/{file_id}/content`

## Описание проблемы
Мы используем OpenAPI-совместимый интерфейс Яндекс Cloud (эндпоинт `rest-assistant.api.cloud.yandex.net`) через Python-клиент (совместимый с OpenAI SDK / httpx). При попытке скачать содержимое ранее полученного `file_id` запросом `GET /v1/files/{file_id}/content` API стабильно возвращает `404 Not Found`.

Критично то, что ответ `404` приходит от API-шлюза (есть `x-server-trace-id`), а тело ответа пустое (`content-length: 0`), из-за чего невозможно понять причину (файл не найден, истёк TTL, нет прав, неверный регион/проект, либо требуется другой URL/метод).

## Пример запроса (Python)
Ниже пример запроса, который выполняется в нашем коде (по сути это `GET` на `/v1/files/{file_id}/content`).

### Вариант 1: через OpenAI-совместимый SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://rest-assistant.api.cloud.yandex.net/v1",
    api_key="<YANDEX_API_KEY>",
)

file_id = "fvtsj5c0o2fva9nqsucc"

# SDK делает GET /v1/files/{file_id}/content
content = client.files.content(file_id)
```

### Вариант 2: прямой HTTP-запрос (httpx)
```python
import httpx

base_url = "https://rest-assistant.api.cloud.yandex.net/v1"
file_id = "fvtsj5c0o2fva9nqsucc"

headers = {
    "Authorization": "Api-Key <YANDEX_API_KEY>",
}

url = f"{base_url}/files/{file_id}/content"

with httpx.Client(timeout=60) as http:
    r = http.get(url, headers=headers)
    r.raise_for_status()
    data = r.content
```

## Фактический ответ, который получаем
Лог клиента (урезано только до релевантного):

```text
[2025-12-17 09:01:06,973][openai._base_client][DEBUG][97c56c9d-4d95-4cb5-941e-8e0006239865] HTTP Response: GET https://rest-assistant.api.cloud.yandex.net/v1/files/fvtsj5c0o2fva9nqsucc/content "404 Not Found" Headers({'content-length': '0', 'date': 'Wed, 17 Dec 2025 09:01:06 GMT', 'x-server-trace-id': '839954165675b6d8:f65ca7d80c642b3d:6686b73ee037b728:1', 'server': 'ycalb'})
[2025-12-17 09:01:06,974][openai._base_client][DEBUG][97c56c9d-4d95-4cb5-941e-8e0006239865] request_id: None
[2025-12-17 09:01:06,974][openai._base_client][DEBUG][97c56c9d-4d95-4cb5-941e-8e0006239865] Encountered httpx.HTTPStatusError
Traceback (most recent call last):
  File "/usr/local/lib/python3.12/site-packages/openai/_base_client.py", line 1027, in request
    response.raise_for_status()
  File "/usr/local/lib/python3.12/site-packages/httpx/_models.py", line 829, in raise_for_status
    raise HTTPStatusError(message, request=request, response=self)
httpx.HTTPStatusError: Client error '404 Not Found' for url 'https://rest-assistant.api.cloud.yandex.net/v1/files/fvtsj5c0o2fva9nqsucc/content'
```

### Тело ответа
- **HTTP status**: `404 Not Found`
- **Response body**: пустое (по заголовкам `content-length: 0`)

### Заголовки ответа
- `content-length: 0`
- `date: Wed, 17 Dec 2025 09:01:06 GMT`
- `x-server-trace-id: 839954165675b6d8:f65ca7d80c642b3d:6686b73ee037b728:1`
- `server: ycalb`

## Ожидаемое поведение
Получить бинарное содержимое файла (или понятное JSON-сообщение об ошибке с причиной), чтобы корректно обработать ситуацию программно.

## Просьба к техподдержке
1. Подскажите, в каких случаях `GET /v1/files/{file_id}/content` возвращает `404` (файл удалён, истёк срок хранения, нет прав, неверный облачный контекст и т.д.).
2. Проверьте по `x-server-trace-id`:
   - `839954165675b6d8:f65ca7d80c642b3d:6686b73ee037b728:1`
   что конкретно произошло на стороне API.
3. Подтвердите, что эндпоинт и метод корректны именно для получения **контента** файла, и не требуется другой путь/параметры.
4. Если `file_id` имеет TTL/ограничения, пришлите ссылку на документацию и рекомендуемый паттерн обработки (повторная загрузка/пересоздание файла и т.п.).
