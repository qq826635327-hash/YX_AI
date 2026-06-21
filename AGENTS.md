# AI Drama Studio - Project Rules

> **优先级**：最高。每次接收任务后，先完成下方「开始工作前自检清单」，再动手。
> **版本**：v5.0 | 2026-06-21
> **位置**：`.trae/rules/project_rules.md`（Trae Solo 自动读取）

---

## 一、开始工作前自检清单

- [ ] 已阅读 `doc/开发手册/08-常见Bug与注意事项.md`
- [ ] 已阅读 `doc/开发手册/CHANGELOG.md` 最近 3 条
- [ ] 已确认相关模块手册（`doc/产品手册/` + `doc/开发手册/`）
- [ ] 已定位需要修改的代码文件，并用 Read 工具读过关键段落
- [ ] 任务超过 3 步时，已用 TodoWrite 拆分

---

## 二、技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite 5 + TypeScript 5 + Tailwind CSS + TanStack Query + shadcn/ui |
| 后端 | Python 3.11+ + FastAPI + SQLModel + SQLite |
| 任务队列 | Celery（如启用）|
| 通信 | REST API + WebSocket |
| 运行环境 | Windows PowerShell |
| 包管理 | 前端 npm，后端 Python venv |

---

## 三、文档体系

| 文档 | 路径 | 用途 | AI 是否直接写入 |
|------|------|------|----------------|
| **本文件** | `.trae/rules/project_rules.md` | AI 执行规则、工作流、验证标准 | 仅当用户要求优化规则时修改 |
| **每日任务汇总** | `doc/记忆文件/任务-YYYY-MM-DD.md` | 当日所有任务的记录 | 任务结束后写入 |
| **CHANGELOG** | `doc/开发手册/CHANGELOG.md` | 正式变更记录 | 用户确认后再同步 |
| **产品手册** | `doc/产品手册/` | 产品行为描述 | 行为变化且用户确认后更新 |
| **开发手册** | `doc/开发手册/` | 架构、代码地图、编码规范 | 架构变化且用户确认后更新 |
| **常见 Bug** | `doc/开发手册/08-常见Bug与注意事项.md` | 历次踩坑记录 | 发现新坑时立即追加 |
| **测试手册** | `doc/测试手册/` | 测试用例、框架、数据工厂 | 新增测试时更新 |

### 3.1 每日任务汇总用法

1. 同一天的任务全部归到一个文件，例如：`任务-2026-06-21.md`
2. 每条任务独立成节，标题格式：
   ```
   ## 任务 N：<简短标题>
   ```
3. 任务编号按当天顺序递增，**不要跳号或乱序**
4. 内容包含：**目标 / 结果 / 修改文件 / 核心设计（可选）/ 验证结果 / 状态**
5. 状态示例：`已完成`、`待用户确认`、`已验证通过`、`有遗留问题`

---

## 四、任务执行流程

```
接收需求
  → 完成「开始工作前自检清单」
  → 探索分析（搜索代码 + 读相关文件 + 定位影响面）
  → 制定计划（复杂任务用 TodoWrite 拆分，超 5 步先向用户确认）
  → 编写代码（遵守编码规范，一次只改一个关注点）
  → 自动自省（每轮改完立即跑对应检查：tsc / build / pytest / import）
  → 修复 Bug（最多 3 轮，超过必须报告用户）
  → 更新文档（任务-日期.md + 常见Bug；CHANGELOG/产品手册待用户确认后同步）
  → 报告结果
```

---

## 五、强制规则

### 5.1 修改代码前

1. **必须先读 `08-常见Bug与注意事项.md`** — 避免重复已知错误
2. **必须先读 `CHANGELOG.md` 最近 3 条** — 避免与刚完成的改动冲突
3. **必须先理解通用 CRUD 模式**（`doc/开发手册/04-通用CRUD模式.md`）— 不要创建新的 Service 类来重复 `business_service.py` 的功能
4. **必须先用 Read 读过要改的文件**，禁止直接 Edit/Write
5. **复杂任务必须先计划** — 用 TodoWrite 列出步骤，超 5 步或涉及多个模块先向用户确认方案

### 5.2 修改代码后（自动自省）

每次 Edit/Write 后，必须立即运行对应检查，不要等用户催：

- 后端改完：
  1. `py_compile` 语法检查
  2. `from app.main import app` import 验证
  3. 相关 pytest（如有测试）
- 前端改完：
  1. `npx tsc --noEmit`
  2. `npm run build`
- 前端 UI 改动后：浏览器**强制刷新**（`Ctrl + F5`），排除 HMR 缓存干扰
- 自测失败必须修复后重测 — 最多 3 轮，超过则报告用户

### 5.3 完成任务后

1. **必须更新 `任务-YYYY-MM-DD.md`** — 按 3.1 格式汇总
2. **发现新 Bug 时，立即更新 `08-常见Bug与注意事项.md`**
3. **新增测试时，更新 `doc/测试手册/`**
4. `CHANGELOG.md` 和 `doc/产品手册/` 必须等用户确认后再同步，不要提前动

### 5.4 不确定就问（禁止瞎猜）

遇到以下情况必须停下来问用户，不能自行决定：

- 需求有歧义
- 会改动用户没提到的文件
- 需要安装新依赖
- 需要修改配置/环境变量
- 测试失败超过 3 轮
- 需要引入新的设计模式或架构改动

---

## 六、上下文管理

