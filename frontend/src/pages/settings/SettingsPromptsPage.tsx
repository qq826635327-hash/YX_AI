/** 配置中心 - 提示词模板与画风预置管理。 */

import { useState, useEffect, useRef } from "react";
import { Plus, Pencil, Trash2, Star, FileText, GripVertical, Palette, Shield } from "lucide-react";
import { PageContainer, EmptyState, LoadingState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  usePromptTemplates,
  useCreatePromptTemplate,
  useUpdatePromptTemplate,
  useDeletePromptTemplate,
  useStylePresets,
  useCreateStylePreset,
  useUpdateStylePreset,
  useDeleteStylePreset,
  useReorderStylePresets,
} from "@/hooks/useApi";
import {
  PROMPT_TEMPLATE_TYPE_LABELS,
  type PromptTemplate,
  type PromptTemplateType,
  type StylePreset,
} from "@/types";
import { useConfirm } from "@/components/ConfirmDialog";

const PROMPT_TEMPLATE_TYPES = Object.keys(
  PROMPT_TEMPLATE_TYPE_LABELS
) as PromptTemplateType[];

// 所有 Tab 值：模板类型 + 画风预置
const STYLE_PRESET_TAB = "__style_preset__";

export function SettingsPromptsPage() {
  const { data: templates, isLoading } = usePromptTemplates();

  return (
    <PageContainer
      title="提示词模版"
      description="管理剧本解析各阶段使用的 AI 提示词模板与画风预置，支持自定义与默认设置"
    >
      <Tabs defaultValue="character" className="w-full">
        <TabsList className="flex-wrap">
          {PROMPT_TEMPLATE_TYPES.map((type) => (
            <TabsTrigger key={type} value={type}>
              {PROMPT_TEMPLATE_TYPE_LABELS[type]}
            </TabsTrigger>
          ))}
          <TabsTrigger value={STYLE_PRESET_TAB}>
            <Palette className="mr-1 h-3.5 w-3.5" />
            画风预置
          </TabsTrigger>
        </TabsList>

        {isLoading ? (
          <LoadingState />
        ) : (
          <>
            {PROMPT_TEMPLATE_TYPES.map((type) => (
              <TabsContent key={type} value={type}>
                <TemplateTypePanel
                  templateType={type}
                  templates={templates?.filter((t) => t.template_type === type) || []}
                />
              </TabsContent>
            ))}
            <TabsContent value={STYLE_PRESET_TAB}>
              <StylePresetPanel />
            </TabsContent>
          </>
        )}
      </Tabs>
    </PageContainer>
  );
}

// ============================================================
// 画风预置面板（支持拖拽排序）
// ============================================================

function StylePresetPanel() {
  const { data: presets, isLoading } = useStylePresets();
  const reorderMutation = useReorderStylePresets();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<StylePreset | null>(null);

  // 拖拽排序状态
  const [localOrder, setLocalOrder] = useState<string[]>([]);
  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);

  // 同步服务端排序到本地
  useEffect(() => {
    if (presets) {
      const sorted = [...presets].sort(
        (a, b) => a.sort_order - b.sort_order || a.created_at.localeCompare(b.created_at)
      );
      setLocalOrder(sorted.map((p) => p.id));
    }
  }, [presets]);

  const sortedPresets = (() => {
    const map = new Map((presets || []).map((p) => [p.id, p]));
    return localOrder.map((id) => map.get(id)).filter(Boolean) as StylePreset[];
  })();

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (preset: StylePreset) => {
    setEditing(preset);
    setDialogOpen(true);
  };

  const handleDialogChange = (open: boolean) => {
    setDialogOpen(open);
    if (!open) setEditing(null);
  };

  // 拖拽事件
  const handleDragStart = (index: number) => {
    dragItem.current = index;
  };

  const handleDragEnter = (index: number) => {
    dragOverItem.current = index;
  };

  const handleDragEnd = () => {
    if (dragItem.current === null || dragOverItem.current === null) return;
    const from = dragItem.current;
    const to = dragOverItem.current;
    if (from === to) return;

    const newOrder = [...localOrder];
    const [moved] = newOrder.splice(from, 1);
    newOrder.splice(to, 0, moved);
    setLocalOrder(newOrder);

    // 发送到后端
    reorderMutation.mutate(newOrder);

    dragItem.current = null;
    dragOverItem.current = null;
  };

  if (isLoading) return <LoadingState />;

  const items = sortedPresets;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          共 {items.length} 个画风预置 · 拖拽卡片可排序 · 画风的描述文本会自动注入提示词模板的 {`{{style_hint}}`} 占位符
        </p>
        <Button onClick={openCreate}>
          <Plus className="mr-1 h-4 w-4" />
          新增画风
        </Button>
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="暂无画风预置"
          description="点击右上角新增画风"
        />
      ) : (
        <div className="space-y-2">
          {items.map((preset, index) => (
            <StylePresetCard
              key={preset.id}
              preset={preset}
              index={index}
              onEdit={() => openEdit(preset)}
              onDragStart={handleDragStart}
              onDragEnter={handleDragEnter}
              onDragEnd={handleDragEnd}
            />
          ))}
        </div>
      )}

      <StylePresetEditDialog
        open={dialogOpen}
        editing={editing}
        onOpenChange={handleDialogChange}
      />
    </div>
  );
}

