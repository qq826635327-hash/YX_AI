/** 左侧导航栏：根据当前模块动态渲染菜单。 */

import { NavLink, useLocation } from "react-router-dom";
import {
  FileText, Users, Map, Package, Clapperboard,
  Loader2, CheckCircle2, XCircle, ListFilter,
  Server, Puzzle, Cog, FileEdit, Workflow,
  Sun, Moon, Monitor,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui";
import { Button } from "@/components/ui/button";
import { useParams } from "react-router-dom";
import { useMemo } from "react";

// 项目内容菜单
const projectNavItems = [
  { key: "script", label: "剧本", icon: FileText },
  { key: "characters", label: "角色", icon: Users },
  { key: "scenes", label: "场景", icon: Map },
  { key: "props", label: "道具", icon: Package },
  { key: "episodes", label: "剧集结构", icon: Clapperboard },
];

const tasksFilterItems = [
  { key: "all", label: "全部", icon: ListFilter, to: "/tasks", search: "?filter=all" },
  { key: "active", label: "进行中", icon: Loader2, to: "/tasks", search: "?filter=active" },
  { key: "completed", label: "已完成", icon: CheckCircle2, to: "/tasks", search: "?filter=completed" },
  { key: "failed", label: "失败", icon: XCircle, to: "/tasks", search: "?filter=failed" },
  { key: "cancelled", label: "已取消", icon: XCircle, to: "/tasks", search: "?filter=cancelled" },
];

// 配置中心菜单
const configNavItems = [
  { key: "api", label: "API 供应商", icon: Server, to: "/settings/api" },
  { key: "plugins", label: "插件扩展", icon: Puzzle, to: "/settings/plugins" },
  { key: "models", label: "模型配置", icon: Cog, to: "/settings/models" },
  { key: "prompts", label: "提示词模版", icon: FileEdit, to: "/settings/prompts" },
  { key: "comfyui-servers", label: "ComfyUI 服务器", icon: Server, to: "/settings/comfyui-servers" },
  { key: "comfyui-workflows", label: "ComfyUI 工作流", icon: Workflow, to: "/settings/comfyui-workflows" },
];

export function Sidebar() {
  const location = useLocation();
  const { theme, setTheme } = useUiStore();
  const { projectId } = useParams();

  // 根据当前路由自动判断激活模块（刷新页面时 store 会重置，路由更可靠）
  const activeModule = useMemo<"project" | "tasks" | "config">(() => {
    if (location.pathname.startsWith("/tasks")) return "tasks";
    if (location.pathname.startsWith("/settings")) return "config";
    return "project";
  }, [location.pathname]);

  const ThemeIcon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;

  const cycleTheme = () => {
    const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
    setTheme(next);
  };

  // 根据模块选择菜单数据
  let navItems: { key: string; label: string; icon: React.ElementType; to: string; search?: string }[] = [];
  let groupTitle = "";

  if (activeModule === "project") {
    navItems = projectNavItems.map((item) => ({
      ...item,
      to: projectId ? `/projects/${projectId}/${item.key}` : "#",
    }));
    groupTitle = "项目内容";
  } else if (activeModule === "tasks") {
    groupTitle = "任务中心";
  } else if (activeModule === "config") {
    navItems = configNavItems;
    groupTitle = "配置中心";
  }

  return (
    <aside className="flex h-full w-52 flex-col border-r bg-card">
      {/* 导航区域 */}
      <nav className="flex-1 overflow-y-auto p-3">
        {activeModule === "tasks" ? (
          <>
            <div className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              状态过滤
            </div>
            <div className="space-y-0.5">
              {tasksFilterItems.map((item) => (
                <NavItem
                  key={item.key}
                  to={item.to}
                  search={item.search}
                  label={item.label}
                  icon={item.icon}
                />
              ))}
            </div>
          </>
        ) : (
          <>
            {/* 分组标题 */}
            <div className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {groupTitle}
            </div>

            {/* 菜单项 */}
            <div className="space-y-0.5">
              {navItems.map((item) => {
                const isDisabled = item.to === "#";
                return (
                  <NavItem
                    key={item.key}
                    to={item.to}
                    search={item.search}
                    label={item.label}
                    icon={item.icon}
                    disabled={isDisabled}
                  />
                );
              })}
            </div>

            {activeModule === "project" && !projectId && (
              <p className="mt-4 px-3 text-xs text-muted-foreground">请先选择一个项目</p>
            )}
          </>
        )}
      </nav>

      {/* 底部：主题切换 */}
      <div className="border-t p-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={cycleTheme}
          className="w-full justify-start gap-2"
          title={`主题: ${theme}`}
        >
          <ThemeIcon className="h-4 w-4" />
          <span className="text-xs">
            {theme === "light" ? "浅色模式" : theme === "dark" ? "深色模式" : "跟随系统"}
          </span>
        </Button>
      </div>
    </aside>
  );
}

interface NavItemProps {
  to: string;
  search?: string;
  label: string;
  icon: React.ElementType;
  disabled?: boolean;
}

function NavItem({ to, search, label, icon: Icon, disabled }: NavItemProps) {
  const location = useLocation();
  const targetSearch = search ?? "";
  const isActive = location.pathname === to && location.search === targetSearch;

  const className = cn(
    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
    isActive
      ? "bg-primary text-primary-foreground"
      : disabled
        ? "text-muted-foreground/50 cursor-not-allowed pointer-events-none"
        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
  );

  // 禁用项或占位符 # 不渲染 NavLink，避免 react-router 解析 # 报错
  if (disabled || to === "#") {
    return (
      <div className={className}>
        <Icon className="h-4 w-4 shrink-0" />
        <span>{label}</span>
      </div>
    );
  }

  return (
    <NavLink
      to={{ pathname: to, search: targetSearch || undefined }}
      end={false}
      className={className}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span>{label}</span>
    </NavLink>
  );
}
