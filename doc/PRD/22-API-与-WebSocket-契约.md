# PRD-22 · API 与 WebSocket 契约

> **版本**：v1.0 · **Owner**：架构负责人 · **关联**：`doc/开发手册/11-核心数据流.md`

## 1. 通用契约

### 1.1 基础 URL

| 环境 | URL |
|---|---|
| 开发（前端） | `http://127.0.0.1:5173/api`（Vite 代理到 8000） |
| 开发（后端） | `http://127.0.0.1:8000/api` |
| 生产 | `http://<host>:8000/api` |

### 1.2 统一响应格式

**成功响应（200 / 201）**：
```json
{
  "success": true,
  "data": { ... }           // 单个对象或数组
}
```

**分页响应**：
```json
{
  "success": true,
  "data": {
    "items": [ ... ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

**错误响应（4xx / 5xx）**：
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "name is required",
    "details": [ ... ]       // 可选
  }
}
```

### 1.3 HTTP 状态码规范

| 码 | 含义 | 使用场景 |
|---|---|---|
| 200 | 成功 | GET / PATCH / DELETE |
| 201 | 创建成功 | POST 创建资源 |
| 204 | 无内容 | 部分 DELETE |
| 400 | 客户端错误 | 参数校验失败 |
| 401 | 未认证 | BasicAuth 失败 |
| 404 | 资源不存在 | ID 不存在 |
| 405 | 方法不允许 | 路由顺序错误（固定路径在动态路径前） |
| 409 | 冲突 | 名称重复 |
| 422 | 不可处理实体 | Pydantic 校验失败 |
| 500 | 服务器错误 | 未捕获异常 |
| 501 | 未实现 | Provider 暂未注册 |

### 1.4 通用查询参数

| 参数 | 类型 | 说明 |
|---|---|---|
| page | int | 页码（默认 1） |
| page_size | int | 每页条数（默认 20，最大 100） |
| keyword | string | 关键词搜索（模糊匹配 name / description） |
| order_by | string | 排序字段（默认 created_at） |
| order_dir | string | asc / desc（默认 desc） |

## 2. REST 端点清单

### § 1 Projects

| Method | Path | 说明 | 请求体 / 参数 | 响应 |
|---|---|---|---|---|
| GET | `/api/projects` | 列表 | `status`, `keyword`, `page`, `page_size` | 分页列表 |
| POST | `/api/projects` | 创建 | `{name, description?, style_preset?}` | 单对象 |
| GET | `/api/projects/{id}` | 详情 | — | 单对象 |
| PATCH | `/api/projects/{id}` | 更新 | 部分字段 | 单对象 |
| DELETE | `/api/projects/{id}` | 删除 | `delete_files: bool` | 204 |

### § 2 Script

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/projects/{id}/script` | 获取剧本文档 |
| PUT | `/api/projects/{id}/script` | 更新剧本（version += 1） |
| POST | `/api/projects/{id}/script/parse` | 触发 AI 解析（异步） |
| POST | `/api/projects/{id}/script/cancel-parse` | 取消正在进行的解析 |

### § 3 Characters / Scenes / Props

每类实体共用 5 个端点：
```
GET    /api/projects/{pid}/{type}           # list（type ∈ characters/scenes/props）
POST   /api/projects/{pid}/{type}           # create
GET    /api/projects/{pid}/{type}/{id}      # get
PATCH  /api/projects/{pid}/{type}/{id}      # update
DELETE /api/projects/{pid}/{type}/{id}      # delete
```

### § 4 Episodes

| Method | Path | 说明 |
|---|---|---|
| GET / POST / GET / PATCH / DELETE | `/api/projects/{pid}/episodes[/{id}]` | 标准 CRUD |

### § 5 Shots

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/episodes/{eid}/shots` | 列表（按 shot_no 排序） |
| POST | `/api/episodes/{eid}/shots` | 创建 |
| POST | `/api/episodes/{eid}/shots/reorder` | 批量排序 `{shot_ids: [uuid...]}` |
| GET | `/api/shots/{id}` | 详情 |
| PATCH | `/api/shots/{id}` | 更新 |
| DELETE | `/api/shots/{id}` | 删除 |

### § 6 Shot References

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/shots/{id}/references` | 获取所有引用 |
| POST | `/api/shots/{id}/characters` | 添加角色引用 |
| DELETE | `/api/shots/{id}/characters/{cid}` | 删除角色引用 |
| POST | `/api/shots/{id}/scenes` | 添加场景引用 |
| DELETE | `/api/shots/{id}/scenes/{sid}` | 删除场景引用 |
| POST | `/api/shots/{id}/props` | 添加道具引用 |
| DELETE | `/api/shots/{id}/props/{pid}` | 删除道具引用 |

### § 7 Generate

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/generate` | 提交单任务（支持 `force` 字段强制跳过 Prompt 缓存） |
| POST | `/api/generate/batch` | 批量提交 |
| POST | `/api/generate/{task_id}/retry` | 重试失败任务（自动设置 `force=True`，清除 `cache_key`，重置 `auto_retry_count`） |
| POST | `/api/generate/{task_id}/cancel` | 取消任务 |

**StandardGenerateRequest**：见 PRD-13 § 7。

