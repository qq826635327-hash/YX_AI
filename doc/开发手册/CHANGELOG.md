# CHANGELOG · 开发手册变更记录

> **强制规则**：每次执行任务完成后，**必须**在本文件添加一条记录。
> 同时更新对应的 `doc/产品手册/` 文档。
>
> **AI 必读**：在你开始任何新任务前，先扫一眼本文件最近 3 条变更，避免破坏刚定型的约定。

---

## 2026-06-21 · 文档体系精简与整合

**任务**：精简项目文件，拆分测试用例文档，整合产品手册，更新开发手册架构一致性。

**变更**：

**文档精简**：
- 删除 `doc/自动化测试手册.md`（3235 行，与 `自动化测试用例说明.md` 大量重叠）
- 删除 `doc/AI开发工作流协议.md`（936 行，与 `Ai执行必读.md` 高度重叠）
- 删除 `backend/app/data/`（旧路径数据库目录）
- `doc/记忆文件/Ai执行必读.md` 升级为 v3.0 总纲文档（整合工作流协议核心内容）

**测试用例拆分**：
- `doc/自动化测试用例说明.md` → `doc/自动化测试用例/` 文件夹（17 个 md 文件）
  - 按模块拆分：项目管理/剧本/角色/场景/道具/剧集/分镜/生成任务/素材/Provider/工作流与配置/单元测试/WebSocket/前端/E2E/数据工厂与CI

**产品手册整合**（6 个文件合并为 3 个）：
- `10-API供应商.md` + `12-模型配置.md` → `10-API供应商与模型配置.md`
- `14-ComfyUI服务器.md` + `15-ComfyUI工作流.md` → `14-ComfyUI.md`
- `16-通用资产卡片.md` + `17-通用编辑对话框.md` → `16-通用组件.md`
- `11-插件扩展.md` 更新 BaseProvider 接口为 translate/parse 模式
- 更新所有交叉引用

**开发手册架构一致性更新**：
- `01-项目结构与代码地图.md`：添加 `core/trace.py`、`schemas/provider_types.py`、更新 providers/ 和 task_log_service.py 描述
- `02-后端架构.md`：新增 §5.5 全链路追踪（trace.py）+ §5.6 Provider 标准化类型（provider_types.py）
- `05-Provider与ComfyUI对接.md`：更新产品手册引用
- `11-核心数据流.md`：更新 execute_task_async 描述（添加 trace_id、参考图收集、translate/parse 模式、结构化日志、下载重试）

---

## 2026-06-21 · Provider 标准化架构重构 + 结构化日志系统 + trace_id 全链路追踪

**任务**：用户报告分镜生图走文生图而非图生图，要求设计多 Provider API 架构 + 完善日志系统。

**变更**：

**Phase 1: Provider 标准化架构（translate/parse 模式）**：
- `backend/app/schemas/provider_types.py`（新增）：
  - `StandardGenerateRequest`：统一输入模型（model/prompt/size/reference_images/extra）
  - `StandardGenerateResult`：统一输出模型（success/image_urls/raw_request/raw_response/duration_ms/error）
  - `ModelCapabilities`：扩展版能力声明（image_to_image/video_generation/batch_support/max_reference_images 等）
- `backend/app/providers/base.py`（重构）：
  - 新增 `translate(request) → (url, payload, headers)` 抽象方法
  - 新增 `parse(response_body, status_code) → StandardGenerateResult` 抽象方法
  - `generate_image()` 改为基类通用实现（translate → httpx → parse），子类无需覆盖
  - `get_capabilities()` 支持 `ModelCapabilities` 实例和 dict 两种格式
  - `_empty_capabilities()` 返回空能力声明
- `backend/app/providers/agnes_handler.py`（重构）：
  - 实现 `translate()`：标准请求 → Agnes API 的 url/payload/headers（含图生图 extra_body.image）
  - 实现 `parse()`：Agnes API 响应 → StandardGenerateResult
  - `SUPPORTED_MODELS` 中 `capabilities` 改用 `ModelCapabilities` 实例
  - 移除手写的 `generate_image()` 覆盖

**Phase 2: TaskLog 结构化日志**：
- `backend/app/models/task_log.py`（扩展）：
  - 新增 `phase`（阶段标记）、`event_type`（事件类型）、`data_json`（JSON 结构化数据）、`trace_id`（请求追踪 ID）字段
