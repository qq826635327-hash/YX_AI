import { useEffect, useMemo, useState } from "react";
import {
  ListTodo,
  Loader2,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Trash2,
  Clock,
  Calendar,
  AlertCircle,
  Image as ImageIcon,
  FileText,
  Terminal,
  Maximize2,
} from "lucide-react";
import { LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  useTasks,
  useCancelTask,
  useRetryTask,
  useClearTasks,
} from "@/hooks/useApi";
import { assetsApi } from "@/api/assets";
import { useConfirm } from "@/components/ConfirmDialog";
import type { GenerationTask, TaskStatus } from "@/types";

export type TaskFilter = "all" | "active" | "completed" | "failed" | "cancelled";

interface StatusConfig {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: any;
}

const statusConfig: Record<TaskStatus, StatusConfig> = {
  pending: {
    label: "排队中",
    color: "text-yellow-600",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/20",
    icon: ListTodo,
  },
  queued: {
    label: "排队中",
    color: "text-yellow-600",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/20",
    icon: ListTodo,
  },
  running: {
    label: "生成中",
    color: "text-blue-600",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/20",
    icon: Loader2,
  },
  succeeded: {
    label: "已完成",
    color: "text-green-600",
    bgColor: "bg-green-500/10",
    borderColor: "border-green-500/20",
    icon: CheckCircle2,
  },
  failed: {
    label: "失败",
    color: "text-red-600",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/20",
    icon: XCircle,
  },
  cancelled: {
    label: "已取消",
    color: "text-gray-600",
    bgColor: "bg-gray-500/10",
    borderColor: "border-gray-500/20",
    icon: XCircle,
  },
};

function getStatusConfig(status: string): StatusConfig {
  return statusConfig[status as TaskStatus] || statusConfig.pending;
}

