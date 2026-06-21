"""SQLModel 模型聚合导出。

按模块拆分，每个实体独立文件，便于维护。
导入此模块即可确保所有表模型注册到 SQLModel.metadata。
"""

from app.models.asset import Asset, ASSET_CATEGORIES, ASSET_STATUSES, ASSET_TYPES
from app.models.base import IDMixin, TimestampMixin, gen_uuid, utcnow
from app.models.character import CHARACTER_TYPES, Character
from app.models.episode import Episode
from app.models.project import Project
from app.models.prop import Prop
from app.models.provider import PROVIDER_KINDS, ApiProvider, MODEL_TAG_LABELS, ProviderModel
from app.models.scene import Scene
from app.models.script import ScriptDocument
from app.models.shot import Shot
from app.models.shot_reference import ShotCharacter, ShotScene, ShotProp
from app.models.task import (
    PROVIDER_TYPES,
    TARGET_TYPES,
    TASK_STATUSES,
    GenerationTask,
)
from app.models.task_log import LOG_LEVELS, TaskLog
from app.models.workflow import WORKFLOW_ASSET_TYPES, WorkflowMapping

__all__ = [
    # 基础
    "IDMixin",
    "TimestampMixin",
    "gen_uuid",
    "utcnow",
    # 实体
    "Project",
    "ScriptDocument",
    "Character",
    "Scene",
    "Prop",
    "Episode",
    "Shot",
    "Asset",
    "GenerationTask",
    "ApiProvider",
    "ProviderModel",
    "WorkflowMapping",
    "ShotCharacter",
    "ShotScene",
    "ShotProp",
    # 枚举常量
    "CHARACTER_TYPES",
    "ASSET_TYPES",
    "ASSET_CATEGORIES",
    "ASSET_STATUSES",
    "TARGET_TYPES",
    "PROVIDER_TYPES",
    "TASK_STATUSES",
    "PROVIDER_KINDS",
    "MODEL_TAG_LABELS",
    "WORKFLOW_ASSET_TYPES",
    "LOG_LEVELS",
    "TaskLog",
]
