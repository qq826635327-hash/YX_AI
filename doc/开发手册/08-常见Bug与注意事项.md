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

## 10. Huey 任务在 in-process 跑会卡住 HTTP 请求（已修，Huey 已移除）

**症状**：用户提交生成 → 前端 30-60 秒没响应。

**根因**：旧版 `api/generate.py` 里 `await execute_task_async(task_id)` 是同步阻塞。

**修复**（2026-06-23）：
- 移除 Huey 依赖，改用 `asyncio.create_task(execute_task_async(task_id))` 异步启动
- 并发控制：`asyncio.Semaphore(_MAX_CONCURRENT_TASKS=4)` 限流
- 优雅关闭：`drain_tasks()` 120s 超时等待在途任务
- 信号量重置：`reset_task_state()` 清除 `--reload` 残留

**教训**：
- 轻量级异步任务用 `asyncio.create_task` 即可，不需要重量级任务队列
- 任务流复杂时再考虑 Temporal / Celery

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

## 19. 日志查看器时间差 8 小时（已修）

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

## 20. 日志查看器最新日志在最顶部（已修）

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

## 21. ⚠️ AI 常见错误

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
| 多个 useEffect 读写同一 state | 竞态导致奇偶交替 Bug | 合并"重置+初始化"到同一 effect |
| bat 中 `cmd /c "..."` 内嵌套双引号 | 引号解析错乱，进程无法启动 | 用临时 `.cmd` 文件替代（见 §37） |

## 22. 已知 TODO（AI 可以认领）

- [ ] ComfyUI 工作流执行器
- [ ] 视频生成（多 Handler 支持）
- [ ] 任务取消（cancel API 接 asyncio）
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

## 26. generate_video 方法签名与基类不匹配（已修）

**症状**：视频生成任务执行时抛 `TypeError`，参数不匹配。

**根因**：`agnes_handler.py` 的 `generate_video` 签名是 `(self, request: StandardGenerateRequest)`，但 `execute_task.py` 调用时传的是 `(model=..., prompt=..., params=...)` 关键字参数，与基类 `base.py` 定义的签名不一致。

**修复**（`backend/app/providers/agnes_handler.py`）：
```python
async def generate_video(
    self,
    model: str,
    prompt: str,
    params: dict,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: int = 120,
) -> list[str]:
    # 内部构建 StandardGenerateRequest
    request = StandardGenerateRequest(model=model, prompt=prompt, params=params)
    ...
```

**教训**：
- Handler 子类重写基类方法时，签名必须与基类完全一致
- 新增 Handler 时先用 `inspect.signature` 对比基类方法签名
- 基类方法签名变更时，必须 grep 所有子类实现并同步更新

## 27. Agnes API 兼容性踩坑

**症状**：调用 Agnes API 时返回 404、JSON 解析失败、或 `response_format: json_object` 报错。

**根因**（多个坑点）：

1. **必须 `/v1` 路径前缀**：Agnes API 兼容 OpenAI 协议，所有请求必须走 `/v1/chat/completions`，不带 `/v1` 会返回 404。
   ```python
   # 错误
   base_url = "https://api.agnes.ai/chat/completions"
   # 正确
   base_url = "https://api.agnes.ai/v1/chat/completions"
   ```

2. **不支持 `response_format: {"type": "json_object"}`**：Agnes API 不支持 OpenAI 的 JSON mode 参数，传了会报错或忽略。必须在 prompt 中要求 JSON 输出 + 后置解析。
   ```python
   # 错误：Agnes 不支持
   payload = {"response_format": {"type": "json_object"}}
   # 正确：在 prompt 中要求 JSON + 后置解析
   prompt = "请以 JSON 格式输出..."
   # 后置解析：提取 ```json ... ``` 或直接 json.loads
   ```

3. **JSON 输出可能被截断**：长剧本解析时 LLM 输出可能被 max_tokens 截断，导致 JSON 不完整无法解析。
   ```python
   # 防御性解析
   try:
       result = json.loads(text)
   except json.JSONDecodeError:
       # 尝试提取 ```json ... ``` 代码块
       # 尝试修复截断的 JSON（补全括号）
       # 最终降级为逐行正则提取
   ```

4. **流式响应解析**：Agnes 支持 SSE 流式输出，但 `stream=True` 时需要逐行解析 `data: {...}` 格式，不能直接 `json.loads(response)`。

