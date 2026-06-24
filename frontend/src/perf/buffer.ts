/** 性能事件缓冲与 flush 策略。 */

import type { PerfEvent, PerfMeasureAggregate } from "./types";
import { reportSession } from "./api";

const BUFFER_MAX = 200;                 // 事件数上限，超过立即 flush
const FLUSH_INTERVAL_MS = 5000;         // 定时 flush 间隔
const LONGTASK_IMMEDIATE_THRESHOLD = 300; // 单条长任务超过 300ms 立即上报
const MAX_RETRY_EVENTS = 200;           // 失败回写时保留的最大事件数

let buffer: PerfEvent[] = [];
let flushTimer: ReturnType<typeof setInterval> | null = null;
let currentSessionId = "";
let startedAt = "";
let flushInProgress = false;
let pendingFlush = false;               // 标记是否有未执行的 flush 请求
let visibilityHandler: (() => void) | null = null;
let beforeUnloadHandler: (() => void) | null = null;

function genSessionId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function initBuffer(sessionId?: string) {
  currentSessionId = sessionId || genSessionId();
  startedAt = new Date().toISOString();
  buffer = [];
  flushInProgress = false;
  pendingFlush = false;
}

export function getSessionId(): string {
  return currentSessionId;
}

export function pushEvent(event: PerfEvent) {
  buffer.push(event);

  // 严重长任务立即触发 flush
  if (event.kind === "longtask" && event.durationMs && event.durationMs > LONGTASK_IMMEDIATE_THRESHOLD) {
    scheduleFlush();
    return;
  }

  if (buffer.length >= BUFFER_MAX) {
    scheduleFlush();
  }
}

/** 调度一次 flush，避免并发执行导致数据被拆成多份。 */
function scheduleFlush() {
  if (flushInProgress) {
    pendingFlush = true;
    return;
  }
  // 异步触发，避免在 pushEvent 调用栈中阻塞业务代码
  Promise.resolve().then(() => flush());
}

export function startAutoFlush() {
  if (flushTimer) return;
  flushTimer = setInterval(() => {
    if (buffer.length > 0) scheduleFlush();
  }, FLUSH_INTERVAL_MS);
}

export function stopAutoFlush() {
  if (flushTimer) {
    clearInterval(flushTimer);
    flushTimer = null;
  }
}

/** 注册页面关闭/隐藏时的兜底上报。 */
export function installLifecycleHandlers() {
  if (typeof window === "undefined" || typeof document === "undefined") return;

  removeLifecycleHandlers();

  // 页面切后台时尝试 flush，sendBeacon 在 hidden 状态下更可靠
  visibilityHandler = () => {
    if (document.hidden && buffer.length > 0) {
      flushWithBeacon();
    }
  };
  document.addEventListener("visibilitychange", visibilityHandler);

  // 页面关闭前兜底：有 sendBeacon 优先用，否则同步 flush
  beforeUnloadHandler = () => {
    if (buffer.length > 0) {
      flushWithBeacon();
    }
  };
  window.addEventListener("beforeunload", beforeUnloadHandler, { once: true });
}

export function removeLifecycleHandlers() {
  if (visibilityHandler && typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", visibilityHandler);
    visibilityHandler = null;
  }
  if (beforeUnloadHandler && typeof window !== "undefined") {
    window.removeEventListener("beforeunload", beforeUnloadHandler);
    beforeUnloadHandler = null;
  }
}

/** 使用 sendBeacon 做一次同步兜底上报，失败不阻塞页面关闭。 */
function flushWithBeacon(): void {
  if (!currentSessionId || buffer.length === 0) return;

  const snapshot = buffer.slice();
  const payload = buildPayload(snapshot);
  const url = getReportUrl();

  try {
    const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
    if (typeof navigator !== "undefined" && navigator.sendBeacon && navigator.sendBeacon(url, blob)) {
      buffer = [];
      return;
    }
  } catch {
    /* sendBeacon 失败则 fallback */
  }

  // 没有 sendBeacon 或发送失败时，尝试同步 XHR 兜底
  try {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url, false);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify(payload));
    if (xhr.status >= 200 && xhr.status < 300) {
      buffer = [];
    }
  } catch {
    /* 页面关闭过程中同步请求失败，数据无法挽回 */
  }
}

