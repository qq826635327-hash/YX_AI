"""启动时将 config.yaml 中的图床配置迁移到数据库。"""

import logging

from sqlmodel import Session, select

from app.core.config import encrypt_secret, get_settings
from app.db import get_engine
from app.models.image_hosting import ImageHostingProvider

logger = logging.getLogger(__name__)


def migrate_image_hosting_from_config():
    """将 config.yaml 中的图床配置迁移到数据库（幂等，仅执行一次）。"""
    settings = get_settings()
    provider = settings.image_hosting.provider

    if not provider:
        return  # 没有配置，无需迁移

    with Session(get_engine()) as session:
        # 检查是否已有图床配置
        existing = session.exec(select(ImageHostingProvider)).first()
        if existing:
            return  # 已有配置，不覆盖

        # 获取 token
        token = ""
        if provider == "smms":
            token = settings.image_hosting.smms_token
        elif provider == "superbed":
            token = settings.image_hosting.superbed_token
        elif provider == "boltp":
            token = settings.image_hosting.boltp_token

        if not token:
            return  # 没有 token，不迁移

        # 创建 DB 记录
        name_map = {
            "smms": "SM.MS 图床",
            "superbed": "聚合图床",
            "boltp": "闪电图床",
        }
        new_provider = ImageHostingProvider(
            name=name_map.get(provider, f"图床({provider})"),
            provider_type=provider,
            token_encrypted=encrypt_secret(token),
            is_default=True,
            enabled=True,
            description="从 config.yaml 自动迁移",
        )
        session.add(new_provider)
        session.commit()
        logger.info(f"已将 config.yaml 中的图床配置({provider})迁移到数据库")
