# CHANGELOG · 开发手册变更记录

> **强制规则**：每次执行任务完成后，**必须**在本文件添加一条记录。
> 同时更新对应的 PRD 文档。
>
> **AI 必读**：在你开始任何新任务前，先扫一眼本文件最近 3 条变更，避免破坏刚定型的约定。

---

## 2026-06-24 · 全局代码审查 + Bug 修复 + 文档同步

**任务**：全面解读代码与文档，发现并修复 Bug，同步更新过时/不一致的文档。

**代码修复**：

1. **Bug #1 `datetime.utcnow()` 废弃 API**（`execute_task.py`）：改用 `datetime.now(timezone.utc)`，统一 aware datetime 计算
2. **Bug #2 `_select_provider_model` 标签匹配失败仍返回第一个模型**（`execute_task.py`）：改为返回 `None`，由调用方处理
3. **Bug #4 `_safe_mark_task_failed` 中 `write_task_log` 多传 `session` 参数**（`execute_task.py`）：移除多余的 `session` 参数
4. **Bug #6 `_is_url_expired_error` 误判风险**（`execute_task.py`）：改用正则词边界 `\b40[34]\b` 匹配 HTTP 状态码
5. **Bug #7 `_auto_fill_entity` 内部 commit 破坏事务边界**（`execute_task.py`）：移除内部 `session.commit()`，由外层统一提交
6. **Bug #5 SQL 拼接缺少白名单校验**（`db.py`）：添加正则白名单校验 + 表名查询改参数化
7. **清理 `_build_request_payload` 未使用方法**（`base.py`）：删除无调用方的废弃方法

**文档更新**：

1. **01-项目结构与代码地图.md**：
   - 补充缺失的 services（`image_hosting_migrate.py`、`style_preset_service.py`、`backup_service.py`）
   - 补充缺失的 API 路由（`image_hosting.py`、`style_presets.py`）
   - 更新前端 pages 目录（移除已删除的 `SettingsPluginsPage`、`SettingsComfyuiServersPage`、`PlaceholderPage`、`EntitiesPage`；补充 `SystemStatusPage`、`SettingsImageHostingPage`）
   - 更新代码量统计（截至 2026-06-24）
2. **03-前端架构.md**：更新路由表，与 `App.tsx` 完全同步
3. **08-常见Bug与注意事项.md**：
   - §43 标记为"已修"（`generate_video()` ratio 参数丢失）
   - 新增 §44-§49 共 6 条修复记录

---

## 2026-06-24 · Agnes 高分辨率档位参数测试与修复 + 模型配置优化 + 角色图片生成失败排查

**任务**：测试 Agnes AI 2K/4K 图片 + 2K 视频生成接口；总结高分辨率调用经验到避坑指南；调整视频模型配置参数；排查角色 4K+9:16 图片生成失败。

**变更**：

**Agnes 档位参数测试与修复（任务10）**：
- `base.py`：`generate_image()` 中将 params 的非标准字段（如 ratio）自动收集到 `request.extra`，修复 ratio 丢失导致 2K 图片返回正方形
- `agnes_handler.py`：`_translate_image()` 支持 `size="2K"/"4K" + ratio="16:9"` 官方推荐档位写法，ratio 同时放在顶层和 `extra_body` 中（双保险）
- `agnes_handler.py`：`_translate_image()` 和 `_translate_video()` URL 拼接修复：base_url 已含 `/v1` 时不再重复
- `execute_task.py`：datetime 时区修复（aware/naive 混用）、`_Shot` import 修复、params 合并修复
- `image_hosting_service.py`：新增 `_compress_for_upload` 自动压缩超限图片（4K PNG ~11MB 超图床 10MB 限制）
- 测试结果：2K 图片 2624x1472 ✅、4K 图片 5248x2944 ✅、2K 视频 1920x1088 ✅

