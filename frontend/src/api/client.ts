/** HTTP 客户端封装（基于 ky）。

后端统一响应格式：
- 成功（带数据）：{ data: T, message?: string }
- 分页：{ data: { items: T[], total, page, page_size } }
- 错误：{ error: string, message: string, details?: unknown }
*/

import ky from "ky";
import type { ApiErrorResponse, ApiResponse, PaginatedData } from "@/types";
import { logger as log } from "@/stores/logStore";

/** 统一错误类。 */
export class ApiError extends Error {
  status: number;
  body?: ApiErrorResponse;

  constructor(message: string, status: number, body?: ApiErrorResponse) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export const http = ky.create({
  prefixUrl: "/api",
  timeout: 60000,
  retry: {
    // 只对幂等操作（GET/HEAD）重试，避免对 DELETE/PATCH 等非幂等操作重复执行
    methods: ["get", "head"],
    limit: 2,
  },
  hooks: {
    afterResponse: [
      async (_request, _options, response) => {
        if (!response.ok) {
          let body: ApiErrorResponse | undefined;
          try {
            body = (await response.clone().json()) as ApiErrorResponse;
          } catch {
            // 非 JSON 错误响应
          }
          const message = body?.message || response.statusText || "请求失败";
          // 写入日志系统（便于 AI 调试时直接看到前后端错误）
          // 4xx 是客户端错误，记为 warning；5xx 才是后端错误
          const level: "WARNING" | "ERROR" =
            response.status >= 500 ? "ERROR" : "WARNING";
          try {
            log[level === "ERROR" ? "error" : "warn"](
              `API ${response.status}: ${message}`,
              "api",
              response.url,
              {
                status: response.status,
                method: _request.method,
                url: response.url,
                body,
              }
            );
          } catch {
            /* 忽略日志写入失败 */
          }
          throw new ApiError(message, response.status, body);
        }
        return response;
      },
    ],
  },
});

/**
 * 提取响应的 data 字段，返回纯业务数据。
 * 后端返回 { data: T, message? } → 返回 T
 */
export async function unwrap<T>(promise: Promise<Response>): Promise<T> {
  const response = await promise;
  const json = (await response.json()) as ApiResponse<T>;
  return json.data;
}

/**
 * 提取分页响应的 data 字段，返回分页数据对象。
 * 后端返回 { data: { items, total, page, page_size } } → 返回 { items, total, page, page_size }
 */
export async function unwrapPaginated<T>(promise: Promise<Response>): Promise<PaginatedData<T>> {
  const response = await promise;
  const json = (await response.json()) as ApiResponse<PaginatedData<T>>;
  return json.data;
}

/**
 * 返回完整响应（含 data 和 message）。
 * 后端返回 { data: T, message? } → 返回 { data: T, message? }
 * 调用方通过 res.data 取数据，res.message 取消息。
 */
export async function unwrapFull<T>(promise: Promise<Response>): Promise<ApiResponse<T>> {
  const response = await promise;
  return (await response.json()) as ApiResponse<T>;
}
