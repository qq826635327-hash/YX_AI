/** 编辑项目弹窗：修改名称、描述、画风、状态。 */

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { useUpdateProject } from "@/hooks/useProjects";
import { useStylePresets } from "@/hooks/useApi";
import type { Project, ProjectUpdate } from "@/types";

interface EditProjectDialogProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  project: Project;
}

export function EditProjectDialog({ open, onOpenChange, project }: EditProjectDialogProps) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description || "");
  const [stylePreset, setStylePreset] = useState(project.style_preset === "default" ? "" : (project.style_preset || ""));
  const [status, setStatus] = useState(project.status);
  const updateMutation = useUpdateProject();
  const { data: stylePresets } = useStylePresets();

  // 项目切换时同步表单
  useEffect(() => {
    setName(project.name);
    setDescription(project.description || "");
    setStylePreset(project.style_preset === "default" ? "" : (project.style_preset || ""));
    setStatus(project.status);
  }, [project]);

  const handleSubmit = () => {
    if (!name.trim()) return;
    const payload: ProjectUpdate = {};
    if (name.trim() !== project.name) payload.name = name.trim();
    if (description.trim() !== (project.description || "")) payload.description = description.trim() || undefined;
    if (stylePreset !== (project.style_preset || "")) payload.style_preset = stylePreset || undefined;
    if (status !== project.status) payload.status = status;

    // 没有变更则直接关闭
    if (Object.keys(payload).length === 0) {
      onOpenChange(false);
      return;
    }

    updateMutation.mutate(
      { id: project.id, payload },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  // 画风预置列表，按 sort_order 排序
  const presets = (stylePresets || [])
    .slice()
    .sort((a, b) => a.sort_order - b.sort_order);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑项目</DialogTitle>
          <DialogDescription>修改项目名称、描述、画风或状态</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="edit-name">项目名称</Label>
            <Input
              id="edit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="项目名称"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-desc">项目描述</Label>
            <Textarea
              id="edit-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="简单描述这个项目的主题、风格..."
              rows={3}
            />
          </div>
          <div className="space-y-2">
            <Label>画风预置</Label>
            <Select value={stylePreset || "__none__"} onValueChange={(v) => setStylePreset(v === "__none__" ? "" : v)}>
              <SelectTrigger>
                <SelectValue placeholder="选择画风" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">不指定</SelectItem>
                {presets.map((p) => (
                  <SelectItem key={p.id} value={p.title}>
                    {p.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              画风描述会自动注入提示词模板的 {`{{style_hint}}`} 占位符
            </p>
          </div>
          <div className="space-y-2">
            <Label>项目状态</Label>
            <Select value={status} onValueChange={(v) => setStatus(v as "active" | "archived")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">活跃</SelectItem>
                <SelectItem value="archived">已归档</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!name.trim() || updateMutation.isPending} onClick={handleSubmit}>
            {updateMutation.isPending ? "保存中..." : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
