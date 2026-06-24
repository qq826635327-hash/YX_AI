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
    save_prompts: bool = True  # 是否保存生成提示词到 txt 文件
    rate_limit_retry: int = 5  # 速率限制自动重试次数（0=不重试）
    rate_limit_wait: int = 65  # 速率限制重试等待时间（秒）
    smart_fallback: bool = True  # 智能降级：主引擎失败时自动切换备选 Provider
    max_concurrent: int = 4  # 任务中心最大并发数
    auto_retry_on_download_fail: bool = True  # API已成功但下载失败时自动重试
    auto_retry_max_attempts: int = 3  # 自动重试最大次数
    task_max_age_minutes: int = 30  # 任务最大存活时间（分钟），超时不再自动重试


class ImageHostingConfig(BaseModel):
    """图床配置（用于将本地图片上传到公网，供需要公网 URL 的 API 使用）。"""
    provider: str = ""  # "smms" | "superbed" | "boltp" | ""（空=不启用）
    smms_token: str = ""  # SM.MS API Secret Token
    superbed_token: str = ""  # 聚合图床(superbed.cc) Token
    boltp_token: str = ""  # 闪电图床(boltp.com) Token


class BackupConfig(BaseModel):
    """SQLite 自动备份配置。"""
    enabled: bool = True
    dir: str = "../data/backups"
    retention_days: int = 7


class RetentionConfig(BaseModel):
    """数据保留策略配置。

    按时间清理过期数据，防止数据库无限膨胀：
    - task_logs_days: 超过此天数的日志无条件清理
    - tasks_days: 超过此天数且已结束（succeeded/failed/cancelled）的任务清理
    """
    task_logs_days: int = 30
    tasks_days: int = 90


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


class DefaultModelsConfig(BaseModel):
    """默认模型配置：全局生效，生图/生视频/文本推理时自动选择。"""
    default_image_model: str = ""   # 默认图片生成模型名
    default_text_model: str = ""    # 默认文本推理模型名
    default_video_model: str = ""   # 默认视频生成模型名


class Settings(BaseModel):
    """全局配置对象。"""

    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    comfyui: ComfyUIConfig = Field(default_factory=ComfyUIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)
    image_hosting: ImageHostingConfig = Field(default_factory=ImageHostingConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    reference_prompt: ReferencePromptConfig = Field(default_factory=ReferencePromptConfig)
    default_models: DefaultModelsConfig = Field(default_factory=DefaultModelsConfig)

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

    # 安全密钥
    if enc_key := os.getenv("ADS_ENCRYPTION_KEY"):
        settings.security.encryption_key = enc_key

    # 图床
    if smms_token := os.getenv("ADS_SMMS_TOKEN"):
        settings.image_hosting.smms_token = smms_token
        if not settings.image_hosting.provider:
            settings.image_hosting.provider = "smms"

    if superbed_token := os.getenv("ADS_SUPERBED_TOKEN"):
        settings.image_hosting.superbed_token = superbed_token
        if not settings.image_hosting.provider:
            settings.image_hosting.provider = "superbed"

    if boltp_token := os.getenv("ADS_BOLTP_TOKEN"):
        settings.image_hosting.boltp_token = boltp_token
        if not settings.image_hosting.provider:
            settings.image_hosting.provider = "boltp"

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


def save_settings_to_yaml(settings: Settings) -> None:
    """将当前 Settings 持久化写入 config.yaml（运行时修改配置后调用）。"""
    config_path = settings.backend_root / "config.yaml"

    # 读取现有 YAML 保留注释和格式
    existing = _load_yaml_config(config_path)

    # 合并变更（只更新有变化的字段，保留其他字段）
    existing.setdefault("default_models", {})
    existing["default_models"]["default_image_model"] = settings.default_models.default_image_model
    existing["default_models"]["default_text_model"] = settings.default_models.default_text_model
    existing["default_models"]["default_video_model"] = settings.default_models.default_video_model

    existing.setdefault("tasks", {})
    existing["tasks"]["rate_limit_retry"] = settings.tasks.rate_limit_retry
    existing["tasks"]["rate_limit_wait"] = settings.tasks.rate_limit_wait
    existing["tasks"]["smart_fallback"] = settings.tasks.smart_fallback
    existing["tasks"]["max_concurrent"] = settings.tasks.max_concurrent
    existing["tasks"]["auto_retry_on_download_fail"] = settings.tasks.auto_retry_on_download_fail
    existing["tasks"]["auto_retry_max_attempts"] = settings.tasks.auto_retry_max_attempts
    existing["tasks"]["task_max_age_minutes"] = settings.tasks.task_max_age_minutes

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("配置已持久化到 %s", config_path)


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


class DecryptionError(Exception):
    """API Key 解密失败异常。"""
    pass


def decrypt_secret(cipher: str) -> str:
    """解密敏感数据。"""
    if not cipher:
        return ""
    try:
        return _get_fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except Exception as e:
        # 解密失败时抛出特定异常，由调用方决定降级策略
        logger.error(f"解密失败: {e}。可能是密钥更换导致旧数据无法解密，请重新配置 API Key。")
        raise DecryptionError(f"解密失败，可能是密钥更换导致。请重新配置 API Key。原始错误: {e}") from e


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
