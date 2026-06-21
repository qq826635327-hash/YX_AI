import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Plus, RefreshCw, CheckSquare, X } from "lucide-react";
import { PageContainer, EmptyState, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GenerateDialog, type GenerateTarget } from "@/components/GenerateDialog";
import { EntityCard } from "@/components/EntityCard";
import { EntityEditDialog } from "@/components/EntityEditDialog";
import type { EntityConfig } from "@/config/entityConfig";

interface EntitiesPageProps<T> {
  config: EntityConfig<T>;
  useEntities: (projectId: string) => { data: T[] | undefined; isLoading: boolean };
  onCreate: (data: Partial<T>) => Promise<any>;
  onUpdate: (id: string, payload: Partial<T>) => Promise<any>;
  onDelete: (id: string) => void;
}

export function EntitiesPage<T>({
  config,
  useEntities,
  onCreate,
  onUpdate,
  onDelete,
}: EntitiesPageProps<T>) {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { data: entities, isLoading } = useEntities(projectId!);

  const [activeTab, setActiveTab] = useState<string>("all");
  const [editing, setEditing] = useState<T | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [generateTargets, setGenerateTargets] = useState<GenerateTarget[]>([]);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState<string>();

  const filtered = config.tabs && config.tabFilter
    ? (entities || []).filter((e: any) => config.tabFilter!(e, activeTab))
    : (entities || []);

  const getId = (e: T): string => (e as any).id;
  const getName = (e: T): string => (e as any).name;
  const getImageAssetId = (e: T): string | null => (e as any).image_asset_id;

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
      setSelectedIds(new Set(filtered.map((e: any) => getId(e))));
    }
  };

  const handleGenerate = (entity: T) => {
    const ent = entity as any;
    setGenerateTargets([{
      target_type: config.targetType,
      target_id: getId(entity),
      name: getName(entity),
      prompt: ent.settings || ent.description || getName(entity),
    }]);
    setGeneratePrompt(ent.settings || ent.description || getName(entity));
    setGenerateOpen(true);
  };

  const handleBatchGenerate = () => {
    const selected = filtered.filter((e: any) => selectedIds.has(getId(e)));
    if (selected.length === 0) return;
    setGenerateTargets(selected.map((e: any) => ({
      target_type: config.targetType,
      target_id: getId(e),
      name: getName(e),
      prompt: e.settings || e.description || getName(e),
    })));
    setGeneratePrompt(undefined);
    setGenerateOpen(true);
  };

  const handleEditSubmit = async (data: Partial<T>) => {
    try {
      if (editing) {
        await onUpdate(getId(editing), data);
      } else {
        await onCreate(data);
      }
      setEditing(null);
      setCreateOpen(false);
    } catch {
      // 失败已由 React Query onError 回调处理
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
            </>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={() => setSelectMode(true)}>
                <CheckSquare className="h-3.5 w-3.5" />
                多选
              </Button>
              <Button onClick={() => setCreateOpen(true)}>
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
          <TabsList>
            {config.tabs.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>
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
            {filtered.map((entity: T) => (
              <EntityCard
                key={getId(entity)}
                imageAssetId={getImageAssetId(entity)}
                name={getName(entity)}
                badge={config.getBadge?.(entity)}
                selectMode={selectMode}
                selected={selectedIds.has(getId(entity))}
                onClick={() => navigate(config.detailPath(projectId!, entity))}
                onToggleSelect={() => toggleSelect(getId(entity))}
                onEdit={() => setEditing(entity)}
                onDelete={() => {
                  if (confirm(`确认删除「${getName(entity)}」？`)) onDelete(getId(entity));
                }}
                onGenerate={() => handleGenerate(entity)}
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