/** 根据当前环境构造上报 URL（优先读取 Vite 环境变量中的 BASE_URL）。 */
function getReportUrl(): string {
  const base =
    (typeof import.meta !== "undefined" && (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE) ||
    (typeof window !== "undefined" && window.location ? `${window.location.origin}/api/` : "/api/");
  return `${base.replace(/\/$/, "")}/perf/sessions`;
}

function buildPayload(events: PerfEvent[]) {
  const { counters, measureAggregates, summary } = buildAggregates(events);
  const durationS = Math.max(1, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));

  return {
    sessionId: currentSessionId,
    startedAt,
    endedAt: new Date().toISOString(),
    ua: typeof navigator !== "undefined" ? navigator.userAgent : "",
    appVersion: getAppVersion(),
    summary: {
      sessionDurationS: durationS,
      longTaskCount: summary.longTaskCount,
      longTaskTotalMs: summary.longTaskTotalMs,
      memUsedMB: summary.memUsedMB,
      memTotalMB: summary.memTotalMB,
      memLimitMB: summary.memLimitMB,
      counters,
      measureAggregates,
    },
    counters,
    measureAggregates,
    events,
  };
}

function getAppVersion(): string {
  const env = (typeof import.meta !== "undefined" ? (import.meta as unknown as { env?: Record<string, string> }).env : undefined) || {};
  return env.VITE_APP_VERSION || "web";
}

function buildAggregates(events: PerfEvent[]): {
  counters: Record<string, number>;
  measureAggregates: PerfMeasureAggregate[];
  summary: {
    longTaskCount: number;
    longTaskTotalMs: number;
    memUsedMB: number;
    memTotalMB?: number;
    memLimitMB?: number;
  };
} {
  const longTasks = events.filter((e) => e.kind === "longtask");
  const counters: Record<string, number> = {};
  const measureMap: Record<string, number[]> = {};

  for (const e of events) {
    if (e.kind === "counter" && e.durationMs !== undefined) {
      counters[e.name] = (counters[e.name] || 0) + Math.max(0, Math.round(e.durationMs));
    } else if (e.kind === "measure" && e.durationMs !== undefined) {
      if (!measureMap[e.name]) measureMap[e.name] = [];
      measureMap[e.name].push(e.durationMs);
    }
  }

  const measureAggregates: PerfMeasureAggregate[] = Object.entries(measureMap).map(([name, values]) => {
    values.sort((a, b) => a - b);
    const p95Idx = Math.max(0, Math.ceil(values.length * 0.95) - 1);
    return {
      name,
      count: values.length,
      totalMs: Math.round(values.reduce((a, b) => a + b, 0) * 100) / 100,
      avgMs: Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 100) / 100,
      p95Ms: Math.round(values[p95Idx] * 100) / 100,
      maxMs: Math.round(Math.max(...values) * 100) / 100,
    };
  });

  const lastMemory = [...events].reverse().find((e) => e.kind === "memory");

  return {
    counters,
    measureAggregates,
    summary: {
      longTaskCount: longTasks.length,
      longTaskTotalMs: Math.round(longTasks.reduce((sum, e) => sum + (e.durationMs || 0), 0) * 100) / 100,
      memUsedMB: (lastMemory?.payload?.usedMB as number) || 0,
      memTotalMB: lastMemory?.payload?.totalMB as number | undefined,
      memLimitMB: lastMemory?.payload?.limitMB as number | undefined,
    },
  };
}

export async function flush(): Promise<void> {
  if (flushInProgress || buffer.length === 0 || !currentSessionId) return;
  flushInProgress = true;
  pendingFlush = false;

  const snapshot = buffer.slice();
  buffer = [];

  try {
    await reportSession(buildPayload(snapshot));
  } catch {
    // 上报失败：把事件回写 buffer，但只保留最近上限数量，避免无限累积
    const merged = snapshot.concat(buffer);
    buffer = merged.slice(-Math.min(BUFFER_MAX, MAX_RETRY_EVENTS));
  } finally {
    flushInProgress = false;
    // 如果 flush 期间又有新事件或调度请求，继续处理
    if (pendingFlush && buffer.length > 0) {
      scheduleFlush();
    }
  }
}
