/** 项目总览页。 */

import { useParams, Link } from "react-router-dom";
import { FileText, Users, Map, Package, Clapperboard, ListTodo } from "lucide-react";
import { PageContainer, LoadingState } from "@/components/layout/PageContainer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProject } from "@/hooks/useProjects";
import { formatTime } from "@/lib/utils";

export function ProjectDetailPage() {
  const { projectId } = useParams();
  const { data: project, isLoading } = useProject(projectId!);

  if (isLoading) return <LoadingState />;
  if (!project) return <PageContainer><p className="text-muted-foreground">项目不存在</p></PageContainer>;

  const stats = [
    { label: "角色", value: project.character_count, icon: Users, to: "characters" },
    { label: "场景", value: project.scene_count, icon: Map, to: "scenes" },
    { label: "道具", value: project.prop_count, icon: Package, to: "props" },
    { label: "剧集", value: project.episode_count, icon: Clapperboard, to: "episodes" },
    { label: "分镜", value: project.shot_count, icon: ListTodo, to: "episodes" },
  ];

  const shortcuts = [
    { label: "剧本", icon: FileText, to: "script", desc: "输入与解析剧本" },
    { label: "剧集结构", icon: Clapperboard, to: "episodes", desc: "管理分镜与素材" },
    { label: "角色管理", icon: Users, to: "characters", desc: "维护角色设定" },
  ];

  return (
    <PageContainer
      title={project.name}
      description={project.description || "暂无描述"}
    >
      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5 mb-8">
        {stats.map((s) => (
          <Link key={s.label} to={s.to}>
            <Card className="transition-all hover:shadow-md hover:-translate-y-0.5">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <s.icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{s.value}</p>
                    <p className="text-xs text-muted-foreground">{s.label}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <div className="mb-2 text-sm text-muted-foreground">
        创建于 {formatTime(project.created_at)} · 项目目录：{project.root_path}
      </div>

      <h2 className="mb-4 text-lg font-semibold">快速开始</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        {shortcuts.map((s) => (
          <Link key={s.label} to={s.to}>
            <Card className="transition-all hover:shadow-md hover:-translate-y-0.5">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <s.icon className="h-5 w-5 text-primary" />
                  <CardTitle className="text-base">{s.label}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{s.desc}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </PageContainer>
  );
}
