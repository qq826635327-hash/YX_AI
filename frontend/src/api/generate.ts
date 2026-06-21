/** 生成任务 API。 */

import { http, unwrap, unwrapFull, unwrapPaginated } from "./client";
import type {
  BatchGenerateRequest,
  GenerateRequest,
  GenerationTask,
  ProviderCapabilities,
} from "@/types";

export const generateApi = {
  submit: (payload: GenerateRequest) =>
    unwrapFull<{ task_id: string; status: string }>(http.post("generate", { json: payload })),

  batch: (payload: BatchGenerateRequest) =>
    unwrapFull<{ task_ids: string[]; count: number }>(http.post("generate/batch", { json: payload })),

  retry: (taskId: string, params?: { provider_id?: string; workflow_mapping_id?: string }) =>
    unwrapFull<{ task_id: string; status: string }>(
      http.post(`generate/${taskId}/retry`, { json: params || {} })
    ),

  cancel: (taskId: string) =>
    unwrapFull<{ task_id: string; status: string }>(http.post(`generate/${taskId}/cancel`)),
};

export const tasksApi = {
  list: (params?: {
    project_id?: string;
    status?: string;
    target_type?: string;
    target_id?: string;
    page?: number;
    page_size?: number;
  }) => unwrapPaginated<GenerationTask>(http.get("tasks", { searchParams: params })),

  /** 批量清理任务（默认清理已结束任务） */
  clear: (params?: { project_id?: string; status?: string }) =>
    unwrapFull<{ cleared: number }>(http.post("tasks/clear", { json: params || {} })),

  get: (id: string) => unwrap<GenerationTask>(http.get(`tasks/${id}`)),

  /** 获取任务日志 */
  getLogs: (taskId: string, limit: number = 100) =>
    unwrap<Array<{ id: string; level: string; message: string; data?: string; created_at: string }>>(
      http.get(`tasks/${taskId}/logs`, { searchParams: { limit } })
    ),
};

export const providerCapabilitiesApi = {
  get: (providerId: string, model?: string) =>
    unwrap<ProviderCapabilities>(
      http.get(`config/providers/${providerId}/capabilities`, {
        searchParams: model ? { model } : undefined,
      })
    ),

  comfyui: () =>
    unwrap<ProviderCapabilities>(http.get("config/providers/comfyui/capabilities")),
};
