/** 右侧属性面板：根据全局选中实体展示详情与编辑入口。 */

import { useState, useEffect, useCallback } from "react";
import {
  MousePointer2, User, MapPin, Package, RefreshCw, Trash2, Star, Upload, Image as ImageIcon, Video, Maximize2,
} from "lucide-react";
import { useUiStore, type SelectedEntity } from "@/stores/ui";
import {
  useCharacter, useScene, useProp,
  useUpdateCharacter, useUpdateScene, useUpdateProp,
  useDeleteCharacter, useDeleteScene, useDeleteProp,
  useUpdateShot,
} from "@/hooks/useBusiness";
import { useNavigate } from "react-router-dom";
import { assetsApi } from "@/api/assets";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { assetKeys, charKeys, sceneKeys, propKeys } from "@/hooks/useBusiness";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { charTypeMap } from "@/lib/utils";
import { toast } from "@/stores/ui";
import type { Asset } from "@/types";
import MediaPreviewModal from "@/components/MediaPreviewModal";
import { useConfirm } from "@/components/ConfirmDialog";

export function RightPanel() {
  const selectedEntity = useUiStore((s) => s.selectedEntity);

  return (
    <aside className="flex h-full w-80 flex-shrink-0 flex-col border-l border-border bg-card">
      <div className="flex h-14 items-center border-b border-border px-4">
        <h2 className="text-sm font-semibold">属性面板</h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        {!selectedEntity ? (
          <div className="flex h-full flex-col items-center justify-center p-6 text-center text-muted-foreground">
            <MousePointer2 className="mb-3 h-10 w-10 text-primary/30" />
            <p className="text-sm text-foreground">选择角色、道具、剧集、场景或分镜</p>
            <p className="mt-1 text-xs text-muted-foreground">查看和编辑属性</p>
          </div>
        ) : (
          <EntityPanel entity={selectedEntity} />
        )}
      </div>
    </aside>
  );
}

function EntityPanel({ entity }: { entity: NonNullable<SelectedEntity> }) {
  switch (entity.type) {
    case "character":
      return <CharacterPanel projectId={entity.projectId} id={entity.id} />;
    case "scene":
      return <ScenePanel projectId={entity.projectId} id={entity.id} />;
    case "prop":
      return <PropPanel projectId={entity.projectId} id={entity.id} />;
    case "asset":
      return <AssetPanel projectId={entity.projectId} assetId={entity.id} entityType={entity.entityType} entityId={entity.entityId} imageAssetId={entity.imageAssetId} />;
    case "shot_frame":
      return <ShotFramePanel projectId={entity.projectId} shotId={entity.shotId} frameType={entity.frameType} />;
    default:
      return null;
  }
}

// ── 通用组件 ──────────────────────────────────────────

function PanelSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-border p-4 last:border-b-0">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}

function PanelLoading() {
  return (
    <div className="flex h-40 items-center justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-primary" />
    </div>
  );
}

function PanelEmpty({ title }: { title: string }) {
  return (
    <div className="flex h-40 flex-col items-center justify-center p-6 text-center text-muted-foreground">
      <p className="text-sm">{title}</p>
    </div>
  );
}

/** 可编辑字段：失焦自动保存 */
function EditableField({
  label,
  value,
  onSave,
  multiline = false,
  rows = 3,
}: {
  label: string;
  value: string;
  onSave: (v: string) => void;
  multiline?: boolean;
  rows?: number;
}) {
  const [local, setLocal] = useState(value);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!dirty) setLocal(value);
  }, [value, dirty]);

  const handleBlur = () => {
    if (dirty && local !== value) {
      onSave(local);
    }
    setDirty(false);
  };

  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {multiline ? (
        <Textarea
          value={local}
          onChange={(e) => { setLocal(e.target.value); setDirty(true); }}
          onBlur={handleBlur}
          rows={rows}
          className="text-sm"
        />
      ) : (
        <Input
          value={local}
          onChange={(e) => { setLocal(e.target.value); setDirty(true); }}
          onBlur={handleBlur}
          className="text-sm"
        />
      )}
    </div>
  );
}

// ── 角色面板 ──────────────────────────────────────────

