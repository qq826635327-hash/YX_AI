"""数据库连接与初始化。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import get_settings


# ============================================================
# 引擎创建
# ============================================================

def _build_engine():
    settings = get_settings()
    db_url = settings.database.url

    # 确保 SQLite 文件目录存在
    if db_url.startswith("sqlite:///"):
        db_file = db_url.replace("sqlite:///", "", 1)
        db_path = Path(db_file)
        if not db_path.is_absolute():
            db_path = settings.backend_root / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # 重新构造为绝对路径的 url
        db_url = f"sqlite:///{db_path.as_posix()}"

    connect_args: dict = {}
    if db_url.startswith("sqlite"):
        connect_args = {
            "check_same_thread": False,
            "timeout": 60,  # sqlite3 模块层锁等待超时（秒），给足时间
        }
    engine = create_engine(
        db_url,
        echo=settings.database.echo,
        connect_args=connect_args,
        pool_pre_ping=True,  # 连接复用前检测存活
    )

    # SQLite 关键 PRAGMA 配置
    if db_url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            # WAL 模式：读写不互斥，大幅提升并发性能
            cursor.execute("PRAGMA journal_mode=WAL")
            # NORMAL 模式：写操作在 WAL 刷盘后才返回，兼顾安全和性能
            cursor.execute("PRAGMA synchronous=NORMAL")
            # 外键约束
            cursor.execute("PRAGMA foreign_keys=ON")
            # ★ 终极修复：busy_timeout 设为 30 秒
            # 这是 SQLite 内置的锁等待机制，当数据库被其他连接锁住时，
            # SQLite 会自动等待最多 30 秒，而不是立即返回 "database is locked"。
            # 这比 Python 层的手动重试更高效，因为：
            # 1. SQLite 内部在锁释放后立即唤醒，不需要轮询
            # 2. 对所有连接生效，包括 SQLAlchemy 内部连接池复用的连接
            # 3. 消除了 Python 层手动重试的复杂性和竞态条件
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


# ============================================================
# 引擎管理（懒加载 + 可重置）
# ============================================================

_engine = None


def get_engine():
    """获取数据库引擎（懒加载，重启时可重置）。"""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def reset_engine() -> None:
    """重置数据库引擎（重启时调用，释放旧连接）。"""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


# ============================================================
# 会话管理
# ============================================================

def get_session() -> Iterator[Session]:
    """FastAPI 依赖注入用的会话生成器。"""
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """上下文管理器形式的会话（用于非 FastAPI 场景，如任务队列）。

    SQLite 锁冲突已通过 PRAGMA busy_timeout=30000 在引擎层解决，
    SQLite 会在内部自动等待锁释放（最多 30 秒），不再需要 Python 层手动重试。
    """
    session = Session(get_engine(), expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ============================================================
# 初始化
# ============================================================

def init_db() -> None:
    """创建所有表（开发期使用，生产环境建议用 Alembic 迁移）。"""
    # 确保所有模型被导入
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())

    # 为已有表添加新列（SQLite ALTER TABLE ADD COLUMN）
    _migrate_add_columns()

    # 将旧版 Provider 单模型字段迁移到 provider_models 表
    _migrate_provider_models()

    # 将 Handler SUPPORTED_MODELS 默认值 seed 到 DB（仅对 param_specs IS NULL 的模型）
    _seed_model_configs()

    # 初始化提示词模板内置数据
    _seed_prompt_templates()

    # 初始化画风预置内置数据
    _seed_style_presets()


def _seed_prompt_templates() -> None:
    """初始化内置提示词模板。"""
    from app.services.prompt_template_service import seed_builtin_templates

    with Session(get_engine(), expire_on_commit=False) as session:
        try:
            seed_builtin_templates(session)
        except Exception:
            session.rollback()
            raise


def _seed_style_presets() -> None:
    """初始化内置画风预置。"""
    from app.services.style_preset_service import seed_builtin_presets

    with Session(get_engine(), expire_on_commit=False) as session:
        try:
            seed_builtin_presets(session)
        except Exception:
            session.rollback()
            raise


def check_db() -> dict:
    """检查数据库连接状态（健康检查用）。"""
    try:
        with session_scope() as session:
            session.exec(select(1))
        return {"status": "ok", "engine": str(get_engine().url)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _migrate_add_columns() -> None:
    """为已有表添加新列（SQLite ALTER TABLE ADD COLUMN）。

    SQLite 不支持 ALTER TABLE ADD COLUMN 带 DEFAULT 以外的约束，
    也不支持 NOT NULL（除非有 DEFAULT）。因此新列都设为 nullable。
    如果列已存在，SQLite 会报错 "duplicate column name"，我们忽略它。
    """
    import logging
    _logger = logging.getLogger(__name__)

    # 定义需要添加的新列：{表名: [(列名, 列类型), ...]}
    new_columns = {
        "task_logs": [
            ("phase", "TEXT"),
            ("event_type", "TEXT"),
            ("data_json", "JSON"),
            ("trace_id", "TEXT"),
        ],
        "assets": [
            ("public_url", "VARCHAR(1000)"),
            ("public_url_uploaded_at", "VARCHAR(40)"),
            ("public_url_file_hash", "VARCHAR(64)"),
        ],
        "characters": [
            ("gender", "VARCHAR(20)"),
            ("age", "VARCHAR(50)"),
        ],
        "scenes": [
            ("camera_hint", "VARCHAR(200)"),
        ],
        "shots": [
            ("camera_size", "VARCHAR(30)"),
            ("camera_angle", "VARCHAR(30)"),
            ("camera_movement", "VARCHAR(30)"),
        ],
        "projects": [
            ("style_preset", "VARCHAR(100)"),
        ],
        "provider_models": [
            ("param_specs", "JSON"),
            ("capabilities", "JSON"),
        ],
        "generation_tasks": [
            ("cache_key", "VARCHAR(64)"),
            ("auto_retry_count", "INTEGER"),
        ],
        "perf_sessions": [
            ("mem_limit_mb", "INTEGER"),
        ],
        "script_documents": [
            ("pre_parse_snapshot", "JSON"),
            ("current_stage", "VARCHAR(20)"),
            ("completed_stages", "JSON"),
        ],
    }

    # 白名单校验：确保表名和列名只包含合法字符，防止 SQL 注入
    import re
    _safe_name_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    engine = get_engine()
    with engine.connect() as conn:
        for table_name, columns in new_columns.items():
            if not _safe_name_pattern.match(table_name):
                _logger.warning(f"[migration] 跳过非法表名: {table_name}")
                continue

            # 检查表是否存在
            result = conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"
                ),
                {"table_name": table_name},
            )
            if not result.fetchone():
                continue

            # 获取已有列名
            result = conn.execute(
                __import__("sqlalchemy").text(f"PRAGMA table_info({table_name})")
            )
            existing_cols = {row[1] for row in result.fetchall()}

            for col_name, col_type in columns:
                if not _safe_name_pattern.match(col_name):
                    _logger.warning(f"[migration] 跳过非法列名: {table_name}.{col_name}")
                    continue
                if col_name not in existing_cols:
                    try:
                        conn.execute(
                            __import__("sqlalchemy").text(
                                f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                            )
                        )
                        conn.commit()
                        _logger.info(f"[migration] 添加列: {table_name}.{col_name}")
                    except Exception as e:
                        if "duplicate column name" in str(e):
                            pass  # 列已存在，忽略
                        else:
                            _logger.warning(f"[migration] 添加列失败: {table_name}.{col_name}: {e}")


def _migrate_provider_models() -> None:
    """将旧版 api_providers.model 单模型字段迁移到 provider_models 表。"""
    import logging

    _logger = logging.getLogger(__name__)
    from app.models import ApiProvider, ProviderModel
    from app.services.config_service import _infer_model_tags

    engine = get_engine()
    with engine.connect() as conn:
        # 检查表是否存在
        result = conn.execute(
            __import__("sqlalchemy").text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='provider_models'"
            )
        )
        if not result.fetchone():
            return

    with Session(engine, expire_on_commit=False) as session:
        providers = session.exec(select(ApiProvider)).all()
        migrated = 0
        for provider in providers:
            if not provider.model:
                continue
            # 已迁移过则跳过
            existing = session.exec(
                select(ProviderModel).where(ProviderModel.provider_id == provider.id)
            ).first()
            if existing:
                continue
            pm = ProviderModel(
                provider_id=provider.id,
                model_name=provider.model,
                tags=_infer_model_tags(provider.model),
                sort_order=0,
            )
            session.add(pm)
            migrated += 1
        if migrated:
            session.commit()
            _logger.info(f"[migration] 已迁移 {migrated} 个 Provider 的模型到 provider_models 表")


def _seed_model_configs() -> None:
    """将 Handler SUPPORTED_MODELS 默认值写入 DB（仅对 param_specs IS NULL 的模型）。

    幂等设计：只在 param_specs 为 NULL（从未初始化）时 seed，
    不会覆盖用户主动清空（param_specs=[]）或已配置的值。
    """
    import logging

    _logger = logging.getLogger(__name__)
    from app.models import ApiProvider, ProviderModel
    from app.providers import get_handler_class
    from app.schemas.provider_types import ModelCapabilities

    engine = get_engine()
    with Session(engine, expire_on_commit=False) as session:
        providers = session.exec(select(ApiProvider)).all()
        seeded = 0

        for provider in providers:
            handler_cls = get_handler_class(provider.provider_kind)
            if not handler_cls or not handler_cls.SUPPORTED_MODELS:
                continue

            # 重新加载 provider 以获取关联的 models
            from sqlalchemy.orm import selectinload
            stmt = select(ApiProvider).where(ApiProvider.id == provider.id).options(selectinload(ApiProvider.models))
            full_provider = session.exec(stmt).first()
            if not full_provider:
                continue

            for model_record in full_provider.models or []:
                # 仅当 param_specs 为 NULL 时 seed（幂等）
                if model_record.param_specs is not None:
                    continue

                default = handler_cls.SUPPORTED_MODELS.get(model_record.model_name)
                if not default:
                    continue

                model_record.param_specs = default.get("param_specs", [])

                if model_record.capabilities is None:
                    caps = default.get("capabilities", {})
                    model_record.capabilities = caps.to_dict() if isinstance(caps, ModelCapabilities) else caps

                session.add(model_record)
                seeded += 1

        if seeded:
            session.commit()
            _logger.info(f"[seed] 已初始化 {seeded} 个模型的 param_specs/capabilities 默认配置")
