/** 删除项目确认弹窗。 */

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useDeleteProject } from "@/hooks/useProjects";
import type { Project } from "@/types";

interface DeleteProjectDialogProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  project: Project;
  onDeleted?: () => void;
}

export function DeleteProjectDialog({ open, onOpenChange, project, onDeleted }: DeleteProjectDialogProps) {
  const [deleteFiles, setDeleteFiles] = useState(false);
  const deleteMutation = useDeleteProject();

  const handleDelete = () => {
    deleteMutation.mutate(
      { id: project.id, deleteFiles },
      {
        onSuccess: () => {
          onOpenChange(false);
          onDeleted?.();
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            删除项目
          </DialogTitle>
          <DialogDescription>此操作不可撤销，请确认</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <p className="text-sm">
            确定要删除项目 <strong className="text-foreground">{project.name}</strong> 吗？
          </p>
          <p className="text-xs text-muted-foreground">
            项目内包含 {project.character_count} 个角色、{project.scene_count} 个场景、{project.shot_count} 个分镜。
          </p>
          <label className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
            <Checkbox
              checked={deleteFiles}
              onCheckedChange={setDeleteFiles}
              className="mt-0.5"
            />
            <div>
              <p className="text-sm font-medium text-destructive">同时删除项目文件</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                勾选后将删除项目目录下的所有文件（图片、视频等），此操作不可恢复
              </p>
            </div>
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button
            variant="destructive"
            disabled={deleteMutation.isPending}
            onClick={handleDelete}
          >
            {deleteMutation.isPending ? "删除中..." : "确认删除"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
