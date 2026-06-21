/** WebSocket 消息消费 Hook：订阅任务状态和剧本解析进度推送。 */

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { tasksWs, scriptWs } from "@/api/websocket";
import type { WsMessage } from "@/types";

/**
 * 订阅任务 WebSocket 消息。
 * 收到 task.completed / task.failed / task.progress 时自动 invalidate 任务缓存。
 */
export function useTaskWsSubscription() {
  const qc = useQueryClient();

  useEffect(() => {
    const unsubscribe = tasksWs.on((msg: WsMessage) => {
      const type = msg.type;

      switch (type) {
        case "task.created":
        case "task.progress":
          // 刷新任务列表
          qc.invalidateQueries({ queryKey: ["tasks"] });
          break;
        case "task.completed":
        case "task.failed": {
          // 根据任务的 target_type 精确刷新对应实体缓存，避免请求风暴
          const data = msg.data as Record<string, unknown> | undefined;
          const targetType = (data?.target_type as string | undefined);
          qc.invalidateQueries({ queryKey: ["tasks"] });
          qc.invalidateQueries({ queryKey: ["assets"] });
          if (targetType?.startsWith("shot_")) {
            qc.invalidateQueries({ queryKey: ["shots"] });
          } else if (targetType === "character") {
            qc.invalidateQueries({ queryKey: ["characters"] });
          } else if (targetType === "scene") {
            qc.invalidateQueries({ queryKey: ["scenes"] });
          } else if (targetType === "prop") {
            qc.invalidateQueries({ queryKey: ["props"] });
          } else {
            // 未知类型，全量刷新
            qc.invalidateQueries({ queryKey: ["characters"] });
            qc.invalidateQueries({ queryKey: ["scenes"] });
            qc.invalidateQueries({ queryKey: ["props"] });
            qc.invalidateQueries({ queryKey: ["shots"] });
          }
          break;
        }
        default:
          // 忽略心跳、connected 等系统消息
          break;
      }
    });

    return () => {
      unsubscribe();
    };
  }, [qc]);
}

/**
 * 订阅剧本解析 WebSocket 消息。
 * 收到 script.completed / script.failed 时自动刷新剧本缓存。
 */
export function useScriptWsSubscription(projectId?: string) {
  const qc = useQueryClient();

  useEffect(() => {
    if (!projectId) return;

    const unsubscribe = scriptWs.on((msg: WsMessage) => {
      const type = msg.type;
      const data = msg.data as Record<string, unknown>;

      // 仅处理当前项目的消息
      if (data.project_id && data.project_id !== projectId) return;

      switch (type) {
        case "script.completed":
          // 解析完成，刷新剧本数据
          qc.invalidateQueries({ queryKey: ["script", projectId] });
          break;
        case "script.failed":
          // 解析失败，也刷新以显示错误信息
          qc.invalidateQueries({ queryKey: ["script", projectId] });
          break;
        case "script.parsing":
          // 解析中，刷新状态
          qc.invalidateQueries({ queryKey: ["script", projectId] });
          break;
        default:
          break;
      }
    });

    return () => {
      unsubscribe();
    };
  }, [qc, projectId]);
}
