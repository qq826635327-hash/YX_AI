/** 角色/场景/道具通用卡片组件 —— 大图展示，无描述。 */

import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pencil, RefreshCw, Trash2, Image as ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EntityCardProps {
  /** 图片 Asset ID（支持 char/image_asset_id、scene/image_asset_id、prop/image_asset_id） */
  imageAssetId: string | null | undefined;
  /** 名称 */
  name: string;
  /** 右上角徽章文字（如"主角"） */
  badge?: string;
  /** 是否多选模式 */
  selectMode?: boolean;
  /** 是否选中 */
  selected?: boolean;
  /** 点击卡片（非选择模式 → 跳转详情） */
  onClick?: () => void;
  /** 切换选中 */
  onToggleSelect?: () => void;
  /** 编辑回调 */
  onEdit?: () => void;
  /** 删除回调 */
  onDelete?: () => void;
  /** 生成回调 */
  onGenerate?: () => void;
}

export function EntityCard({
  imageAssetId,
  name,
  badge,
  selectMode = false,
  selected = false,
  onClick,
  onToggleSelect,
  onEdit,
  onDelete,
  onGenerate,
}: EntityCardProps) {
  const imageUrl = imageAssetId
    ? `/api/assets/${imageAssetId}/file`
    : null;

  const hasActions = !selectMode && (onEdit || onDelete || onGenerate);

  return (
    <Card
      className={cn(
        "group relative overflow-hidden",
        !selectMode && "cursor-pointer hover:shadow-lg transition-shadow duration-200",
        selected && "ring-2 ring-primary"
      )}
      onClick={selectMode ? onToggleSelect : onClick}
    >
      {/* 多选模式：左上角 Checkbox */}
      {selectMode && (
        <div className="absolute left-2 top-2 z-20">
          <Checkbox
            checked={selected}
            onCheckedChange={() => onToggleSelect?.()}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* 大图区域：1:1 方格 */}
      <div className="relative aspect-square bg-muted/40">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={name}
            className="h-full w-full object-contain p-0"
            draggable={false}
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <ImageIcon className="h-16 w-16 text-muted-foreground/30" />
            {onGenerate && !selectMode && (
              <Button
                variant="secondary"
                size="sm"
                onClick={(e) => { e.stopPropagation(); onGenerate(); }}
              >
                <RefreshCw className="mr-1 h-3.5 w-3.5" />
                生成图片
              </Button>
            )}
          </div>
        )}

        {/* Hover 操作遮罩（仅在已有图时显示，编辑/重新生成/删除） */}
        {hasActions && imageUrl && (
          <div
            className={cn(
              "absolute inset-0 z-10 flex items-center justify-center gap-2",
              "bg-black/0 transition-colors duration-200 pointer-events-none",
              "group-hover:bg-black/40"
            )}
          >
            <div className="flex items-center gap-2 opacity-0 transition-opacity duration-200 group-hover:opacity-100 pointer-events-none">
              {onEdit && (
                <Button
                  variant="secondary"
                  size="icon"
                  className="h-8 w-8 bg-white/80 hover:bg-white pointer-events-auto"
                  onClick={(e) => { e.stopPropagation(); onEdit(); }}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
              )}
              {onGenerate && (
                <Button
                  variant="secondary"
                  size="icon"
                  className="h-8 w-8 bg-white/80 hover:bg-white pointer-events-auto"
                  onClick={(e) => { e.stopPropagation(); onGenerate(); }}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </Button>
              )}
              {onDelete && (
                <Button
                  variant="destructive"
                  size="icon"
                  className="h-8 w-8 pointer-events-auto"
                  onClick={(e) => { e.stopPropagation(); onDelete(); }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>
        )}

        {/* 已有图时，右下角也放一个"重新生成"小按钮，常驻可点 */}
        {imageUrl && onGenerate && !selectMode && (
          <div className="absolute bottom-2 right-2 z-10">
            <Button
              variant="secondary"
              size="sm"
              className="h-7 px-2 text-xs bg-white/80 hover:bg-white shadow"
              onClick={(e) => { e.stopPropagation(); onGenerate(); }}
              title="重新生成"
            >
              <RefreshCw className="mr-1 h-3 w-3" />
              重新生成
            </Button>
          </div>
        )}
      </div>

      {/* 名称栏 */}
      <CardContent className="px-3 py-2.5">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium leading-tight">
            {name}
          </span>
          {badge && (
            <Badge variant="secondary" className="shrink-0 text-[10px] px-1.5 py-0 leading-5">
              {badge}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
