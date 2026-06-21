/** 场景详情页。 */

import { useState, useCallback, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Pencil, RefreshCw, Upload, Trash2, Map as MapIcon } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { PageContainer, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { AssetGallery } from "@/components/AssetGallery";
import { useScene, useUpdateScene, useDeleteScene } from "@/hooks/useBusiness";
import { useAssetDetail } from "@/hooks/useAssetDetail";
import type { Scene } from "@/types";

export function SceneDetailPage() {
  const { projectId, sceneId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);

  const { data: scene, isLoading: sceneLoading, refetch: refetchScene } =
    useScene(projectId!, sceneId!);
  const updateMutation = useUpdateScene(projectId!);
  const deleteMutation = useDeleteScene(projectId!);

  // 设为主图回调
  const handleSetPrimary = useCallback(
    (assetId: string) => {
      updateMutation.mutate(
        { id: sceneId!, payload: { image_asset_id: assetId } },
        { onSuccess: () => { refetchScene(); qc.invalidateQueries({ queryKey: ["scenes"] }); } }
      );
    },
    [sceneId, updateMutation, refetchScene, qc]
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
    entityType: "scene",
    entityId: sceneId!,
    imageAssetId: scene?.image_asset_id,
    onSetPrimary: handleSetPrimary,
    onRefetchEntity: refetchScene,
  });

  const handleDelete = () => {
    if (!confirm(`确认删除场景「${scene?.name}」？`)) return;
    deleteMutation.mutate(sceneId!, { onSuccess: () => navigate(`/projects/${projectId}/scenes`) });
  };

  if (sceneLoading || !scene) return <LoadingState />;

  return (
    <>
      <PageContainer
        title=""
        description=""
        showBack
        backTo={`/projects/${projectId}/scenes`}
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
        {/* 场景信息 */}
        <div className="mb-8 grid gap-6 lg:grid-cols-3">
          <Card className="overflow-hidden">
            <div className="flex aspect-square items-center justify-center bg-muted">
              {scene.image_asset_id ? (
                <img src={`/api/assets/${scene.image_asset_id}/file`} alt={scene.name} className="h-full w-full object-cover" />
              ) : (
                <MapIcon className="h-16 w-16 text-muted-foreground/40" />
              )}
            </div>
          </Card>
          <div className="space-y-4 lg:col-span-2">
            <h1 className="text-2xl font-bold">{scene.name}</h1>
            {scene.description && (
              <div>
                <p className="mb-1 text-sm font-medium text-muted-foreground">描述</p>
                <p className="whitespace-pre-wrap text-sm">{scene.description}</p>
              </div>
            )}
            {scene.settings && (
              <div>
                <p className="mb-1 text-sm font-medium text-muted-foreground">生成设定</p>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">{scene.settings}</p>
              </div>
            )}
            <Button variant="outline" size="sm" onClick={handleDelete}
              className="text-destructive hover:bg-destructive/10">
              <Trash2 className="mr-1 h-3.5 w-3.5" />删除场景
            </Button>
          </div>
        </div>

        {/* 图片画廊（通用组件） */}
        <AssetGallery
          imageAssets={imageAssets}
          activeTasks={activeTasks}
          failedTasks={failedTasks}
          imageAssetId={scene.image_asset_id}
          entityName={scene.name}
          entityType="scene"
          entityId={sceneId!}
          projectId={projectId!}
          onSetPrimary={handleSetPrimary}
          onDelete={handleDeleteAsset}
          onGenerating={() => {
            qc.invalidateQueries({ queryKey: ["pending-tasks", projectId, "scene", sceneId] });
          }}
          lightboxImages={lightboxImages}
          lightboxOpen={lightboxOpen}
          lightboxIndex={lightboxIndex}
          onLightboxOpenChange={setLightboxOpen}
          onLightboxIndexChange={setLightboxIndex}
          generateOpen={generateOpen}
          onGenerateOpenChange={setGenerateOpen}
          defaultPrompt={scene.settings || scene.description || scene.name}
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

      <SceneEditDialog open={editing} scene={scene}
        onOpenChange={setEditing} projectId={projectId!} onSaved={() => refetchScene()} />
    </>
  );
}

/** 场景编辑对话框（保持不变）。 */
function SceneEditDialog({ open, scene, onOpenChange, projectId, onSaved }: {
  open: boolean; scene: Scene; onOpenChange: (v: boolean) => void;
  projectId: string; onSaved?: () => void;
}) {
  const [name, setName] = useState(scene?.name || "");
  const [description, setDescription] = useState(scene?.description || "");
  const [settings, setSettings] = useState(scene?.settings || "");
  const updateMutation = useUpdateScene(projectId);
  useEffect(() => { if (open && scene) { setName(scene.name || ""); setDescription(scene.description || ""); setSettings(scene.settings || ""); } }, [open, scene]);
  const handleSave = async () => { await updateMutation.mutateAsync({ id: scene!.id, payload: { name: name.trim(), description, settings } }); onOpenChange(false); onSaved?.(); };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>编辑场景</DialogTitle><DialogDescription>修改场景信息</DialogDescription></DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2"><Label>名称 *</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="场景名称" /></div>
          <div className="space-y-2"><Label>描述</Label><Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} /></div>
          <div className="space-y-2"><Label>设定（用于生成）</Label><Textarea value={settings} onChange={(e) => setSettings(e.target.value)} rows={3} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!name.trim()} onClick={handleSave}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
