/** 全局类型定义。 */

// ============================================================
// 通用响应
// ============================================================

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ApiErrorResponse {
  error: string;
  message: string;
  details?: unknown;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// 项目
// ============================================================

export interface Project {
  id: string;
  name: string;
  description?: string;
  cover_image?: string;
  status: "active" | "archived";
  root_path?: string;
  style_preset?: string;
  character_count: number;
  scene_count: number;
  prop_count: number;
  episode_count: number;
  shot_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  cover_image?: string;
  root_path?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  cover_image?: string;
  status?: "active" | "archived";
  style_preset?: string;
}

// ============================================================
// 剧本
// ============================================================

export interface ScriptDocument {
  id: string;
  project_id: string;
  raw_text: string;
  version: number;
  parse_status: "none" | "parsing" | "parsed" | "failed";
  parse_error?: string;
  parsed_at?: string;
  parsed_result?: ParsedResult;
  created_at: string;
  updated_at: string;
}

export interface ParsedResult {
  characters: ParsedCharacter[];
  scenes: ParsedScene[];
  props: ParsedProp[];
  episodes: ParsedEpisode[];
}

export interface ParsedCharacter {
  name: string;
  gender?: string;
  age?: string;
  char_type: "protagonist" | "supporting" | "extra";
  description?: string;
  settings?: string;
}

export interface ParsedScene {
  name: string;
  description?: string;
  settings?: string;
}

export interface ParsedProp {
  name: string;
  description?: string;
  settings?: string;
}

export interface ParsedEpisode {
  episode_no: number;
  title: string;
  summary?: string;
  shots: ParsedShot[];
}

export interface ParsedShot {
  shot_no: number;
  summary?: string;
  first_frame_prompt?: string;
  last_frame_prompt?: string;
  video_prompt?: string;
}

// ============================================================
// 角色 / 场景 / 道具
// ============================================================

export type CharType = "protagonist" | "supporting" | "extra";
export type GenStatus = "none" | "pending" | "generating" | "ready" | "failed";

/** 角色/场景/道具的公共字段 */
export interface BaseEntity {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  settings?: string;
  image_asset_id?: string | null;
  gen_status: GenStatus;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Character extends BaseEntity {
  gender?: string;
  age?: string;
  char_type: CharType;
}

export interface Scene extends BaseEntity {
  camera_hint?: string;
}

export interface Prop extends BaseEntity {}

// ============================================================
// 剧集 / 分镜
// ============================================================

export interface Episode {
  id: string;
  project_id: string;
  episode_no: number;
  title: string;
  summary?: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Shot {
  id: string;
  episode_id: string;
  project_id: string;
  shot_no: number;
  summary?: string;
  first_frame_prompt?: string;
  first_frame_asset_id?: string;
  first_frame_status: GenStatus;
  last_frame_prompt?: string;
  last_frame_asset_id?: string;
  last_frame_status: GenStatus;
  video_prompt?: string;
  video_asset_id?: string;
  video_status: GenStatus;
  camera_size?: string;
  camera_angle?: string;
  camera_movement?: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

// ============================================================
// 素材
// ============================================================

export interface Asset {
  id: string;
  project_id: string;
  asset_type: "image" | "video";
  category: string;
  file_path: string;
  file_name?: string;
  file_size?: number;
  mime_type?: string;
  width?: number;
  height?: number;
  duration?: number;
  provider_id?: string;
  workflow_mapping_id?: string;
  status: "pending" | "ready" | "failed";
  thumbnail_path?: string;
  created_at: string;
  updated_at: string;
}

// ============================================================
// 生成任务
// ============================================================

export type TaskStatus = "pending" | "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type TargetType =
  | "character"
  | "scene"
  | "prop"
  | "shot_first_frame"
  | "shot_last_frame"
  | "shot_video"
  | "script_parse";

export interface GenerationTask {
  id: string;
  project_id: string;
  target_type: TargetType;
  target_id: string;
  provider_type: "comfyui" | "api";
  provider_id?: string;
  workflow_mapping_id?: string;
  input_payload?: Record<string, unknown>;
  output_payload?: Record<string, unknown>;
  status: TaskStatus;
  progress: number;
  progress_message?: string;
  retry_count: number;
  error_message?: string;
  output_asset_id?: string;
  started_at?: string;
  finished_at?: string;
  created_at: string;
  updated_at: string;
}

export interface GenerateRequest {
  project_id: string;
  target_type: TargetType;
  target_id: string;
  provider_type?: "comfyui" | "api";
  provider_id?: string;
  model?: string;
  workflow_mapping_id?: string;
  prompt?: string;
  size?: string;
  count?: number;
  reference_asset_ids?: string[];
  extra_params?: Record<string, unknown>;
  force?: boolean;
}

// ============================================================
// 批量生成
// ============================================================

export interface ParamSpec {
  key: string;
  label: string;
  required: boolean;
  input_type: "select" | "text" | "number" | "slider";
  options?: string[];
  allow_custom?: boolean;
  default?: string;
  placeholder?: string;
  help_text?: string;
  min?: number;
  max?: number;
  step?: number;
}

export interface ExtraField {
  key: string;
  label: string;
  type: "workflow_select" | "text" | "select";
  options?: string[];
  default?: string;
}

export interface ProviderCapabilities {
  provider_kind: string;
  model: string | null;
  param_specs: ParamSpec[];
  // 能力声明
  image_generation: boolean;
  image_to_image: boolean;
  video_generation: boolean;
  batch_support: boolean;
  max_count: number;
  max_reference_images: number;
  supports_negative_prompt: boolean;
  custom_size_range: [number, number];
  reference_images_need_url: boolean;
  // 兼容旧字段
  reference_image: boolean;
  // 视频参考图配置
  video_reference_types?: string[];
  video_reference_hint?: string;
  extra_fields: ExtraField[];
}

// ============================================================
// 批量生成
// ============================================================

export interface BatchGenerateTarget {
  target_type: TargetType;
  target_id: string;
  prompt?: string;
}

export interface BatchGenerateRequest {
  project_id: string;
  targets: BatchGenerateTarget[];
  provider_type: "comfyui" | "api";
  provider_id?: string;
  model?: string;
  workflow_mapping_id?: string;
  size?: string;
  count?: number;
  reference_asset_ids?: string[];
  extra_params?: Record<string, unknown>;
  force?: boolean;
}

// ============================================================
// 分镜关联
// ============================================================

export interface ShotReferenceEntity {
  id: string;
  name: string;
  image_asset_id?: string;
  gen_status: GenStatus;
}

export interface ShotReferences {
  characters: ShotReferenceEntity[];
  scenes: ShotReferenceEntity[];
  props: ShotReferenceEntity[];
  reference_image_ids: string[];
}

// ============================================================
// 提示词模板
// ============================================================

export type PromptTemplateType = "character" | "scene" | "prop" | "episode" | "shot";

export const PROMPT_TEMPLATE_TYPE_LABELS: Record<PromptTemplateType, string> = {
  character: "角色提取",
  scene: "场景提取",
  prop: "道具提取",
  episode: "章节划分",
  shot: "分镜拆分",
};

export interface PromptTemplate {
  id: string;
  name: string;
  template_type: PromptTemplateType;
  description?: string;
  content: string;
  is_default: boolean;
  is_builtin: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

// ============================================================
// 画风预置
// ============================================================

export interface StylePreset {
  id: string;
  title: string;
  description: string;
  is_default: boolean;
  is_builtin: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplateCreate {
  name: string;
  template_type: PromptTemplateType;
  description?: string;
  content: string;
  is_default?: boolean;
  sort_order?: number;
}

export interface PromptTemplateUpdate {
  name?: string;
  template_type?: PromptTemplateType;
  description?: string;
  content?: string;
  is_default?: boolean;
  sort_order?: number;
}

// ============================================================
// Provider 配置
// ============================================================

export type ProviderKind = "openai" | "fal" | "replicate" | "agnes" | "anthropic" | "custom";

// 模型能力标签（机器标识 -> 展示文案，与后端 MODEL_TAG_LABELS 保持一致）
export type ModelTag = "text_reasoning" | "image_generation" | "image_to_image" | "video_generation";

export const MODEL_TAG_LABELS: Record<ModelTag, string> = {
  text_reasoning: "文本推理",
  image_generation: "图片生成",
  image_to_image: "图片修改",
  video_generation: "视频生成",
};

export interface ProviderModel {
  id: string;
  model_name: string;
  tags: ModelTag[];
  sort_order: number;
  param_specs?: ParamSpec[] | null;
  capabilities?: ModelCapabilitiesConfig | null;
}

export interface ProviderModelInput {
  id?: string;
  model_name: string;
  tags: ModelTag[];
  sort_order: number;
  param_specs?: ParamSpec[] | null;
  capabilities?: ModelCapabilitiesConfig | null;
}

/** 模型能力声明（数据驱动，对应后端 ModelCapabilities.to_dict()） */
export interface ModelCapabilitiesConfig {
  image_generation?: boolean;
  image_to_image?: boolean;
  video_generation?: boolean;
  batch_support?: boolean;
  max_count?: number;
  max_reference_images?: number;
  supports_negative_prompt?: boolean;
  custom_size_range?: [number, number];
  reference_images_need_url?: boolean;
  video_reference_types?: string[];
  video_reference_hint?: string;
}

export interface ApiProvider {
  id: string;
  name: string;
  provider_kind: ProviderKind;
  base_url: string;
  api_key_masked: string;
  // 旧版单模型字段兼容
  model?: string;
  // 新版多模型列表
  models: ProviderModel[];
  timeout_seconds: number;
  enabled: boolean;
  is_default: boolean;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface ProviderCreate {
  name: string;
  provider_kind: ProviderKind;
  base_url: string;
  api_key: string;
  models: ProviderModelInput[];
  model?: string;
  timeout_seconds?: number;
  enabled?: boolean;
  is_default?: boolean;
  description?: string;
}

// ── 图床配置 ──

export type HostingProviderType = "smms" | "superbed" | "boltp" | "github" | "custom";

export interface ImageHostingProvider {
  id: string;
  name: string;
  provider_type: HostingProviderType;
  api_url: string;
  token_masked: string;
  has_token: boolean;
  extra_config: Record<string, unknown> | null;
  max_file_size: number;
  is_default: boolean;
  enabled: boolean;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ImageHostingCreate {
  name: string;
  provider_type: HostingProviderType;
  api_url?: string;
  token?: string;
  extra_config?: Record<string, unknown> | null;
  max_file_size?: number;
  is_default?: boolean;
  enabled?: boolean;
  description?: string | null;
}

// ============================================================
// 工作流映射
// ============================================================

export interface WorkflowMapping {
  id: string;
  name: string;
  asset_type: string;
  description?: string;
  workflow_json?: Record<string, unknown>;
  input_mapping?: Record<string, unknown>;
  output_mapping?: Record<string, unknown>;
  provider_type: "comfyui" | "api";
  provider_id?: string;
  is_default: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

// ============================================================
// 系统配置
// ============================================================

export interface SystemConfig {
  app: { name: string; version: string };
  comfyui: { base_url: string; enabled: boolean; timeout: number };
  storage: { projects_root: string };
  default_models: { default_image_model: string; default_text_model: string; default_video_model: string };
  tasks: {
    rate_limit_retry: number;
    rate_limit_wait: number;
    smart_fallback: boolean;
    max_concurrent: number;
  };
}

// ============================================================
// WebSocket 消息
// ============================================================

export interface WsMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: string;
}

/** 剧本解析步骤状态 */
export type ParseStepStatus = "pending" | "active" | "done";

/** 剧本解析步骤定义 */
export interface ParseStep {
  stage: string;
  label: string;
  status: ParseStepStatus;
  summary?: string;
}

/** script.parsing 消息的 data */
export interface ScriptParsingData {
  project_id: string;
  stage: string;
  message?: string;
  completed_stages?: { stage: string; summary: string }[];
}

/** script.stream 消息的 data */
export interface ScriptStreamData {
  project_id: string;
  stage: string;
  tokens: string;
}

/** script.stage_done 消息的 data */
export interface ScriptStageDoneData {
  project_id: string;
  stage: string;
  summary: string;
  completed_stages?: { stage: string; summary: string }[];
}

// ============================================================
// 日志（前后端错误监听）
// ============================================================

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type LogSource = "frontend" | "backend" | "api" | "ws";

export interface LogEntry {
  /** 自增 ID（仅用于列表渲染） */
  id: string;
  /** 原始 ISO8601 时间戳 */
  timestamp: string;
  /** 错误来源 */
  source: LogSource;
  level: LogLevel;
  /** 来源 logger 名（前端：window.onerror 时为 file:lineno；后端：logger name） */
  logger: string;
  /** 错误消息 */
  message: string;
  /** 额外上下文（API URL、stack、status code 等） */
  context?: Record<string, unknown>;
}

export interface LogListResponse {
  total: number;
  returned: number;
  file: string;
  entries: Array<{
    timestamp: string;
    level: LogLevel;
    logger: string;
    message: string;
  }>;
}

/** 后端 /api/logs/* 返回的包装格式（与项目其他 API 一致） */
export interface LogListApiResponse {
  data: LogListResponse;
  message?: string;
}

export interface LogInfoApiResponse {
  data: {
    file: string;
    exists: boolean;
    size_bytes: number;
    modified_at: string | null;
  };
  message?: string;
}

export interface LogClearApiResponse {
  data: { ok: boolean; file: string };
  message?: string;
}

// ── 任务结构化日志（从 DB 读取） ──

export interface TaskLogEntry {
  id: string;
  task_id: string;
  level: string;
  message: string;
  phase?: string;
  event_type?: string;
  data_json?: Record<string, unknown>;
  trace_id?: string;
  data?: string;
  created_at?: string;
}

export interface TaskLogListResponse {
  task_id: string;
  trace_id?: string;
  total: number;
  entries: TaskLogEntry[];
}

export interface TaskLogListApiResponse {
  data: TaskLogListResponse;
  message?: string;
}