**教训**：
- 接入新 Provider 时先测试基本连通性（/v1/models、简单 chat completion）
- 不要假设所有 OpenAI 兼容 API 都支持全部参数
- JSON 解析必须有降级策略（正则提取、截断修复）
- `script_parser.py` 已实现多层降级解析，可参考

## 28. FastAPI 路由顺序导致 405（已修）

**症状**：`POST /api/episodes/{episode_id}/shots/reorder` 返回 405 Method Not Allowed。

**根因**：FastAPI 按路由定义顺序匹配，`/episodes/{episode_id}/shots` 的 POST 路由先被匹配，`reorder` 路由永远不会被命中。

**修复**（`backend/app/api/shots.py`）：
- 将固定路径路由（如 `/reorder`）放在动态路径路由之前
- 同理：`/sync` 必须在 `/{id}` 之前

**教训**：
- FastAPI 路由顺序：固定路径 > 动态路径
- 新增路由时先检查同前缀的已有路由顺序
- 参见 §19 AI 常见错误表中的"路由顺序"条目

## 29. 分镜创建/删除后编号不连续

**症状**：插入新分镜后，shot_no 出现跳号或重复；删除分镜后编号不连续。

**根因**：创建/删除分镜时没有自动重排 shot_no，依赖前端传入的编号。

**修复**（`backend/app/api/shots.py`）：
```python
# 创建分镜后自动重排
shots = session.exec(select(Shot).where(...).order_by(Shot.sort_order, Shot.created_at)).all()
for idx, s in enumerate(shots):
    s.shot_no = idx + 1
session.commit()

# 删除分镜后同样自动重排
remaining = session.exec(select(Shot).where(...).order_by(Shot.sort_order, Shot.created_at)).all()
for idx, s in enumerate(remaining):
    s.shot_no = idx + 1
session.commit()
```

**教训**：
- shot_no 应由后端自动维护，不依赖前端传入
- 排序依据：sort_order 优先，created_at 兜底
- 前端显示用 `padStart(2, "0")` 格式化为 01/02/03

## 30. 双向同步顺序错误 + Episode 缺失（已修）

**症状**：本地删除角色/场景/道具/剧集目录后，点同步按钮，前端仍然显示这些实体。

**根因**（两个 bug）：
1. `bidirectional_sync()` 先执行 `sync_dirs_from_db`（DB→磁盘），会**重建被删除的目录**，然后 `sync_db_from_dirs` 检查时目录已存在，不会清理 DB 记录
2. `MODULE_DIR_MAP` 缺少 `Episode`，导致剧集不在同步范围内

**修复**：
- 调换 `bidirectional_sync` 执行顺序：先 `disk_to_db`（清理孤立记录），再 `db_to_disk`（补建目录）
- `MODULE_DIR_MAP` 添加 `Episode: "剧集"`
- `_compute_dirname` 添加 Episode 分支：`f"第{episode_no}集"`

---

## 31. 视频生成任务前端卡顿（已修）

**症状**：提交视频生成任务后，整个页面明显卡顿，任务执行期间（3-5 分钟）操作响应迟缓。

**根因**：
1. `task.progress` WS 推送触发 `invalidateQueries(["tasks"])` 全量刷新，叠加 5 秒轮询，每 2-3 秒就请求一次 `/api/tasks`（返回 100 条数据）。
2. `task.completed` / `task.failed` 同时 invalidate tasks/assets/shots/characters/scenes，最多 5 组并行请求。
3. `write_task_log` 每条都 `session.flush()` + WS 推送，视频任务期间 15-20 次调用加重 DB 与前端渲染压力。
4. `usePendingTasks` 2 秒轮询，分镜页挂载后频繁请求。

**修复**：
- `useWs.ts`：`task.progress` 改 `setQueryData` 精确更新单条任务；`completed/failed` 加 300ms 去抖合并刷新。
- `useApi.ts`：`useTasks` 活跃任务时轮询 5s → 15s；`usePendingTasks` 2s → 10s。
- `task_log_service.py`：`write_task_log` 默认 `push_ws=False`，删除 `_push_log_ws`，ERROR/WARNING 仍走 `WsLogHandler`。

**教训**：
- WS 推送不要直接触发全量列表刷新，优先局部更新缓存。
- 多个 `invalidateQueries` 合并 + 去抖，避免并发请求风暴。
- 高频日志写入与 WS 推送解耦，只保留真正需要实时展示的日志通道。

