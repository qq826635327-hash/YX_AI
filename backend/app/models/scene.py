"""场景模型（Scene）。"""

from typing import Optional

from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


class Scene(IDMixin, TimestampMixin, table=True):
    """场景：项目中的场景/地点。"""

    __tablename__ = "scenes"

    project_id: str = Field(foreign_key="projects.id", index=True, max_length=36, ondelete="CASCADE")
    name: str = Field(index=True, max_length=200)
    description: Optional[str] = Field(default=None)
    settings: Optional[str] = Field(default=None)
    camera_hint: Optional[str] = Field(default=None, max_length=200, description="镜头建议：远景/全景/中景/室内/室外/时间等")
    image_asset_id: Optional[str] = Field(
        default=None, foreign_key="assets.id", max_length=36, ondelete="SET NULL"
    )
    gen_status: str = Field(default="none", max_length=20)
    sort_order: int = Field(default=0)
