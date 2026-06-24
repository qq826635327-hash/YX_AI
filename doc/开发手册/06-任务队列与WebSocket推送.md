# 06 · 任务队列与 WebSocket 推送

> 任务从"用户点击生成"到"图片回填到卡片"全过程。

## 1. 任务生命周期

```
用户点击生成
   ↓
[前端] GenerateDialog
   ↓ POST /api/generate
[后端] api/generate.py
   ↓ 1. 校验参数（handler.validate_params）
   ↓ 2. 创建 GenerationTask 记录（status=pending, progress=0）
   ↓ 3. 调 _spawn_task(execute_task_async) 入队
   ↓
[后端] tasks/execute_task.py
   ↓ status: pending → running, progress: 0 → 5
   ↓ push_task_progress(5)
   ↓ ...
   ↓ status: running → succeeded, progress: 100
   ↓ push_task_completed(asset_id=...)
   ↓
[前端] useTaskWsSubscription
   ↓ 收到 task.completed
   ↓ invalidateQueries(["tasks"])
   ↓ invalidateQueries(["business", target_type, projectId])
   ↓ 卡片自动显示新图片
```

## 2. GenerationTask 模型（`models/task.py`）

```python
class GenerationTask(SQLModel, table=True):
    __tablename__ = "generation_tasks"

    id: str                       # UUID
    project_id: str
    target_type: str              # character / scene / prop / shot_first_frame / shot_last_frame / shot_video
    target_id: str
    provider_type: str            # "comfyui" | "api"
    provider_id: Optional[str]    # 指向 ApiProvider
    workflow_mapping_id: Optional[str]
    input_payload: Optional[dict]
    output_payload: Optional[dict]
    status: str                   # pending / queued / running / succeeded / failed / cancelled
    progress: int                 # 0-100
    retry_count: int
    error_message: Optional[str]
    output_asset_id: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
```

## 3. 状态枚举

| 状态 | 含义 |
| --- | --- |
| `pending` | 任务刚创建，未开始 |
| `queued` | 已入队（当前实现跳过此状态，直接 running） |
| `running` | 正在执行 |
| `succeeded` | 成功，output_asset_id 已设置 |
| `failed` | 失败，error_message 已设置 |
| `cancelled` | 用户取消（前端有 cancel 按钮但后端 cancel 实现 TODO） |

> ⚠️ 前端 TasksPage 的"已完成"过滤是 `succeeded`（不是 `completed`），改时注意。

## 4. TaskLog（`models/task_log.py`）

每个任务可以有任意多条日志：

```python
class TaskLog(SQLModel, table=True):
    __tablename__ = "task_logs"

    id: str
    task_id: str
    level: str        # DEBUG / INFO / WARNING / ERROR
    message: str
    data: Optional[str]  # JSON 字符串
    created_at: datetime
```

写入通过 `task_log_service.write_task_log(session, task_id, level, message, data=...)`。

**和后端 logging 的区别**：
- `logging`：全局根 logger，写到 stdout + logs/backend.log + WS（ERROR/WARNING）
- `write_task_log`：针对单个任务，写到 task_logs 表

**两者配合使用**：
- 全局 logger 用于开发调试 + 跨任务监控
- task_log 用于任务详情页展示"这个任务每一步干了啥"

## 5. WebSocket 推送（`ws/routes.py`）

### 任务事件

| 事件 | 触发时机 | data 字段 |
| --- | --- | --- |
| `task.created` | 用户提交生成 | task_id, project_id |
| `task.progress` | 进度变化（5%, 10%, 20%, 30%, 70%, 85%, 90%……） | task_id, progress, message |
| `task.completed` | 任务成功 | task_id, asset_id, message |
| `task.failed` | 任务失败 | task_id, error |

### 剧本解析事件

| 事件 | 触发时机 | data 字段 |
| --- | --- | --- |
| `script.parsing` | 解析中 | project_id, stage |
| `script.completed` | 解析成功 | project_id |
| `script.failed` | 解析失败 | project_id, error |

### 日志事件

详见 `07-日志监控开发指南.md`。

| 事件 | 触发时机 | data 字段 |
| --- | --- | --- |
| `log` | 后端 ERROR/WARNING 日志 | level, logger, message, module, lineno |
| `log.cleared` | 服务端清空 | — |

## 6. 前端 WS 订阅

### `useTaskWsSubscription`（`hooks/useWs.ts`）

