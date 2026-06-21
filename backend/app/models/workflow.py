"""WorkflowMapping 模型：ComfyUI 工作流映射。"""

from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


# 工作流适用的素材类型
WORKFLOW_ASSET_TYPES = (
    "character",
    "scene",
    "prop",
    "first_frame",
    "last_frame",
    "shot_video",
)


class WorkflowMapping(IDMixin, TimestampMixin, table=True):
    """ComfyUI 工作流映射表。"""

    __tablename__ = "workflow_mappings"

    name: str = Field(index=True, max_length=200, unique=True)
    asset_type: str = Field(max_length=30, index=True, description="适用素材类型")
    description: Optional[str] = Field(default=None)

    # ComfyUI 工作流 JSON
    workflow_json: Optional[dict] = Field(default=None, sa_column=Column(JSON), description="ComfyUI 工作流定义")
    # 输入映射
    input_mapping: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # 输出映射
    output_mapping: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Provider 类型与关联
    provider_type: str = Field(default="comfyui", max_length=20)
    provider_id: Optional[str] = Field(
        default=None, foreign_key="api_providers.id", max_length=36, ondelete="SET NULL"
    )

    # 是否默认
    is_default: bool = Field(default=False, index=True)
    enabled: bool = Field(default=True)
