from __future__ import annotations

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken


def _make_fernet(key: str) -> Fernet:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_json(data: dict, key: str) -> dict:
    token = _make_fernet(key).encrypt(json.dumps(data).encode("utf-8")).decode("utf-8")
    return {
        "v": 1,
        "alg": "fernet-sha256",
        "token": token,
    }


def decrypt_json(payload: dict, key: str) -> dict:
    if payload.get("v") != 1 or payload.get("alg") != "fernet-sha256" or "token" not in payload:
        raise ValueError("Некорректный формат зашифрованных данных")

    try:
        raw = _make_fernet(key).decrypt(payload["token"].encode("utf-8"))
    except InvalidToken as e:
        raise ValueError("Не удалось расшифровать данные") from e

    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Расшифрованное значение должно быть JSON-объектом")
    return value
