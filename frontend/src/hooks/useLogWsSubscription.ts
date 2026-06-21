/** 订阅后端 /ws/logs 推送，把 ERROR/WARNING 写入 logStore。 */

import { useEffect } from "react";
import { logsWs } from "@/api/websocket";
import { useLogStore } from "@/stores/logStore";
import type { LogLevel, WsMessage } from "@/types";

interface BackendLogData {
  level: string;
  logger: string;
  message: string;
  module?: string;
  lineno?: number;
  func?: string;
  phase?: string;
  event_type?: string;
  data_json?: Record<string, unknown>;
  trace_id?: string;
}

/** 把后端推送的日志写入 store。 */
export function useLogWsSubscription(): void {
  useEffect(() => {
    const unsubscribe = logsWs.on((msg: WsMessage) => {
      switch (msg.type) {
        case "log": {
          const data = msg.data as BackendLogData;
          if (!data) return;
          // 兼容大小写
          const level = (data.level?.toUpperCase() || "INFO") as LogLevel;
          const logger = data.logger || data.module || "backend";
          useLogStore.getState().pushEntry({
            timestamp: msg.timestamp || new Date().toISOString(),
            source: "backend",
            level,
            logger,
            message: data.message || "",
            context: {
              ...(data.module ? { module: data.module, lineno: data.lineno, func: data.func } : {}),
              ...(data.phase ? { phase: data.phase } : {}),
              ...(data.event_type ? { event_type: data.event_type } : {}),
              ...(data.data_json ? { data_json: data.data_json } : {}),
              ...(data.trace_id ? { trace_id: data.trace_id } : {}),
            },
          });
          break;
        }
        case "log.cleared":
          // 服务端清空后，前端也跟着清（可选）
          // useLogStore.getState().clear();
          break;
        default:
          break;
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);
}