- `backend/app/core/trace.py`（新增）：
  - `contextvars` 实现的 trace_id 追踪（`new_trace_id()`/`get_trace_id()`/`clear_trace_id()`）
- `backend/app/services/task_log_service.py`（重写）：
  - `write_task_log()` 增强：支持 phase/event_type/data_json/trace_id + WS 推送
  - `log_api_call()`：记录 API 调用完整生命周期（请求/响应/耗时/错误 + 自动脱敏）
  - `log_ref_collect()`：记录参考图收集（source/count/details）
  - `log_download()`：记录文件下载（url/size/duration/error）
  - `_sanitize_payload()`：脱敏 API Key + 截断 Data URI
  - `_push_log_ws()`：任务日志通过 WS 推送到前端
- `backend/app/db.py`（扩展）：
  - `_migrate_add_columns()`：自动为已有表添加新列（SQLite ALTER TABLE ADD COLUMN）

**Phase 3: execute_task 集成**：
- `backend/app/tasks/execute_task.py`（重写）：
  - 每个任务分配唯一 trace_id，贯穿全链路
  - ref_collect → generate → download → save 各阶段结构化日志
  - API 调用成功/失败都有 `log_api_call()` 记录
  - 下载成功/失败都有 `log_download()` 记录
  - 参考图收集有 `log_ref_collect()` 详情记录

**Phase 4: 前端增强**：
- `frontend/src/types/index.ts`：新增 `TaskLogEntry`/`TaskLogListResponse` 类型
- `frontend/src/api/logs.ts`：新增 `taskLogs()` API 方法
- `frontend/src/components/LogViewer.tsx`：
  - LogRow 展示 phase 标签（系统/校验/参考图/生成/下载）
  - 结构化摘要行（API 调用显示 provider/model/status/duration）
  - 展开详情查看完整 data_json
- `frontend/src/hooks/useLogWsSubscription.ts`：WS 推送携带 phase/event_type/data_json
- `backend/app/api/logs.py`：新增 `GET /api/logs/tasks/{task_id}` 结构化日志查询 API

**Bug 修复**：
- `backend/app/clients/agnes_client.py`：`download_file` 新增 3 次重试（递增等待 2s/4s/6s），修复 SSL 连接中断导致任务失败
- `backend/app/api/logs.py`：`entries` 变量名应为 `sliced` 的 NameError 修复

**影响**：
- 新增 Provider 只需实现 translate/parse 两个方法
- 任务日志从纯文本升级为结构化数据，可查询可分析
- trace_id 串联同一任务的多步操作，便于问题定位
- 前端日志面板展示阶段标签和结构化摘要
- 下载失败自动重试，减少瞬时网络错误影响

**手册同步**：
- `doc/开发手册/05-Provider与ComfyUI对接.md`：更新 Provider 架构说明（translate/parse 模式）
- `doc/开发手册/07-日志监控开发指南.md`：更新结构化日志 + trace_id + 任务日志 API
- `doc/开发手册/09-测试与调试指南.md`：新增 Provider translate/parse 测试方法
- `doc/产品手册/22-日志监控.md`：更新结构化日志展示 + 任务日志 API

---

## 2026-06-20 · 实体重命名同步 + 同步按钮修复 + 任务中心优化

**任务**：修复同步按钮无反应、实体改名后磁盘目录不同步、任务中心 UI 调整。

**变更**：

**后端**：
- `backend/app/services/business_service.py`：
  - `update_entity` 新增目录重命名逻辑：更新前计算旧目录名，更新后比较新目录名，不一致则重命名磁盘目录 + 更新 Asset `file_path`
  - 新增 `_compute_dirname(model, entity, session)`：根据实体类型计算目录名（角色/场景/道具用 `sanitize_name(name)`，分镜用 `第{ep_no}集_{shot_no}`）
  - 新增 `_rename_entity_dir()`：重命名磁盘目录 + 更新关联 Asset 的 `file_path`（替换路径前缀）
  - 分镜的 Asset 查询用 `target_type.like("shot_%")` 兼容三种 target_type
- `backend/app/api/episodes.py`：
  - 新增 `_rename_shots_dirs()`：`episode_no` 变更时批量重命名该剧集下所有分镜目录 + 更新 Asset 路径