**模型配置参数优化（任务11）**：
- `agnes-image-2.1-flash`：`custom_size_range` 从 (256,4096) 改为 (256,8192)
- `agnes-video-v2.0`：`param_specs` 从 width/height 数字输入改为 size(720p/1080p) + ratio 档位选择
- 新增 `VIDEO_SIZE_TIERS` 和 `_resolve_video_size` 方法，支持视频档位写法
- `validate_params` 视频校验支持 720p/1080p 档位 + ratio

**角色图片生成失败排查（任务12）**：
- 根因1：`execute_task.py` 中 `generate_image()`/`generate_video()` 未传 timeout，默认 120 秒不够 4K 竖图（需 225 秒）→ 修复：传 `timeout=getattr(handler, "_timeout", 120)`
- 根因2：SenseNova base_url 已含 `/v1`，拼接时又加 `/v1` → 404 Not Found → 已在任务10中修复
- 根因3：智能降级标签匹配错误，LongCat 只有 `text_reasoning` 标签被选为图片降级目标 → 修复：标签未匹配时跳过 Provider（`continue`）
- 验证：4K+9:16 图片 2944x5248 生成成功，耗时 225 秒

**文档**：
- 新建 `doc/服务商API/Agnes/Agnes高分辨率调用避坑指南.md`
- 更新 `doc/记忆文件/任务-2026-06-24.md`

**影响**：
- Agnes 图片 API 支持官方推荐的档位+比例写法，高分辨率生成稳定
- 视频模型前端参数从数字输入改为档位选择，更易用
- 4K 竖图生成不再超时失败
- 智能降级不再错误降级到不支持对应功能的 Provider

---

## 2026-06-24 · 图床自由配置（数据库化 + GitHub/自定义图床 + 前端CRUD页面）

**任务**：将图床配置从 config.yaml 硬编码改为数据库管理，新增 GitHub 和自定义图床类型，前端新增图床配置设置页面。

**变更**：

**后端**：
- `models/image_hosting.py`（新建）：ImageHostingProvider 模型，支持 smms/superbed/boltp/github/custom 五种类型，token 加密存储，extra_config JSON 字段
- `models/__init__.py`：注册 ImageHostingProvider + HOSTING_PROVIDER_TYPES
- `api/image_hosting.py`（新建）：7 个 API 端点（列表/创建/详情/更新/删除/测试上传/设默认），预设类型自动填充 api_url，token 脱敏返回
- `api/__init__.py`：注册 image_hosting 路由
- `services/image_hosting_service.py`：重构 — 新增 `upload_to_provider()` 统一分发、`_upload_to_github()`（GitHub Contents API Base64 上传）、`_upload_to_custom()`（通用 multipart POST）；`get_or_upload_public_url()` 优先从 DB 读取图床配置，fallback 到 config.yaml（向后兼容）
- `services/image_hosting_migrate.py`（新建）：启动时幂等迁移 config.yaml 中的图床配置到 DB（仅首次执行，已有配置不覆盖）
- `main.py`：lifespan 中调用迁移

**前端**：
- `types/index.ts`：新增 HostingProviderType、ImageHostingProvider、ImageHostingCreate 类型
- `api/config.ts`：新增 imageHostingApi（7 个方法）
- `hooks/useApi.ts`：新增 6 个 React Query hooks
- `pages/settings/SettingsImageHostingPage.tsx`（新建）：图床配置页面 — 列表展示、新增/编辑对话框、测试上传、设为默认、删除确认，GitHub 和自定义类型有专属配置面板
- `App.tsx`：添加 /settings/image-hosting 路由
- `components/layout/Sidebar.tsx`：设置菜单中添加"图床配置"入口

**影响**：
- 图床配置可在前端界面自由管理，无需手动编辑 config.yaml
- 新增 GitHub 图床支持（通过 Contents API 上传，访问 raw.githubusercontent.com）
- 新增自定义图床支持（适配任何 multipart POST 图床 API）
- 启动时自动迁移现有 config.yaml 中的闪电图床配置到数据库
- 模型配置中已有的"参考图需要公网URL"勾选项无需修改，自动使用默认图床

---