function formatTime(iso?: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

function formatDuration(start?: string, end?: string): string {
  if (!start || !end) return "";
  const s = new Date(start).getTime();
  const e = new Date(end).getTime();
  if (Number.isNaN(s) || Number.isNaN(e)) return "";
  const ms = e - s;
  if (ms < 0) return "";
  if (ms < 1000) return `${ms}ms`;
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return `${totalSec}秒`;
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return sec > 0 ? `${min}分${sec}秒` : `${min}分`;
}

function targetTypeLabel(type?: string): string {
  const map: Record<string, string> = {
    character: "角色",
    scene: "场景",
    prop: "道具",
    shot_first_frame: "分镜首帧",
    shot_last_frame: "分镜尾帧",
    shot_video: "分镜视频",
    script_parse: "剧本解析",
  };
  return map[type || ""] || type || "未知";
}

function taskTitle(task: GenerationTask): string {
  return `${targetTypeLabel(task.target_type)} · ${task.target_id.slice(0, 8)}`;
}

function taskSubtitle(task: GenerationTask): string {
  const payload = task.input_payload || {};
  const prompt = typeof payload.prompt === "string" ? payload.prompt : "";
  if (prompt) return prompt.length > 40 ? prompt.slice(0, 40) + "…" : prompt;
  return getStatusConfig(task.status).label;
}

/** 根据进度百分比推断当前阶段标签 */
function getStageLabel(progress: number, targetType?: string): string {
  if (progress <= 5) return "准备参数...";
  if (progress <= 15) return "收集参考图...";
  if (progress <= 25) return "上传参考图到图床...";
  if (progress <= 35) return "正在调用AI生成引擎...";
  if (progress <= 65) return targetType === "shot_video" ? "视频生成中（API轮询）..." : "图片生成中...";
  if (progress <= 75) return "下载生成结果...";
  if (progress <= 85) return "保存记录...";
  if (progress <= 95) return "回填到实体...";
  return "即将完成...";
}

const statusQueryMap: Record<TaskFilter, string | undefined> = {
  active: "pending,running,queued",
  completed: "succeeded",
  failed: "failed",
  cancelled: "cancelled",
  all: undefined,
};

const clearStatusMap: Record<TaskFilter, string | undefined> = {
  active: undefined,
  completed: "succeeded",
  failed: "failed",
  cancelled: "cancelled",
  all: "succeeded,failed,cancelled",
};

interface TaskCenterProps {
  filter: TaskFilter;
}

export function TaskCenter({ filter }: TaskCenterProps) {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const confirm = useConfirm();

  const { data, isLoading, refetch } = useTasks({
    status: statusQueryMap[filter],
    page_size: 100,
  });

  const cancelMutation = useCancelTask();
  const retryMutation = useRetryTask();
  const clearMutation = useClearTasks();

  const tasks: GenerationTask[] = data?.items || [];

  const selectedTask = useMemo(() => {
    if (selectedTaskId) {
      return tasks.find((t) => t.id === selectedTaskId) || tasks[0] || null;
    }
    return tasks[0] || null;
  }, [tasks, selectedTaskId]);

  const handleClear = async () => {
    const status = clearStatusMap[filter];
    if (!status) return;
    const statusLabel = filter === "all" ? "所有已结束任务" : `${filter} 任务`;
    if (await confirm({ title: `确定清理所有项目的${statusLabel}？`, description: "此操作不可恢复。", variant: "destructive" })) {
      clearMutation.mutate({ status });
    }
  };

  const canClear = filter !== "active";

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-end gap-2 px-4 py-3">
        {canClear && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleClear}
            disabled={clearMutation.isPending}
            className="text-destructive"
          >
            <Trash2 className="mr-1 h-3.5 w-3.5" />
            {clearMutation.isPending ? "清理中…" : "一键清理"}
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-1 h-3.5 w-3.5" />
          刷新
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : tasks.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
          <p>暂无任务</p>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 gap-4 px-4 pb-4">
          {/* 左侧列表 */}
          <Card className="flex w-80 flex-col overflow-hidden xl:w-96">
            <div className="min-h-0 flex-1 overflow-y-auto">
              <div className="p-2">
                {tasks.map((task) => {
                  const config = getStatusConfig(task.status);
                  const StatusIcon = config.icon;
                  const isSelected = selectedTask?.id === task.id;

                  return (
                    <button
                      key={task.id}
                      onClick={() => setSelectedTaskId(task.id)}
                      className={`w-full rounded-lg border p-3 text-left transition-colors ${
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "border-transparent hover:bg-muted/50"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${config.bgColor}`}
                        >
                          <StatusIcon
                            className={`h-4 w-4 ${config.color} ${
                              task.status === "running" ? "animate-spin" : ""
                            }`}
                          />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate font-medium">{taskTitle(task)}</span>
                            <span className="shrink-0 text-xs text-muted-foreground">
                              {formatTime(task.created_at)}
                            </span>
                          </div>
                          <p className="mt-0.5 truncate text-xs text-muted-foreground">
                            {taskSubtitle(task)}
                          </p>
                          <div className="mt-1.5 flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <Badge variant="secondary" className="text-[10px] px-1 py-0">
                                {config.label}
                              </Badge>
                              {task.status === "running" && task.progress > 0 && (
                                <span className="text-xs font-medium">{task.progress}%</span>
                              )}
                            </div>
                            {task.started_at && task.finished_at && (
                              <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                                <Clock className="h-3 w-3" />
                                {formatDuration(task.started_at, task.finished_at)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </Card>

          {/* 右侧详情 */}
          <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {selectedTask ? (
              <TaskDetailPanel
                task={selectedTask}
                cancelMutation={cancelMutation}
                retryMutation={retryMutation}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                选择左侧任务查看详情
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

interface TaskDetailPanelProps {
  task: GenerationTask;
  cancelMutation: ReturnType<typeof useCancelTask>;
  retryMutation: ReturnType<typeof useRetryTask>;
}

function TaskDetailPanel({ task, cancelMutation, retryMutation }: TaskDetailPanelProps) {
  const config = getStatusConfig(task.status);
  const StatusIcon = config.icon;
  const payload = task.input_payload || {};
  const outputPayload = task.output_payload || {};
  const [imageError, setImageError] = useState(false);
  const confirm = useConfirm();

  useEffect(() => {
    setImageError(false);
  }, [task.id]);

  const infoRows = [
    { label: "任务 ID", value: task.id },
    { label: "项目 ID", value: task.project_id },
    { label: "目标", value: `${targetTypeLabel(task.target_type)} / ${task.target_id}` },
    { label: "Provider", value: task.provider_id || "—" },
    { label: "类型", value: task.provider_type === "comfyui" ? "ComfyUI" : "API" },
    { label: "重试次数", value: task.retry_count },
  ];

  // 解析错误类型
  const errorAnalysis = useMemo(() => {
    if (!task.error_message) return null;
    const msg = task.error_message.toLowerCase();
    if (msg.includes("content_violation") || msg.includes("content_policy") || msg.includes("safety") || msg.includes("内容违规") || msg.includes("flagged")) {
      return { type: "内容违规", desc: "提示词或参考图触发了 AI 平台的内容安全策略，请修改后重试", color: "text-orange-600" };
    }
    if (msg.includes("timeout") || msg.includes("timed out") || msg.includes("超时")) {
      return { type: "请求超时", desc: "AI 服务响应时间过长，可能是服务繁忙或网络不稳定，建议稍后重试", color: "text-yellow-600" };
    }
    if (msg.includes("401") || msg.includes("unauthorized") || msg.includes("authentication") || msg.includes("api_key") || msg.includes("invalid api key")) {
      return { type: "认证失败", desc: "API Key 无效或已过期，请检查 Provider 配置中的 API Key", color: "text-red-600" };
    }
    if (msg.includes("402") || msg.includes("payment") || msg.includes("quota") || msg.includes("余额") || msg.includes("insufficient_quota") || msg.includes("billing")) {
      return { type: "额度不足", desc: "API 账户余额不足或已超出配额限制，请充值或更换 Provider", color: "text-red-600" };
    }
    if (msg.includes("403") || msg.includes("forbidden")) {
      return { type: "权限拒绝", desc: "API 返回权限错误，可能是模型访问权限或地域限制", color: "text-red-600" };
    }
    if (msg.includes("404") || msg.includes("not_found") || msg.includes("model_not_found")) {
      return { type: "模型不可用", desc: "请求的模型不存在或已下线，请更换模型或检查 Provider 配置", color: "text-red-600" };
    }
    if (msg.includes("429") || msg.includes("rate_limit") || msg.includes("too many requests") || msg.includes("频率限制")) {
      return { type: "请求限频", desc: "API 调用频率超限，请稍后重试或降低并发数", color: "text-yellow-600" };
    }
    if (msg.includes("500") || msg.includes("502") || msg.includes("503") || msg.includes("internal server error") || msg.includes("bad gateway") || msg.includes("service unavailable")) {
      return { type: "服务端错误", desc: "AI 服务端暂时异常，建议稍后重试", color: "text-yellow-600" };
    }
    if (msg.includes("connection") || msg.includes("network") || msg.includes("econnrefused") || msg.includes("网络")) {
      return { type: "网络错误", desc: "无法连接到 AI 服务，请检查网络和 Provider 地址配置", color: "text-yellow-600" };
    }
    if (msg.includes("参数校验失败") || msg.includes("validate")) {
      return { type: "参数错误", desc: "生成参数不符合模型要求，请检查分辨率、模型等配置", color: "text-orange-600" };
    }
    return { type: "未知错误", desc: "请查看下方详细错误信息", color: "text-red-600" };
  }, [task.error_message]);

  const refDetails: Array<{ type: string; label: string; file: string; size_kb: number }> =
    (payload.ref_details as any[]) || [];

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="p-6">
        {/* 头部 */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-full border ${config.bgColor} ${config.borderColor}`}
            >
              <StatusIcon
                className={`h-6 w-6 ${config.color} ${task.status === "running" ? "animate-spin" : ""}`}
              />
            </div>
            <div>
              <h3 className="text-lg font-semibold">{taskTitle(task)}</h3>
              <p className="text-sm text-muted-foreground">{taskSubtitle(task)}</p>
            </div>
          </div>

          <div className="flex flex-col items-end gap-2">
            <div className="flex items-center gap-3">
              <Badge variant="secondary">{config.label}</Badge>
              {task.status === "running" && task.progress > 0 && (
                <span className="text-sm font-medium">{task.progress}%</span>
              )}
              {task.started_at && task.finished_at && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  {formatDuration(task.started_at, task.finished_at)}
                </span>
              )}
            </div>
            <div className="flex gap-2">
              {task.status === "running" || task.status === "pending" || task.status === "queued" ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    if (await confirm({ title: "确认取消此任务？", variant: "destructive" })) {
                      cancelMutation.mutate(task.id);
                    }
                  }}
                  disabled={cancelMutation.isPending}
                >
                  取消
                </Button>
              ) : task.status === "failed" ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => retryMutation.mutate({ taskId: task.id })}
                  disabled={retryMutation.isPending}
                >
                  <RefreshCw className={`mr-1 h-3.5 w-3.5 ${retryMutation.isPending ? "animate-spin" : ""}`} />
                  重试
                </Button>
              ) : null}
            </div>
          </div>
        </div>

        {/* 进度条 */}
        {task.status === "running" && (
          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-sm font-medium">
                {task.progress_message || getStageLabel(task.progress, task.target_type)}
              </span>
              <span className="text-sm text-muted-foreground">{task.progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${task.progress}%` }}
              />
            </div>
          </div>
        )}

        {/* 重试快速拉取提示 */}
        {task.status === "failed" && Boolean(
          (task.input_payload as Record<string, unknown>)?._result_urls ||
          (task.input_payload as Record<string, unknown>)?._video_task_id
        ) && (
          <div className="mt-3 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm dark:border-blue-900 dark:bg-blue-950">
            <p className="font-medium text-blue-700 dark:text-blue-300">
              API已成功生成，重试将快速拉取结果
            </p>
            <p className="mt-0.5 text-muted-foreground">
              点击"重试"按钮即可从API拉取已生成的{task.target_type === "shot_video" ? "视频" : "图片"}，无需重新生成
            </p>
          </div>
        )}

        <hr className="my-5 border-border" />

        {/* 时间线 */}
        <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <TimeBox icon={Calendar} label="创建时间" value={formatTime(task.created_at)} />
          <TimeBox icon={Clock} label="开始时间" value={formatTime(task.started_at)} />
          <TimeBox icon={CheckCircle2} label="完成时间" value={formatTime(task.finished_at)} />
        </div>

        {/* 基本信息 */}
        <Section title="任务信息" icon={FileText}>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {infoRows.map((row) => (
              <div key={row.label} className="flex gap-2 text-sm">
                <span className="shrink-0 text-muted-foreground">{row.label}</span>
                <span className="font-mono truncate">{String(row.value)}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* 输入参数 */}
        {Object.keys(payload).length > 0 && (
          <Section title="输入参数" icon={Terminal}>
            <div className="space-y-2">
              {typeof payload.prompt === "string" && payload.prompt && (
                <div className="rounded-md bg-muted p-3 text-sm">
                  <span className="text-muted-foreground">提示词：</span>
                  <span>{payload.prompt}</span>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 text-sm">
                {typeof payload.model === "string" && payload.model && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">模型</span>
                    <span className="font-mono">{payload.model}</span>
                  </div>
                )}
                {typeof payload.size === "string" && payload.size && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">请求分辨率</span>
                    <span className="font-mono">{payload.size}</span>
                  </div>
                )}
                {typeof payload.count === "number" && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">数量</span>
                    <span>{payload.count}</span>
                  </div>
                )}
                {typeof payload.asset_type === "string" && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">素材类型</span>
                    <span>{payload.asset_type === "video" ? "视频" : "图片"}</span>
                  </div>
                )}
              </div>
              {refDetails.length > 0 ? (
                <div className="rounded-md border p-2">
                  <p className="mb-1 text-xs font-medium text-muted-foreground">参考图片（{refDetails.length} 张）</p>
                  <div className="space-y-1">
                    {refDetails.map((ref, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <ImageIcon className="h-3 w-3 text-muted-foreground" />
                        <span>{ref.label}</span>
                        <span className="text-muted-foreground">{ref.file}</span>
                        <span className="text-muted-foreground">({ref.size_kb}KB)</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {payload.extra_params && typeof payload.extra_params === "object" && Object.keys(payload.extra_params as object).length > 0 ? (
                <div className="rounded-md bg-muted p-2">
                  <p className="mb-1 text-xs font-medium text-muted-foreground">额外参数</p>
                  <pre className="text-xs">{JSON.stringify(payload.extra_params, null, 2)}</pre>
                </div>
              ) : null}
            </div>
          </Section>
        )}

        {/* 错误报告 */}
        {task.error_message && (
          <Section title="错误报告" icon={AlertCircle}>
            {errorAnalysis && (
              <div className="mb-2 rounded-md border border-orange-200 bg-orange-50 p-3 text-sm dark:border-orange-900 dark:bg-orange-950">
                <p className={`font-medium ${errorAnalysis.color}`}>
                  {errorAnalysis.type}
                </p>
                <p className="mt-0.5 text-muted-foreground">{errorAnalysis.desc}</p>
              </div>
            )}
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
              <p className="whitespace-pre-wrap break-words">{task.error_message}</p>
            </div>
          </Section>
        )}

        {/* 结果素材 */}
        {task.output_asset_id && (
          <Section title="结果素材" icon={ImageIcon}>
            <div className="overflow-hidden rounded-md border">
              {imageError ? (
                <div className="flex h-48 items-center justify-center bg-muted text-sm text-muted-foreground">
                  素材文件缺失或加载失败
                </div>
              ) : outputPayload.asset_type === "video" || task.target_type === "shot_video" ? (
                <video
                  src={assetsApi.fileUrl(task.output_asset_id)}
                  controls
                  className="max-h-96 w-full object-contain"
                  onError={() => setImageError(true)}
                />
              ) : (
                <img
                  src={assetsApi.fileUrl(task.output_asset_id)}
                  alt="生成结果"
                  className="max-h-96 w-full object-contain"
                  onError={() => setImageError(true)}
                />
              )}
            </div>
          </Section>
        )}

        {/* 输出详情 */}
        {(outputPayload.actual_size || Object.keys(outputPayload).length > 0) && (
          <Section title="输出详情" icon={Terminal}>
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2 text-sm">
                {/* 实际分辨率 — 突出展示 */}
                {outputPayload.actual_size ? (
                  <div className="col-span-2 flex items-center gap-2 rounded-md border p-2">
                    <Maximize2 className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">实际分辨率</span>
                    <span className="font-mono font-semibold">{String(outputPayload.actual_size)}</span>
                    {outputPayload.size_mismatch && outputPayload.requested_size ? (
                      <span className="text-orange-600 text-xs">(请求: {String(outputPayload.requested_size)}，AI 服务端已标准化)</span>
                    ) : null}
                  </div>
                ) : null}
                {outputPayload.model ? (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">模型</span>
                    <span className="font-mono">{String(outputPayload.model)}</span>
                  </div>
                ) : null}
                {outputPayload.asset_type ? (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">类型</span>
                    <span>{outputPayload.asset_type === "video" ? "视频" : "图片"}</span>
                  </div>
                ) : null}
                {outputPayload.output_count ? (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">输出数量</span>
                    <span>{String(outputPayload.output_count)}</span>
                  </div>
                ) : null}
                {outputPayload.duration_ms ? (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">API 耗时</span>
                    <span>{Number(outputPayload.duration_ms) > 1000 ? `${(Number(outputPayload.duration_ms) / 1000).toFixed(1)}秒` : `${String(outputPayload.duration_ms)}ms`}</span>
                  </div>
                ) : null}
                {outputPayload.cache_hit ? (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">缓存命中</span>
                    <span className="text-green-600">是</span>
                  </div>
                ) : null}
                {outputPayload.usage && typeof outputPayload.usage === "object" ? (
                  <div className="col-span-2 flex gap-2">
                    <span className="text-muted-foreground">Token 用量</span>
                    <span className="font-mono text-xs">{JSON.stringify(outputPayload.usage)}</span>
                  </div>
                ) : null}
              </div>
              <details className="text-xs">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground">查看完整输出 JSON</summary>
                <pre className="mt-1 max-h-60 overflow-auto rounded-md bg-muted p-3">
                  {JSON.stringify(outputPayload, null, 2)}
                </pre>
              </details>
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

function TimeBox({
  icon: Icon,
  label,
  value,
}: {
  icon: any;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-md border p-3">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium">{value}</p>
      </div>
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: any;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium">
        <Icon className="h-4 w-4 text-muted-foreground" />
        {title}
      </div>
      {children}
    </div>
  );
}
