/** 配置中心 API：Provider、工作流映射、系统配置。 */

import { http, unwrap, unwrapFull } from "./client";
import type { ApiProvider, ProviderCreate, SystemConfig, WorkflowMapping } from "@/types";

export const providersApi = {
  list: (enabled?: boolean) =>
    unwrap<ApiProvider[]>(http.get("config/providers", { searchParams: enabled !== undefined ? { enabled } : undefined })),

  get: (id: string) => unwrap<ApiProvider>(http.get(`config/providers/${id}`)),

  create: (payload: ProviderCreate) =>
    unwrapFull<ApiProvider>(http.post("config/providers", { json: payload })),

  update: (id: string, payload: Partial<ProviderCreate>) =>
    unwrapFull<ApiProvider>(http.patch(`config/providers/${id}`, { json: payload })),

  delete: (id: string) => unwrapFull<null>(http.delete(`config/providers/${id}`)),

  test: (id: string) => unwrapFull<unknown>(http.post(`config/providers/${id}/test`)),
};

export const workflowsApi = {
  list: (params?: { asset_type?: string; enabled?: boolean }) =>
    unwrap<WorkflowMapping[]>(http.get("config/workflows", { searchParams: params })),

  get: (id: string) => unwrap<WorkflowMapping>(http.get(`config/workflows/${id}`)),

  create: (payload: Partial<WorkflowMapping>) =>
    unwrapFull<WorkflowMapping>(http.post("config/workflows", { json: payload })),

  update: (id: string, payload: Partial<WorkflowMapping>) =>
    unwrapFull<WorkflowMapping>(http.patch(`config/workflows/${id}`, { json: payload })),

  delete: (id: string) => unwrapFull<null>(http.delete(`config/workflows/${id}`)),
};

export const llmConfigApi = {
  update: (payload: Record<string, unknown>) =>
    unwrapFull<unknown>(http.patch("config/llm", { json: payload })),
};

export const systemApi = {
  config: () => unwrap<SystemConfig>(http.get("config/system")),
  comfyui: () => unwrap<SystemConfig["comfyui"] & { output_dir: string }>(http.get("config/comfyui")),
  health: () => http.get("health").json() as Promise<unknown>,
};