## 32. Prompt 缓存命中导致生图瞬间完成（已彻底移除缓存功能）

**症状**：用户点击生成图片，任务瞬间完成，结果与上次一模一样。**每次生图都一样**，即使没有修改提示词。

**根因**：Prompt 缓存机制导致相同 `model + prompt + params` 命中缓存，直接复制旧文件跳过 API 调用。AI 生图需要同一提示词多次抽卡才能得到满意结果，缓存完全不需要。

**修复**（彻底移除 Prompt 缓存功能）：
- 移除 `_compute_cache_key()` 函数
- 移除 `execute_task.py` 中缓存命中检查逻辑（整个 if 块）
- 移除 `generation.py` schema 中的 `force` 字段
- 移除 `generation_service.py` 中 `force`/`cache_key` 相关代码
- 移除 `GenerateDialog.tsx` 中的"使用缓存"复选框
- 数据库 `cache_key` 列保留（不影响，不再写入）

**教训**：
- **AI 生图场景下，Prompt 缓存是有害的**——用户需要同一提示词多次抽卡，缓存只会导致"每次都一样"
- 任何"优化"功能的默认值，都应该选择对用户最直观的行为
- 不需要的功能就应该彻底移除，而不是加开关——开关越多，AI 越容易"失忆"把开关拨错

## 33. 默认模型配置重启后丢失（已修）

**症状**：在设置页面修改默认模型配置后，重启后端配置恢复为默认值。

**根因**：`api_update_default_models` 只修改内存中的 Settings 对象，不持久化到 `config.yaml`，重启后从配置文件重新加载，修改丢失。

**修复**（`config.py` + `settings.py`）：
```python
def save_settings_to_yaml():
    """将当前运行时配置写入 config.yaml"""
    settings = get_settings()
    yaml_data = {
        # ... 其他配置 ...
        "default_models": {
            "default_image_model": settings.default_models.default_image_model,
            "default_video_model": settings.default_models.default_video_model,
            "default_text_model": settings.default_models.default_text_model,
        },
        "tasks": {
            # ... 含新增的 auto_retry 配置 ...
        },
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True)
```

- `api_update_default_models` 和 `api_update_tasks_config` 修改后均调用 `save_settings_to_yaml()`

**教训**：
- 运行时配置修改必须同时持久化到配置文件
- 配置 API 修改后必须验证重启后是否生效

## 34. 数据库锁死（SQLite WAL 残留）

**症状**：后端启动报 `sqlite3.OperationalError: database is locked`，或查询超时。

**根因**：
1. 异常退出时 WAL 文件未自动清理
2. 多个 session 同时写入 SQLite（SQLite 写入是串行的）
3. `execute_task.py` 中多个 `session_scope()` 嵌套或并发使用

**修复**（`execute_task.py`）：
- 合并 session_scope：从 ~10 个减少到 5 个（3 阶段：读取上下文+准备参数、API 调用、保存结果）
- Prompt 缓存检查与阶段 1 合并为同一 session
- 缓存复制用 `asyncio.to_thread` 避免阻塞事件循环

**预防**：
- 关闭后端进程后清理 WAL 文件（见 §14）
- 尽量减少 session_scope 的数量和并发
- 长事务拆分为短事务

## 35. URL 过期导致重试死循环（已修）

**症状**：API 返回的下载 URL 过期后（HTTP 403/410/404），自动重试仍尝试用过期 URL 下载，反复失败。

**根因**：自动重试机制复用 `_result_urls` 中的 URL，但未检测 URL 是否已过期。过期 URL 永远下载失败，导致重试次数耗尽。

**修复**（`execute_task.py`）：
```python
def _is_url_expired_error(err: Exception) -> bool:
    """检测 URL 过期错误（HTTP 403/410/404）"""
    err_str = str(err).lower()
    return any(code in err_str for code in ["403", "410", "404"])

def _clear_result_urls_if_expired(task_id, dl_err, url_str, asset_label):
    """URL 过期时清除 _result_urls，下次重试将重新调 API"""
    if not _is_url_expired_error(dl_err):
        return
    # 清除 _result_urls，下次重试走完整 API 流程
    with session_scope() as sess:
        t = sess.get(GenerationTask, task_id)
        if t and t.input_payload and "_result_urls" in t.input_payload:
            t.input_payload.pop("_result_urls", None)
            sess.add(t)
            sess.commit()
```

