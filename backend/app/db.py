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
            "timeout": 30,  # 增加锁等待超时（秒）
        }
    engine = create_engine(db_url, echo=settings.database.echo, connect_args=connect_args)

    # SQLite 启用 WAL 模式（Write-Ahead Logging，提升并发性能）
    if db_url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
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
    """上下文管理器形式的会话（用于非 FastAPI 场景，如任务队列）。"""
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
    }

    engine = get_engine()
    with engine.connect() as conn:
        for table_name, columns in new_columns.items():
            # 检查表是否存在
            result = conn.execute(
                __import__("sqlalchemy").text(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                )
            )
            if not result.fetchone():
                continue

            # 获取已有列名
            result = conn.execute(
                __import__("sqlalchemy").text(f"PRAGMA table_info({table_name})")
            )
            existing_cols = {row[1] for row in result.fetchall()}

            for col_name, col_type in columns:
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