## 2026-06-24 · 批量删除 + 任务进度条增强 + 重试快速拉取提示

**任务**：角色/场景/道具模块添加批量删除功能；任务中心完善视频生成进度条（显示上传图床/打包发送API等阶段）；失败任务重试时如果API已生成视频，显示快速拉取提示。

**变更**：

**批量删除功能**：
- `characters.py` / `scenes.py` / `props.py`：各添加 `BatchDeleteRequest` 模型和 `POST /batch-delete` 路由（置于 `/{id}` 路由之前，避免 FastAPI 路径匹配冲突）
- `business.ts`：`charactersApi` / `scenesApi` / `propsApi` 各添加 `batchDelete` 方法
- `EntitiesPage.tsx`：多选模式下添加红色"批量删除"按钮，确认后调用对应 API

**任务进度条增强**：
- `execute_task.py`：进度消息从 2 个粗粒度阶段扩展为 9 个细粒度阶段：准备参数(5%)→收集参考图(10%)→上传图床(15%)→已打包发送API(20%)→调用AI引擎(25%)→视频生成中(30%)→复用已有结果(50%)→下载生成结果(70%)→保存记录(85%)→回填到实体(90%)
- `types/index.ts`：`GenerationTask` 添加 `progress_message` 字段
- `useWs.ts`：`task.progress` 处理中提取 `message` 字段写入 `progress_message`
- `TaskCenter.tsx`：运行中任务显示可视化进度条 + 阶段标签（WS 推送 `progress_message` 或根据百分比推断）

**重试快速拉取提示**：
- `TaskCenter.tsx`：失败任务若 `input_payload` 含 `_result_urls` 或 `_video_task_id`，显示蓝色提示框告知"API已成功生成，重试将快速拉取结果"

**影响**：
- 角色/场景/道具页多选模式下可批量删除
- 任务中心运行中任务显示可视化进度条和阶段标签
- 失败任务若API已成功，重试提示可快速拉取

---

## 2026-06-23 · 智能自动重试 + 性能监控增强 + 多项 Bug 修复

**任务**：实现 API 已成功时自动复用 URL 重试下载；修复 Prompt 缓存命中导致重试瞬间完成；修复默认模型配置重启丢失；性能监控增加 API 请求监控和长任务明细；帧卡片生成进度转圈+媒体预览弹窗；闪电图床 is_public 修复；视频参考图类型可配置。

**变更**：

**智能自动重试（任务20-21）**：
- `TasksConfig` 新增 3 个配置项：`auto_retry_on_download_fail`、`auto_retry_max_attempts`、`task_max_age_minutes`
- `GenerationTask` 新增 `auto_retry_count` 字段（INTEGER，默认 0）
- API 成功后将 URL 列表保存到 `input_payload._result_urls`，重试时检测并跳过 API 调用
- 新增 `_handle_task_failure`：任务失败时判断是否自动重试（条件：`_result_urls` 存在 + 未超次数 + 未超时）
- 新增 `_is_url_expired_error`：检测 URL 过期（HTTP 403/410/404），过期时清除 `_result_urls`
- 新增 `_clear_result_urls_if_expired`：公共函数，消除视频/图片下载失败 URL 过期检测的代码重复
- 新增 `cancel_auto_retry`：手动重试时取消正在等待的自动重试协程，避免竞态
- `retry_task` 重置 `auto_retry_count=0` + 调用 `cancel_auto_retry`
- `recover_orphan_tasks` 增强：有 `_result_urls` 的孤儿任务自动重试下载
- 重试延迟公式：`10 * retry_count` 秒（10s, 20s, 30s）
- `config.yaml` 新增 `auto_retry_on_download_fail: true`、`auto_retry_max_attempts: 3`、`task_max_age_minutes: 30`