**教训**：
- 自动重试机制必须检测 URL 有效性，过期时清除缓存 URL
- HTTP 403/410/404 通常表示 URL 过期或资源不存在，应触发重新获取

## 36. useEffect 竞态导致弹窗模型选择交替为空（已修）

**症状**：点击生图/生视频按钮，第一次打开弹窗模型正常选中默认，第二次打开选项为空，第三次正常，第四次又空——奇偶交替。

**根因**：两个 `useEffect` 竞态条件：
```typescript
// Effect 1：open 变为 true 时重置 selectedModelKey 为 ""
useEffect(() => {
  if (open) setSelectedModelKey("");
}, [open]);

// Effect 2：selectedModelKey 为空时自动选默认模型
useEffect(() => {
  if (!open || selectedModelKey) return;  // ← 读到的是上一次渲染的旧值（非空）
  setSelectedModelKey(defaultKey);
}, [open, modelOptions, selectedModelKey]);
```

两个 effect 在同一渲染周期执行，Effect 2 读到的 `selectedModelKey` 是**上一次渲染的旧值**（非空），所以跳过了自动选择。但 Effect 1 的 `setSelectedModelKey("")` 已排入队列，下次渲染时 `selectedModelKey` 变成空，Effect 2 却不会再执行了。

**修复**（`GenerateDialog.tsx`）：合并为一个 effect，在 `open` 变为 `true` 时同时完成重置和自动选择：
```typescript
useEffect(() => {
  if (!open) return;
  // 重置表单
  setSelectedModelKey("");
  // 自动选择默认模型（同一 effect 内，state 更新批量处理）
  if (modelOptions.length > 0) {
    setSelectedModelKey(defaultKey);
  }
}, [open, defaultPrompt]);

// 补充 effect：providers 异步加载完成时补选
useEffect(() => {
  if (!open || modelOptions.length === 0 || selectedModelKey) return;
  setSelectedModelKey(defaultKey);
}, [open, modelOptions.length, requiredCapability, sysConfig]);
```

**教训**：
- **多个 useEffect 读写同一个 state 时，极易产生竞态条件**——一个 effect 重置 state，另一个 effect 依赖该 state 做判断，但两者在同一渲染周期执行时读到的是旧值
- 正确做法：把"重置 + 初始化"合并到同一个 effect 中，避免中间状态
- 或者用 `useRef` 跟踪"是否需要初始化"，绕过 state 闭包陷阱

---

## 37. start.bat 一键启动失败（已根治：改用 PowerShell + 英文输出）

**症状**：双击 `start.bat` 后，后端/前端 30s 超时报错"未就绪"，日志文件不存在或为空。或者报错 `'AI' 不是内部或外部命令`，或者中文全乱码。**经常性复现**。

**根因**（4 个坑叠加，每个都足以让 bat 失败）：

1. **`cmd /c` 引号嵌套**：`cmd /c "cd /d "%ROOT%backend" && ..."` 中外层双引号 + 内部双引号，cmd 引号解析器错乱，进程根本没启动
2. **`chcp 65001` 拆碎中文路径**：`chcp 65001` 让 cmd 用 UTF-8 解析命令行，但 cmd 的 UTF-8 实现有 bug，会把 `影序AI` 的字节拆错，`AI` 被当成独立命令执行，报错 `'AI' 不是内部或外部命令`
3. **PowerShell .ps1 文件 UTF-8 乱码**：Windows PowerShell（5.x）默认用系统编码（GBK）读取 .ps1 文件，即使文件是 UTF-8 保存的，中文输出仍然乱码。`[Console]::OutputEncoding = UTF8` 只影响输出，不影响文件读取
4. **bat 执行完窗口闪退**：成功/失败后没有 `pause`，窗口瞬间关闭，用户看不到任何信息

**修复**（彻底方案，4 个坑全部绕过）：

```bat
REM start.bat — 入口，不设 chcp，用 pushd+相对路径避免中文路径经过 cmd 命令行解析
@echo off
pushd "%~dp0"
start "AI Drama Studio" powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\restart.ps1"
popd
```

`scripts\restart.ps1` 负责（**全英文输出**，彻底避免编码问题）：
1. `Get-NetTCPConnection` + `Stop-Process -Force` 强制杀端口占用进程（含子进程树）
2. `Start-Process -PassThru` 启动后端/前端（无引号嵌套问题）
3. `Invoke-WebRequest` 健康检查（每次间隔 1s）
4. 启动失败自动 dump 日志末尾 30 行
5. 成功/失败都 `ReadKey` 等用户按键才关闭窗口

