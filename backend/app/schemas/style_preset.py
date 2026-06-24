"""画风预置 Schema。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StylePresetBase(BaseModel):
    """画风预置基础字段。"""

    title: str = Field(..., max_length=100, description="画风选项名")
    description: str = Field(..., max_length=500, description="提示词文本")
    is_default: bool = False
    sort_order: int = 0


class StylePresetCreate(StylePresetBase):
    """创建画风预置请求。"""

    pass


class StylePresetUpdate(BaseModel):
    """更新画风预置请求（全部可选）。"""

    title: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None


class StylePresetResponse(StylePresetBase):
    """画风预置响应。"""

    id: str
    is_builtin: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
