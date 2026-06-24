# Agents 详细参考

> 本文件是 `AGENTS.md` 的详细参考，包含编码规范、文档体系、约束规则等完整内容。
> 日常工作中以 `AGENTS.md` 的核心规则为准，需要时查阅本文件。

---

## 一、编码规范

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

## 二、文档体系与写入权限

| 文档 | 路径 | 用途 | AI 是否直接写入 |
|------|------|------|----------------|
| **AGENTS.md** | `AGENTS.md`（项目根目录） | AI 执行规则 | 仅当用户要求优化规则时修改 |
| **每日任务汇总** | `doc/记忆文件/任务-YYYY-MM-DD.md` | 当日所有任务的记录 | 任务结束后写入 |
| **CHANGELOG** | `doc/开发手册/CHANGELOG.md` | 正式变更记录 | 用户确认后再同步 |
| **PRD** | `doc/PRD/` | 产品需求规格 | 行为变化且用户确认后更新 |
| **开发手册** | `doc/开发手册/` | 架构、代码地图、编码规范 | 架构变化且用户确认后更新 |
| **常见 Bug** | `doc/开发手册/08-常见Bug与注意事项.md` | 历次踩坑记录 | 发现新坑时立即追加 |
| **测试手册** | `doc/测试手册/` | 测试用例、框架、数据工厂 | 新增测试时更新 |

### 每日任务汇总用法

1. 同一天的任务全部归到一个文件，例如：`任务-2026-06-21.md`
2. 每条任务独立成节，标题格式：`## 任务 N：<简短标题>`
3. 任务编号按当天顺序递增，**不要跳号或乱序**
4. 内容精简：目标 / 结果 / 修改文件 / 状态，每个最多一两句
5. 状态示例：`已完成`、`待用户确认`、`已验证通过`、`有遗留问题`

---

## 三、上下文管理规则

1. **禁止一次性读取超大文件全文**，优先读相关区间
2. **禁止把无关文件塞进上下文** — 先 Grep 定位，再 Read 确认
3. **禁止一次改多个关注点** — 一个任务只解决一个问题，不要把重构、Bug 修复、新功能混在一起
4. **复杂逻辑必须加注释** — 函数超过 50 行或嵌套超过 3 层，考虑拆分

---

## 四、Windows / PowerShell 执行约束

1. **不要使用 `&&` 连接命令** — PowerShell 不支持。改用分号 `;` 或分多条执行
2. **URL 中的 `&` 必须加引号** — 例如 `"http://127.0.0.1:8000/api/logs?level=ERROR&limit=5"`
3. **删除文件前考虑文件锁** — 必要时用 `try-except` 包装
4. **路径使用反斜杠或原始字符串** — 避免转义问题

---

## 五、前端调试与 HMR

1. dev server 固定地址：`http://127.0.0.1:5173/`
2. 若 UI 显示异常/旧版/空白：
   - 先检查 dev server 是否在运行（端口 5173）
   - 浏览器**强制刷新**（`Ctrl + F5`）
   - 仍异常则重启 `npm run dev`
3. 前端报错优先看浏览器 Console，其次看 `npx tsc --noEmit`
4. Vite HMR 偶发缓存脏状态，重启 dev server 是最稳的排查手段

---

## 六、自测通过标准

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

## 七、依赖与安装规则

- **禁止擅自 `pip install` / `npm install` 新依赖**
- 如果确实需要，先向用户说明：理由、包名、版本、影响范围
- 优先使用项目已有依赖解决问题

---

## 八、Git 同步约定

> 只有用户明确要求时，才执行 Git 同步操作。禁止自动提交或推送。

### 仓库信息

| 项 | 值 |
|---|---|
| 远程仓库 | `https://github.com/qq826635327-hash/-AI.git` |
| 默认分支 | `main` |
| 提交者 | `qq826635327-hash <qq826635327@gmail.com>` |
| 仓库可见性 | 私有 |

### 已忽略内容

`.gitignore` 已配置忽略：

- `.venv/`、`node_modules/`、`__pycache__/`、`.pytest_cache/`
- `data/db/*.sqlite*`、`data/projects/`
- `dist/`、`.vite/`、`*.log`、`logs/`
- `.env`、`.env.local`

### 安全提醒

- `backend/config.yaml` 中带有开发环境默认 `encryption_key`，若仓库为公开状态，必须先改为环境变量 `ADS_ENCRYPTION_KEY` 注入，再提交
- 禁止执行 `git push --force`，除非用户明确要求

---

## 九、回滚策略

如果修改后导致：
- 测试连续失败
- 用户反馈功能异常
- 服务无法启动

**优先回滚到修改前状态**，再重新分析根因，而不是继续打补丁。

---

## 十、完整禁止事项清单

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
12. 禁止用户未确认就改 `CHANGELOG.md` 或 `doc/PRD/`
13. 禁止擅自安装新依赖
14. 禁止需求歧义时自行猜测