**教训**：
- **cmd bat 不适合做复杂的进程管理**：引号嵌套、中文编码、变量作用域都是坑
- **`chcp 65001` 在 bat 中是毒药**：会让 cmd 把中文路径的字节拆错，导致命令解析失败
- **Windows PowerShell .ps1 文件中的中文输出必然乱码**：5.x 默认用 GBK 读文件，无法根治。**脚本输出用英文是最可靠的方案**
- **bat 调 ps1 时用 `pushd + 相对路径`**：避免中文路径经过 cmd 命令行参数解析
- **bat 中用 `start "title" powershell -File ...`**：开新 PowerShell 窗口运行，cmd 窗口立即关闭，用户只看到 PowerShell 窗口
- **脚本末尾必须 pause/ReadKey**：否则窗口闪退，用户看不到结果

---

## 38. 视频任务中断后重试重新提交 API（已修：断点续传）

**症状**：视频生成任务在轮询阶段中断（服务重启/网络断开），重试时重新提交了一个全新的 API 任务，而不是复用已有的 `video_id` 继续轮询。导致：①浪费 API 额度；②之前已生成好的视频丢失；③用户等待时间翻倍。

**根因**：`_result_urls` 只在整个 `generate_video()` 返回后（提交+轮询全部完成）才保存到 DB。如果任务在轮询阶段中断，`video_id` 从未持久化，重试时只能重新提交。

**修复**（4 处改动）：

1. **`AgnesHandler.generate_video()`**：新增 `resume_video_id` 和 `on_submitted` 参数
   - `resume_video_id`：传入已有的 video_id，跳过提交直接轮询
   - `on_submitted`：提交成功后的异步回调，立即将 video_id 持久化到 DB

2. **`_execute_task_inner()`**：
   - 提交成功后通过 `on_submitted` 回调立即保存 `_video_task_id` 到 `input_payload`
   - 重试时检查 `_video_task_id`，传给 handler 的 `resume_video_id`
   - 下载完成后同时清除 `_result_urls` 和 `_video_task_id`

3. **`_handle_task_failure()` / `recover_orphan_tasks()`**：`_video_task_id` 也作为自动重试条件（API 已提交但轮询未完成）

4. **`_clear_result_urls_if_expired()`**：URL 过期时只清 `_result_urls`，保留 `_video_task_id` 以便重新轮询获取新 URL

5. **`retry_task()`**：切换 Provider 时清除 `_video_task_id` 和 `_result_urls`（旧 Provider 的 video_id 无效）

**断点续传流程**：
```
首次执行：提交 API → on_submitted 保存 _video_task_id → 轮询 → 保存 _result_urls → 下载 → 清除两者
轮询中断：_video_task_id 已在 DB，_result_urls 未保存
重试执行：检测到 _video_task_id → 传 resume_video_id → 跳过提交 → 直接轮询 → 下载
URL 过期：清除 _result_urls，保留 _video_task_id → 重试时重新轮询获取新 URL
切换 Provider：清除 _video_task_id + _result_urls → 完全重新提交
```

**教训**：
- **异步 API（提交+轮询模式）的断点续传，必须在提交成功后立即持久化任务 ID**，不能等轮询完成
- **`_result_urls` 和 `_video_task_id` 是两个不同阶段的数据**：前者是最终结果，后者是中间状态，需要分别管理
- **URL 过期 ≠ 任务过期**：视频 URL 可能过期，但 API 端的任务可能还在，可以通过 video_id 重新获取

---

## 39. Agnes API 超时 120 秒不够 4K 竖图（已修）

**症状**：角色图片生成（4K + 9:16 竖屏）失败，错误信息为 "Not Found"。

**根因**：`execute_task.py` 中 `generate_image()` 和 `generate_video()` 调用时未传 `timeout` 参数，使用了默认值 120 秒。4K 竖图（2944x5248）计算量大，Agnes API 需要 225 秒才能返回，超时后触发智能降级。

**修复**：

```python
# ❌ 错误：未传 timeout，默认 120 秒
image_urls = await handler.generate_image(model=model_name, prompt=prompt, params=params)

# ✅ 正确：传 handler 的 timeout 配置
image_urls = await handler.generate_image(
    model=model_name, prompt=prompt, params=params,
    timeout=getattr(handler, "_timeout", 120),
)
```

