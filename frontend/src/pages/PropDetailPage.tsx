/** 道具详情页。 */

import { useState, useCallback, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Pencil, RefreshCw, Upload, Trash2, Package } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { PageContainer, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { AssetGallery } from "@/components/AssetGallery";
import { useProp, useUpdateProp, useDeleteProp } from "@/hooks/useBusiness";
import { useAssetDetail } from "@/hooks/useAssetDetail";
import type { Prop } from "@/types";

export function PropDetailPage() {
  const { projectId, propId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);

  const { data: prop, isLoading: propLoading, refetch: refetchProp } =
    useProp(projectId!, propId!);
  const updateMutation = useUpdateProp(projectId!);
  const deleteMutation = useDeleteProp(projectId!);

  // 设为主图回调
  const handleSetPrimary = useCallback(
    (assetId: string) => {
      updateMutation.mutate(
        { id: propId!, payload: { image_asset_id: assetId } },
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

  const handleDelete = () => {
    if (!confirm(`确认删除道具「${prop?.name}」？`)) return;
    deleteMutation.mutate(propId!, { onSuccess: () => navigate(`/projects/${projectId}/props`) });
  };

  if (propLoading || !prop) return <LoadingState />;

  return (
    <>
      <PageContainer
        title=""
        description=""
        showBack
        backTo={`/projects/${projectId}/props`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil className="mr-1 h-3.5 w-3.5" />编辑
            </Button>
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
        {/* 道具信息 */}
        <div className="mb-8 grid gap-6 lg:grid-cols-3">
          <Card className="overflow-hidden">
            <div className="flex aspect-square items-center justify-center bg-muted">
              {prop.image_asset_id ? (
                <img src={`/api/assets/${prop.image_asset_id}/file`} alt={prop.name} className="h-full w-full object-cover" />
              ) : (
                <Package className="h-16 w-16 text-muted-foreground/40" />
              )}
            </div>
          </Card>

          <div className="space-y-4 lg:col-span-2">
            <h1 className="text-2xl font-bold">{prop.name}</h1>
            {prop.description && (
              <div>
                <p className="mb-1 text-sm font-medium text-muted-foreground">描述</p>
                <p className="whitespace-pre-wrap text-sm">{prop.description}</p>
              </div>
            )}
            {prop.settings && (
              <div>
                <p className="mb-1 text-sm font-medium text-muted-foreground">生成设定</p>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">{prop.settings}</p>
              </div>
            )}
            <Button variant="outline" size="sm" onClick={handleDelete}
              className="text-destructive hover:bg-destructive/10">
              <Trash2 className="mr-1 h-3.5 w-3.5" />删除道具
            </Button>
          </div>
        </div>

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