function StylePresetCard({
  preset,
  index,
  onEdit,
  onDragStart,
  onDragEnter,
  onDragEnd,
}: {
  preset: StylePreset;
  index: number;
  onEdit: () => void;
  onDragStart: (index: number) => void;
  onDragEnter: (index: number) => void;
  onDragEnd: () => void;
}) {
  const updateMutation = useUpdateStylePreset();
  const deleteMutation = useDeleteStylePreset();
  const confirm = useConfirm();

  const handleSetDefault = () => {
    if (preset.is_default) return;
    updateMutation.mutate({ id: preset.id, is_default: true });
  };

  const handleDelete = async () => {
    if (await confirm({ title: `确定删除画风预置「${preset.title}」？`, variant: "destructive" })) {
      deleteMutation.mutate(preset.id);
    }
  };

  return (
    <Card
      draggable
      onDragStart={() => onDragStart(index)}
      onDragEnter={() => onDragEnter(index)}
      onDragEnd={onDragEnd}
      onDragOver={(e) => e.preventDefault()}
      className="cursor-grab active:cursor-grabbing transition-shadow hover:shadow-md"
    >
      <CardContent className="p-3">
        <div className="flex items-center gap-3">
          <GripVertical className="h-4 w-4 shrink-0 text-muted-foreground/50" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{preset.title}</span>
              {preset.is_default && (
                <Badge variant="success" className="text-xs">
                  <Star className="mr-1 h-3 w-3" />
                  默认
                </Badge>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground truncate">
              {preset.description}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {!preset.is_default && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={(e) => { e.stopPropagation(); handleSetDefault(); }}
                disabled={updateMutation.isPending}
              >
                <Star className="mr-1 h-3 w-3" />
                设默认
              </Button>
            )}
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); onEdit(); }}>
              <Pencil className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 hover:text-destructive"
              onClick={(e) => { e.stopPropagation(); handleDelete(); }}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function StylePresetEditDialog({
  open,
  editing,
  onOpenChange,
}: {
  open: boolean;
  editing: StylePreset | null;
  onOpenChange: (open: boolean) => void;
}) {
  const createMutation = useCreateStylePreset();
  const updateMutation = useUpdateStylePreset();

  const [form, setForm] = useState({
    title: "",
    description: "",
    is_default: false,
  });

  useEffect(() => {
    if (editing) {
      setForm({
        title: editing.title,
        description: editing.description,
        is_default: editing.is_default,
      });
    } else if (open) {
      setForm({
        title: "",
        description: "",
        is_default: false,
      });
    }
  }, [editing, open]);

  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleSubmit = () => {
    if (editing) {
      updateMutation.mutate({
        id: editing.id,
        title: form.title.trim(),
        description: form.description.trim(),
        is_default: form.is_default,
      });
    } else {
      createMutation.mutate({
        title: form.title.trim(),
        description: form.description.trim(),
        is_default: form.is_default,
      });
    }
    onOpenChange(false);
  };

  const canSubmit =
    form.title.trim() && form.description.trim() && !isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑画风预置" : "新增画风预置"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "修改画风预置的标题和提示词描述"
              : "创建画风预置，标题用于选择器展示，描述会注入提示词模板的 {{style_hint}} 占位符"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>标题 *</Label>
            <Input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="如：写实摄影、二次元动漫"
            />
            <p className="text-xs text-muted-foreground">
              画风选项名，用于项目设置和剧本页的选择器展示
            </p>
          </div>

          <div className="space-y-2">
            <Label>提示词描述 *</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="如：写实摄影，真实感影像，电影级画质，8K超高清"
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              解析时自动注入提示词模板 {`{{style_hint}}`} 占位符的文本，应作为每个提示词的第一句
            </p>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
            />
            设为默认画风
          </label>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!canSubmit} onClick={handleSubmit}>
            {isPending ? "保存中..." : editing ? "保存" : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
// 提示词模板面板（原有逻辑不变）
// ============================================================

function TemplateTypePanel({
  templateType,
  templates,
}: {
  templateType: PromptTemplateType;
  templates: PromptTemplate[];
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PromptTemplate | null>(null);

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (tmpl: PromptTemplate) => {
    setEditing(tmpl);
    setDialogOpen(true);
  };

  const handleDialogChange = (open: boolean) => {
    setDialogOpen(open);
    if (!open) setEditing(null);
  };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          共 {templates.length} 个模板 · 每个类型可设置一个默认模板
        </p>
        <Button onClick={openCreate}>
          <Plus className="mr-1 h-4 w-4" />
          新增模板
        </Button>
      </div>

      {templates.length === 0 ? (
        <EmptyState
          icon={FileText}
          title={`暂无${PROMPT_TEMPLATE_TYPE_LABELS[templateType]}模板`}
          description="点击右上角新增模板，或等待系统初始化内置模板"
        />
      ) : (
        <div className="space-y-3">
          {templates
            .slice()
            .sort((a, b) => b.sort_order - a.sort_order || a.created_at.localeCompare(b.created_at))
            .map((tmpl) => (
              <TemplateCard
                key={tmpl.id}
                template={tmpl}
                onEdit={() => openEdit(tmpl)}
              />
            ))}
        </div>
      )}

      <TemplateEditDialog
        open={dialogOpen}
        editing={editing}
        defaultType={templateType}
        onOpenChange={handleDialogChange}
      />
    </div>
  );
}

function TemplateCard({
  template,
  onEdit,
}: {
  template: PromptTemplate;
  onEdit: () => void;
}) {
  const updateMutation = useUpdatePromptTemplate();
  const deleteMutation = useDeletePromptTemplate();
  const confirm = useConfirm();

  const handleSetDefault = () => {
    if (template.is_default) return;
    updateMutation.mutate({ id: template.id, is_default: true });
  };

  const handleDelete = async () => {
    if (await confirm({ title: `确定删除模板「${template.name}」？`, variant: "destructive" })) {
      deleteMutation.mutate(template.id);
    }
  };

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{template.name}</span>
              {template.is_default && (
                <Badge variant="success" className="text-xs">
                  <Star className="mr-1 h-3 w-3" />
                  默认
                </Badge>
              )}
              {template.is_builtin && (
                <Badge variant="secondary" className="text-xs">
                  <Shield className="mr-1 h-3 w-3" />
                  内置
                </Badge>
              )}
              <Badge variant="outline" className="text-xs">
                排序 {template.sort_order}
              </Badge>
            </div>
            {template.description && (
              <p className="mt-1 text-xs text-muted-foreground">{template.description}</p>
            )}
            <p className="mt-2 line-clamp-2 whitespace-pre-wrap text-xs text-muted-foreground/80">
              {template.content}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {!template.is_default && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8"
                onClick={handleSetDefault}
                disabled={updateMutation.isPending}
              >
                <Star className="mr-1 h-3.5 w-3.5" />
                设默认
              </Button>
            )}
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onEdit}>
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            {!template.is_builtin && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 hover:text-destructive"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function TemplateEditDialog({
  open,
  editing,
  defaultType,
  onOpenChange,
}: {
  open: boolean;
  editing: PromptTemplate | null;
  defaultType: PromptTemplateType;
  onOpenChange: (open: boolean) => void;
}) {
  const createMutation = useCreatePromptTemplate();
  const updateMutation = useUpdatePromptTemplate();

  const [form, setForm] = useState({
    name: "",
    template_type: defaultType,
    description: "",
    content: "",
    is_default: false,
    sort_order: 0,
  });

  useEffect(() => {
    if (editing) {
      setForm({
        name: editing.name,
        template_type: editing.template_type,
        description: editing.description || "",
        content: editing.content,
        is_default: editing.is_default,
        sort_order: editing.sort_order,
      });
    } else if (open) {
      setForm({
        name: "",
        template_type: defaultType,
        description: "",
        content: "",
        is_default: false,
        sort_order: 0,
      });
    }
  }, [editing, open, defaultType]);

  const isBuiltin = editing?.is_builtin ?? false;
  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleSubmit = () => {
    if (editing) {
      if (isBuiltin) {
        // 内置模板仅允许修改 content / description / sort_order
        updateMutation.mutate({
          id: editing.id,
          content: form.content,
          description: form.description.trim() || undefined,
          sort_order: Number.isNaN(form.sort_order) ? 0 : form.sort_order,
        });
      } else {
        updateMutation.mutate({
          id: editing.id,
          name: form.name.trim(),
          template_type: form.template_type,
          description: form.description.trim() || undefined,
          content: form.content,
          is_default: form.is_default,
          sort_order: Number.isNaN(form.sort_order) ? 0 : form.sort_order,
        });
      }
    } else {
      createMutation.mutate({
        name: form.name.trim(),
        template_type: form.template_type,
        description: form.description.trim() || undefined,
        content: form.content,
        is_default: form.is_default,
        sort_order: Number.isNaN(form.sort_order) ? 0 : form.sort_order,
      });
    }
    onOpenChange(false);
  };

  const canSubmit =
    form.name.trim() && form.content.trim() && !isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑模板" : "新增模板"}</DialogTitle>
          <DialogDescription>
            {editing
              ? isBuiltin
                ? "内置模板仅允许修改内容、描述和排序"
                : "修改模板内容，可重新设置默认模板"
              : "创建自定义提示词模板，用于剧本解析阶段"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>名称 *</Label>
            <Input
              value={form.name}
              disabled={isBuiltin}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：自定义角色提取"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>模板类型</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                value={form.template_type}
                disabled={!!editing}
                onChange={(e) =>
                  setForm({ ...form, template_type: e.target.value as PromptTemplateType })
                }
              >
                {PROMPT_TEMPLATE_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {PROMPT_TEMPLATE_TYPE_LABELS[type]}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>排序权重</Label>
              <Input
                type="number"
                value={form.sort_order}
                onChange={(e) =>
                  setForm({ ...form, sort_order: parseInt(e.target.value || "0", 10) })
                }
                placeholder="数值越大越靠前"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>描述</Label>
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="简要说明该模板的用途"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>提示词内容 *</Label>
              <span className="text-xs text-muted-foreground">
                支持 {"{{script_text}}"}、{"{{characters}}"}、{"{{scenes}}"}、{"{{props}}"}、{"{{style_hint}}"} 等占位符
              </span>
            </div>
            <Textarea
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder="在此输入提示词内容..."
              rows={12}
              className="font-mono text-xs"
            />
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
            />
            设为该类型默认模板
          </label>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!canSubmit} onClick={handleSubmit}>
            {isPending ? "保存中..." : editing ? "保存" : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