- `backend/app/services/asset_service.py`：
  - `sync_assets` 从单向清理改为双向同步（清理 + 发现磁盘上未注册的文件）
  - 新增磁盘扫描：遍历 `角色/`、`场景/`、`道具/`、`分镜/` 目录下的 `images/` 和 `videos/`，为没有 DB 记录的文件自动创建 Asset 并回填到实体

**前端**：
- `frontend/src/api/assets.ts`：
  - `sync` 返回类型添加 `discovered` 字段
  - `http.post` 添加 `json: {}` 确保 POST 请求正确发送
- `frontend/src/components/TaskCenter.tsx`：
  - 任务信息模块：`justify-between` → `flex gap-2`，左对齐
  - 输入参数："尺寸"改为"分辨率"，同样左对齐
- `frontend/src/components/layout/Sidebar.tsx`：
  - 状态过滤菜单新增"全部"选项（`ListFilter` 图标），默认展示全部

**数据修复**：
- 修正 `projects.root_path` 从 `D:/web工作流/影序AI/...` 为 `D:/影序AI/...`
- 重命名磁盘目录 `角色/丽水/` → `角色/李四/`，更新 4 条 Asset 的 `file_path`
- 清理孤儿文件和空目录

**影响**：
- 实体改名后磁盘目录和 Asset 路径自动同步
- 同步按钮正常工作，支持双向同步
- 任务中心默认展示全部任务，信息左对齐，输入参数显示分辨率

**手册同步**：
- `doc/开发手册/04-通用CRUD模式.md`：新增 §3 `update_entity` 重命名目录逻辑
- `doc/开发手册/08-常见Bug与注意事项.md`：新增 §23 实体改名不同步、§24 root_path 错误、§25 同步按钮无反应
- `doc/产品手册/09-任务中心.md`：更新状态过滤（全部为默认）
- `doc/产品手册/18-素材画廊.md`：新增 §3.6 双向同步

---

## 2026-06-20 · 全局代码优化（第二轮）

**任务**：用户要求"仔细阅读 doc 里的文档，并审查代码，全局进行优化"。

**变更**：

**后端**：
- `backend/app/services/business_service.py`：
  - `_sanitize_name` → `sanitize_name`（公开导出）
  - `_get_entity_dirname` → `get_entity_dirname`（改为接收 `target_type + target_id`，统一入口）
  - `_MODULE_DIR` → `MODULE_DIR_MAP`，`_TARGET_TYPE` → `TARGET_TYPE_MAP`，新增 `TARGET_TYPE_DIR_MAP`
  - `delete_entity` 中引用更新
- `backend/app/tasks/execute_task.py`：
  - 删除重复的 `_get_entity_name`、`_get_module_dir`、`_sanitize_name`，改为引用 `business_service`
  - 合并 session_scope：从 ~10 个减少到 5 个（3 阶段：读取上下文+准备参数、API 调用、保存结果）
- `backend/app/api/generate.py`：批量生成 `await asyncio.gather` → `asyncio.create_task`，不阻塞 HTTP 响应
- `backend/app/services/generation_service.py`：
  - `list_tasks` 的 count 查询用 `stmt.subquery()` 复用 where 条件
  - `recover_orphan_tasks` 中 `asyncio.get_event_loop()` → `asyncio.get_running_loop()`
- `backend/app/ws/routes.py`：提取 `_ws_channel_handler()` 通用函数，消除 3 处重复的 WS 路由处理代码
- `backend/app/api/tasks.py`：task_log 序列化改用 `serialize_models`，统一日期格式
- `backend/app/api/characters.py`：添加缺失的 `from typing import Optional`
- `backend/app/api/assets.py`：路由顺序修复 — 固定路径（`/sync`、`/projects/{id}/upload`）移到动态路径（`/{asset_id}`）之前
- `backend/app/api/logs.py`：日志文件读取从 `readlines()` 改为 `deque(f, maxlen=N)` 只读末尾 N 行
- `backend/app/api/providers.py`：导入整理（logger 位置调整）
- `backend/app/providers/agnes_handler.py`：`import re` 从函数内部移到文件顶部
- `backend/app/services/asset_service.py`：`_get_entity_name_for_upload` 复用 `business_service.get_entity_dirname`
- `backend/app/services/project_service.py`：`list_projects` count 查询用 `subquery()` 复用 where 条件

