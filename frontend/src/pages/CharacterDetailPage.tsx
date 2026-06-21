/** 角色详情页：查看/编辑角色信息，浏览所有生成图片，设置主图。 */

import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Pencil, RefreshCw, Upload, Trash2, ImageIcon } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { PageContainer, LoadingState, EmptyState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { AssetGallery } from "@/components/AssetGallery";
import { useCharacter, useUpdateCharacter, useDeleteCharacter } from "@/hooks/useBusiness";
import { useAssetDetail } from "@/hooks/useAssetDetail";
import { charTypeMap } from "@/lib/utils";
import type { Character } from "@/types";

export function CharacterDetailPage() {
  const { projectId, characterId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);

  const { data: character, isLoading: charLoading, isError: charError, refetch: refetchChar } =
    useCharacter(projectId!, characterId!);
  const updateMutation = useUpdateCharacter(projectId!);
  const deleteMutation = useDeleteCharacter(projectId!);

  // 设为主图的回调（传给 useAssetDetail）
  const handleSetPrimary = useCallback(
    (assetId: string) => {
      updateMutation.mutate(
        { id: characterId!, payload: { image_asset_id: assetId } },
        {
          onSuccess: () => {
            refetchChar();
            qc.invalidateQueries({ queryKey: ["characters"] });
          },
        }
      );
    },
    [characterId, updateMutation, refetchChar, qc]
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
    entityType: "character",
    entityId: characterId!,
    imageAssetId: character?.image_asset_id,
    onSetPrimary: handleSetPrimary,
    onRefetchEntity: refetchChar,
  });

  const handleDelete = () => {
    if (!confirm(`确认删除角色「${character?.name}」？`)) return;
    deleteMutation.mutate(characterId!, {
      onSuccess: () => navigate(`/projects/${projectId}/characters`),
    });
  };

  if (charLoading) return <LoadingState />;
  if (charError || !character) return <EmptyState title="角色不存在或加载失败" />;

  return (
    <>
      <PageContainer
        title=""
        description=""
        showBack
        backTo={`/projects/${projectId}/characters`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil className="mr-1 h-3.5 w-3.5" />
              编辑
            </Button>
            <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
              <Upload className="mr-1 h-3.5 w-3.5" />
              {uploading ? "上传中..." : "上传图片"}
            </Button>
            <Button size="sm" onClick={() => setGenerateOpen(true)}>
              <RefreshCw className="mr-1 h-3.5 w-3.5" />
              生成图片
            </Button>
          </div>
        }
      >
        {/* 角色信息 */}
        <div className="mb-8 grid gap-6 lg:grid-cols-3">
          <Card className="overflow-hidden">
            <div className="flex aspect-square items-center justify-center bg-muted">
              {character.image_asset_id ? (
                <img
                  src={`/api/assets/${character.image_asset_id}/file`}
                  alt={character.name}
                  className="h-full w-full object-cover"
                />
              ) : (
                <ImageIcon className="h-16 w-16 text-muted-foreground/40" />
              )}
            </div>
          </Card>

          <div className="space-y-4 lg:col-span-2">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{character.name}</h1>
              <Badge variant="secondary">{charTypeMap[character.char_type]}</Badge>
            </div>
            {character.description && (
              <div>
                <p className="mb-1 text-sm font-medium text-muted-foreground">描述</p>
                <p className="whitespace-pre-wrap text-sm">{character.description}</p>
              </div>
            )}
            {character.settings && (
              <div>
                <p className="mb-1 text-sm font-medium text-muted-foreground">生成设定</p>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">{character.settings}</p>
              </div>
            )}
            <Button variant="outline" size="sm" onClick={handleDelete}
              className="text-destructive hover:bg-destructive/10">
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              删除角色
            </Button>
          </div>
        </div>

        {/* 图片画廊（通用组件） */}
        <AssetGallery
          imageAssets={imageAssets}
          activeTasks={activeTasks}
          failedTasks={failedTasks}
          imageAssetId={character.image_asset_id}
          entityName={character.name}
          entityType="character"
          entityId={characterId!}
          projectId={projectId!}
          onSetPrimary={handleSetPrimary}
          onDelete={handleDeleteAsset}
          onGenerating={() => {
            qc.invalidateQueries({ queryKey: ["pending-tasks", projectId, "character", characterId] });
          }}
          lightboxImages={lightboxImages}
          lightboxOpen={lightboxOpen}
          lightboxIndex={lightboxIndex}
          onLightboxOpenChange={setLightboxOpen}
          onLightboxIndexChange={setLightboxIndex}
          generateOpen={generateOpen}
          onGenerateOpenChange={setGenerateOpen}
          defaultPrompt={character.settings || character.description || character.name}
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

      <CharacterEditDialog open={editing} character={character}
        onOpenChange={setEditing} projectId={projectId!} onSaved={() => refetchChar()} />
    </>
  );
}

/** 角色编辑对话框（保持不变）。 */
function CharacterEditDialog({
  open, character, onOpenChange, projectId, onSaved,
}: {
  open: boolean;
  character: Character;
  onOpenChange: (v: boolean) => void;
  projectId: string;
  onSaved?: () => void;
}) {
  const [name, setName] = useState(character?.name || "");
  const [charType, setCharType] = useState<"protagonist" | "supporting" | "extra">(character?.char_type || "supporting");
  const [description, setDescription] = useState(character?.description || "");
  const [settings, setSettings] = useState(character?.settings || "");
  const updateMutation = useUpdateCharacter(projectId);

  useEffect(() => {
    if (open && character) {
      setName(character.name || "");
      setCharType(character.char_type || "supporting");
      setDescription(character.description || "");
      setSettings(character.settings || "");
    }
  }, [open, character]);

  const handleSave = async () => {
    await updateMutation.mutateAsync({
      id: character!.id,
      payload: { name: name.trim(), char_type: charType, description, settings },
    });
    onOpenChange(false);
    onSaved?.();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑角色</DialogTitle>
          <DialogDescription>修改角色信息</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>名称 *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="角色名称" />
          </div>
          <div className="space-y-2">
            <Label>分类</Label>
            <Tabs value={charType} onValueChange={(v) => setCharType(v as "protagonist" | "supporting" | "extra")}>
              <TabsList>
                <TabsTrigger value="protagonist">主角</TabsTrigger>
                <TabsTrigger value="supporting">配角</TabsTrigger>
                <TabsTrigger value="extra">群演</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <div className="space-y-2">
            <Label>描述</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="角色背景、性格等" rows={3} />
          </div>
          <div className="space-y-2">
            <Label>设定（用于生成）</Label>
            <Textarea value={settings} onChange={(e) => setSettings(e.target.value)} placeholder="外貌、服装等生成提示词" rows={3} />
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
