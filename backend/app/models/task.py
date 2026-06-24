"""GenerationTask 模型：生成任务实体。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


# 任务目标类型
TARGET_TYPES = (
    "character",
    "scene",
    "prop",
    "shot_first_frame",
    "shot_last_frame",
    "shot_video",
    "script_parse",
)
# Provider 类型
PROVIDER_TYPES = ("comfyui", "api")
# 任务状态
TASK_STATUSES = ("pending", "queued", "running", "succeeded", "failed", "cancelled")


class GenerationTask(IDMixin, TimestampMixin, table=True):
    """生成任务表。"""

    __tablename__ = "generation_tasks"

    project_id: str = Field(foreign_key="projects.id", index=True, max_length=36, ondelete="CASCADE")
    target_type: str = Field(max_length=30, index=True)
    target_id: str = Field(max_length=36, index=True, description="目标实体 ID（角色/场景/道具/分镜）")

    # 生成配置
    provider_type: str = Field(max_length=20, description="comfyui / api")
    provider_id: Optional[str] = Field(
        default=None, foreign_key="api_providers.id", max_length=36, ondelete="SET NULL"
    )
    workflow_mapping_id: Optional[str] = Field(
        default=None, foreign_key="workflow_mappings.id", max_length=36, ondelete="SET NULL"
    )

    # 输入输出
    input_payload: Optional[dict] = Field(default=None, sa_column=Column(JSON), description="输入参数 JSON")
    output_payload: Optional[dict] = Field(default=None, sa_column=Column(JSON), description="输出结果 JSON")

    # 状态
    status: str = Field(default="pending", max_length=20, index=True)
    progress: int = Field(default=0, description="0-100")
    retry_count: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)

    # 输出素材
    output_asset_id: Optional[str] = Field(
        default=None, foreign_key="assets.id", max_length=36, ondelete="SET NULL"
    )

    # 开始/结束时间（timezone-aware datetime）
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)

    # 缓存键（用于 Prompt 缓存：相同 model+prompt+params 命中缓存跳过 API 调用）
    cache_key: Optional[str] = Field(default=None, max_length=64, index=True)

    # 自动重试（API已成功但下载失败时，自动重试下载而不重新调API）
    auto_retry_count: int = Field(default=0, description="自动重试已执行次数")

    __table_args__ = (
        Index("ix_generation_tasks_project_status", "project_id", "status"),
    )
