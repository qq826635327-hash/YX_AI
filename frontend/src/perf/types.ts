/** 性能监控 SDK 类型定义。 */

export type PerfEventKind =
  | "mark"
  | "measure"
  | "counter"
  | "longtask"
  | "paint"
  | "memory"
  | "fps" // 帧率采样
  | "block"; // 主线程阻塞（rAF 心跳丢失或 Worker 心跳超时）

export interface LongTaskAttribution {
  /** 触发长任务的脚本 URL（LoAF 归因） */
  scriptUrl?: string;
  /** 调用方名称，如事件处理器 / Promise.then */
  invoker?: string;
  /** 函数名（如可获取） */
  functionName?: string;
  /** 该帧内长任务数量 */
  blockingDuration?: number;
}

export interface FpsPayload {
  fps: number;
  /** 采样窗口内的帧间隔标准差，衡量稳定性 */
  jitter?: number;
  /** 连续低于阈值的采样次数 */
  droppedStreak?: number;
}

export interface BlockPayload {
  /** 阻塞持续时长（ms），估算值 */
  durationMs: number;
  /** 检测来源：raf=主线程心跳丢失，worker=Worker 心跳超时（主线程彻底卡死） */
  source: "raf" | "worker";
  /** 阻塞发生时附近的 LoAF 归因（如有） */
  attribution?: LongTaskAttribution;
}

export interface PerfEvent {
  seq: number;
  ts: number;
  kind: PerfEventKind;
  name: string;
  durationMs?: number;
  payload?: Record<string, unknown>;
}

export interface PerfMeasureAggregate {
  name: string;
  count: number;
  totalMs: number;
  avgMs: number;
  p95Ms: number;
  maxMs: number;
}

export interface PerfSessionSummary {
  sessionDurationS: number;
  longTaskCount: number;
  longTaskTotalMs: number;
  memUsedMB: number;
  memTotalMB?: number;
  counters: Record<string, number>;
  measureAggregates: PerfMeasureAggregate[];
}

export interface PerfSession {
  id: string;
  session_id: string;
  started_at: string;
  ended_at?: string;
  ua?: string;
  app_version?: string;
  session_duration_s: number;
  long_task_count: number;
  long_task_total_ms: number;
  mem_used_mb: number;
  mem_total_mb?: number;
  counters: Record<string, number>;
  measure_aggregates: PerfMeasureAggregate[];
  created_at: string;
}

export interface PerfAlert {
  id: string;
  session_id: string;
  level: "warning" | "error";
  metric: string;
  threshold: number;
  actual: number;
  message: string;
  acknowledged: boolean;
  created_at: string;
}
