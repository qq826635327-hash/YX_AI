/** 帧块组件：展示首帧/尾帧/视频素材及提示词编辑。 */

import { useState, useEffect, memo } from "react";
import {
  Video,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui";
import type { GenStatus } from "@/types";

const genStatusBadge: Record<GenStatus, {
  label: string;
  variant: "secondary" | "warning" | "success" | "destructive" | "default";
}> = {
  none: { label: "未生成", variant: "secondary" },
  pending: { label: "等待中", variant: "default" },
  generating: { label: "生成中", variant: "warning" },
  ready: { label: "已就绪", variant: "success" },
  failed: { label: "失败", variant: "destructive" },
};

export default memo(function FrameBlock({
  title,
  icon: Icon,
  prompt,
  assetId,
  status,
  isVideo,
  hint,
  shotId,
  projectId,
  frameType,
  onPromptChange,
  onGenerate,
}: {
  title: string;
  icon: React.ElementType;
  prompt: string;
  assetId?: string;
  status: GenStatus;
  isVideo?: boolean;
  /** 提示文字，如"需先生成首帧" */
  hint?: string;
  /** 分镜ID，用于右侧面板 */
  shotId?: string;
  /** 项目ID，用于右侧面板 */
  projectId?: string;
  /** 帧类型，用于右侧面板 */
  frameType?: "first_frame" | "last_frame" | "video";
  onPromptChange: (v: string) => void;
  onGenerate: () => void;
}) {
  const badge = genStatusBadge[status];
  const showBadge = status !== "none";
  const setSelectedEntity = useUiStore((s) => s.setSelectedEntity);

  // 本地编辑状态：输入时不触发 API，失焦时才提交
  const [localPrompt, setLocalPrompt] = useState(prompt);
  const [dirty, setDirty] = useState(false);

  // 外部 prompt 变化时同步到本地
  useEffect(() => {
    if (!dirty) {
      setLocalPrompt(prompt);
    }
  }, [prompt, dirty]);

  const handleBlur = () => {
    if (dirty && localPrompt !== prompt) {
      onPromptChange(localPrompt);
    }
    setDirty(false);
  };

  // 点击帧区域：右侧面板展示帧属性
  const handleFrameClick = () => {
    if (shotId && projectId && frameType) {
      setSelectedEntity({
        type: "shot_frame",
        id: `${shotId}_${frameType}`,
        projectId,
        shotId,
        frameType,
      });
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-sm font-medium">
          <Icon className="h-3.5 w-3.5" />
          {title}
        </div>
        {showBadge && <Badge variant={badge.variant} className="text-xs">{badge.label}</Badge>}
      </div>
      <div
        className={cn(
          "group relative flex aspect-video cursor-pointer items-center justify-center overflow-hidden rounded-lg border border-border/60 bg-muted transition-shadow duration-200 hover:ring-1 hover:ring-primary/30"
        )}
        onClick={handleFrameClick}
      >
        {assetId ? (
          <>
            {isVideo ? (
              <video src={`/api/assets/${assetId}/file`} className="h-full w-full object-cover" muted playsInline />
            ) : (
              <img src={`/api/assets/${assetId}/file`} alt={title} className="h-full w-full object-cover" />
            )}
            {/* 有内容时，在左上角显示重新生成按钮 */}
            <Button
              variant="secondary"
              size="sm"
              className="absolute left-1 top-1 h-6 gap-1 px-2 text-xs bg-card/90 text-foreground opacity-0 transition-opacity hover:bg-primary hover:text-primary-foreground group-hover:opacity-100"
              onClick={(e) => { e.stopPropagation(); onGenerate(); }}
            >
              {isVideo ? <Video className="h-2.5 w-2.5" /> : <RefreshCw className="h-2.5 w-2.5" />}
              {isVideo ? "生成视频" : "生成图片"}
            </Button>
          </>
        ) : status === "generating" || status === "pending" ? (
          /* 生成中：显示进度转圈 */
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="h-8 w-8 animate-spin text-primary/60" />
            <span className="text-xs text-muted-foreground">
              {status === "pending" ? "等待中..." : "生成中..."}
            </span>
          </div>
        ) : (
          /* 无内容时，生成按钮替换未生成占位符 */
          <div className="flex flex-col items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 text-xs text-muted-foreground hover:border-primary/50 hover:text-primary"
              onClick={(e) => { e.stopPropagation(); onGenerate(); }}
            >
              {isVideo ? <Video className="h-3 w-3" /> : <RefreshCw className="h-3 w-3" />}
              {isVideo ? "生成视频" : "生成图片"}
            </Button>
            {hint && (
              <span className="text-xs text-amber-500">{hint}</span>
            )}
          </div>
        )}
      </div>
      <Textarea
        value={localPrompt}
        onChange={(e) => { setLocalPrompt(e.target.value); setDirty(true); }}
        onBlur={handleBlur}
        placeholder={`${title}提示词...`}
        rows={2}
        className="text-xs"
      />
    </div>
  );
});
