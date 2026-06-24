/** 角色/场景/道具通用卡片组件 —— 大图展示，无悬浮按钮。 */

import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Image as ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EntityCardProps {
  /** 图片 Asset ID */
  imageAssetId: string | null | undefined;
  /** 名称 */
  name: string;
  /** 副标题（如性别/年龄） */
  subtitle?: string;
  /** 右上角徽章文字（如"主角"） */
  badge?: string;
  /** 是否多选模式 */
  selectMode?: boolean;
  /** 是否选中 */
  selected?: boolean;
  /** 点击卡片 */
  onClick?: () => void;
  /** 切换选中 */
  onToggleSelect?: () => void;
}

export function EntityCard({
  imageAssetId,
  name,
  subtitle,
  badge,
  selectMode = false,
  selected = false,
  onClick,
  onToggleSelect,
}: EntityCardProps) {
  const imageUrl = imageAssetId
    ? `/api/assets/${imageAssetId}/file`
    : null;

  return (
    <Card
      className={cn(
        "group relative overflow-hidden border-border/60 bg-card transition-[transform,box-shadow] duration-200",
        !selectMode && "cursor-pointer hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/5 hover:ring-1 hover:ring-primary/30",
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
          </div>
        )}
      </div>

      {/* 名称栏 */}
      <CardContent className="px-3 py-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <span className="truncate text-sm font-medium leading-tight">
              {name}
            </span>
            {subtitle && (
              <span className="ml-1.5 text-xs text-muted-foreground">
                {subtitle}
              </span>
            )}
          </div>
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
