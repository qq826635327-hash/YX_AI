/** React Query Hooks：剧本、生成任务、配置。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scriptApi } from "@/api/script";
import { generateApi, tasksApi, providerCapabilitiesApi } from "@/api/generate";
import { providersApi, workflowsApi, systemApi, llmConfigApi } from "@/api/config";
import { toast } from "@/stores/ui";
import { assetsApi } from "@/api/assets";
import type { BatchGenerateRequest, GenerateRequest } from "@/types";

// ============================================================
// 剧本
// ============================================================

export function useScript(projectId: string) {
  return useQuery({
    queryKey: ["script", projectId],
    queryFn: () => scriptApi.get(projectId),
    enabled: !!projectId,
  });
}

export function useSaveScript(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rawText: string) => scriptApi.update(projectId, rawText),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["script", projectId] });
      toast.success("剧本已保存");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useParseScript(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (force: boolean) => scriptApi.parse(projectId, force),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["script", projectId] });
      toast.info("剧本解析已启动，请稍候");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ============================================================
// 生成任务
// ============================================================

export function useGenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: GenerateRequest) => generateApi.submit(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("任务已提交");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useRetryTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, ...params }: { taskId: string; provider_id?: string; workflow_mapping_id?: string }) =>
      generateApi.retry(taskId, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("任务已重新提交");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useCancelTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => generateApi.cancel(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("任务已取消");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useClearTasks() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params?: { project_id?: string; status?: string }) =>
      tasksApi.clear(params),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      toast.success(`已清理 ${data.data?.cleared ?? 0} 个任务`);
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useBatchGenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: BatchGenerateRequest) => generateApi.batch(payload),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      toast.success(`已提交 ${res.data.count} 个生成任务`);
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteAsset() {
  return useMutation({
    mutationFn: (assetId: string) => assetsApi.delete(assetId, true),
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useProviderCapabilities(providerId?: string, model?: string, isComfyui?: boolean) {
  return useQuery({
    queryKey: ["provider-capabilities", providerId, model, isComfyui],
    queryFn: () =>
      isComfyui
        ? providerCapabilitiesApi.comfyui()
        : providerCapabilitiesApi.get(providerId!, model),
    enabled: !!(isComfyui || providerId),
  });
}

export function useTasks(params?: {
  project_id?: string;
  status?: string;
  target_type?: string;
  target_id?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: [
      "tasks",
      params?.project_id,
      params?.status,
      params?.target_type,
      params?.target_id,
      params?.page,
      params?.page_size,
    ],
    queryFn: () => tasksApi.list(params),
    // 智能轮询：有活跃任务时 5s，否则 30s（WS 推送会即时 invalidate）
    refetchInterval: (query) => {
      const items = query.state.data?.items || [];
      const hasActive = items.some(
        (t: any) => t.status === "pending" || t.status === "running" || t.status === "queued"
      );
      return hasActive ? 5000 : 30000;
    },
  });
}

/** 获取指定实体的 pending/running 任务（用于详情页显示加载占位符）。 */
export function usePendingTasks(projectId: string, targetType: string, targetId: string) {
  return useQuery({
    queryKey: ["pending-tasks", projectId, targetType, targetId],
    queryFn: () =>
      tasksApi.list({
        project_id: projectId,
        target_type: targetType,
        target_id: targetId,
        status: "pending,running,queued", // 只查进行中的任务
        page_size: 20,
      }),
    refetchInterval: (query) => {
      // 如果有 pending/running 任务，2 秒轮询；否则停止轮询
      const items = query.state.data?.items || [];
      const hasActive = items.some(
        (t: any) => t.status === "pending" || t.status === "running" || t.status === "queued"
      );
      return hasActive ? 2000 : false; // 无进行中任务时停止轮询
    },
    enabled: !!projectId && !!targetId,
  });
}

/** 轮询单个任务状态。 */
export function useTaskPolling(taskId: string | null) {
  return useQuery({
    queryKey: ["task-poll", taskId],
    queryFn: () => tasksApi.get(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "succeeded" || status === "failed" || status === "cancelled") {
        return false; // 停止轮询
      }
      return 2000; // 2 秒轮询
    },
    refetchOnWindowFocus: false,
  });
}

// ============================================================
// 配置
// ============================================================

export function useProviders(enabled?: boolean) {
  return useQuery({
    queryKey: ["providers", enabled],
    queryFn: () => providersApi.list(enabled),
  });
}

export function useCreateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof providersApi.create>[0]) => providersApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["providers"] });
      toast.success("Provider 已创建");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Partial<Parameters<typeof providersApi.update>[1]>) =>
      providersApi.update(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["providers"] });
      toast.success("Provider 已更新");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => providersApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["providers"] });
      toast.success("Provider 已删除");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useWorkflows(params?: { asset_type?: string; enabled?: boolean }) {
  return useQuery({
    queryKey: ["workflows", params],
    queryFn: () => workflowsApi.list(params),
  });
}

export function useCreateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof workflowsApi.create>[0]) =>
      workflowsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflows"] });
      toast.success("工作流映射已创建");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Partial<Parameters<typeof workflowsApi.update>[1]>) =>
      workflowsApi.update(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflows"] });
      toast.success("工作流映射已更新");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => workflowsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflows"] });
      toast.success("工作流映射已删除");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useSystemConfig() {
  return useQuery({
    queryKey: ["system-config"],
    queryFn: () => systemApi.config(),
  });
}

export function useUpdateLLMConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) => llmConfigApi.update(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["system-config"] });
      toast.success("LLM 配置已更新");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}
