/** 通用素材画廊组件：用于角色/场景/道具详情页的图片展示。 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Star, Trash2, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { ImageLightbox } from "@/components/ImageLightbox";
import { GenerateDialog } from "@/components/GenerateDialog";
import { cn } from "@/lib/utils";
import type { Asset, GenerationTask, TargetType } from "@/types";
import { useQueryClient } from "@tanstack/react-query";
import { assetsApi } from "@/api/assets";
import { toast } from "@/stores/ui";

interface AssetGalleryProps {
  // 数据
  imageAssets: Asset[];
  activeTasks: GenerationTask[];
  failedTasks: GenerationTask[];
  imageAssetId?: string | null;
  entityName: string;
  entityType: TargetType;
  entityId: string;
  projectId: string;

  // 回调
  onSetPrimary: (assetId: string) => void;
  onDelete: (assetId: string) => void;
  onGenerating: () => void;

  // Lightbox
  lightboxImages: { id: string; url: string; name: string }[];
  lightboxOpen: boolean;
  lightboxIndex: number;
  onLightboxOpenChange: (open: boolean) => void;
  onLightboxIndexChange: (idx: number) => void;

  // 生成对话框
  generateOpen: boolean;
  onGenerateOpenChange: (open: boolean) => void;
  defaultPrompt?: string;
}

export function AssetGallery({
  imageAssets,
  activeTasks,
  failedTasks,
  imageAssetId,
  entityName,
  entityType,
  entityId,
  projectId,
  onSetPrimary,
  onDelete,
  onGenerating,
  lightboxImages,
  lightboxOpen,
  lightboxIndex,
  onLightboxOpenChange,
  onLightboxIndexChange,
  generateOpen,
  onGenerateOpenChange,
  defaultPrompt,
}: AssetGalleryProps) {
  const [syncing, setSyncing] = useState(false);
  const queryClient = useQueryClient();
  const hasImages = imageAssets.length > 0 || activeTasks.length > 0 || failedTasks.length > 0;

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await assetsApi.sync(projectId);
      const parts: string[] = [];
      if (result.cleaned > 0) parts.push(`清理 ${result.cleaned} 条无效记录`);
      if (result.discovered > 0) parts.push(`发现 ${result.discovered} 个新素材`);
      if (parts.length > 0) {
        toast.success(`同步完成：${parts.join("，")}`);
      } else {
        toast.info("同步完成：素材已是最新");
      }
      // 刷新所有涉及该项目的素材查询
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["characters"] });
      queryClient.invalidateQueries({ queryKey: ["scenes"] });
      queryClient.invalidateQueries({ queryKey: ["props"] });
      queryClient.invalidateQueries({ queryKey: ["shots"] });
    } catch (e: any) {
      toast.error(`同步失败：${e.message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="mb-8">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-lg font-semibold">
          生成图片 ({imageAssets.length})
          {activeTasks.length > 0 && (
            <span className="ml-2 text-sm font-normal text-primary">
              · {activeTasks.length} 个任务进行中
            </span>
          )}
        </h2>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto gap-1 text-muted-foreground hover:text-foreground"
          onClick={handleSync}
          disabled={syncing}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", syncing && "animate-spin")} />
          同步
        </Button>
      </div>

      {!hasImages ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
          <p className="mb-2">暂无生成图片</p>
          <Button variant="outline" size="sm" onClick={() => onGenerateOpenChange(true)}>
            立即生成
          </Button>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {/* 已有图片 */}
          {imageAssets.map((asset, idx) => (
            <Card
              key={asset.id}
              className={cn(
                "group relative overflow-hidden",
                imageAssetId === asset.id && "ring-2 ring-primary"
              )}
            >
              <div
                className="aspect-square cursor-pointer overflow-hidden bg-muted"
                onClick={() => { onLightboxIndexChange(idx); onLightboxOpenChange(true); }}
              >
                <img
                  src={`/api/assets/${asset.id}/file`}
                  alt={asset.file_name || "生成图片"}
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
              </div>

              {/* 主图标记 */}
              {imageAssetId === asset.id && (
                <Badge className="absolute right-1 top-1 bg-primary/90 text-primary-foreground">
                  <Star className="mr-1 h-3 w-3 fill-current" />
                  主图
                </Badge>
              )}

              {/* 设为主图按钮 */}
              {imageAssetId !== asset.id && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1 h-7 w-7 bg-black/50 text-white opacity-0 transition-opacity hover:bg-primary/80 hover:text-white group-hover:opacity-100"
                  onClick={(e: React.MouseEvent) => { e.stopPropagation(); onSetPrimary(asset.id); }}
                  title="设为主图"
                >
                  <Star className="h-3.5 w-3.5" />
                </Button>
              )}

              {/* 删除按钮 */}
              <Button
                variant="ghost"
                size="icon"
                className="absolute left-1 top-1 h-7 w-7 bg-black/50 text-white opacity-0 transition-opacity hover:bg-destructive hover:text-white group-hover:opacity-100"
                onClick={(e: React.MouseEvent) => { e.stopPropagation(); onDelete(asset.id); }}
                title="删除图片"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </Card>
          ))}

          {/* 进行中任务占位符 */}
          {activeTasks.map((task) => (
            <Card key={task.id} className="relative overflow-hidden">
              <div className="flex aspect-square flex-col items-center justify-center gap-3 bg-muted/50">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <div className="px-2 text-center">
                  <p className="text-xs font-medium text-muted-foreground">
                    {task.progress > 0 ? `${task.progress}%` : "等待中..."}
                  </p>
                  <p className="mt-1 text-[10px] text-muted-foreground/70">
                    {task.status === "running" ? "正在生成" : "排队中"}
                  </p>
                </div>
              </div>
              <div
                className="absolute bottom-0 left-0 h-1 bg-primary transition-all duration-500"
                style={{ width: `${task.progress || 0}%` }}
              />
            </Card>
          ))}

          {/* 失败任务占位符 */}
          {failedTasks.slice(0, 3).map((task) => (
            <Card key={task.id} className="relative overflow-hidden">
              <div className="flex aspect-square flex-col items-center justify-center gap-2 bg-destructive/5">
                <AlertCircle className="h-8 w-8 text-destructive/60" />
                <div className="px-2 text-center">
                  <p className="text-xs font-medium text-destructive">生成失败</p>
                  {task.error_message && (
                    <p className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">
                      {task.error_message}
                    </p>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Lightbox */}
      <ImageLightbox
        images={lightboxImages}
        initialIndex={lightboxIndex}
        open={lightboxOpen}
        onOpenChange={onLightboxOpenChange}
      />

      {/* 生成对话框 */}
      <GenerateDialog
        open={generateOpen}
        onOpenChange={onGenerateOpenChange}
        projectId={projectId}
        targets={[
          {
            target_type: entityType,
            target_id: entityId,
            name: entityName,
            prompt: defaultPrompt || entityName,
          },
        ]}
        defaultPrompt={defaultPrompt || entityName}
        onSuccess={onGenerating}
      />
    </div>
  );
}
