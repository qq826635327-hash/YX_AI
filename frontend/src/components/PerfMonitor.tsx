/** 性能监控弹窗面板。 */

import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, ChevronDown, Copy, Download, Sparkles, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  type PerfAlert,
  type PerfSession,
  type PerfMeasureAggregate,
  type DiagnoseFinding,
  type DiagnoseResult,
  type QueueDepth,
} from "@/perf";
import { fetchSessions, fetchAlerts, clearAllPerfData, diagnoseSession, fetchQueueDepth } from "@/perf/api";
import { toast } from "@/stores/ui";

interface PerfMonitorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** 将 ISO 时间字符串格式化为北京时间（Asia/Shanghai）。
 *  后端返回的 datetime 无 Z 后缀（如 2026-06-24T05:01:12），
 *  需要补 Z 让浏览器按 UTC 解析，再转为北京时间显示。
 */
function formatBeijingTime(iso: string | undefined): string {
  if (!iso) return "-";
  // 补 Z 后缀确保按 UTC 解析
  const fixed = iso.endsWith("Z") ? iso : iso + "Z";
  return new Date(fixed).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
}

/** 长任务占比计算：阻塞总时长 / 会话总时长 * 100 */
function longTaskPercent(totalMs: number, sessionDurationS: number): number {
  const sessionMs = Math.max(1, sessionDurationS) * 1000;
  return (totalMs / sessionMs) * 100;
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: "text-destructive",
  error: "text-destructive",
  warning: "text-amber-500",
  overall: "text-muted-foreground",
};

/** 内部监控事件前缀，过滤掉不展示给用户的事件 */
const INTERNAL_PREFIXES = ["sample.", "paint", "raf."];

