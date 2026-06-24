/** 首页：自动跳转到最近操作的项目，或显示新建项目弹窗。 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { FolderKanban, Plus } from "lucide-react";
import { PageContainer, EmptyState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { useProjects, useCreateProject } from "@/hooks/useProjects";

export function HomePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const shouldCreate = searchParams.get("create") === "1";
  const [createOpen, setCreateOpen] = useState(shouldCreate);

  const { data, isLoading } = useProjects({ page_size: 100 });
  const projects = data?.items || [];
  const createMutation = useCreateProject();

  // 自动跳转到最近操作的项目
  useEffect(() => {
    if (!isLoading && projects.length > 0 && !shouldCreate) {
      // 按 updated_at 排序取最新的
      const latest = [...projects].sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      )[0];
      navigate(`/projects/${latest.id}`, { replace: true });
    }
  }, [isLoading, projects, navigate, shouldCreate]);

  // 新建项目后跳转
  const handleCreate = async (name: string, description: string) => {
    try {
      const res = await createMutation.mutateAsync({ name, description });
      setCreateOpen(false);
      if (res.data?.id) navigate(`/projects/${res.data.id}`);
    } catch {
      // mutateAsync 失败已由 React Query onError 回调处理（显示 toast）
    }
  };

  return (
    <PageContainer title="AI Drama Studio" description="选择一个项目开始创作">
      {isLoading ? (
        <EmptyState icon={FolderKanban} title="加载中..." description="正在获取项目列表" />
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 py-20">
          <EmptyState
            icon={FolderKanban}
            title="还没有项目"
            description="创建你的第一个 AI 剧集创作项目"
          />
          <div className="flex items-center gap-3">
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              新建项目
            </Button>
            <Button variant="outline" asChild>
              <Link to="/projects">
                <FolderKanban className="h-4 w-4" />
                项目管理
              </Link>
            </Button>
          </div>
        </div>
      ) : (
        !shouldCreate && (
          <p className="text-muted-foreground">正在跳转到最近操作的项目...</p>
        )
      )}

      <CreateProjectDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={handleCreate}
      />
    </PageContainer>
  );
}

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
