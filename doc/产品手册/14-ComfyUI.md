# 14. ComfyUI

**路由**：`/settings/comfyui-servers` + `/settings/comfyui-workflows`
**对应文件**：`pages/settings/SettingsComfyuiServersPage.tsx` + `SettingsComfyuiWorkflowsPage.tsx`

> ⚠️ **[Phase 1 占位 · 服务器配置通过 config.yaml 管理]** 工作流 CRUD UI 已完成，服务器管理 UI 为占位。

---

## 1. 功能描述

管理 ComfyUI 服务器连接和工作流模板。ComfyUI 是基于节点的异步工作流引擎，通过 WebSocket 推送执行进度。

## 2. ComfyUI 服务器

### 2.1 服务器列表

| 列 | 内容 |
|----|------|
| 名称 | 唯一标识 |
| 地址 | HTTP 地址 |
| WebSocket | WS 地址 |
| 状态 | 在线/离线/未知 |
| 队列长度 | 当前任务数 |

### 2.2 新建/编辑服务器对话框

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 名称 | text | ✅ | 唯一 |
| HTTP 地址 | text | ✅ | 如 `http://127.0.0.1:8188` |
| WebSocket 地址 | text | ✅ | 如 `ws://127.0.0.1:8188/ws` |
| 用户名 | text | ❌ | 可选认证 |
| 密码 | password | ❌ | 可选认证 |
| 描述 | textarea | ❌ | - |
| 启用 | bool | ✅ | 默认 true |

### 2.3 服务器数据模型（计划）

```python
class ComfyUIServer:
    id: str
    name: str
    base_url: str
    ws_url: str
    username: str | None
    encrypted_password: str | None
    description: str
    enabled: bool
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
```

### 2.4 服务器 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config/comfyui` | 获取 ComfyUI 配置 |

> 注：前端服务器管理页面已预留路由，待后端实现独立 CRUD 后完善。

## 3. ComfyUI 工作流

### 3.1 工作流列表

| 列 | 内容 |
|----|------|
| 名称 | 唯一标识 |
| 关联服务器 | 来自 ComfyUI 服务器 |
| 类型 | 图片生成 / 视频生成 |
| 状态 | 启用/禁用 |
| 操作 | 编辑/复制/删除 |

### 3.2 新建/编辑工作流对话框

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 名称 | text | ✅ | 唯一 |
| 关联服务器 | select | ✅ | 从 ComfyUI 服务器列表选 |
| 工作流 JSON | code/textarea | ✅ | 粘贴或上传 .json 文件 |
| 类型 | select | ✅ | 图片生成 / 视频生成 |
| 输入参数映射 | mapping | ❌ | 哪些是 prompt、参考图、宽度/高度等 |
| 启用 | bool | ✅ | 默认 true |

### 3.3 工作流数据模型（WorkflowMapping）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | UUID |
| name | str | 唯一名称 |
| server_id | str | 关联服务器 |
| workflow_json | dict | 工作流 JSON |
| asset_type | str | image / video |
| param_mapping | dict | 输入参数映射 |
| extra_params | dict | 额外参数 |
| enabled | bool | 启用/禁用 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 3.4 参数映射示例

```json
{
  "prompt": "node_1.inputs.text",
  "negative_prompt": "node_2.inputs.text",
  "width": "node_3.inputs.width",
  "height": "node_3.inputs.height",
  "seed": "node_4.inputs.seed",
  "reference_image": "node_5.inputs.image"
}
```

### 3.5 工作流 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config/workflows?asset_type=&enabled=` | 列表 |
| POST | `/api/config/workflows` | 新建 |
| GET | `/api/config/workflows/{id}` | 详情 |
| PATCH | `/api/config/workflows/{id}` | 更新 |
| DELETE | `/api/config/workflows/{id}` | 删除 |

### 3.6 工作流编辑器

**Phase 1**：JSON 文本编辑（大文本框 + JSON 格式校验 + 错误提示）

**Phase 4 规划**：可视化节点编辑器（拖拽节点 + 可视化连线 + 参数面板 + 实时预览）

### 3.7 工作流校验

保存前自动校验：JSON 格式合法 / 节点引用存在 / 必需参数非空 / 服务器可达

## 4. 与 API 供应商的区别

| 维度 | ComfyUI 服务器 | API 供应商 |
|------|---------------|-----------|
| 部署 | 本地为主 | 远程云端 |
| 协议 | WebSocket + HTTP | HTTP REST |
| 工作流 | JSON 配置 | 平台固定 |
| 异步 | WS 推送进度 | 轮询或回调 |
| 鉴权 | 可选 Basic | API Key |

## 5. 与 Provider 体系的关系

- ComfyUI 工作流也是一种 provider
- 在 [生成对话框](./19-生成对话框.md) 中选择 provider 时，ComfyUI 类型的工作流会出现在列表中
- 与 API 供应商统一在 `Provider` 抽象下管理

## 6. Phase 状态

- **服务器管理**：Phase 1 占位页面，配置通过 `config.yaml` 管理
- **工作流管理**：Phase 1 已有完整 CRUD UI，执行层在 Phase 3 实现

## 7. 已知限制

- 服务器管理 UI 为占位
- 服务器连接测试为占位实现
- WebSocket 重连机制待实现
- 工作流 JSON 编辑器无语法高亮
- 无工作流预览图和版本管理

---

## AI 开发检查清单

> AI 修改本模块时，必须执行以下检查。

- [ ] 已阅读 `doc/开发手册/08-常见Bug与注意事项.md`
- [ ] 后端改动：Python 语法检查通过 + pytest 全部通过
- [ ] 前端改动：`npx tsc --noEmit` 无错误
- [ ] `doc/开发手册/CHANGELOG.md` 已更新
- [ ] 本文件已更新（如产品行为有变化）

---

## 8. 相关模块

- [API 供应商与模型配置](./10-API供应商与模型配置.md)
- [插件扩展](./11-插件扩展.md)
- [生成对话框](./19-生成对话框.md)
