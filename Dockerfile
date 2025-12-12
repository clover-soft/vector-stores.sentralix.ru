FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg wget
RUN rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install pydub
RUN pip install librosa
RUN pip install ffmpeg
RUN pip install fastapi
RUN pip install uvicorn
RUN pip install python-multipart
RUN pip install opensearch-py
RUN pip install python-dotenv
RUN pip install requests
RUN pip install pydantic
RUN pip install python-magic
RUN pip install pytest
RUN pip install httpx
RUN pip install sqlalchemy
RUN pip install pymysql
RUN pip install email-validator
RUN pip install yandex-cloud-ml-sdk
RUN pip install "pyjwt[crypto]"
RUN pip install jsonpath-ng

WORKDIR /app

# Запускаем сервер
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
