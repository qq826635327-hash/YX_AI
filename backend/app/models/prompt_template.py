"""提示词模板模型。

用户可自定义角色/场景/道具/剧集/分镜等 AI 解析环节的提示词模板。
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.base import IDMixin, TimestampMixin


# 支持的模板类型
PROMPT_TEMPLATE_TYPES = [
    "character",
    "scene",
    "prop",
    "episode",
    "shot",
]


class PromptTemplate(IDMixin, TimestampMixin, table=True):
    """提示词模板表。

    每个模板对应一种解析阶段（角色/场景/道具/剧集/分镜），
    用户可新增、编辑、删除自定义模板，也可设置每个类型的默认模板。
    """

    __tablename__ = "prompt_templates"

    name: str = Field(..., max_length=100, description="模板名称")
    template_type: str = Field(
        ...,
        max_length=20,
        description=f"模板类型：{', '.join(PROMPT_TEMPLATE_TYPES)}",
    )
    description: Optional[str] = Field(default=None, description="模板说明")
    content: str = Field(..., description="提示词内容，支持 {{占位符}}")
    is_default: bool = Field(default=False, description="是否为该类型的默认模板")
    is_builtin: bool = Field(default=False, description="内置模板，不可删除")
    sort_order: int = Field(default=0, description="排序权重")
