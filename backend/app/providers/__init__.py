"""Provider 适配器包 — 自动导入并注册所有 Handler。"""

from __future__ import annotations

# 导入注册表
from app.providers.registry import get_handler, get_handler_class, list_registered, register

# 自动导入所有 Handler（触发装饰器注册）
# 注意：新增 Handler 时，需要在这里加上 import
from app.providers.agnes_handler import AgnesHandler  # noqa: F401
from app.providers.registry import register_alias

# 兼容旧数据：历史上 AgnesHandler 被注册为 openai
register_alias("openai", AgnesHandler)

# （后续新增 Handler 时，在这里加一行 import）
# from app.providers.sensenova_handler import SenseNovaHandler  # noqa: F401


__all__ = [
    "register",
    "get_handler",
    "get_handler_class",
    "list_registered",
    "AgnesHandler",
]

# 调试：打印已注册的 Handler
import logging
_logger = logging.getLogger(__name__)
_logger.info(f"[providers] 已注册 Handler: {list_registered()}")
