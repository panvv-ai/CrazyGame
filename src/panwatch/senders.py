from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

import httpx

from src.panwatch.notifications import (
    build_aliyun_template_params,
    build_feishu_payload,
)


class NotificationSender:
    def send(
        self,
        channel_type: str,
        config: dict,
        title: str,
        content: str,
        context: dict | None = None,
    ) -> bool:
        if channel_type == "feishu":
            return self._send_feishu(config, title, content)
        if channel_type == "aliyun_sms":
            return self._send_aliyun_sms(config, title, content, context or {})
        raise ValueError(f"unsupported channel type: {channel_type}")

    def _send_feishu(self, config: dict, title: str, content: str) -> bool:
        webhook_url = str(config.get("webhook_url") or "")
        if not webhook_url:
            raise ValueError("Feishu webhook_url is required")
        payload = build_feishu_payload(
            title=title,
            body=content,
            url=str(config.get("app_url") or ""),
        )
        secret = str(config.get("secret") or "")
        if secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\n{secret}"
            signature = base64.b64encode(
                hmac.new(
                    string_to_sign.encode("utf-8"),
                    digestmod=hashlib.sha256,
                ).digest()
            ).decode("ascii")
            payload["timestamp"] = timestamp
            payload["sign"] = signature
        response = httpx.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        body = response.json()
        code = body.get("code", body.get("StatusCode", 0))
        return code in (0, "0", None)

    def _send_aliyun_sms(
        self,
        config: dict,
        title: str,
        content: str,
        context: dict,
    ) -> bool:
        access_key_id = str(config.get("access_key_id") or "")
        access_key_secret = str(config.get("access_key_secret") or "")
        sign_name = str(config.get("sign_name") or "")
        language = str(context.get("language") or "zh-CN")
        template_code = str(
            config.get("template_code_en" if language.startswith("en") else "template_code_zh")
            or config.get("template_code")
            or ""
        )
        phone_numbers = str(config.get("phone_numbers") or "")
        if not all(
            (access_key_id, access_key_secret, sign_name, template_code, phone_numbers)
        ):
            raise ValueError("Aliyun SMS configuration is incomplete")

        params = {
            "AccessKeyId": access_key_id,
            "Action": "SendSms",
            "Format": "JSON",
            "PhoneNumbers": phone_numbers,
            "RegionId": config.get("region_id") or "cn-hangzhou",
            "SignName": sign_name,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureNonce": uuid.uuid4().hex,
            "SignatureVersion": "1.0",
            "TemplateCode": template_code,
            "TemplateParam": __import__("json").dumps(
                build_aliyun_template_params(context),
                ensure_ascii=False,
            ),
            "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Version": "2017-05-25",
        }
        params["Signature"] = _aliyun_signature(params, access_key_secret)
        response = httpx.post(
            "https://dysmsapi.aliyuncs.com/",
            data=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("Code") == "OK"


def _percent_encode(value: str) -> str:
    return urllib.parse.quote(str(value), safe="~")


def _aliyun_signature(params: dict, access_key_secret: str) -> str:
    canonical = "&".join(
        f"{_percent_encode(key)}={_percent_encode(value)}"
        for key, value in sorted(params.items())
    )
    string_to_sign = f"POST&%2F&{_percent_encode(canonical)}"
    digest = hmac.new(
        f"{access_key_secret}&".encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _json_string(value: str) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)