**教训**：
- **高分辨率图片生成耗时远超低分辨率**：4K 竖图需 200+ 秒，Provider 的 timeout 应设为 300 秒
- **调用 handler 方法时必须显式传 timeout**，不能依赖默认值

---

## 40. SenseNova base_url 重复 `/v1` 导致 404（已修）

**症状**：Agnes API 超时后智能降级到 SenseNova，但 SenseNova 返回 404 Not Found。

**根因**：SenseNova 的 `base_url` 是 `https://token.sensenova.cn/v1`，已包含 `/v1`。`agnes_handler.py` 的 `_translate_image()` 拼接 URL 时无条件追加 `/v1/images/generations`，导致最终 URL 变成 `https://token.sensenova.cn/v1/v1/images/generations`。

**修复**：

```python
# ❌ 错误：无条件追加 /v1
url = f"{self._base_url}/v1/images/generations"

# ✅ 正确：检查 base_url 是否已含 /v1
if self._base_url.endswith("/v1"):
    url = f"{self._base_url}/images/generations"
else:
    url = f"{self._base_url}/v1/images/generations"
```

**教训**：
- **不同 Provider 的 base_url 格式可能不同**：有的已含 `/v1`，有的没有
- **URL 拼接前必须检查路径前缀是否重复**

---

## 41. 智能降级标签匹配错误（已修）

**症状**：图片生成降级时选择了 LongCat（只有 `text_reasoning` 标签），LongCat 不支持图片生成，调用失败。

**根因**：`_find_fallback_handler()` 中标签未匹配到时取了第一个模型作为降级目标，没有检查该模型是否支持对应功能。

**修复**：

```python
# ❌ 错误：标签未匹配时取第一个模型
fallback_model = next((m for m in models if required_tag in (m.tags or [])), models[0])

# ✅ 正确：标签未匹配时跳过此 Provider
fallback_model = next((m for m in models if required_tag in (m.tags or [])), None)
if not fallback_model:
    continue  # 跳过不支持对应功能的 Provider
```

**教训**：
- **智能降级必须按功能标签匹配**，不能盲目取第一个模型
- **降级到不支持对应功能的 Provider 比不降级更糟**

---

## 42. 4K 图片超图床 10MB 限制（已修：自动压缩）

**症状**：4K 图片（5248x2944）PNG 文件约 11.3MB，上传闪电图床失败。

**根因**：闪电图床/聚合图床最大文件大小 10MB，4K PNG 超限。

**修复**：`image_hosting_service.py` 新增 `_compress_for_upload` 自动压缩功能：
1. 先尝试降低 JPEG 质量（85 → 75 → 65 → ... → 35）
2. 如果质量降到 35 仍超限，缩小到 1920px 宽后重试
3. 压缩后的临时文件上传后自动清理

**教训**：
- **4K 图片文件大小容易超过图床限制**，上传前必须检查并压缩
- **压缩后的图片作为视频参考图是可接受的**（视频 API 最大 1920px）

---

## 43. `generate_video()` 中 ratio 参数丢失（已修）

**症状**：视频生成时用户选了 ratio（如 9:16），但最终视频比例不对。

**根因**：`base.py` 的 `generate_image()` 有将 params 中非标准字段（如 ratio）收集到 `request.extra` 的逻辑，但 `agnes_handler.py` 的 `generate_video()` 直接用 `params.get("extra", {})` 构建 `StandardGenerateRequest`，没有这个收集逻辑。

**修复**（`agnes_handler.py`）：在 `generate_video()` 中也加入非标准字段收集逻辑（与 `base.py` 的 `generate_image()` 一致）：
```python
_standard_keys = {"size", "reference_images", "count", "negative_prompt", "extra", "model", "prompt"}
extra = dict(params.get("extra", {}))
for k, v in params.items():
    if k not in _standard_keys:
        extra[k] = v
```

**教训**：
- **`generate_image()` 和 `generate_video()` 的参数映射逻辑应保持一致**
- **新增参数映射时，必须检查两个方法是否都需要更新**

---

## 44. `datetime.utcnow()` 废弃 API 导致时区计算错误（已修）

**症状**：`_handle_task_failure` 中计算任务年龄时，`datetime.utcnow()` 返回 naive datetime，与 SQLite 读回的可能带 tzinfo 的 datetime 相减可能抛 `TypeError`。

