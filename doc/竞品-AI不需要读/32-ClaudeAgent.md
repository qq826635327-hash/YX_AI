# 32 Claude Agent

## 1. 入口

`/settings/providers` → "Claude Agent" 卡片；或在生成对话框里"使用 Claude Agent 改写"。

## 2. 进程

`out/main/claudeAgent.cjs` 包装 `@anthropic-ai/claude-agent-sdk`：

- 必须 `unpacked`（`resources/app.asar.unpacked/node_modules/@anthropic-ai/claude-agent-sdk`）
- 启动子进程，与 SDK 进程通信

## 3. 配置

- API Key（明文传入，存 userData/.enc 加密）
- baseUrl（可选）
- model
- autoConfirm（权限请求是否自动批准）
- skillIds（启用的 Skill 列表）

## 4. Skill 系统

### 4.1 内置 Skill

应用随包携带若干 Skill（`out/main/chunks/builtin-skills-BNLDQWD2.cjs` 13 KB）。`claudeAgent:builtin-skill-bodies` 返回所有内置 Skill 的 markdown 正文。

### 4.2 自定义 Skill

存放于 `userData/claude-skills/<id>/SKILL.md`，CRUD：

- `listCustomSkills` / `saveCustomSkill(create: bool)` / `deleteCustomSkill`
- `getCustomSkillsDir` / `revealCustomSkills`（系统资源管理器打开）

### 4.3 Skill 内容

Markdown 文件 + YAML frontmatter：

```markdown
---
name: 分镜师
description: 负责把剧本改写成结构化分镜
---

# 角色
你是一个资深的漫剧分镜师…
# 工作流
…
```

## 5. 任务管理

```ts
window.electronAPI.claudeAgent.start({
  prompt, workdir?, autoConfirm?, skillIds?
})
// → { turnId, messages[] }
```

事件：

```
claudeAgent:event {
  type: "message_start" | "content_block_delta" | "content_block_stop"
      | "tool_use" | "tool_result" | "permission_request"
      | "result" | "error" | "end",
  ...payload
}
```

- 流式文本：把 `content_block_delta` 累积到 UI
- 工具调用：渲染端根据 `name` 字段做高亮 + 结果展示
- 权限请求：`permission_request` 弹窗 → 用户点"批准/拒绝" → `respondPermission(permissionId, decision)`

## 6. 会话历史

- `listSessions(dir)` 扫描 `<workdir>/.claude/sessions/*.json`
- `getSessionMessages(sessionId, dir)` 取一条会话的所有消息
- `deleteSession`
- `rewindSession(sessionId, dir, userPromptIndex)` → 回退到第 N 轮

## 7. 测通

`testConnection({ apiKey, baseUrl, model })`：用最小 prompt 测一次。

## 8. 复刻提示

- Claude Agent SDK 是 Anthropic 官方 Node 包，复刻时**必须用同一个 SDK**，否则行为差异大
- Skill 系统是产品亮点（用户可自建"分镜师"、"角色设计师"等），复刻时务必保留

---

**下一步**：`33-火山方舟集成.md`。
