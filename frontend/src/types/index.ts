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

export interface Character {
  id: string;
  project_id: string;
  name: string;
  char_type: CharType;
  description?: string;
  settings?: string;
  image_asset_id?: string;
  gen_status: GenStatus;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Scene {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  settings?: string;
  image_asset_id?: string;
  gen_status: GenStatus;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Prop {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  settings?: string;
  image_asset_id?: string;
  gen_status: GenStatus;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

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
  | "shot_video";

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
  reference_preset?: "full" | "first_frame_only" | "first_and_last_frame" | "none";
  extra_params?: Record<string, unknown>;
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
  batch_support: boolean;
  max_count: number;
  reference_image: boolean;
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
  reference_preset?: "full" | "first_frame_only" | "first_and_last_frame" | "none";
  extra_params?: Record<string, unknown>;
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
}

export interface ProviderModelInput {
  id?: string;
  model_name: string;
  tags: ModelTag[];
  sort_order: number;
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
  llm: { enabled: boolean; provider: string; model: string; base_url: string };
  storage: { projects_root: string };
}

// ============================================================
// WebSocket 消息
// ============================================================

export interface WsMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: string;
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
