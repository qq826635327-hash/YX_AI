/**
 * 生成配置弹窗：选择模型、调整参数、提交生成任务。
 *
 * 支持单个实体和批量模式。
 */

import { useState, useEffect, useMemo, useCallback, memo } from "react";
import { X } from "lucide-react";
import { toast } from "@/stores/ui";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProviders, useGenerate, useBatchGenerate, useProviderCapabilities, useWorkflows, useSystemConfig } from "@/hooks/useApi";
import {
  MODEL_TAG_LABELS,
} from "@/types";
import type {
  TargetType,
  ApiProvider,
  ProviderCapabilities,
  ParamSpec,
  ExtraField,
  ProviderModel,
  ModelTag,
} from "@/types";

// ============================================================
// 类型
// ============================================================

export interface GenerateTarget {
  target_type: TargetType;
  target_id: string;
  name?: string;
  prompt?: string;
  /** 首帧素材ID，用于尾帧/视频生成时校验首帧是否存在 */
  firstFrameAssetId?: string;
}

interface GenerateDialogProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  projectId: string;
  /** 单个实体或批量 */
  targets: GenerateTarget[];
  /** 默认 prompt（单个时使用） */
  defaultPrompt?: string;
  /** 提交完成回调 */
  onSuccess?: () => void;
}

// ============================================================
// 组件
// ============================================================

/** 批量任务摘要展示 */
function BatchSummary({ targets }: { targets: GenerateTarget[] }) {
  return (
    <div className="rounded-md border p-3">
      <Label className="text-xs text-muted-foreground">将生成 {targets.length} 个任务：</Label>
      <div className="mt-1 flex flex-wrap gap-1">
        {targets.slice(0, 10).map((t) => (
          <Badge key={t.target_id} variant="secondary" className="text-xs">
            {t.name || t.target_id.slice(0, 8)}
          </Badge>
        ))}
        {targets.length > 10 && (
          <Badge variant="secondary" className="text-xs">
            +{targets.length - 10} 更多
          </Badge>
        )}
      </div>
    </div>
  );
}

/** 引擎选择按钮组 */
function EngineSelector({
  engineType,
  onEngineTypeChange,
}: {
  engineType: "api" | "comfyui";
  onEngineTypeChange: (v: "api" | "comfyui") => void;
}) {
  return (
    <div className="space-y-2">
      <Label>生成引擎</Label>
      <div className="flex gap-2">
        <Button
          variant={engineType === "api" ? "default" : "outline"}
          size="sm"
          onClick={() => onEngineTypeChange("api")}
        >
          API Provider
        </Button>
        <Button
          variant={engineType === "comfyui" ? "default" : "outline"}
          size="sm"
          onClick={() => onEngineTypeChange("comfyui")}
        >
          ComfyUI 本地
        </Button>
      </div>
    </div>
  );
}

