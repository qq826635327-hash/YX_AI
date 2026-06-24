/** 项目管理页：展示所有项目的卡片列表，支持搜索、筛选、编辑、删除。 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FolderKanban, Plus, Search, Pencil, Trash2, Archive, ArchiveRestore,
  Users, Map, Package, ListTodo,
} from "lucide-react";
import { PageContainer, EmptyState, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/utils";
import { useProjects, useCreateProject, useUpdateProject } from "@/hooks/useProjects";
import { EditProjectDialog } from "@/components/EditProjectDialog";
import { DeleteProjectDialog } from "@/components/DeleteProjectDialog";
import type { Project } from "@/types";

// 状态筛选选项
const statusTabs = [
  { key: "", label: "全部" },
  { key: "active", label: "活跃" },
  { key: "archived", label: "已归档" },
] as const;

export function ProjectListPage() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editProject, setEditProject] = useState<Project | null>(null);
  const [deleteProject, setDeleteProject] = useState<Project | null>(null);

  const { data, isLoading } = useProjects({
    keyword: keyword || undefined,
    status: statusFilter || undefined,
    page_size: 100,
  });
  const projects = data?.items || [];
  const createMutation = useCreateProject();

  const handleCreate = async (name: string, description: string) => {
    try {
      const res = await createMutation.mutateAsync({ name, description });
      setCreateOpen(false);
      if (res.data?.id) navigate(`/projects/${res.data.id}`);
    } catch {
      /* toast 已由 hook 处理 */
    }
  };

  return (
    <PageContainer
      title="项目管理"
      description="管理你的所有创作项目"
      actions={
        <Button onClick={() => setCreateOpen(true)} className="gap-1">
          <Plus className="h-4 w-4" />
          新建项目
        </Button>
      }
    >
      {/* 搜索 + 筛选栏 */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索项目名称..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-1 rounded-lg border bg-card p-1">
          {statusTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setStatusFilter(tab.key)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                statusFilter === tab.key
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 项目卡片列表 */}
      {isLoading ? (
        <LoadingState />
      ) : projects.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title={keyword || statusFilter ? "没有匹配的项目" : "还没有项目"}
          description={keyword || statusFilter ? "尝试调整搜索条件" : "点击上方按钮创建你的第一个项目"}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onOpen={() => navigate(`/projects/${project.id}`)}
              onEdit={() => setEditProject(project)}
              onDelete={() => setDeleteProject(project)}
            />
          ))}
        </div>
      )}

      {/* 新建项目弹窗 */}
      <CreateProjectDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={handleCreate}
      />

      {/* 编辑项目弹窗 */}
      {editProject && (
        <EditProjectDialog
          open={!!editProject}
          onOpenChange={(v) => { if (!v) setEditProject(null); }}
          project={editProject}
        />
      )}

      {/* 删除项目弹窗 */}
      {deleteProject && (
        <DeleteProjectDialog
          open={!!deleteProject}
          onOpenChange={(v) => { if (!v) setDeleteProject(null); }}
          project={deleteProject}
          onDeleted={() => setDeleteProject(null)}
        />
      )}
    </PageContainer>
  );
}

/** 项目卡片。 */
function ProjectCard({
  project,
  onOpen,
  onEdit,
  onDelete,
}: {
  project: Project;
  onOpen: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const updateMutation = useUpdateProject();
  const isArchived = project.status === "archived";

  // 归档/取消归档
  const toggleArchive = (e: React.MouseEvent) => {
    e.stopPropagation();
    updateMutation.mutate({
      id: project.id,
      payload: { status: isArchived ? "active" : "archived" },
    });
  };

  const stats = [
    { icon: Users, label: "角色", value: project.character_count },
    { icon: Map, label: "场景", value: project.scene_count },
    { icon: Package, label: "道具", value: project.prop_count },
    { icon: ListTodo, label: "分镜", value: project.shot_count },
  ];

  return (
    <Card
      className={cn(
        "group cursor-pointer border-border/60 bg-card transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/5 hover:ring-1 hover:ring-primary/30",
        isArchived && "opacity-60"
      )}
      onClick={onOpen}
    >
      <CardContent className="p-4">
        {/* 标题行 */}
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-base font-semibold">{project.name}</h3>
            {project.description ? (
              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{project.description}</p>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground/40 italic">暂无描述</p>
            )}
          </div>
          {isArchived && (
            <Badge variant="secondary" className="shrink-0 text-[10px]">已归档</Badge>
          )}
        </div>

        {/* 统计数据 */}
        <div className="mb-3 grid grid-cols-4 gap-1">
          {stats.map((s) => (
            <div key={s.label} className="flex flex-col items-center rounded-md bg-muted/50 py-1.5">
              <s.icon className="mb-0.5 h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-sm font-bold">{s.value}</span>
              <span className="text-[10px] text-muted-foreground">{s.label}</span>
            </div>
          ))}
        </div>

        {/* 底部：时间 + 操作 */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-muted-foreground">
            更新于 {formatTime(project.updated_at)}
          </span>
          <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
            <ActionButton icon={Pencil} label="编辑" onClick={onEdit} />
            <ActionButton
              icon={isArchived ? ArchiveRestore : Archive}
              label={isArchived ? "取消归档" : "归档"}
              onClick={toggleArchive}
            />
            <ActionButton icon={Trash2} label="删除" onClick={onDelete} destructive />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/** 卡片上的小操作按钮。 */
function ActionButton({
  icon: Icon,
  label,
  onClick,
  destructive,
}: {
  icon: React.ElementType;
  label: string;
  onClick: (e: React.MouseEvent) => void;
  destructive?: boolean;
}) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick(e);
      }}
      title={label}
      className={cn(
        "rounded-md p-1.5 transition-colors",
        destructive
          ? "text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          : "text-muted-foreground hover:bg-accent hover:text-foreground"
      )}
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

/** 新建项目弹窗（复用 HomePage 中的逻辑）。 */
function CreateProjectDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSubmit: (name: string, description: string) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建项目</DialogTitle>
          <DialogDescription>创建一个新的 AI 剧集创作项目</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="name">项目名称 *</Label>
            <Input
              id="name"
              placeholder="例如：末世余生 第一季"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="desc">项目描述</Label>
            <Textarea
              id="desc"
              placeholder="简单描述这个项目的主题、风格..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!name.trim()} onClick={() => onSubmit(name.trim(), description.trim())}>
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
