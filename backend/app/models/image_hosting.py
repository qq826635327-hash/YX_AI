"""ImageHostingProvider 模型：图床配置表。"""

from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.base import IDMixin, TimestampMixin

# 图床类型标识
HOSTING_PROVIDER_TYPES = ("smms", "superbed", "boltp", "github", "custom")


class ImageHostingProvider(IDMixin, TimestampMixin, table=True):
    """图床配置表。"""

    __tablename__ = "image_hosting_providers"

    name: str = Field(index=True, max_length=100, unique=True)
    provider_type: str = Field(default="custom", max_length=30, index=True)
    # 上传接口地址（custom 类型必填，预设类型自动填充）
    api_url: str = Field(default="", max_length=500)
    # 加密存储的密钥/Token
    token_encrypted: str = Field(default="", max_length=2000)
    # 额外配置（JSON），如 GitHub 的 owner/repo/branch/path_prefix
    extra_config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # 文件大小限制（字节），0 表示不限制
    max_file_size: int = Field(default=10485760)  # 默认 10MB
    # 是否为默认图床
    is_default: bool = Field(default=False)
    # 是否启用
    enabled: bool = Field(default=True, index=True)
    # 备注
    description: Optional[str] = Field(default=None)
