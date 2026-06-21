"""通用模型序列化工具。"""

from __future__ import annotations

from typing import Any, List

# 需要序列化为字符串的字段
_DATE_FIELDS = ("created_at", "updated_at", "started_at", "finished_at", "last_used_at")


def serialize_model(obj: Any) -> dict:
    """把 ORM/SQLModel 对象序列化为前端友好的 dict。

    处理：
    - datetime 字段 -> ISO 字符串（UTC 时间统一带 Z）
    - 跳过 None
    """
    from datetime import datetime, timezone

    data = obj.model_dump()
    for field in _DATE_FIELDS:
        value = data.get(field)
        if value is not None and isinstance(value, datetime):
            # SQLite 读出的 datetime 可能是 naive（被存成 UTC），需要解释成 UTC
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            data[field] = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return data


def serialize_models(items: List[Any]) -> List[dict]:
    """批量序列化。"""
    return [serialize_model(item) for item in items]
