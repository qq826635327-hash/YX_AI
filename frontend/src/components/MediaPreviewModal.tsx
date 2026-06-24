/**
 * 媒体预览弹窗：图片/视频全屏预览，支持缩放、拖拽、左右切换、预览内删除。
 *
 * 行为约定：
 * - items 为同类型素材列表（图片只切图片，视频只切视频）
 * - 图片：左右键 / 按钮均可切换
 * - 视频：键盘左右键不拦截（避免与 video controls seek 冲突），仅按钮切换
 * - 删除：停在原位显示下一张；删的是最后一张则回退；全删完则关闭弹窗
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { X, ZoomIn, ZoomOut, RotateCcw, Trash2, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useConfirm } from "@/components/ConfirmDialog";

export interface MediaItem {
  id: string;
  url: string;
  isVideo?: boolean;
  name?: string;
}

interface MediaPreviewModalProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** 同类型素材列表。列表懒加载未回来时可为空，此时用 fallbackUrl 兜底 */
  items: MediaItem[];
  /** 打开时定位到哪张（by id）。找不到则取第一张 */
  initialId?: string;
  /** 标题（弹窗左上角） */
  title?: string;
  /** 删除回调。返回 Promise 时按钮显示 loading */
  onDelete?: (id: string) => Promise<void> | void;
}

/** 缩放级别列表 */
const ZOOM_LEVELS = [0.5, 0.75, 1, 1.5, 2, 3];
const DEFAULT_ZOOM_INDEX = 2; // 1x

