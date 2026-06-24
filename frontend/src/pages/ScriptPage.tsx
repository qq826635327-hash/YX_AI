/** 剧本页：编辑、保存、AI 解析（含实时进度 + LLM 流式输出）。 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import { Save, Sparkles, FileText, Palette, Check, Circle, Loader2, ChevronDown, XOctagon } from "lucide-react";
import { PageContainer, LoadingState, EmptyState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useScript, useSaveScript, useParseScript, useStylePresets } from "@/hooks/useApi";
import { scriptApi } from "@/api/script";
import { useScriptWsSubscription, PARSE_STEPS_DEFAULT, rebuildSteps } from "@/hooks/useWs";
import type { ScriptWsCallbacks } from "@/hooks/useWs";
import { useProject } from "@/hooks/useProjects";
import { projectsApi } from "@/api/projects";
import { useQueryClient } from "@tanstack/react-query";
import { formatTime } from "@/lib/utils";
import { toast } from "@/stores/ui";
import { useConfirm } from "@/components/ConfirmDialog";
import type { ParseStep } from "@/types";

/** 支持流式输出的阶段 */
const STREAM_STAGES = new Set(["character", "episode", "shot"]);

/** 解析目标选项 */
const PARSE_TARGETS = [
  { key: "characters", label: "角色" },
  { key: "scenes", label: "场景" },
  { key: "props", label: "道具" },
  { key: "episodes", label: "剧集结构" },
] as const;

type ParseTargetKey = (typeof PARSE_TARGETS)[number]["key"];

/** 步骤进度清单组件 */
function ParseStepList({ steps }: { steps: ParseStep[] }) {
  return (
    <div className="space-y-2">
      {steps.map((step) => (
        <div key={step.stage} className="flex items-center gap-2 text-sm">
          {step.status === "done" ? (
            <Check className="h-4 w-4 text-green-500 shrink-0" />
          ) : step.status === "active" ? (
            <Loader2 className="h-4 w-4 text-amber-500 shrink-0 animate-spin" />
          ) : (
            <Circle className="h-4 w-4 text-muted-foreground/40 shrink-0" />
          )}
          <span className={step.status === "pending" ? "text-muted-foreground/60" : ""}>
            {step.label}
          </span>
          {step.summary && step.status === "done" && (
            <span className="text-muted-foreground text-xs ml-auto">{step.summary}</span>
          )}
          {step.status === "active" && (
            <span className="text-amber-600 text-xs ml-auto animate-pulse">进行中...</span>
          )}
        </div>
      ))}
    </div>
  );
}

/** LLM 流式输出展示区 */
function StreamOutput({ text, isActive }: { text: string; isActive: boolean }) {
  const scrollRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [text]);

  if (!text && !isActive) return null;

  return (
    <pre
      ref={scrollRef}
      className="bg-muted/50 rounded-md p-3 text-sm font-mono leading-relaxed whitespace-pre-wrap break-words max-h-[50vh] overflow-y-auto"
    >
      {text}
      {isActive && <span className="inline-block w-2 h-4 bg-foreground/70 animate-pulse ml-0.5 align-text-bottom" />}
    </pre>
  );
}