**Prompt 缓存命中修复（任务15）**：
- `retry_task()` 重置时设置 `input_payload.force = True`，强制跳过 Prompt 缓存
- `retry_task()` 重置时清除 `cache_key = None`
- 缓存键增强：将排序后的 `reference_asset_ids` 纳入缓存键计算，避免换参考图后错误命中缓存
- 新增 `force` 字段：支持强制重新生成、跳过 Prompt 缓存
- 前端生成配置弹窗增加「强制重新生成」复选框

**默认模型配置持久化（任务18）**：
- 根因：`api_update_default_models` 只修改内存 Settings，不持久化到 config.yaml，重启后丢失
- 新增 `save_settings_to_yaml()` 函数，修改配置后自动写入 config.yaml
- `api_update_default_models` 和 `api_update_tasks_config` 修改后均调用持久化
- 后端 `_execute_task_inner` 新增：当 `provider_id` 为空时，根据 `default_models` 配置自动查找匹配的 Provider 和模型

**性能监控增强（任务22）**：
- `observer.ts` 新增 fetch 拦截器，自动记录所有 `/api/` 请求的 URL + 耗时 + 状态码（排除 `/api/perf/` 避免递归）
- `observer.ts` 长任务 payload 增强：记录 `startTime` 和 `name`
- `PerfMonitor.tsx` 新增"长任务明细"区域：4 格 MiniStat 展示平均/P95/最长/占比
- `PerfMonitor.tsx` 新增"慢请求 Top 10"区域：按最大耗时排序展示 API 接口，>1s 琥珀色、>5s 红色
- 原"耗时分布"拆分为三个区域：长任务明细、慢请求、其他耗时分布

**帧卡片转圈 + 媒体预览弹窗（任务16）**：
- `FrameBlock` 增加 generating/pending 状态的 Loader2 转圈动画 + 文字提示
- 新建 `MediaPreviewModal` 组件：全屏弹窗预览图片/视频，支持 6 级缩放、滚轮缩放、拖拽平移
- 右侧面板所有预览区点击弹出预览弹窗，hover 显示放大图标

**闪电图床 is_public 修复（任务17）**：
- 去掉 `is_public` 参数。闪电图床 API 在 multipart/form-data 下无法正确接收布尔值

**视频参考图类型可配置（任务19-20）**：
- `ModelCapabilities` 新增 `video_reference_types` / `video_reference_hint`
- 前端弹窗支持视频参考图多选 + 提示
- 仅 `video_generation=true` 的模型显示视频参考图配置

**影响**：
- API 已成功返回 URL 但下载失败时，系统自动重试下载（不重新调 API），30 分钟超时不再重试
- 手动重试也可复用已有 URL，URL 过期时自动清除并重新调 API
- Prompt 缓存键包含 reference_asset_ids，换参考图后不再错误命中缓存
- 默认模型配置重启后不再丢失
- 性能监控可定位 API 请求耗时和长任务来源

---

## 2026-06-23 · 文档逻辑冲突全面修复（第二轮）

**任务**：深度复查所有文档，对照实际代码验证 API 端点、字段名、WS 事件等。

**变更**：

**PRD-22 API 契约修正**：
- `POST /api/logs/clear` → `DELETE /api/logs/clear`（与代码一致）
- 补充 `POST /api/script/cancel-parse`（代码已有但文档遗漏）
- 补充 `POST /api/assets/open-dir`（代码已有但文档遗漏）
- 补充 `GET /api/providers/{id}/capabilities`（代码已有但文档遗漏）
- 删除 `PATCH /api/config/llm`（代码中不存在此端点）
- perf 端点对齐代码：补充 `POST /api/perf/sessions`（创建）、`POST /api/perf/alerts/{id}/acknowledge`（确认告警），删除不存在的 `sessions/{id}` 和 `sessions/{id}/summary`

**PRD-13 字段名修正**：
- `task.prompt_hash` → `task.cache_key`（与代码 `models/task.py` 一致）

**影响**：
- API 契约与实际路由完全一致
- 数据模型字段名与代码一致

---

## 2026-06-23 · 文档逻辑冲突全面修复

**任务**：检查所有文档的逻辑冲突和不合理之处，按实际代码修正。

**变更**：

