/** 左侧导航栏：参考目标截图的深色影视工作台风格。 */

import { Link, useLocation, useParams } from "react-router-dom";
import {
  FileText, Users, Map, Package, Clapperboard,
  LayoutDashboard, Loader2, CheckCircle2, XCircle, ListFilter,
  Server, Cog, Workflow, BookOpen,
  Sun, Moon, Monitor, Activity,
  Pencil, Image,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui";
import { useMemo } from "react";
import { useEpisodes, useCharacters, useScenes, useProps } from "@/hooks/useBusiness";

// 项目内容菜单
const projectNavItems = [
  { key: "overview", label: "项目总览", icon: LayoutDashboard },
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
  { key: "image-hosting", label: "图床配置", icon: Image, to: "/settings/image-hosting" },
  { key: "models", label: "模型配置", icon: Cog, to: "/settings/models" },
  { key: "comfyui-workflows", label: "ComfyUI 工作流", icon: Workflow, to: "/settings/comfyui-workflows" },
  { key: "prompts", label: "提示词模版", icon: BookOpen, to: "/settings/prompts" },
  { key: "system-status", label: "系统状态", icon: Activity, to: "/settings/system-status" },
];

export function Sidebar() {
  const location = useLocation();
  const { theme, setTheme } = useUiStore();
  const { projectId } = useParams();

  // 根据当前路由自动判断激活模块
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

  // 各实体数量（不触发额外请求，复用已有列表缓存）
  const { data: characters } = useCharacters(projectId || "");
  const { data: scenes } = useScenes(projectId || "");
  const { data: props } = useProps(projectId || "");
  const counts: Record<string, number | undefined> = {
    characters: characters?.length,
    scenes: scenes?.length,
    props: props?.length,
  };

  // 根据模块选择菜单数据
  let navItems: { key: string; label: string; icon: React.ElementType; to: string; search?: string }[] = [];
  let groupTitle = "";

  if (activeModule === "project") {
    navItems = projectNavItems.map((item) => ({
      ...item,
      to: projectId
        ? item.key === "overview"
          ? `/projects/${projectId}`
          : `/projects/${projectId}/${item.key}`
        : "#",
    }));
    groupTitle = "项目内容";
  } else if (activeModule === "tasks") {
    groupTitle = "任务中心";
  } else if (activeModule === "config") {
    navItems = configNavItems;
    groupTitle = "配置中心";
  }

  // 判断当前是否在剧集页面
  const isEpisodesPage = location.pathname.includes("/episodes");

  return (
    <aside className="flex h-full w-56 flex-shrink-0 flex-col border-r border-border bg-[#0c0d11]">
      {/* 导航区域 */}
      <nav className="flex-1 overflow-y-auto p-3">
        {activeModule === "tasks" ? (
          <>
            <div className="mb-2 px-3 text-xs font-medium text-muted-foreground/60">状态过滤</div>
            <div className="space-y-1">
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
            <div className="mb-2 px-3 text-xs font-medium text-muted-foreground/60">{groupTitle}</div>

            {/* 菜单项 */}
            <div className="space-y-1">
              {navItems.map((item) => {
                const isDisabled = item.to === "#";
                return (
                  <div key={item.key}>
                    <NavItem
                      to={item.to}
                      search={item.search}
                      label={item.label}
                      icon={item.icon}
                      disabled={isDisabled}
                      badge={counts[item.key]}
                    />
                    {/* 剧集结构二级菜单 */}
                    {item.key === "episodes" && isEpisodesPage && projectId && (
                      <EpisodeSubNav projectId={projectId} />
                    )}
                  </div>
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
      <div className="border-t border-border/50 p-3">
        <button
          onClick={cycleTheme}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          title={`主题: ${theme}`}
        >
          <ThemeIcon className="h-4 w-4" />
          <span className="text-xs">
            {theme === "light" ? "浅色模式" : theme === "dark" ? "深色模式" : "跟随系统"}
          </span>
        </button>
      </div>
    </aside>
  );
}

/** 剧集二级子菜单 */
function EpisodeSubNav({ projectId }: { projectId: string }) {
  const { data: episodes } = useEpisodes(projectId);
  const location = useLocation();

  if (!episodes || episodes.length === 0) return null;

  return (
    <div className="ml-4 mt-1 space-y-1 border-l border-border pl-2">
      {episodes.map((ep) => {
        const to = `/projects/${projectId}/episodes?ep=${ep.id}`;
        const isActive = location.search === `?ep=${ep.id}`;
        return (
          <div
            key={ep.id}
            className={cn(
              "group flex items-center justify-between rounded-md px-2 py-1.5 text-xs transition-colors",
              isActive
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Link to={to} className="flex-1 truncate">
              第{ep.episode_no}集 {ep.title !== `第${ep.episode_no}集` ? ep.title : ""}
            </Link>
            <button
              className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100 hover:text-primary"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                window.dispatchEvent(new CustomEvent("episode:edit", { detail: ep.id }));
              }}
              title="编辑剧集"
            >
              <Pencil className="h-3 w-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

interface NavItemProps {
  to: string;
  search?: string;
  label: string;
  icon: React.ElementType;
  disabled?: boolean;
  badge?: number;
}

function NavItem({ to, search, label, icon: Icon, disabled, badge }: NavItemProps) {
  const location = useLocation();
  const targetSearch = search ?? "";
  const isActive = location.pathname === to && location.search === targetSearch;

  const className = cn(
    "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    isActive
      ? "bg-primary text-primary-foreground shadow-sm shadow-primary/10"
      : disabled
        ? "text-muted-foreground/40 cursor-not-allowed pointer-events-none"
        : "text-muted-foreground hover:bg-secondary hover:text-foreground"
  );

  const content = (
    <>
      <div className="flex items-center gap-3">
        <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground")} />
        <span>{label}</span>
      </div>
      {badge !== undefined && badge > 0 && (
        <span className={cn(
          "ml-2 rounded px-1.5 py-0 text-[10px] font-semibold",
          isActive ? "bg-primary-foreground/20 text-primary-foreground" : "bg-secondary text-muted-foreground"
        )}>
          {badge}
        </span>
      )}
    </>
  );

  if (disabled || to === "#") {
    return <div className={className}>{content}</div>;
  }

  return (
    <Link
      to={{ pathname: to, search: targetSearch || undefined }}
      className={className}
      aria-current={isActive ? "page" : undefined}
    >
      {content}
    </Link>
  );
}
