"""Asset 模型：素材资源实体。"""

from typing import Optional

from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


# 素材类型
ASSET_TYPES = ("image", "video")
# 素材分类
ASSET_CATEGORIES = (
    "character",
    "scene",
    "prop",
    "first_frame",
    "last_frame",
    "shot_video",
    "upload",
)
# 素材状态
ASSET_STATUSES = ("pending", "ready", "failed")


class Asset(IDMixin, TimestampMixin, table=True):
    """素材资源表。"""

    __tablename__ = "assets"

    project_id: str = Field(foreign_key="projects.id", index=True, max_length=36, ondelete="CASCADE")
    asset_type: str = Field(max_length=20, index=True, description="image / video")
    category: str = Field(max_length=30, index=True, description="character/scene/prop/first_frame/...")
    file_path: str = Field(max_length=1000, description="相对项目根目录的路径")
    file_name: Optional[str] = Field(default=None, max_length=300)
    file_size: Optional[int] = Field(default=None)
    mime_type: Optional[str] = Field(default=None, max_length=100)
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    duration: Optional[float] = Field(default=None, description="视频时长（秒）")

    # 生成来源
    provider_id: Optional[str] = Field(
        default=None, foreign_key="api_providers.id", max_length=36, ondelete="SET NULL"
    )
    workflow_mapping_id: Optional[str] = Field(
        default=None, foreign_key="workflow_mappings.id", max_length=36, ondelete="SET NULL"
    )
    task_id: Optional[str] = Field(
        default=None, foreign_key="generation_tasks.id", max_length=36, ondelete="SET NULL"
    )

    status: str = Field(default="pending", max_length=20, index=True)
    # 关联目标（哪个实体生成了这个素材）
    target_type: Optional[str] = Field(default=None, max_length=20, index=True, description="character/scene/prop/shot_first_frame/...")
    target_id: Optional[str] = Field(default=None, max_length=36, index=True, description="关联的实体 ID")
    # 缩略图路径
    thumbnail_path: Optional[str] = Field(default=None, max_length=1000)
    # 图床公网 URL（供需要公网地址的 API 使用，如 Agnes 视频）
    public_url: Optional[str] = Field(default=None, max_length=1000, description="图床公网 URL")
    public_url_uploaded_at: Optional[str] = Field(default=None, max_length=40, description="图床上传时间 ISO8601")
    public_url_file_hash: Optional[str] = Field(default=None, max_length=64, description="上传时的文件 SHA256")