/** 可折叠区块：有告警时默认展开，无告警时默认收起 */
function CollapsibleSection({
  title,
  icon,
  hasAlert,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  hasAlert?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(!!hasAlert);
  // 当 hasAlert 变化时同步展开状态
  useEffect(() => { if (hasAlert) setOpen(true); }, [hasAlert]);

  return (
    <section>
      <button
        type="button"
        className="flex items-center gap-2 text-sm font-medium mb-2 text-muted-foreground w-full text-left hover:text-foreground transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        {icon}
        {title}
        <ChevronDown className={cn("h-4 w-4 ml-auto transition-transform", open && "rotate-180")} />
      </button>
      {open && children}
    </section>
  );
}

export function PerfMonitor({ open, onOpenChange }: PerfMonitorProps) {
  const [sessions, setSessions] = useState<PerfSession[]>([]);
  const [alerts, setAlerts] = useState<PerfAlert[]>([]);
  const [queue, setQueue] = useState<QueueDepth | null>(null);
  const [diagnose, setDiagnose] = useState<DiagnoseResult | null>(null);
  const [diagnosing, setDiagnosing] = useState(false);

  useEffect(() => {
    if (!open) return;
    loadData();
    setDiagnose(null);
  }, [open]);

  async function loadData() {
    try {
      const [sess, al, qd] = await Promise.all([fetchSessions(10, 0), fetchAlerts(false), fetchQueueDepth().catch(() => null)]);
      setSessions(sess);
      setAlerts(al);
      setQueue(qd);
    } catch {
      /* 忽略加载失败 */
    }
  }

  const latest = sessions[0];

  const summary = useMemo(() => {
    if (!latest) return null;
    const aggs = (latest.measure_aggregates as PerfMeasureAggregate[]) || [];
    const longTaskAgg = aggs.find((a) => a.name === "main-thread" || a.name === "main-thread.loaf");
    const fpsAgg = aggs.find((a) => a.name === "fps.min");
    const blockAgg = aggs.find((a) => a.name === "block.max");
    const apiAggs = aggs
      .filter((a) => a.name.startsWith("api"))
      .sort((a, b) => b.maxMs - a.maxMs);
    // 过滤掉内部监控事件
    const otherAggs = aggs.filter(
      (a) =>
        a.name !== "main-thread" &&
        a.name !== "main-thread.loaf" &&
        a.name !== "fps.min" &&
        a.name !== "block.max" &&
        !a.name.startsWith("api") &&
        !INTERNAL_PREFIXES.some((p) => a.name.startsWith(p)),
    );

    return {
      longTaskCount: latest.long_task_count ?? 0,
      longTaskTotalMs: latest.long_task_total_ms ?? 0,
      memUsedMB: latest.mem_used_mb ?? 0,
      longTaskAgg,
      fpsAgg,
      blockAgg,
      apiAggs,
      otherAggs,
    };
  }, [latest]);

  // 判断各区块是否有告警
  const hasBlockAlert = (summary?.blockAgg?.maxMs ?? 0) > 200;
  const hasFpsAlert = (summary?.fpsAgg?.maxMs ?? 60) < 50;
  const hasLongTaskAlert = (summary?.longTaskCount ?? 0) > 0;
  const hasApiAlert = (summary?.apiAggs.some((a) => a.maxMs > 3000) ?? false);

  async function runDiagnose() {
    if (!latest) return;
    setDiagnosing(true);
    try {
      const result = await diagnoseSession(latest.session_id);
      setDiagnose(result);
      if (result.findings.length === 0) {
        toast.success("未发现性能问题");
      } else {
        toast.success(`AI 诊断完成，发现 ${result.findings.length} 个问题`);
      }
    } catch {
      toast.error("诊断失败");
    } finally {
      setDiagnosing(false);
    }
  }

  async function copyReport() {
    if (!latest) return;
    const report = diagnose?.report ?? {
      version: 3,
      exportedAt: new Date().toISOString(),
      sessionStartedAt: latest.started_at,
      ua: navigator.userAgent,
      appVersion: latest.app_version,
      summary: {
        sessionDurationS: latest.session_duration_s,
        longTaskCount: latest.long_task_count,
        longTaskTotalMs: latest.long_task_total_ms,
        memUsedMB: latest.mem_used_mb,
      },
      counters: latest.counters,
      measureAggregates: latest.measure_aggregates,
    };
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      toast.success("性能报告已复制到剪贴板，可粘贴给 AI");
    } catch {
      toast.error("复制失败");
    }
  }

  function downloadReport() {
    if (!latest) return;
    const report = diagnose?.report ?? {
      version: 3,
      exportedAt: new Date().toISOString(),
      sessionStartedAt: latest.started_at,
      summary: {
        longTaskCount: latest.long_task_count,
        longTaskTotalMs: latest.long_task_total_ms,
        memUsedMB: latest.mem_used_mb,
      },
      counters: latest.counters,
      measureAggregates: latest.measure_aggregates,
    };
    try {
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `perf-report-${latest.session_id.slice(0, 8)}-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("报告已下载");
    } catch {
      toast.error("下载失败");
    }
  }

  async function handleClearAll() {
    try {
      await clearAllPerfData();
      setSessions([]);
      setAlerts([]);
      setDiagnose(null);
      toast.success("性能数据已清空");
    } catch {
      toast.error("清空失败");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            性能监控
            {/* 操作按钮固定在右上角 */}
            <div className="ml-auto flex gap-2">
              <Button
                variant="default"
                size="sm"
                className="gap-1 h-7"
                onClick={runDiagnose}
                disabled={!latest || diagnosing}
              >
                <Sparkles className="h-3.5 w-3.5" />
                {diagnosing ? "诊断中..." : "AI 诊断"}
              </Button>
              <Button variant="outline" size="sm" className="gap-1 h-7" onClick={downloadReport} disabled={!latest}>
                <Download className="h-3.5 w-3.5" />
                导出
              </Button>
              <Button variant="outline" size="sm" className="gap-1 h-7" onClick={copyReport} disabled={!latest}>
                <Copy className="h-3.5 w-3.5" />
                复制
              </Button>
              <Button variant="destructive" size="sm" className="gap-1 h-7" onClick={handleClearAll}>
                <Trash2 className="h-3.5 w-3.5" />
                清空
              </Button>
              <Button variant="outline" size="sm" className="h-7" onClick={loadData}>
                刷新
              </Button>
            </div>
          </DialogTitle>
        </DialogHeader>

        {!summary ? (
          <div className="text-sm text-muted-foreground py-8 text-center">暂无性能数据</div>
        ) : (
          <div className="space-y-4 overflow-y-auto flex-1 min-h-0">
            {/* 顶部指标 + 队列深度（始终展示） */}
            <div className="grid grid-cols-4 gap-4">
              <MetricCard
                label="长任务"
                value={summary.longTaskCount}
                highlight={summary.longTaskCount > 0 ? "warning" : undefined}
              />
              <MetricCard
                label="阻塞总时"
                value={`${Math.round(summary.longTaskTotalMs)}ms`}
                highlight={summary.longTaskTotalMs > 300 ? "warning" : undefined}
              />
              <MetricCard label="内存" value={`${summary.memUsedMB}MB`} />
              <MetricCard
                label="后端队列"
                value={queue ? `${queue.active_tasks}/${queue.semaphore_max}` : "-"}
                highlight={queue?.saturated ? "warning" : undefined}
              />
            </div>

            {/* 告警（始终展示，有告警时突出） */}
            <section>
              <h3 className="text-sm font-medium mb-2 text-muted-foreground flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                告警
                {alerts.length > 0 && (
                  <Badge variant="destructive" className="text-[10px] px-1.5 py-0">{alerts.length}</Badge>
                )}
              </h3>
              {alerts.length === 0 ? (
                <div className="text-xs text-muted-foreground">暂无告警</div>
              ) : (
                <div className="space-y-2">
                  {[...alerts]
                    .sort((a, b) => severityRank(b.level) - severityRank(a.level))
                    .map((alert) => (
                    <div
                      key={alert.id}
                      className={cn(
                        "rounded-md border p-2 text-sm",
                        alert.level === "error" && "border-destructive/40 bg-destructive/5",
                      )}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={alert.level === "error" ? "destructive" : "warning"}>
                          {alert.level}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatBeijingTime(alert.created_at)}
                        </span>
                      </div>
                      <div>{alert.message}</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {alert.metric}: 实际 {alert.actual.toFixed(2)} / 阈值 {alert.threshold}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* AI 诊断结果（有诊断时展示） */}
            {diagnose && (
              <section className="rounded-lg border border-primary/30 bg-primary/5 p-4">
                <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  AI 诊断结果
                  <Badge variant={diagnose.severity === "critical" || diagnose.severity === "error" ? "destructive" : diagnose.severity === "warning" ? "warning" : "secondary"}>
                    {diagnose.severity}
                  </Badge>
                  <span className="text-xs font-normal text-muted-foreground ml-auto">
                    {diagnose.findings.length} 个发现
                  </span>
                </h3>
                {diagnose.findings.length === 0 ? (
                  <div className="text-sm text-muted-foreground">未发现性能问题，各项指标正常</div>
                ) : (
                  <div className="space-y-3">
                    {diagnose.findings.map((f) => (
                      <FindingCard key={f.id} finding={f} />
                    ))}
                  </div>
                )}
                <div className="mt-3 pt-3 border-t text-xs text-muted-foreground">
                  提示：点击「复制」可获取完整诊断报告，粘贴给任意 AI 助手可进一步分析
                </div>
              </section>
            )}

            {/* FPS / Block 指标（可折叠，有告警时默认展开） */}
            {(summary.fpsAgg || summary.blockAgg) && (
              <CollapsibleSection
                title="FPS / 主线程阻塞"
                hasAlert={hasBlockAlert || hasFpsAlert}
              >
                <div className="grid grid-cols-2 gap-4">
                  {summary.fpsAgg && (
                    <MiniStat
                      label={`最低 FPS ${Math.round(summary.fpsAgg.maxMs)} / 均 ${Math.round(summary.fpsAgg.avgMs)}`}
                      value={`${Math.round(summary.fpsAgg.maxMs)}`}
                      highlight={summary.fpsAgg.maxMs < 50 ? "warning" : undefined}
                    />
                  )}
                  {summary.blockAgg && (
                    <MiniStat
                      label={`阻塞（${summary.blockAgg.count} 次 / 最长 ${Math.round(summary.blockAgg.maxMs)}ms）`}
                      value={`${Math.round(summary.blockAgg.maxMs)}ms`}
                      highlight={summary.blockAgg.maxMs > 200 ? "error" : undefined}
                    />
                  )}
                </div>
              </CollapsibleSection>
            )}

            {/* 长任务明细（可折叠，有告警时默认展开） */}
            <CollapsibleSection
              title="长任务明细"
              icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
              hasAlert={hasLongTaskAlert}
            >
              {summary.longTaskAgg ? (
                <div className="grid grid-cols-4 gap-3">
                  <MiniStat label="平均" value={`${Math.round(summary.longTaskAgg.avgMs)}ms`} />
                  <MiniStat label="P95" value={`${Math.round(summary.longTaskAgg.p95Ms)}ms`} />
                  <MiniStat label="最长" value={`${Math.round(summary.longTaskAgg.maxMs)}ms`} highlight={summary.longTaskAgg.maxMs > 300 ? "warning" : undefined} />
                  <MiniStat
                    label="占比"
                    value={`${longTaskPercent(summary.longTaskTotalMs, latest?.session_duration_s ?? 1).toFixed(1)}%`}
                    highlight={longTaskPercent(summary.longTaskTotalMs, latest?.session_duration_s ?? 1) > 10 ? "warning" : undefined}
                  />
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">无长任务</div>
              )}
            </CollapsibleSection>

            {/* 慢请求 Top 10（可折叠，有慢请求时默认展开） */}
            <CollapsibleSection
              title="慢请求"
              hasAlert={hasApiAlert}
            >
              {summary.apiAggs.length === 0 ? (
                <div className="text-xs text-muted-foreground">无 API 请求记录</div>
              ) : (
                <div className="border rounded-md overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">接口</th>
                        <th className="text-right px-3 py-2 font-medium">次数</th>
                        <th className="text-right px-3 py-2 font-medium">平均</th>
                        <th className="text-right px-3 py-2 font-medium">P95</th>
                        <th className="text-right px-3 py-2 font-medium">最大</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.apiAggs.slice(0, 10).map((agg) => (
                        <tr key={agg.name} className="border-t">
                          <td className="px-3 py-1.5 font-mono text-xs" title={agg.name}>{agg.name.replace("api/api/", "/")}</td>
                          <td className="px-3 py-1.5 text-right font-mono">{agg.count}</td>
                          <td className="px-3 py-1.5 text-right font-mono">{Math.round(agg.avgMs)}ms</td>
                          <td className="px-3 py-1.5 text-right font-mono">{Math.round(agg.p95Ms)}ms</td>
                          <td className={cn("px-3 py-1.5 text-right font-mono", agg.maxMs > 1000 && "text-amber-500", agg.maxMs > 5000 && "text-destructive")}>
                            {Math.round(agg.maxMs)}ms
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CollapsibleSection>

            {/* 其他耗时分布（可折叠，默认收起） */}
            {summary.otherAggs.length > 0 && (
              <CollapsibleSection title="其他耗时分布">
                <div className="border rounded-md overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">名称</th>
                        <th className="text-right px-3 py-2 font-medium">次数</th>
                        <th className="text-right px-3 py-2 font-medium">平均</th>
                        <th className="text-right px-3 py-2 font-medium">P95</th>
                        <th className="text-right px-3 py-2 font-medium">最大</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...summary.otherAggs]
                        .sort((a, b) => b.totalMs - a.totalMs)
                        .map((agg) => (
                          <tr key={agg.name} className="border-t">
                            <td className="px-3 py-1.5">{agg.name}</td>
                            <td className="px-3 py-1.5 text-right font-mono">{agg.count}</td>
                            <td className="px-3 py-1.5 text-right font-mono">{Math.round(agg.avgMs)}ms</td>
                            <td className="px-3 py-1.5 text-right font-mono">{Math.round(agg.p95Ms)}ms</td>
                            <td className="px-3 py-1.5 text-right font-mono">{Math.round(agg.maxMs)}ms</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </CollapsibleSection>
            )}

            {/* 历史趋势 mini 图（可折叠，默认收起） */}
            {sessions.length > 1 && (
              <CollapsibleSection title="最近会话趋势">
                <TrendChart sessions={sessions.slice(0, 10).reverse()} />
              </CollapsibleSection>
            )}

            {/* 历史会话（可折叠，默认收起） */}
            <CollapsibleSection title="最近会话">
              <div className="space-y-1">
                {sessions.slice(0, 5).map((s) => (
                  <div key={s.id} className="flex justify-between text-xs text-muted-foreground py-1 border-b last:border-0">
                    <span>{formatBeijingTime(s.created_at)}</span>
                    <span>
                      LT{s.long_task_count} / {s.long_task_total_ms.toFixed(0)}ms / {s.mem_used_mb}MB
                    </span>
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function severityRank(level: string): number {
  return { critical: 4, error: 3, warning: 2, info: 1 }[level] ?? 0;
}

function FindingCard({ finding }: { finding: DiagnoseFinding }) {
  return (
    <div className={cn("rounded-md border p-3", finding.severity === "critical" && "border-destructive/40 bg-destructive/5")}>
      <div className="flex items-center gap-2 mb-1">
        <Badge
          variant={finding.severity === "critical" || finding.severity === "error" ? "destructive" : finding.severity === "warning" ? "warning" : "secondary"}
        >
          {finding.severity}
        </Badge>
        <span className="text-xs text-muted-foreground">{finding.category}</span>
      </div>
      <div className={cn("text-sm font-medium mb-1", SEVERITY_COLOR[finding.severity])}>{finding.title}</div>
      {finding.evidence && <div className="text-xs text-muted-foreground mb-1">证据：{finding.evidence}</div>}
      {finding.suggestion && <div className="text-xs mt-1">建议：{finding.suggestion}</div>}
      {finding.suspects && finding.suspects.length > 0 && (
        <div className="text-xs mt-1 font-mono text-muted-foreground">
          可疑：{finding.suspects.join(" / ")}
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number;
  highlight?: "warning" | "error";
}) {
  return (
    <div className="rounded-lg border p-3 text-center">
      <div
        className={cn(
          "text-2xl font-bold",
          highlight === "error" && "text-destructive",
          highlight === "warning" && "text-amber-500"
        )}
      >
        {value}
      </div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: "warning" | "error";
}) {
  return (
    <div className="rounded-md border px-3 py-2 text-center">
      <div className={cn(
        "text-lg font-bold font-mono",
        highlight === "error" && "text-destructive",
        highlight === "warning" && "text-amber-500"
      )}>
        {value}
      </div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

/** 多会话历史趋势 mini 折线图（纯 SVG，无依赖）。 */
function TrendChart({ sessions }: { sessions: PerfSession[] }) {
  if (sessions.length < 2) return null;
  const W = 560;
  const H = 80;
  const pad = 8;
  const n = sessions.length;
  const xs = (i: number) => pad + (i * (W - pad * 2)) / Math.max(1, n - 1);

  const ltValues = sessions.map((s) => s.long_task_count || 0);
  const durValues = sessions.map((s) => Math.round(s.long_task_total_ms || 0));
  const memValues = sessions.map((s) => s.mem_used_mb || 0);

  const maxLt = Math.max(1, ...ltValues);
  const maxDur = Math.max(1, ...durValues);
  const maxMem = Math.max(1, ...memValues);

  const line = (vals: number[], max: number, color: string) => {
    const pts = vals.map((v, i) => `${xs(i)},${H - pad - (v / max) * (H - pad * 2)}`).join(" ");
    return <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />;
  };

  return (
    <div className="border rounded-md p-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 80 }}>
        {line(ltValues, maxLt, "#7F77DD")}
        {line(durValues, maxDur, "#D85A30")}
        {line(memValues, maxMem, "#378ADD")}
      </svg>
      <div className="flex gap-4 text-xs text-muted-foreground mt-1">
        <span><span className="inline-block w-3 h-0.5 align-middle mr-1" style={{ background: "#7F77DD" }} />长任务数(最大 {maxLt})</span>
        <span><span className="inline-block w-3 h-0.5 align-middle mr-1" style={{ background: "#D85A30" }} />阻塞ms(最大 {maxDur})</span>
        <span><span className="inline-block w-3 h-0.5 align-middle mr-1" style={{ background: "#378ADD" }} />内存MB(最大 {maxMem})</span>
      </div>
    </div>
  );
}
