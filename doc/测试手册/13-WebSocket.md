# WebSocket 测试用例

> 本文件包含 WebSocket 相关的所有测试用例，对应原文 §4。

---

## 4. WebSocket 测试用例

### 4.1 连接管理

| 编号 | 名称 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|------|------|----------|------|----------|--------|
| TC-WS-CONN-001 | 连接 /ws/tasks | 服务运行中 | 建立 WebSocket 连接 | 连接成功，收到欢迎消息 | P0 |
| TC-WS-CONN-002 | 连接 /ws/script | 服务运行中 | 建立 WebSocket 连接 | 连接成功 | P0 |
| TC-WS-CONN-003 | 连接 /ws/logs | 服务运行中 | 建立 WebSocket 连接 | 连接成功，开始接收日志 | P0 |
| TC-WS-CONN-004 | 正常断开 | 已连接 | 客户端主动关闭 | 连接正常关闭，服务端清理资源 | P0 |
| TC-WS-CONN-005 | 异常断开 | 已连接 | 强制断开（网络中断） | 服务端检测到断开并清理 | P1 |
| TC-WS-CONN-006 | 无效路径 | 服务运行中 | 连接 /ws/invalid | 连接被拒绝 (404) | P1 |

```python
class TestWebSocketConnection:
    """WebSocket 连接测试"""

    @pytest.mark.asyncio
    async def test_tc_ws_conn_001_connect_tasks(self, client: AsyncClient):
        """TC-WS-CONN-001: 连接任务 WebSocket"""
        from httpx import AsyncClient
        async with client.stream("GET", "/ws/tasks") as ws:
            # 或使用 websockets 库
            pass

    @pytest.mark.asyncio
    async def test_tc_ws_conn_001_with_websockets(self):
        """TC-WS-CONN-001: 使用 websockets 库测试"""
        import websockets
        async with websockets.connect(
            "ws://localhost:8000/ws/tasks"
        ) as ws:
            # 验证连接成功
            msg = await ws.recv()
            assert msg is not None
```

### 4.2 消息收发

| 编号 | 名称 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|------|------|----------|------|----------|--------|
| TC-WS-MSG-001 | 任务进度推送 | 已连接 /ws/tasks | 触发生成任务 | 收到进度更新消息 | P0 |
| TC-WS-MSG-002 | 任务状态变更 | 已连接 /ws/tasks | 任务状态从 pending → running → succeeded | 依次收到状态变更通知 | P0 |
| TC-WS-MSG-003 | 剧本解析推送 | 已连接 /ws/script | 触发剧本解析 | 收到解析进度消息 | P0 |
| TC-WS-MSG-004 | 日志推送 | 已连接 /ws/logs | 系统产生日志 | 实时收到日志消息 | P1 |
| TC-WS-MSG-005 | 消息格式验证 | 已连接 | 接收任意消息 | JSON 格式正确，含 type/data 字段 | P0 |
| TC-WS-MSG-006 | 客户端发送消息 | 已连接 | 发送 ping 消息 | 收到 pong 响应 | P1 |

```python
class TestWebSocketMessages:
    """WebSocket 消息收发测试"""

    @pytest.mark.asyncio
    async def test_tc_ws_msg_001_task_progress(self):
        """TC-WS-MSG-001: 任务进度推送"""
        import websockets
        import json
        async with websockets.connect(
            "ws://localhost:8000/ws/tasks"
        ) as ws:
            # 触发生成任务（通过 HTTP API）
            # ...
            # 接收进度消息
            msg = json.loads(await ws.recv())
            assert "type" in msg
            assert msg["type"] == "task_progress"
            assert "data" in msg
            assert "progress" in msg["data"]

    @pytest.mark.asyncio
    async def test_tc_ws_msg_005_format_validation(self):
        """TC-WS-MSG-005: 消息格式验证"""
        import websockets
        import json
        async with websockets.connect(
            "ws://localhost:8000/ws/tasks"
        ) as ws:
            msg = json.loads(await ws.recv())
            # 验证消息结构
            assert isinstance(msg, dict)
            assert "type" in msg
            assert isinstance(msg["type"], str)
```

### 4.3 多客户端

| 编号 | 名称 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|------|------|----------|------|----------|--------|
| TC-WS-MULTI-001 | 多客户端广播 | 3个客户端连接 /ws/tasks | 触发任务 | 所有客户端收到相同消息 | P0 |
| TC-WS-MULTI-002 | 互不干扰 | 2个客户端分别连接不同WS | 各自收发消息 | 互不影响 | P1 |
| TC-WS-MULTI-003 | 客户端退出广播 | 3个客户端，1个退出 | 触发任务 | 剩余2个收到消息，退出的不收到 | P1 |
| TC-WS-MULTI-004 | 大量客户端 | 50个客户端连接 | 触发任务 | 所有客户端及时收到消息 | P2 |

```python
class TestWebSocketMultiClient:
    """WebSocket 多客户端测试"""

    @pytest.mark.asyncio
    async def test_tc_ws_multi_001_broadcast(self):
        """TC-WS-MULTI-001: 多客户端广播"""
        import websockets
        import asyncio
        clients = await asyncio.gather(*[
            websockets.connect("ws://localhost:8000/ws/tasks")
            for _ in range(3)
        ])
        try:
            # 触发生成任务
            # ...
            # 验证所有客户端收到消息
            messages = await asyncio.gather(*[
                ws.recv() for ws in clients
            ])
            assert len(set(messages)) == 1  # 所有消息相同
        finally:
            for ws in clients:
                await ws.close()
```

### 4.4 心跳与重连

| 编号 | 名称 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|------|------|----------|------|----------|--------|
| TC-WS-HB-001 | 心跳保活 | 已连接 | 等待心跳间隔 | 收到 ping/pong | P1 |
| TC-WS-HB-002 | 心跳超时断开 | 已连接 | 阻止心跳响应 | 超时时连接断开 | P2 |
| TC-WS-HB-003 | 断线重连 | 连接已断开 | 重新建立连接 | 连接成功，恢复接收消息 | P1 |
| TC-WS-HB-004 | 重连后消息连续性 | 重连后 | 检查消息序列 | 不丢失关键消息 | P2 |
