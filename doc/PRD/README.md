# 影序 AI Drama Studio — PRD 索引

> 产品需求文档（Product Requirements Document）总入口。
> 版本：v1.1 | 基线日期：2026-06-23 | 当前阶段：Phase 3（真实生成引擎集成）

## 1. 文档总览

本 PRD 拆分为 **4 大类共 15 份独立文档**，覆盖产品全生命周期。所有文档均与 `doc/开发手册/`、`doc/测试手册/` 保持引用关系，由本索引统一锚定。

| 类别 | 编号 | 文件 | 阅读对象 | 核心职责 |
|---|---|---|---|---|
| **一、基础篇** | PRD-01 | [01-产品概览与愿景.md](./01-产品概览与愿景.md) | 全员 | 产品定位、核心价值、成功指标 |
| | PRD-02 | [02-用户画像与使用场景.md](./02-用户画像与使用场景.md) | 产品 / 设计 | 用户画像、JTBD、核心场景 |
| | PRD-03 | [03-核心工作流与功能地图.md](./03-核心工作流与功能地图.md) | 全员 | 端到端工作流、功能树、优先级矩阵 |
| **二、功能规格篇** | PRD-10 | [10-项目与剧本模块.md](./10-项目与剧本模块.md) | PM / 研发 | 项目 CRUD、剧本编辑器、AI 解析 |
| | PRD-11 | [11-角色与场景道具模块.md](./11-角色与场景道具模块.md) | PM / 研发 | 通用 CRUD 实体、资产画廊 |
| | PRD-12 | [12-剧集与分镜模块.md](./12-剧集与分镜模块.md) | PM / 研发 | 剧集层级、分镜编排、引用关系 |
| | PRD-13 | [13-AI-生成引擎.md](./13-AI-生成引擎.md) | PM / 研发 | Provider 架构、任务队列、生成对话框 |
| | PRD-14 | [14-任务中心与日志.md](./14-任务中心与日志.md) | PM / 研发 | 任务生命周期、WebSocket 推送、日志监控 |
| | PRD-15 | [15-配置中心与设置.md](./15-配置中心与设置.md) | PM / 研发 | Provider 配置、提示词模板、ComfyUI |
| | PRD-16 | [16-资产管理与存储.md](./16-资产管理与存储.md) | PM / 研发 | 资产 CRUD、双向同步、图床集成 |
| **三、非功能规格篇** | PRD-20 | [20-非功能需求与安全合规.md](./20-非功能需求与安全合规.md) | 架构 / 安全 | 性能、可用性、安全、加密 |
| | PRD-21 | [21-技术架构与数据模型.md](./21-技术架构与数据模型.md) | 架构 / 研发 | 技术栈、ER 图、分层架构 |
| | PRD-22 | [22-API-与-WebSocket-契约.md](./22-API-与-WebSocket-契约.md) | 研发 / 前端 | REST 端点、WS 频道、响应契约 |
| **四、演进篇** | PRD-30 | [30-路线图与验收标准.md](./30-路线图与验收标准.md) | 全员 | Phase 路线图、里程碑、验收标准 |

## 2. 阅读顺序建议

- **新人入职 / 跨团队介绍**：01 → 02 → 03 → 30
- **新功能评审**：02 → 03 → 对应功能模块（10-16）→ 22 → 30
- **架构评审 / 安全审计**：21 → 20 → 22 → 对应模块
- **开发实现**：对应模块 PRD → 22 → 21 → 20
- **版本发布**：30 → 对应模块 PRD → 20


## 3. 文档维护规则

1. **变更审批**：基础篇与非功能篇修改须产品负责人 + 架构负责人双重确认；功能规格篇修改须对应模块 Owner 确认。
2. **变更日志**：每次修改在本文件末尾"变更日志"节追加条目，格式 `YYYY-MM-DD | PRD-XX | 变更摘要`。
3. **一致性校验**：每次修改后同步更新 `doc/开发手册/01-项目结构与代码地图.md`、以及受影响的其他 PRD。
4. **版本号约定**：基础篇大版本升级用 v1.x → v2.x；功能规格篇小迭代用 v1.0 → v1.1。

