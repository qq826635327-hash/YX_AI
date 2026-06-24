"""生成任务、Provider、工作流、素材 Schema。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ============================================================
# 生成任务
# ============================================================

class GenerateRequest(BaseModel):
    """提交生成任务。"""

    project_id: str
    target_type: str = Field(
        ...,
        pattern="^(character|scene|prop|shot_first_frame|shot_last_frame|shot_video)$",
        description="character/scene/prop/shot_first_frame/shot_last_frame/shot_video",
    )
    target_id: str
    provider_type: str = Field(default="api", pattern="^(comfyui|api)$")
    provider_id: Optional[str] = None
    workflow_mapping_id: Optional[str] = None
    prompt: Optional[str] = Field(default=None, description="覆盖默认提示词")
    size: Optional[str] = None
    count: int = Field(default=1, ge=1, le=10)
    reference_asset_ids: list[str] = Field(default_factory=list)
    extra_params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_provider_id(self):
        """api 模式下必须指定 provider_id（ComfyUI 未实现时同样要求）。"""
        if self.provider_type == "api" and not self.provider_id:
            raise ValueError("api 模式必须指定 provider_id")
        # MVP 阶段 ComfyUI 执行器未实现，直接拒绝
        if self.provider_type == "comfyui":
            raise ValueError("ComfyUI 执行器尚未实现，请使用 api 模式")
        return self


class GenerateRetryRequest(BaseModel):
    """重试任务（可切换 Provider/工作流）。"""

    provider_id: Optional[str] = None
    workflow_mapping_id: Optional[str] = None


class BatchGenerateTarget(BaseModel):
    """批量生成中的单个目标。"""
    target_type: str = Field(
        ...,
        pattern="^(character|scene|prop|shot_first_frame|shot_last_frame|shot_video)$",
        description="character/scene/prop/shot_first_frame/shot_last_frame/shot_video",
    )
    target_id: str
    prompt: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    """批量提交生成任务。"""
    project_id: str
    targets: list[BatchGenerateTarget] = Field(..., min_length=1)
    provider_type: str = Field(default="api", pattern="^(comfyui|api)$")
    provider_id: Optional[str] = None
    workflow_mapping_id: Optional[str] = None
    size: Optional[str] = None
    count: int = Field(default=1, ge=1, le=10)
    reference_asset_ids: list[str] = Field(default_factory=list)
    extra_params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_provider_id(self):
        """api 模式下必须指定 provider_id。"""
        if self.provider_type == "api" and not self.provider_id:
            raise ValueError("api 模式下必须指定 provider_id")
        if self.provider_type == "comfyui":
            raise ValueError("ComfyUI 执行器尚未实现，请使用 api 模式")
        return self


# ============================================================
# API Provider 配置
# ============================================================

class ProviderModelItem(BaseModel):
    """Provider 下的单个模型配置（创建/更新/展示通用）。"""

    id: Optional[str] = None
    model_name: str = Field(..., min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list)
    sort_order: int = Field(default=0)
    # 数据驱动的参数规范和能力声明（为 None 时 fallback 到 Handler 代码）
    param_specs: Optional[list[dict[str, Any]]] = None
    capabilities: Optional[dict[str, Any]] = None


class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider_kind: str = Field(default="custom", pattern="^(openai|fal|replicate|agnes|custom)$")
    base_url: str = Field(..., max_length=500)
    api_key: str = Field(default="", description="明文 API Key，后端会加密存储")
    # 新版：支持多个模型，每个模型可打多个能力标签
    models: list[ProviderModelItem] = Field(default_factory=list)
    # 兼容旧版单模型字段（优先使用 models）
    model: Optional[str] = None
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    enabled: bool = True
    is_default: bool = False
    description: Optional[str] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    provider_kind: Optional[str] = Field(default=None, pattern="^(openai|fal|replicate|agnes|custom)$")
    base_url: Optional[str] = Field(default=None, max_length=500)
    api_key: Optional[str] = Field(default=None, description="留空表示不修改")
    models: Optional[list[ProviderModelItem]] = None
    model: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


class ProviderModelView(BaseModel):
    """Provider 模型视图。"""

    id: str
    model_name: str
    tags: list[str]
    sort_order: int
    param_specs: Optional[list[dict[str, Any]]] = None
    capabilities: Optional[dict[str, Any]] = None


class ProviderView(BaseModel):
    """Provider 视图（脱敏）。"""

    id: str
    name: str
    provider_kind: str
    base_url: str
    api_key_masked: str
    # 旧版字段兼容
    model: Optional[str] = None
    # 新版多模型列表
    models: list[ProviderModelView] = Field(default_factory=list)
    timeout_seconds: int
    enabled: bool
    is_default: bool
    description: Optional[str] = None
    created_at: str
    updated_at: str


# ============================================================
# 工作流映射
# ============================================================

class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    asset_type: str = Field(..., description="character/scene/prop/first_frame/last_frame/shot_video")
    description: Optional[str] = None
    workflow_json: Optional[dict[str, Any]] = None
    input_mapping: Optional[dict[str, Any]] = None
    output_mapping: Optional[dict[str, Any]] = None
    provider_type: str = Field(default="comfyui", pattern="^(comfyui|api)$")
    provider_id: Optional[str] = None
    is_default: bool = False
    enabled: bool = True


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    asset_type: Optional[str] = None
    description: Optional[str] = None
    workflow_json: Optional[dict[str, Any]] = None
    input_mapping: Optional[dict[str, Any]] = None
    output_mapping: Optional[dict[str, Any]] = None
    provider_type: Optional[str] = None
    provider_id: Optional[str] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None


# ============================================================
# 素材
# ============================================================

class AssetView(BaseModel):
    id: str
    project_id: str
    asset_type: str
    category: str
    file_path: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    provider_id: Optional[str] = None
    workflow_mapping_id: Optional[str] = None
    status: str
    thumbnail_path: Optional[str] = None
    created_at: str


# ============================================================
# 任务视图
# ============================================================

class TaskView(BaseModel):
    id: str
    project_id: str
    target_type: str
    target_id: str
    provider_type: str
    provider_id: Optional[str] = None
    workflow_mapping_id: Optional[str] = None
    status: str
    progress: int
    retry_count: int
    error_message: Optional[str] = None
    output_asset_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: str
    updated_at: str


# ============================================================
# 分镜关联引用
# ============================================================

class ShotReferenceAdd(BaseModel):
    """给分镜添加关联实体。"""
    entity_ids: list[str] = Field(..., min_length=1)


class ProviderCapabilitiesView(BaseModel):
    """Provider 能力声明（含动态参数规范）。"""

    provider_kind: str
    # 当 Provider 配置多个模型时，此处为代表模型（默认取第一个）
    model: str | None = None
    # 该 Provider 下所有模型（含标签），供前端筛选
    models: list[ProviderModelView] = Field(default_factory=list)
    param_specs: list[dict[str, Any]] = Field(default_factory=list)
    batch_support: bool = False
    max_count: int = 1
    reference_image: bool = False
    max_reference_images: int = 0
    supports_negative_prompt: bool = False
    reference_images_need_url: bool = False
    # 视频参考图配置
    video_reference_types: list[str] = Field(default_factory=lambda: ["first_frame", "last_frame", "character", "scene", "prop"])
    video_reference_hint: str = ""
    extra_fields: list[dict[str, Any]] = Field(default_factory=list)
