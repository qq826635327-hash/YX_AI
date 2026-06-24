"""ApiProvider 模型：API 生成 Provider 配置。"""

from typing import List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import IDMixin, TimestampMixin


# Provider 类型
PROVIDER_KINDS = ("openai", "fal", "replicate", "agnes", "custom")


# 模型能力标签（机器标识 -> 展示文案）
MODEL_TAG_LABELS = {
    "text_reasoning": "文本推理",
    "image_generation": "图片生成",
    "image_to_image": "图片修改",
    "video_generation": "视频生成",
}


class ApiProvider(IDMixin, TimestampMixin, table=True):
    """API Provider 配置表。"""

    __tablename__ = "api_providers"

    name: str = Field(index=True, max_length=100, unique=True)
    provider_kind: str = Field(default="custom", max_length=30, index=True)
    base_url: str = Field(max_length=500)
    # 加密存储的 API Key
    api_key_encrypted: str = Field(default="", max_length=1000)
    # 旧版单模型字段（已弃用，保留用于数据迁移）
    model: Optional[str] = Field(default=None, max_length=100)
    timeout_seconds: int = Field(default=120)
    enabled: bool = Field(default=True, index=True)
    is_default: bool = Field(default=False)
    # 备注
    description: Optional[str] = Field(default=None)

    # 关系：一个 Provider 可有多个模型
    models: List["ProviderModel"] = Relationship(
        back_populates="provider",
        sa_relationship_kwargs={"order_by": "ProviderModel.sort_order", "cascade": "all, delete-orphan"},
    )


class ProviderModel(IDMixin, TimestampMixin, table=True):
    """Provider 下的模型配置表。

    一个 Provider 可绑定多个模型，每个模型可打多个能力标签，
    便于后续按能力（图片生成/视频生成等）筛选。
    """

    __tablename__ = "provider_models"

    provider_id: str = Field(foreign_key="api_providers.id", index=True, max_length=36)
    model_name: str = Field(max_length=100)
    # 能力标签列表，如 ["image_generation", "video_generation"]
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    sort_order: int = Field(default=0)

    # 模型参数规范（数据驱动，优先于 Handler 代码中的 SUPPORTED_MODELS）
    # 格式同 SUPPORTED_MODELS[model].param_specs，为 None 时 fallback 到 Handler 代码
    param_specs: Optional[list] = Field(default=None, sa_column=Column(JSON))
    # 模型能力声明（数据驱动，优先于 Handler 代码中的 ModelCapabilities）
    # 格式同 ModelCapabilities.to_dict()，为 None 时 fallback 到 Handler 代码
    capabilities: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    provider: Optional[ApiProvider] = Relationship(back_populates="models")
