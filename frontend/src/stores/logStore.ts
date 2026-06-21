/** 全局日志状态：记录前后端错误，方便 AI 开发或开发者直接看。 */

import { create } from "zustand";
import type { LogEntry, LogLevel, LogSource } from "@/types";

/** 内存中保留的最大日志条数。 */
const MAX_ENTRIES = 500;

interface LogState {
  /** 全部日志条目（最新的在前） */
  entries: LogEntry[];

  /** 未读数量（用于在浮动按钮上显示红点） */
  unread: number;

  /** LogViewer 浮窗是否展开 */
  viewerOpen: boolean;

  /** 当前选中的级别过滤（null = 全部） */
  levelFilter: LogLevel | null;

  /** 关键字过滤 */
  keyword: string;

  // ---------- 增删 ----------
  pushEntry: (entry: Omit<LogEntry, "id">) => void;
  pushBatch: (entries: Array<Omit<LogEntry, "id">>) => void;
  clear: () => void;
  markRead: () => void;

  // ---------- 开关 ----------
  openViewer: () => void;
  closeViewer: () => void;
  toggleViewer: () => void;

  // ---------- 过滤 ----------
  setLevelFilter: (level: LogLevel | null) => void;
  setKeyword: (kw: string) => void;

  // ---------- 计算 ----------
  filteredEntries: () => LogEntry[];
}

let _idCounter = 0;
function nextId(): string {
  _idCounter += 1;
  return `${Date.now().toString(36)}-${_idCounter}`;
}

export const useLogStore = create<LogState>((set, get) => ({
  entries: [],
  unread: 0,
  viewerOpen: false,
  levelFilter: null,
  keyword: "",

  pushEntry: (entry) => {
    set((s) => {
      const newEntry: LogEntry = { ...entry, id: nextId() };
      // 最新日志追加到末尾，方便像 tail -f 一样看
      const entries = [...s.entries, newEntry].slice(-MAX_ENTRIES);
      // 仅 ERROR / WARNING / CRITICAL 算作"未读"
      const isUrgent =
        newEntry.level === "ERROR" || newEntry.level === "CRITICAL" || newEntry.level === "WARNING";
      const unread = s.viewerOpen || !isUrgent ? s.unread : s.unread + 1;
      return { entries, unread };
    });
  },

  pushBatch: (batch) => {
    set((s) => {
      // batch 应该按时间正序传入（旧的在前，新的在后），直接追加到现有 entries 末尾
      const newEntries: LogEntry[] = batch.map((e) => ({ ...e, id: nextId() }));
      const entries = [...s.entries, ...newEntries].slice(-MAX_ENTRIES);
      const urgentCount = newEntries.filter(
        (e) => e.level === "ERROR" || e.level === "CRITICAL" || e.level === "WARNING"
      ).length;
      const unread = s.viewerOpen ? s.unread : s.unread + urgentCount;
      return { entries, unread };
    });
  },

  clear: () => set({ entries: [], unread: 0 }),

  markRead: () => set({ unread: 0 }),

  openViewer: () => set({ viewerOpen: true, unread: 0 }),
  closeViewer: () => set({ viewerOpen: false }),
  toggleViewer: () =>
    set((s) => ({ viewerOpen: !s.viewerOpen, unread: !s.viewerOpen ? 0 : s.unread })),

  setLevelFilter: (level) => set({ levelFilter: level }),
  setKeyword: (kw) => set({ keyword: kw }),

  filteredEntries: () => {
    const { entries, levelFilter, keyword } = get();
    const kw = keyword.trim().toLowerCase();
    return entries.filter((e) => {
      if (levelFilter && e.level !== levelFilter) return false;
      if (kw && !`${e.message} ${e.logger}`.toLowerCase().includes(kw)) return false;
      return true;
    });
  },
}));

// ============================================================
// 便捷 API：业务层直接调用，无需关心 store 实例
// ============================================================

/** 便捷 API：业务层直接调用，无需关心 store 实例。 */

// ============================================================

/** 记录一条日志。 */
export function log(
  level: LogLevel,
  source: LogSource,
  message: string,
  logger: string = source,
  context?: Record<string, unknown>
): void {
  useLogStore.getState().pushEntry({
    timestamp: new Date().toISOString(),
    source,
    level,
    logger,
    message,
    context,
  });
}

/** 便捷方法 */
type LogFn = (
  msg: string,
  source?: LogSource,
  loggerName?: string,
  ctx?: Record<string, unknown>
) => void;

export const logger: { debug: LogFn; info: LogFn; warn: LogFn; error: LogFn } = {
  debug: (msg, source, loggerName, ctx) => {
    const s: LogSource = source ?? "frontend";
    log("DEBUG", s, msg, loggerName ?? s, ctx);
  },
  info: (msg, source, loggerName, ctx) => {
    const s: LogSource = source ?? "frontend";
    log("INFO", s, msg, loggerName ?? s, ctx);
  },
  warn: (msg, source, loggerName, ctx) => {
    const s: LogSource = source ?? "frontend";
    log("WARNING", s, msg, loggerName ?? s, ctx);
  },
  error: (msg, source, loggerName, ctx) => {
    const s: LogSource = source ?? "frontend";
    log("ERROR", s, msg, loggerName ?? s, ctx);
  },
};
