/** WebSocket 客户端封装：任务状态、剧本解析进度、实时日志。 */

import type { WsMessage } from "@/types";

type MessageHandler = (msg: WsMessage) => void;

/**
 * 计算 WS 基础 URL。
 * - 生产模式：浏览器同源访问 `/ws/...`（FastAPI 自己托管前端）
 * - 开发模式：默认直连后端 8000 端口，**绕过 Vite WS 代理**
 *   （Vite 5 的 WS 代理对自定义路径经常失败，HTTP API 走 Vite 代理就够了）
 *   也可以通过 `VITE_WS_BASE_URL` 显式覆盖
 */
function resolveWsBaseUrl(): string {
  // 1. 显式覆盖（最高优先级）
  const override = (import.meta as any).env?.VITE_WS_BASE_URL as string | undefined;
  if (override) return override.replace(/\/$/, "");

  // 2. 生产模式：同源（相对协议 + 当前 host）
  if ((import.meta as any).env?.PROD) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  }

  // 3. 开发模式：直连后端 8000 端口（默认）
  return "ws://127.0.0.1:8000";
}

const WS_BASE = resolveWsBaseUrl();

/** 带自动重连的 WebSocket 客户端。 */
export class WsClient {
  private url: string;
  private ws: WebSocket | null = null;
  private handlers = new Set<MessageHandler>();
  private reconnectAttempts = 0;
  private maxReconnectDelay = 30000;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private closed = false;

  constructor(path: string) {
    // path 形如 "/ws/tasks"，拼到 WS_BASE 后面
    const normalized = path.startsWith("/") ? path : `/${path}`;
    this.url = `${WS_BASE}${normalized}`;
  }

  connect(): void {
    if (this.closed) return;
    // 防止重复创建连接（Fast Refresh / 业务层误调用）
    if (this.ws && this.ws.readyState !== WebSocket.CLOSED) {
      return;
    }
    try {
      this.ws = new WebSocket(this.url);
    } catch (e) {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WsMessage;
        this.handlers.forEach((h) => h(msg));
      } catch {
        // 忽略非 JSON 消息
      }
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      if (!this.closed) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    const baseDelay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay);
    // 添加 ±25% 的随机抖动，避免多客户端同时重连造成惊群
    const jitter = baseDelay * 0.25 * (Math.random() * 2 - 1);
    const delay = Math.max(100, baseDelay + jitter);
    this.reconnectAttempts++;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send("ping");
      }
    }, 30000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  on(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  close(): void {
    this.closed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}

// 全局单例
export const tasksWs = new WsClient("/ws/tasks");
export const scriptWs = new WsClient("/ws/script");
export const logsWs = new WsClient("/ws/logs");

/** 当前使用的 WS 基础 URL（调试用：可在浏览器 console 看 `import.meta.env`） */
export const WS_BASE_URL = WS_BASE;
