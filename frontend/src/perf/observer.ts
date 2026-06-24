/** 浏览器性能事件自动观测：longtask(LoAF 归因) / paint / memory / fps / 实时阻塞。
 *
 * 阻塞检测双层兜底：
 *   1. rAF 心跳：主线程还在跑但掉帧时，200ms 无帧立即上报 block 事件（source=raf）
 *   2. Web Worker 心跳：主线程彻底卡死（rAF 不再触发）时，Worker 侧 300ms 收不到回复即上报（source=worker）
 */

import { pushEvent } from "./buffer";
import { nextSeq } from "./seq";
import type {
  BlockPayload,
  FpsPayload,
  LongTaskAttribution,
  PerfEvent,
  PerfEventKind,
} from "./types";

let longTaskObserver: PerformanceObserver | null = null;
let loafObserver: PerformanceObserver | null = null;
let paintObserver: PerformanceObserver | null = null;
let memoryTimer: ReturnType<typeof setInterval> | null = null;
let started = false;

// ---- FPS / 实时阻塞 ----
let rafId: number | null = null;
let lastFrameTs = 0;
let lastBlockReportTs = 0;
let frameSamples: number[] = []; // 最近一个采样窗口的帧间隔
let fpsTimer: ReturnType<typeof setInterval> | null = null;
let droppedStreak = 0;
let worker: Worker | null = null;
let lastWorkerReplyTs = 0;
let workerCheckTimer: ReturnType<typeof setInterval> | null = null;

// 最近一次 LoAF 归因缓存，供阻塞事件附带
let recentAttribution: LongTaskAttribution | undefined;

const FPS_SAMPLE_WINDOW_MS = 1000; // 每秒计算一次 fps
const FPS_DROP_THRESHOLD = 50; // 低于 50fps 视为掉帧
const RAF_BLOCK_THRESHOLD_MS = 200; // rAF 200ms 无帧 → 主线程阻塞
const WORKER_BLOCK_THRESHOLD_MS = 1500; // Worker 1500ms 收不到回复且 rAF 也停了 → 主线程彻底冻结（阈值必须远大于 rAF 的 200ms，否则会把"主线程持续繁忙"误判为"阻塞"）
const BLOCK_REPORT_COOLDOWN_MS = 2000; // 阻塞事件上报冷却，避免刷屏

function makeEvent(
  kind: PerfEventKind,
  name: string,
  durationMs?: number,
  payload?: Record<string, unknown>,
): PerfEvent {
  return {
    seq: nextSeq(),
    ts: Date.now(),
    kind,
    name,
    durationMs,
    payload,
  };
}

export function startObservers() {
  if (typeof window === "undefined" || !("PerformanceObserver" in window)) {
    return;
  }
  if (started) return;
  started = true;

  // 长任务监听（>50ms 主线程阻塞），buffered 捕获已发生的长任务
  try {
    longTaskObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        pushEvent(
          makeEvent("longtask", "main-thread", entry.duration, {
            startTime: Math.round(entry.startTime),
            name: entry.name || "",
            attribution: recentAttribution,
          }),
        );
      }
    });
    longTaskObserver.observe({ entryTypes: ["longtask"], buffered: true } as PerformanceObserverInit);
  } catch {
    /* 浏览器不支持则忽略 */
  }

  // LoAF（Long Animation Frames）长任务归因 —— Chrome 116+ 原生支持
  // 给出 script.url / invoker / functionName，让 AI 能定位卡顿源头
  try {
    loafObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as unknown as PerformanceEntry[]) {
        // PerformanceLongAnimationFrameEntry 的 scripts 数组包含归因
        const scripts = (entry as unknown as { scripts?: Array<{ name?: string; invoker?: string; sourceURL?: string; sourceFunctionName?: string; duration?: number }> }).scripts;
        if (scripts && scripts.length > 0) {
          // 取该帧内耗时最长的脚本作为归因
          const top = scripts.reduce((a, b) => ((b.duration || 0) > (a.duration || 0) ? b : a));
          recentAttribution = {
            scriptUrl: top.sourceURL || top.name,
            invoker: top.invoker,
            functionName: top.sourceFunctionName,
            blockingDuration: Math.round(top.duration || 0),
          };
          pushEvent(
            makeEvent("longtask", "main-thread.loaf", entry.duration, {
              startTime: Math.round(entry.startTime),
              attribution: recentAttribution,
              scriptCount: scripts.length,
            }),
          );
        }
      }
    });
    // entryTypes 兼容写法：部分浏览器类型名为 "long-animation-frame"
    loafObserver.observe({ type: "long-animation-frame", buffered: true } as PerformanceObserverInit);
  } catch {
    /* LoAF 不支持时降级为普通 longtask，归因字段为空 */
  }

  // First Paint / First Contentful Paint
  try {
    paintObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        pushEvent(makeEvent("paint", entry.name, entry.startTime));
      }
    });
    paintObserver.observe({ entryTypes: ["paint"], buffered: true } as PerformanceObserverInit);
  } catch {
    /* ignore */
  }

  // 内存采样（Chrome / Electron）
  // 注意：jsHeapSizeLimit 才是浏览器堆上限，totalJSHeapSize 只是已分配量
  // usedJSHeapSize / totalJSHeapSize 通常 85-95%，属正常现象，不能用来判断 OOM
  // 正确指标：usedJSHeapSize / jsHeapSizeLimit
  memoryTimer = setInterval(() => {
    const mem = (
      performance as unknown as {
        memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number };
      }
    ).memory;
    if (mem) {
      pushEvent(
        makeEvent("memory", "sample.memory", undefined, {
          usedMB: Math.round(mem.usedJSHeapSize / 1024 / 1024),
          totalMB: Math.round(mem.totalJSHeapSize / 1024 / 1024),
          limitMB: Math.round(mem.jsHeapSizeLimit / 1024 / 1024),
        }),
      );
    }
  }, 5000);

  // FPS 帧率监控 + rAF 心跳阻塞检测
  startFpsAndBlockDetection();

  // Web Worker 心跳兜底：主线程彻底卡死时 rAF 不再触发，靠 Worker 兜底
  startWorkerHeartbeat();
}