export function GenerateDialog({
  open,
  onOpenChange,
  projectId,
  targets,
  defaultPrompt,
  onSuccess,
}: GenerateDialogProps) {
  const isBatch = targets.length > 1;

  // 模型选择（格式：provider_id|model_name）
  const [engineType, setEngineType] = useState<"comfyui" | "api">("api");
  const [selectedModelKey, setSelectedModelKey] = useState<string>("");
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");

  const selectedProviderId = useMemo(() => selectedModelKey.split("|")[0] || "", [selectedModelKey]);
  const selectedModelName = useMemo(() => selectedModelKey.split("|")[1] || "", [selectedModelKey]);

  // 动态参数（根据 param_specs 收集）
  const [params, setParams] = useState<Record<string, string>>({});
  const [count, setCount] = useState<number>(1);

  // Prompt
  const [prompt, setPrompt] = useState(defaultPrompt || "");

  // 参考图（当 target_type 为 shot_* 时可传入参考资产 ID）
  const [referenceAssetIds, setReferenceAssetIds] = useState<string[]>([]);

  // 视频参考图类型选择（仅 shot_video）
  const [videoRefTypes, setVideoRefTypes] = useState<string[]>([]);

  // 是否是视频目标
  const isVideoTarget = targets[0]?.target_type === "shot_video";

  // Hooks
  const { data: providers } = useProviders(true);
  const { data: workflows } = useWorkflows();
  const { data: sysConfig } = useSystemConfig();
  const generateMutation = useGenerate();
  const batchMutation = useBatchGenerate();

  // 根据 target_type 判断需要的能力
  const requiredCapability = useMemo(() => {
    const targetType = targets[0]?.target_type;
    if (targetType === "shot_video") return "video_generation";
    if (["character", "scene", "prop", "shot_first_frame", "shot_last_frame"].includes(targetType || ""))
      return "image_generation";
    return null;
  }, [targets]);

  // 平铺所有 Provider 下的模型作为选项，按 target_type 过滤
  const modelOptions = useMemo(() => {
    const options: { key: string; provider: ApiProvider; model: ProviderModel }[] = [];
    for (const p of providers || []) {
      const models = p.models?.length
        ? p.models
        : p.model
          ? [{ id: "", model_name: p.model, tags: [], sort_order: 0 } as ProviderModel]
          : [];
      for (const m of models) {
        // 按能力过滤：生图只显示 image_generation 模型，生视频只显示 video_generation 模型
        if (requiredCapability) {
          const hasCapability = m.tags?.includes(requiredCapability as ModelTag);
          if (!hasCapability) continue;
        }
        options.push({ key: `${p.id}|${m.model_name}`, provider: p, model: m });
      }
    }
    return options;
  }, [providers, requiredCapability]);

  // 能力查询
  const isComfyui = engineType === "comfyui";
  const { data: capabilities } = useProviderCapabilities(
    engineType === "api" ? selectedProviderId : undefined,
    engineType === "api" ? selectedModelName : undefined,
    isComfyui,
  );

  // 打开时重置表单 + 自动选择默认模型（合并为一个 effect 避免竞态条件）
  useEffect(() => {
    if (!open) return;

    // 重置表单
    setPrompt(defaultPrompt || "");
    setEngineType("api");
    setSelectedWorkflowId("");
    setCount(1);
    setReferenceAssetIds([]);
    setVideoRefTypes([]);

    // 自动选择默认模型
    if (modelOptions.length > 0) {
      const defaultModelName =
        requiredCapability === "video_generation"
          ? sysConfig?.default_models?.default_video_model
          : requiredCapability === "image_generation"
            ? sysConfig?.default_models?.default_image_model
            : requiredCapability === "text_reasoning"
              ? sysConfig?.default_models?.default_text_model
              : null;

      let def = modelOptions[0];
      if (defaultModelName) {
        const matched = modelOptions.find((o) => o.model.model_name === defaultModelName);
        if (matched) def = matched;
      } else {
        const defaultProvider = providers?.find((p) => p.is_default);
        if (defaultProvider) {
          const matched = modelOptions.find((o) => o.provider.id === defaultProvider.id);
          if (matched) def = matched;
        }
      }
      setSelectedModelKey(def.key);
    } else {
      setSelectedModelKey("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultPrompt]);

  // providers 异步加载完成时补选默认模型（弹窗已打开但尚未选中模型）
  useEffect(() => {
    if (!open || modelOptions.length === 0 || selectedModelKey) return;

    const defaultModelName =
      requiredCapability === "video_generation"
        ? sysConfig?.default_models?.default_video_model
        : requiredCapability === "image_generation"
          ? sysConfig?.default_models?.default_image_model
          : requiredCapability === "text_reasoning"
            ? sysConfig?.default_models?.default_text_model
            : null;

    let def = modelOptions[0];
    if (defaultModelName) {
      const matched = modelOptions.find((o) => o.model.model_name === defaultModelName);
      if (matched) def = matched;
    } else {
      const defaultProvider = providers?.find((p) => p.is_default);
      if (defaultProvider) {
        const matched = modelOptions.find((o) => o.provider.id === defaultProvider.id);
        if (matched) def = matched;
      }
    }
    setSelectedModelKey(def.key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, modelOptions.length, requiredCapability, sysConfig]);

  // 能力变化时重置参数（根据 param_specs 初始化）
  useEffect(() => {
    if (capabilities && capabilities.param_specs) {
      // 根据 param_specs 的默认值初始化 params
      const defaults: Record<string, string> = {};
      for (const spec of capabilities.param_specs) {
        if (spec.default) {
          defaults[spec.key] = spec.default;
        }
      }
      setParams(defaults);
      setCount(1);
    }
    // 视频目标：初始化参考图类型为模型默认值
    if (isVideoTarget && capabilities?.video_reference_types) {
      setVideoRefTypes([...capabilities.video_reference_types]);
    } else {
      setVideoRefTypes([]);
    }
  }, [capabilities, isVideoTarget]);

  // 是否是分镜目标
  const isShotTarget = !isBatch && targets[0]?.target_type?.startsWith("shot_");

  const isSubmitting = generateMutation.isPending || batchMutation.isPending;

  const handleSubmit = async () => {
    // 兜底：提交前用 capabilities 的默认值填充未填的必填参数
    const finalParams = { ...params };
    if (capabilities?.param_specs) {
      for (const spec of capabilities.param_specs) {
        if (spec.required && !finalParams[spec.key] && spec.default) {
          finalParams[spec.key] = spec.default;
        }
      }
    }
    // 视频目标：将参考图类型选择写入 extra_params
    if (isVideoTarget && videoRefTypes.length > 0) {
      finalParams.reference_types = videoRefTypes.join(",");
    }

    // 尾帧/视频生成：校验首帧是否存在，过滤无首帧的分镜
    const needsFirstFrame = (t: GenerateTarget) =>
      t.target_type === "shot_last_frame" || t.target_type === "shot_video";
    const hasFirstFrame = (t: GenerateTarget) => !!t.firstFrameAssetId;

    if (isBatch) {
      const needsCheck = targets.filter(needsFirstFrame);
      if (needsCheck.length > 0) {
        const withoutFirstFrame = needsCheck.filter((t) => !hasFirstFrame(t));
        if (withoutFirstFrame.length > 0) {
          toast.warning(`已跳过 ${withoutFirstFrame.length} 个无首帧的分镜，请先生成首帧`);
        }
      }
    } else if (targets.length === 1 && needsFirstFrame(targets[0]) && !hasFirstFrame(targets[0])) {
      toast.warning("请先生成首帧后再生成尾帧/视频");
      return;
    }

    const baseParams = {
      provider_type: engineType,
      provider_id: engineType === "api" ? selectedProviderId : undefined,
      model: engineType === "api" ? selectedModelName : undefined,
      workflow_mapping_id: engineType === "comfyui" ? selectedWorkflowId : undefined,
      extra_params: finalParams,
      count,
      reference_asset_ids: referenceAssetIds.length > 0 ? referenceAssetIds : undefined,
    } as Record<string, unknown>;

    try {
      if (isBatch) {
        // 过滤掉无首帧的尾帧/视频目标
        const filteredTargets = targets.filter((t) => {
          if (needsFirstFrame(t) && !hasFirstFrame(t)) return false;
          return true;
        });
        if (filteredTargets.length === 0) {
          toast.warning("所有选中分镜均无首帧，无法生成");
          return;
        }
        const batchPayload = {
          project_id: projectId,
          targets: filteredTargets.map((t) => ({
            target_type: t.target_type,
            target_id: t.target_id,
            prompt: t.prompt || prompt,
          })),
          ...baseParams,
          provider_type: engineType,
        } as Parameters<typeof batchMutation.mutateAsync>[0];
        await batchMutation.mutateAsync(batchPayload);
      } else {
        const singlePayload = {
          project_id: projectId,
          target_type: targets[0].target_type,
          target_id: targets[0].target_id,
          prompt: prompt || targets[0].prompt,
          ...baseParams,
        };
        await generateMutation.mutateAsync(singlePayload);
      }

      onOpenChange(false);
      onSuccess?.();
    } catch {
      // mutateAsync 失败已由 React Query onError 回调处理（显示 toast）
    }
  };

  const targetLabel = useMemo(() => {
    const typeMap: Record<string, string> = {
      character: "角色",
      scene: "场景",
      prop: "道具",
      shot_first_frame: "首帧",
      shot_last_frame: "尾帧",
      shot_video: "视频",
    };
    if (targets.length === 0) {
      return "生成配置";
    }
    if (isBatch) {
      return `为 ${targets.length} 个目标生成`;
    }
    const t = targets[0];
    const typeName = typeMap[t.target_type] || t.target_type;
    return `${typeName}${t.name ? `: ${t.name}` : ""}`;
  }, [targets, isBatch]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>生成配置</DialogTitle>
          <DialogDescription>{targetLabel}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* 引擎选择 */}
          <EngineSelector engineType={engineType} onEngineTypeChange={setEngineType} />

          {/* API 模型选择 */}
          {engineType === "api" && (
            <div className="space-y-2">
              <Label>选择模型</Label>
              <Select value={selectedModelKey} onValueChange={setSelectedModelKey}>
                <SelectTrigger>
                  <SelectValue placeholder="选择模型" />
                </SelectTrigger>
                <SelectContent>
                  {modelOptions.map((o) => (
                    <SelectItem key={o.key} value={o.key}>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{o.model.model_name}</span>
                        <span className="text-xs text-muted-foreground">({o.provider.name})</span>
                        {o.model.tags?.map((tag) => (
                          <Badge key={tag} variant="secondary" className="px-1 py-0 text-[10px]">
                            {MODEL_TAG_LABELS[tag] || tag}
                          </Badge>
                        ))}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* ComfyUI 工作流选择 */}
          {engineType === "comfyui" && (
            <div className="space-y-2">
              <Label>工作流映射</Label>
              <Select value={selectedWorkflowId} onValueChange={setSelectedWorkflowId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择工作流" />
                </SelectTrigger>
                <SelectContent>
                  {(workflows || []).filter((w: { enabled: boolean }) => w.enabled).map((w: { id: string; name: string; asset_type: string }) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name} ({w.asset_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* 动态参数面板 */}
          {capabilities && capabilities.param_specs && capabilities.param_specs.length > 0 && (
            <DynamicParamsPanel
              paramSpecs={capabilities.param_specs}
              params={params}
              onParamsChange={setParams}
              count={count}
              onCountChange={setCount}
              capabilities={capabilities}
            />
          )}

          {/* Prompt 编辑 */}
          <div className="space-y-2">
            <Label>Prompt</Label>
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={isBatch ? "批量生成时各目标使用各自的 prompt，此处为可选覆盖" : "输入生成提示词..."}
              rows={3}
            />
            {isBatch && (
            <p className="text-xs text-muted-foreground">
              留空则使用各目标自身的 prompt
            </p>
          )}

        </div>

        {/* 参考图提示（仅分镜目标，非视频） */}
          {isShotTarget && !isVideoTarget && (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">
                系统会自动收集关联的角色/场景/道具参考图，有则图生图，无则文生图
              </p>
              {capabilities?.reference_images_need_url && (
                <p className="text-xs text-amber-600">
                  当前模型要求参考图为公网 URL，系统将自动上传到图床
                </p>
              )}
            </div>
          )}

          {/* 视频参考图类型选择（仅视频目标） */}
          {isVideoTarget && (
            <div className="space-y-2 rounded-md border p-3">
              <Label className="text-sm font-medium">参考图类型</Label>
              {capabilities?.video_reference_hint && (
                <p className="text-xs text-amber-600">{capabilities.video_reference_hint}</p>
              )}
              <div className="flex flex-wrap gap-3">
                {([
                  { value: "first_frame", label: "首帧" },
                  { value: "last_frame", label: "尾帧" },
                  { value: "character", label: "人物" },
                  { value: "scene", label: "场景" },
                  { value: "prop", label: "道具" },
                ] as const).map((opt) => (
                  <label key={opt.value} className="flex items-center gap-1.5 text-sm cursor-pointer">
                    <Checkbox
                      checked={videoRefTypes.includes(opt.value)}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setVideoRefTypes((prev) => [...prev, opt.value]);
                        } else {
                          setVideoRefTypes((prev) => prev.filter((t) => t !== opt.value));
                        }
                      }}
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
              {capabilities?.max_reference_images && videoRefTypes.length > capabilities.max_reference_images && (
                <p className="text-xs text-destructive">
                  当前模型最多支持 {capabilities.max_reference_images} 张参考图，已选 {videoRefTypes.length} 种类型
                </p>
              )}
              {capabilities?.reference_images_need_url && (
                <p className="text-xs text-muted-foreground">
                  参考图将自动上传到图床获取公网 URL
                </p>
              )}
            </div>
          )}

          {/* 参考图（手动追加） */}
          {isShotTarget && referenceAssetIds.length > 0 && (
            <div className="space-y-2">
              <Label>手动参考图</Label>
              <div className="flex flex-wrap gap-2">
                {referenceAssetIds.map((assetId) => (
                  <div
                    key={assetId}
                    className="relative h-16 w-16 overflow-hidden rounded-md border"
                  >
                    <img
                      src={`/api/assets/${assetId}/file`}
                      alt="参考图"
                      className="h-full w-full object-cover"
                    />
                    <button
                      className="absolute right-0 top-0 rounded-bl bg-background/80 p-0.5 hover:bg-destructive hover:text-destructive-foreground"
                      onClick={() =>
                        setReferenceAssetIds((prev) => prev.filter((id) => id !== assetId))
                      }
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                手动追加的参考图，会与自动收集的参考图合并后提交
              </p>
            </div>
          )}

          {/* 批量摘要 */}
          {isBatch && <BatchSummary targets={targets} />}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            disabled={isSubmitting || (engineType === "api" && !selectedModelKey)}
            onClick={handleSubmit}
          >
            {isSubmitting ? "提交中..." : "提交生成"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
// 动态参数面板（根据 param_specs 渲染）
// ============================================================

const DynamicParamsPanel = memo(function DynamicParamsPanel({
  paramSpecs,
  params,
  onParamsChange,
  count,
  onCountChange,
  capabilities,
}: {
  paramSpecs: ParamSpec[];
  params: Record<string, string>;
  onParamsChange: (v: Record<string, string>) => void;
  count: number;
  onCountChange: (v: number) => void;
  capabilities: ProviderCapabilities;
}) {
  const updateParam = useCallback((key: string, value: string) => {
    onParamsChange({ ...params, [key]: value });
  }, [params, onParamsChange]);

  return (
    <div className="space-y-3 rounded-md border p-3">
      <Label className="text-xs font-semibold text-muted-foreground uppercase">参数配置</Label>

      {/* 动态参数（根据 param_specs 渲染） */}
      {paramSpecs.map((spec) => (
        <div key={spec.key} className="space-y-1">
          <div className="flex items-center justify-between">
            <Label className="text-sm">
              {spec.label}
              {spec.required && <span className="ml-1 text-destructive">*</span>}
            </Label>
            {spec.help_text && (
              <span className="text-xs text-muted-foreground">{spec.help_text}</span>
            )}
          </div>

          {spec.input_type === "select" && (
            <div className="space-y-1">
              <Select
                value={params[spec.key] || spec.default || ""}
                onValueChange={(v) => updateParam(spec.key, v)}
              >
                <SelectTrigger className="h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(spec.options || []).flatMap((opt) =>
                    // 兼容：如果选项中包含逗号（中文或英文），拆分为多个选项
                    opt.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
                  ).map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* 自定义输入（allow_custom=true 时） */}
              {spec.allow_custom && (
                <Input
                  value={params[spec.key] || ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    // 简单校验：允许数字、x、X
                    if (/^[0-9xX]*$/.test(val)) {
                      updateParam(spec.key, val);
                    }
                  }}
                  placeholder={spec.placeholder || "自定义..."}
                  className="h-8 mt-1"
                />
              )}
            </div>
          )}

          {spec.input_type === "text" && (
            <Input
              value={params[spec.key] || spec.default || ""}
              onChange={(e) => updateParam(spec.key, e.target.value)}
              placeholder={spec.placeholder}
              className="h-8"
            />
          )}

          {spec.input_type === "number" && (
            <Input
              type="number"
              value={parseInt(params[spec.key]) || spec.default || 0}
              onChange={(e) => updateParam(spec.key, e.target.value)}
              className="h-8"
            />
          )}

          {spec.input_type === "slider" && (
            <div className="flex items-center gap-2">
              <Input
                type="range"
                min={spec.min || 0}
                max={spec.max || 100}
                step={spec.step || 1}
                value={parseFloat(params[spec.key]) || spec.default || 0}
                onChange={(e) => updateParam(spec.key, e.target.value)}
                className="h-8 flex-1"
              />
              <span className="text-sm tabular-nums">
                {params[spec.key] || spec.default}
              </span>
            </div>
          )}
        </div>
      ))}

      {/* 生成数量 */}
      {capabilities.batch_support && (
        <div className="space-y-1">
          <Label className="text-sm">生成数量 (1-{capabilities.max_count})</Label>
          <Input
            type="number"
            min={1}
            max={capabilities.max_count}
            value={count}
            onChange={(e) => onCountChange(Math.min(Math.max(1, parseInt(e.target.value) || 1), capabilities.max_count))}
            className="h-8"
          />
        </div>
      )}

      {/* 额外字段（extra_fields） */}
      {(capabilities.extra_fields ?? [])
        .filter((f: ExtraField) => f.type !== "workflow_select")
        .map((field: ExtraField) => (
          <div key={field.key} className="space-y-1">
            <Label className="text-sm">{field.label}</Label>
            {field.type === "select" && field.options ? (
              <Select
                value={String(params[field.key] ?? field.default ?? "")}
                onValueChange={(v) => updateParam(field.key, v)}
              >
                <SelectTrigger className="h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(field.options || []).map((opt: string) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input
                value={String(params[field.key] ?? field.default ?? "")}
                onChange={(e) => updateParam(field.key, e.target.value)}
                className="h-8"
              />
            )}
          </div>
        ))}
    </div>
  );
});
