"""图床配置 API 路由。"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import decrypt_secret, encrypt_secret, mask_secret
from app.db import get_session
from app.models.image_hosting import ImageHostingProvider
from app.schemas.common import ok

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config/image-hosting", tags=["config"])


# ── Request/Response schemas ──

class ImageHostingCreate(BaseModel):
    name: str
    provider_type: str  # smms / superbed / boltp / github / custom
    api_url: str = ""
    token: str = ""
    extra_config: dict | None = None
    max_file_size: int = 10485760
    is_default: bool = False
    enabled: bool = True
    description: str | None = None


class ImageHostingUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    api_url: str | None = None
    token: str | None = None
    extra_config: dict | None = None
    max_file_size: int | None = None
    is_default: bool | None = None
    enabled: bool | None = None
    description: str | None = None


# 预设类型的默认 API URL
_PRESET_API_URLS = {
    "smms": "https://sm.ms/api/v2/upload",
    "superbed": "https://api.superbed.cc/upload",
    "boltp": "https://www.boltp.com/api/v2/upload",
    "github": "https://api.github.com/repos/{owner}/{repo}/contents/{path}",
}


def _provider_to_view(p: ImageHostingProvider) -> dict:
    """将 ImageHostingProvider 转为前端展示的 dict（脱敏）。"""
    token_decrypted = ""
    if p.token_encrypted:
        try:
            token_decrypted = decrypt_secret(p.token_encrypted)
        except Exception:
            token_decrypted = "[解密失败]"
    return {
        "id": p.id,
        "name": p.name,
        "provider_type": p.provider_type,
        "api_url": p.api_url,
        "token_masked": mask_secret(token_decrypted),
        "has_token": bool(token_decrypted),
        "extra_config": p.extra_config,
        "max_file_size": p.max_file_size,
        "is_default": p.is_default,
        "enabled": p.enabled,
        "description": p.description,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("")
async def api_list_image_hosting(session: Session = Depends(get_session)):
    """图床列表（脱敏）。"""
    statement = select(ImageHostingProvider).order_by(ImageHostingProvider.created_at.desc())
    items = session.exec(statement).all()
    return ok([_provider_to_view(p) for p in items])


@router.post("")
async def api_create_image_hosting(
    payload: ImageHostingCreate,
    session: Session = Depends(get_session),
):
    """新增图床配置。"""
    # 检查名称唯一性
    existing = session.exec(
        select(ImageHostingProvider).where(ImageHostingProvider.name == payload.name)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail={"error": "duplicate", "message": f"图床名称「{payload.name}」已存在"})

    # 预设类型自动填充 api_url
    api_url = payload.api_url
    if not api_url and payload.provider_type in _PRESET_API_URLS:
        api_url = _PRESET_API_URLS[payload.provider_type]

    # 如果设为默认，先取消其他默认
    if payload.is_default:
        _clear_other_defaults(session)

    provider = ImageHostingProvider(
        name=payload.name,
        provider_type=payload.provider_type,
        api_url=api_url,
        token_encrypted=encrypt_secret(payload.token) if payload.token else "",
        extra_config=payload.extra_config,
        max_file_size=payload.max_file_size,
        is_default=payload.is_default,
        enabled=payload.enabled,
        description=payload.description,
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return ok(_provider_to_view(provider), message="图床配置已创建")


@router.get("/{provider_id}")
async def api_get_image_hosting(provider_id: str, session: Session = Depends(get_session)):
    provider = session.get(ImageHostingProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "图床配置不存在"})
    return ok(_provider_to_view(provider))


@router.patch("/{provider_id}")
async def api_update_image_hosting(
    provider_id: str,
    payload: ImageHostingUpdate,
    session: Session = Depends(get_session),
):
    provider = session.get(ImageHostingProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "图床配置不存在"})

    # 检查名称唯一性
    if payload.name and payload.name != provider.name:
        existing = session.exec(
            select(ImageHostingProvider).where(ImageHostingProvider.name == payload.name)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail={"error": "duplicate", "message": f"图床名称「{payload.name}」已存在"})

    # 如果设为默认，先取消其他默认
    if payload.is_default and not provider.is_default:
        _clear_other_defaults(session)

    # 更新字段
    if payload.name is not None:
        provider.name = payload.name
    if payload.provider_type is not None:
        provider.provider_type = payload.provider_type
        # 预设类型自动填充 api_url（如果当前为空或是预设 URL）
        if not provider.api_url or provider.api_url in _PRESET_API_URLS.values():
            provider.api_url = _PRESET_API_URLS.get(payload.provider_type, provider.api_url)
    if payload.api_url is not None:
        provider.api_url = payload.api_url
    if payload.token is not None:
        provider.token_encrypted = encrypt_secret(payload.token) if payload.token else ""
    if payload.extra_config is not None:
        provider.extra_config = payload.extra_config
    if payload.max_file_size is not None:
        provider.max_file_size = payload.max_file_size
    if payload.is_default is not None:
        provider.is_default = payload.is_default
    if payload.enabled is not None:
        provider.enabled = payload.enabled
    if payload.description is not None:
        provider.description = payload.description

    session.add(provider)
    session.commit()
    session.refresh(provider)
    return ok(_provider_to_view(provider), message="图床配置已更新")


@router.delete("/{provider_id}")
async def api_delete_image_hosting(provider_id: str, session: Session = Depends(get_session)):
    provider = session.get(ImageHostingProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "图床配置不存在"})
    session.delete(provider)
    session.commit()
    return ok(None, message="图床配置已删除")


@router.post("/{provider_id}/test")
async def api_test_image_hosting(
    provider_id: str,
    session: Session = Depends(get_session),
):
    """测试图床上传：上传一张 1x1 透明 PNG 测试图。"""
    provider = session.get(ImageHostingProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "图床配置不存在"})

    token = ""
    if provider.token_encrypted:
        try:
            token = decrypt_secret(provider.token_encrypted)
        except Exception:
            return ok({"success": False, "message": "Token 解密失败，请重新配置图床密钥"})
    if not token and provider.provider_type != "custom":
        return ok({"success": False, "message": "Token 未配置"})

    # 1x1 透明 PNG（67 字节）
    import base64
    import tempfile
    test_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(base64.b64decode(test_png_b64))
    tmp.close()

    try:
        from app.services.image_hosting_service import upload_to_provider
        url = await upload_to_provider(
            provider_type=provider.provider_type,
            api_url=provider.api_url,
            token=token,
            file_path=tmp.name,
            extra_config=provider.extra_config,
        )
        return ok({"success": True, "message": "上传测试成功", "url": url})
    except Exception as e:
        return ok({"success": False, "message": f"上传测试失败: {e}"})
    finally:
        from pathlib import Path
        Path(tmp.name).unlink(missing_ok=True)


@router.post("/{provider_id}/set-default")
async def api_set_default_image_hosting(
    provider_id: str,
    session: Session = Depends(get_session),
):
    """设置默认图床。"""
    provider = session.get(ImageHostingProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "图床配置不存在"})
    _clear_other_defaults(session)
    provider.is_default = True
    session.add(provider)
    session.commit()
    return ok(_provider_to_view(provider), message="已设为默认图床")


def _clear_other_defaults(session: Session):
    """取消所有图床的默认标记。"""
    defaults = session.exec(
        select(ImageHostingProvider).where(ImageHostingProvider.is_default == True)  # noqa: E712
    ).all()
    for d in defaults:
        d.is_default = False
        session.add(d)