## 4. 术语表（Glossary）

| 术语 | 定义 |
|---|---|
| **项目（Project）** | 一部短剧 / 漫剧的顶层容器，包含剧本、角色、场景、道具、剧集、资产 |
| **剧本（Script）** | 项目原始文本，经 AI 解析后产出结构化实体 |
| **实体（Entity）** | 角色 / 场景 / 道具的统称，共享通用 CRUD 模式 |
| **剧集（Episode）** | 项目下的章节单元，包含若干分镜 |
| **分镜（Shot）** | 剧集下的最小叙事单元，含 7 段式 Prompt（原文 / 角色 / 画面 / 台词 / 首帧 / 末帧 / 视频） |
| **资产（Asset）** | 项目产出的图片 / 视频 / Prompt 文件，按实体类别存放在磁盘目录树 |
| **Provider** | AI 服务提供商（Agnes / SenseNova / OpenAI-compatible / ComfyUI / custom） |
| **ProviderModel** | Provider 下挂载的模型，附带 `param_specs` 与 `capabilities` |
| **GenerationTask** | 一次 AI 生成任务，目标为某实体或分镜的某类资产 |
| **Huey** | ~~任务队列（进程内，SQLite backend）~~ — **v1.1 已移除**，从 pyproject.toml / config.py / config.yaml 清除 |
| **Fernet** | 用于加密 API Key 的对称加密方案（AES-128-CBC + HMAC-SHA256） |
| **style_preset** | 项目级画风预设（anime / 3d / ink / realistic / comic / default） |
| **CRUD** | Create / Read / Update / Delete 的统称，本项目通过 `business_service` 统一实现 |
| **SQLite WAL** | SQLite 的 Write-Ahead Logging 模式，允许并发读写 |
| **TanStack Query** | 前端服务端状态管理库，负责 API 缓存与自动刷新 |
| **Zustand** | 前端轻量 UI 状态管理库，仅用于非服务端状态 |
| **JTBD** | Jobs To Be Done，用户购买产品要完成的"任务" |
| **North Star Metric** | 北极星指标，衡量产品核心价值的关键单一指标 |
| **RICE** | Reach × Impact × Confidence / Effort，功能优先级评分框架 |
| **AC** | Acceptance Criteria，验收标准，采用 Given-When-Then 格式 |
| **FR** | Functional Requirement，功能需求 |
| **BR** | Business Rule，业务规则 |
| **UC** | Use Case，使用场景 |
| **US** | User Story，用户故事 |
| **WAC** | Weekly Active Creator，周活跃创作者数 |
| **trace_id** | 跨层传递的请求追踪 ID，由 contextvars 实现 |
| **IPC** | Inter-Process Communication，Electron 等桌面应用的进程间通信方式（竞品采用） |
| **param_specs** | ProviderModel 的参数规格（JSON Schema），驱动 GenerateDialog 动态渲染控件 |
| **capabilities** | ProviderModel 的能力标签（如 image_generation / video_generation） |
| **cache_key** | Prompt 缓存键（VARCHAR(64)），用于识别相同 Prompt 请求以命中 Provider 侧缓存，减少重复调用成本 |
| **fallback_provider** | 备用 Provider，当主 Provider 调用失败时自动降级切换，保障生成任务不中断 |
| **_last_result** | Provider 元数据字段，每次调用后记录成本、耗时、token 用量等信息，用于成本追踪和可观测性 |
| **drain_tasks** | 优雅关闭函数，在服务器退出前等待 in-flight 任务完成（默认 120s 超时），防止任务数据丢失 |
| **WAL checkpoint** | SQLite WAL 模式检查点操作，TRUNCATE 模式可收缩 WAL 文件至最小，防止长期运行后磁盘膨胀 |
| **output_payload** | GenerationTask 的 JSON 扩展输出字段，存储 Provider 返回的成本元数据（cost / tokens_used 等） |
