"""图床服务：将本地图片上传到公网，供需要公网 URL 的 API 使用。

当前支持：SM.MS、聚合图床(superbed.cc)、闪电图床(boltp.com)、GitHub、自定义。
缓存机制：上传结果存入 Asset 表的 public_url / public_url_file_hash 字段，
          同一文件不重复上传（基于 SHA256 hash 判断）。
"""

from __future__ import annotations

import base64
import hashlib
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlmodel import Session, select

from app.core.config import decrypt_secret, get_settings
from app.models.asset import Asset
from app.models.image_hosting import ImageHostingProvider

logger = logging.getLogger(__name__)

# 各图床的默认文件大小限制（字节）
_HOSTING_MAX_SIZE = {
    "smms": 5 * 1024 * 1024,      # SM.MS: 5MB
    "superbed": 10 * 1024 * 1024,  # 聚合图床: 10MB
    "boltp": 10 * 1024 * 1024,     # 闪电图床: 10MB
    "github": 100 * 1024 * 1024,   # GitHub: 100MB
    "custom": 10 * 1024 * 1024,    # 自定义: 10MB
}


def _file_sha256(file_path: str | Path) -> str:
    """计算文件的 SHA256 hash。"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _compress_for_upload(file_path: str | Path, max_bytes: int) -> Path:
    """如果文件超过大小限制，压缩为 JPEG 后返回临时文件路径；否则返回原路径。"""
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    if file_size <= max_bytes:
        return file_path

    from PIL import Image

    img = Image.open(file_path)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    for quality in range(85, 30, -10):
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img.save(tmp, format="JPEG", quality=quality, optimize=True)
        tmp.close()
        if Path(tmp.name).stat().st_size <= max_bytes:
            compressed_kb = Path(tmp.name).stat().st_size // 1024
            original_kb = file_size // 1024
            logger.info(
                f"图片压缩: {file_path.name} {original_kb}KB → {compressed_kb}KB (quality={quality})"
            )
            return Path(tmp.name)
        Path(tmp.name).unlink(missing_ok=True)

    max_dim = 1920
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        for quality in range(85, 40, -10):
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            img.save(tmp, format="JPEG", quality=quality, optimize=True)
            tmp.close()
            if Path(tmp.name).stat().st_size <= max_bytes:
                compressed_kb = Path(tmp.name).stat().st_size // 1024
                original_kb = file_size // 1024
                logger.info(
                    f"图片压缩+缩放: {file_path.name} {original_kb}KB → {compressed_kb}KB "
                    f"({img.size[0]}x{img.size[1]}, quality={quality})"
                )
                return Path(tmp.name)
            Path(tmp.name).unlink(missing_ok=True)

    raise RuntimeError(
        f"图片压缩失败: {file_path.name} 原始 {file_size // 1024}KB，"
        f"无法压缩到 {max_bytes // 1024}KB 以下"
    )


# ── 各图床上传实现 ──


async def _upload_to_smms(file_path: str | Path, token: str) -> str:
    """上传图片到 SM.MS 图床，返回公网 URL。"""
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
        if body.get("code") == "image_repeated" and body.get("images"):
            url = body["images"]
            logger.info(f"SM.MS: 图片已存在，复用 URL: {url}")
            return url

        if not body.get("success"):
            error_msg = body.get("message", "未知错误")
            raise RuntimeError(f"SM.MS 上传失败: {error_msg}")

        url = body["data"]["url"]
        logger.info(f"SM.MS: 上传成功, URL: {url}")
        return url


async def _upload_to_superbed(file_path: str | Path, token: str) -> str:
    """上传图片到聚合图床(superbed.cc)，返回公网 URL。"""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {file_path}")

    async with httpx.AsyncClient(timeout=60) as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "image/png")}
            resp = await client.post(
                "https://api.superbed.cc/upload",
                data={"token": token},
                files=files,
            )

        body = resp.json()
        if body.get("err") != 0:
            error_msg = body.get("msg", "未知错误")
            raise RuntimeError(f"Superbed 上传失败: {error_msg}")

        url = body.get("url")
        if not url:
            raise RuntimeError("Superbed 上传成功但返回 URL 为空")

        logger.info(f"Superbed: 上传成功, URL: {url}")
        return url


async def _upload_to_boltp(file_path: str | Path, token: str) -> str:
    """上传图片到闪电图床(boltp.com)，返回公网 URL。"""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {file_path}")

    async with httpx.AsyncClient(timeout=60) as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "image/png")}
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
            resp = await client.post(
                "https://www.boltp.com/api/v2/upload",
                files=files,
                data={"storage_id": "2", "is_public": "true"},
                headers=headers,
            )

        body = resp.json()
        if body.get("status") != "success":
            error_msg = body.get("message", "未知错误")
            raise RuntimeError(f"闪电图床上传失败: {error_msg}")

        url = body.get("data", {}).get("public_url")
        if not url:
            raise RuntimeError("闪电图床上传成功但返回 URL 为空")

        logger.info(f"闪电图床: 上传成功, URL: {url}")
        return url


async def _upload_to_github(
    file_path: str | Path,
    token: str,
    extra_config: dict | None = None,
) -> str:
    """上传图片到 GitHub 仓库（通过 Contents API），返回 raw URL。

    extra_config 需包含：
      - owner: GitHub 用户名
      - repo: 仓库名
      - branch: 分支名（默认 main）
      - path_prefix: 路径前缀（默认 assets）
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {file_path}")

    cfg = extra_config or {}
    owner = cfg.get("owner", "")
    repo = cfg.get("repo", "")
    branch = cfg.get("branch", "main")
    path_prefix = cfg.get("path_prefix", "assets")

    if not owner or not repo:
        raise RuntimeError("GitHub 图床缺少 owner 或 repo 配置")

    # 读取文件并 Base64 编码
    with open(file_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    # 构建路径：path_prefix/日期/文件名
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    gh_path = f"{path_prefix}/{date_str}/{file_path.name}"

    # GitHub Contents API
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{gh_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "message": f"upload image: {file_path.name}",
        "content": content_b64,
        "branch": branch,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.put(url, json=payload, headers=headers)

    if resp.status_code == 422:
        # 文件已存在，获取已有文件的 download_url
        body = resp.json()
        if "errors" in body:
            for err_item in body["errors"]:
                if err_item.get("code") == "already_exists":
                    # 文件已存在，尝试获取其 URL
                    async with httpx.AsyncClient(timeout=60) as client:
                        get_resp = await client.get(url, params={"ref": branch}, headers=headers)
                    if get_resp.status_code == 200:
                        existing = get_resp.json()
                        download_url = existing.get("download_url", "")
                        if download_url:
                            logger.info(f"GitHub: 文件已存在，复用 URL: {download_url}")
                            return download_url
        raise RuntimeError(f"GitHub 上传失败: {resp.text[:200]}")

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"GitHub 上传失败 (HTTP {resp.status_code}): {resp.text[:200]}")

    body = resp.json()
    download_url = body.get("content", {}).get("download_url", "")

    if not download_url:
        # 手动构建 raw URL
        download_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{gh_path}"

    logger.info(f"GitHub: 上传成功, URL: {download_url}")
    return download_url


async def _upload_to_custom(
    file_path: str | Path,
    api_url: str,
    token: str,
    extra_config: dict | None = None,
) -> str:
    """上传图片到自定义图床（通用 multipart POST），返回公网 URL。

    请求格式：
      POST api_url
      Header: Authorization: Bearer <token>（如有 token）
      Body: file=<file> (multipart/form-data)

    响应格式（通过 extra_config.url_path 指定 URL 在响应 JSON 中的路径）：
      默认从 data.url 或 data.public_url 或 url 字段提取
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {file_path}")

    if not api_url:
        raise RuntimeError("自定义图床缺少 API 地址")

    cfg = extra_config or {}
    # 表单字段名（默认 file）
    file_field = cfg.get("file_field", "file")
    # 额外表单参数
    extra_fields = cfg.get("extra_fields", {})
    # URL 在响应中的 JSON 路径（如 "data.url"）
    url_path = cfg.get("url_path", "")

    headers = {}
    if token:
        # 支持自定义 Authorization 格式
        auth_format = cfg.get("auth_format", "Bearer {token}")
        headers["Authorization"] = auth_format.format(token=token)

    async with httpx.AsyncClient(timeout=60) as client:
        with open(file_path, "rb") as f:
            files = {file_field: (file_path.name, f, "image/png")}
            data = {k: str(v) for k, v in extra_fields.items()}
            resp = await client.post(
                api_url,
                files=files,
                data=data,
                headers=headers,
            )

    if resp.status_code >= 400:
        raise RuntimeError(f"自定义图床上传失败 (HTTP {resp.status_code}): {resp.text[:200]}")

    body = resp.json()

    # 从响应中提取 URL
    url = ""
    if url_path:
        # 按路径提取，如 "data.public_url"
        parts = url_path.split(".")
        node = body
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part)
            elif isinstance(node, list) and part.isdigit():
                node = node[int(part)]
            else:
                node = None
                break
        if isinstance(node, str):
            url = node
    else:
        # 自动尝试常见路径
        for candidate in ["data.url", "data.public_url", "url", "data.link", "data.image"]:
            parts = candidate.split(".")
            node = body
            for part in parts:
                if isinstance(node, dict):
                    node = node.get(part)
                else:
                    node = None
                    break
            if isinstance(node, str) and node.startswith("http"):
                url = node
                break

    if not url:
        raise RuntimeError(f"自定义图床上传成功但无法从响应中提取 URL: {str(body)[:200]}")

    logger.info(f"自定义图床: 上传成功, URL: {url}")
    return url


async def upload_to_provider(
    provider_type: str,
    api_url: str,
    token: str,
    file_path: str | Path,
    extra_config: dict | None = None,
) -> str:
    """根据图床类型上传图片，返回公网 URL。

    此函数供 API 测试端点和 get_or_upload_public_url 调用。
    """
    if provider_type == "smms":
        return await _upload_to_smms(file_path, token)
    elif provider_type == "superbed":
        return await _upload_to_superbed(file_path, token)
    elif provider_type == "boltp":
        return await _upload_to_boltp(file_path, token)
    elif provider_type == "github":
        return await _upload_to_github(file_path, token, extra_config)
    elif provider_type == "custom":
        return await _upload_to_custom(file_path, api_url, token, extra_config)
    else:
        raise RuntimeError(f"不支持的图床类型: {provider_type}")


def _get_default_provider_from_db(session: Session) -> ImageHostingProvider | None:
    """从数据库获取默认图床配置。"""
    # 优先取 is_default=True 且 enabled=True 的
    provider = session.exec(
        select(ImageHostingProvider)
        .where(ImageHostingProvider.is_default == True, ImageHostingProvider.enabled == True)  # noqa: E712
    ).first()
    if provider:
        return provider
    # 其次取第一个 enabled=True 的
    provider = session.exec(
        select(ImageHostingProvider).where(ImageHostingProvider.enabled == True)  # noqa: E712
    ).first()
    return provider


async def get_or_upload_public_url(
    asset_id: str,
    file_path: str | Path,
    session: Session,
) -> str:
    """获取 Asset 的公网 URL，如果未上传或文件已变更则上传到图床。

    优先从数据库读取图床配置，fallback 到 config.yaml。
    """
    # ── 从 DB 获取默认图床 ──
    db_provider = _get_default_provider_from_db(session)

    if db_provider:
        provider_type = db_provider.provider_type
        token = ""
        if db_provider.token_encrypted:
            try:
                token = decrypt_secret(db_provider.token_encrypted)
            except Exception:
                raise RuntimeError("图床 Token 解密失败，请重新配置图床密钥")
        api_url = db_provider.api_url
        extra_config = db_provider.extra_config
        max_bytes = db_provider.max_file_size or _HOSTING_MAX_SIZE.get(provider_type, 10 * 1024 * 1024)
    else:
        # ── Fallback: 从 config.yaml 读取（向后兼容） ──
        settings = get_settings()
        provider_type = settings.image_hosting.provider
        if not provider_type:
            raise RuntimeError(
                "图床未配置。请在设置中添加图床配置，或在 config.yaml 中设置 image_hosting.provider。"
            )

        if provider_type == "smms":
            token = settings.image_hosting.smms_token
        elif provider_type == "superbed":
            token = settings.image_hosting.superbed_token
        elif provider_type == "boltp":
            token = settings.image_hosting.boltp_token
        else:
            token = ""

        if not token:
            raise RuntimeError(f"图床 {provider_type} 的 Token 未配置。")

        api_url = ""
        extra_config = None
        max_bytes = _HOSTING_MAX_SIZE.get(provider_type, 10 * 1024 * 1024)

    # 计算当前文件 hash
    current_hash = _file_sha256(file_path)

    # 查询缓存
    asset = session.get(Asset, asset_id)
    if asset and asset.public_url and asset.public_url_file_hash == current_hash:
        logger.debug(f"Asset {asset_id} 图床缓存命中: {asset.public_url}")
        return asset.public_url

    # 需要上传
    upload_path = _compress_for_upload(file_path, max_bytes)
    is_compressed = upload_path != Path(file_path)

    try:
        url = await upload_to_provider(
            provider_type=provider_type,
            api_url=api_url,
            token=token,
            file_path=upload_path,
            extra_config=extra_config,
        )
    finally:
        # 清理压缩临时文件
        if is_compressed:
            try:
                upload_path.unlink()
            except OSError:
                pass

    # 更新 Asset 缓存
    if asset:
        asset.public_url = url
        asset.public_url_uploaded_at = datetime.now(timezone.utc).isoformat()
        asset.public_url_file_hash = current_hash
        session.add(asset)
        session.commit()

    return url
