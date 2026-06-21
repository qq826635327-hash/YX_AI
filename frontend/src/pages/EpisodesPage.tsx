/** 剧集结构页：剧集列表 + 分镜管理（首帧/尾帧/视频）+ 分镜关联引用。 */

import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import {
  Clapperboard,
  Image as ImageIcon,
  Video,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Trash2,
  Plus,
  CheckSquare,
  X,
  Users,
  Map,
  Package,
  Link2,
} from "lucide-react";
import { PageContainer, EmptyState, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  useEpisodes,
  useShots,
  useUpdateShot,
  useCreateEpisode,
  useDeleteEpisode,
  useCreateShot,
  useDeleteShot,
  useShotReferences,
  useAddShotCharacters,
  useRemoveShotCharacter,
  useAddShotScenes,
  useRemoveShotScene,
  useAddShotProps,
  useRemoveShotProp,
  useCharacters,
  useScenes,
  useProps,
} from "@/hooks/useBusiness";
import { shotReferencesApi } from "@/api/shotReferences";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "@/stores/ui";
import type { Shot, GenStatus, Episode, ShotReferenceEntity, TargetType } from "@/types";
import { GenerateDialog, type GenerateTarget } from "@/components/GenerateDialog";
import { Checkbox } from "@/components/ui/checkbox";

