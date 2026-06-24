/** 配置中心 - 图床配置：管理图片上传到公网的服务。 */

import { useState, useEffect } from "react";
import { Plus, Trash2, Pencil, Image, Loader2, Star } from "lucide-react";
import { PageContainer, EmptyState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import {
  useImageHostingProviders,
  useCreateImageHosting,
  useUpdateImageHosting,
  useDeleteImageHosting,
  useTestImageHosting,
  useSetDefaultImageHosting,
} from "@/hooks/useApi";
import { useConfirm } from "@/components/ConfirmDialog";
import { toast } from "@/stores/ui";
import type { ImageHostingProvider, HostingProviderType, ImageHostingCreate } from "@/types";

// 图床类型选项
const HOSTING_TYPE_OPTIONS: { value: HostingProviderType; label: string; desc: string }[] = [
  { value: "boltp", label: "闪电图床", desc: "boltp.com，国内访问快" },
  { value: "smms", label: "SM.MS", desc: "老牌图床，稳定可靠" },
  { value: "superbed", label: "聚合图床", desc: "superbed.cc，多源聚合" },
  { value: "github", label: "GitHub", desc: "免费存储，需配置仓库" },
  { value: "custom", label: "自定义", desc: "适配任何图床 API" },
];

export function SettingsImageHostingPage() {
  const { data: providers } = useImageHostingProviders();

  return (
    <PageContainer title="图床配置" description="管理图片上传服务，部分 AI 模型需要公网 URL 时使用">
      <ImageHostingManager providers={providers || []} />
    </PageContainer>
  );
}

function ImageHostingManager({ providers }: { providers: ImageHostingProvider[] }) {
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<ImageHostingProvider | null>(null);
  const createMutation = useCreateImageHosting();
  const updateMutation = useUpdateImageHosting();
  const deleteMutation = useDeleteImageHosting();
  const testMutation = useTestImageHosting();
  const setDefaultMutation = useSetDefaultImageHosting();
  const confirm = useConfirm();

  const [form, setForm] = useState<{
    name: string;
    provider_type: HostingProviderType;
    api_url: string;
    token: string;
    extra_config: Record<string, unknown>;
    max_file_size: number;
    is_default: boolean;
    enabled: boolean;
    description: string;
  }>({
    name: "",
    provider_type: "boltp",
    api_url: "",
    token: "",
    extra_config: {},
    max_file_size: 10485760,
    is_default: false,
    enabled: true,
    description: "",
  });

  useEffect(() => {
    if (editing) {
      setForm({
        name: editing.name,
        provider_type: editing.provider_type,
        api_url: editing.api_url,
        token: "",
        extra_config: (editing.extra_config as Record<string, unknown>) || {},
        max_file_size: editing.max_file_size,
        is_default: editing.is_default,
        enabled: editing.enabled,
        description: editing.description || "",
      });
    } else if (!createOpen) {
      setForm({
        name: "",
        provider_type: "boltp",
        api_url: "",
        token: "",
        extra_config: {},
        max_file_size: 10485760,
        is_default: providers.length === 0,
        enabled: true,
        description: "",
      });
    }
  }, [editing, createOpen, providers.length]);

  const isOpen = createOpen || !!editing;
  const onOpenChange = (v: boolean) => { if (!v) { setCreateOpen(false); setEditing(null); } };

  const handleSubmit = async () => {
    const payload: ImageHostingCreate = {
      name: form.name.trim(),
      provider_type: form.provider_type,
      api_url: form.api_url.trim() || undefined,
      token: form.token || undefined,
      extra_config: Object.keys(form.extra_config).length > 0 ? form.extra_config : null,
      max_file_size: form.max_file_size,
      is_default: form.is_default,
      enabled: form.enabled,
      description: form.description.trim() || null,
    };

    if (editing) {
      await updateMutation.mutateAsync({ id: editing.id, ...payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
    onOpenChange(false);
  };

  const handleTest = async (id: string) => {
    const result = await testMutation.mutateAsync(id);
    if (result.data.success) {
      toast.success(`上传测试成功！URL: ${result.data.url?.slice(0, 60)}...`);
    } else {
      toast.error(result.data.message || "上传测试失败");
    }
  };

  const handleSetDefault = async (id: string) => {
    await setDefaultMutation.mutateAsync(id);
    toast.success("已设为默认图床");
  };

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" />
          新增图床
        </Button>
      </div>

      {providers.length === 0 ? (
        <EmptyState
          icon={Image}
          title="暂无图床配置"
          description="添加图床后，需要公网 URL 的 AI 模型可自动上传参考图"
        />
      ) : (
        <div className="space-y-2">
          {providers.map((p) => (
            <Card key={p.id}>
              <CardContent className="flex items-center justify-between p-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{p.name}</span>
                    <Badge variant="outline" className="text-xs">
                      {HOSTING_TYPE_OPTIONS.find((t) => t.value === p.provider_type)?.label || p.provider_type}
                    </Badge>
                    {p.is_default && (
                      <Badge variant="secondary" className="text-xs">
                        <Star className="mr-1 h-3 w-3" /> 默认
                      </Badge>
                    )}
                    {p.enabled ? (
                      <Badge variant="success" className="text-xs">启用</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">停用</Badge>
                    )}
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {p.api_url || "自动填充"} · {p.token_masked || "未配置密钥"}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  {!p.is_default && p.enabled && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={() => handleSetDefault(p.id)}
                    >
                      <Star className="mr-1 h-3 w-3" /> 设为默认
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8"
                    disabled={testMutation.isPending || !p.enabled}
                    onClick={() => handleTest(p.id)}
                  >
                    {testMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "测试"}
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(p)}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:text-destructive"
                    onClick={async () => {
                      if (await confirm({ title: `确认删除图床「${p.name}」？`, variant: "destructive" }))
                        deleteMutation.mutate(p.id);
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
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "编辑图床" : "新增图床"}</DialogTitle>
            <DialogDescription>
              {editing ? "修改图床配置（密钥留空则不修改）" : "配置图片上传服务"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2 max-h-[60vh] overflow-y-auto">
            <div className="space-y-2">
              <Label>名称 *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如：闪电图床" />
            </div>
            <div className="space-y-2">
              <Label>类型</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.provider_type}
                onChange={(e) => setForm({ ...form, provider_type: e.target.value as HostingProviderType })}
              >
                {HOSTING_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label} — {opt.desc}</option>
                ))}
              </select>
            </div>

            {/* API 地址：预设类型自动填充，custom 类型必填 */}
            <div className="space-y-2">
              <Label>API 地址{form.provider_type === "custom" ? " *" : ""}</Label>
              <Input
                value={form.api_url}
                onChange={(e) => setForm({ ...form, api_url: e.target.value })}
                placeholder={form.provider_type === "custom" ? "https://api.example.com/upload" : "预设类型自动填充，也可自定义"}
              />
            </div>

            <div className="space-y-2">
              <Label>密钥/Token{editing ? "（留空不修改）" : " *"}</Label>
              <Input
                type="password"
                value={form.token}
                onChange={(e) => setForm({ ...form, token: e.target.value })}
                placeholder={
                  form.provider_type === "github"
                    ? "ghp_xxxx（GitHub Personal Access Token）"
                    : form.provider_type === "boltp"
                    ? "用户ID|Token（如 2150|ZtcAJx...）"
                    : "图床 API 密钥"
                }
              />
            </div>

            {/* GitHub 专属配置 */}
            {form.provider_type === "github" && (
              <div className="space-y-3 rounded-md border p-3">
                <Label className="text-sm font-medium">GitHub 仓库配置</Label>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label className="text-xs">用户名 (owner)</Label>
                    <Input
                      value={(form.extra_config.owner as string) || ""}
                      onChange={(e) =>
                        setForm({ ...form, extra_config: { ...form.extra_config, owner: e.target.value } })
                      }
                      placeholder="如 qq826635327-hash"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">仓库名 (repo)</Label>
                    <Input
                      value={(form.extra_config.repo as string) || ""}
                      onChange={(e) =>
                        setForm({ ...form, extra_config: { ...form.extra_config, repo: e.target.value } })
                      }
                      placeholder="如 image-hosting"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label className="text-xs">分支</Label>
                    <Input
                      value={(form.extra_config.branch as string) || ""}
                      onChange={(e) =>
                        setForm({ ...form, extra_config: { ...form.extra_config, branch: e.target.value } })
                      }
                      placeholder="main"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">路径前缀</Label>
                    <Input
                      value={(form.extra_config.path_prefix as string) || ""}
                      onChange={(e) =>
                        setForm({ ...form, extra_config: { ...form.extra_config, path_prefix: e.target.value } })
                      }
                      placeholder="assets"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* 自定义图床专属配置 */}
            {form.provider_type === "custom" && (
              <div className="space-y-3 rounded-md border p-3">
                <Label className="text-sm font-medium">自定义图床配置</Label>
                <div className="space-y-1">
                  <Label className="text-xs">文件字段名</Label>
                  <Input
                    value={(form.extra_config.file_field as string) || ""}
                    onChange={(e) =>
                      setForm({ ...form, extra_config: { ...form.extra_config, file_field: e.target.value } })
                    }
                    placeholder="file（默认）"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">URL 路径</Label>
                  <Input
                    value={(form.extra_config.url_path as string) || ""}
                    onChange={(e) =>
                      setForm({ ...form, extra_config: { ...form.extra_config, url_path: e.target.value } })
                    }
                    placeholder="如 data.url 或 data.public_url"
                  />
                  <p className="text-xs text-muted-foreground">响应 JSON 中图片 URL 的路径，如 data.url</p>
                </div>
              </div>
            )}

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                />
                设为默认图床
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                启用
              </label>
            </div>

            <div className="space-y-2">
              <Label>备注</Label>
              <Input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="可选"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
            <Button
              disabled={
                !form.name.trim() ||
                (form.provider_type === "custom" && !form.api_url.trim()) ||
                (!editing && !form.token) ||
                createMutation.isPending ||
                updateMutation.isPending
              }
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
