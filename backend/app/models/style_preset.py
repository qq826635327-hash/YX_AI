"""画风预置模型。

用户可自定义画风预置，每个预置包含标题（选项名）和描述（提示词文本）。
剧本解析时自动将选中画风的描述注入 {{style_hint}} 占位符。
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


class StylePreset(IDMixin, TimestampMixin, table=True):
    """画风预置表。

    title：画风选项名（如"写实摄影"、"二次元动漫"），用于前端选择器展示。
    description：提示词文本（如"写实摄影，真实感影像，电影级画质，8K超高清"），
                 解析时注入模板的 {{style_hint}} 占位符。
    """

    __tablename__ = "style_presets"

    title: str = Field(..., max_length=100, description="画风选项名，如：写实摄影")
    description: str = Field(
        ...,
        max_length=500,
        description="提示词文本，注入模板 {{style_hint}} 占位符",
    )
    is_default: bool = Field(default=False, description="是否为默认画风")
    is_builtin: bool = Field(default=False, description="内置预置，不可删除")
    sort_order: int = Field(default=0, description="排序权重")
