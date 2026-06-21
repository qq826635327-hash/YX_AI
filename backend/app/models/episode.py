"""剧集模型（Episode）。"""

from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


class Episode(IDMixin, TimestampMixin, table=True):
    """剧集：一个项目包含多集。"""

    __tablename__ = "episodes"

    project_id: str = Field(foreign_key="projects.id", index=True, max_length=36, ondelete="CASCADE")
    episode_no: int = Field(index=True)
    title: str = Field(default="", max_length=200)
    summary: str = Field(default="")
    sort_order: int = Field(default=0)
