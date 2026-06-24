/** 性能监控后端 API 调用。 */

import { http } from "@/api/client";
import type { PerfAlert, PerfEvent, PerfSession, PerfSessionSummary } from "./types";

export interface PerfSessionPayload {
  sessionId: string;
  startedAt?: string;
  endedAt?: string;
  ua?: string;
  appVersion?: string;
  summary: PerfSessionSummary;
  counters: Record<string, number>;
  measureAggregates: PerfSessionSummary["measureAggregates"];
  events: PerfEvent[];
}

export async function reportSession(payload: PerfSessionPayload): Promise<{ session_id: string; alert_count: number }> {
  const response = await http.post("perf/sessions", { json: payload });
  return (await response.json()) as { session_id: string; alert_count: number };
}

export async function fetchSessions(limit = 50, offset = 0): Promise<PerfSession[]> {
  const response = await http.get(`perf/sessions?limit=${limit}&offset=${offset}`);
  return (await response.json()) as PerfSession[];
}

export async function fetchAlerts(acknowledged?: boolean): Promise<PerfAlert[]> {
  const url = acknowledged !== undefined
    ? `perf/alerts?acknowledged=${acknowledged}`
    : "perf/alerts";
  const response = await http.get(url);
  return (await response.json()) as PerfAlert[];
}

export async function acknowledgeAlert(alertId: string): Promise<PerfAlert | null> {
  const response = await http.post(`perf/alerts/${alertId}/acknowledge`);
  return (await response.json()) as PerfAlert | null;
}

export async function clearAllPerfData(): Promise<{ deleted: boolean }> {
  const response = await http.delete("perf/clear");
  return (await response.json()) as { deleted: boolean };
}

export interface DiagnoseFinding {
  id: string;
  severity: "overall" | "warning" | "error" | "critical";
  category: string;
  title: string;
  evidence?: string;
  suggestion?: string;
  suspects?: string[];
}

export interface DiagnoseResult {
  session_id: string;
  severity: "overall" | "warning" | "error" | "critical";
  findings: DiagnoseFinding[];
  report: Record<string, unknown>;
}

export async function diagnoseSession(sessionId: string): Promise<DiagnoseResult> {
  const response = await http.post("perf/diagnose", { json: { session_id: sessionId } });
  return (await response.json()) as DiagnoseResult;
}

export interface QueueDepth {
  active_tasks: number;
  semaphore_available: number;
  semaphore_max: number;
  saturated: boolean;
}

export async function fetchQueueDepth(): Promise<QueueDepth> {
  const response = await http.get("perf/queue-depth");
  const json = (await response.json()) as { data: QueueDepth };
  return json.data;
}
