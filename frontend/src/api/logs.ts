/** 日志查询 API 封装。 */

import { http, unwrap } from "./client";
import type { LogListResponse, TaskLogListResponse } from "@/types";

export interface LogQueryParams {
  level?: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  limit?: number;
  offset?: number;
  keyword?: string;
}

export interface TaskLogQueryParams {
  level?: "DEBUG" | "INFO" | "WARN" | "ERROR";
  phase?: string;
  limit?: number;
}

export const logsApi = {
  /** 拉取历史日志（默认倒序） */
  list: (params: LogQueryParams = {}) => {
    const search: Record<string, string> = {};
    if (params.level) search.level = params.level;
    if (params.limit) search.limit = String(params.limit);
    if (params.offset) search.offset = String(params.offset);
    if (params.keyword) search.keyword = params.keyword;
    return unwrap<LogListResponse>(http.get("logs", { searchParams: search }));
  },

  /** 获取日志文件元信息 */
  info: () =>
    unwrap<{
      file: string;
      exists: boolean;
      size_bytes: number;
      modified_at: string | null;
    }>(http.get("logs/info")),

  /** 清空日志（仅开发模式） */
  clear: () => unwrap<{ ok: boolean; file: string }>(http.post("logs/clear")),

  /** 获取任务的结构化日志（从 DB 读取） */
  taskLogs: (taskId: string, params: TaskLogQueryParams = {}) => {
    const search: Record<string, string> = {};
    if (params.level) search.level = params.level;
    if (params.phase) search.phase = params.phase;
    if (params.limit) search.limit = String(params.limit);
    return unwrap<TaskLogListResponse>(http.get(`logs/tasks/${taskId}`, { searchParams: search }));
  },
};