### § 8 Tasks

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/tasks` | 列表（过滤：project_id, status, target_type, target_id） |
| POST | `/api/tasks/clear` | 批量清理完成 / 取消任务 |
| GET | `/api/tasks/queue/status` | 队列可观测性（pending/running/max_concurrent 等） |
| GET | `/api/tasks/{id}` | 详情 |
| GET | `/api/tasks/{id}/logs` | 任务结构化日志 |

### § 9 Assets

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/assets` | 列表 |
| POST | `/api/assets/sync` | 双向同步 |
| POST | `/api/assets/sync-dirs` | 创建缺失目录 |
| POST | `/api/assets/open-dir` | 打开资产目录（资源管理器） |
| POST | `/api/assets/projects/{pid}/upload` | 上传新资产 |
| GET | `/api/assets/{id}` | 详情 |
| GET | `/api/assets/{id}/file` | 下载文件（流式） |
| POST | `/api/assets/{id}/upload` | 替换文件 |
| DELETE | `/api/assets/{id}` | 删除（可选删磁盘） |

### § 10 Config — Providers

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/config/providers` | 列表（脱敏，无 Key） |
| POST | `/api/config/providers` | 创建 |
| GET | `/api/config/providers/comfyui/capabilities` | ComfyUI 能力 |
| GET | `/api/config/providers/{id}` | 详情 |
| GET | `/api/config/providers/{id}/capabilities` | 单个 Provider 支持的模型/参数 |
| PATCH | `/api/config/providers/{id}` | 更新 |
| DELETE | `/api/config/providers/{id}` | 删除 |
| POST | `/api/config/providers/{id}/test` | 测试连接 |

### § 11 Config — Workflows

| Method | Path | 说明 |
|---|---|---|
| GET / POST / GET / PATCH / DELETE | `/api/config/workflows[/{id}]` | 标准 CRUD |

### § 12 Config — System / LLM / Tasks / Backup

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/config/system` | 系统配置摘要（含 default_models、tasks 运行时配置） |
| GET | `/api/config/comfyui` | ComfyUI 配置 |
| PATCH | `/api/config/default-models` | 更新默认模型（image / text / video） |
| PATCH | `/api/config/tasks` | 更新任务运行时配置（max_concurrent / rate_limit_retry / rate_limit_wait / smart_fallback / auto_retry_on_download_fail / auto_retry_max_attempts / task_max_age_minutes） |
| POST | `/api/config/backup` | 手动触发数据库备份 + WAL checkpoint |

### § 13 Prompt Templates

| Method | Path | 说明 |
|---|---|---|
| GET / POST / GET / PUT / DELETE | `/api/prompt-templates[/{id}]` | 标准 CRUD |

### § 14 Logs

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/logs` | 历史日志（level / keyword / 分页） |
| GET | `/api/logs/info` | 日志文件元信息（路径、大小、行数） |
| DELETE | `/api/logs/clear` | 清空后端日志文件 |
| GET | `/api/logs/tasks/{task_id}` | 任务结构化日志 |

### § 14.5 Perf（性能监控）

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/perf/sessions` | 创建性能会话（前端上报） |
| GET | `/api/perf/sessions` | 性能会话列表 |
| GET | `/api/perf/alerts` | 告警列表 |
| POST | `/api/perf/alerts/{alert_id}/acknowledge` | 确认告警 |
| DELETE | `/api/perf/clear` | 清空所有性能数据 |

### § 15 Health

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（db / comfyui / llm） |

## 3. WebSocket 契约

### 3.1 连接地址

| 频道 | 开发环境 | 生产环境 |
|---|---|---|
| Tasks | `ws://127.0.0.1:8000/ws/tasks` | 同源 |
| Script | `ws://127.0.0.1:8000/ws/script` | 同源 |
| Logs | `ws://127.0.0.1:8000/ws/logs` | 同源 |
| Perf | `ws://127.0.0.1:8000/ws/perf` | 同源 |

> 注意：开发环境绕过 Vite WS 代理，直连 8000。

### 3.2 消息格式

```json
{
  "type": "task.progress",         // 事件类型
  "data": { ... },                   // 事件数据
  "timestamp": "2026-06-22T10:30:00Z"
}
```

### 3.3 Tasks 频道事件

| type | 触发时机 | data 字段 |
|---|---|---|
| `task.created` | 任务创建 | `{task_id, target_type, target_id}` |
| `task.progress` | 进度更新 | `{task_id, progress, phase}` |
| `task.completed` | 成功 | `{task_id, asset_ids}` |
| `task.failed` | 失败 | `{task_id, error, trace_id}` |
| `task.cancelled` | 取消 | `{task_id}` |

### 3.4 Script 频道事件

| type | data 字段 |
|---|---|
| `script.parsing` | `{project_id, stage, message}` — 阶段：reading / parsing / writing |
| `script.stream` | `{project_id, stage, tokens}` — LLM 流式输出片段 |
| `script.stage_done` | `{project_id, stage, ...}` — 某阶段完成 |
| `script.completed` | `{project_id, stats}` — 解析完成 |
| `script.failed` | `{project_id, error}` — 解析失败 |

### 3.5 Logs 频道事件

```json
{
  "type": "log",
  "data": {
    "level": "ERROR",
    "message": "...",
    "phase": "generate",
    "trace_id": "abc123"
  }
}
```

## 4. 客户端错误处理规范

- 前端 `ky` 实例统一捕获 4xx / 5xx，包装为 `ApiError`
- 4xx 错误：Toast 提示用户
- 5xx 错误：Toast + LogViewer 红点
- 网络错误：触发 fallback polling（仅 Tasks 频道）

## 5. 关联文档

- 路由总表：本文档 §2（REST 端点清单）
- 测试用例：`doc/测试手册/` 各模块
