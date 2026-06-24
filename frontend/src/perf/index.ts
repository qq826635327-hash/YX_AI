/** 性能监控 SDK 入口。
 *
 * 用法：
 *   perf.mark("editor.loadProject.start", { id })
 *   perf.measure("store.listProjects", durationMs)
 *   perf.count("editor.render")
 *
 * 自动采集：longtask / paint / memory
 */

import { flush, initBuffer, installLifecycleHandlers, pushEvent, removeLifecycleHandlers, startAutoFlush, stopAutoFlush } from "./buffer";
import { startObservers, stopObservers } from "./observer";
import { nextSeq } from "./seq";
import type { PerfEvent } from "./types";

function makeEvent(kind: PerfEvent["kind"], name: string, durationMs?: number, payload?: Record<string, unknown>): PerfEvent {
  return {
    seq: nextSeq(),
    ts: Date.now(),
    kind,
    name,
    durationMs,
    payload,
  };
}

export const perf = {
  /** 初始化会话并开始自动观测。 */
  start() {
    initBuffer();
    startObservers();
    startAutoFlush();
    installLifecycleHandlers();
  },

  /** 标记一个时间点。 */
  mark(name: string, payload?: Record<string, unknown>) {
    pushEvent(makeEvent("mark", name, undefined, payload));
  },

  /** 记录一段耗时。 */
  measure(name: string, durationMs: number, payload?: Record<string, unknown>) {
    pushEvent(makeEvent("measure", name, durationMs, payload));
  },

  /** 计数器。 */
  count(name: string, delta = 1, payload?: Record<string, unknown>) {
    pushEvent(makeEvent("counter", name, delta, payload));
  },

  /** 立即 flush 当前 buffer（页面关闭前调用）。 */
  flush(): Promise<void> {
    return flush();
  },

  /** 停止自动 flush 与观测器。 */
  stop() {
    stopAutoFlush();
    stopObservers();
    removeLifecycleHandlers();
  },
};

export type { PerfEvent, PerfMeasureAggregate, PerfSession, PerfAlert } from "./types";
export { fetchSessions, fetchAlerts } from "./api";
export { diagnoseSession, fetchQueueDepth } from "./api";
export type { DiagnoseFinding, DiagnoseResult, QueueDepth } from "./api";