// ============================================================
// FPS 采样 + rAF 心跳阻塞检测
// ============================================================

function startFpsAndBlockDetection() {
  if (typeof window === "undefined" || typeof requestAnimationFrame === "undefined") return;

  lastFrameTs = performance.now();
  lastBlockReportTs = 0;

  const tick = (now: number) => {
    const delta = now - lastFrameTs;
    lastFrameTs = now;

    // 帧间隔超过阈值 → 主线程在两帧之间被阻塞
    if (delta > RAF_BLOCK_THRESHOLD_MS) {
      reportBlock(delta, "raf");
    } else {
      frameSamples.push(delta);
    }

    rafId = requestAnimationFrame(tick);
  };
  rafId = requestAnimationFrame(tick);

  // 每秒计算一次 fps
  fpsTimer = setInterval(() => {
    if (frameSamples.length === 0) return;
    const sum = frameSamples.reduce((a, b) => a + b, 0);
    const fps = Math.round(1000 / (sum / frameSamples.length));
    // 抖动 = 帧间隔标准差
    const mean = sum / frameSamples.length;
    const jitter = Math.round(Math.sqrt(frameSamples.reduce((a, b) => a + (b - mean) ** 2, 0) / frameSamples.length) * 100) / 100;

    const payload: FpsPayload = { fps, jitter, droppedStreak };
    pushEvent(makeEvent("fps", "sample.fps", undefined, payload as unknown as Record<string, unknown>));

    if (fps < FPS_DROP_THRESHOLD) {
      droppedStreak += 1;
    } else {
      droppedStreak = 0;
    }
    frameSamples = [];
  }, FPS_SAMPLE_WINDOW_MS);
}

// ============================================================
// Web Worker 心跳兜底（主线程彻底卡死时）
// ============================================================

function startWorkerHeartbeat() {
  if (typeof Worker === "undefined") return;
  try {
    // 内联 Worker：主线程彻底冻结时（rAF 不再触发）靠它兜底检测
    // Worker 只负责回复 pong，不主动判定——主线程繁忙但未冻结时 Worker 收 ping 会延迟，
    // 由 Worker 自己判定会误报"阻塞"。判定逻辑全部放主线程，且要求 rAF 也停止才报。
    const workerCode = `
      self.onmessage = function(e) {
        if (e.data === 'ping') {
          self.postMessage('pong');
        }
      };
    `;
    const blob = new Blob([workerCode], { type: "application/javascript" });
    const url = URL.createObjectURL(blob);
    worker = new Worker(url);
    URL.revokeObjectURL(url);
    lastWorkerReplyTs = Date.now();

    worker.onmessage = (e: MessageEvent) => {
      if (e.data === "pong") {
        lastWorkerReplyTs = Date.now();
      }
    };

    // 主线程定时 ping Worker；判定阻塞必须同时满足：
    //   1. rAF 已停止（lastFrameTs 超过 RAF_BLOCK_THRESHOLD_MS 没更新）→ 主线程真的冻结了
    //   2. Worker 也超过 WORKER_BLOCK_THRESHOLD_MS 没回复 → 双重确认
    // 单纯 Worker 回复慢但 rAF 仍在跑 = 主线程持续繁忙（低 FPS），不算冻结，靠 FPS 监控反映
    workerCheckTimer = setInterval(() => {
      const rafStalled = lastFrameTs > 0 && (performance.now() - lastFrameTs) > RAF_BLOCK_THRESHOLD_MS;
      if (rafStalled && Date.now() - lastWorkerReplyTs > WORKER_BLOCK_THRESHOLD_MS) {
        reportBlock(Date.now() - lastWorkerReplyTs, "worker");
        lastWorkerReplyTs = Date.now();
      }
      worker?.postMessage("ping");
    }, 200);
  } catch {
    /* Worker 创建失败则降级为仅 rAF 检测 */
  }
}

function reportBlock(durationMs: number, source: "raf" | "worker") {
  const now = Date.now();
  // 冷却，避免一次卡顿被多次上报
  if (now - lastBlockReportTs < BLOCK_REPORT_COOLDOWN_MS) return;
  lastBlockReportTs = now;

  const payload: BlockPayload = {
    durationMs: Math.round(durationMs),
    source,
    attribution: recentAttribution,
  };
  pushEvent(makeEvent("block", `main-thread.block.${source}`, durationMs, payload as unknown as Record<string, unknown>));
}

export function stopObservers() {
  if (longTaskObserver) {
    longTaskObserver.disconnect();
    longTaskObserver = null;
  }
  if (loafObserver) {
    loafObserver.disconnect();
    loafObserver = null;
  }
  if (paintObserver) {
    paintObserver.disconnect();
    paintObserver = null;
  }
  if (memoryTimer) {
    clearInterval(memoryTimer);
    memoryTimer = null;
  }
  if (rafId !== null && typeof cancelAnimationFrame !== "undefined") {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
  if (fpsTimer) {
    clearInterval(fpsTimer);
    fpsTimer = null;
  }
  if (workerCheckTimer) {
    clearInterval(workerCheckTimer);
    workerCheckTimer = null;
  }
  if (worker) {
    worker.terminate();
    worker = null;
  }
  recentAttribution = undefined;
  droppedStreak = 0;
  frameSamples = [];
  started = false;
}