**严重冲突修复**：
- `06-任务队列与WebSocket推送.md` / `08-常见Bug与注意事项.md` / `PRD README.md`：`drain_tasks` 超时 10s → 120s（与代码一致）
- `02-后端架构.md`：FastAPI 版本 `0.137` → `≥0.110.0`（与 pyproject.toml 一致）
- `PRD-22`：WS 事件名 `task.succeeded` → `task.completed`（与代码一致）
- `PRD-22`：WS 剧本事件名从 `script.parse.started/stage/succeeded/failed` 改为 `script.parsing/stream/stage_done/completed/failed`（与代码一致）
- `PRD-22`：WS 消息格式字段名 `event` → `type`（与代码一致）

**中等冲突修复**：
- `01-项目结构与代码地图.md`：补充 `perf.py`（models/schemas/api/services）、`image_hosting_service.py`、`perf_service.py`
- `03-前端架构.md`：补充 `PerfMonitor` 组件、`api/perf.ts`
- `PRD-21`：补充 `perf_sessions / perf_events / perf_alerts` 表
- `PRD-22`：补充 `§ 14.5 Perf` API 端点 + `/ws/perf` 频道
- `PRD-13` / `PRD-16`：图床引用 `SM.MS / Superbed` → `boltp / 闪电图床`（当前默认）
- `08-常见Bug与注意事项.md`：修复编号跳跃（§19-22 顺序纠正）

**影响**：
- 文档与代码完全一致，无误导性描述
- perf 性能监控模块完整纳入文档体系

---

## 2026-06-23 · 文档体系清理最终确认

**任务**：按用户最终指令确认文档清理结果：删除所有 `doc/产品手册/` 引用、测试指南改编号 13、PRD-15 不再改动、其余按实际代码修正。

**变更**：
- 全局确认：`doc/产品手册/` 目录已不存在，文档内无残留引用（CHANGELOG 历史记录除外）
- `doc/开发手册/13-测试与调试指南.md` 编号与 README 索引已统一为 13
- PRD-15 保持当前状态，未再修改
- 用户指定的“明文不改”已遵守

**影响**：
- 文档索引与引用一致
- 产品相关内容统一归口 PRD

---

## 2026-06-22 · 剧本解析增强 + 画风预置 + 分镜拖拽排序 + 文档全量修复

**任务**：角色提示词缺少年龄/性别/画风字段；剧本模块增加画风预置；分镜拖拽排序+自动编号；尾帧提示词为空修复；视频提示词逻辑修复；文档全量审查修复。

**变更**：

**数据模型增强**：
- `backend/app/models/character.py`：新增 `gender`（性别）、`age`（年龄描述）字段
- `backend/app/models/scene.py`：新增 `camera_hint`（镜头建议）字段
- `backend/app/models/shot.py`：新增 `camera_size`（景别）、`camera_angle`（视角）、`camera_movement`（运镜）字段
- `backend/app/models/project.py`：新增 `style_preset`（画风预置）字段
- `backend/app/schemas/business.py`：CharacterCreate/Update 增加 gender/age；SceneCreate/Update 增加 camera_hint；ShotCreate/Update 增加 camera_size/camera_angle/camera_movement
- `backend/app/schemas/project.py`：ProjectUpdate/ProjectDetail 增加 style_preset
- `backend/app/db.py`：`_migrate_add_columns()` 增加所有新列的自动迁移

**剧本解析管线增强**：
- `backend/app/pipelines/script_parser.py`：
  - `_extract_characters()` 增加 gender/age 提取
  - `_extract_scenes()` 增加 camera_hint 提取
  - `_extract_shots()` 增加 style_hint 参数，从项目画风设置注入
  - `_parse_delimiter_shots()` 完全重写，支持7段格式（原文对照/出场人物/画面/对话OS/首帧提示词/尾帧提示词/视频提示词）
  - `parse_script_async()` 增加画风获取逻辑，从 Project.style_preset 映射为中文描述
