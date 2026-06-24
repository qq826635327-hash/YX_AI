"""角色模型（Character）。"""

from typing import Optional

from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin

# 角色分类枚举
CHARACTER_TYPES = ("protagonist", "supporting", "extra")


class Character(IDMixin, TimestampMixin, table=True):
    """角色：项目中的出场人物。"""

    __tablename__ = "characters"

    project_id: str = Field(foreign_key="projects.id", index=True, max_length=36, ondelete="CASCADE")
    name: str = Field(index=True, max_length=200)
    gender: Optional[str] = Field(default=None, max_length=20, description="性别：男/女/其他")
    age: Optional[str] = Field(default=None, max_length=50, description="年龄描述")
    char_type: str = Field(default="protagonist", max_length=20)
    description: Optional[str] = Field(default=None)
    settings: Optional[str] = Field(default=None)
    image_asset_id: Optional[str] = Field(
        default=None, foreign_key="assets.id", max_length=36, ondelete="SET NULL"
    )
    gen_status: str = Field(default="none", max_length=20)
    sort_order: int = Field(default=0)
