"""Provider Handler 注册表 — 按 provider_kind 查找对应的 Handler。"""

from __future__ import annotations

from typing import Type

from app.providers.base import ProviderHandler


# 注册表：{ provider_kind: HandlerClass }
_REGISTRY: dict[str, Type[ProviderHandler]] = {}


def register(handler_cls: Type[ProviderHandler]) -> Type[ProviderHandler]:
    """注册一个 Provider Handler（装饰器用法）。"""
    if not handler_cls.PROVIDER_KIND:
        raise ValueError(f"Handler {handler_cls.__name__} 未设置 PROVIDER_KIND")
    _REGISTRY[handler_cls.PROVIDER_KIND] = handler_cls
    return handler_cls


def register_alias(kind: str, handler_cls: Type[ProviderHandler]) -> None:
    """为已注册的 Handler 添加别名（用于兼容旧 provider_kind）。"""
    if not kind:
        raise ValueError("别名不能为空")
    _REGISTRY[kind] = handler_cls


def get_handler_class(provider_kind: str) -> Type[ProviderHandler] | None:
    """根据 provider_kind 获取 Handler 类（不实例化）。"""
    return _REGISTRY.get(provider_kind)


def get_handler(provider_kind: str, **kwargs) -> ProviderHandler | None:
    """根据 provider_kind 实例化 Handler（可选传参给构造函数）。"""
    cls = _REGISTRY.get(provider_kind)
    if not cls:
        return None
    return cls(**kwargs)


def list_registered() -> dict[str, str]:
    """列出所有已注册的 Handler（用于调试）。"""
    return {kind: cls.__name__ for kind, cls in _REGISTRY.items()}
