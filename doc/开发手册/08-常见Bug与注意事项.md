# 08 · 常见 Bug 与注意事项

> 历次踩坑记录。AI 改代码前**必看**这一章，能避免 90% 的重蹈覆辙。

## 1. DELETE 图片 500（已修，记住别再犯）

**症状**：`DELETE /api/assets/{id}?delete_file=true` 返回 500。

**根因**（`asset_service.py` 旧版）：
```python
session.delete(asset)
session.commit()                        # ← 提交后对象过期
file_path = asset.file_path            # ← 此时访问 lazy attribute 失败
```

commit 后 SQLAlchemy 默认会 expire 所有属性，再次访问 `asset.file_path` 会触发 lazy load，**而此时 session 已经被管理或对象已 detached** → 抛 `DetachedInstanceError`。

**修复**（`asset_service.py:191` 附近）：
```python
# 缓存关键字段
project_id = asset.project_id
file_path = asset.file_path
asset_type = asset.asset_type
file_name = asset.file_name

# 然后再 commit
session.commit()

# 用缓存的字段做后续操作
```

**教训**：
- `expire_on_commit=False` 已经在 `db.py` 启用，但跨 session 还是会失效
- 任何在 commit 后访问 ORM 对象属性的代码都要警惕

## 2. 角色/场景/道具代码 70-80% 重复（已修）

**症状**：3 个实体的 model / service / api / page / detail 几乎一模一样。

**修复**（2026-06-20）：
- 删除 5 个 Service 类（`CharacterService/SceneService/PropService/EpisodeService/ShotService`）
- 改为 `business_service` 通用函数：`list_by_project / get_one / create_entity / update_entity / delete_entity`
- 前端：复用 `EntityCard` / `EntityEditDialog` + `entityConfig.ts` 驱动

**教训**：
- 加新实体时**先看能不能复用通用 CRUD**
- 写新代码前先 grep 现有代码看是不是已有相似实现

## 3. Vite 代理端口错（8001 → 8000）

**症状**：前端调 API 全部 404。

**根因**：`vite.config.ts` 写死了 `target: "http://127.0.0.1:8001"`，但后端实际跑 8000。

**修复**：
```typescript
server: {
  port: 5173,
  host: process.env.VITE_HOST || "127.0.0.1",
  proxy: {
    "/api": { target: `http://127.0.0.1:${process.env.VITE_API_PORT || 8000}` },
    "/ws":  { target: `ws://127.0.0.1:${process.env.VITE_API_PORT || 8000}`, ws: true },
  },
}
```

**教训**：用环境变量，别硬编码。

## 4. ky 重试 DELETE/PATCH 导致重复执行

**症状**：删除按钮点了多次会触发多次 DELETE。

**根因**：`ky` 默认会重试所有方法，DELETE 不幂等。

**修复**（`api/client.ts`）：
```typescript
retry: {
  methods: ["get", "head"],   // 只重试幂等操作
  limit: 2,
}
```

**教训**：网络库默认行为要查文档。

## 5. 任务状态"completed" vs "succeeded"

**症状**：任务完成后在"已完成"过滤里看不到。

**根因**：后端用 `succeeded`，前端过滤条件写成了 `completed`。

**修复**（`TasksPage.tsx`）：
```typescript
statusFilter === "completed" ? "succeeded" : statusFilter
```

**教训**：状态枚举值要前后端一致，**统一用 `succeeded`**。

## 6. 局域网访问失败

**症状**：局域网内 `http://<本机IP>:5173` 打不开前端；`http://<本机IP>:8000` 打不开后端。

**根因**：
- Vite 默认只 bind 127.0.0.1
- 后端 `app.host` 默认 127.0.0.1

**修复**：
```powershell
# 前端
$env:VITE_HOST = "0.0.0.0"; npm run dev

# 后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**生产模式**才能局域网访问（前端 dist + 后端 FastAPI 托管）。

## 7. `scripts/start-dev.bat` 闪退

**症状**：双击 bat 立刻关闭，看不到错误。

**排查**：
1. 在 PowerShell 里手动跑：`cd scripts && .\start-dev.bat`
2. 或手动启动（见 `00-快速开始.md` 方式二）

**教训**：bat 闪退基本是 PATH 或 Python 环境问题。直接手动跑命令最清晰。

## 8. `scripts/start-dev.bat` 端口冲突

**症状**：8000 端口被占用。

**解决**：
```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

## 9. 文件删除 PermissionError（Windows）

**症状**：删除图片时 Windows 报文件被占用。

**修复**（`asset_service.delete_asset`）：
```python
try:
    Path(file_path).unlink(missing_ok=True)
except (PermissionError, OSError, ValueError) as e:
    logger.warning(f"删除文件失败（已忽略）: {e}")
```

