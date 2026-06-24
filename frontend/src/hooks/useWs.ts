/** WebSocket 消息消费 Hook：订阅任务状态和剧本解析进度推送。 */

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { tasksWs, scriptWs } from "@/api/websocket";
import type { WsMessage, ScriptParsingData, ScriptStreamData, ScriptStageDoneData, ParseStep } from "@/types";

/** 剧本解析步骤定义（固定顺序） */
export const PARSE_STEPS_DEFAULT: ParseStep[] = [
  { stage: "reading", label: "读取剧本", status: "pending" },
  { stage: "character", label: "提取角色/场景/道具", status: "pending" },
  { stage: "episode", label: "章节划分", status: "pending" },
  { stage: "shot", label: "分镜拆分", status: "pending" },
  { stage: "writing", label: "写入数据库", status: "pending" },
];

/** 剧本解析 WebSocket 回调集合 */
export interface ScriptWsCallbacks {
  /** 步骤进度更新 */
  onStepsChange?: (steps: ParseStep[]) => void;
  /** LLM 流式输出 token */
  onStreamToken?: (stage: string, tokens: string) => void;
  /** 流式输出阶段切换（清空旧内容） */
  onStreamStageChange?: (stage: string) => void;
}

/** 从 completed_stages 恢复步骤状态 */
export function rebuildSteps(currentStage: string, completedStages?: { stage: string; summary: string }[]): ParseStep[] {
  const completed = new Map((completedStages || []).map(c => [c.stage, c.summary]));
  return PARSE_STEPS_DEFAULT.map(s => {
    if (completed.has(s.stage)) {
      return { ...s, status: "done" as const, summary: completed.get(s.stage) };
    }
    if (s.stage === currentStage) {
      return { ...s, status: "active" as const };
    }
    return { ...s, status: "pending" as const };
  });
}

/**
 * 订阅任务 WebSocket 消息。
 * 收到 task.completed / task.failed / task.progress 时更新缓存。
 *
 * 性能优化：
 * - task.progress：精确更新单条任务缓存，不触发全量 invalidate
 * - task.completed/failed：去抖 300ms 后统一 invalidate，避免请求风暴
 */
export function useTaskWsSubscription() {
  const qc = useQueryClient();

  useEffect(() => {
    // 去抖定时器：task.completed/failed 在 300ms 内只 invalidate 一次
    let invalidateTimer: ReturnType<typeof setTimeout> | null = null;
    // 收集需要刷新的 queryKey
    const pendingKeys: string[][] = [];

    const scheduleInvalidate = (keys: string[][]) => {
      for (const key of keys) {
        if (!pendingKeys.some(k => k.join(",") === key.join(","))) {
          pendingKeys.push(key);
        }
      }
      if (invalidateTimer) clearTimeout(invalidateTimer);
      invalidateTimer = setTimeout(() => {
        const uniqueKeys = [...pendingKeys];
        pendingKeys.length = 0;
        invalidateTimer = null;
        for (const key of uniqueKeys) {
          qc.invalidateQueries({ queryKey: key });
        }
      }, 300);
    };

    const unsubscribe = tasksWs.on((msg: WsMessage) => {
      const type = msg.type;

      switch (type) {
        case "task.created":
          // 新任务不在缓存中，走去抖 invalidate 避免批量创建时请求风暴
          scheduleInvalidate([["tasks"]]);
          break;
        case "task.progress": {
          // 精确更新：直接修改缓存中对应任务的 progress，不触发全量请求
          const data = msg.data as Record<string, unknown> | undefined;
          const taskId = data?.task_id as string | undefined;
          const progress = data?.progress as number | undefined;
          const message = data?.message as string | undefined;
          if (taskId && progress !== undefined) {
            qc.setQueryData(["task-poll", taskId], (old: any) => {
              if (!old) return old;
              return { ...old, progress, status: "running", progress_message: message };
            });
            // 也更新任务列表缓存中对应条目
            qc.setQueryData(["tasks"], (old: any) => {
              if (!old?.items) return old;
              return {
                ...old,
                items: old.items.map((t: any) =>
                  t.id === taskId ? { ...t, progress, status: "running", progress_message: message } : t
                ),
              };
            });
          }
          break;
        }
        case "task.completed":
        case "task.failed": {
          // 去抖 invalidate：300ms 内多次 completed/failed 只刷新一次
          // 不直接 setQueryData 改状态，等 API 返回确认后的数据为准
          const data = msg.data as Record<string, unknown> | undefined;
          const targetType = (data?.target_type as string | undefined);

          const keys: string[][] = [["tasks"], ["assets"]];
          if (targetType?.startsWith("shot_")) {
            keys.push(["shots"]);
          } else if (targetType === "character") {
            keys.push(["characters"]);
          } else if (targetType === "scene") {
            keys.push(["scenes"]);
          } else if (targetType === "prop") {
            keys.push(["props"]);
          } else {
            keys.push(["characters"], ["scenes"], ["props"], ["shots"]);
          }
          scheduleInvalidate(keys);
          break;
        }
        default:
          break;
      }
    });

    return () => {
      unsubscribe();
      if (invalidateTimer) clearTimeout(invalidateTimer);
    };
  }, [qc]);
}

