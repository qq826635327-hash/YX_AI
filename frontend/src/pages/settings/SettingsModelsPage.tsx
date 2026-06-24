/** 配置中心 - 模型配置：为每个 Provider 下的模型配置参数规范和能力声明。 */

import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Plus, Trash2, Save } from "lucide-react";
import { PageContainer, LoadingState, EmptyState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProviders, useUpdateProvider } from "@/hooks/useApi";
import { MODEL_TAG_LABELS } from "@/types";
import type {
  ApiProvider,
  ModelCapabilitiesConfig,
  ParamSpec,
  ProviderModelInput,
} from "@/types";

// ============================================================
// 主页面
// ============================================================

export function SettingsModelsPage() {
  const { data: providers, isLoading } = useProviders();
  const [selectedId, setSelectedId] = useState<string>("");

  // 切换 Provider 列表时自动选中第一个
  useEffect(() => {
    if (providers && providers.length > 0 && !providers.find((p) => p.id === selectedId)) {
      setSelectedId(providers[0].id);
    }
  }, [providers, selectedId]);

  const selectedProvider = providers?.find((p) => p.id === selectedId);

  if (isLoading) return <LoadingState />;

  return (
    <PageContainer title="模型配置" description="为每个 Provider 下的模型配置参数规范与能力声明">
      {/* Provider 选择器 */}
      <div className="mb-6 flex items-center gap-3">
        <Label className="shrink-0">选择 Provider</Label>
        <Select value={selectedId} onValueChange={setSelectedId}>
          <SelectTrigger className="w-64">
            <SelectValue placeholder="请选择 Provider" />
          </SelectTrigger>
          <SelectContent>
            {providers && providers.length > 0 ? (
              providers.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                  <span className="ml-2 text-xs text-muted-foreground">({p.provider_kind})</span>
                </SelectItem>
              ))
            ) : (
              <SelectItem value="__none" disabled>
                暂无 Provider
              </SelectItem>
            )}
          </SelectContent>
        </Select>
      </div>

      {/* 模型列表 */}
      {selectedProvider ? (
        <ModelListEditor provider={selectedProvider} />
      ) : (
        <EmptyState title="请先选择一个 Provider" description="在上方下拉框中选择要配置的 API Provider" />
      )}
    </PageContainer>
  );
}

// ============================================================
// 模型列表编辑器
// ============================================================

function ModelListEditor({ provider }: { provider: ApiProvider }) {
  const updateMutation = useUpdateProvider();

  // 本地编辑状态：深拷贝 models
  const [localModels, setLocalModels] = useState<ProviderModelInput[]>([]);

  useEffect(() => {
    setLocalModels(
      provider.models.map((m) => ({
        id: m.id,
        model_name: m.model_name,
        tags: [...m.tags],
        sort_order: m.sort_order,
        param_specs: m.param_specs ? m.param_specs.map((ps) => ({ ...ps })) : null,
        capabilities: m.capabilities ? { ...m.capabilities } : null,
      }))
    );
  }, [provider]);

  const handleSave = () => {
    updateMutation.mutate({
      id: provider.id,
      models: localModels,
    });
  };

  const hasChanges = JSON.stringify(localModels) !== JSON.stringify(
    provider.models.map((m) => ({
      id: m.id,
      model_name: m.model_name,
      tags: [...m.tags],
      sort_order: m.sort_order,
      param_specs: m.param_specs ? m.param_specs.map((ps) => ({ ...ps })) : null,
      capabilities: m.capabilities ? { ...m.capabilities } : null,
    }))
  );

  return (
    <div>
      <div className="space-y-4">
        {localModels.map((model, idx) => (
          <ModelCard
            key={model.id || idx}
            model={model}
            onChange={(updated) => {
              const next = [...localModels];
              next[idx] = updated;
              setLocalModels(next);
            }}
          />
        ))}
      </div>

      {localModels.length === 0 && (
        <EmptyState title="该 Provider 暂无模型" description="请先在 API Provider 页面为该 Provider 添加模型" />
      )}

      {localModels.length > 0 && (
        <div className="mt-6 flex justify-end">
          <Button
            onClick={handleSave}
            disabled={!hasChanges || updateMutation.isPending}
          >
            <Save className="mr-2 h-4 w-4" />
            {updateMutation.isPending ? "保存中..." : "保存修改"}
          </Button>
        </div>
      )}
    </div>
  );
}

// ============================================================
// 单个模型卡片
// ============================================================