1. **禁止一次性读取超大文件全文**，优先读相关区间
2. **禁止把无关文件塞进上下文** — 先 Grep 定位，再 Read 确认
3. **禁止一次改多个关注点** — 一个任务只解决一个问题，不要把重构、Bug 修复、新功能混在一起
4. **复杂逻辑必须加注释** — 函数超过 50 行或嵌套超过 3 层，考虑拆分

---

## 七、编码规范

### 后端

- 新实体优先复用 `backend/app/services/business_service.py` 的通用 CRUD 函数
- 使用 `HTTPException` 抛异常，禁止裸 `raise Exception`
- 序列化用 `backend/app/core/serialization.py` 的 `serialize_model` / `serialize_models`
- API 路由只做参数解析 + 调 service，不放业务逻辑
- session 管理：HTTP 用 `Depends(get_session)`，后台任务用 `session_scope()`
- 日志用 `logger.info/warning/error`，不用 print
- Provider 开发遵循 `backend/app/providers/base.py` 的 translate/parse 模式 + `registry.py` 注册机制
- 配置统一走 `config.yaml`，禁止硬编码路径和密钥

### 前端

- 服务端数据用 TanStack Query，不存 Zustand
- API 调用走 `frontend/src/api/` 层，不在组件里直接 fetch
- 类型定义放 `frontend/src/types/index.ts`
- 使用 Tailwind utility class，不写自定义 CSS
- WebSocket 订阅走 `frontend/src/hooks/useWs.ts` 和 `useLogWsSubscription.ts`
- 前端端口固定为 `5173`，`vite.config.ts` 已配置 `strictPort: true`，禁止改回自动端口

---

## 八、Windows / PowerShell 执行约束

1. **不要使用 `&&` 连接命令** — PowerShell 不支持。改用分号 `;` 或分多条执行
2. **URL 中的 `&` 必须加引号** — 例如 `"http://127.0.0.1:8000/api/logs?level=ERROR&limit=5"`
3. **删除文件前考虑文件锁** — 必要时用 `try-except` 包装
4. **路径使用反斜杠或原始字符串** — 避免转义问题

---

## 九、前端调试与 HMR

1. dev server 固定地址：`http://127.0.0.1:5173/`
2. 若 UI 显示异常/旧版/空白：
   - 先检查 dev server 是否在运行（端口 5173）
   - 浏览器**强制刷新**（`Ctrl + F5`）
   - 仍异常则重启 `npm run dev`
3. 前端报错优先看浏览器 Console，其次看 `npx tsc --noEmit`
4. Vite HMR 偶发缓存脏状态，重启 dev server 是最稳的排查手段

---

## 十、快速自测命令（PowerShell 可用）

```powershell
# 后端语法检查（替换实际文件路径）
cd D:\影序AI\backend
.venv\Scripts\python.exe -c "import py_compile; py_compile.compile('app/文件.py', doraise=True)"

# 后端 import 验证
.venv\Scripts\python.exe -c "from app.main import app; print('Import OK')"

# 运行 pytest
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short -x

# 前端类型检查
cd D:\影序AI\frontend
npx tsc --noEmit

# 前端 build 检查
npm run build

# 日志检查（注意 URL 引号）
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/logs?level=ERROR&limit=5').read().decode())"

# 健康检查
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read().decode())"
```

---

## 十一、自测通过标准

| 检查 | 通过条件 | 失败处理 |
|------|---------|---------|
| 语法检查 | 无 SyntaxError | 修复语法，重新检查 |
| Import 验证 | 输出 "Import OK" | 修复 import，检查依赖 |
| pytest | 全部 PASS | 分析失败用例，修复代码，重跑 |
| TypeScript | 无类型错误 | 修复类型定义 |
| 前端 build | 无错误 | 修复 TS/构建错误 |
| 日志检查 | 无新 ERROR | 分析错误原因，修复 |
| 功能验证 | 用户场景可跑通 | 若无法自动验证，标记「待用户确认」 |

---

## 十二、依赖与安装

- **禁止擅自 `pip install` / `npm install` 新依赖**
- 如果确实需要，先向用户说明：理由、包名、版本、影响范围
- 优先使用项目已有依赖解决问题

---

## 十三、Git 处理

- 当前项目**不是 Git 仓库**，不要执行 `git status` / `git diff` / `git commit` 等命令
- 如果用户明确要求提交，先确认项目是否已初始化 Git，再按规范执行
- 不要替用户创建 `.git` 或提交历史

---

## 十四、回滚策略

如果修改后导致：
- 测试连续失败
- 用户反馈功能异常
- 服务无法启动

**优先回滚到修改前状态**，再重新分析根因，而不是继续打补丁。

---

## 十五、禁止事项

1. 禁止不测试就声称完成
2. 禁止跳过文档更新（`任务-日期.md` 是必须的）
3. 禁止重复已知错误（先看 `08-常见Bug`）
4. 禁止手动改 `.venv` / `node_modules` / `__pycache__`
5. 禁止在未理解通用 CRUD 模式时新增 Service 类
6. 禁止 print 调试 — 使用 logger
7. 禁止硬编码路径 — 使用 `config.yaml`
8. 禁止忽略路由顺序 — 固定路径在动态路径前
9. 禁止 session 泄漏 — HTTP 用 Depends，后台用 session_scope
10. 禁止忽略 Windows 文件锁 — 删除文件必须 try-except
11. 禁止在 PowerShell 里使用 `&&` 连接命令
12. 禁止用户未确认就改 `CHANGELOG.md` 或 `doc/产品手册/`
13. 禁止擅自安装新依赖
14. 禁止需求歧义时自行猜测