**前端**：
- `frontend/src/components/TaskCenter.tsx`：移除冗余的 `completed` 状态（后端用 `succeeded`）
- `frontend/src/hooks/useApi.ts`：`useTasks` 智能轮询（有活跃任务 5s，否则 30s）
- `frontend/src/components/layout/Sidebar.tsx`：移除冗余的 `tasksScopeItems`（当前项目/全部项目），简化为仅状态过滤
- `frontend/src/api/websocket.ts`：重连添加 ±25% 随机 jitter，避免惊群效应
- `frontend/src/components/GenerateDialog.tsx`：`DynamicParamsPanel` 用 `memo` + `useCallback` 包裹，减少不必要重渲染

**影响**：
- 后端重复代码大幅减少（3 处重复逻辑统一到 `business_service`）
- 批量生成不再阻塞 HTTP 响应
- WS 重连不会造成惊群
- 日志 API 大文件性能优化
- 资产路由 `/sync` 和 `/projects/{id}/upload` 不再被 `/{asset_id}` 拦截

**手册同步**：
- `doc/开发手册/02-后端架构.md`：更新 session_scope 建议、WS 通用处理、序列化说明、目录名计算
- `doc/开发手册/04-通用CRUD模式.md`：新增实体目录名计算统一入口说明
- `doc/开发手册/06-任务队列与WebSocket推送.md`：更新异步化现状、智能轮询、任务详情页
- `doc/开发手册/08-常见Bug与注意事项.md`：§16 标记已修、§19 新增 4 条 AI 常见错误
- `doc/开发手册/10-Phase路线图与重构计划.md`：标记全局代码优化已完成

---

## 2026-06-20 · 日志查看器修复与完善

**任务**：用户反馈日志查看器"时间不对"、"最新日志在最顶部应该在最下方"、"清空按钮只清前端缓存"。

**变更**：

**后端**：
- 修改 `backend/app/api/logs.py`：`_parse_log_line` 不再把无 tz 的日志时间当成 UTC，而是用 `dt.astimezone()` 解释成本地时间后输出 ISO8601（如 `2026-06-20T11:53:42+08:00`），修复历史日志时间差 8 小时的问题

**前端**：
- 修改 `frontend/src/components/LogViewer.tsx`：
  - `formatTime` 增加日期显示（当天显示时间，跨天显示 `MM-DD HH:MM:SS`）
  - 清空按钮调用 `logsApi.clear()`，真正清空后端日志文件 + 前端缓存
- 修改 `frontend/src/stores/logStore.ts`：
  - `pushEntry` 改为追加到数组末尾（`[...s.entries, newEntry]`）
  - `pushBatch` 改为追加到数组末尾（`[...s.entries, ...newEntries]`）
  - 限制改为 `slice(-MAX_ENTRIES)` 保留最新的 500 条

**影响**：
- 历史日志时间与本地时间一致
- LogViewer 最新日志在最下方，像 `tail -f` 一样自然滚动
- 清空操作真正清空后端日志文件

**手册同步**：
- `doc/开发手册/08-常见Bug与注意事项.md` 新增 §21（日志时间差 8 小时）、§22（日志排序方向）
- `doc/产品手册/22-日志监控.md` 更新 API 响应示例、LogViewer 功能说明、排序与清空描述

---

## 2026-06-20 · Bug 修复：WS 连接失败 + 角色页"生成图片"按钮无反应

**任务**：用户报告"角色页点击生成图片完全没反应；WebSocket connection to 'ws://127.0.0.1:5173/ws/logs' failed"。

**根因**：
1. **Vite 5 WS 代理坑**：浏览器通过 `ws://127.0.0.1:5173/ws/logs` 连 Vite，Vite 5 对自定义路径的 WS 升级经常失败
2. **后端进程未重启**：之前加的 `/ws/logs` 路由在 8000 端口的旧版后端里没有（403）
3. **EntityCard 按钮位置**：未生成状态下没显示"生成图片"按钮，已生成状态下"重新生成"只在 hover 时出现

**变更**：

