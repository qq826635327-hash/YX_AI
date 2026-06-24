/** 分镜列表组件：管理单个剧集下的所有分镜，含拖拽排序、批量操作、生成对话框。 */

import { useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Image as ImageIcon,
  Video,
  Plus,
  CheckSquare,
  X,
  Users,
  Map,
  Package,
  Link2,
} from "lucide-react";
import { LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { toast } from "@/stores/ui";
import { useConfirm } from "@/components/ConfirmDialog";
import {
  useShots,
  useUpdateShot,
  useCreateShot,
  useDeleteShot,
} from "@/hooks/useBusiness";
import { shotsApi } from "@/api/episodes";
import type { Shot, TargetType } from "@/types";
import { GenerateDialog, type GenerateTarget } from "@/components/GenerateDialog";
import ShotItem from "./ShotItem";
import BatchReferenceDialog from "./BatchReferenceDialog";

export default function ShotsList({ episodeId, projectId }: { episodeId: string; projectId: string }) {
  const confirm = useConfirm();
  const { data: shots, isLoading } = useShots(episodeId);
  const updateMutation = useUpdateShot(projectId);
  const createShotMutation = useCreateShot(projectId);
  const deleteShotMutation = useDeleteShot(projectId);
  const qc = useQueryClient();

  const [createShotOpen, setCreateShotOpen] = useState(false);
  const [shotForm, setShotForm] = useState({ shot_no: 1, summary: "" });
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [generateTargets, setGenerateTargets] = useState<GenerateTarget[]>([]);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState<string>();
  const [batchRefOpen, setBatchRefOpen] = useState<"characters" | "scenes" | "props" | null>(null);

  // 拖拽排序状态
  const [draggedShotId, setDraggedShotId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);

  // 分镜排序 mutation
  const reorderMutation = useMutation({
    mutationFn: (items: { id: string; sort_order: number }[]) =>
      shotsApi.reorder(episodeId, items),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shots", episodeId] });
      toast.success("分镜顺序已更新");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleCreateShot = async () => {
    try {
      await createShotMutation.mutateAsync({
        episodeId,
        payload: {
          shot_no: shotForm.shot_no,
          summary: shotForm.summary.trim() || undefined,
        },
      });
      setCreateShotOpen(false);
      // 后端已自动重排编号，刷新列表即可
      qc.invalidateQueries({ queryKey: ["shots", episodeId] });
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

  // 稳定化回调：传给 ShotItem 的 memo 才能真正生效
  const handleUpdateShot = useCallback(
    (id: string, payload: Partial<Shot>) => updateMutation.mutate({ id, payload }),
    [updateMutation],
  );

  const handleShotGenerate = useCallback(
    (id: string, targetType: "shot_first_frame" | "shot_last_frame" | "shot_video", prompt?: string) => {
      const shot = allShots.find((s) => s.id === id);
      if (!shot) return;
      setGenerateTargets([{
        target_type: targetType,
        target_id: shot.id,
        name: `分镜${String(shot.shot_no).padStart(2, "0")}`,
        prompt,
        firstFrameAssetId: shot.first_frame_asset_id,
      }]);
      setGeneratePrompt(prompt);
      setGenerateOpen(true);
    },
    [allShots],
  );

  const handleDeleteShot = useCallback(
    async (id: string) => {
      const shot = allShots.find((s) => s.id === id);
      const label = shot ? `分镜 ${String(shot.shot_no).padStart(2, "0")}` : "该分镜";
      if (await confirm({ title: `确认删除${label}？`, variant: "destructive" })) {
        deleteShotMutation.mutate(id);
      }
    },
    [allShots, deleteShotMutation],
  );

  // 拖拽排序：放下时计算新 sort_order 并调用 API
  const handleDrop = (targetShotId: string) => {
    if (!draggedShotId || draggedShotId === targetShotId) {
      setDraggedShotId(null);
      setDropTargetId(null);
      return;
    }
    const draggedIndex = allShots.findIndex((s) => s.id === draggedShotId);
    const targetIndex = allShots.findIndex((s) => s.id === targetShotId);
    if (draggedIndex === -1 || targetIndex === -1) return;

    // 重新排列数组
    const reordered = [...allShots];
    const [draggedItem] = reordered.splice(draggedIndex, 1);
    reordered.splice(targetIndex, 0, draggedItem);

    // 分配新的 sort_order
    const items = reordered.map((s, i) => ({ id: s.id, sort_order: i + 1 }));
    reorderMutation.mutate(items);
    setDraggedShotId(null);
    setDropTargetId(null);
  };

  // 在指定位置插入分镜
  const handleInsertShot = (position: number) => {
    setShotForm({ shot_no: position, summary: "" });
    setCreateShotOpen(true);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === allShots.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(allShots.map((s) => s.id)));
    }
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
      name: `分镜${String(s.shot_no).padStart(2, "0")}`,
      prompt: (s[promptField] as string) || s.summary || undefined,
      firstFrameAssetId: s.first_frame_asset_id,
    })));
    setGeneratePrompt(undefined);
    setGenerateOpen(true);
  };

  if (isLoading) return <LoadingState />;

  return (
    <div className="space-y-3">
      {/* 操作栏固定顶部 */}
      <div className="sticky top-0 z-10 -mx-4 -mt-4 mb-3 border-b border-border/60 bg-card/95 backdrop-blur px-4 py-2">
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
      </div>

      {(shots || []).length > 0 &&
        (shots as Shot[]).map((shot, index) => (
          <div key={shot.id}>
            {/* 分镜之间的插入按钮 */}
            <div
              className="group flex items-center justify-center py-0.5"
            >
              <Button
                variant="ghost"
                size="sm"
                className="h-5 gap-1 px-2 text-xs text-primary/80 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-primary/10 hover:text-primary"
                onClick={() => handleInsertShot(index + 1)}
              >
                <Plus className="h-3 w-3" />
                在此插入
              </Button>
            </div>
            <div
              className={cn(
                "relative transition-shadow",
                selectMode && "cursor-pointer",
                selectedIds.has(shot.id) && "ring-2 ring-primary rounded-lg",
                draggedShotId === shot.id && "opacity-40",
                dropTargetId === shot.id && "shadow-md ring-2 ring-primary/50 rounded-lg",
              )}
              style={{ contentVisibility: "auto", containIntrinsicSize: "320px" }}
              onClick={selectMode ? () => toggleSelect(shot.id) : undefined}
              draggable={!selectMode}
              onDragStart={(e) => {
                if (selectMode) { e.preventDefault(); return; }
                setDraggedShotId(shot.id);
                e.dataTransfer.effectAllowed = "move";
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                setDropTargetId(shot.id);
              }}
              onDragLeave={() => {
                setDropTargetId(null);
              }}
              onDrop={(e) => {
                e.preventDefault();
                handleDrop(shot.id);
              }}
              onDragEnd={() => {
                setDraggedShotId(null);
                setDropTargetId(null);
              }}
            >
              {selectMode && (
                <div className="absolute left-2 top-2 z-10">
                  <Checkbox checked={selectedIds.has(shot.id)} onChange={() => toggleSelect(shot.id)} onClick={(e) => e.stopPropagation()} />
                </div>
              )}
              <ShotItem
                shot={shot}
                projectId={projectId}
                showDragHandle={!selectMode}
                onUpdate={handleUpdateShot}
                onGenerate={handleShotGenerate}
                onDelete={handleDeleteShot}
              />
            </div>
          </div>
        ))}

      {/* 末尾插入按钮 */}
      {(shots || []).length > 0 && (
        <div className="group flex items-center justify-center py-0.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-5 gap-1 px-2 text-xs text-primary/80 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-primary/10 hover:text-primary"
            onClick={() => handleInsertShot(allShots.length + 1)}
          >
            <Plus className="h-3 w-3" />
            在此插入
          </Button>
        </div>
      )}

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
