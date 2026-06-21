"""剧本文档模型（ScriptDocument）。"""

from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


class ScriptDocument(IDMixin, TimestampMixin, table=True):
    """剧本原始文本与解析结果。"""

    __tablename__ = "script_documents"

    project_id: str = Field(foreign_key="projects.id", index=True, max_length=36, ondelete="CASCADE")
    raw_text: str = Field(default="")
    parsed_result: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    version: int = Field(default=1)
    parse_status: str = Field(default="none", max_length=20)
    parse_error: Optional[str] = Field(default=None)
    parsed_at: Optional[str] = Field(default=None, max_length=50)
