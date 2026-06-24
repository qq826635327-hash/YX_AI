/** 剧集结构页：剧集列表 + 分镜管理 + 右侧编辑面板。 */

import { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  Clapperboard,
  ChevronDown,
  ChevronRight,
  Trash2,
  Plus,
  Pencil,
  FolderOpen,
  X,
} from "lucide-react";
import { PageContainer, EmptyState, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  useEpisodes,
  useCreateEpisode,
  useDeleteEpisode,
  useUpdateEpisode,
} from "@/hooks/useBusiness";
import { assetsApi } from "@/api/assets";
import { toast } from "@/stores/ui";
import { useConfirm } from "@/components/ConfirmDialog";
import type { Episode } from "@/types";
import ShotsList from "@/components/episodes/ShotsList";

export function EpisodesPage() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const confirm = useConfirm();
  const { data: episodes, isLoading } = useEpisodes(projectId!);
  const createEpisodeMutation = useCreateEpisode(projectId!);
  const deleteEpisodeMutation = useDeleteEpisode(projectId!);
  const updateEpisodeMutation = useUpdateEpisode(projectId!);

  const [expandedEpisode, setExpandedEpisode] = useState<string | null>(null);
  const [createEpOpen, setCreateEpOpen] = useState(false);
  const [epForm, setEpForm] = useState({ episode_no: 1, title: "", summary: "" });

  // 右侧编辑面板状态
  const [editingEp, setEditingEp] = useState<Episode | null>(null);
  const [editForm, setEditForm] = useState({ episode_no: 1, title: "", summary: "" });

  // 监听侧边栏编辑事件
  useEffect(() => {
    const handler = (e: Event) => {
      const epId = (e as CustomEvent).detail;
      const ep = episodes?.find((ep) => ep.id === epId);
      if (ep) openEditPanel(ep);
    };
    window.addEventListener("episode:edit", handler);
    return () => window.removeEventListener("episode:edit", handler);
  }, [episodes]);

  // URL 参数 ?ep=xxx 自动展开对应剧集
  useEffect(() => {
    const epId = searchParams.get("ep");
    if (epId) setExpandedEpisode(epId);
  }, [searchParams]);

  const openEditPanel = useCallback((ep: Episode) => {
    setEditingEp(ep);
    setEditForm({
      episode_no: ep.episode_no,
      title: ep.title,
      summary: ep.summary || "",
    });
  }, []);

  const handleSaveEdit = async () => {
    if (!editingEp) return;
    try {
      await updateEpisodeMutation.mutateAsync({
        id: editingEp.id,
        episode_no: editForm.episode_no,
        title: editForm.title.trim() || `第${editForm.episode_no}集`,
        summary: editForm.summary.trim() || undefined,
      });
      setEditingEp(null);
    } catch {
      // 已由 mutation onError 处理
    }
  };

  const handleDelete = async (ep: Episode) => {
    if (!(await confirm({ title: `确认删除「第${ep.episode_no}集 ${ep.title}」？`, variant: "destructive" }))) return;
    try {
      await deleteEpisodeMutation.mutateAsync(ep.id);
      if (editingEp?.id === ep.id) setEditingEp(null);
    } catch {
      // 已由 mutation onError 处理
    }
  };

  const handleOpenDir = async (ep: Episode) => {
    if (!projectId) return;
    // 构建剧集目录路径
    const dirName = `第${ep.episode_no}集`;
    try {
      // 先同步确保目录存在
      await assetsApi.syncDirs(projectId, "db_to_disk");
      // 获取项目根目录
      const sysConfig = await (await fetch("/api/config/system")).json();
      const root = sysConfig?.data?.storage?.projects_root;
      if (!root) { toast.error("无法获取项目根目录"); return; }
      const dirPath = `${root}\\${projectId}\\剧集\\${dirName}`;
      await assetsApi.openDir(dirPath);
    } catch (e: any) {
      toast.error(`打开目录失败：${e.message ?? "未知错误"}`);
    }
  };

  const handleCreateEpisode = async () => {
    try {
      await createEpisodeMutation.mutateAsync({
        episode_no: epForm.episode_no,
        title: epForm.title.trim() || `第${epForm.episode_no}集`,
        summary: epForm.summary.trim() || undefined,
      });
      setEpForm({ episode_no: epForm.episode_no + 1, title: "", summary: "" });
      setCreateEpOpen(false);
    } catch {
      // mutateAsync 失败已由 React Query onError 回调处理
    }
  };

  if (isLoading) return <LoadingState />;

  return (
    <div className="flex h-full">
      {/* 主内容区 */}
      <div className={`flex-1 overflow-y-auto ${editingEp ? "mr-[300px]" : ""} transition-[margin] duration-200`}>
        <PageContainer
          title="剧集结构"
          description="管理剧集、分镜与首帧/尾帧/视频素材"
          actions={
            <Button onClick={() => setCreateEpOpen(true)}>
              <Plus className="h-4 w-4" />
              新增剧集
            </Button>
          }
        >
          {(episodes || []).length === 0 ? (
            <EmptyState
              icon={Clapperboard}
              title="暂无剧集"
              description="点击右上角「新增剧集」创建，或通过剧本解析自动生成"
            />
          ) : (
            <div className="space-y-3">
              {(episodes as Episode[]).map((ep) => {
                const isExpanded = expandedEpisode === ep.id;
                return (
                  <Card key={ep.id} className="group border-border/60 bg-card">
                    <CardHeader
                      className="cursor-pointer py-4 transition-colors hover:bg-secondary/30"
                      onClick={() => setExpandedEpisode(isExpanded ? null : ep.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                          <Badge variant="secondary">第 {ep.episode_no} 集</Badge>
                          <CardTitle className="text-base">{ep.title}</CardTitle>
                        </div>
                        <div className="flex items-center gap-1">
                          {ep.summary && (
                            <span className="max-w-md truncate text-sm text-muted-foreground">{ep.summary}</span>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
                            onClick={(e) => { e.stopPropagation(); openEditPanel(ep); }}
                            title="编辑"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
                            onClick={(e) => { e.stopPropagation(); handleDelete(ep); }}
                            title="删除"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    {isExpanded && (
                      <CardContent className="border-t pt-4">
                        <ShotsList episodeId={ep.id} projectId={projectId!} />
                      </CardContent>
                    )}
                  </Card>
                );
              })}
            </div>
          )}

          {/* 新增剧集对话框 */}
          <Dialog open={createEpOpen} onOpenChange={setCreateEpOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>新增剧集</DialogTitle>
                <DialogDescription>创建一个新的剧集</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="space-y-2">
                  <Label>集号 *</Label>
                  <Input
                    type="number"
                    min={1}
                    value={epForm.episode_no}
                    onChange={(e) => setEpForm({ ...epForm, episode_no: parseInt(e.target.value) || 1 })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>标题</Label>
                  <Input
                    value={epForm.title}
                    onChange={(e) => setEpForm({ ...epForm, title: e.target.value })}
                    placeholder="留空则自动生成「第N集」"
                  />
                </div>
                <div className="space-y-2">
                  <Label>摘要</Label>
                  <Textarea
                    value={epForm.summary}
                    onChange={(e) => setEpForm({ ...epForm, summary: e.target.value })}
                    rows={3}
                    placeholder="本集剧情摘要"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setCreateEpOpen(false)}>取消</Button>
                <Button disabled={createEpisodeMutation.isPending} onClick={handleCreateEpisode}>
                  创建
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </PageContainer>
      </div>

      {/* 右侧编辑面板 */}
      {editingEp && (
        <div className="fixed right-0 top-0 z-30 h-full w-[300px] border-l bg-card shadow-lg animate-in slide-in-from-right duration-200">
          <div className="flex h-full flex-col">
            {/* 面板头部 */}
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h3 className="text-sm font-semibold">编辑剧集</h3>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditingEp(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* 面板内容 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div className="space-y-2">
                <Label>集号</Label>
                <Input
                  type="number"
                  min={1}
                  value={editForm.episode_no}
                  onChange={(e) => setEditForm({ ...editForm, episode_no: parseInt(e.target.value) || 1 })}
                />
              </div>
              <div className="space-y-2">
                <Label>标题</Label>
                <Input
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  placeholder="留空则自动生成「第N集」"
                />
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea
                  value={editForm.summary}
                  onChange={(e) => setEditForm({ ...editForm, summary: e.target.value })}
                  rows={4}
                  placeholder="本集剧情摘要"
                />
              </div>

              {/* 打开本地目录 */}
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                onClick={() => handleOpenDir(editingEp)}
              >
                <FolderOpen className="h-4 w-4" />
                打开本地目录
              </Button>

              {/* 删除按钮 */}
              <Button
                variant="destructive"
                className="w-full"
                disabled={deleteEpisodeMutation.isPending}
                onClick={() => handleDelete(editingEp)}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                删除此剧集
              </Button>
            </div>

            {/* 面板底部保存 */}
            <div className="border-t p-4">
              <Button
                className="w-full"
                disabled={updateEpisodeMutation.isPending}
                onClick={handleSaveEdit}
              >
                {updateEpisodeMutation.isPending ? "保存中..." : "保存修改"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
