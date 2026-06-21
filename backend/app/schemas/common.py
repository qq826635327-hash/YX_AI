"""统一响应模型与分页工具。"""

from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """错误响应。"""

    error: str = "error"
    message: str
    details: Optional[Any] = None


class DataResponse(BaseModel, Generic[T]):
    """成功响应（带数据）。"""

    data: T
    message: Optional[str] = None


class PaginatedData(BaseModel, Generic[T]):
    """分页数据。"""

    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应。"""

    data: PaginatedData[T]
    message: Optional[str] = None


class PaginationParams(BaseModel):
    """分页查询参数。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def ok(data: Any, message: Optional[str] = None) -> dict:
    """构造成功响应字典。"""
    resp = {"data": data}
    if message:
        resp["message"] = message
    return resp


def err(message: str, error: str = "error", details: Optional[Any] = None) -> dict:
    """构造错误响应字典。"""
    resp = {"error": error, "message": message}
    if details is not None:
        resp["details"] = details
    return resp


def paginate(items: List[Any], total: int, page: int, page_size: int) -> dict:
    """构造分页响应字典。"""
    return {
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    }