function CharacterPanel({ projectId, id }: { projectId: string; id: string }) {
  const confirm = useConfirm();
  const { data: character, isLoading } = useCharacter(projectId, id);
  const updateMutation = useUpdateCharacter(projectId);
  const deleteMutation = useDeleteCharacter(projectId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);

  // 懒加载该角色的所有图片（打开预览才请求）
  const { data: charAssets = [] } = useQuery({
    queryKey: ["assets", projectId, "character", id],
    queryFn: () => assetsApi.list(projectId, { target_type: "character", target_id: id }),
    enabled: !!character?.image_asset_id && previewOpen,
  });
  const previewItems = charAssets
    .filter((a: Asset) => a.asset_type === "image")
    .map((a: Asset) => ({ id: a.id, url: `/api/assets/${a.id}/file`, name: a.file_name || undefined }));

  // 预览内删除：删 asset + 若为主图清引用
  const handleDeletePreviewImage = useCallback(async (assetId: string) => {
    await assetsApi.delete(assetId, true);
    if (assetId === character?.image_asset_id) {
      const { charactersApi } = await import("@/api/business");
      await charactersApi.update(projectId, id, { image_asset_id: null });
    }
    qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, "character", id) });
    qc.invalidateQueries({ queryKey: charKeys.detail(projectId, id) });
    toast.success("图片已删除");
  }, [character, projectId, id, qc]);

  if (isLoading) return <PanelLoading />;
  if (!character) return <PanelEmpty title="角色不存在" />;

  const handleUpdate = (field: string, value: string) => {
    updateMutation.mutate({ id, payload: { [field]: value } });
  };

  const handleDelete = async () => {
    if (!(await confirm({ title: `确认删除角色「${character.name}」？`, variant: "destructive" }))) return;
    deleteMutation.mutate(id, {
      onSuccess: () => navigate(`/projects/${projectId}/characters`),
    });
  };

  const handleGenerate = () => {
    window.dispatchEvent(new CustomEvent("generate-entity", {
      detail: { targetType: "character", targetId: id, name: character.name, prompt: character.settings || character.description || character.name },
    }));
  };

  const mediaUrl = character.image_asset_id ? `/api/assets/${character.image_asset_id}/file` : "";

  return (
    <>
      <div
        className={`group relative h-40 w-full overflow-hidden bg-muted ${character.image_asset_id ? "cursor-zoom-in" : ""}`}
        onClick={() => character.image_asset_id && setPreviewOpen(true)}
      >
        {character.image_asset_id ? (
          <img src={mediaUrl} alt={character.name} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <User className="h-12 w-12 text-muted-foreground/30" />
          </div>
        )}
        {character.image_asset_id && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/20">
            <Maximize2 className="h-6 w-6 text-white opacity-0 transition-opacity group-hover:opacity-80" />
          </div>
        )}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
          <h3 className="text-lg font-bold text-white">{character.name}</h3>
          <Badge variant="default" className="mt-1">{charTypeMap[character.char_type]}</Badge>
        </div>
      </div>

      {character.image_asset_id && (
        <MediaPreviewModal
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          items={previewItems}
          initialId={character.image_asset_id}
          title={character.name}
          onDelete={handleDeletePreviewImage}
        />
      )}

      <PanelSection title="基本信息">
        <div className="space-y-3">
          <EditableField label="姓名" value={character.name} onSave={(v) => handleUpdate("name", v)} />
          <EditableField label="描述" value={character.description || ""} onSave={(v) => handleUpdate("description", v)} multiline />
          <EditableField label="生成设定" value={character.settings || ""} onSave={(v) => handleUpdate("settings", v)} multiline />
        </div>
      </PanelSection>

      <div className="flex gap-2 p-4">
        <Button className="flex-1" size="sm" onClick={handleGenerate}>
          <RefreshCw className="mr-1 h-3.5 w-3.5" />
          生成形象
        </Button>
        <Button variant="outline" size="sm" onClick={handleDelete} className="text-destructive hover:bg-destructive/10">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </>
  );
}

// ── 场景面板 ──────────────────────────────────────────

