/** 浮动日志查看器：右下角悬浮按钮 + 弹窗，展示前后端错误。

设计目标：
- 不打扰主流程：默认折叠成一个圆形按钮，仅 ERROR/WARNING 时显示红点
- AI 开发友好：可以一键复制全部日志为 JSON / 文本，方便贴给 AI
- 自动滚动 + 过滤 + 关键字搜索
- 支持加载历史日志（/api/logs）
*/

import { useEffect, useMemo, useRef, useState } from "react";
import { useLogStore, logger as logHelper } from "@/stores/logStore";
import { logsApi } from "@/api/logs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { LogEntry, LogLevel } from "@/types";

const LEVEL_STYLES: Record<LogLevel, { dot: string; text: string; bg: string; label: string }> = {
  DEBUG: { dot: "bg-slate-400", text: "text-slate-500", bg: "bg-slate-500/10", label: "DEBUG" },
  INFO: { dot: "bg-blue-500", text: "text-blue-600 dark:text-blue-400", bg: "bg-blue-500/10", label: "INFO" },
  WARNING: {
    dot: "bg-amber-500",
    text: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-500/10",
    label: "WARN",
  },
  ERROR: {
    dot: "bg-red-500",
    text: "text-red-600 dark:text-red-400",
    bg: "bg-red-500/10",
    label: "ERROR",
  },
  CRITICAL: {
    dot: "bg-red-700",
    text: "text-red-700 dark:text-red-300",
    bg: "bg-red-700/15",
    label: "CRIT",
  },
};

const SOURCE_LABELS: Record<string, string> = {
  frontend: "前端",
  backend: "后端",
  api: "API",
  ws: "WS",
};

const PHASE_LABELS: Record<string, { label: string; color: string }> = {
  system: { label: "系统", color: "text-slate-500" },
  validate: { label: "校验", color: "text-blue-500" },
  ref_collect: { label: "参考图", color: "text-purple-500" },
  generate: { label: "生成", color: "text-green-500" },
  download: { label: "下载", color: "text-cyan-500" },
};

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const isToday =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    if (isToday) {
      return d.toLocaleTimeString("zh-CN", { hour12: false });
    }
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

function copyToClipboard(text: string): void {
  try {
    void navigator.clipboard.writeText(text);
  } catch {
    /* 忽略剪贴板错误 */
  }
}

/** 浮动按钮：只订阅 unread，不订阅 entries 数组。
 * 后端每推一条 WS 日志只更新 unread 计数，不触发按钮重渲染。 */
