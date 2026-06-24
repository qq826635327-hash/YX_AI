/** 顶部栏：Logo + 项目切换标签 + 右侧固定按钮。 */

import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Film, ListTodo, Settings, Plus, Activity, FolderKanban } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import { useProjects } from "@/hooks/useProjects";
import { useUiStore } from "@/stores/ui";
import { TaskCenter } from "@/components/TaskCenter";
import { PerfMonitor } from "@/components/PerfMonitor";

export function TopBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data } = useProjects({ page_size: 100 });
  const projects = data?.items || [];
  const setActiveModule = useUiStore((s) => s.setActiveModule);
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [perfDialogOpen, setPerfDialogOpen] = useState(false);

  // 从 URL 判断当前激活的项目 ID
  const activeId = extractProjectId(location.pathname);

  return (
    <>
      <header className="flex h-14 items-center justify-between border-b bg-card px-4">
        {/* 左侧 Logo + 项目管理入口 */}
        <div className="flex items-center gap-2 shrink-0">
          <Film className="h-5 w-5 text-primary" />
          <span className="text-sm font-bold tracking-tight">AI Drama Studio</span>
          <button
            onClick={() => navigate("/projects")}
            className={cn(
              "ml-1 rounded-md p-1.5 transition-colors",
              location.pathname === "/projects"
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            )}
            title="项目管理"
          >
            <FolderKanban className="h-4 w-4" />
          </button>
        </div>

        {/* 中间：项目标签页 */}
        <div className="flex items-center gap-1 overflow-x-auto">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                setActiveModule("project");
                navigate(`/projects/${p.id}`);
              }}
              className={cn(
                "relative whitespace-nowrap rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
                p.id === activeId
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              <span>{p.name}</span>
              {p.id === activeId && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-primary" />
              )}
            </button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/?create=1")}
            className="shrink-0 h-7 gap-1 text-muted-foreground"
            title="新建项目"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* 右侧：性能监控 + 任务中心 + 配置中心 */}
        <div className="flex items-center gap-1 shrink-0">
          <TopBarButton
            icon={Activity}
            label="性能监控"
            isActive={false}
            onClick={() => setPerfDialogOpen(true)}
          />
          <TopBarButton
            icon={ListTodo}
            label="任务中心"
            isActive={false}
            onClick={() => setTaskDialogOpen(true)}
          />
          <TopBarButton
            icon={Settings}
            label="配置中心"
            isActive={location.pathname.startsWith("/settings")}
            onClick={() => {
              setActiveModule("config");
              navigate("/settings/api");
            }}
          />
        </div>
      </header>

      {/* 性能监控弹窗 */}
      <PerfMonitor open={perfDialogOpen} onOpenChange={setPerfDialogOpen} />

      {/* 任务中心弹窗 */}
      <Dialog open={taskDialogOpen} onOpenChange={setTaskDialogOpen}>
        <DialogContent className="w-[80vw] max-w-[80vw] max-h-[90vh] p-0 gap-0 overflow-hidden flex flex-col">
          <TaskCenter filter="all" />
        </DialogContent>
      </Dialog>
    </>
  );
}

/** 顶部栏右侧按钮 */
function TopBarButton({
  icon: Icon,
  label,
  isActive,
  onClick,
}: {
  icon: React.ElementType;
  label: string;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors",
        isActive
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:text-foreground hover:bg-accent"
      )}
    >
      <Icon className="h-4 w-4" />
      <span>{label}</span>
    </button>
  );
}

/** 从路径中提取 projectId */
function extractProjectId(pathname: string): string | null {
  const match = pathname.match(/^\/projects\/([^/]+)/);
  return match ? match[1] : null;
}
