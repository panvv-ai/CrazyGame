from __future__ import annotations

from datetime import datetime, timezone


def iso_utc(value: datetime | None) -> str | None:
    """把数据库中的 naive UTC 时间规范化为带时区标记的 ISO 字符串。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()

