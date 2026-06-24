# AI Drama Studio - Agents
> **优先级**：最高。违反核心规则 = Bug。
> **版本**：v6.0 | 2026-06-22

---

## ⚡ 核心规则（7 条，不可违反）

1. **改代码前必须先读文件** — 禁止直接 Edit/Write 没读过的文件
2. **改完必须跑检查** — 后端：py_compile + import 验证；前端：tsc + build
3. **改完必须重启前后端并验证健康检查** — 禁止假设 `--reload` 自动生效，进程可能已崩溃
4. **必须更新 `doc/记忆文件/任务-YYYY-MM-DD.md`** — 任务结束即写入，不要等
5. **不确定就问，禁止瞎猜** — 需求歧义 / 改动未提及文件 / 安装新依赖 / 测试失败超 3 轮
6. **PowerShell 禁止用 `&&`** — 用分号 `;` 或分多条执行
7. **禁止自动 git commit/push** — 只有用户明确要求时才执行

---

## 📋 每轮必做流程

```
接收任务
  → 读 D:\影序AI\doc\开发手册文件夹下，08-常见Bug与注意事项，CHANGELOG
  → 用 Read 读要改的文件
  → 超 5 步用 TodoWrite 拆分（必须包含验证步骤）
  → 编写代码（一次只改一个关注点）
  → 跑检查（py_compile / tsc / build）
  → 重启前后端 + 健康检查
  → 更新 任务-日期.md
  → 报告结果
```

### TodoWrite 验证步骤模板

每个代码修改任务的 todo 必须包含：

```
[ ] 修改代码
[ ] 后端检查（py_compile + import 验证）
[ ] 前端检查（tsc + build）
[ ] 重启后端 + 健康检查
[ ] 重启前端 + 验证
[ ] 更新 任务-日期.md
```

---

## 🏗️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite 5 + TypeScript 5 + Tailwind CSS + TanStack Query + shadcn/ui |
| 后端 | Python 3.11+ + FastAPI + SQLModel + SQLite |
| 任务队列 | asyncio.Semaphore + create_task |
| 通信 | REST API + WebSocket |
| 运行环境 | Windows PowerShell |
| 包管理 | 前端 npm，后端 Python venv |

---

## 📝 记忆文件格式（精简版）

每个任务最多 5 行，禁止大段重复：

```markdown
## 任务 N：<简短标题>

### 目标
一句话

### 结果
一句话

### 修改文件
- 文件列表

### 状态
已完成 / 待用户验证
```

---

## 🔧 快速自测命令

```powershell
# 后端语法检查
cd D:\影序AI\backend; .venv\Scripts\python.exe -c "import py_compile; py_compile.compile('app/文件.py', doraise=True)"

# 后端 import 验证
cd D:\影序AI\backend; .venv\Scripts\python.exe -c "from app.main import app; print('Import OK')"

# 前端类型检查 + build
cd D:\影序AI\frontend; npx tsc --noEmit; npm run build

# 健康检查
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read().decode())"

# 前端端口检查
netstat -ano | findstr ":5173.*LISTENING"
```

---

## 📖 详细参考

以下内容已移至 `doc/开发手册/09-Agents详细参考.md`，需要时查阅：

- 编码规范（后端 / 前端）
- 文档体系与写入权限
- 上下文管理规则
- Windows / PowerShell 执行约束
- 前端调试与 HMR
- 自测通过标准
- 依赖与安装规则
- Git 同步约定
- 回滚策略
- 完整禁止事项清单