- `backend/app/services/script_service.py`：`write_parsed_to_db()` 增加 gender/age/camera_hint/镜头参数写入

**提示词模板更新**：
- `backend/app/services/prompt_template_service.py`：
  - 角色模板：增加 gender/age 必填要求 + `{{style_hint}}` 占位符
  - 分镜模板：从4段扩展为7段，增加【首帧提示词】【尾帧提示词】【视频提示词】独立输出

**分镜拖拽排序**：
- `backend/app/api/shots.py`：
  - 新增 `ReorderItem`/`ReorderRequest` 模型
  - 新增 `POST /episodes/{episode_id}/shots/reorder` 路由（固定路径在动态路径前）
  - 创建分镜后自动重排 shot_no
  - 删除分镜后自动重排 shot_no
- `frontend/src/api/episodes.ts`：shotsApi 增加 reorder 方法
- `frontend/src/pages/EpisodesPage.tsx`：增加 HTML5 原生拖拽排序 + 分镜插入按钮 + shot_no 显示为 01/02/03 格式

**画风预置**：
- `frontend/src/pages/ScriptPage.tsx`：增加画风预置选择器（默认/二次元动漫/3D渲染/水墨插画/写实/漫画）
- 画风传递链：项目 style_preset → 映射中文描述(style_hint) → 注入模板 {{style_hint}} → LLM输出含画风的提示词

**前端类型同步**：
- `frontend/src/types/index.ts`：Project/ProjectUpdate 增加 style_preset；Character/ParsedCharacter 增加 gender/age；Scene 增加 camera_hint；Shot 增加 camera_size/camera_angle/camera_movement
- `frontend/src/components/EntityCard.tsx`：增加 subtitle 属性，显示性别·年龄
- `frontend/src/config/entityConfig.ts`：角色配置增加 gender/age 编辑字段和 getSubtitle；场景配置增加 camera_hint
- `frontend/src/pages/EntitiesPage.tsx`：传递 subtitle 到 EntityCard

**文档全量修复**（审查发现25个不一致问题，全部修复）：
- `AGENTS.md`：Celery→Huey、Git仓库状态修正
- 同步更新 PRD-10/11/12/15/16 中对应的 UI/UX 与数据模型章节
- `doc/开发手册/CHANGELOG.md`：补充 06-22 记录
- `doc/开发手册/08-常见Bug与注意事项.md`：补充 Agnes API 踩坑记录
- `doc/开发手册/01-项目结构与代码地图.md`：同步新字段
- `doc/开发手册/10-Phase路线图与重构计划.md`：更新 LLM 解析状态

**Bug 修复**：
- 拖拽 405 错误：reorder 路由顺序修正（固定路径在动态路径前）
- 分镜插入后编号不对：创建/删除后自动重排 shot_no
- 尾帧提示词为空：7段模板独立输出首帧/尾帧/视频提示词
- 视频提示词逻辑错误：从重复旁白改为描述首帧到尾帧的视觉运动

**影响**：
- 角色提示词包含性别、年龄、画风信息
- 分镜提示词7段完整输出，首帧/尾帧/视频提示词独立
- 画风从项目级设置传递到所有提示词
- 分镜支持拖拽排序，编号自动更新
- 文档与代码完全一致

---

## 2026-06-21 · 文档体系精简与整合

**任务**：精简项目文件，拆分测试用例文档，整合 PRD，更新开发手册架构一致性。

**变更**：

**文档精简**：
- 删除 `doc/自动化测试手册.md`（3235 行，与 `自动化测试用例说明.md` 大量重叠）
- 删除 `doc/AI开发工作流协议.md`（936 行，与 `Ai执行必读.md` 高度重叠）
- 删除 `backend/app/data/`（旧路径数据库目录）
- `doc/记忆文件/Ai执行必读.md` 升级为 v3.0 总纲文档（整合工作流协议核心内容）