/**
 * 订阅剧本解析 WebSocket 消息。
 * 支持步骤进度、LLM 流式输出、阶段完成等消息类型。
 *
 * callbacks 用 ref 持有，不作为 useEffect 依赖，避免重复订阅。
 */
export function useScriptWsSubscription(projectId?: string, callbacks?: ScriptWsCallbacks) {
  const qc = useQueryClient();
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  useEffect(() => {
    if (!projectId) return;

    const unsubscribe = scriptWs.on((msg: WsMessage) => {
      const type = msg.type;
      const data = msg.data as Record<string, unknown>;

      // 仅处理当前项目的消息
      if (data.project_id && data.project_id !== projectId) return;

      switch (type) {
        case "script.parsing": {
          const pData = data as unknown as ScriptParsingData;
          const steps = rebuildSteps(pData.stage, pData.completed_stages);
          callbacksRef.current?.onStepsChange?.(steps);
          callbacksRef.current?.onStreamStageChange?.(pData.stage);
          break;
        }
        case "script.stream": {
          const sData = data as unknown as ScriptStreamData;
          callbacksRef.current?.onStreamToken?.(sData.stage, sData.tokens);
          break;
        }
        case "script.stage_done": {
          const dData = data as unknown as ScriptStageDoneData;
          // 优先使用 completed_stages 重建步骤（后端 v2 消息携带）
          if (dData.completed_stages && dData.completed_stages.length > 0) {
            const doneIdx = PARSE_STEPS_DEFAULT.findIndex(s => s.stage === dData.stage);
            // 找到下一个阶段作为 active
            const nextStage = doneIdx >= 0 && doneIdx < PARSE_STEPS_DEFAULT.length - 1
              ? PARSE_STEPS_DEFAULT[doneIdx + 1].stage
              : "";
            const steps = rebuildSteps(nextStage, dData.completed_stages);
            // 确保当前完成阶段标记为 done（带 summary）
            const finalSteps = steps.map(s =>
              s.stage === dData.stage ? { ...s, status: "done" as const, summary: dData.summary } : s
            );
            callbacksRef.current?.onStepsChange?.(finalSteps);
          } else {
            // 兼容旧版消息：标记完成阶段为 done，下一个为 active，之前的全部为 done
            const doneIdx = PARSE_STEPS_DEFAULT.findIndex(s => s.stage === dData.stage);
            callbacksRef.current?.onStepsChange?.(
              PARSE_STEPS_DEFAULT.map((s, idx) => {
                if (idx < doneIdx) {
                  return { ...s, status: "done" as const };
                }
                if (s.stage === dData.stage) {
                  return { ...s, status: "done" as const, summary: dData.summary };
                }
                if (idx === doneIdx + 1) {
                  return { ...s, status: "active" as const };
                }
                return { ...s, status: "pending" as const };
              })
            );
          }
          break;
        }
        case "script.completed":
          qc.invalidateQueries({ queryKey: ["script", projectId] });
          qc.invalidateQueries({ queryKey: ["characters"] });
          qc.invalidateQueries({ queryKey: ["scenes"] });
          qc.invalidateQueries({ queryKey: ["props"] });
          qc.invalidateQueries({ queryKey: ["episodes"] });
          qc.invalidateQueries({ queryKey: ["shots"] });
          break;
        case "script.failed":
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
