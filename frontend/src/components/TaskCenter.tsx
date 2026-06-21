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
  if (!start || !end) return "—";
  const s = new Date(start).getTime();
  const e = new Date(end).getTime();
  if (Number.isNaN(s) || Number.isNaN(e)) return "—";
  const ms = e - s;
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${Math.round(ms / 1000)}s`;
  return `${Math.round(ms / 1000 / 60)}m ${Math.round((ms / 1000) % 60)}s`;
}

function targetTypeLabel(type?: string): string {
  const map: Record<string, string> = {
    character: "角色",
    scene: "场景",
    prop: "道具",
    shot_first_frame: "分镜首帧",
    shot_last_frame: "分镜尾帧",
    shot_video: "分镜视频",
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

  const handleClear = () => {
    const status = clearStatusMap[filter];
    if (!status) return;
    const statusLabel = filter === "all" ? "所有已结束任务" : `${filter} 任务`;
    if (confirm(`确定清理所有项目的 ${statusLabel}？此操作不可恢复。`)) {
      clearMutation.mutate({ status });
    }
  };

  const canClear = filter !== "active";

  const actions = (
    <>
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
    </>
  );

  return (
    <div className="flex h-full flex-col">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-end gap-2 px-4 py-3">
        {actions}
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
            <div className="flex-1 overflow-y-auto">
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
                          <div className="mt-1.5 flex items-center gap-2">
                            <Badge variant="secondary" className="text-[10px] px-1 py-0">
                              {config.label}
                            </Badge>
                            {task.status === "running" && task.progress > 0 && (
                              <span className="text-xs font-medium">{task.progress}%</span>
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
          <Card className="flex flex-1 flex-col overflow-hidden">
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

  // 切换任务时重置图片错误状态
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

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-6">
        {/* 头部：状态标签移到右上角 */}
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
              <span className="text-xs text-muted-foreground">
                耗时 {formatDuration(task.started_at, task.finished_at)}
              </span>
            </div>
            <div className="flex gap-2">
              {task.status === "running" || task.status === "pending" || task.status === "queued" ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (confirm("确认取消此任务？")) {
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
                  <RefreshCw className="mr-1 h-3.5 w-3.5" />
                  重试
                </Button>
              ) : null}
            </div>
          </div>
        </div>

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
              {typeof payload.prompt === "string" && (
                <div className="rounded-md bg-muted p-3 text-sm">
                  <span className="text-muted-foreground">提示词：</span>
                  <span>{payload.prompt}</span>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 text-sm">
                {typeof payload.size === "string" && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">分辨率</span>
                    <span>{payload.size}</span>
                  </div>
                )}
                {typeof payload.count === "number" && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">数量</span>
                    <span>{payload.count}</span>
                  </div>
                )}
                {typeof payload.model === "string" && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">模型</span>
                    <span>{payload.model}</span>
                  </div>
                )}
              </div>
            </div>
          </Section>
        )}

        {/* 错误信息 */}
        {task.error_message && (
          <Section title="错误报告" icon={AlertCircle}>
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

        {/* 输出 payload（调试用） */}
        {Object.keys(outputPayload).length > 0 && (
          <Section title="输出详情" icon={Terminal}>
            <pre className="max-h-60 overflow-auto rounded-md bg-muted p-3 text-xs">
              {JSON.stringify(outputPayload, null, 2)}
            </pre>
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