function ModelCard({
  model,
  onChange,
}: {
  model: ProviderModelInput;
  onChange: (updated: ProviderModelInput) => void;
}) {
  const [paramsOpen, setParamsOpen] = useState(false);
  const [capsOpen, setCapsOpen] = useState(false);

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        {/* 模型名称 + 标签 */}
        <div>
          <span className="font-medium text-base">{model.model_name}</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {model.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {MODEL_TAG_LABELS[tag] || tag}
              </Badge>
            ))}
          </div>
        </div>

        {/* 参数规范折叠区 */}
        <div className="rounded-md border">
          <button
            type="button"
            className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium hover:bg-muted/50 transition-colors"
            onClick={() => setParamsOpen(!paramsOpen)}
          >
            <span className="flex items-center gap-2">
              {paramsOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              参数规范
              {model.param_specs ? (
                <Badge variant="outline" className="text-xs">({model.param_specs.length}项)</Badge>
              ) : (
                <Badge variant="outline" className="text-xs">(使用 Handler 默认)</Badge>
              )}
            </span>
          </button>
          {paramsOpen && (
            <ParamSpecsEditor
              specs={model.param_specs ?? null}
              onChange={(specs) => onChange({ ...model, param_specs: specs ?? null })}
            />
          )}
        </div>

        {/* 能力声明折叠区 */}
        <div className="rounded-md border">
          <button
            type="button"
            className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium hover:bg-muted/50 transition-colors"
            onClick={() => setCapsOpen(!capsOpen)}
          >
            <span className="flex items-center gap-2">
              {capsOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              能力声明
              {model.capabilities ? (
                <Badge variant="outline" className="text-xs">(已自定义)</Badge>
              ) : (
                <Badge variant="outline" className="text-xs">(使用 Handler 默认)</Badge>
              )}
            </span>
          </button>
          {capsOpen && (
            <CapabilitiesEditor
              caps={model.capabilities ?? null}
              onChange={(caps) => onChange({ ...model, capabilities: caps ?? null })}
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================
// 参数规范编辑器
// ============================================================

const INPUT_TYPE_OPTIONS: ParamSpec["input_type"][] = ["select", "text", "number", "slider"];

const INPUT_TYPE_LABELS: Record<ParamSpec["input_type"], string> = {
  select: "下拉选择",
  text: "文本",
  number: "数字",
  slider: "滑块",
};

function ParamSpecsEditor({
  specs,
  onChange,
}: {
  specs: ParamSpec[] | null;
  onChange: (specs: ParamSpec[] | null) => void;
}) {
  // 如果 specs 为 null，展开时初始化为空数组让用户开始编辑
  const currentSpecs = specs ?? [];

  const handleAdd = () => {
    const newSpec: ParamSpec = {
      key: "",
      label: "",
      required: false,
      input_type: "text",
    };
    onChange([...currentSpecs, newSpec]);
  };

  const handleUpdate = (idx: number, updated: ParamSpec) => {
    const next = [...currentSpecs];
    next[idx] = updated;
    onChange(next);
  };

  const handleRemove = (idx: number) => {
    const next = currentSpecs.filter((_, i) => i !== idx);
    onChange(next.length === 0 ? null : next);
  };

  return (
    <div className="px-3 pb-3 space-y-3">
      {currentSpecs.length === 0 && (
        <p className="text-xs text-muted-foreground py-2">
          暂无参数规范，将使用 Handler 默认值。点击下方按钮添加自定义参数。
        </p>
      )}

      {currentSpecs.map((spec, idx) => (
        <ParamSpecItem
          key={idx}
          spec={spec}
          onChange={(updated) => handleUpdate(idx, updated)}
          onRemove={() => handleRemove(idx)}
        />
      ))}

      <Button type="button" variant="outline" size="sm" onClick={handleAdd}>
        <Plus className="mr-1 h-3 w-3" /> 添加参数
      </Button>
    </div>
  );
}

function ParamSpecItem({
  spec,
  onChange,
  onRemove,
}: {
  spec: ParamSpec;
  onChange: (updated: ParamSpec) => void;
  onRemove: () => void;
}) {
  const update = (partial: Partial<ParamSpec>) => onChange({ ...spec, ...partial });

  return (
    <div className="rounded-md border bg-muted/30 p-3 space-y-2">
      {/* 第一行：key + label + 必填 + 删除 */}
      <div className="flex items-start gap-2">
        <div className="flex-1 space-y-1">
          <Label className="text-xs">Key (标识)</Label>
          <Input
            value={spec.key}
            onChange={(e) => update({ key: e.target.value })}
            placeholder="如 size"
            className="h-8 text-sm"
          />
        </div>
        <div className="flex-1 space-y-1">
          <Label className="text-xs">标签 (显示名)</Label>
          <Input
            value={spec.label}
            onChange={(e) => update({ label: e.target.value })}
            placeholder="如 分辨率"
            className="h-8 text-sm"
          />
        </div>
        <label className="flex items-center gap-1.5 pt-5 shrink-0 text-xs">
          <input
            type="checkbox"
            checked={spec.required}
            onChange={(e) => update({ required: e.target.checked })}
          />
          必填
        </label>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="shrink-0 mt-5 h-7 w-7 hover:text-destructive"
          onClick={onRemove}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* 第二行：输入类型 + 默认值 + placeholder */}
      <div className="flex items-start gap-2">
        <div className="w-32 space-y-1">
          <Label className="text-xs">输入类型</Label>
          <select
            className="flex h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
            value={spec.input_type}
            onChange={(e) => update({ input_type: e.target.value as ParamSpec["input_type"] })}
          >
            {INPUT_TYPE_OPTIONS.map((t) => (
              <option key={t} value={t}>{INPUT_TYPE_LABELS[t]}</option>
            ))}
          </select>
        </div>
        <div className="flex-1 space-y-1">
          <Label className="text-xs">默认值</Label>
          <Input
            value={spec.default ?? ""}
            onChange={(e) => update({ default: e.target.value || undefined })}
            placeholder="可选"
            className="h-8 text-sm"
          />
        </div>
        <div className="flex-1 space-y-1">
          <Label className="text-xs">占位提示</Label>
          <Input
            value={spec.placeholder ?? ""}
            onChange={(e) => update({ placeholder: e.target.value || undefined })}
            placeholder="可选"
            className="h-8 text-sm"
          />
        </div>
      </div>

      {/* select 类型：选项列表 + allow_custom */}
      {spec.input_type === "select" && (
        <div className="space-y-1">
          <Label className="text-xs">选项列表（逗号分隔）</Label>
          <Input
            value={spec.options?.join(", ") ?? ""}
            onChange={(e) => {
              const opts = e.target.value
                .split(/[,，]/)
                .map((s) => s.trim())
                .filter(Boolean);
              update({ options: opts.length > 0 ? opts : undefined });
            }}
            placeholder="512x512, 1024x1024, 1920x1080"
            className="h-8 text-sm"
          />
          <label className="flex items-center gap-1.5 text-xs">
            <input
              type="checkbox"
              checked={spec.allow_custom ?? false}
              onChange={(e) => update({ allow_custom: e.target.checked || undefined })}
            />
            允许自定义输入
          </label>
        </div>
      )}

      {/* number / slider 类型：min / max / step */}
      {(spec.input_type === "number" || spec.input_type === "slider") && (
        <div className="flex items-start gap-2">
          <div className="flex-1 space-y-1">
            <Label className="text-xs">最小值</Label>
            <Input
              type="number"
              value={spec.min ?? ""}
              onChange={(e) => update({ min: e.target.value ? Number(e.target.value) : undefined })}
              className="h-8 text-sm"
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label className="text-xs">最大值</Label>
            <Input
              type="number"
              value={spec.max ?? ""}
              onChange={(e) => update({ max: e.target.value ? Number(e.target.value) : undefined })}
              className="h-8 text-sm"
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label className="text-xs">步长</Label>
            <Input
              type="number"
              value={spec.step ?? ""}
              onChange={(e) => update({ step: e.target.value ? Number(e.target.value) : undefined })}
              className="h-8 text-sm"
            />
          </div>
        </div>
      )}

      {/* 帮助文本 */}
      <div className="space-y-1">
        <Label className="text-xs">帮助文本</Label>
        <Input
          value={spec.help_text ?? ""}
          onChange={(e) => update({ help_text: e.target.value || undefined })}
          placeholder="可选，鼠标悬停时显示"
          className="h-8 text-sm"
        />
      </div>
    </div>
  );
}

// ============================================================
// 能力声明编辑器
// ============================================================

const CAP_BOOLEAN_FIELDS: { key: keyof ModelCapabilitiesConfig; label: string }[] = [
  { key: "image_generation", label: "图片生成" },
  { key: "image_to_image", label: "图生图" },
  { key: "video_generation", label: "视频生成" },
  { key: "batch_support", label: "批量支持" },
  { key: "supports_negative_prompt", label: "支持反向提示词" },
  { key: "reference_images_need_url", label: "参考图需要公网URL" },
];

const CAP_NUMBER_FIELDS: { key: keyof ModelCapabilitiesConfig; label: string; placeholder: string }[] = [
  { key: "max_count", label: "最大生成数", placeholder: "如 4" },
  { key: "max_reference_images", label: "最大参考图数", placeholder: "如 5" },
];

function CapabilitiesEditor({
  caps,
  onChange,
}: {
  caps: ModelCapabilitiesConfig | null;
  onChange: (caps: ModelCapabilitiesConfig | null) => void;
}) {
  // null 时使用空对象让用户开始编辑
  const current = caps ?? {};

  const updateField = (key: keyof ModelCapabilitiesConfig, value: unknown) => {
    onChange({ ...current, [key]: value });
  };

  const handleCustomSizeChange = (index: 0 | 1, value: number | "") => {
    const prev = current.custom_size_range ?? [0, 0];
    const next: [number, number] = [...prev];
    next[index] = value === "" ? 0 : value;
    updateField("custom_size_range", next);
  };

  return (
    <div className="px-3 pb-3 space-y-4">
      {caps === null && (
        <p className="text-xs text-muted-foreground">
          当前使用 Handler 默认能力声明。修改任意字段后将覆盖默认值。
        </p>
      )}

      {/* 布尔能力 */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {CAP_BOOLEAN_FIELDS.map(({ key, label }) => (
          <label key={key} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={current[key] as boolean ?? false}
              onChange={(e) => updateField(key, e.target.checked)}
            />
            {label}
          </label>
        ))}
      </div>

      {/* 数值能力 */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {CAP_NUMBER_FIELDS.map(({ key, label, placeholder }) => (
          <div key={key} className="flex items-center gap-2">
            <Label className="text-sm shrink-0">{label}</Label>
            <Input
              type="number"
              value={current[key] as number ?? ""}
              onChange={(e) => updateField(key, e.target.value ? Number(e.target.value) : undefined)}
              placeholder={placeholder}
              className="h-8 w-24 text-sm"
            />
          </div>
        ))}
      </div>

      {/* 自定义尺寸范围 */}
      <div className="flex items-center gap-2">
        <Label className="text-sm shrink-0">自定义尺寸范围</Label>
        <Input
          type="number"
          value={current.custom_size_range?.[0] ?? ""}
          onChange={(e) => handleCustomSizeChange(0, e.target.value ? Number(e.target.value) : "")}
          placeholder="最小"
          className="h-8 w-24 text-sm"
        />
        <span className="text-muted-foreground">-</span>
        <Input
          type="number"
          value={current.custom_size_range?.[1] ?? ""}
          onChange={(e) => handleCustomSizeChange(1, e.target.value ? Number(e.target.value) : "")}
          placeholder="最大"
          className="h-8 w-24 text-sm"
        />
      </div>

      {/* 视频参考图配置（仅视频生成模型显示） */}
      {current.video_generation && (
      <div className="space-y-2 rounded-md border p-3">
        <Label className="text-sm font-medium">视频参考图配置</Label>
        <p className="text-xs text-muted-foreground">
          配置视频生成时的默认参考图类型，用户可在生成弹窗中手动调整
        </p>
        <div className="flex flex-wrap gap-3">
          {([
            { value: "first_frame", label: "首帧" },
            { value: "last_frame", label: "尾帧" },
            { value: "character", label: "人物" },
            { value: "scene", label: "场景" },
            { value: "prop", label: "道具" },
          ] as const).map((opt) => (
            <label key={opt.value} className="flex items-center gap-1.5 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={(current.video_reference_types ?? []).includes(opt.value)}
                onChange={(e) => {
                  const prev = current.video_reference_types ?? [];
                  const next = e.target.checked
                    ? [...prev, opt.value]
                    : prev.filter((t) => t !== opt.value);
                  updateField("video_reference_types", next.length > 0 ? next : undefined);
                }}
              />
              {opt.label}
            </label>
          ))}
        </div>
        <div className="space-y-1">
          <Label className="text-xs">提示文案</Label>
          <Input
            value={current.video_reference_hint ?? ""}
            onChange={(e) => updateField("video_reference_hint", e.target.value || undefined)}
            placeholder="如：当前模型为首尾关键帧模式，建议仅选择首帧和尾帧"
            className="h-8 text-sm"
          />
        </div>
      </div>
      )}

      {/* 重置为默认按钮 */}
      {caps !== null && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          onClick={() => onChange(null)}
        >
          重置为 Handler 默认
        </Button>
      )}
    </div>
  );
}