**前端**：
- 修改 `frontend/src/api/websocket.ts`：新增 `resolveWsBaseUrl()`，开发模式默认直连 `ws://127.0.0.1:8000`，绕过 Vite WS 代理；支持 `VITE_WS_BASE_URL` 环境变量覆盖；导出 `WS_BASE_URL` 方便调试
- 修改 `frontend/src/components/EntityCard.tsx`：
  - 未生成状态：占位图标下方加常驻"生成图片"按钮
  - 已生成状态：右下角加常驻"重新生成"小按钮
  - hover 操作遮罩仅在已有图时显示

**后端**：
- 无代码变更（仅重启进程加载新代码）

**影响**：
- WebSocket 直接连后端 8000 端口，跨域无 CORS 限制（WS 不走 CORS）
- 角色/场景/道具页"生成图片"按钮常驻可点
- 生产模式无变化（FastAPI 托管前端天然同源）

**手册同步**：
- `doc/开发手册/08-常见Bug与注意事项.md` 新增 §17（Vite WS 代理坑）、§18（EntityCard 按钮）

---

## 2026-06-20 · 创建开发手册体系

**任务**：用户要求"根据现有的情况，把开发手册也完善一下"。

**变更**：
- 新建 `doc/开发手册/README.md`：手册总览 + AI 工作约定
- 新建 `doc/开发手册/00-快速开始.md`：环境准备 + 启动方式 + 第一个生成流程
- 新建 `doc/开发手册/01-项目结构与代码地图.md`：目录树 + "我要加新功能去哪改"
- 新建 `doc/开发手册/02-后端架构.md`：FastAPI + SQLModel + WS + Huey 详解
- 新建 `doc/开发手册/03-前端架构.md`：React + TanStack Query + Zustand
- 新建 `doc/开发手册/04-通用CRUD模式.md`：5 个相似实体的抽象做法
- 新建 `doc/开发手册/05-Provider与ComfyUI对接.md`：新增 AI Provider 步骤
- 新建 `doc/开发手册/06-任务队列与WebSocket推送.md`：任务全生命周期
- 新建 `doc/开发手册/07-日志监控开发指南.md`：WsLogHandler + LogViewer 实现细节
- 新建 `doc/开发手册/08-常见Bug与注意事项.md`：历次踩坑 + AI 改代码前必看
- 新建 `doc/开发手册/09-测试与调试指南.md`：测试 + 调试技巧
- 新建 `doc/开发手册/10-Phase路线图与重构计划.md`：Phase 1-5 + 紧急 TODO
- 新建 `doc/开发手册/CHANGELOG.md`：本文件

**影响**：
- 新增 13 个开发手册文件
- 不涉及代码变更

**手册同步**：
- 创建 `doc/开发手册/` 整个目录
- 同步在 README 里指向 `doc/产品手册/15-日志监控.md`

---

## 2026-06-20 · 详细日志监听功能（前后端错误统一监控）

**任务**：用户要求"写一个详细日志监听的功能，方便 AI 开发的时候直接获取前后端错误信息"。

**变更**：

**后端**：
- 新建 `backend/app/ws/log_handler.py`：`WsLogHandler` 把根 logger 的 ERROR/WARNING 广播到 `/ws/logs`
- 修改 `backend/app/ws/routes.py`：新增 `/ws/logs` 端点
- 修改 `backend/app/main.py`：注入事件循环和 manager；把 handler 接入根 logger
- 新建 `backend/app/api/logs.py`：`GET /api/logs`、`GET /api/logs/info`、`POST /api/logs/clear`

**前端**：
- 修改 `frontend/src/api/websocket.ts`：新增 `logsWs` 单例
- 新建 `frontend/src/api/logs.ts`：历史日志 API 封装
- 新建 `frontend/src/stores/logStore.ts`：Zustand 日志 store（最多 500 条）
- 新建 `frontend/src/hooks/useLogWsSubscription.ts`：订阅 `/ws/logs` 写入 store
- 新建 `frontend/src/components/LogViewer.tsx`：浮动日志查看器
- 修改 `frontend/src/components/layout/MainLayout.tsx`：挂载 LogViewer
- 修改 `frontend/src/api/client.ts`：ky 4xx/5xx 自动写日志
- 修改 `frontend/src/main.tsx`：接入 `window.onerror` / `unhandledrejection` / `console.error`
- 修改 `frontend/src/types/index.ts`：新增 `LogEntry` / `LogLevel` / `LogSource` 类型