**根因**：`datetime.utcnow()` 是 Python 已废弃 API，返回 naive datetime（无时区信息）。§13 已明确要求"统一用 `utcnow()`（带 timezone）"，但此处违反了自己的规则。

**修复**（`execute_task.py`）：
```python
# ❌ 错误：废弃 API，返回 naive datetime
created_naive = task.created_at.replace(tzinfo=None)
age_minutes = (datetime.utcnow() - created_naive).total_seconds() / 60

# ✅ 正确：统一用 aware datetime
created_aware = task.created_at.replace(tzinfo=timezone.utc) if task.created_at.tzinfo is None else task.created_at
age_minutes = (datetime.now(timezone.utc) - created_aware).total_seconds() / 60
```

**教训**：
- **全项目统一用 `datetime.now(timezone.utc)`，禁止 `datetime.utcnow()`**
- SQLite 读回的 datetime 可能丢失 tzinfo，需要显式替换

## 45. `_select_provider_model` 标签匹配失败仍返回第一个模型（已修）

**症状**：Provider 配置了多个模型但都没有对应标签时，盲目返回第一个模型，可能导致用图片模型生成视频或反之。

**根因**：`_select_provider_model` 在标签匹配不到时仍 `return models[0].model_name`，与 `_find_fallback_handler` 的修复（§41）不一致。

**修复**（`execute_task.py`）：标签匹配不到时返回 `None`，由调用方处理（`model_name` 为空时抛 `ValueError`）。

**教训**：
- **与 §41 同理：标签匹配不到时不盲目兜底**
- **两个函数的匹配逻辑应保持一致**

## 46. `_safe_mark_task_failed` 中 `write_task_log` 参数不一致（已修）

**症状**：`_safe_mark_task_failed` 中调用 `write_task_log(session, task_id, ...)` 多传了 `session` 作为第一个参数，导致 `session` 对象被当成 `task_id` 使用，日志写入可能静默失败。

**根因**：`write_task_log` 的签名第一个参数是 `task_id`（字符串），但调用时多传了 `session` 对象。`write_task_log` 内部使用缓冲模式不依赖 session，所以传 session 是多余的。

**修复**（`execute_task.py`）：移除多余的 `session` 参数。

**教训**：
- **调用函数前确认签名，不要想当然**
- **`write_task_log` 是缓冲模式，不需要 session**

## 47. `_is_url_expired_error` 误判导致清除有效 URL（已修）

**症状**：下载失败时错误信息中恰好包含 "403" 子串（如 "Error 4034: timeout"），被误判为 URL 过期，清除 `_result_urls`，下次重试重新调 API 浪费额度。

**根因**：`_is_url_expired_error` 用 `"403" in err_str` 做子串匹配，会误匹配包含 403 的任意字符串。

**修复**（`execute_task.py`）：使用正则词边界匹配 `\b40[34]\b`，确保只匹配完整的 HTTP 状态码。

**教训**：
- **HTTP 状态码检测必须用词边界匹配**，不能简单 `in` 检查
- **误判比漏判更危险**：误判会清除有效 URL 导致浪费 API 额度

## 48. `_auto_fill_entity` 内部 commit 破坏事务边界（已修）

**症状**：`_auto_fill_entity` 内部调用 `session.commit()`，会提交整个 session 的所有未提交变更，破坏外层事务边界。

**根因**：`_auto_fill_entity` 在 `_execute_task_inner` 的阶段 3（已有 `session_scope()`）中被调用，内部的 `session.commit()` 会提前提交所有变更。

**修复**（`execute_task.py`）：移除 `_auto_fill_entity` 内部的 `session.commit()`，由外层 `session_scope()` 统一提交。

**教训**：
- **子函数不应自行 commit，由调用方统一管理事务边界**
- **SQLite 事务管理要特别注意 commit 的位置**

## 49. SQL 拼接缺少白名单校验（已修）

**症状**：`_migrate_add_columns` 中使用 f-string 拼接 SQL，虽然当前值来自硬编码字典，但缺少防御性校验。

**修复**（`db.py`）：
1. 添加正则白名单校验 `_safe_name_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')`
2. 表名检查改用参数化查询 `name=:table_name`

**教训**：
- **即使当前硬编码安全，也应添加白名单校验作为防御性编程**
- **SQL 拼接优先用参数化查询**

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
