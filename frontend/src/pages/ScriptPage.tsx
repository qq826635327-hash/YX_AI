/** 剧本页：编辑、保存、AI 解析。 */

import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Save, Sparkles, FileText } from "lucide-react";
import { PageContainer, LoadingState, EmptyState } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useScript, useSaveScript, useParseScript } from "@/hooks/useApi";
import { useScriptWsSubscription } from "@/hooks/useWs";
import { formatTime } from "@/lib/utils";

export function ScriptPage() {
  const { projectId } = useParams();
  const { data: script, isLoading } = useScript(projectId!);
  const saveMutation = useSaveScript(projectId!);
  const parseMutation = useParseScript(projectId!);

  // 订阅剧本解析 WebSocket 推送
  useScriptWsSubscription(projectId);

  const [text, setText] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (script && !dirty) {
      // scriptApi.get 返回 ScriptDocument 或简化类型，统一处理
      const rawText = typeof script === "object" && "raw_text" in script
        ? (script as { raw_text: string }).raw_text
        : "";
      setText(rawText || "");
      setDirty(false);
    }
  }, [script, dirty]);

  const handleSave = () => {
    saveMutation.mutate(text);
    setDirty(false);
  };

  const handleParse = async () => {
    try {
      if (dirty) {
        if (!confirm("剧本有未保存的修改，是否先保存再解析？")) return;
        await saveMutation.mutateAsync(text);
        setDirty(false);
      }
      parseMutation.mutate(true);
    } catch {
      // mutateAsync 失败已由 React Query onError 回调处理（显示 toast）
    }
  };

  if (isLoading) return <LoadingState />;

  const scriptData = script as { raw_text?: string; version?: number; parse_status?: string; parsed_at?: string; parse_error?: string; parsed_result?: unknown };

  const parseStatusMap: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "success" | "warning" }> = {
    none: { label: "未解析", variant: "secondary" },
    parsing: { label: "解析中", variant: "warning" },
    parsed: { label: "已解析", variant: "success" },
    failed: { label: "解析失败", variant: "destructive" },
  };
  const statusInfo = parseStatusMap[scriptData?.parse_status || "none"];

  return (
    <PageContainer
      title="剧本"
      description="输入完整剧本，AI 自动解析角色、场景、道具与剧集结构"
      actions={
        <>
          <Button variant="outline" onClick={handleSave} disabled={!dirty || saveMutation.isPending}>
            <Save className="h-4 w-4" />
            保存
          </Button>
          <Button onClick={handleParse} disabled={parseMutation.isPending || !text.trim()}>
            <Sparkles className="h-4 w-4" />
            {parseMutation.isPending ? "解析中..." : "AI 解析"}
          </Button>
        </>
      }
    >
      <Tabs defaultValue="edit">
        <TabsList>
          <TabsTrigger value="edit">编辑</TabsTrigger>
          <TabsTrigger value="info">解析信息</TabsTrigger>
        </TabsList>

        <TabsContent value="edit">
          <Card>
            <CardContent className="p-4">
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
                </div>
                {scriptData?.parsed_at && (
                  <p className="text-sm text-muted-foreground">解析时间：{formatTime(scriptData.parsed_at)}</p>
                )}
                {scriptData?.parse_error && (
                  <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                    {scriptData.parse_error}
                  </div>
                )}
              </CardContent>
            </Card>

            {scriptData?.parse_status === "parsing" && (
              <Card>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground animate-pulse">AI 正在解析剧本，请稍候...</p>
                </CardContent>
              </Card>
            )}

            {scriptData?.parse_status === "none" && !text.trim() && (
              <EmptyState icon={FileText} title="还没有剧本" description="在「编辑」标签页输入剧本后保存" />
            )}
          </div>
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