**文档**：
- 新建 `doc/产品手册/22-日志监控.md`：功能说明 + 架构图 + API

**影响**：
- API：新增 3 个 `/api/logs/*` 端点
- WebSocket：新增 `/ws/logs` 频道
- 前端：右下角新增浮动按钮（带未读红点）；`Ctrl+Shift+L` 快捷键

**手册同步**：
- 新建 `doc/开发手册/07-日志监控开发指南.md`（详细实现文档）
- 新建 `doc/产品手册/15-日志监控.md`（功能文档）

---

## 2026-06-20 · 全量重构：屎山代码清理 + Bug 修复

**任务**：用户要求"按照你的建议，全部执行"（基于 2026-06-20 之前生成的产品设计手册 + 开发指导手册中的建议）。

**变更**（简化版，完整列表见 git diff）：

**后端**：
- 新建 `backend/app/core/serialization.py`：通用 `serialize_model` / `serialize_models` 工具
- 修改 `backend/app/core/config.py`：新增 `logs_dir` 字段
- 修改 `backend/app/services/asset_service.py`：修复 `delete_asset` 500 bug（缓存字段+独立 try-except）
- 重写 `backend/app/services/business_service.py`：删除 5 个 Service 类；通用 CRUD 函数
- 重写 `backend/app/api/characters.py`、`scenes.py`、`props.py`、`episodes.py`、`shots.py`、`shot_references.py`：全部走 `business_service`
- 修改 `backend/app/main.py`：`_setup_logging` 写入文件 + WsLogHandler 集成

**前端**：
- 修改 `frontend/src/api/client.ts`：ky 只重试 GET/HEAD
- 修改 `frontend/src/pages/TasksPage.tsx`：任务状态枚举修正（completed → succeeded）
- 修改 `frontend/src/vite.config.ts`：代理端口 8001 → 8000
- 修改 `frontend/src/pages/EpisodesPage.tsx`：UI 优化（合并引用、调整按钮）

**影响**：
- 后端 5 个 Service 类被删除（API 层无感）
- 删除图片 500 bug 修复
- 前端 Vite 代理修复
- 任务状态显示修复

**手册同步**：
- `doc/产品手册/00-产品概览.md` 反映重构后的架构
- `doc/产品手册/08-剧集结构.md` 反映 EpisodesPage UI 变更
- `doc/产品手册/09-任务中心.md` 反映状态枚举
- `doc/产品手册/A-完整路由表.md` 反映重构后的 API 端点
- `doc/产品手册/B-Phase状态对比.md` 反映 Phase 1 进度
- （注：本次重构时手册尚未拆分到 doc/产品手册/，已在后续"产品手册拆分"任务中补齐）

---

## 2026-06-20 · 产品手册拆分到独立文件

**任务**：用户要求"产品手册写到 D:\web工作流\ai-drama-studio\doc\产品手册，拆分模块，每个模块一个 md"。

**变更**：
- 删除 `doc/产品手册.md`（单文件大文档）
- 新建 `doc/产品手册/` 目录
- 拆分 25 个模块文件：
  - `00-产品概览.md`、`01-全局说明.md`、`02-首页项目列表.md`、`03-项目总览.md`、`04-剧本.md`
  - `05-角色.md`、`06-场景.md`、`07-道具.md`、`08-剧集结构.md`、`09-任务中心.md`
  - `10-API供应商.md`、`11-插件扩展.md`、`12-模型配置.md`、`13-提示词模版.md`
  - `14-ComfyUI服务器.md`、`15-ComfyUI工作流.md`、`16-通用资产卡片.md`、`17-通用编辑对话框.md`
  - `18-素材画廊.md`、`19-生成对话框.md`、`20-图片灯箱.md`、`21-主题与系统功能.md`
  - `A-完整路由表.md`、`B-Phase状态对比.md`
  - `README.md`

**影响**：
- 文档结构清晰
- 不涉及代码变更

**手册同步**：
- 创建整个 `doc/产品手册/` 目录
- 后续"日志监控"任务时新建 `22-日志监控.md`

---

## 历史记录

> 在此之前的变更在合并历史中追溯，本文件从 2026-06-20 开始。
> 建议每周把关键 Bug 修复和重构挪到"永久 Bug 记录"小节（TODO）。
