import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 Tailwind 类名工具。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 格式化时间。 */
export function formatTime(value: string | Date | undefined): string {
  if (!value) return "-";
  const d = typeof value === "string" ? new Date(value) : value;
  if (isNaN(d.getTime())) return "-";
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** 文件大小格式化。 */
export function formatSize(bytes?: number | null): string {
  if (!bytes) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(1)} ${units[i]}`;
}

/** 任务状态对应的颜色与文案。 */
export const taskStatusMap: Record<string, { label: string; color: string }> = {
  pending: { label: "等待中", color: "text-muted-foreground" },
  queued: { label: "排队中", color: "text-blue-500" },
  running: { label: "运行中", color: "text-amber-500" },
  succeeded: { label: "成功", color: "text-green-500" },
  failed: { label: "失败", color: "text-red-500" },
  cancelled: { label: "已取消", color: "text-muted-foreground" },
};

/** 角色类型文案。 */
export const charTypeMap: Record<string, string> = {
  protagonist: "主角",
  supporting: "配角",
  extra: "群演",
};
