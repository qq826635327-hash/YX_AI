/** 系统状态页：应用信息 + 默认模型配置。 */

import { useState, useEffect, useMemo } from "react";
import { Info, Server, Image, Type, Video, FolderOpen, Settings2 } from "lucide-react";
import { PageContainer, LoadingState } from "@/components/layout/PageContainer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useSystemConfig, useProviders } from "@/hooks/useApi";
import { systemApi } from "@/api/config";
import { toast } from "@/stores/ui";
import { useQueryClient } from "@tanstack/react-query";
import type { ModelTag } from "@/types";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-right break-all">{value}</span>
    </div>
  );
}

/** 按能力标签从所有 Provider 的模型中筛选，返回去重的模型名列表 */
function filterModelsByTag(providers: { models?: { model_name: string; tags: ModelTag[] }[] }[], requiredTag: ModelTag): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const p of providers) {
    for (const m of p.models ?? []) {
      if (m.tags.includes(requiredTag) && !seen.has(m.model_name)) {
        seen.add(m.model_name);
        result.push(m.model_name);
      }
    }
  }
  return result;
}

export function SystemStatusPage() {
  const { data: sysConfig, isLoading } = useSystemConfig();
  const { data: providers } = useProviders();
  const queryClient = useQueryClient();
  const [models, setModels] = useState({
    default_image_model: "",
    default_text_model: "",
    default_video_model: "",
  });
  const [tasksConfig, setTasksConfig] = useState({
    rate_limit_retry: 5,
    rate_limit_wait: 65,
    smart_fallback: true,
    max_concurrent: 4,
  });
  const [saving, setSaving] = useState(false);
  const [savingTasks, setSavingTasks] = useState(false);

  useEffect(() => {
    if (sysConfig?.default_models) {
      setModels({
        default_image_model: sysConfig.default_models.default_image_model || "",
        default_text_model: sysConfig.default_models.default_text_model || "",
        default_video_model: sysConfig.default_models.default_video_model || "",
      });
    }
    if (sysConfig?.tasks) {
      setTasksConfig({
        rate_limit_retry: sysConfig.tasks.rate_limit_retry,
        rate_limit_wait: sysConfig.tasks.rate_limit_wait,
        smart_fallback: sysConfig.tasks.smart_fallback,
        max_concurrent: sysConfig.tasks.max_concurrent,
      });
    }
  }, [sysConfig]);

  const imageModels = useMemo(() => filterModelsByTag(providers ?? [], "image_generation"), [providers]);
  const textModels = useMemo(() => filterModelsByTag(providers ?? [], "text_reasoning"), [providers]);
  const videoModels = useMemo(() => filterModelsByTag(providers ?? [], "video_generation"), [providers]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await systemApi.updateDefaultModels(models);
      toast.success("默认模型配置已保存");
      queryClient.invalidateQueries({ queryKey: ["system-config"] });
    } catch (e: any) {
      toast.error(`保存失败：${e.message ?? "未知错误"}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveTasks = async () => {
    setSavingTasks(true);
    try {
      await systemApi.updateTasks(tasksConfig);
      toast.success("任务配置已保存");
      queryClient.invalidateQueries({ queryKey: ["system-config"] });
    } catch (e: any) {
      toast.error(`保存失败：${e.message ?? "未知错误"}`);
    } finally {
      setSavingTasks(false);
    }
  };

  if (isLoading) return <LoadingState />;

  return (
    <PageContainer title="系统状态" description="应用信息与默认模型配置">
      <div className="grid gap-4 md:grid-cols-2">
        {/* 应用信息 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Info className="h-4 w-4" /> 应用信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="名称" value={sysConfig?.app.name} />
            <Row label="版本" value={sysConfig?.app.version} />
          </CardContent>
        </Card>

        {/* 存储信息 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FolderOpen className="h-4 w-4" /> 存储
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="项目根目录" value={sysConfig?.storage.projects_root} />
          </CardContent>
        </Card>

        {/* ComfyUI 状态 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Server className="h-4 w-4" /> ComfyUI
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="地址" value={sysConfig?.comfyui.base_url} />
            <Row
              label="状态"
              value={
                sysConfig?.comfyui.enabled ? (
                  <Badge variant="success">已启用</Badge>
                ) : (
                  <Badge variant="secondary">未启用</Badge>
                )
              }
            />
          </CardContent>
        </Card>
      </div>

      {/* 默认模型配置 */}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Image className="h-4 w-4" /> 默认模型配置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-muted-foreground">
            配置全局默认模型，生图/生视频/文本推理时自动选择对应默认模型。仅显示已添加的模型中具备对应能力的选项。
          </p>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5">
                <Image className="h-3.5 w-3.5" /> 默认图片模型
              </Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={models.default_image_model}
                onChange={(e) => setModels({ ...models, default_image_model: e.target.value })}
              >
                <option value="">未选择</option>
                {imageModels.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
              {imageModels.length === 0 && (
                <p className="text-xs text-muted-foreground">暂无图片生成模型，请先在 API 供应商中添加</p>
              )}
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5">
                <Type className="h-3.5 w-3.5" /> 默认文本模型
              </Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={models.default_text_model}
                onChange={(e) => setModels({ ...models, default_text_model: e.target.value })}
              >
                <option value="">未选择</option>
                {textModels.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
              {textModels.length === 0 && (
                <p className="text-xs text-muted-foreground">暂无文本推理模型，请先在 API 供应商中添加</p>
              )}
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5">
                <Video className="h-3.5 w-3.5" /> 默认视频模型
              </Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={models.default_video_model}
                onChange={(e) => setModels({ ...models, default_video_model: e.target.value })}
              >
                <option value="">未选择</option>
                {videoModels.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
              {videoModels.length === 0 && (
                <p className="text-xs text-muted-foreground">暂无视频生成模型，请先在 API 供应商中添加</p>
              )}
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "保存中..." : "保存配置"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 任务配置 */}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Settings2 className="h-4 w-4" /> 任务配置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-muted-foreground">
            控制生成任务的速率限制重试、智能降级和并发数量。
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>速率限制重试次数</Label>
              <input
                type="number"
                min={0}
                max={20}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={tasksConfig.rate_limit_retry}
                onChange={(e) => setTasksConfig({ ...tasksConfig, rate_limit_retry: parseInt(e.target.value) || 0 })}
              />
              <p className="text-xs text-muted-foreground">遇到 429/Rate Limit 时自动重试次数（0=不重试）</p>
            </div>
            <div className="space-y-2">
              <Label>重试等待时间（秒）</Label>
              <input
                type="number"
                min={10}
                max={300}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={tasksConfig.rate_limit_wait}
                onChange={(e) => setTasksConfig({ ...tasksConfig, rate_limit_wait: parseInt(e.target.value) || 65 })}
              />
              <p className="text-xs text-muted-foreground">每次重试前的等待秒数</p>
            </div>
            <div className="space-y-2">
              <Label>最大并发数</Label>
              <input
                type="number"
                min={1}
                max={20}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={tasksConfig.max_concurrent}
                onChange={(e) => setTasksConfig({ ...tasksConfig, max_concurrent: parseInt(e.target.value) || 4 })}
              />
              <p className="text-xs text-muted-foreground">同时运行的最大生成任务数（1-20）</p>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div className="space-y-0.5">
                <Label>智能降级</Label>
                <p className="text-xs text-muted-foreground">主引擎失败时自动切换备选 Provider</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={tasksConfig.smart_fallback}
                onClick={() => setTasksConfig({ ...tasksConfig, smart_fallback: !tasksConfig.smart_fallback })}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${tasksConfig.smart_fallback ? "bg-primary" : "bg-input"}`}
              >
                <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow ring-0 transition duration-200 ease-in-out ${tasksConfig.smart_fallback ? "translate-x-5" : "translate-x-0"}`} />
              </button>
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={handleSaveTasks} disabled={savingTasks}>
              {savingTasks ? "保存中..." : "保存配置"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