```typescript
useEffect(() => {
  const unsubscribe = tasksWs.on((msg) => {
    switch (msg.type) {
      case "task.created":
      case "task.progress":
      case "task.completed":
      case "task.failed":
        qc.invalidateQueries({ queryKey: ["tasks"] });
        break;
    }
  });
  return unsubscribe;
}, [qc]);
```

**挂载点**：`MainLayout.WsSubscriptions()`（应用启动时执行一次）。

### `useScriptWsSubscription(projectId)`

订阅剧本解析进度，**仅处理当前项目**的消息：

```typescript
if (data.project_id && data.project_id !== projectId) return;
```

## 7. 异步任务调度

### 当前实现：asyncio.Semaphore + create_task

```python
# api/generate.py
_MAX_CONCURRENT_TASKS = 4
_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_TASKS)
_inflight_tasks: set[asyncio.Task] = set()

def _spawn_task(coro):
    """启动后台异步任务，保存引用防 GC。"""
    task = asyncio.create_task(coro)
    _inflight_tasks.add(task)
    task.add_done_callback(_inflight_tasks.discard)

# api/generate.py:api_generate
async def api_generate(payload, session):
    task = create_task(session, payload)
    update_task_status(session, task.id, status="running", progress=5)
    _spawn_task(execute_task_async(task.id))
    _notify_task_created(task.id, task.project_id)
    return ok({"task_id": task.id, "status": "running"})
```

**关键设计**：
- `asyncio.Semaphore(4)` 限制最大并发任务数
- `asyncio.create_task()` 在主事件循环中启动，不阻塞 HTTP 响应
- 任务引用保存在 `_inflight_tasks` 集合中，完成后自动移除
- `execute_task_async` 是 `async def`，可以直接 `await` WS 推送函数

### 优雅关闭

```python
# main.py lifespan
async def drain_tasks(timeout: float = 120.0):
    """等待在途任务完成，超时后保留 running 状态。"""
    if not _inflight_tasks:
        return
    done, pending = await asyncio.wait(_inflight_tasks, timeout=timeout)
    for t in pending:
        t.cancel()
```

### 信号量重置

```python
# main.py lifespan startup
def reset_task_state():
    """清除 --reload 残留的 Semaphore 计数和孤儿任务。"""
    global _semaphore
    _semaphore = asyncio.Semaphore(_MAX_CONCURRENT_TASKS)
    # 标记残留 running 任务为 failed
```

## 7.1 前端智能轮询

`useTasks` hook 采用智能轮询策略，配合 WS 推送实现即时刷新：

```typescript
refetchInterval: (query) => {
  const items = query.state.data?.items || [];
  const hasActive = items.some(
    (t) => t.status === "pending" || t.status === "running" || t.status === "queued"
  );
  return hasActive ? 5000 : 30000;  // 有活跃任务 5s，否则 30s
},
```

WS 推送（`task.progress`/`task.completed`/`task.failed`）会 `invalidateQueries`，触发即时刷新。

## 8. 取消任务

**当前未实现**。前端"取消"按钮触发的 `cancel` API 还没接 asyncio。

TODO：

```python
# 取消正在运行的 asyncio 任务
task = _find_inflight_task(task_id)
if task:
    task.cancel()

# 标记状态
update_task_status(session, task_id, status="cancelled")
push_task_cancelled(task_id)
```

## 9. 任务详情页（前端）

- 路由：`/tasks`（任务中心，按状态过滤）
- 任务列表来自 `["tasks"]` query
- 左右布局：左侧任务列表 + 右侧详情面板（含 TaskLog 时间线）
- Sidebar 按状态过滤：全部任务 / 进行中 / 已完成 / 失败 / 已取消

## 10. 故障排查

| 现象 | 排查 |
| --- | --- |
| 任务卡在 pending | 后端未正常启动；或 execute_task 抛了未捕获异常 |
| 任务卡在 running | execute_task 内部 await 某个 IO 永久阻塞；看 `GET /api/logs?keyword=<task_id>` |
| 任务 failed 但消息不明确 | 看 `TaskLog.data` 字段（execute_task 会把 traceback 前 500 字符写进去） |
| WS 收不到推送 | 看 `logs/backend.log` 是否有 `WsLogHandler` 异常；前端打开 LogViewer 看是否有 WS 断开 |
| 进度不更新 | execute_task 调 `push_task_progress` 时事件循环死了（重启后端） |