export function ScriptPage() {
  const { projectId } = useParams();
  const { data: script, isLoading } = useScript(projectId!);
  const saveMutation = useSaveScript(projectId!);
  const parseMutation = useParseScript(projectId!);
  const { data: project } = useProject(projectId!);
  const { data: stylePresets } = useStylePresets();
  const qc = useQueryClient();
  const confirm = useConfirm();

  // 解析进度状态
  const [parseSteps, setParseSteps] = useState<ParseStep[]>([]);
  const [streamText, setStreamText] = useState("");
  const [streamStage, setStreamStage] = useState("");
  const [isParsing, setIsParsing] = useState(false);

  // 用 useRef 稳定 callbacks，避免 useEffect 重复订阅
  const callbacksRef = useRef<ScriptWsCallbacks>({});

  callbacksRef.current = {
    onStepsChange: (steps: ParseStep[]) => {
      setParseSteps(steps);
      // 如果所有步骤都不是 active，说明解析结束
      const hasActive = steps.some(s => s.status === "active");
      if (!hasActive && isParsing) {
        setIsParsing(false);
        setStreamText("");
      }
    },
    onStreamToken: (stage: string, tokens: string) => {
      // 只展示支持流式的阶段的输出
      if (STREAM_STAGES.has(stage)) {
        setStreamText(prev => prev + tokens);
      }
    },
    onStreamStageChange: (stage: string) => {
      // 切换到新的流式阶段时，清空旧内容
      if (STREAM_STAGES.has(stage) && stage !== streamStage) {
        setStreamText("");
        setStreamStage(stage);
      }
    },
  };

  // 订阅剧本解析 WebSocket 推送
  useScriptWsSubscription(projectId, callbacksRef.current);

  const [text, setText] = useState("");
  const [dirty, setDirty] = useState(false);
  const [stylePreset, setStylePreset] = useState("");
  const [preservePrompts, setPreservePrompts] = useState(false);
  const [parseTargets, setParseTargets] = useState<Set<ParseTargetKey>>(
    new Set(PARSE_TARGETS.map(t => t.key))
  );
  const [showTargetMenu, setShowTargetMenu] = useState(false);

  useEffect(() => {
    if (script && !dirty) {
      const rawText = typeof script === "object" && "raw_text" in script
        ? (script as { raw_text: string }).raw_text
        : "";
      setText(rawText || "");
      setDirty(false);
    }
  }, [script, dirty]);

  useEffect(() => {
    if (project) {
      setStylePreset((project as { style_preset?: string }).style_preset || "");
    }
  }, [project]);

  // 同步 parse_status 到 isParsing，并在重挂载时用 current_stage/completed_stages 恢复步骤进度
  useEffect(() => {
    const scriptData = script as { parse_status?: string; current_stage?: string; completed_stages?: { stage: string; summary: string }[] } | undefined;
    if (scriptData?.parse_status === "parsing") {
      setIsParsing(true);
      // 用后端持久化的 current_stage 和 completed_stages 重建步骤进度
      if (scriptData.current_stage || scriptData.completed_stages?.length) {
        const steps = rebuildSteps(scriptData.current_stage || "", scriptData.completed_stages);
        setParseSteps(steps);
      } else if (parseSteps.length === 0) {
        // 兜底：没有持久化数据时用默认步骤
        setParseSteps(PARSE_STEPS_DEFAULT.map(s => ({
          ...s,
          status: s.stage === "character" ? ("active" as const) : ("pending" as const),
        })));
      }
    } else if (scriptData?.parse_status === "parsed" || scriptData?.parse_status === "failed" || scriptData?.parse_status === "none" || scriptData?.parse_status === "cancelled") {
      setIsParsing(false);
    }
  }, [script]);

  const handleStyleChange = async (value: string) => {
    setStylePreset(value);
    try {
      await projectsApi.update(projectId!, { style_preset: value });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
      toast.success("画风已更新");
    } catch {
      toast.error("画风更新失败");
    }
  };

  const handleSave = () => {
    saveMutation.mutate(text);
    setDirty(false);
  };

  const handleCancelParse = useCallback(async () => {
    if (!(await confirm({ title: "确定取消解析？", description: "数据将恢复到解析前状态。", variant: "destructive" }))) return;
    try {
      await scriptApi.cancelParse(projectId!);
      toast.info("已发送取消信号");
    } catch (e: any) {
      toast.error(`取消失败：${e.message ?? "未知错误"}`);
    }
  }, [projectId]);

  const handleParse = useCallback(async () => {
    try {
      if (dirty) {
        if (!(await confirm({ title: "剧本有未保存的修改", description: "是否先保存再解析？" }))) return;
        await saveMutation.mutateAsync(text);
        setDirty(false);
      }
      // 重置进度状态
      setParseSteps([]);
      setStreamText("");
      setStreamStage("");
      setIsParsing(true);
      parseMutation.mutate({
        force: true,
        preservePrompts,
        parseTargets: Array.from(parseTargets),
      });
    } catch {
      // mutateAsync 失败已由 React Query onError 回调处理
    }
  }, [dirty, saveMutation, text, parseMutation, preservePrompts, parseTargets]);

  if (isLoading) return <LoadingState />;

  const scriptData = script as { raw_text?: string; version?: number; parse_status?: string; parsed_at?: string; parse_error?: string; parsed_result?: unknown };

  const parseStatusMap: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "success" | "warning" }> = {
    none: { label: "未解析", variant: "secondary" },
    parsing: { label: "解析中", variant: "warning" },
    parsed: { label: "已解析", variant: "success" },
    failed: { label: "解析失败", variant: "destructive" },
    cancelled: { label: "已取消", variant: "secondary" },
  };
  const statusInfo = parseStatusMap[scriptData?.parse_status || "none"];

  return (
    <PageContainer
      title="剧本"
      description="输入完整剧本，AI 自动解析角色、场景、道具与剧集结构"
      actions={
        <>
          {/* 解析目标勾选 */}
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowTargetMenu(v => !v)}
              disabled={isParsing}
            >
              解析范围
              <ChevronDown className="ml-1 h-3 w-3" />
            </Button>
            {showTargetMenu && (
              <div className="absolute right-0 top-full z-20 mt-1 w-36 rounded-md border bg-card p-2 shadow-md">
                {PARSE_TARGETS.map(t => (
                  <label key={t.key} className="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent cursor-pointer">
                    <Checkbox
                      checked={parseTargets.has(t.key)}
                      onCheckedChange={(checked) => {
                        setParseTargets(prev => {
                          const next = new Set(prev);
                          if (checked) next.add(t.key);
                          else next.delete(t.key);
                          return next;
                        });
                      }}
                    />
                    {t.label}
                  </label>
                ))}
              </div>
            )}
          </div>
          <Button variant="outline" onClick={handleSave} disabled={!dirty || saveMutation.isPending}>
            <Save className="h-4 w-4" />
            保存
          </Button>
          <Button onClick={handleParse} disabled={parseMutation.isPending || !text.trim() || parseTargets.size === 0}>
            <Sparkles className="h-4 w-4" />
            {isParsing ? "解析中..." : "AI 解析"}
          </Button>
        </>
      }
    >
      <Tabs defaultValue={isParsing ? "info" : "edit"}>
        <TabsList>
          <TabsTrigger value="edit">编辑</TabsTrigger>
          <TabsTrigger value="info">
            解析信息
            {isParsing && <Loader2 className="h-3 w-3 ml-1 animate-spin" />}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="edit">
          <Card>
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center gap-3">
                <Palette className="h-4 w-4 text-muted-foreground shrink-0" />
                <Label className="shrink-0 text-sm">画风预置</Label>
                <div className="flex flex-wrap gap-1.5">
                  <Button
                    variant={!stylePreset || stylePreset === "default" ? "default" : "outline"}
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => handleStyleChange("")}
                  >
                    不指定
                  </Button>
                  {(stylePresets || [])
                    .slice()
                    .sort((a, b) => a.sort_order - b.sort_order)
                    .map((s) => (
                      <Button
                        key={s.id}
                        variant={stylePreset === s.title ? "default" : "outline"}
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => handleStyleChange(s.title)}
                      >
                        {s.title}
                      </Button>
                    ))}
                </div>
              </div>
              <Textarea
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  setDirty(true);
                }}
                placeholder="在此粘贴或输入完整剧本...&#10;&#10;支持格式：&#10;第1集&#10;分镜1：...&#10;分镜2：..."
                className="min-h-[60vh] font-mono text-sm leading-relaxed"
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="info">
          <div className="space-y-4">
            {/* 解析状态概览 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  解析状态
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">状态：</span>
                  <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                  {scriptData?.version ? (
                    <Badge variant="outline">v{scriptData.version}</Badge>
                  ) : null}
                  {isParsing && (
                    <Button variant="destructive" size="sm" className="ml-auto" onClick={handleCancelParse}>
                      <XOctagon className="h-3.5 w-3.5" />
                      取消解析
                    </Button>
                  )}
                </div>
                {scriptData?.parsed_at && (
                  <p className="text-sm text-muted-foreground">解析时间：{formatTime(scriptData.parsed_at)}</p>
                )}
                {scriptData?.parse_error && (
                  <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                    {scriptData.parse_error}
                  </div>
                )}
                {/* 重新解析选项 */}
                {(scriptData?.parse_status === "parsed" || scriptData?.parse_status === "failed") && !isParsing && (
                  <div className="flex items-center gap-2 pt-1">
                    <Checkbox
                      id="preserve-prompts"
                      checked={preservePrompts}
                      onCheckedChange={(checked) => setPreservePrompts(checked === true)}
                    />
                    <Label htmlFor="preserve-prompts" className="text-sm cursor-pointer">
                      保留已有提示词
                    </Label>
                    <span className="text-xs text-muted-foreground">
                      （勾选后重新解析时不会覆盖已编辑的提示词）
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 解析中：步骤进度 + 流式输出 */}
            {isParsing && (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">解析进度</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {parseSteps.length > 0 ? (
                      <ParseStepList steps={parseSteps} />
                    ) : (
                      <p className="text-sm text-muted-foreground animate-pulse">正在启动解析...</p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      AI 实时输出
                      {streamStage && STREAM_STAGES.has(streamStage) && (
                        <Badge variant="outline" className="text-xs">
                          {streamStage === "character" ? "提取角色/场景/道具" : streamStage === "episode" ? "章节划分" : streamStage === "shot" ? "分镜拆分" : streamStage}
                        </Badge>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <StreamOutput
                      text={streamText}
                      isActive={isParsing && STREAM_STAGES.has(streamStage)}
                    />
                    {!streamText && !STREAM_STAGES.has(streamStage) && (
                      <p className="text-sm text-muted-foreground">
                        当前阶段不产生流式输出，完成后自动进入下一阶段
                      </p>
                    )}
                  </CardContent>
                </Card>
              </>
            )}

            {scriptData?.parse_status === "none" && !text.trim() && !isParsing && (
              <EmptyState icon={FileText} title="还没有剧本" description="在「编辑」标签页输入剧本后保存" />
            )}
          </div>
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