**测试用例拆分**：
- `doc/自动化测试用例说明.md` → `doc/自动化测试用例/` 文件夹（17 个 md 文件）
  - 按模块拆分：项目管理/剧本/角色/场景/道具/剧集/分镜/生成任务/素材/Provider/工作流与配置/单元测试/WebSocket/前端/E2E/数据工厂与CI

**PRD 整合**（6 个文件合并为 3 个）：
- `10-API供应商.md` + `12-模型配置.md` → `10-API供应商与模型配置.md`
- `14-ComfyUI服务器.md` + `15-ComfyUI工作流.md` → `14-ComfyUI.md`
- `16-通用资产卡片.md` + `17-通用编辑对话框.md` → `16-通用组件.md`
- `11-插件扩展.md` 更新 BaseProvider 接口为 translate/parse 模式
- 更新所有交叉引用

**开发手册架构一致性更新**：
- `01-项目结构与代码地图.md`：添加 `core/trace.py`、`schemas/provider_types.py`、更新 providers/ 和 task_log_service.py 描述
- `02-后端架构.md`：新增 §5.5 全链路追踪（trace.py）+ §5.6 Provider 标准化类型（provider_types.py）
- `05-Provider与ComfyUI对接.md`：更新 PRD 引用
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
- `doc/开发手册/07-日志监控开发指南.md`：更新结构化日志 + trace_id + 任务日志 API
- `doc/PRD/14-任务中心与日志.md` / `doc/开发手册/07-日志监控开发指南.md`：更新结构化日志展示 + 任务日志 API

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
- `doc/PRD/14-任务中心与日志.md`：更新状态过滤（全部为默认）
- `doc/PRD/16-资产管理与存储.md`：新增双向同步说明

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
- `doc/PRD/14-任务中心与日志.md` / `doc/开发手册/07-日志监控开发指南.md` 更新 API 响应示例、LogViewer 功能说明、排序与清空描述

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
- 新建 `doc/开发手册/13-测试与调试指南.md`：测试 + 调试技巧
- 新建 `doc/开发手册/10-Phase路线图与重构计划.md`：Phase 1-5 + 紧急 TODO
- 新建 `doc/开发手册/CHANGELOG.md`：本文件

**影响**：
- 新增 13 个开发手册文件
- 不涉及代码变更

**手册同步**：
- 创建 `doc/开发手册/` 整个目录
- 同步在 README 里指向 PRD-14 任务中心与日志

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
- 新建 `doc/PRD/14-任务中心与日志.md`：功能说明 + 架构图 + API

**影响**：
- API：新增 3 个 `/api/logs/*` 端点
- WebSocket：新增 `/ws/logs` 频道
- 前端：右下角新增浮动按钮（带未读红点）；`Ctrl+Shift+L` 快捷键

**手册同步**：
- 新建 `doc/开发手册/07-日志监控开发指南.md`（详细实现文档）
- 新建 `doc/PRD/14-任务中心与日志.md`（功能文档）

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
- `doc/PRD/01-产品概览与愿景.md` 反映重构后的架构
- `doc/PRD/12-剧集与分镜模块.md` 反映 EpisodesPage UI 变更
- `doc/PRD/14-任务中心与日志.md` 反映状态枚举
- `doc/PRD/22-API-与-WebSocket-契约.md` 反映重构后的 API 端点
- `doc/PRD/30-路线图与验收标准.md` 反映 Phase 1 进度

---

## 2026-06-20 · 产品内容并入 PRD

**任务**：产品层面的 UI/UX 细节与功能说明已合并到各 PRD 章节，不再单独维护产品手册目录。

**变更**：
- 删除旧产品手册单文件（`产品手册.md`）
- 删除旧产品手册目录
- 原产品手册内容按模块并入 PRD-01/02/03/10/11/12/13/14/15/16 等

**影响**：
- 文档结构简化，产品需求统一由 PRD 维护
- 不涉及代码变更

---

## 历史记录

> 在此之前的变更在合并历史中追溯，本文件从 2026-06-20 开始。
> 建议每周把关键 Bug 修复和重构挪到"永久 Bug 记录"小节（TODO）。