export function EpisodesPage() {
  const { projectId } = useParams();
  const { data: episodes, isLoading } = useEpisodes(projectId!);
  const createEpisodeMutation = useCreateEpisode(projectId!);
  const deleteEpisodeMutation = useDeleteEpisode(projectId!);

  const [expandedEpisode, setExpandedEpisode] = useState<string | null>(null);
  const [createEpOpen, setCreateEpOpen] = useState(false);
  const [epForm, setEpForm] = useState({ episode_no: 1, title: "", summary: "" });

  const handleCreateEpisode = async () => {
    try {
      await createEpisodeMutation.mutateAsync({
        episode_no: epForm.episode_no,
        title: epForm.title.trim() || `第${epForm.episode_no}集`,
        summary: epForm.summary.trim() || undefined,
      });
      setEpForm({ episode_no: epForm.episode_no + 1, title: "", summary: "" });
      setCreateEpOpen(false);
    } catch {
      // mutateAsync 失败已由 React Query onError 回调处理
    }
  };

  if (isLoading) return <LoadingState />;

  return (
    <PageContainer
      title="剧集结构"
      description="管理剧集、分镜与首帧/尾帧/视频素材"
      actions={
        <Button onClick={() => setCreateEpOpen(true)}>
          <Plus className="h-4 w-4" />
          新增剧集
        </Button>
      }
    >
      {(episodes || []).length === 0 ? (
        <EmptyState
          icon={Clapperboard}
          title="暂无剧集"
          description="点击右上角「新增剧集」创建，或通过剧本解析自动生成"
        />
      ) : (
        <div className="space-y-3">
          {(episodes as Episode[]).map((ep) => {
            const isExpanded = expandedEpisode === ep.id;
            return (
              <Card key={ep.id} className="group">
                <CardHeader
                  className="cursor-pointer py-4"
                  onClick={() => setExpandedEpisode(isExpanded ? null : ep.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                      <Badge variant="secondary">第 {ep.episode_no} 集</Badge>
                      <CardTitle className="text-base">{ep.title}</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                      {ep.summary && (
                        <span className="max-w-md truncate text-sm text-muted-foreground">{ep.summary}</span>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm(`确认删除「第${ep.episode_no}集 ${ep.title}」？`)) {
                            deleteEpisodeMutation.mutate(ep.id);
                          }
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                {isExpanded && (
                  <CardContent className="border-t pt-4">
                    <ShotsList episodeId={ep.id} projectId={projectId!} />
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* 新增剧集对话框 */}
      <Dialog open={createEpOpen} onOpenChange={setCreateEpOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增剧集</DialogTitle>
            <DialogDescription>创建一个新的剧集</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>集号 *</Label>
              <Input
                type="number"
                min={1}
                value={epForm.episode_no}
                onChange={(e) => setEpForm({ ...epForm, episode_no: parseInt(e.target.value) || 1 })}
              />
            </div>
            <div className="space-y-2">
              <Label>标题</Label>
              <Input
                value={epForm.title}
                onChange={(e) => setEpForm({ ...epForm, title: e.target.value })}
                placeholder="留空则自动生成「第N集」"
              />
            </div>
            <div className="space-y-2">
              <Label>摘要</Label>
              <Textarea
                value={epForm.summary}
                onChange={(e) => setEpForm({ ...epForm, summary: e.target.value })}
                rows={3}
                placeholder="本集剧情摘要"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateEpOpen(false)}>取消</Button>
            <Button disabled={createEpisodeMutation.isPending} onClick={handleCreateEpisode}>
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}

function ShotsList({ episodeId, projectId }: { episodeId: string; projectId: string }) {
  const { data: shots, isLoading } = useShots(episodeId);
  const updateMutation = useUpdateShot(projectId);
  const createShotMutation = useCreateShot(projectId);
  const deleteShotMutation = useDeleteShot(projectId);

  const [createShotOpen, setCreateShotOpen] = useState(false);
  const [shotForm, setShotForm] = useState({ shot_no: 1, summary: "" });
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [generateTargets, setGenerateTargets] = useState<GenerateTarget[]>([]);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState<string>();
  const [batchRefOpen, setBatchRefOpen] = useState<"characters" | "scenes" | "props" | null>(null);

  const handleCreateShot = async () => {
    try {
      await createShotMutation.mutateAsync({
        episodeId,
        payload: {
          shot_no: shotForm.shot_no,
          summary: shotForm.summary.trim() || undefined,
        },
      });
      setShotForm({ shot_no: shotForm.shot_no + 1, summary: "" });
      setCreateShotOpen(false);
    } catch {
      // mutateAsync 失败已由 React Query onError 回调处理
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allShots = (shots || []) as Shot[];

  const toggleSelectAll = () => {
    if (selectedIds.size === allShots.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(allShots.map((s) => s.id)));
    }
  };

  const handleShotGenerate = (shot: Shot, targetType: "shot_first_frame" | "shot_last_frame" | "shot_video", prompt?: string) => {
    setGenerateTargets([{
      target_type: targetType,
      target_id: shot.id,
      name: `分镜${shot.shot_no}`,
      prompt,
    }]);
    setGeneratePrompt(prompt);
    setGenerateOpen(true);
  };

  const handleBatchGenerate = (targetType: TargetType = "shot_first_frame") => {
    const selected = allShots.filter((s) => selectedIds.has(s.id));
    if (selected.length === 0) return;
    const promptField =
      targetType === "shot_first_frame" ? "first_frame_prompt" :
      targetType === "shot_last_frame" ? "last_frame_prompt" :
      "video_prompt";
    setGenerateTargets(selected.map((s) => ({
      target_type: targetType,
      target_id: s.id,
      name: `分镜${s.shot_no}`,
      prompt: (s[promptField] as string) || s.summary || undefined,
    })));
    setGeneratePrompt(undefined);
    setGenerateOpen(true);
  };

  if (isLoading) return <LoadingState />;

  return (
    <div className="space-y-3">
      {(shots || []).length > 0 &&
        (shots as Shot[]).map((shot) => (
          <div
            key={shot.id}
            className={cn("relative", selectMode && "cursor-pointer", selectedIds.has(shot.id) && "ring-2 ring-primary rounded-lg")}
            onClick={selectMode ? () => toggleSelect(shot.id) : undefined}
          >
            {selectMode && (
              <div className="absolute left-2 top-2 z-10">
                <Checkbox checked={selectedIds.has(shot.id)} onChange={() => toggleSelect(shot.id)} onClick={(e) => e.stopPropagation()} />
              </div>
            )}
            <ShotItem
              shot={shot}
              projectId={projectId}
              onUpdate={(payload) => updateMutation.mutate({ id: shot.id, payload })}
              onGenerate={(targetType, prompt) => handleShotGenerate(shot, targetType, prompt)}
              onDelete={() => {
                if (confirm(`确认删除分镜 ${shot.shot_no}？`)) {
                  deleteShotMutation.mutate(shot.id);
                }
              }}
            />
          </div>
        ))}

      <div className="flex flex-wrap items-center gap-2">
        {selectMode ? (
          <>
            <Button variant="outline" size="sm" onClick={toggleSelectAll}>
              <CheckSquare className="h-3.5 w-3.5" />
              {selectedIds.size === allShots.length ? "取消全选" : "全选"}
            </Button>
            <span className="text-sm text-muted-foreground">已选 {selectedIds.size} 项</span>
            <Button variant="outline" size="sm" onClick={() => { setSelectMode(false); setSelectedIds(new Set()); }}>
              <X className="h-3.5 w-3.5" />
              退出选择
            </Button>

            {/* 批量生成 - 可选目标类型 */}
            <div className="flex items-center gap-1">
              <Button size="sm" disabled={selectedIds.size === 0} onClick={() => handleBatchGenerate("shot_first_frame")}>
                <ImageIcon className="h-3.5 w-3.5" />
                批量首帧
              </Button>
              <Button variant="outline" size="sm" disabled={selectedIds.size === 0} onClick={() => handleBatchGenerate("shot_last_frame")}>
                <ImageIcon className="h-3.5 w-3.5" />
                尾帧
              </Button>
              <Button variant="outline" size="sm" disabled={selectedIds.size === 0} onClick={() => handleBatchGenerate("shot_video")}>
                <Video className="h-3.5 w-3.5" />
                视频
              </Button>
            </div>

            {/* 批量关联 */}
            <div className="flex items-center gap-1">
              <Link2 className="h-3.5 w-3.5 text-muted-foreground" />
              <Button variant="outline" size="sm" disabled={selectedIds.size === 0} onClick={() => setBatchRefOpen("characters")}>
                <Users className="h-3 w-3" /> 关联角色
              </Button>
              <Button variant="outline" size="sm" disabled={selectedIds.size === 0} onClick={() => setBatchRefOpen("scenes")}>
                <Map className="h-3 w-3" /> 关联场景
              </Button>
              <Button variant="outline" size="sm" disabled={selectedIds.size === 0} onClick={() => setBatchRefOpen("props")}>
                <Package className="h-3 w-3" /> 关联道具
              </Button>
            </div>
          </>
        ) : (
          <Button variant="outline" size="sm" onClick={() => setSelectMode(true)}>
            <CheckSquare className="h-3.5 w-3.5" />
            多选
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={() => setCreateShotOpen(true)}>
          <Plus className="h-3.5 w-3.5" />
          新增分镜
        </Button>
      </div>

      {/* 批量关联对话框 */}
      {batchRefOpen && (
        <BatchReferenceDialog
          open={!!batchRefOpen}
          onOpenChange={(v) => !v && setBatchRefOpen(null)}
          type={batchRefOpen}
          projectId={projectId}
          shotIds={Array.from(selectedIds)}
          onClose={() => setBatchRefOpen(null)}
        />
      )}

      <Dialog open={createShotOpen} onOpenChange={setCreateShotOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>新增分镜</DialogTitle>
            <DialogDescription>在当前剧集下创建一个新分镜</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>分镜号 *</Label>
              <Input
                type="number"
                min={1}
                value={shotForm.shot_no}
                onChange={(e) => setShotForm({ ...shotForm, shot_no: parseInt(e.target.value) || 1 })}
              />
            </div>
            <div className="space-y-2">
              <Label>描述</Label>
              <Textarea
                value={shotForm.summary}
                onChange={(e) => setShotForm({ ...shotForm, summary: e.target.value })}
                rows={3}
                placeholder="本分镜的画面描述"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateShotOpen(false)}>取消</Button>
            <Button disabled={createShotMutation.isPending} onClick={handleCreateShot}>
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <GenerateDialog
        open={generateOpen}
        onOpenChange={setGenerateOpen}
        projectId={projectId}
        targets={generateTargets}
        defaultPrompt={generatePrompt}
      />
    </div>
  );
}

const genStatusBadge: Record<GenStatus, {
  label: string;
  variant: "secondary" | "warning" | "success" | "destructive" | "default";
}> = {
  none: { label: "未生成", variant: "secondary" },
  pending: { label: "等待中", variant: "default" },
  generating: { label: "生成中", variant: "warning" },
  ready: { label: "已就绪", variant: "success" },
  failed: { label: "失败", variant: "destructive" },
};

function ShotItem({
  shot,
  projectId,
  onUpdate,
  onGenerate,
  onDelete,
}: {
  shot: Shot;
  projectId: string;
  onUpdate: (payload: Partial<Shot>) => void;
  onGenerate: (targetType: "shot_first_frame" | "shot_last_frame" | "shot_video", prompt?: string) => void;
  onDelete: () => void;
}) {
  return (
    <div className="rounded-lg border p-4">
      {/* 标题行：分镜号 + 摘要 + 关联引用 + 删除按钮 */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Badge variant="outline" className="shrink-0">分镜 {shot.shot_no}</Badge>
          {shot.summary && <span className="truncate text-sm text-muted-foreground">{shot.summary}</span>}
          {/* 关联引用内联到标题行 */}
          <ShotReferenceInline shotId={shot.id} projectId={projectId} />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0 hover:text-destructive"
          onClick={onDelete}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {/* 首帧 */}
        <FrameBlock
          title="首帧"
          icon={ImageIcon}
          prompt={shot.first_frame_prompt || ""}
          assetId={shot.first_frame_asset_id}
          status={shot.first_frame_status}
          onPromptChange={(v) => onUpdate({ first_frame_prompt: v })}
          onGenerate={() => onGenerate("shot_first_frame", shot.first_frame_prompt || undefined)}
        />
        {/* 尾帧 */}
        <FrameBlock
          title="尾帧"
          icon={ImageIcon}
          prompt={shot.last_frame_prompt || ""}
          assetId={shot.last_frame_asset_id}
          status={shot.last_frame_status}
          onPromptChange={(v) => onUpdate({ last_frame_prompt: v })}
          onGenerate={() => onGenerate("shot_last_frame", shot.last_frame_prompt || undefined)}
        />
        {/* 视频 */}
        <FrameBlock
          title="视频"
          icon={Video}
          prompt={shot.video_prompt || ""}
          assetId={shot.video_asset_id}
          status={shot.video_status}
          isVideo
          onPromptChange={(v) => onUpdate({ video_prompt: v })}
          onGenerate={() => onGenerate("shot_video", shot.video_prompt || undefined)}
        />
      </div>
    </div>
  );
}

/** 分镜关联引用（内联到标题行）：紧凑显示角色/场景/道具标签。 */
function ShotReferenceInline({ shotId, projectId }: { shotId: string; projectId: string }) {
  const { data: refs, isLoading } = useShotReferences(shotId);
  const [pickerOpen, setPickerOpen] = useState<"characters" | "scenes" | "props" | null>(null);

  if (isLoading) return null;

  return (
    <>
      <div className="flex shrink-0 items-center gap-1">
        {/* 已关联的标签（紧凑显示） */}
        {refs?.characters?.map((item) => (
          <ReferenceInlineTag key={`c-${item.id}`} item={item} shotId={shotId} type="characters" />
        ))}
        {refs?.scenes?.map((item) => (
          <ReferenceInlineTag key={`s-${item.id}`} item={item} shotId={shotId} type="scenes" />
        ))}
        {refs?.props?.map((item) => (
          <ReferenceInlineTag key={`p-${item.id}`} item={item} shotId={shotId} type="props" />
        ))}
        {/* 添加按钮 */}
        <Button variant="ghost" size="sm" className="h-5 shrink-0 px-1 text-muted-foreground" onClick={() => setPickerOpen("characters")}>
          <Users className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="sm" className="h-5 shrink-0 px-1 text-muted-foreground" onClick={() => setPickerOpen("scenes")}>
          <Map className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="sm" className="h-5 shrink-0 px-1 text-muted-foreground" onClick={() => setPickerOpen("props")}>
          <Package className="h-3 w-3" />
        </Button>
      </div>

      {/* 实体选择器对话框 */}
      {pickerOpen && (
        <EntityPickerDialog
          open={!!pickerOpen}
          onOpenChange={(v) => !v && setPickerOpen(null)}
          type={pickerOpen}
          projectId={projectId}
          shotId={shotId}
        />
      )}
    </>
  );
}

/** 内联关联标签（紧凑版，带删除）。 */
function ReferenceInlineTag({
  item,
  shotId,
  type,
}: {
  item: ShotReferenceEntity;
  shotId: string;
  type: "characters" | "scenes" | "props";
}) {
  const removeCharacterMutation = useRemoveShotCharacter(shotId);
  const removeSceneMutation = useRemoveShotScene(shotId);
  const removePropMutation = useRemoveShotProp(shotId);

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (type === "characters") removeCharacterMutation.mutate(item.id);
    else if (type === "scenes") removeSceneMutation.mutate(item.id);
    else removePropMutation.mutate(item.id);
  };

  return (
    <Badge
      variant="secondary"
      className="cursor-default gap-0.5 px-1.5 py-0 text-xs"
    >
      {item.name}
      <button className="ml-0.5 hover:text-destructive" onClick={handleRemove}>
        <X className="h-2.5 w-2.5" />
      </button>
    </Badge>
  );
}

/** 实体选择器对话框：从项目实体列表中选择并关联到分镜。 */
function EntityPickerDialog({
  open,
  onOpenChange,
  type,
  projectId,
  shotId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  type: "characters" | "scenes" | "props";
  projectId: string;
  shotId: string;
}) {
  const { data: characters } = useCharacters(projectId);
  const { data: scenes } = useScenes(projectId);
  const { data: props } = useProps(projectId);

  const addCharsMutation = useAddShotCharacters(shotId);
  const addScenesMutation = useAddShotScenes(shotId);
  const addPropsMutation = useAddShotProps(shotId);

  const [selected, setSelected] = useState<Set<string>>(new Set());

  const items =
    type === "characters" ? (characters || []) :
    type === "scenes" ? (scenes || []) :
    (props || []);

  const titleMap = { characters: "选择角色", scenes: "选择场景", props: "选择道具" };

  const handleConfirm = () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    if (type === "characters") addCharsMutation.mutate(ids);
    else if (type === "scenes") addScenesMutation.mutate(ids);
    else addPropsMutation.mutate(ids);
    setSelected(new Set());
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{titleMap[type]}</DialogTitle>
          <DialogDescription>选择要关联到此分镜的实体</DialogDescription>
        </DialogHeader>
        <div className="max-h-64 space-y-1 overflow-y-auto py-2">
          {items.map((item: { id: string; name: string }) => (
            <label
              key={item.id}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 hover:bg-muted",
                selected.has(item.id) && "bg-muted"
              )}
            >
              <Checkbox
                checked={selected.has(item.id)}
                onChange={() => {
                  setSelected((prev) => {
                    const next = new Set(prev);
                    if (next.has(item.id)) next.delete(item.id);
                    else next.add(item.id);
                    return next;
                  });
                }}
              />
              <span className="text-sm">{item.name}</span>
            </label>
          ))}
          {items.length === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无可选实体</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={selected.size === 0} onClick={handleConfirm}>
            添加 {selected.size > 0 ? `(${selected.size})` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FrameBlock({
  title,
  icon: Icon,
  prompt,
  assetId,
  status,
  isVideo,
  onPromptChange,
  onGenerate,
}: {
  title: string;
  icon: React.ElementType;
  prompt: string;
  assetId?: string;
  status: GenStatus;
  isVideo?: boolean;
  onPromptChange: (v: string) => void;
  onGenerate: () => void;
}) {
  const badge = genStatusBadge[status];
  const showBadge = status !== "none";
  // 本地编辑状态：输入时不触发 API，失焦时才提交
  const [localPrompt, setLocalPrompt] = useState(prompt);
  const [dirty, setDirty] = useState(false);

  // 外部 prompt 变化时同步到本地（如其他地方更新了提示词）
  useEffect(() => {
    if (!dirty) {
      setLocalPrompt(prompt);
    }
  }, [prompt, dirty]);

  const handleBlur = () => {
    if (dirty && localPrompt !== prompt) {
      onPromptChange(localPrompt);
    }
    setDirty(false);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-sm font-medium">
          <Icon className="h-3.5 w-3.5" />
          {title}
        </div>
        {showBadge && <Badge variant={badge.variant} className="text-xs">{badge.label}</Badge>}
      </div>
      <div className={cn("group relative flex aspect-video items-center justify-center overflow-hidden rounded-md border bg-muted")}>
        {assetId ? (
          <>
            {isVideo ? (
              <video src={`/api/assets/${assetId}/file`} className="h-full w-full object-cover" muted playsInline />
            ) : (
              <img src={`/api/assets/${assetId}/file`} alt={title} className="h-full w-full object-cover" />
            )}
            {/* 有内容时，在左上角显示重新生成按钮 */}
            <Button
              variant="secondary"
              size="sm"
              className="absolute left-1 top-1 h-6 gap-1 px-2 text-xs opacity-0 transition-opacity hover:opacity-100 group-hover:opacity-100"
              onClick={onGenerate}
            >
              {isVideo ? <Video className="h-2.5 w-2.5" /> : <RefreshCw className="h-2.5 w-2.5" />}
              {isVideo ? "生成视频" : "生成图片"}
            </Button>
          </>
        ) : (
          /* 无内容时，生成按钮替换未生成占位符 */
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5 text-xs text-muted-foreground"
            onClick={onGenerate}
          >
            {isVideo ? <Video className="h-3 w-3" /> : <RefreshCw className="h-3 w-3" />}
            {isVideo ? "生成视频" : "生成图片"}
          </Button>
        )}
      </div>
      <Textarea
        value={localPrompt}
        onChange={(e) => { setLocalPrompt(e.target.value); setDirty(true); }}
        onBlur={handleBlur}
        placeholder={`${title}提示词...`}
        rows={2}
        className="text-xs"
      />
    </div>
  );
}

/** 批量关联对话框：为多个分镜批量添加关联的角色/场景/道具。 */
function BatchReferenceDialog({
  open,
  onOpenChange,
  type,
  projectId,
  shotIds,
  onClose,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  type: "characters" | "scenes" | "props";
  projectId: string;
  shotIds: string[];
  onClose: () => void;
}) {
  const { data: characters } = useCharacters(projectId);
  const { data: scenes } = useScenes(projectId);
  const { data: props } = useProps(projectId);
  const qc = useQueryClient();

  const [selected, setSelected] = useState<Set<string>>(new Set());

  const items =
    type === "characters" ? (characters || []) :
    type === "scenes" ? (scenes || []) :
    (props || []);

  const titleMap = { characters: "批量关联角色", scenes: "批量关联场景", props: "批量关联道具" };
  const descMap = { characters: "选中的角色将关联到所有已选分镜", scenes: "选中的场景将关联到所有已选分镜", props: "选中的道具将关联到所有已选分镜" };

  const batchMutation = useMutation({
    mutationFn: async (entityIds: string[]) => {
      const results: { shotId: string; ok: boolean }[] = [];
      for (const shotId of shotIds) {
        let promise: Promise<unknown>;
        if (type === "characters") {
          promise = shotReferencesApi.addCharacters(shotId, entityIds);
        } else if (type === "scenes") {
          promise = shotReferencesApi.addScenes(shotId, entityIds);
        } else {
          promise = shotReferencesApi.addProps(shotId, entityIds);
        }
        try {
          await promise;
          results.push({ shotId, ok: true });
        } catch {
          results.push({ shotId, ok: false });
        }
      }
      return results;
    },
    onSuccess: (results) => {
      // 刷新所有分镜的关联引用缓存
      for (const shotId of shotIds) {
        qc.invalidateQueries({ queryKey: ["shot-references", shotId] });
      }
      const okCount = results.filter((r) => r.ok).length;
      const failCount = results.length - okCount;
      const typeLabel = type === "characters" ? "角色" : type === "scenes" ? "场景" : "道具";
      if (failCount === 0) {
        toast.success(`已为 ${okCount} 个分镜批量关联${typeLabel}`);
      } else {
        toast.warning(`批量关联${typeLabel}：成功 ${okCount} 个，失败 ${failCount} 个`);
      }
      setSelected(new Set());
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleConfirm = () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    batchMutation.mutate(ids);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{titleMap[type]}</DialogTitle>
          <DialogDescription>{descMap[type]}（共 {shotIds.length} 个分镜）</DialogDescription>
        </DialogHeader>
        <div className="max-h-64 space-y-1 overflow-y-auto py-2">
          {items.map((item: { id: string; name: string }) => (
            <label
              key={item.id}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 hover:bg-muted",
                selected.has(item.id) && "bg-muted"
              )}
            >
              <Checkbox
                checked={selected.has(item.id)}
                onChange={() => {
                  setSelected((prev) => {
                    const next = new Set(prev);
                    if (next.has(item.id)) next.delete(item.id);
                    else next.add(item.id);
                    return next;
                  });
                }}
              />
              <span className="text-sm">{item.name}</span>
            </label>
          ))}
          {items.length === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无可选实体</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button disabled={selected.size === 0 || batchMutation.isPending} onClick={handleConfirm}>
            {batchMutation.isPending ? "关联中..." : `关联到 ${shotIds.length} 个分镜`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
