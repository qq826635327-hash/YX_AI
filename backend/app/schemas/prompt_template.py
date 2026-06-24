"""提示词模板 Schema。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.prompt_template import PROMPT_TEMPLATE_TYPES


class PromptTemplateBase(BaseModel):
    """提示词模板基础字段。"""

    name: str = Field(..., max_length=100)
    template_type: str = Field(..., description=f"类型：{', '.join(PROMPT_TEMPLATE_TYPES)}")
    description: Optional[str] = None
    content: str
    is_default: bool = False
    sort_order: int = 0


class PromptTemplateCreate(PromptTemplateBase):
    """创建模板请求。"""

    pass


class PromptTemplateUpdate(BaseModel):
    """更新模板请求（全部可选）。"""

    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    content: Optional[str] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None


class PromptTemplateResponse(PromptTemplateBase):
    """模板响应。"""

    id: str
    is_builtin: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
