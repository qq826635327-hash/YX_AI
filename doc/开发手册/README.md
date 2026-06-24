# AI Drama Studio · 开发手册

> 面向 AI 编程助手（以及新加入的开发者）的快速入门 + 内部实现地图。
> 目标：**5 分钟内知道项目怎么跑起来，10 分钟内知道哪里改什么。**

## 目录

| 编号 | 主题 | 用途 |
| --- | --- | --- |
| 00 | [快速开始](./00-快速开始.md) | 环境准备、启动后端 / 前端、第一个生成流程跑通 |
| 01 | [项目结构与代码地图](./01-项目结构与代码地图.md) | 目录树、关键文件索引、"我要加新功能去哪改" |
| 02 | [后端架构](./02-后端架构.md) | FastAPI + SQLModel + WebSocket + asyncio 任务队列 |
| 03 | [前端架构](./03-前端架构.md) | React + TanStack Query + Zustand + Vite + Tailwind |
| 04 | [通用 CRUD 模式](./04-通用CRUD模式.md) | 角色/场景/道具/剧集/分镜的抽象做法 |
| 05 | [Provider 与 ComfyUI 对接](./05-Provider与ComfyUI对接.md) | 新增 AI Provider 的步骤 |
| 06 | [任务队列与 WebSocket 推送](./06-任务队列与WebSocket推送.md) | 任务生命周期、状态推送 |
| 07 | [日志监控开发指南](./07-日志监控开发指南.md) | **给 AI 用的事实日志（前后端错误）** |
| 08 | [常见 Bug 与注意事项](./08-常见Bug与注意事项.md) | **历次踩坑记录、AI 改代码前必看** |
| 09 | [Agents 详细参考](./09-Agents详细参考.md) | 编码规范、文档体系、上下文管理等 AI 执行细则 |
| 13 | [测试与调试指南](./13-测试与调试指南.md) | 单元 / 集成 / 手动测试、调试技巧 |
| 10 | [Phase 路线图与重构计划](./10-Phase路线图与重构计划.md) | 后续要做什么、按什么顺序 |
| 11 | [核心数据流](./11-核心数据流.md) | 4 条关键数据流链路的完整路径 |
| 12 | [文件存储约定](./12-文件存储约定.md) | 目录结构、命名规则、路径解析、同步机制 |
| — | [CHANGELOG](./CHANGELOG.md) | 每次执行任务后的变更记录 |

## 项目一句话总结

AI Drama Studio 是一个面向短剧 / 短片生产的 Web 工作台：

- **后端**：FastAPI + SQLModel（SQLite WAL）+ WebSocket + asyncio
- **前端**：React 18 + Vite + Tailwind + TanStack Query + Zustand
- **核心流程**：项目 → 剧本 → 自动解析出角色/场景/道具/剧集/分镜 → AI 生成图片/视频 → 资产库 → 导出
- **多 Provider**：内置 Agnes（云端），预留 ComfyUI（本地工作流），Provider 通过 Handler 注册

## 关键技术决策

| 决策 | 原因 | 文件 |
| --- | --- | --- |
| SQLite + WAL | 零部署，本地开发友好 | `backend/app/db.py` |
| SQLModel | 同时拿 Pydantic + SQLAlchemy | 所有 `models/*.py` |
| 通用 CRUD 函数代替 5 个 Service 类 | 5 个实体几乎一模一样 | `services/business_service.py` |
| WebSocket 频道化（tasks/script/logs） | 一份代码多频道复用 | `ws/routes.py` |
| WebSocket LogHandler 广播 ERROR/WARNING | 实时把后端错误推给 AI 调试 | `ws/log_handler.py` |
| 实体配置驱动前端（`entityConfig.ts`） | 角色/场景/道具前端模板共用 | `frontend/src/config/entityConfig.ts` |
| `ky` 替代 fetch | 内置超时/重试/拦截器 | `api/client.ts` |
| BasicAuth 可选中间件 | 简单保护 | `main.py` |
| Fernet 加密 API Key | API Key 不能明文存 | `core/config.py` |
| 浮窗式 LogViewer | 不打扰主流程，可一键复制日志给 AI | `components/LogViewer.tsx` |

## AI 工作约定（重要）

1. **修改代码前先看 `08-常见Bug与注意事项.md`**，避免重蹈覆辙。
2. **新增实体**（除角色/场景/道具/剧集/分镜/任务/资产/项目/剧本/Provider/工作流/分镜关联）时，先和用户确认是否要复用 `business_service` 的通用 CRUD。
3. **改 API** 时同步检查 `doc/PRD/22-API-与-WebSocket-契约.md`，若行为变化要更新。
4. **改前端组件**时同步检查 `doc/PRD/` 里对应模块的 PRD（PRD-10~16）。
5. **完成任务后**：必须更新 `CHANGELOG.md` 和相关模块的 PRD / 开发手册（日志 / 监控相关改动需同步更新 `07-日志监控开发指南.md`）。
6. **遇到错误**：先用浮动 LogViewer 看实时错误（`Ctrl+Shift+L` 打开），再用 `GET /api/logs?keyword=...` 查历史。
7. **不要碰 `.venv/`、`node_modules/`、`__pycache__/`、`*.pyc`**。

## AI 自测协议（强制执行）

> 每次修改代码后，AI 必须按以下流程自测，**不得跳过任何步骤**。

### 快速自测（5 分钟内完成）

```powershell
# 1. 后端语法检查（替换为实际修改的文件）
cd D:\影序AI\backend
.venv\Scripts\python.exe -c "import py_compile; py_compile.compile('app/services/business_service.py', doraise=True)"

# 2. 后端启动验证
.venv\Scripts\python.exe -c "from app.main import app; print('Import OK')"

# 3. 运行自动化测试
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short -x -q 2>&1

# 4. 前端类型检查
cd D:\影序AI\frontend
npx tsc --noEmit

# 5. 检查日志
cd D:\影序AI\backend
.venv\Scripts\python.exe -c "
import httpx; r = httpx.get('http://127.0.0.1:8000/api/logs?level=ERROR&limit=5')
errors = r.json().get('data', {}).get('entries', [])
if errors: print(f'发现 {len(errors)} 条错误日志:'); [print(f'  - {e[\"message\"][:100]}') for e in errors]
else: print('无错误日志 ✓')
"
```

### 自测通过标准

| 检查 | 通过条件 | 失败处理 |
|------|---------|---------|
| 语法检查 | 无 SyntaxError | 修复语法，重新检查 |
| Import 验证 | 输出 "Import OK" | 修复 import，检查依赖 |
| pytest | 全部 PASS | 分析失败用例，修复代码，重跑 |
| TypeScript | 无类型错误 | 修复类型定义 |
| 日志检查 | 无新 ERROR | 分析错误原因，修复 |

### 自测失败处理流程

```
发现失败 → 记录失败信息 → 分析根因 → 修复代码 → 重新自测 → 最多循环 3 次
   ↓ 3 次仍未通过
   报告给用户：错误详情 + 已尝试方案 + 建议
```

### 详细协议

详见 `AGENTS.md`（项目根目录，AI 执行总纲文档）。
