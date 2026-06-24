# 21 设置 · ComfyUI

## 1. 入口

`/settings/comfyui`

## 2. ComfyUI 服务器

- 服务器 URL（默认 `http://127.0.0.1:8188`）
- 多个服务器预设（用户可添加）
- "测通"：调 `/system_stats`
- "在浏览器中打开"：调 `shell:open-external`

## 3. ComfyUI 工作流

### 3.1 三种来源

- **内置**：随应用打包（`src/lib/comfy/builtin-workflows/registry/*.wlmj-workflow.zip`），只读
- **导入**：用户从 ComfyUI 导出的 API 格式 JSON 或 zip
- **标记为内置**：把工作流 zip 复制到内置目录，仅 dev 模式可用（`fs:write-builtin-template-zip`）

### 3.2 内置 zip 格式

```
<slug>.wlmj-workflow.zip
├── manifest.json     # { name, version, kind, params, defaults }
└── media/            # 静态资源（LoRA / 嵌入等）
```

slug 校验：仅 Unicode / 数字 / `.` / `+`，≤80 字符，路径分隔符过滤。

### 3.3 列表视图

```
工作流
├── 内置
│   ├── [基础文生图] v1.0
│   ├── [图生图] v1.0
│   ├── [首帧+尾帧] v1.0
│   └── [SDXL 1.0] v1.0
└── 导入
    ├── my-style-flow.zip  [默认] [编辑] [删除]
    └── 二次元-lora.zip    [默认] [编辑] [删除]
```

### 3.4 调用

生成时把"工作流 zip"解包为 API JSON，按占位符填入用户参数后 POST 到 ComfyUI 的 `/prompt`：

```ts
async function runComfy(workflow, inputs) {
  const api = expand(workflow.manifest, inputs);
  const clientId = uuid();
  const { prompt_id } = await fetchJson(`${serverUrl}/prompt`, { client_id: clientId, prompt: api });
  // WebSocket 监听 clientId / prompt_id
  // 收集 outputs 节点
  return { images: [...] };
}
```

### 3.5 关键 IPC

- `fs:write-builtin-template-zip`（仅 dev）
- `fs:read-file` / `fs:read-file-binary`（读 zip / 资源）
- `outbound:request`（统一走出站，但 provider = comfy）

## 4. 复刻提示

ComfyUI 是出站 provider 的一种，复刻时建议：

1. 把 ComfyUI 适配器写到 `services/comfy.adapter.ts`
2. 用 `outbound:request` 复用出站栈
3. 任务进度走 `outbound:event` 流式 chunk

---

**下一步**：`22-设置-插件与扩展.md`。
