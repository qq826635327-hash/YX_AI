/** 分镜关联引用（内联到标题行）：紧凑显示角色/场景/道具标签，及实体选择器对话框。 */

import { useState } from "react";
import { Users, Map, Package, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import {
  useShotReferences,
  useCharacters,
  useScenes,
  useProps,
  useAddShotCharacters,
  useAddShotScenes,
  useAddShotProps,
  useRemoveShotCharacter,
  useRemoveShotScene,
  useRemoveShotProp,
} from "@/hooks/useBusiness";
import type { ShotReferenceEntity } from "@/types";

/** 分镜关联引用（内联到标题行）：紧凑显示角色/场景/道具标签。 */
export default function ShotReferenceInline({ shotId, projectId }: { shotId: string; projectId: string }) {
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
export function ReferenceInlineTag({
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
export function EntityPickerDialog({
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