**教训**：Windows 下文件锁比 Linux 严格，所有文件 IO 都要 try/except。

## 10. Huey 任务在 in-process 跑会卡住 HTTP 请求

**症状**：用户提交生成 → 前端 30-60 秒没响应。

**根因**：`api/generate.py` 里 `await execute_task_async(task_id)` 是同步阻塞；in-process 跑没真正异步化。

**临时方案**（当前）：用户提交后端一直在跑，前端会超时；`ky` 默认 60 秒超时。

**正确方案**（Phase 2）：用 Huey consumer 进程解耦：
```python
# tasks/execute_task.py
huey = SqliteHuey("ai_drama_studio", filename="data/db/huey.sqlite")

@huey.task()
def execute_task(task_id: str):
    asyncio.run(execute_task_async(task_id))
```

启动：`huey_consumer tasks.execute_task.huey`

## 11. uvicorn `--reload` 在 Windows 不可靠

**症状**：`--reload` 模式下文件修改后没自动重启。

**根因**：uvicorn 在 Windows 下用 `stat` 检测文件变化，watchdog 不可靠。

**建议**：
- 开发时手动重启（Ctrl+C 再起）
- 或用外部 nodemon/watchdog 监听
- 长期方案：换 hypercorn

## 12. 前端 console.error 拦截导致无限循环

**症状**：加了 console.error 拦截后页面卡死。

**根因**：拦截器内部调 `log.error()`，而 `log.error` 内部的 `pushEntry` 失败又 console.error……

**修复**（`main.tsx`）：
```typescript
try {
  log.error(text, "frontend", "console.error");
} catch {
  /* 兜底 */
}
```

**教训**：所有日志写入都要 try/except。

## 13. SQLModel + Pydantic 序列化 datetime

**症状**：返回 JSON 时 `datetime` 被 Pydantic 转成奇怪的格式。

**原因**：Pydantic v2 默认转 ISO 8601（带时区）。`datetime.now(timezone.utc)` 出来的对象有 tzinfo，正常。

**坑点**：如果用 `datetime.utcnow()`（**已 deprecated**），返回的 datetime 没有 tzinfo，序列化时会变 naive 字符串，前后端时区容易错。

**修复**：统一用 `app/models/base.py` 的 `utcnow()`（带 timezone）。

## 14. SQLite WAL 文件残留

**症状**：数据库锁死，提示 "database is locked"。

**解决**：
```powershell
# 关闭后端进程
Get-Process python | Where-Object { $_.Path -like "*.venv*" } | Stop-Process -Force

# 清理 WAL 文件
Remove-Item D:\影序AI\backend\data\db\app.sqlite-wal
Remove-Item D:\影序AI\backend\data\db\app.sqlite-shm
```

**教训**：WAL 文件在异常退出时可能不自动清理；这是 SQLite 的特性不是 bug。

## 15. Fernet 密钥生产环境忘改

**症状**：生产部署后数据库里的 API Key 仍用默认密钥加密。

**解决**（`core/config.py`）：
```python
def validate_security(settings):
    if settings.security.is_default_key:
        env = os.getenv("ADS_ENV", "development")
        if env != "development":
            raise RuntimeError("生产环境禁止使用默认 Fernet 密钥")
```

部署时必须设置 `ADS_ENCRYPTION_KEY` 环境变量。

## 16. WebSocket 重连风暴（已修）

**症状**：服务端重启瞬间，所有客户端同时重连。

**根因**：`scheduleReconnect` 用指数退避但所有客户端同步重连。

**修复**（`frontend/src/api/websocket.ts`）：
```typescript
const baseDelay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay);
const jitter = baseDelay * 0.25 * (Math.random() * 2 - 1);  // ±25% 随机抖动
const delay = Math.max(100, baseDelay + jitter);
```

**教训**：指数退避必须加 jitter，否则多客户端同时重连造成惊群效应。

## 17. ⚠️ Vite 5 WS 代理坑（已修）

**症状**：浏览器 Console 报错：
```
WebSocket connection to 'ws://127.0.0.1:5173/ws/logs' failed:
websocket.ts:26
```

**根因**：Vite 5 的 `proxy.ws = true` 对**自定义路径**经常升级失败。HTTP API 走 Vite 代理没问题，但 WebSocket 升级请求会被 Vite 内部处理失败。

**修复**（`frontend/src/api/websocket.ts`）：
- 不要再依赖 Vite WS 代理
- 让 `WsClient` 在**开发模式默认直连后端 8000 端口**：`ws://127.0.0.1:8000`
- 生产模式（FastAPI 托管前端）浏览器同源访问 `/ws/...`，天然没问题
- 可通过 `VITE_WS_BASE_URL` 环境变量显式覆盖

