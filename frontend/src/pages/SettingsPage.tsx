/** 配置中心页：系统状态、API Provider 管理、工作流映射管理、LLM 配置。 */

import { useState, useEffect } from "react";
import { Plus, Trash2, Pencil, Server, Workflow, Info, CheckCircle2, XCircle, Brain } from "lucide-react";
import { PageContainer, EmptyState, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import {
  useSystemConfig,
  useProviders,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
  useWorkflows,
  useCreateWorkflow,
  useUpdateWorkflow,
  useDeleteWorkflow,
  useUpdateLLMConfig,
} from "@/hooks/useApi";
import { toast } from "@/stores/ui";
import { MODEL_TAG_LABELS } from "@/types";
import type { ApiProvider, ModelTag, ProviderKind, ProviderModelInput, WorkflowMapping } from "@/types";

export function SettingsPage() {
  const { data: sysConfig, isLoading: sysLoading } = useSystemConfig();
  const { data: providers } = useProviders();

  return (
    <PageContainer title="配置中心" description="管理系统配置、API Provider 与 ComfyUI 工作流映射">
      <Tabs defaultValue="system">
        <TabsList>
          <TabsTrigger value="system">系统状态</TabsTrigger>
          <TabsTrigger value="providers">API Provider</TabsTrigger>
          <TabsTrigger value="llm">LLM 解析</TabsTrigger>
          <TabsTrigger value="workflows">工作流映射</TabsTrigger>
        </TabsList>

        {/* 系统状态 */}
        <TabsContent value="system">
          {sysLoading ? (
            <LoadingState />
          ) : sysConfig ? (
            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Info className="h-4 w-4" /> 应用信息
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <Row label="名称" value={sysConfig.app.name} />
                  <Row label="版本" value={sysConfig.app.version} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Server className="h-4 w-4" /> ComfyUI
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <Row label="地址" value={sysConfig.comfyui.base_url} />
                  <Row
                    label="状态"
                    value={
                      sysConfig.comfyui.enabled ? (
                        <Badge variant="success"><CheckCircle2 className="mr-1 h-3 w-3" />已启用</Badge>
                      ) : (
                        <Badge variant="secondary"><XCircle className="mr-1 h-3 w-3" />未启用</Badge>
                      )
                    }
                  />
                  <Row label="超时" value={`${sysConfig.comfyui.timeout} 秒`} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Workflow className="h-4 w-4" /> LLM 解析
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <Row label="Provider" value={sysConfig.llm.provider} />
                  <Row label="模型" value={sysConfig.llm.model} />
                  <Row
                    label="状态"
                    value={
                      sysConfig.llm.enabled ? (
                        <Badge variant="success">已启用</Badge>
                      ) : (
                        <Badge variant="secondary">未启用（使用规则解析）</Badge>
                      )
                    }
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">存储</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <Row label="项目根目录" value={sysConfig.storage.projects_root} />
                </CardContent>
              </Card>
            </div>
          ) : null}
        </TabsContent>

        {/* Provider */}
        <TabsContent value="providers">
          <ProviderManager providers={providers || []} />
        </TabsContent>

        {/* LLM 配置 */}
        <TabsContent value="llm">
          <LLMConfigManager sysConfig={sysConfig} />
        </TabsContent>

        {/* 工作流 */}
        <TabsContent value="workflows">
          <WorkflowManager />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-right break-all">{value}</span>
    </div>
  );
}

function ProviderManager({ providers }: { providers: ApiProvider[] }) {
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<ApiProvider | null>(null);
  const createMutation = useCreateProvider();
  const updateMutation = useUpdateProvider();
  const deleteMutation = useDeleteProvider();

  const [form, setForm] = useState<{
    name: string;
    provider_kind: ProviderKind;
    base_url: string;
    api_key: string;
    models: ProviderModelInput[];
  }>({
    name: "",
    provider_kind: "custom",
    base_url: "",
    api_key: "",
    models: [{ model_name: "", tags: [], sort_order: 0 }],
  });

  // Sync form when editing
  useEffect(() => {
    if (editing) {
      setForm({
        name: editing.name,
        provider_kind: editing.provider_kind,
        base_url: editing.base_url,
        api_key: "",
        models: editing.models?.length
          ? editing.models.map((m) => ({ ...m }))
          : editing.model
            ? [{ model_name: editing.model, tags: [], sort_order: 0 }]
            : [{ model_name: "", tags: [], sort_order: 0 }],
      });
    } else if (!createOpen) {
      setForm({
        name: "",
        provider_kind: "custom",
        base_url: "",
        api_key: "",
        models: [{ model_name: "", tags: [], sort_order: 0 }],
      });
    }
  }, [editing, createOpen]);

  const isOpen = createOpen || !!editing;
  const onOpenChange = (v: boolean) => { if (!v) { setCreateOpen(false); setEditing(null); } };

  const handleSubmit = async () => {
    const validModels = form.models
      .map((m, idx) => ({ ...m, model_name: m.model_name.trim(), sort_order: idx }))
      .filter((m) => m.model_name);

    if (editing) {
      const payload: Record<string, unknown> = {
        name: form.name.trim(),
        provider_kind: form.provider_kind,
        base_url: form.base_url.trim(),
        models: validModels,
      };
      if (form.api_key) payload.api_key = form.api_key;
      await updateMutation.mutateAsync({ id: editing.id, ...payload });
    } else {
      await createMutation.mutateAsync({
        name: form.name.trim(),
        provider_kind: form.provider_kind,
        base_url: form.base_url.trim(),
        api_key: form.api_key,
        models: validModels,
      });
    }
    setForm({
      name: "",
      provider_kind: "custom",
      base_url: "",
      api_key: "",
      models: [{ model_name: "", tags: [], sort_order: 0 }],
    });
    onOpenChange(false);
  };

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" />
          新增 Provider
        </Button>
      </div>

      {providers.length === 0 ? (
        <EmptyState icon={Server} title="暂无 Provider" description="添加 API Provider 以使用远程生成能力" />
      ) : (
        <div className="space-y-2">
          {providers.map((p) => (
            <Card key={p.id}>
              <CardContent className="flex items-center justify-between p-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{p.name}</span>
                    <Badge variant="outline" className="text-xs">{p.provider_kind}</Badge>
                    {p.is_default && <Badge variant="secondary" className="text-xs">默认</Badge>}
                    {p.enabled ? (
                      <Badge variant="success" className="text-xs">启用</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">停用</Badge>
                    )}
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {p.base_url} · {p.api_key_masked}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    {p.models?.length ? (
                      p.models.map((m) => (
                        <span key={m.id} className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px]">
                          {m.model_name}
                          {m.tags?.map((tag) => (
                            <Badge key={tag} variant="secondary" className="px-1 py-0 text-[9px]">
                              {MODEL_TAG_LABELS[tag] || tag}
                            </Badge>
                          ))}
                        </span>
                      ))
                    ) : p.model ? (
                      <span className="text-xs text-muted-foreground">{p.model}</span>
                    ) : (
                      <span className="text-xs text-muted-foreground">未配置模型</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setEditing(p)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:text-destructive"
                    onClick={() => {
                      if (confirm(`确认删除 Provider「${p.name}」？`)) deleteMutation.mutate(p.id);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={isOpen} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "编辑 Provider" : "新增 API Provider"}</DialogTitle>
            <DialogDescription>{editing ? "修改 Provider 配置（API Key 留空则不修改）" : "配置远程生成 API"}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>名称 *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>类型</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.provider_kind}
                onChange={(e) => setForm({ ...form, provider_kind: e.target.value as ProviderKind })}
              >
                <option value="openai">OpenAI 兼容</option>
                <option value="fal">Fal</option>
                <option value="replicate">Replicate</option>
                <option value="agnes">Agnes</option>
                <option value="custom">自定义</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>Base URL *</Label>
              <Input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.example.com/v1" />
            </div>
            <div className="space-y-2">
              <Label>API Key{editing ? "（留空不修改）" : ""}</Label>
              <Input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>模型配置</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setForm({
                      ...form,
                      models: [...form.models, { model_name: "", tags: [], sort_order: form.models.length }],
                    })
                  }
                >
                  <Plus className="mr-1 h-3 w-3" /> 添加模型
                </Button>
              </div>
              <div className="space-y-2">
                {form.models.map((m, idx) => (
                  <div key={idx} className="rounded-md border p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <Input
                        value={m.model_name}
                        onChange={(e) => {
                          const next = [...form.models];
                          next[idx] = { ...next[idx], model_name: e.target.value };
                          setForm({ ...form, models: next });
                        }}
                        placeholder="模型名，如 gpt-4o-mini / flux-dev / agnes-video-v2.0"
                      />
                      {form.models.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="shrink-0"
                          onClick={() => {
                            const next = form.models.filter((_, i) => i !== idx);
                            setForm({ ...form, models: next });
                          }}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(Object.keys(MODEL_TAG_LABELS) as ModelTag[]).map((tag) => {
                        const selected = m.tags.includes(tag);
                        return (
                          <button
                            key={tag}
                            type="button"
                            onClick={() => {
                              const next = [...form.models];
                              const tags = selected ? next[idx].tags.filter((t) => t !== tag) : [...next[idx].tags, tag];
                              next[idx] = { ...next[idx], tags };
                              setForm({ ...form, models: next });
                            }}
                            className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                              selected
                                ? "bg-primary text-primary-foreground border-primary"
                                : "bg-background text-muted-foreground hover:bg-muted"
                            }`}
                          >
                            {MODEL_TAG_LABELS[tag]}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                标签用于按能力筛选：文本推理、图片生成、图片修改、视频生成
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
            <Button
              disabled={!form.name.trim() || !form.base_url.trim() || createMutation.isPending || updateMutation.isPending}
              onClick={handleSubmit}
            >
              {editing ? "保存" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function LLMConfigManager({ sysConfig }: { sysConfig: import("@/types").SystemConfig | undefined }) {
  const updateMutation = useUpdateLLMConfig();

  const [form, setForm] = useState({
    enabled: false,
    provider: "openai",
    base_url: "https://api.openai.com/v1",
    api_key: "",
    model: "gpt-4o-mini",
  });

  useEffect(() => {
    if (sysConfig?.llm) {
      setForm((prev) => ({
        ...prev,
        enabled: sysConfig.llm.enabled,
        provider: sysConfig.llm.provider,
        base_url: sysConfig.llm.base_url,
        model: sysConfig.llm.model,
      }));
    }
  }, [sysConfig]);

  const handleSave = () => {
    const payload: Record<string, unknown> = {
      enabled: form.enabled,
      provider: form.provider,
      base_url: form.base_url.trim(),
      model: form.model.trim(),
    };
    if (form.api_key) payload.api_key = form.api_key;
    updateMutation.mutate(payload);
  };

  return (
    <div className="max-w-lg space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Brain className="h-4 w-4" /> LLM 剧本解析配置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>启用 LLM 解析</Label>
            <Button
              variant={form.enabled ? "default" : "outline"}
              size="sm"
              onClick={() => setForm({ ...form, enabled: !form.enabled })}
            >
              {form.enabled ? "已启用" : "未启用"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            {form.enabled
              ? "启用后将使用 LLM 进行智能剧本解析（角色/场景/道具/剧集结构）"
              : "未启用时使用规则引擎解析剧本，效果有限"}
          </p>

          <div className="space-y-2">
            <Label>Provider</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
            >
              <option value="openai">OpenAI 兼容</option>
              <option value="anthropic">Anthropic</option>
              <option value="custom">自定义</option>
            </select>
          </div>

          <div className="space-y-2">
            <Label>Base URL</Label>
            <Input
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
            />
          </div>

          <div className="space-y-2">
            <Label>API Key（留空不修改）</Label>
            <Input
              type="password"
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              placeholder="sk-..."
            />
          </div>

          <div className="space-y-2">
            <Label>模型</Label>
            <Input
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              placeholder="gpt-4o-mini / gpt-4o / claude-3-haiku ..."
            />
          </div>

          <Button
            disabled={updateMutation.isPending || !form.base_url.trim() || !form.model.trim()}
            onClick={handleSave}
          >
            {updateMutation.isPending ? "保存中..." : "保存配置"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function WorkflowEditDialog({
  open,
  workflow,
  onOpenChange,
}: {
  open: boolean;
  workflow?: WorkflowMapping;
  onOpenChange: (open: boolean) => void;
}) {
  const [form, setForm] = useState({
    name: "",
    asset_type: "character",
    description: "",
    provider_type: "comfyui" as "comfyui" | "api",
    provider_id: "",
    is_default: false,
    enabled: true,
    workflow_json: "",
    input_mapping: "",
    output_mapping: "",
  });

  useEffect(() => {
    if (open) {
      setForm({
        name: workflow?.name || "",
        asset_type: workflow?.asset_type || "character",
        description: workflow?.description || "",
        provider_type: workflow?.provider_type || "comfyui",
        provider_id: workflow?.provider_id || "",
        is_default: workflow?.is_default || false,
        enabled: workflow?.enabled ?? true,
        workflow_json: workflow?.workflow_json ? JSON.stringify(workflow.workflow_json, null, 2) : "",
        input_mapping: workflow?.input_mapping ? JSON.stringify(workflow.input_mapping, null, 2) : "",
        output_mapping: workflow?.output_mapping ? JSON.stringify(workflow.output_mapping, null, 2) : "",
      });
    }
  }, [open, workflow]);

  const createMutation = useCreateWorkflow();
  const updateMutation = useUpdateWorkflow();

  const parseJsonField = (value: string, fieldName: string): Record<string, unknown> | null | undefined => {
    if (!value.trim()) return null;
    try {
      return JSON.parse(value);
    } catch {
      toast.error(`${fieldName} 不是合法 JSON`);
      return undefined; // 哨兵值：解析失败
    }
  };

  const handleSubmit = () => {
    const workflowJson = form.workflow_json.trim() ? parseJsonField(form.workflow_json, "workflow_json") : null;
    const inputMapping = form.input_mapping.trim() ? parseJsonField(form.input_mapping, "input_mapping") : null;
    const outputMapping = form.output_mapping.trim() ? parseJsonField(form.output_mapping, "output_mapping") : null;

    if (workflowJson === undefined || inputMapping === undefined || outputMapping === undefined) return;

    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      asset_type: form.asset_type,
      description: form.description.trim() || undefined,
      provider_type: form.provider_type,
      is_default: form.is_default,
      enabled: form.enabled,
    };
    if (form.provider_id.trim()) payload.provider_id = form.provider_id.trim();
    if (workflowJson) payload.workflow_json = workflowJson;
    if (inputMapping) payload.input_mapping = inputMapping;
    if (outputMapping) payload.output_mapping = outputMapping;

    if (workflow) {
      updateMutation.mutate({ id: workflow.id, ...payload });
    } else {
      createMutation.mutate(payload);
    }
    onOpenChange(false);
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{workflow ? "编辑工作流映射" : "新增工作流映射"}</DialogTitle>
          <DialogDescription>
            {workflow ? "修改工作流映射配置" : "创建新的 ComfyUI / API 工作流映射"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>名称 *</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如：角色头像生成" />
          </div>
          <div className="space-y-2">
            <Label>素材类型 *</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={form.asset_type}
              onChange={(e) => setForm({ ...form, asset_type: e.target.value })}
            >
              <option value="character">角色 (character)</option>
              <option value="scene">场景 (scene)</option>
              <option value="prop">道具 (prop)</option>
              <option value="shot_image">分镜图片 (shot_image)</option>
              <option value="shot_video">分镜视频 (shot_video)</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label>描述</Label>
            <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="可选" rows={2} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Provider 类型</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.provider_type}
                onChange={(e) => setForm({ ...form, provider_type: e.target.value as "comfyui" | "api" })}
              >
                <option value="comfyui">ComfyUI</option>
                <option value="api">API</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>Provider ID</Label>
              <Input value={form.provider_id} onChange={(e) => setForm({ ...form, provider_id: e.target.value })} placeholder="关联 Provider 编号" />
            </div>
          </div>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              启用
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
              设为默认
            </label>
          </div>
          <details className="space-y-2">
            <summary className="cursor-pointer text-sm font-medium">高级：JSON 配置</summary>
            <div className="space-y-2">
              <Label>workflow_json (ComfyUI 工作流 JSON)</Label>
              <Textarea value={form.workflow_json} onChange={(e) => setForm({ ...form, workflow_json: e.target.value })} placeholder='粘贴 ComfyUI 工作流 JSON...' rows={4} className="font-mono text-xs" />
            </div>
            <div className="space-y-2">
              <Label>input_mapping (输入映射)</Label>
              <Textarea value={form.input_mapping} onChange={(e) => setForm({ ...form, input_mapping: e.target.value })} placeholder='{"prompt": "inputs.text"}' rows={2} className="font-mono text-xs" />
            </div>
            <div className="space-y-2">
              <Label>output_mapping (输出映射)</Label>
              <Textarea value={form.output_mapping} onChange={(e) => setForm({ ...form, output_mapping: e.target.value })} placeholder='{"image": "outputs.result"}' rows={2} className="font-mono text-xs" />
            </div>
          </details>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!form.name.trim() || isPending} onClick={handleSubmit}>
            {isPending ? "保存中..." : workflow ? "保存" : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function WorkflowManager() {
  const { data: workflows = [] } = useWorkflows();
  const deleteMutation = useDeleteWorkflow();
  const [editing, setEditing] = useState<WorkflowMapping | undefined>();
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleDelete = (w: WorkflowMapping) => {
    if (window.confirm(`确定删除工作流映射「${w.name}」？`)) {
      deleteMutation.mutate(w.id);
    }
  };

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => { setEditing(undefined); setDialogOpen(true); }}>
          <Plus className="h-4 w-4" />
          新增工作流映射
        </Button>
      </div>
      {workflows.length === 0 ? (
        <EmptyState
          icon={Workflow}
          title="暂无工作流映射"
          description="创建 ComfyUI 或 API 工作流映射，将素材类型绑定到具体生成流程"
        />
      ) : (
        <div className="space-y-2">
          {workflows.map((w) => (
            <Card key={w.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium">{w.name}</span>
                    <Badge variant="outline" className="ml-2 text-xs">{w.asset_type}</Badge>
                    <Badge variant={w.enabled ? "success" : "secondary"} className="ml-1 text-xs">
                      {w.enabled ? "已启用" : "未启用"}
                    </Badge>
                    {w.is_default && <Badge variant="default" className="ml-1 text-xs">默认</Badge>}
                  </div>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" onClick={() => { setEditing(w); setDialogOpen(true); }}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(w)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
                {w.description && <p className="mt-1 text-xs text-muted-foreground">{w.description}</p>}
                <div className="mt-1 flex gap-2 text-xs text-muted-foreground">
                  <span>Provider: {w.provider_type}{w.provider_id ? ` / ${w.provider_id}` : ""}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <WorkflowEditDialog open={dialogOpen} workflow={editing} onOpenChange={(open) => { setDialogOpen(open); if (!open) setEditing(undefined); }} />
    </div>
  );
}
