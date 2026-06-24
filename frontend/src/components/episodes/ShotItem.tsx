/** 分镜卡片组件：展示单个分镜的信息、帧素材及关联引用。 */

import { memo, useCallback } from "react";
import { GripVertical, Trash2, Image as ImageIcon, Video } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Shot } from "@/types";
import FrameBlock from "./FrameBlock";
import ShotReferenceInline from "./ShotReferences";

export default memo(function ShotItem({
  shot,
  projectId,
  onUpdate,
  onGenerate,
  onDelete,
  showDragHandle,
}: {
  shot: Shot;
  projectId: string;
  /** 稳定引用：传入 shot.id + payload */
  onUpdate: (id: string, payload: Partial<Shot>) => void;
  /** 稳定引用：传入 shot.id + targetType + prompt */
  onGenerate: (id: string, targetType: "shot_first_frame" | "shot_last_frame" | "shot_video", prompt?: string) => void;
  /** 稳定引用：传入 shot.id */
  onDelete: (id: string) => void;
  showDragHandle?: boolean;
}) {
  // 内部用 useCallback 稳定化传给 FrameBlock 的回调，让 FrameBlock 的 memo 真正生效
  const handleFirstFrameUpdate = useCallback(
    (v: string) => onUpdate(shot.id, { first_frame_prompt: v }),
    [onUpdate, shot.id],
  );
  const handleLastFrameUpdate = useCallback(
    (v: string) => onUpdate(shot.id, { last_frame_prompt: v }),
    [onUpdate, shot.id],
  );
  const handleVideoUpdate = useCallback(
    (v: string) => onUpdate(shot.id, { video_prompt: v }),
    [onUpdate, shot.id],
  );

  const handleFirstFrameGenerate = useCallback(
    () => onGenerate(shot.id, "shot_first_frame", shot.first_frame_prompt || undefined),
    [onGenerate, shot.id, shot.first_frame_prompt],
  );
  const handleLastFrameGenerate = useCallback(
    () => onGenerate(shot.id, "shot_last_frame", shot.last_frame_prompt || undefined),
    [onGenerate, shot.id, shot.last_frame_prompt],
  );
  const handleVideoGenerate = useCallback(
    () => onGenerate(shot.id, "shot_video", shot.video_prompt || undefined),
    [onGenerate, shot.id, shot.video_prompt],
  );

  return (
    <div className="rounded-xl border border-border/60 bg-card p-4 transition-shadow duration-200 hover:shadow-md hover:shadow-primary/5">
      {/* 标题行：拖拽手柄 + 分镜号 + 摘要 + 关联引用 + 删除按钮 */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {showDragHandle && (
            <div
              className="cursor-grab text-muted-foreground hover:text-foreground active:cursor-grabbing"
              onMouseDown={(e) => e.stopPropagation()}
            >
              <GripVertical className="h-4 w-4" />
            </div>
          )}
          <Badge variant="outline" className="shrink-0">分镜 {String(shot.shot_no).padStart(2, "0")}</Badge>
          {shot.summary && <span className="truncate text-sm text-muted-foreground">{shot.summary}</span>}
          {/* 关联引用内联到标题行 */}
          <ShotReferenceInline shotId={shot.id} projectId={projectId} />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0 hover:text-destructive"
          onClick={() => onDelete(shot.id)}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {/* 首帧 */}
        <FrameBlock
          title="首帧"
          icon={ImageIcon}
          prompt={shot.first_frame_prompt || ""}
          assetId={shot.first_frame_asset_id}
          status={shot.first_frame_status}
          shotId={shot.id}
          projectId={projectId}
          frameType="first_frame"
          onPromptChange={handleFirstFrameUpdate}
          onGenerate={handleFirstFrameGenerate}
        />
        {/* 尾帧 */}
        <FrameBlock
          title="尾帧"
          icon={ImageIcon}
          prompt={shot.last_frame_prompt || ""}
          assetId={shot.last_frame_asset_id}
          status={shot.last_frame_status}
          hint={!shot.first_frame_asset_id ? "需先生成首帧" : undefined}
          shotId={shot.id}
          projectId={projectId}
          frameType="last_frame"
          onPromptChange={handleLastFrameUpdate}
          onGenerate={handleLastFrameGenerate}
        />
        {/* 视频 */}
        <FrameBlock
          title="视频"
          icon={Video}
          prompt={shot.video_prompt || ""}
          assetId={shot.video_asset_id}
          status={shot.video_status}
          isVideo
          hint={!shot.first_frame_asset_id ? "需先生成首帧" : undefined}
          shotId={shot.id}
          projectId={projectId}
          frameType="video"
          onPromptChange={handleVideoUpdate}
          onGenerate={handleVideoGenerate}
        />
      </div>
    </div>
  );
});
