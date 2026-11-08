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
    """使用 Fernet 对通知凭据和 AI Key 做对称加密。

    写入数据库的是密文；只有在实际发送通知或调用 AI 时才解密，API 层只返回掩码。
    """

    def __init__(self, secret_key: str):
        digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        """把明文凭据加密成可安全写入 SQLite 的 ASCII 字符串。"""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """解密数据库中的凭据；密钥不匹配时会抛出 Fernet 异常。"""
        return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")


def mask_config(config: dict) -> dict:
    """返回脱敏后的配置副本，避免敏感字段通过接口泄露。"""
    return {
        key: "••••••••" if key in SENSITIVE_FIELDS and value not in (None, "") else value
        for key, value in config.items()
    }

