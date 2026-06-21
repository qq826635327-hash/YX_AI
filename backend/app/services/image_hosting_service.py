"""图床服务：将本地图片上传到公网，供需要公网 URL 的 API 使用。

当前支持：SM.MS 图床。
缓存机制：上传结果存入 Asset 表的 public_url / public_url_file_hash 字段，
          同一文件不重复上传（基于 SHA256 hash 判断）。
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlmodel import Session

from app.core.config import get_settings
from app.models.asset import Asset

logger = logging.getLogger(__name__)


def _file_sha256(file_path: str | Path) -> str:
    """计算文件的 SHA256 hash。"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def _upload_to_smms(file_path: str | Path, token: str) -> str:
    """上传图片到 SM.MS 图床，返回公网 URL。

    SM.MS API v2:
      POST https://sm.ms/api/v2/upload
      Header: Authorization: <Secret Token>
      Body: smfile=<file> (multipart/form-data)
      成功返回: {"success": true, "data": {"url": "https://..."}}
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {file_path}")

    async with httpx.AsyncClient(timeout=60) as client:
        with open(file_path, "rb") as f:
            files = {"smfile": (file_path.name, f, "image/png")}
            headers = {"Authorization": token}
            resp = await client.post(
                "https://sm.ms/api/v2/upload",
                files=files,
                headers=headers,
            )

        body = resp.json()

        # SM.MS 可能返回图片已存在的响应
        if body.get("code") == "image_repeated" and body.get("images"):
            # 图片已存在，返回已有 URL
            url = body["images"]
            logger.info(f"SM.MS: 图片已存在，复用 URL: {url}")
            return url

        if not body.get("success"):
            error_msg = body.get("message", "未知错误")
            raise RuntimeError(f"SM.MS 上传失败: {error_msg}")

        url = body["data"]["url"]
        logger.info(f"SM.MS: 上传成功, URL: {url}")
        return url


async def get_or_upload_public_url(
    asset_id: str,
    file_path: str | Path,
    session: Session,
) -> str:
    """获取 Asset 的公网 URL，如果未上传或文件已变更则上传到图床。

    Args:
        asset_id: Asset 记录 ID
        file_path: 本地图片文件路径
        session: 数据库 session

    Returns:
        公网 URL 字符串

    Raises:
        RuntimeError: 图床未配置或上传失败
        FileNotFoundError: 本地文件不存在
    """
    settings = get_settings()
    provider = settings.image_hosting.provider

    if not provider:
        raise RuntimeError(
            "图床未配置。请在 config.yaml 中设置 image_hosting.provider 和对应 token，"
            "或设置环境变量 ADS_SMMS_TOKEN。"
        )

    # 计算当前文件 hash
    current_hash = _file_sha256(file_path)

    # 查询缓存
    asset = session.get(Asset, asset_id)
    if asset and asset.public_url and asset.public_url_file_hash == current_hash:
        logger.debug(f"Asset {asset_id} 图床缓存命中: {asset.public_url}")
        return asset.public_url

    # 需要上传
    if provider == "smms":
        token = settings.image_hosting.smms_token
        if not token:
            raise RuntimeError("SM.MS token 未配置。请设置 image_hosting.smms_token 或环境变量 ADS_SMMS_TOKEN。")
        url = await _upload_to_smms(file_path, token)
    else:
        raise RuntimeError(f"不支持的图床类型: {provider}")

    # 更新 Asset 缓存
    if asset:
        asset.public_url = url
        asset.public_url_uploaded_at = datetime.now(timezone.utc).isoformat()
        asset.public_url_file_hash = current_hash
        session.add(asset)
        session.commit()

    return url
