"""道具模型（Prop）。"""

from typing import Optional

from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


class Prop(IDMixin, TimestampMixin, table=True):
    """道具：项目中的小物件。"""

    __tablename__ = "props"

    project_id: str = Field(foreign_key="projects.id", index=True, max_length=36, ondelete="CASCADE")
    name: str = Field(index=True, max_length=200)
    description: Optional[str] = Field(default=None)
    settings: Optional[str] = Field(default=None)
    image_asset_id: Optional[str] = Field(
        default=None, foreign_key="assets.id", max_length=36, ondelete="SET NULL"
    )
    gen_status: str = Field(default="none", max_length=20)
    sort_order: int = Field(default=0)
