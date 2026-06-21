"""AI Drama Studio 后端应用入口。"""

from __future__ import annotations

import base64
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import clear_settings_cache, get_settings, validate_security
from app.db import check_db, init_db, reset_engine
from app.providers import get_handler_class, list_registered  # 触发 Handler 注册  # noqa: F401
from app.ws.log_handler import set_ws_manager, ws_log_handler
from app.ws.routes import ws_router

# 配置日志（同时输出到 stdout、文件和 WebSocket）
def _setup_logging():
    """初始化日志处理器，确保日志同时输出到控制台、文件和 WebSocket。"""
    from app.core.config import get_settings

    settings = get_settings()
    log_dir = Path(settings.app.logs_dir) if hasattr(settings.app, "logs_dir") else Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"

    # 根 logger 重设
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # 清空已有 handler 避免重复输出
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # 文件输出（追加模式，自动创建）
    try:
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8", mode="a")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        # 写一条启动标记
        root.info(f"=== 日志会话开始，日志文件: {log_file} ===")
    except Exception as e:
        # 文件日志失败不影响控制台
        print(f"无法初始化文件日志 ({log_file}): {e}", flush=True)

    # WebSocket 实时日志推送（ERROR/WARNING）
    try:
        ws_log_handler.setFormatter(formatter)
        root.addHandler(ws_log_handler)
    except Exception as e:
        print(f"无法初始化 WebSocket 日志处理器: {e}", flush=True)

    # 降低 uvicorn 默认 logger 的级别
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger(__name__)

# 调试：验证 Provider 注册（必须在 basicConfig 之后）
logger.info(f"Provider Handler 注册表: {list_registered()}")


# ============================================================
# 生命周期管理
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动与关闭钩子。"""
    # 重启时清空缓存和旧引擎（防止 Windows 下进程未完全退出导致旧状态残留）
    clear_settings_cache()
    reset_engine()

    # 把主事件循环注入 WS LogHandler（用于从其他线程广播）
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        ws_log_handler.set_loop(loop)
        set_ws_manager(ws_router.manager if hasattr(ws_router, "manager") else None)
    except RuntimeError as e:
        logger.warning(f"WS LogHandler 循环注入失败: {e}")
    # 兜底：上面的方式拿不到 manager 时，从 routes 模块取
    try:
        from app.ws.routes import manager as _ws_manager
        set_ws_manager(_ws_manager)
    except Exception as e:
        logger.warning(f"WS manager 兜底设置失败: {e}")

    # 启动时初始化数据库
    init_db()
    settings = get_settings()

    # 安全校验
    validate_security(settings)

    # 恢复被中断的任务（uvicorn 重启 / 崩溃导致 running 状态卡住的任务）
    from app.services.generation_service import recover_orphan_tasks
    recover_orphan_tasks()

    logger.info(f"数据库已初始化: {settings.database.url}")
    logger.info(f"项目根目录: {settings.projects_root_abs}")
    logger.info(f"ComfyUI: {'已启用' if settings.comfyui.enabled else '未启用'}")
    logger.info(f"LLM 解析: {'已启用' if settings.llm.enabled else '未启用'}")
    if settings.security.is_default_key:
        logger.warning("⚠️ 使用默认开发密钥，请勿用于生产环境！")
    yield
    logger.info("服务已关闭")


# ============================================================
# Basic Auth 中间件
# ============================================================

class CacheControlMiddleware:
    """给所有 API 响应加 Cache-Control 头，防止浏览器缓存 JSON 数据。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # 只给 API 路径加 no-cache；静态文件和 docs 允许缓存
        if not path.startswith("/api"):
            await self.app(scope, receive, send)
            return

        # 包装 send，在响应返回前加头
        response_headers = []

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # 加 Cache-Control: no-cache
                headers.append(
                    (b"cache-control", b"no-cache, no-store, must-revalidate")
                )
                headers.append((b"pragma", b"no-cache"))
                headers.append((b"expires", b"0"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BasicAuthMiddleware:
    """HTTP Basic Auth 中间件（可选）。"""

    def __init__(self, app, username: str, password: str):
        self.app = app
        self.username = username
        self.password = password

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http",):
            await self.app(scope, receive, send)
            return

        # 跳过健康检查、WebSocket、docs 路径
        path = scope.get("path", "")
        if path.startswith(("/api/health", "/ws/", "/api/ws/", "/docs", "/redoc", "/openapi.json", "/assets")):
            await self.app(scope, receive, send)
            return

        # 检查 Authorization 头
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="replace")

        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, password = decoded.split(":", 1)
                if username == self.username and password == self.password:
                    await self.app(scope, receive, send)
                    return
            except Exception:
                pass

        # 认证失败
        response = JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "需要认证"},
            headers={"WWW-Authenticate": 'Basic realm="AI Drama Studio"'},
        )
        await response(scope, receive, send)


# ============================================================
# 应用创建
# ============================================================

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        description="面向 AI 剧集/短片生产的 Web 工作台后端",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Cache-Control：防止浏览器缓存 API 响应（必须放在最外层）
    app.add_middleware(CacheControlMiddleware)

    # Basic Auth 鉴权（按配置启用）
    if settings.security.basic_auth_enabled:
        logger.info("Basic Auth 鉴权已启用")
        app.add_middleware(
            BasicAuthMiddleware,
            username=settings.security.basic_auth_user,
            password=settings.security.basic_auth_password,
        )

    # CORS —— 后添加，使其成为最外层（确保所有响应包含 CORS 头，包括 401）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API 路由
    app.include_router(api_router)

    # WebSocket 路由
    app.include_router(ws_router)

    # 健康检查
    @app.get("/api/health", tags=["system"])
    async def health():
        db_status = check_db()
        return {
            "status": "ok",
            "app": settings.app.name,
            "version": settings.app.version,
            "database": db_status,
            "comfyui_enabled": settings.comfyui.enabled,
            "llm_enabled": settings.llm.enabled,
        }

    # 托管前端构建产物（生产模式）
    frontend_dist = Path(settings.app.frontend_dist)
    if not frontend_dist.is_absolute():
        frontend_dist = settings.backend_root / frontend_dist

    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        # 静态资源
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # SPA fallback：所有非 API 路由返回 index.html
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            # 排除 API 和 WebSocket 路径
            if full_path.startswith(("api/", "docs", "redoc", "ws/")):
                return JSONResponse({"error": "not_found", "message": "资源不存在"}, status_code=404)

            file_path = frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(frontend_dist / "index.html"))

        logger.info(f"前端构建产物已挂载: {frontend_dist}")
    else:
        logger.info(f"前端构建产物未找到（开发模式）: {frontend_dist}")

    return app


app = create_app()


if __name__ == "__main__":
    import sys

    import uvicorn

    settings = get_settings()

    # Windows 下 uvicorn --reload 文件检测不可靠，默认关闭。
    # 开发时建议手动 Ctrl+C 杀进程后重开，或使用 nodemon 等外部工具。
    use_reload = "--reload" in sys.argv
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=use_reload,
    )
