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
    # 当前解析阶段：reading / character / episode / shot / writing
    current_stage: Optional[str] = Field(default=None, max_length=20)
    # 已完成阶段列表 JSON: [{"stage":"reading","summary":"读取完成"}, ...]
    completed_stages: Optional[list] = Field(default=None, sa_column=Column(JSON))
    # 解析前快照：保存解析前的实体数据，用于取消时恢复
    pre_parse_snapshot: Optional[dict] = Field(default=None, sa_column=Column(JSON))