**教训**：
- 凡是 Vite dev server 自定义配置都先在浏览器 Console 验证 WebSocket 是否真能连
- 跨域 WS 调试：DevTools → Network → WS → 看 Upgrade 是否成功

## 18. EntityCard "生成图片"按钮看不到 / 没反应（已修）

**症状**：在角色/场景/道具页，鼠标 hover 卡片也只能看到中间一个图标按钮，容易点不到；未生成状态下完全看不到生成按钮。

**根因**：
1. "生成图片"按钮只在 `group-hover:opacity-100` 时显示，hover 范围有限
2. 未生成状态（`imageUrl` 为 null）只显示占位图标 `ImageIcon`，没有"生成图片"按钮
3. 鼠标 hover 出现后，hover 区域 + 按钮位置都在卡片正中央，鼠标移动过程按钮就消失了

**修复**（`frontend/src/components/EntityCard.tsx`）：
1. **未生成状态**：直接显示"生成图片"按钮（常驻可点）
2. **已生成状态**：右下角常驻"重新生成"小按钮 + hover 仍显示操作遮罩
3. 这样无论 hover 与否，用户都能找到生成入口

**教训**：
- 不要把"主要操作"放在 hover 状态里。
- 高频操作按钮要常驻可点

## 21. 日志查看器时间差 8 小时（已修）

**症状**：LogViewer 里历史日志的时间比实际时间快 8 小时。

**根因**：
1. 后端 `main.py` 的 Formatter 用 `datefmt="%Y-%m-%d %H:%M:%S"` 写日志，时间是服务器本地时间（Asia/Shanghai，UTC+8），但没有时区标记
2. `backend/app/api/logs.py` 的 `_parse_log_line` 把它当成 UTC，直接拼 `"Z"`：`dt.isoformat() + "Z"`
3. 前端 `new Date(iso)` 看到 `Z` 按 UTC 解析，再转回北京时区 → 显示多了 8 小时

**修复**（`backend/app/api/logs.py`）：
```python
# 把 naive datetime 解释成本地时间，再转成带时区 ISO
timestamp = dt.astimezone().isoformat()
```

返回例如 `2026-06-20T11:53:42+08:00`，前端正确显示本地时间。

**教训**：
- 日志文件本身不带时区时，解析后必须附加本地时区，不能默认 UTC
- 改日志格式要同时改 `_LOG_PATTERN` 和解析逻辑

## 22. 日志查看器最新日志在最顶部（已修）

**症状**：LogViewer 里最新的日志在最上方，用户想看最新日志还要往上翻。

**根因**：`frontend/src/stores/logStore.ts` 的 `pushEntry` / `pushBatch` 把新日志插到数组开头：
```ts
// 旧代码
const entries = [newEntry, ...s.entries].slice(0, MAX_ENTRIES);
```

**修复**（`frontend/src/stores/logStore.ts`）：
```ts
// 新代码：追加到末尾，像 tail -f 一样
const entries = [...s.entries, newEntry].slice(-MAX_ENTRIES);
const entries = [...s.entries, ...newEntries].slice(-MAX_ENTRIES);
```

`LogViewer` 加载历史时仍把后端倒序列表 reverse 成正序后 pushBatch，最终 store 从早到晚排列，最新日志在最下方。

**教训**：
- 日志类 UI 默认按时间正序排列，最新在底部，符合 tail -f / 终端习惯
- 自动滚动到底部 = `scrollTop = scrollHeight`

## 19. ⚠️ AI 常见错误

| AI 行为 | 问题 | 怎么做 |
| --- | --- | --- |
| 直接 import 然后调函数 | 可能循环导入 | 用 TYPE_CHECKING + 字符串引用 |
| `datetime.now()`（无时区） | 序列化时区错 | 用 `utcnow()` |
| 在 HTTP handler 里 `await` 长任务 | 阻塞 | 改 `asyncio.create_task` |
| 用 `print(...)` 调试 | 不会进日志 | 用 `logger.info(...)` |
| 修改日志格式 | 历史 API 解析失败 | 改格式要同时改 `_LOG_PATTERN` |
| 用 `Path.relative_to` 跨盘符 | 抛 ValueError | 用 `os.path.relpath` 或先 `resolve` |
| 改 Vite 代理 port 忘了重启 | 配置不生效 | 改 vite.config.ts 必须重启 vite |
| 给前端 store 加同步 await | 死锁 | Zustand store 永远同步；异步用 TanStack Query |
| 用 `import * as X` 引入整个包 | bundle 大 | 用具名导入 |
| 在 `useEffect` 里没清理 subscription | 内存泄漏 | 必须 return unsubscribe |
| 在函数内部 `import re` 等标准库 | 每次调用都查模块缓存 | 移到文件顶部 |
| `asyncio.get_event_loop()` | Python 3.10+ 已 deprecated | 用 `asyncio.get_running_loop()` |
| 多处重复构建 SQL where 条件 | 维护困难，容易漏改 | 用 `stmt.subquery()` 复用 |
| FastAPI 路由动态路径在固定路径前 | `/sync` 被 `/{id}` 拦截 | 固定路径路由放前面 |

