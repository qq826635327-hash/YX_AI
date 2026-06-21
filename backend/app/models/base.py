"""SQLModel 模型基类与通用 Mixin。"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def gen_uuid() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """UTC 当前时间。"""
    return datetime.now(timezone.utc)


class TimestampMixin(SQLModel):
    """时间戳 Mixin：所有业务表通用。"""

    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class IDMixin(SQLModel):
    """主键 Mixin：使用 UUID 字符串。"""

    id: str = Field(default_factory=gen_uuid, primary_key=True, max_length=36)
