/** 通用 Hook：角色/场景/道具 的素材管理逻辑（上传、删除、设主图、轮询）。 */

import { useState, useCallback, useEffect, useRef } from "react";
import { usePendingTasks, useDeleteAsset } from "./useApi";
import { useAssets } from "./useBusiness";
import { assetsApi } from "@/api/assets";
import { toast } from "@/stores/ui";
import { useConfirm } from "@/components/ConfirmDialog";
import type { Asset, GenerationTask } from "@/types";

interface UseAssetDetailOptions {
  projectId: string;
  entityType: "character" | "scene" | "prop";   // 实体类型
  entityId: string;                               // 实体 ID
  imageAssetId?: string | null;                   // 当前主图 ID（用于设主图回调）
  onSetPrimary: (assetId: string) => void;       // 设主图的回调
  onRefetchEntity: () => void;                    // 刷新实体数据的回调
}

export function useAssetDetail({
  projectId,
  entityType,
  entityId,
  imageAssetId,
  onSetPrimary,
  onRefetchEntity,
}: UseAssetDetailOptions) {
  const confirm = useConfirm();

  // ---------- 素材列表 ----------
  const {
    data: assets,
    isLoading: assetsLoading,
    refetch: refetchAssets,
  } = useAssets(projectId, entityType, entityId);

  const imageAssets: Asset[] = (assets || []).filter((a: Asset) => a.asset_type === "image");
  const videoAssets: Asset[] = (assets || []).filter((a: Asset) => a.asset_type === "video");

  // ---------- 删除 ----------
  const deleteAssetMutation = useDeleteAsset();

  const handleDeleteAsset = useCallback(
    async (assetId: string) => {
      if (!(await confirm({ title: "确认删除这张图片？", variant: "destructive" }))) return;
      deleteAssetMutation.mutate(assetId, {
        onSuccess: () => {
          refetchAssets();
          // 如果删的是主图，清空主图引用
          if (imageAssetId === assetId) {
            onSetPrimary("");
          }
        },
      });
    },
    [imageAssetId, deleteAssetMutation, refetchAssets, onSetPrimary]
  );

  // ---------- 设主图 ----------
  const handleSetPrimary = useCallback(
    (assetId: string) => {
      onSetPrimary(assetId);
    },
    [onSetPrimary]
  );

  // ---------- 上传 ----------
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;

      // 前端文件类型校验
      const allowedExts = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".mp4", ".webm", ".mov"];
      const invalidFiles = Array.from(files).filter(
        (f) => !allowedExts.some((ext) => f.name.toLowerCase().endsWith(ext))
      );
      if (invalidFiles.length > 0) {
        toast.error(`不支持的文件类型: ${invalidFiles.map((f) => f.name).join(", ")}`);
        if (fileInputRef.current) fileInputRef.current.value = "";
        return;
      }

      // 前端文件大小校验（200MB）
      const oversized = Array.from(files).filter((f) => f.size > 200 * 1024 * 1024);
      if (oversized.length > 0) {
        toast.error(`文件过大（超过 200MB）: ${oversized.map((f) => f.name).join(", ")}`);
        if (fileInputRef.current) fileInputRef.current.value = "";
        return;
      }

      setUploading(true);
      try {
        for (const file of Array.from(files)) {
          await assetsApi.uploadNew({
            projectId,
            category: entityType,
            file,
            target_type: entityType,
            target_id: entityId,
          });
        }
        toast.success(`成功上传 ${files.length} 张图片`);
        refetchAssets();
      } catch (err: any) {
        toast.error(err.message || "上传失败");
      } finally {
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [projectId, entityType, entityId, refetchAssets]
  );

  // ---------- 任务轮询 ----------
  const { data: pendingTasksData } = usePendingTasks(projectId, entityType, entityId);
  const allTasks: GenerationTask[] = pendingTasksData?.items || [];
  const activeTasks = allTasks.filter(
    (t: GenerationTask) => t.status === "pending" || t.status === "running" || t.status === "queued"
  );
  const failedTasks = allTasks.filter((t: GenerationTask) => t.status === "failed");

  // 任务完成时刷新素材列表
  const prevActiveCount = useRef(0);
  useEffect(() => {
    if (prevActiveCount.current > 0 && activeTasks.length === 0) {
      refetchAssets();
      onRefetchEntity();
    }
    prevActiveCount.current = activeTasks.length;
  }, [activeTasks.length, refetchAssets, onRefetchEntity]);

  // ---------- Lightbox ----------
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const lightboxImages = imageAssets.map((a: Asset) => ({
    id: a.id,
    url: `/api/assets/${a.id}/file`,
    name: a.file_name || `图片 ${a.id.slice(0, 8)}`,
  }));

  return {
    // 素材数据
    assets,
    assetsLoading,
    imageAssets,
    videoAssets,
    refetchAssets,

    // 删除
    handleDeleteAsset,

    // 主图
    handleSetPrimary,
    imageAssetId,

    // 上传
    fileInputRef,
    uploading,
    handleFileSelect,

    // 任务
    activeTasks,
    failedTasks,

    // Lightbox
    lightboxOpen,
    setLightboxOpen,
    lightboxIndex,
    setLightboxIndex,
    lightboxImages,
  };
}
