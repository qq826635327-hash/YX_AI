/** API 供应商管理页。 */

import { useState, useEffect } from "react";
import { Plus, Trash2, Pencil, Server } from "lucide-react";
import { PageContainer, EmptyState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import {
  useProviders,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
} from "@/hooks/useApi";
import { MODEL_TAG_LABELS } from "@/types";
import { useConfirm } from "@/components/ConfirmDialog";
import type { ApiProvider, ModelTag, ProviderKind, ProviderModelInput } from "@/types";

export function SettingsPage() {
  const { data: providers } = useProviders();

  return (
    <PageContainer title="API 供应商" description="管理远程生成 API Provider">
      <ProviderManager providers={providers || []} />
    </PageContainer>
  );
}

function ProviderManager({ providers }: { providers: ApiProvider[] }) {
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<ApiProvider | null>(null);
  const createMutation = useCreateProvider();
  const updateMutation = useUpdateProvider();
  const deleteMutation = useDeleteProvider();
  const confirm = useConfirm();

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
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(p)}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:text-destructive"
                    onClick={async () => {
                      if (await confirm({ title: `确认删除 Provider「${p.name}」？`, variant: "destructive" })) deleteMutation.mutate(p.id);
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
