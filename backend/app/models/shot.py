"""分镜模型（Shot）。"""

from typing import Optional

from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


class Shot(IDMixin, TimestampMixin, table=True):
    """分镜：一集包含多个分镜。"""

    __tablename__ = "shots"

    episode_id: str = Field(foreign_key="episodes.id", index=True, max_length=36, ondelete="CASCADE")
    project_id: str = Field(foreign_key="projects.id", index=True, max_length=36, ondelete="CASCADE")
    shot_no: int = Field(index=True)
    summary: str = Field(default="")

    # 首帧 / 尾帧 / 视频
    first_frame_prompt: Optional[str] = Field(default=None)
    first_frame_asset_id: Optional[str] = Field(
        default=None, foreign_key="assets.id", max_length=36, ondelete="SET NULL"
    )
    first_frame_status: str = Field(default="none", max_length=20)

    last_frame_prompt: Optional[str] = Field(default=None)
    last_frame_asset_id: Optional[str] = Field(
        default=None, foreign_key="assets.id", max_length=36, ondelete="SET NULL"
    )
    last_frame_status: str = Field(default="none", max_length=20)

    video_prompt: Optional[str] = Field(default=None)
    video_asset_id: Optional[str] = Field(
        default=None, foreign_key="assets.id", max_length=36, ondelete="SET NULL"
    )
    video_status: str = Field(default="none", max_length=20)

    sort_order: int = Field(default=0)