function ScenePanel({ projectId, id }: { projectId: string; id: string }) {
  const confirm = useConfirm();
  const { data: scene, isLoading } = useScene(projectId, id);
  const updateMutation = useUpdateScene(projectId);
  const deleteMutation = useDeleteScene(projectId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);

  // 懒加载该场景的所有图片
  const { data: sceneAssets = [] } = useQuery({
    queryKey: ["assets", projectId, "scene", id],
    queryFn: () => assetsApi.list(projectId, { target_type: "scene", target_id: id }),
    enabled: !!scene?.image_asset_id && previewOpen,
  });
  const previewItems = sceneAssets
    .filter((a: Asset) => a.asset_type === "image")
    .map((a: Asset) => ({ id: a.id, url: `/api/assets/${a.id}/file`, name: a.file_name || undefined }));

  const handleDeletePreviewImage = useCallback(async (assetId: string) => {
    await assetsApi.delete(assetId, true);
    if (assetId === scene?.image_asset_id) {
      const { scenesApi } = await import("@/api/business");
      await scenesApi.update(projectId, id, { image_asset_id: null });
    }
    qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, "scene", id) });
    qc.invalidateQueries({ queryKey: sceneKeys.detail(projectId, id) });
    toast.success("图片已删除");
  }, [scene, projectId, id, qc]);

  if (isLoading) return <PanelLoading />;
  if (!scene) return <PanelEmpty title="场景不存在" />;

  const handleUpdate = (field: string, value: string) => {
    updateMutation.mutate({ id, payload: { [field]: value } });
  };

  const handleDelete = async () => {
    if (!(await confirm({ title: `确认删除场景「${scene.name}」？`, variant: "destructive" }))) return;
    deleteMutation.mutate(id, {
      onSuccess: () => navigate(`/projects/${projectId}/scenes`),
    });
  };

  const handleGenerate = () => {
    window.dispatchEvent(new CustomEvent("generate-entity", {
      detail: { targetType: "scene", targetId: id, name: scene.name, prompt: scene.description || scene.settings || scene.name },
    }));
  };

  const mediaUrl = scene.image_asset_id ? `/api/assets/${scene.image_asset_id}/file` : "";

  return (
    <>
      <div
        className={`group relative h-40 w-full overflow-hidden bg-muted ${scene.image_asset_id ? "cursor-zoom-in" : ""}`}
        onClick={() => scene.image_asset_id && setPreviewOpen(true)}
      >
        {scene.image_asset_id ? (
          <img src={mediaUrl} alt={scene.name} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <MapPin className="h-12 w-12 text-muted-foreground/30" />
          </div>
        )}
        {scene.image_asset_id && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/20">
            <Maximize2 className="h-6 w-6 text-white opacity-0 transition-opacity group-hover:opacity-80" />
          </div>
        )}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
          <h3 className="text-lg font-bold text-white">{scene.name}</h3>
        </div>
      </div>

      {scene.image_asset_id && (
        <MediaPreviewModal
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          items={previewItems}
          initialId={scene.image_asset_id}
          title={scene.name}
          onDelete={handleDeletePreviewImage}
        />
      )}

      <PanelSection title="基本信息">
        <div className="space-y-3">
          <EditableField label="名称" value={scene.name} onSave={(v) => handleUpdate("name", v)} />
          <EditableField label="描述 / 提示词" value={scene.description || scene.settings || ""} onSave={(v) => handleUpdate("description", v)} multiline rows={4} />
        </div>
      </PanelSection>

      <div className="flex gap-2 p-4">
        <Button className="flex-1" size="sm" onClick={handleGenerate}>
          <RefreshCw className="mr-1 h-3.5 w-3.5" />
          生成概念图
        </Button>
        <Button variant="outline" size="sm" onClick={handleDelete} className="text-destructive hover:bg-destructive/10">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </>
  );
}

// ── 道具面板 ──────────────────────────────────────────

function PropPanel({ projectId, id }: { projectId: string; id: string }) {
  const confirm = useConfirm();
  const { data: prop, isLoading } = useProp(projectId, id);
  const updateMutation = useUpdateProp(projectId);
  const deleteMutation = useDeleteProp(projectId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);

  // 懒加载该道具的所有图片
  const { data: propAssets = [] } = useQuery({
    queryKey: ["assets", projectId, "prop", id],
    queryFn: () => assetsApi.list(projectId, { target_type: "prop", target_id: id }),
    enabled: !!prop?.image_asset_id && previewOpen,
  });
  const previewItems = propAssets
    .filter((a: Asset) => a.asset_type === "image")
    .map((a: Asset) => ({ id: a.id, url: `/api/assets/${a.id}/file`, name: a.file_name || undefined }));

  const handleDeletePreviewImage = useCallback(async (assetId: string) => {
    await assetsApi.delete(assetId, true);
    if (assetId === prop?.image_asset_id) {
      const { propsApi } = await import("@/api/business");
      await propsApi.update(projectId, id, { image_asset_id: null });
    }
    qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, "prop", id) });
    qc.invalidateQueries({ queryKey: propKeys.detail(projectId, id) });
    toast.success("图片已删除");
  }, [prop, projectId, id, qc]);

  if (isLoading) return <PanelLoading />;
  if (!prop) return <PanelEmpty title="道具不存在" />;

  const handleUpdate = (field: string, value: string) => {
    updateMutation.mutate({ id, payload: { [field]: value } });
  };

  const handleDelete = async () => {
    if (!(await confirm({ title: `确认删除道具「${prop.name}」？`, variant: "destructive" }))) return;
    deleteMutation.mutate(id, {
      onSuccess: () => navigate(`/projects/${projectId}/props`),
    });
  };

  const handleGenerate = () => {
    window.dispatchEvent(new CustomEvent("generate-entity", {
      detail: { targetType: "prop", targetId: id, name: prop.name, prompt: prop.description || prop.name },
    }));
  };

  const mediaUrl = prop.image_asset_id ? `/api/assets/${prop.image_asset_id}/file` : "";

  return (
    <>
      <div
        className={`group relative h-40 w-full overflow-hidden bg-muted ${prop.image_asset_id ? "cursor-zoom-in" : ""}`}
        onClick={() => prop.image_asset_id && setPreviewOpen(true)}
      >
        {prop.image_asset_id ? (
          <img src={mediaUrl} alt={prop.name} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Package className="h-12 w-12 text-muted-foreground/30" />
          </div>
        )}
        {prop.image_asset_id && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/20">
            <Maximize2 className="h-6 w-6 text-white opacity-0 transition-opacity group-hover:opacity-80" />
          </div>
        )}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
          <h3 className="text-lg font-bold text-white">{prop.name}</h3>
        </div>
      </div>

      {prop.image_asset_id && (
        <MediaPreviewModal
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          items={previewItems}
          initialId={prop.image_asset_id}
          title={prop.name}
          onDelete={handleDeletePreviewImage}
        />
      )}

      <PanelSection title="基本信息">
        <div className="space-y-3">
          <EditableField label="名称" value={prop.name} onSave={(v) => handleUpdate("name", v)} />
          <EditableField label="描述" value={prop.description || ""} onSave={(v) => handleUpdate("description", v)} multiline />
        </div>
      </PanelSection>

      <div className="flex gap-2 p-4">
        <Button className="flex-1" size="sm" onClick={handleGenerate}>
          <RefreshCw className="mr-1 h-3.5 w-3.5" />
          生成图片
        </Button>
        <Button variant="outline" size="sm" onClick={handleDelete} className="text-destructive hover:bg-destructive/10">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </>
  );
}