## 20. 已知 TODO（AI 可以认领）

- [ ] Huey 任务队列改造（用 consumer 进程）
- [ ] ComfyUI 工作流执行器
- [ ] 视频生成（多 Handler 支持）
- [ ] 任务取消（cancel API 接 Huey）
- [ ] 任务详情页（TaskLog 列表）
- [ ] 用户/权限系统
- [ ] 导出/导入项目（zip）
- [ ] 标签系统
- [ ] 多语言 i18n
- [ ] Electron 桌面版（Tauri 也可以）

## 23. 实体改名后磁盘目录不同步（已修）

**症状**：角色/场景/道具改名后，磁盘上的文件夹名仍是旧名，导致新生成的素材保存到错误目录或找不到文件。

**根因**：`update_entity` 只更新 DB 字段，没有同步重命名磁盘目录和更新 Asset 的 `file_path`。

**修复**（`business_service.py`）：
- `update_entity` 更新前计算旧目录名，更新后计算新目录名
- 目录名变化时调用 `_rename_entity_dir()`：
  - 磁盘目录重命名
  - 更新关联 Asset 的 `file_path`（替换路径前缀）
- 分镜目录名依赖 `episode_no` + `shot_no`：
  - `shot_no` 变更：`update_entity` 自动处理
  - `episode_no` 变更：`api/episodes.py` 的 `_rename_shots_dirs()` 批量处理

**教训**：
- 任何涉及磁盘路径的逻辑，更新 DB 后必须同步更新磁盘和 Asset 路径
- 目录名计算必须统一走 `sanitize_name` / `get_entity_dirname`，不要分散

## 24. 项目 root_path 指向错误目录

**症状**：生成素材后前端能看到，但本地对应文件夹里没有文件。

**根因**：`projects.root_path` 存的是绝对路径。项目目录迁移或重命名后，DB 中的路径没有同步更新，导致后端读写的是旧目录。

**排查**：
```python
# 检查 DB 中的 root_path
from app.models import Project
project = session.get(Project, project_id)
print(project.root_path)  # 是否指向实际存在的目录？
```

**修复**：更新 DB 中的 `root_path` 为正确路径。

**预防**：
- 迁移项目目录后必须更新 `projects.root_path`
- `config.yaml` 的 `storage.projects_root` 用相对路径，启动时自动解析为绝对路径

## 25. 同步按钮点击无反应

**症状**：角色详情页点击"同步"按钮，前端无任何反馈。

**根因**：
1. 前端 `assetsApi.sync` 的 TypeScript 返回类型缺少 `discovered` 字段
2. `ky.post()` 没有传 `json` 参数，某些情况下 POST 请求可能未正确发送

**修复**（`frontend/src/api/assets.ts`）：
```typescript
// 更新返回类型，添加 discovered 字段
sync: (projectId: string) =>
  unwrap<{ checked: number; cleaned: number; discovered: number; errors: number; details: [...] }>(
    http.post("assets/sync", { searchParams: { project_id: projectId }, json: {} })
  ),
```

**教训**：
- 后端新增返回字段后，前端 TypeScript 类型定义必须同步更新
- `ky.post()` 建议始终传 `json: {}` 确保请求正确发送

---

## AI 改代码前的强制检查清单

> 每次修改代码前，AI 必须逐项确认：

### 后端修改前
- [ ] 确认要改的文件在 `01-项目结构与代码地图.md` 中有记录
- [ ] 确认是否可复用 `business_service.py` 的通用 CRUD
- [ ] 确认路由顺序：固定路径（如 `/sync`）在动态路径（如 `/{id}`）之前
- [ ] 确认 session 管理方式：HTTP 用 `Depends(get_session)`，后台用 `session_scope()`
- [ ] 确认序列化方式：使用 `serialize_model/serialize_models`，不手动拼 dict
- [ ] 确认文件操作有 try-except（Windows 文件锁）
- [ ] 确认不引入新的循环 import

### 前端修改前
- [ ] 确认状态管理方式：服务端数据用 TanStack Query，UI 用 Zustand
- [ ] 确认 API 调用走 `api/` 层
- [ ] 确认类型定义在 `types/index.ts` 中
- [ ] 确认 useEffect 依赖数组完整（特别注意闭包捕获的变量）
- [ ] 确认 WebSocket 单例不被重复创建

### 通用检查
- [ ] 已阅读本文件的所有已知 Bug 记录
- [ ] 已阅读 CHANGELOG.md 最近 3 条变更
- [ ] 修改不会影响其他模块的正常功能
