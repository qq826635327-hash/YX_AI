/** 批量关联对话框：为多个分镜批量添加关联的角色/场景/道具。 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { toast } from "@/stores/ui";
import {
  useCharacters,
  useScenes,
  useProps,
} from "@/hooks/useBusiness";
import { shotReferencesApi } from "@/api/shotReferences";

export default function BatchReferenceDialog({
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
