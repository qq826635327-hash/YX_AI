import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Plus, RefreshCw, CheckSquare, X, Download, Upload, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { PageContainer, EmptyState, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GenerateDialog, type GenerateTarget } from "@/components/GenerateDialog";
import { EntityCard } from "@/components/EntityCard";
import { EntityEditDialog } from "@/components/EntityEditDialog";
import { assetsApi } from "@/api/assets";
import { charactersApi, scenesApi, propsApi } from "@/api/business";
import { toast, useUiStore } from "@/stores/ui";
import { useConfirm } from "@/components/ConfirmDialog";
import type { EntityConfig } from "@/config/entityConfig";
import type { BaseEntity } from "@/types";

interface EntitiesPageProps<T extends BaseEntity> {
  config: EntityConfig<T>;
  useEntities: (projectId: string) => { data: T[] | undefined; isLoading: boolean };
  onCreate: (data: Partial<T>) => Promise<unknown>;
  onUpdate: (id: string, payload: Partial<T>) => Promise<unknown>;
  onDelete: (id: string) => void;
}

export function EntitiesPage<T extends BaseEntity>({
  config,
  useEntities,
  onCreate,
  onUpdate,
  onDelete: _onDelete,
}: EntitiesPageProps<T>) {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setSelectedEntity = useUiStore((s) => s.setSelectedEntity);
  const confirm = useConfirm();
  const { data: entities, isLoading } = useEntities(projectId!);

  const [activeTab, setActiveTab] = useState<string>("all");
  const [editing, setEditing] = useState<T | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [generateTargets, setGenerateTargets] = useState<GenerateTarget[]>([]);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState<string>();
  const [syncing, setSyncing] = useState<"to_local" | "from_local" | null>(null);

  // 监听右侧面板触发的生成请求
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (!detail) return;
      setGenerateTargets([{
        target_type: detail.targetType,
        target_id: detail.targetId,
        name: detail.name,
        prompt: detail.prompt,
      }]);
      setGeneratePrompt(detail.prompt);
      setGenerateOpen(true);
    };
    window.addEventListener("generate-entity", handler);
    return () => window.removeEventListener("generate-entity", handler);
  }, []);

  const filtered = config.tabs && config.tabFilter
    ? (entities || []).filter((e) => config.tabFilter!(e, activeTab))
    : (entities || []);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((e) => e.id)));
    }
  };

  const handleBatchGenerate = () => {
    const selected = filtered.filter((e) => selectedIds.has(e.id));
    if (selected.length === 0) return;
    setGenerateTargets(selected.map((e) => ({
      target_type: config.targetType,
      target_id: e.id,
      name: e.name,
      prompt: e.settings || e.description || e.name,
    })));
    setGeneratePrompt(undefined);
    setGenerateOpen(true);
  };

  const handleBatchDelete = async () => {
    const selected = filtered.filter((e) => selectedIds.has(e.id));
    if (selected.length === 0) return;
    if (!await confirm({
      title: `确定删除选中的 ${selected.length} 个${config.title}？`,
      description: "此操作不可恢复，关联的素材和磁盘文件也将被删除。",
      variant: "destructive",
    })) return;

    try {
      const ids = selected.map((e) => e.id);
      let result: { deleted: number; errors: Array<{ id: string; error: string }> };
      switch (config.entityType) {
        case "character":
          result = (await charactersApi.batchDelete(projectId!, ids)).data;
          break;
        case "scene":
          result = (await scenesApi.batchDelete(projectId!, ids)).data;
          break;
        case "prop":
          result = (await propsApi.batchDelete(projectId!, ids)).data;
          break;
        default:
          return;
      }
      if (result.errors.length > 0) {
        toast.error(`${result.deleted} 个已删除，${result.errors.length} 个失败`);
      } else {
        toast.success(`已删除 ${result.deleted} 个${config.title}`);
      }
      setSelectedIds(new Set());
      setSelectMode(false);
      queryClient.invalidateQueries({ queryKey: [config.entityType + "s"] });
    } catch (e: any) {
      toast.error(`批量删除失败：${e.message ?? "未知错误"}`);
    }
  };

  const handleEditSubmit = async (data: Partial<T>) => {
    try {
      if (editing) {
        await onUpdate(editing.id, data);
      } else {
        await onCreate(data);
      }
      setEditing(null);
      setCreateOpen(false);
    } catch {
      // 失败已由 React Query onError 回调处理
    }
  };

  const handleSyncToLocal = async () => {
    if (!projectId || syncing) return;
    setSyncing("to_local");
    try {
      const res = await assetsApi.syncDirs(projectId, "db_to_disk");
      const data = res.data;
      const created = data.created ?? 0;
      const skipped = data.skipped ?? 0;
      const removed = data.removed ?? 0;
      const parts: string[] = [];
      if (created > 0) parts.push(`新建 ${created} 个`);
      if (removed > 0) parts.push(`删除多余 ${removed} 个`);
      if (skipped > 0) parts.push(`跳过 ${skipped} 个`);
      if (parts.length > 0) {
        toast.success(`同步到本地完成：${parts.join("，")}`);
      } else {
        toast.success("本地目录已是最新，无变更");
      }
      await queryClient.invalidateQueries();
    } catch (e: any) {
      toast.error(`同步失败：${e.message ?? "未知错误"}`);
    } finally {
      setSyncing(null);
    }
  };

  const handleSyncFromLocal = async () => {
    if (!projectId || syncing) return;
    setSyncing("from_local");
    try {
      const res = await assetsApi.syncDirs(projectId, "disk_to_db");
      const data: any = res.data;
      const checked = data.checked ?? 0;
      const deleted = data.deleted ?? 0;
      if (deleted > 0) {
        toast.success(`从本地同步完成：检查 ${checked} 条，清理 ${deleted} 条孤立记录`);
      } else {
        toast.success("本地与数据库一致，无变更");
      }
      await queryClient.invalidateQueries();
    } catch (e: any) {
      toast.error(`同步失败：${e.message ?? "未知错误"}`);
    } finally {
      setSyncing(null);
    }
  };

  return (
    <PageContainer
      title={config.title}
      description={config.description}
      actions={
        <div className="flex items-center gap-2">
          {selectMode ? (
            <>
              <Button variant="outline" size="sm" onClick={toggleSelectAll}>
                <CheckSquare className="h-3.5 w-3.5" />
                {selectedIds.size === filtered.length ? "取消全选" : "全选"}
              </Button>
              <span className="text-sm text-muted-foreground">
                已选 {selectedIds.size} 项
              </span>
              <Button variant="outline" size="sm" onClick={() => { setSelectMode(false); setSelectedIds(new Set()); }}>
                <X className="h-3.5 w-3.5" />
                退出选择
              </Button>
              <Button size="sm" disabled={selectedIds.size === 0} onClick={handleBatchGenerate}>
                <RefreshCw className="h-3.5 w-3.5" />
                批量生成
              </Button>
              <Button variant="outline" size="sm" disabled={selectedIds.size === 0} onClick={handleBatchDelete} className="text-destructive">
                <Trash2 className="h-3.5 w-3.5" />
                批量删除
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={() => setSelectMode(true)}>
                <CheckSquare className="h-3.5 w-3.5" />
                多选
              </Button>
              <Button variant="outline" size="sm" onClick={handleSyncToLocal} disabled={!!syncing}>
                <Download className="h-3.5 w-3.5" />
                {syncing === "to_local" ? "同步中..." : "同步到本地"}
              </Button>
              <Button variant="outline" size="sm" onClick={handleSyncFromLocal} disabled={!!syncing}>
                <Upload className="h-3.5 w-3.5" />
                {syncing === "from_local" ? "同步中..." : "本地上传同步"}
              </Button>
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                新建
              </Button>
            </>
          )}
        </div>
      }
    >
      {config.tabs && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-secondary/60 p-1">
            {config.tabs.map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
              >
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      )}

      <div className="mt-6">
        {isLoading ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={config.emptyIcon}
            title={`暂无${config.title}`}
            description={`新建${config.title}或通过剧本解析自动生成`}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {filtered.map((entity) => (
              <EntityCard
                key={entity.id}
                imageAssetId={entity.image_asset_id ?? undefined}
                name={entity.name}
                subtitle={config.getSubtitle?.(entity)}
                badge={config.getBadge?.(entity)}
                selectMode={selectMode}
                selected={selectedIds.has(entity.id)}
                onClick={() => {
                  setSelectedEntity({
                    type: config.entityType,
                    id: entity.id,
                    projectId: projectId!,
                  });
                  navigate(config.detailPath(projectId!, entity));
                }}
                onToggleSelect={() => toggleSelect(entity.id)}
              />
            ))}
          </div>
        )}
      </div>

      <GenerateDialog
        open={generateOpen}
        onOpenChange={setGenerateOpen}
        projectId={projectId!}
        targets={generateTargets}
        defaultPrompt={generatePrompt}
      />

      <EntityEditDialog
        config={config}
        open={!!editing || createOpen}
        entity={editing}
        onOpenChange={(v) => {
          if (!v) { setEditing(null); setCreateOpen(false); }
        }}
        onSubmit={handleEditSubmit}
      />
    </PageContainer>
  );
}
