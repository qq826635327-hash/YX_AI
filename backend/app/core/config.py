"""核心配置模块：应用配置加载、密钥管理、路径解析。"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 开发环境默认密钥（生产环境必须通过环境变量 ADS_ENCRYPTION_KEY 覆盖）
_DEV_DEFAULT_KEY = "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg="


# ============================================================
# 配置 Schema 定义
# ============================================================

class AppConfig(BaseModel):
    name: str = "AI Drama Studio"
    version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_dist: str = "../frontend/dist"
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    logs_dir: str = "../logs"


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/db/app.sqlite"
    echo: bool = False


class StorageConfig(BaseModel):
    projects_root: str = "../data/projects"
    allowed_image_types: List[str] = Field(default_factory=lambda: ["png", "jpg", "jpeg", "webp", "gif"])
    allowed_video_types: List[str] = Field(default_factory=lambda: ["mp4", "webm", "mov", "mkv"])


class ComfyUIConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8188"
    timeout: int = 300
    output_dir: str = ""
    enabled: bool = False


class SecurityConfig(BaseModel):
    encryption_key: str = _DEV_DEFAULT_KEY
    basic_auth_enabled: bool = False
    basic_auth_user: str = "admin"
    basic_auth_password: str = "admin"

    @property
    def is_default_key(self) -> bool:
        """检测是否使用了默认开发密钥。"""
        return self.encryption_key == _DEV_DEFAULT_KEY


class TasksConfig(BaseModel):
    backend: str = "sqlite"
    huey_path: str = "./data/db/huey.sqlite"
    max_retry: int = 3
    timeout: int = 600
    save_prompts: bool = True  # 是否保存生成提示词到 txt 文件


class LLMConfig(BaseModel):
    enabled: bool = False
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout: int = 120


class ImageHostingConfig(BaseModel):
    """图床配置（用于将本地图片上传到公网，供需要公网 URL 的 API 使用）。"""
    provider: str = ""  # "smms" | ""（空=不启用）
    smms_token: str = ""  # SM.MS API Secret Token


class ReferencePromptConfig(BaseModel):
    """参考图 prompt 自动拼接模板配置。

    当任务携带参考图且启用时，系统会自动在 prompt 中追加参考图描述行。
    可通过修改配置快速调整话术，无需改代码。
    """
    enabled: bool = True
    # 整体排版模板：{items} 为拼接后的描述行，{original_prompt} 为用户原始提示词
    template: str = "{items}\n{original_prompt}"
    # 单条参考图描述模板：{index} 为序号（从 1 开始），{label} 为参考图标签
    item_template: str = "图{index}是{label}"
    # 多条参考图之间的分隔符
    separator: str = "、"
    # 描述行整体结尾符号
    item_terminator: str = "。"
    # 描述行位置：prefix=放在原始 prompt 前面，suffix=放在后面
    position: str = "prefix"


class Settings(BaseModel):
    """全局配置对象。"""

    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    comfyui: ComfyUIConfig = Field(default_factory=ComfyUIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    image_hosting: ImageHostingConfig = Field(default_factory=ImageHostingConfig)
    reference_prompt: ReferencePromptConfig = Field(default_factory=ReferencePromptConfig)

    # 运行时计算的字段
    backend_root: Path = Path(__file__).resolve().parent.parent.parent  # backend/
    projects_root_abs: Path = Path(".")  # 启动时计算

    model_config = {"arbitrary_types_allowed": True}


# ============================================================
# 配置加载
# ============================================================

def _load_yaml_config(config_path: Path) -> dict:
    """加载 YAML 配置文件。"""
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_env_overrides(settings: Settings) -> Settings:
    """应用环境变量覆盖（环境变量优先级最高）。"""
    # 数据库
    if db_url := os.getenv("ADS_DB_URL"):
        settings.database.url = db_url

    # ComfyUI
    if comfyui_url := os.getenv("ADS_COMFYUI_URL"):
        settings.comfyui.base_url = comfyui_url
    if comfyui_enabled := os.getenv("ADS_COMFYUI_ENABLED"):
        settings.comfyui.enabled = comfyui_enabled.lower() in ("1", "true", "yes")

    # LLM
    if llm_key := os.getenv("ADS_LLM_API_KEY"):
        settings.llm.api_key = llm_key
        settings.llm.enabled = True
    if llm_base := os.getenv("ADS_LLM_BASE_URL"):
        settings.llm.base_url = llm_base

    # 安全密钥
    if enc_key := os.getenv("ADS_ENCRYPTION_KEY"):
        settings.security.encryption_key = enc_key

    # 图床
    if smms_token := os.getenv("ADS_SMMS_TOKEN"):
        settings.image_hosting.smms_token = smms_token
        if not settings.image_hosting.provider:
            settings.image_hosting.provider = "smms"

    # 端口
    if port := os.getenv("ADS_PORT"):
        settings.app.port = int(port)

    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局配置（单例，首次调用时加载）。"""
    backend_root = Path(__file__).resolve().parent.parent.parent  # backend/
    config_path = backend_root / "config.yaml"

    raw = _load_yaml_config(config_path)
    settings = Settings.model_validate(raw) if raw else Settings()

    settings.backend_root = backend_root

    # 计算项目根目录的绝对路径
    projects_root = Path(settings.storage.projects_root)
    if not projects_root.is_absolute():
        projects_root = (backend_root / projects_root).resolve()
    settings.projects_root_abs = projects_root

    # 环境变量覆盖
    settings = _apply_env_overrides(settings)

    return settings


def clear_settings_cache() -> None:
    """清除配置缓存（应用重启时调用，确保配置重新加载）。"""
    get_settings.cache_clear()
    _get_fernet.cache_clear()


# ============================================================
# 密钥加密工具
# ============================================================

@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """获取 Fernet 加密实例。"""
    key = get_settings().security.encryption_key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plain: str) -> str:
    """加密敏感数据（如 API Key）。"""
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher: str) -> str:
    """解密敏感数据。"""
    if not cipher:
        return ""
    try:
        return _get_fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except Exception:
        # 解密失败：不再回退到原始密文，避免泄露密文内容
        logger.warning("解密失败，返回空字符串。如果这是旧数据，请重新配置 API Key。")
        return ""


def mask_secret(secret: str) -> str:
    """脱敏展示：只显示前4位和后4位。"""
    if not secret or len(secret) <= 8:
        return "*" * len(secret) if secret else ""
    return f"{secret[:4]}****{secret[-4:]}"


def validate_security(settings: Settings) -> None:
    """启动时安全校验，生产环境使用默认密钥时拒绝启动。"""
    if settings.security.is_default_key:
        env = os.getenv("ADS_ENV", "development")
        if env != "development":
            raise RuntimeError(
                "安全错误：生产环境禁止使用默认 Fernet 密钥。\n"
                "请设置环境变量 ADS_ENCRYPTION_KEY 为一个安全的 Fernet 密钥。\n"
                "生成方法: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        else:
            logger.warning(
                "[安全警告] 当前使用默认开发密钥，API Key 加密强度不足。"
                "生产环境请设置环境变量 ADS_ENCRYPTION_KEY。"
            )