// ── 素材面板（二级页面点击图片时）──────────────────────

function AssetPanel({
  projectId, assetId, entityType, entityId, imageAssetId,
}: {
  projectId: string;
  assetId: string;
  entityType: string;
  entityId: string;
  imageAssetId?: string;
}) {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);
  const { data: asset, isLoading } = useQuery({
    queryKey: ["asset", assetId],
    queryFn: () => assetsApi.get(assetId),
    enabled: !!assetId,
  });

  const isPrimary = imageAssetId === assetId;

  // 懒加载同实体同类型素材（打开预览才请求）
  const { data: siblingAssets = [] } = useQuery({
    queryKey: ["assets", projectId, entityType, entityId, asset?.asset_type],
    queryFn: () => assetsApi.list(projectId, { target_type: entityType, target_id: entityId }),
    enabled: !!assetId && previewOpen,
  });
  // 列表回来前用当前 asset 兜底，避免白屏
  const previewItems = (siblingAssets.length > 0
    ? siblingAssets.filter((a: Asset) => a.asset_type === asset?.asset_type)
    : (asset ? [asset] : [])
  ).map((a: Asset) => ({
    id: a.id,
    url: `/api/assets/${a.id}/file`,
    isVideo: a.asset_type === "video",
    name: a.file_name || undefined,
  }));

  // 设为主图：更新实体的 image_asset_id
  const handleSetPrimary = useCallback(async () => {
    const apiMap: Record<string, (projectId: string, id: string, payload: Record<string, unknown>) => Promise<unknown>> = {};
    const { charactersApi, scenesApi, propsApi } = await import("@/api/business");
    if (entityType === "character") apiMap.character = (pid, id, p) => charactersApi.update(pid, id, p);
    if (entityType === "scene") apiMap.scene = (pid, id, p) => scenesApi.update(pid, id, p);
    if (entityType === "prop") apiMap.prop = (pid, id, p) => propsApi.update(pid, id, p);

    const updateFn = apiMap[entityType];
    if (!updateFn) return;

    try {
      await updateFn(projectId, entityId, { image_asset_id: assetId });
      // 只刷新相关实体的详情和素材列表
      if (entityType === "character") qc.invalidateQueries({ queryKey: charKeys.detail(projectId, entityId) });
      if (entityType === "scene") qc.invalidateQueries({ queryKey: sceneKeys.detail(projectId, entityId) });
      if (entityType === "prop") qc.invalidateQueries({ queryKey: propKeys.detail(projectId, entityId) });
      qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, entityType, entityId) });
      toast.success("已设为主图");
    } catch (e: any) {
      toast.error(`设为主图失败：${e.message}`);
    }
  }, [assetId, entityId, entityType, projectId, qc]);

  // 删除：按钮（无参，需 confirm）+ 预览（传 id，跳过 confirm，因 Modal 内已 confirm）
  const handleDelete = useCallback(async (targetAssetId?: string) => {
    const idToDelete = targetAssetId || assetId;
    if (!targetAssetId && !(await confirm({ title: "确认删除此图片？", variant: "destructive" }))) return;
    try {
      await assetsApi.delete(idToDelete, true);
      // 如果删的是主图，清空实体的 image_asset_id
      if (idToDelete === imageAssetId) {
        const { charactersApi, scenesApi, propsApi } = await import("@/api/business");
        const apiMap: Record<string, (pid: string, id: string, p: Record<string, unknown>) => Promise<unknown>> = {};
        if (entityType === "character") apiMap.character = (pid, id, p) => charactersApi.update(pid, id, p);
        if (entityType === "scene") apiMap.scene = (pid, id, p) => scenesApi.update(pid, id, p);
        if (entityType === "prop") apiMap.prop = (pid, id, p) => propsApi.update(pid, id, p);
        const updateFn = apiMap[entityType];
        if (updateFn) {
          await updateFn(projectId, entityId, { image_asset_id: null });
        }
      }
      qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, entityType, entityId) });
      // 如果删的是主图，需要刷新实体详情（image_asset_id 已被后端清空）
      if (idToDelete === imageAssetId) {
        if (entityType === "character") qc.invalidateQueries({ queryKey: charKeys.detail(projectId, entityId) });
        if (entityType === "scene") qc.invalidateQueries({ queryKey: sceneKeys.detail(projectId, entityId) });
        if (entityType === "prop") qc.invalidateQueries({ queryKey: propKeys.detail(projectId, entityId) });
      }
      // 如果删的就是当前面板展示的 asset，清空右侧面板
      if (idToDelete === assetId) {
        useUiStore.getState().setSelectedEntity(null);
      }
      toast.success("图片已删除");
    } catch (e: any) {
      toast.error(`删除失败：${e.message}`);
    }
  }, [assetId, imageAssetId, entityType, entityId, projectId, qc]);

  if (isLoading) return <PanelLoading />;
  if (!asset) return <PanelEmpty title="素材不存在" />;

  const isVideo = asset.asset_type === "video";
  const mediaUrl = `/api/assets/${asset.id}/file`;

  return (
    <>
      {/* 预览图：点击弹窗放大 */}
      <div
        className="group relative h-40 w-full cursor-zoom-in overflow-hidden bg-muted"
        onClick={() => setPreviewOpen(true)}
      >
        {isVideo ? (
          <video src={mediaUrl} className="h-full w-full object-cover" muted />
        ) : (
          <img src={mediaUrl} alt={asset.file_name || "素材"} className="h-full w-full object-cover" />
        )}
        {/* 悬浮放大提示 */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/20">
          <Maximize2 className="h-6 w-6 text-white opacity-0 transition-opacity group-hover:opacity-80" />
        </div>
        {isPrimary && (
          <Badge className="absolute right-2 top-2 bg-primary/90 text-primary-foreground">
            <Star className="mr-1 h-3 w-3 fill-current" />
            主图
          </Badge>
        )}
      </div>

      {/* 媒体预览弹窗 */}
      <MediaPreviewModal
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        items={previewItems}
        initialId={asset.id}
        title={asset.file_name || undefined}
        onDelete={handleDelete}
      />

      <PanelSection title="素材信息">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">文件名</span>
            <span className="truncate max-w-[160px]">{asset.file_name || "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">类型</span>
            <span>{isVideo ? "视频" : "图片"}</span>
          </div>
          {asset.width && asset.height ? (
            <div className="flex justify-between">
              <span className="text-muted-foreground">分辨率</span>
              <span>{asset.width} × {asset.height}</span>
            </div>
          ) : null}
          {asset.file_size ? (
            <div className="flex justify-between">
              <span className="text-muted-foreground">大小</span>
              <span>{(asset.file_size / 1024).toFixed(1)} KB</span>
            </div>
          ) : null}
          {isVideo && asset.duration ? (
            <div className="flex justify-between">
              <span className="text-muted-foreground">时长</span>
              <span>{asset.duration.toFixed(1)}s</span>
            </div>
          ) : null}
          <div className="flex justify-between">
            <span className="text-muted-foreground">状态</span>
            <Badge variant={asset.status === "ready" ? "success" : asset.status === "failed" ? "destructive" : "secondary"} className="text-xs">
              {asset.status === "ready" ? "就绪" : asset.status === "failed" ? "失败" : "处理中"}
            </Badge>
          </div>
        </div>
      </PanelSection>

      <div className="flex flex-col gap-2 p-4">
        {!isPrimary && (
          <Button variant="outline" size="sm" className="w-full" onClick={handleSetPrimary}>
            <Star className="mr-1 h-3.5 w-3.5" />
            设为主图
          </Button>
        )}
        <Button variant="outline" size="sm" className="w-full text-destructive hover:bg-destructive/10" onClick={() => handleDelete()}>
          <Trash2 className="mr-1 h-3.5 w-3.5" />
          删除
        </Button>
      </div>
    </>
  );
}

// ── 分镜帧面板（首帧/尾帧/视频）──────────────────────

function ShotFramePanel({
  projectId, shotId, frameType,
}: {
  projectId: string;
  shotId: string;
  frameType: "first_frame" | "last_frame" | "video";
}) {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const updateShotMutation = useUpdateShot(projectId);

  // 预览弹窗状态
  const [previewAssetId, setPreviewAssetId] = useState<string | null>(null);

  // 获取分镜数据
  const { data: shot, isLoading } = useQuery({
    queryKey: ["shot", shotId],
    queryFn: async () => {
      const { shotsApi } = await import("@/api/episodes");
      return shotsApi.get(shotId);
    },
    enabled: !!shotId,
  });

  // 获取当前帧的 asset 详情
  const assetId = frameType === "first_frame"
    ? shot?.first_frame_asset_id
    : frameType === "last_frame"
      ? shot?.last_frame_asset_id
      : shot?.video_asset_id;

  const { data: asset } = useQuery({
    queryKey: ["asset", assetId],
    queryFn: () => assetsApi.get(assetId!),
    enabled: !!assetId,
  });

  const frameLabel = frameType === "first_frame" ? "首帧" : frameType === "last_frame" ? "尾帧" : "视频";
  const isVideo = frameType === "video";
  const promptField = isVideo ? "video_prompt" : frameType === "first_frame" ? "first_frame_prompt" : "last_frame_prompt";
  const prompt = shot ? (shot as any)[promptField] || "" : "";

  // 获取该分镜下同类型的所有 asset（用于"选择其他图作为主图"）
  const { data: frameAssets = [] } = useQuery({
    queryKey: ["assets", projectId, `shot_${frameType}`, shotId],
    queryFn: () => assetsApi.list(projectId, {
      target_type: `shot_${frameType}`,
      target_id: shotId,
    }),
    enabled: !!shotId,
  });

  const handleUpdatePrompt = (value: string) => {
    updateShotMutation.mutate({ id: shotId, payload: { [promptField]: value } });
  };

  // 选择其他图作为当前帧的主图
  const handleSelectAsset = (newAssetId: string) => {
    const fieldMap = {
      first_frame: "first_frame_asset_id",
      last_frame: "last_frame_asset_id",
      video: "video_asset_id",
    };
    updateShotMutation.mutate(
      { id: shotId, payload: { [fieldMap[frameType]]: newAssetId } },
      {
        onSuccess: () => {
          qc.invalidateQueries({ queryKey: ["shots"] });
          qc.invalidateQueries({ queryKey: ["shot", shotId] });
          toast.success(`${frameLabel}已更换`);
        },
      },
    );
  };

  const handleDeleteAllAssets = async () => {
    if (frameAssets.length === 0) return;
    const label = isVideo ? "视频" : "图片";
    if (!(await confirm({ title: `确认删除此${frameLabel}的所有${label}（共 ${frameAssets.length} 个）？`, variant: "destructive" }))) return;
    try {
      // 逐个删除所有该帧类型的 asset
      for (const a of frameAssets) {
        await assetsApi.delete(a.id, true);
      }
      // 清空分镜上的 asset_id 引用（等待后端更新完成再刷新缓存）
      const fieldMap = { first_frame: "first_frame_asset_id", last_frame: "last_frame_asset_id", video: "video_asset_id" };
      await updateShotMutation.mutateAsync({ id: shotId, payload: { [fieldMap[frameType]]: null } });
      qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, `shot_${frameType}`, shotId) });
      qc.invalidateQueries({ queryKey: ["shots"] });
      qc.invalidateQueries({ queryKey: ["shot", shotId] });
      useUiStore.getState().setSelectedEntity(null);
      toast.success(`${frameLabel}所有${label}已删除`);
    } catch (e: any) {
      toast.error(`删除失败：${e.message}`);
    }
  };

  // 删除单个 asset（改为返回 Promise，供预览 Modal await）
  const handleDeleteSingleAsset = useCallback(async (a: Asset) => {
    const label = isVideo ? "视频" : "图片";
    if (!(await confirm({ title: `确认删除此${label}？`, variant: "destructive" }))) return;
    try {
      await assetsApi.delete(a.id, true);
      // 如果删的是当前主图，清空分镜引用（等待后端更新完成再刷新缓存）
      if (a.id === assetId) {
        const fieldMap = { first_frame: "first_frame_asset_id", last_frame: "last_frame_asset_id", video: "video_asset_id" };
        await updateShotMutation.mutateAsync({ id: shotId, payload: { [fieldMap[frameType]]: null } });
      }
      qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, `shot_${frameType}`, shotId) });
      qc.invalidateQueries({ queryKey: ["shots"] });
      qc.invalidateQueries({ queryKey: ["shot", shotId] });
      toast.success(`${label}已删除`);
    } catch (err: any) {
      toast.error(`删除失败：${err.message}`);
    }
  }, [isVideo, assetId, shotId, frameType, updateShotMutation, qc]);

  // 预览用 items（列表回来前用当前主图兜底）
  const shotPreviewItems = (frameAssets.length > 0 ? frameAssets : (asset ? [asset] : [])).map((a: Asset) => ({
    id: a.id,
    url: `/api/assets/${a.id}/file`,
    isVideo: a.asset_type === "video",
    name: a.file_name || undefined,
  }));

  // 预览内删除回调：Modal 已 confirm，此处不 confirm
  const handleDeleteFromShotPreview = useCallback(async (id: string) => {
    const targetAsset = frameAssets.find((a: Asset) => a.id === id) || asset;
    if (!targetAsset) return;
    try {
      await assetsApi.delete(id, true);
      if (id === assetId) {
        const fieldMap = { first_frame: "first_frame_asset_id", last_frame: "last_frame_asset_id", video: "video_asset_id" };
        await updateShotMutation.mutateAsync({ id: shotId, payload: { [fieldMap[frameType]]: null } });
      }
      qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, `shot_${frameType}`, shotId) });
      qc.invalidateQueries({ queryKey: ["shots"] });
      qc.invalidateQueries({ queryKey: ["shot", shotId] });
      if (id === assetId) {
        useUiStore.getState().setSelectedEntity(null);
      }
      toast.success(`${isVideo ? "视频" : "图片"}已删除`);
    } catch (err: any) {
      toast.error(`删除失败：${err.message}`);
    }
  }, [frameAssets, asset, assetId, shotId, frameType, updateShotMutation, qc, isVideo]);

  // 上传图片
  const handleUpload = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = isVideo ? "video/*" : "image/*";
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      try {
        const result = await assetsApi.uploadNew({
          projectId,
          category: frameType === "video" ? "shot_video" : frameType,
          file,
          target_type: `shot_${frameType}`,
          target_id: shotId,
        });
        // 设为当前帧的主图
        const fieldMap = { first_frame: "first_frame_asset_id", last_frame: "last_frame_asset_id", video: "video_asset_id" };
        updateShotMutation.mutate({ id: shotId, payload: { [fieldMap[frameType]]: result.data.id } });
        qc.invalidateQueries({ queryKey: assetKeys.byTarget(projectId, `shot_${frameType}`, shotId) });
        qc.invalidateQueries({ queryKey: ["shots"] });
        toast.success("上传成功");
      } catch (e: any) {
        toast.error(`上传失败：${e.message}`);
      }
    };
    input.click();
  };

  if (isLoading) return <PanelLoading />;
  if (!shot) return <PanelEmpty title="分镜不存在" />;

  // 当前帧的媒体 URL
  const mediaUrl = assetId ? `/api/assets/${assetId}/file` : "";

  return (
    <>
      {/* 预览：点击弹窗放大 */}
      <div
        className={`group relative h-40 w-full overflow-hidden bg-muted ${assetId ? "cursor-zoom-in" : ""}`}
        onClick={() => assetId && setPreviewAssetId(assetId)}
      >
        {assetId ? (
          isVideo ? (
            <video src={mediaUrl} className="h-full w-full object-cover" muted />
          ) : (
            <img src={mediaUrl} alt={frameLabel} className="h-full w-full object-cover" />
          )
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            {isVideo ? <Video className="h-12 w-12 text-muted-foreground/30" /> : <ImageIcon className="h-12 w-12 text-muted-foreground/30" />}
          </div>
        )}
        {/* 有素材时悬浮放大提示 */}
        {assetId && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/20">
            <Maximize2 className="h-6 w-6 text-white opacity-0 transition-opacity group-hover:opacity-80" />
          </div>
        )}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
          <h3 className="text-lg font-bold text-white">{frameLabel}</h3>
          <span className="text-xs text-white/70">分镜 {String((shot as any).shot_no || "").padStart(2, "0")}</span>
        </div>
      </div>

      {/* 素材信息 */}
      {asset && (
        <PanelSection title="素材信息">
          <div className="space-y-2 text-sm">
            {asset.width && asset.height ? (
              <div className="flex justify-between">
                <span className="text-muted-foreground">分辨率</span>
                <span>{asset.width} × {asset.height}</span>
              </div>
            ) : null}
            {asset.file_size ? (
              <div className="flex justify-between">
                <span className="text-muted-foreground">大小</span>
                <span>{(asset.file_size / 1024).toFixed(1)} KB</span>
              </div>
            ) : null}
            {isVideo && asset.duration ? (
              <div className="flex justify-between">
                <span className="text-muted-foreground">时长</span>
                <span>{asset.duration.toFixed(1)}s</span>
              </div>
            ) : null}
            <div className="flex justify-between">
              <span className="text-muted-foreground">文件名</span>
              <span className="truncate max-w-[160px]">{asset.file_name || "—"}</span>
            </div>
          </div>
        </PanelSection>
      )}

      {/* 提示词 */}
      <PanelSection title="提示词">
        <EditableField label="" value={prompt} onSave={handleUpdatePrompt} multiline rows={3} />
      </PanelSection>

      {/* 操作按钮 */}
      <div className="flex flex-col gap-2 p-4">
        <Button variant="outline" size="sm" className="w-full" onClick={handleUpload}>
          <Upload className="mr-1 h-3.5 w-3.5" />
          上传{isVideo ? "视频" : "图片"}
        </Button>

        {/* 所有帧素材缩略图：每列2个，hover 显示操作，点击弹窗看大图 */}
        {frameAssets.length > 0 && (
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">所有{frameLabel}{isVideo ? "视频" : "图片"} ({frameAssets.length})</Label>
            <div className="grid grid-cols-2 gap-2">
              {frameAssets.map((a: Asset) => (
                <div key={a.id} className="group relative">
                  <div
                    className={`aspect-square w-full cursor-zoom-in overflow-hidden rounded-lg border-2 ${a.id === assetId ? "border-primary" : "border-transparent hover:border-primary/50"}`}
                    onClick={() => setPreviewAssetId(a.id)}
                  >
                    {a.asset_type === "video" ? (
                      <video src={`/api/assets/${a.id}/file`} className="h-full w-full object-cover" muted />
                    ) : (
                      <img src={`/api/assets/${a.id}/file`} alt="" className="h-full w-full object-cover" />
                    )}
                    {/* hover 遮罩：显示设为主图或删除 */}
                    <div className="absolute inset-0 flex items-end justify-center gap-1 bg-black/0 p-1.5 transition-colors group-hover:bg-black/40">
                      {a.id !== assetId && (
                        <button
                          className="translate-y-2 rounded bg-primary/90 px-2 py-0.5 text-xs text-primary-foreground opacity-0 transition-[transform,opacity] group-hover:translate-y-0 group-hover:opacity-100 hover:bg-primary"
                          onClick={(e) => { e.stopPropagation(); handleSelectAsset(a.id); }}
                          title="设为主图"
                        >
                          <Star className="inline h-3 w-3" /> 设为主图
                        </button>
                      )}
                      <button
                        className="translate-y-2 rounded bg-destructive/90 px-2 py-0.5 text-xs text-white opacity-0 transition-[transform,opacity] group-hover:translate-y-0 group-hover:opacity-100 hover:bg-destructive"
                        onClick={(e) => { e.stopPropagation(); handleDeleteSingleAsset(a); }}
                        title="删除"
                      >
                        <Trash2 className="inline h-3 w-3" /> 删除
                      </button>
                    </div>
                  </div>
                  {/* 主图标记 */}
                  {a.id === assetId && (
                    <Badge className="absolute right-1 top-1 bg-primary/90 text-primary-foreground text-[10px] px-1 py-0">
                      <Star className="mr-0.5 h-2.5 w-2.5 fill-current" />
                      主图
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {frameAssets.length > 0 && (
          <Button variant="outline" size="sm" className="w-full text-destructive hover:bg-destructive/10" onClick={handleDeleteAllAssets}>
            <Trash2 className="mr-1 h-3.5 w-3.5" />
            删除{frameLabel}所有{isVideo ? "视频" : "图片"}
          </Button>
        )}
      </div>

      {/* 缩略图预览弹窗 */}
      <MediaPreviewModal
        open={!!previewAssetId}
        onOpenChange={(v) => { if (!v) setPreviewAssetId(null); }}
        items={shotPreviewItems}
        initialId={previewAssetId || undefined}
        title={`${frameLabel} - 分镜 ${String((shot as any).shot_no || "").padStart(2, "0")}`}
        onDelete={handleDeleteFromShotPreview}
      />
    </>
  );
}
