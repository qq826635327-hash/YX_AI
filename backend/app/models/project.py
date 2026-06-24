"""Project 模型：项目主实体。"""

from typing import Optional

from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


class Project(IDMixin, TimestampMixin, table=True):
    """项目表。"""

    __tablename__ = "projects"

    name: str = Field(index=True, max_length=200)
    cover_image: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None)
    root_path: str = Field(max_length=1000, description="项目根目录绝对路径")
    # 项目状态：active / archived
    status: str = Field(default="active", max_length=20, index=True)

    # 统计字段（冗余，定期更新）
    character_count: int = Field(default=0)
    scene_count: int = Field(default=0)
    prop_count: int = Field(default=0)
    episode_count: int = Field(default=0)
    shot_count: int = Field(default=0)

    # 画风预置
    style_preset: Optional[str] = Field(default=None, max_length=100, description="画风预置：如 anime/3d/ink/default")