export default function MediaPreviewModal({
  open,
  onOpenChange,
  items,
  initialId,
  title,
  onDelete,
}: MediaPreviewModalProps) {
  const confirm = useConfirm();
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, ox: 0, oy: 0 });

  // 当前索引（items 刷新后通过 effect 重算）
  const [currentIndex, setCurrentIndex] = useState(0);
  const [deleting, setDeleting] = useState(false);

  const zoom = ZOOM_LEVELS[zoomIndex];

  // ---------- 索引管理 ----------
  // 打开或 initialId 变化时定位
  useEffect(() => {
    if (!open) return;
    if (items.length === 0) return; // 列表未回来，保持 0
    const idx = initialId ? items.findIndex((it) => it.id === initialId) : -1;
    setCurrentIndex(idx >= 0 ? idx : 0);
  }, [open, initialId, items]);

  // 列表刷新后（如删除后）重算 index
  useEffect(() => {
    if (!open) return;
    if (items.length === 0) {
      // 全删完 → 关闭弹窗
      onOpenChange(false);
      return;
    }
    if (currentIndex >= items.length) {
      // 删的是最后一张 → 回退到新的最后一张
      setCurrentIndex(items.length - 1);
    }
    // 否则保持 currentIndex 不变，自然显示下一张
  }, [items, open, currentIndex, onOpenChange]);

  // ---------- 视图重置 ----------
  const resetView = useCallback(() => {
    setZoomIndex(DEFAULT_ZOOM_INDEX);
    setOffset({ x: 0, y: 0 });
  }, []);

  const goPrev = useCallback(() => {
    if (items.length <= 1) return;
    setCurrentIndex((i) => (i > 0 ? i - 1 : items.length - 1));
    resetView();
  }, [items.length, resetView]);

  const goNext = useCallback(() => {
    if (items.length <= 1) return;
    setCurrentIndex((i) => (i < items.length - 1 ? i + 1 : 0));
    resetView();
  }, [items.length, resetView]);

  // ---------- 缩放 ----------
  const handleZoomIn = useCallback(() => {
    setZoomIndex((i) => Math.min(i + 1, ZOOM_LEVELS.length - 1));
  }, []);
  const handleZoomOut = useCallback(() => {
    setZoomIndex((i) => Math.max(i - 1, 0));
  }, []);

  // ---------- 拖拽 ----------
  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (zoom <= 1) return;
      setIsDragging(true);
      dragStart.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [zoom, offset],
  );
  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging) return;
      const dx = e.clientX - dragStart.current.x;
      const dy = e.clientY - dragStart.current.y;
      setOffset({ x: dragStart.current.ox + dx, y: dragStart.current.oy + dy });
    },
    [isDragging],
  );
  const handlePointerUp = useCallback(() => setIsDragging(false), []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      setZoomIndex((i) => Math.min(i + 1, ZOOM_LEVELS.length - 1));
    } else {
      setZoomIndex((i) => Math.max(i - 1, 0));
    }
  }, []);

  // ---------- 键盘监听（视频焦点时不拦截左右键）----------
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      const active = document.activeElement;
      const isVideoFocused = active?.tagName === "VIDEO";
      if (e.key === "ArrowLeft" && !isVideoFocused) {
        e.preventDefault();
        goPrev();
      }
      if (e.key === "ArrowRight" && !isVideoFocused) {
        e.preventDefault();
        goNext();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, goPrev, goNext]);

  // ---------- 删除 ----------
  const handleDelete = useCallback(async () => {
    const current = items[currentIndex];
    if (!current || !onDelete || deleting) return;
    if (!(await confirm({ title: "确认删除此图片？", variant: "destructive" }))) return;
    setDeleting(true);
    try {
      await onDelete(current.id);
      // 父组件会 invalidate 列表 → items 刷新 → effect 重算 index
    } catch (e) {
      console.error("删除失败:", e);
    } finally {
      setDeleting(false);
    }
  }, [items, currentIndex, onDelete, deleting]);

  // ---------- 打开/关闭 ----------
  const handleOpenChange = useCallback(
    (v: boolean) => {
      if (v) resetView();
      onOpenChange(v);
    },
    [onOpenChange, resetView],
  );

  // ---------- 当前显示项 ----------
  const hasItems = items.length > 0;
  const current = hasItems ? items[Math.min(currentIndex, items.length - 1)] : undefined;
  const src = current?.url || "";
  const isVideo = current?.isVideo || false;
  const showNav = hasItems && items.length > 1;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex h-[90vh] w-[90vw] max-w-none flex-col gap-0 overflow-hidden border-border/50 bg-black/95 p-0"
        hideCloseButton
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {/* 顶部工具栏 */}
        <div className="flex items-center justify-between border-b border-white/10 bg-black/80 px-4 py-2">
          <div className="flex items-center gap-3">
            {title && <span className="text-sm font-medium text-white/80">{title}</span>}
            {isVideo && (
              <span className="rounded bg-white/10 px-1.5 py-0.5 text-xs text-white/60">视频</span>
            )}
            {hasItems && (
              <span className="text-xs text-white/50">
                {currentIndex + 1} / {items.length}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8 text-white/70 hover:text-white hover:bg-white/10" onClick={handleZoomOut} disabled={zoomIndex <= 0}>
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="min-w-[3rem] text-center text-xs text-white/60">{Math.round(zoom * 100)}%</span>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-white/70 hover:text-white hover:bg-white/10" onClick={handleZoomIn} disabled={zoomIndex >= ZOOM_LEVELS.length - 1}>
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-white/70 hover:text-white hover:bg-white/10" onClick={resetView}>
              <RotateCcw className="h-4 w-4" />
            </Button>
            {onDelete && (
              <>
                <div className="mx-1 h-4 w-px bg-white/20" />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/20"
                  onClick={handleDelete}
                  disabled={deleting || !current}
                  title="删除当前图片"
                >
                  {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </Button>
              </>
            )}
            <div className="mx-1 h-4 w-px bg-white/20" />
            <Button variant="ghost" size="icon" className="h-8 w-8 text-white/70 hover:text-white hover:bg-white/10" onClick={() => handleOpenChange(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* 内容区 */}
        <div
          className="relative flex flex-1 items-center justify-center overflow-hidden"
          onWheel={handleWheel}
        >
          {/* 左箭头 */}
          {showNav && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute left-2 top-1/2 z-10 h-10 w-10 -translate-y-1/2 rounded-full bg-black/40 text-white hover:bg-black/60"
              onClick={(e) => { e.stopPropagation(); goPrev(); }}
            >
              <ChevronLeft className="h-6 w-6" />
            </Button>
          )}

          {src ? (
            isVideo ? (
              <video
                src={src}
                className="max-h-full max-w-full object-contain"
                controls
                autoPlay
                style={{ transform: `scale(${zoom}) translate(${offset.x / zoom}px, ${offset.y / zoom}px)` }}
              />
            ) : (
              <img
                src={src}
                alt={current?.name || title || "预览"}
                className={cn("max-h-full max-w-full object-contain transition-transform", zoom > 1 && "cursor-grab", isDragging && "cursor-grabbing")}
                style={{ transform: `scale(${zoom}) translate(${offset.x / zoom}px, ${offset.y / zoom}px)` }}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
                draggable={false}
              />
            )
          ) : (
            <div className="flex items-center justify-center text-white/40">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              <span className="text-sm">加载中...</span>
            </div>
          )}

          {/* 右箭头 */}
          {showNav && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 top-1/2 z-10 h-10 w-10 -translate-y-1/2 rounded-full bg-black/40 text-white hover:bg-black/60"
              onClick={(e) => { e.stopPropagation(); goNext(); }}
            >
              <ChevronRight className="h-6 w-6" />
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