function LogViewerFloatingButton() {
  const viewerOpen = useLogStore((s) => s.viewerOpen);
  const toggleViewer = useLogStore((s) => s.toggleViewer);
  const unread = useLogStore((s) => s.unread);

  if (viewerOpen) return null;

  return (
    <button
      onClick={toggleViewer}
      className={cn(
        "fixed bottom-4 right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full shadow-lg transition-[background-color,transform]",
        "bg-background border hover:bg-accent active:scale-95",
        unread > 0 && "ring-2 ring-red-500/50"
      )}
      title={`日志查看器（${unread} 条未读）`}
    >
      <span className="text-lg">📋</span>
      {unread > 0 && (
        <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </button>
  );
}

/** 日志列表浮窗：展开时才渲染，才订阅 entries 数组。 */
function LogViewerPanel() {
  const viewerOpen = useLogStore((s) => s.viewerOpen);
  const toggleViewer = useLogStore((s) => s.toggleViewer);
  const closeViewer = useLogStore((s) => s.closeViewer);
  const clear = useLogStore((s) => s.clear);
  const levelFilter = useLogStore((s) => s.levelFilter);
  const setLevelFilter = useLogStore((s) => s.setLevelFilter);
  const keyword = useLogStore((s) => s.keyword);
  const setKeyword = useLogStore((s) => s.setKeyword);

  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [clearing, setClearing] = useState(false);
  const listRef = useRef<HTMLDivElement | null>(null);

  // 清空：调后端接口 + 清前端缓存
  const handleClear = async () => {
    try {
      setClearing(true);
      await logsApi.clear();
      clear();
      logHelper.info("日志已清空", "frontend", "LogViewer");
    } catch (err: any) {
      logHelper.error(`清空日志失败: ${err?.message || "未知错误"}`, "frontend", "LogViewer");
    } finally {
      setClearing(false);
    }
  };

  // 取所有 entries（用于显示总数）
  const allEntries = useLogStore((s) => s.entries);
  // filteredEntries 是方法，每次渲染调用即可；用 useMemo 缓存避免 filter 开销
  const entries = useMemo(
    () =>
      allEntries.filter((e) => {
        if (levelFilter && e.level !== levelFilter) return false;
        const kw = keyword.trim().toLowerCase();
        if (kw && !`${e.message} ${e.logger}`.toLowerCase().includes(kw)) return false;
        return true;
      }),
    [allEntries, levelFilter, keyword]
  );

  // 打开时加载历史日志
  useEffect(() => {
    if (viewerOpen && !historyLoaded) {
      setLoadingHistory(true);
      logsApi
        .list({ limit: 200 })
        .then((resp) => {
          // 后端返回的是倒序（最新在前），这里 reverse 成正序（旧的在前）
          // 这样 pushBatch 后 store.entries 从早到晚排列，最新日志在最下方
          const ordered = [...resp.entries].reverse();
          useLogStore.getState().pushBatch(
            ordered.map((e) => ({
              timestamp: e.timestamp,
              source: "backend" as const,
              level: e.level,
              logger: e.logger,
              message: e.message,
            }))
          );
          setHistoryLoaded(true);
        })
        .catch((err) => {
          logHelper.error(`加载历史日志失败: ${err.message}`, "frontend", "LogViewer");
        })
        .finally(() => setLoadingHistory(false));
    }
  }, [viewerOpen, historyLoaded]);

  // 自动滚动到底部
  useEffect(() => {
    if (!autoScroll || !listRef.current) return;
    const el = listRef.current;
    el.scrollTop = el.scrollHeight;
  }, [entries, autoScroll, viewerOpen]);

  // 复制全部为 JSON（方便贴给 AI）
  const copyAll = () => {
    copyToClipboard(JSON.stringify(entries, null, 2));
    logHelper.info("已复制日志到剪贴板", "frontend", "LogViewer");
  };

  // 复制全部为纯文本
  const copyAsText = () => {
    const text = entries
      .map(
        (e) =>
          `[${formatTime(e.timestamp)}] [${e.level}] [${e.source}/${e.logger}] ${e.message}` +
          (e.context ? ` ${JSON.stringify(e.context)}` : "")
      )
      .join("\n");
    copyToClipboard(text);
    logHelper.info("已复制日志为文本格式", "frontend", "LogViewer");
  };

  // 快捷键：Ctrl/Cmd + Shift + L 打开/关闭
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        toggleViewer();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggleViewer]);

  if (!viewerOpen) return null;

  return (
    <div
      className={cn(
        "fixed bottom-4 right-4 z-50 flex flex-col rounded-lg border bg-background shadow-2xl",
        "h-[70vh] w-[640px] max-w-[calc(100vw-2rem)]"
      )}
    >
      {/* 头部 */}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">日志查看器</span>
          <Badge variant="secondary" className="text-[10px]">
            {entries.length} 条
          </Badge>
          {loadingHistory && <span className="text-xs text-muted-foreground">加载中…</span>}
        </div>
        <div className="flex items-center gap-1">
          <Button size="sm" variant="ghost" onClick={copyAsText} title="复制为文本">
            📝
          </Button>
          <Button size="sm" variant="ghost" onClick={copyAll} title="复制为 JSON">
            {"{}"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={handleClear}
            disabled={clearing}
            title="清空日志（后端 + 前端）"
            className="text-destructive"
          >
            {clearing ? "清空中…" : "清空"}
          </Button>
          <Button size="sm" variant="ghost" onClick={closeViewer} title="关闭">
            ✕
          </Button>
        </div>
      </div>

      {/* 过滤栏 */}
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <input
          type="text"
          placeholder="搜索日志…"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="flex-1 rounded-md border bg-background px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        <div className="flex items-center gap-1">
          {(["ERROR", "WARNING", "INFO", "DEBUG"] as LogLevel[]).map((lv) => (
            <button
              key={lv}
              onClick={() => setLevelFilter(levelFilter === lv ? null : lv)}
              className={cn(
                "rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors",
                LEVEL_STYLES[lv].text,
                levelFilter === lv ? LEVEL_STYLES[lv].bg : "hover:bg-accent"
              )}
            >
              {LEVEL_STYLES[lv].label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="h-3 w-3"
          />
          自动滚动
        </label>
      </div>

      {/* 列表 */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto px-2 py-1 font-mono text-xs"
        onScroll={(e) => {
          // 用户向上滚动时，暂停自动滚动
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
          if (!atBottom) setAutoScroll(false);
        }}
      >
        {entries.length === 0 && !loadingHistory && (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            暂无日志。试试看触发一个后端 API 错误看看吧～
          </div>
        )}
        {entries.map((e) => (
          <LogRow key={e.id} entry={e} />
        ))}
      </div>

      {/* 底部状态栏 */}
      <div className="flex items-center justify-between border-t px-3 py-1.5 text-[10px] text-muted-foreground">
        <span>实时接收后端 ERROR/WARNING · 快捷键 Ctrl+Shift+L</span>
        <span>来源: 实时 WS + /api/logs 历史</span>
      </div>
    </div>
  );
}

/** 日志查看器入口：浮动按钮（常驻，只订阅 unread）+ 浮窗（展开时才渲染，订阅 entries）。 */
export function LogViewer() {
  return (
    <>
      <LogViewerFloatingButton />
      <LogViewerPanel />
    </>
  );
}

function LogRow({ entry }: { entry: LogEntry }) {
  const style = LEVEL_STYLES[entry.level] || LEVEL_STYLES.INFO;
  const [expanded, setExpanded] = useState(false);
  const hasContext = !!entry.context && Object.keys(entry.context).length > 0;

  // 从 context 中提取结构化日志字段
  const phase = entry.context?.phase as string | undefined;
  const eventType = entry.context?.event_type as string | undefined;
  const dataJson = entry.context?.data_json as Record<string, unknown> | undefined;

  // 生成阶段标签
  const phaseInfo = phase ? PHASE_LABELS[phase] : undefined;

  // 结构化数据摘要（API 调用/下载/参考图收集）
  const summary = dataJson ? getStructuredSummary(dataJson, eventType) : null;

  return (
    <div
      className={cn(
        "group flex flex-col gap-0.5 rounded px-2 py-1 hover:bg-accent/40",
        entry.level === "ERROR" || entry.level === "CRITICAL" ? "border-l-2 border-red-500" : "",
        entry.level === "WARNING" ? "border-l-2 border-amber-500" : ""
      )}
    >
      <div className="flex items-start gap-2">
        <span className="text-[10px] text-muted-foreground shrink-0 mt-0.5">
          {formatTime(entry.timestamp)}
        </span>
        <Badge className={cn("shrink-0 px-1.5 py-0 text-[10px]", style.text, style.bg, "border-0")}>
          {style.label}
        </Badge>
        {phaseInfo && (
          <span className={cn("shrink-0 text-[10px] font-medium", phaseInfo.color)}>
            [{phaseInfo.label}]
          </span>
        )}
        <span className="shrink-0 text-[10px] text-muted-foreground">
          [{SOURCE_LABELS[entry.source] || entry.source}/{entry.logger}]
        </span>
        <span
          className={cn("flex-1 break-all", style.text, !expanded && "line-clamp-2")}
          onClick={() => (hasContext || dataJson) && setExpanded(!expanded)}
        >
          {entry.message}
        </span>
        {(hasContext || dataJson) && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="shrink-0 text-[10px] text-muted-foreground hover:text-foreground"
          >
            {expanded ? "收起" : "详情"}
          </button>
        )}
      </div>
      {/* 结构化摘要（不展开时显示） */}
      {summary && !expanded && (
        <div className="ml-20 text-[10px] text-muted-foreground">
          {summary}
        </div>
      )}
      {expanded && (hasContext || dataJson) && (
        <pre className="ml-12 mt-1 overflow-x-auto rounded bg-muted/50 p-2 text-[10px] text-muted-foreground">
          {dataJson
            ? JSON.stringify(dataJson, null, 2)
            : JSON.stringify(entry.context, null, 2)}
        </pre>
      )}
    </div>
  );
}

/** 从结构化数据生成人类可读的摘要行 */
function getStructuredSummary(data: Record<string, unknown>, eventType?: string): string | null {
  if (eventType === "api_request") {
    const parts: string[] = [];
    if (data.provider_kind) parts.push(String(data.provider_kind));
    if (data.model) parts.push(String(data.model));
    if (data.response_status) parts.push(`→ ${data.response_status}`);
    if (data.duration_ms) parts.push(`${data.duration_ms}ms`);
    if (data.error) parts.push(`Error: ${String(data.error).slice(0, 80)}`);
    return parts.join(" | ") || null;
  }
  if (eventType === "download") {
    const parts: string[] = [];
    if (data.file_size) parts.push(`${Math.round(Number(data.file_size) / 1024)}KB`);
    if (data.duration_ms) parts.push(`${data.duration_ms}ms`);
    if (data.error) parts.push(`Error: ${String(data.error).slice(0, 80)}`);
    return parts.join(" | ") || null;
  }
  if (eventType === "ref_collect") {
    const parts: string[] = [];
    if (data.source) parts.push(String(data.source));
    if (data.count) parts.push(`${data.count} 张`);
    return parts.join(" | ") || null;
  }
  return null;
}
