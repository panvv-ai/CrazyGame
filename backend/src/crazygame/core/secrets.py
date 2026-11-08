from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

SENSITIVE_FIELDS = {
    "api_key",
    "webhook_url",
    "secret",
    "access_key_id",
    "access_key_secret",
    "phone_numbers",
    "bot_token",
    "token",
}


class SecretBox:
    def __init__(self, secret_key: str):
        digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")


def mask_config(config: dict) -> dict:
    return {
        key: "••••••••" if key in SENSITIVE_FIELDS and value not in (None, "") else value
        for key, value in config.items()
    }

