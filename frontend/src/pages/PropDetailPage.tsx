/** 道具详情页。 */

import { useState, useCallback, useEffect } from "react";
import { useParams } from "react-router-dom";
import { RefreshCw, Upload } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { PageContainer, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { AssetGallery } from "@/components/AssetGallery";
import { useProp, useUpdateProp } from "@/hooks/useBusiness";
import { useAssetDetail } from "@/hooks/useAssetDetail";
import { useUiStore } from "@/stores/ui";
import type { Prop } from "@/types";

export function PropDetailPage() {
  const { projectId, propId } = useParams();
  const qc = useQueryClient();
  const setSelectedEntity = useUiStore((s) => s.setSelectedEntity);

  const [editing, setEditing] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);

  // 加载到详情页时同步设置右侧属性面板
  useEffect(() => {
    if (projectId && propId) {
      setSelectedEntity({ type: "prop", id: propId, projectId });
    }
  }, [projectId, propId, setSelectedEntity]);

  const { data: prop, isLoading: propLoading, refetch: refetchProp } =
    useProp(projectId!, propId!);
  const updateMutation = useUpdateProp(projectId!);

  // 设为主图回调
  const handleSetPrimary = useCallback(
    (assetId: string) => {
      updateMutation.mutate(
        { id: propId!, payload: { image_asset_id: assetId || null } },
        { onSuccess: () => { refetchProp(); qc.invalidateQueries({ queryKey: ["props"] }); } }
      );
    },
    [propId, updateMutation, refetchProp, qc]
  );

  // 通用素材管理 Hook
  const {
    uploading,
    fileInputRef,
    handleFileSelect,
    handleDeleteAsset,
    activeTasks,
    failedTasks,
    imageAssets,
    videoAssets,
    lightboxOpen,
    setLightboxOpen,
    lightboxIndex,
    setLightboxIndex,
    lightboxImages,
  } = useAssetDetail({
    projectId: projectId!,
    entityType: "prop",
    entityId: propId!,
    imageAssetId: prop?.image_asset_id,
    onSetPrimary: handleSetPrimary,
    onRefetchEntity: refetchProp,
  });

  if (propLoading || !prop) return <LoadingState />;

  return (
    <>
      <PageContainer
        title={prop.name}
        description=""
        showBack
        backTo={`/projects/${projectId}/props`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
              <Upload className="mr-1 h-3.5 w-3.5" />
              {uploading ? "上传中..." : "上传图片"}
            </Button>
            <Button size="sm" onClick={() => setGenerateOpen(true)}>
              <RefreshCw className="mr-1 h-3.5 w-3.5" />生成图片
            </Button>
          </div>
        }
      >
        {/* 图片画廊（通用组件） */}
        <AssetGallery
          imageAssets={imageAssets}
          activeTasks={activeTasks}
          failedTasks={failedTasks}
          imageAssetId={prop.image_asset_id}
          entityName={prop.name}
          entityType="prop"
          entityId={propId!}
          projectId={projectId!}
          onSetPrimary={handleSetPrimary}
          onDelete={handleDeleteAsset}
          onGenerating={() => {
            qc.invalidateQueries({ queryKey: ["pending-tasks", projectId, "prop", propId] });
          }}
          lightboxImages={lightboxImages}
          lightboxOpen={lightboxOpen}
          lightboxIndex={lightboxIndex}
          onLightboxOpenChange={setLightboxOpen}
          onLightboxIndexChange={setLightboxIndex}
          generateOpen={generateOpen}
          onGenerateOpenChange={setGenerateOpen}
          defaultPrompt={prop.settings || prop.description || prop.name}
        />

        {/* 视频列表 */}
        {videoAssets.length > 0 && (
          <div className="mb-8">
            <h2 className="mb-3 text-lg font-semibold">生成视频 ({videoAssets.length})</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {videoAssets.map((asset) => (
                <Card key={asset.id} className="overflow-hidden">
                  <video src={`/api/assets/${asset.id}/file`} className="aspect-video w-full object-cover" controls />
                </Card>
              ))}
            </div>
          </div>
        )}
      </PageContainer>

      {/* 隐藏的文件上传 input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={handleFileSelect}
      />

      <PropEditDialog open={editing} prop={prop}
        onOpenChange={setEditing} projectId={projectId!} onSaved={() => refetchProp()} />
    </>
  );
}

/** 道具编辑对话框（保持不变）。 */
function PropEditDialog({ open, prop, onOpenChange, projectId, onSaved }: {
  open: boolean;
  prop: Prop;
  onOpenChange: (v: boolean) => void;
  projectId: string;
  onSaved?: () => void;
}) {
  const [name, setName] = useState(prop?.name || "");
  const [description, setDescription] = useState(prop?.description || "");
  const [settings, setSettings] = useState(prop?.settings || "");
  const updateMutation = useUpdateProp(projectId);

  useEffect(() => {
    if (open && prop) {
      setName(prop.name || "");
      setDescription(prop.description || "");
      setSettings(prop.settings || "");
    }
  }, [open, prop]);

  const handleSave = async () => {
    await updateMutation.mutateAsync({ id: prop!.id, payload: { name: name.trim(), description, settings } });
    onOpenChange(false);
    onSaved?.();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑道具</DialogTitle>
          <DialogDescription>修改道具信息</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>名称 *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="道具名称" />
          </div>
          <div className="space-y-2">
            <Label>描述</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </div>
          <div className="space-y-2">
            <Label>设定（用于生成）</Label>
            <Textarea value={settings} onChange={(e) => setSettings(e.target.value)} rows={3} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!name.trim()} onClick={handleSave}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
