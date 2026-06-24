# -*- coding: utf-8 -*-
"""备份与数据保留策略服务。

启动时自动执行：
1. SQLite 数据库热备份（使用 .backup API，对 WAL 安全）
2. 数据保留策略（清理过期的 task_logs 和已结束任务）
3. WAL checkpoint（收缩 WAL 文件，防止无限增长）

另提供手动触发备份的函数供 API 端点调用。
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# SQLite 热备份
# ============================================================

def backup_database() -> Path | None:
    """使用 SQLite .backup API 创建一致性数据库快照。

    .backup 命令在 WAL 模式下也是安全的，它会等待所有写操作完成
    后再复制主数据库文件，得到的是一个完整一致的状态。

    Returns:
        备份文件路径；未启用或失败时返回 None。
    """
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.backup.enabled:
        logger.info("数据库备份未启用（backup.enabled=false）")
        return None

    db_url = settings.database.url
    if not db_url.startswith("sqlite:///"):
        logger.warning("备份功能仅支持 SQLite，当前数据库类型不支持")
        return None

    db_file = db_url.replace("sqlite:///", "", 1)
    db_path = Path(db_file)
    if not db_path.is_absolute():
        db_path = settings.backend_root / db_path

    if not db_path.exists():
        logger.warning(f"数据库文件不存在，跳过备份: {db_path}")
        return None

    # 备份目录
    backup_dir = Path(settings.backup.dir)
    if not backup_dir.is_absolute():
        backup_dir = settings.backend_root / backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 去重：同一天内已有足够新的备份则跳过，避免开发阶段频繁重启产生备份风暴
    _BACKUP_MIN_INTERVAL_S = 3600  # 同一小时内不重复备份
    _BACKUP_MAX_COUNT = 20         # 最多保留 20 个备份文件
    existing_backups = sorted(
        backup_dir.glob("app_backup_*.sqlite"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if existing_backups:
        newest_mtime = existing_backups[0].stat().st_mtime
        import time as _time
        if _time.time() - newest_mtime < _BACKUP_MIN_INTERVAL_S:
            logger.info(f"跳过备份：最近一次备份在 {_time.time() - newest_mtime:.0f}s 前（阈值 {_BACKUP_MIN_INTERVAL_S}s）")
            return None
        # 超出数量上限时删除最旧的
        if len(existing_backups) > _BACKUP_MAX_COUNT:
            for old_file in existing_backups[_BACKUP_MAX_COUNT:]:
                try:
                    old_file.unlink()
                    logger.debug(f"删除超量备份: {old_file.name}")
                except OSError:
                    pass

    # 带时间戳的文件名，便于保留多份历史
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"app_backup_{ts}.sqlite"

    try:
        # sqlite3 .backup API：对 WAL 安全，不锁库，可在运行时执行
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(backup_file))
        src.backup(dst)
        dst.close()
        src.close()

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        logger.info(f"数据库备份完成: {backup_file.name} ({size_mb:.2f} MB)")

        # 顺便清理过期备份
        _cleanup_old_backups(backup_dir, settings.backup.retention_days)

        return backup_file

    except Exception as e:
        logger.error(f"数据库备份失败: {e}")
        return None


def _cleanup_old_backups(backup_dir: Path, retention_days: int) -> None:
    """清理超过保留天数的旧备份文件（仅删除 .sqlite 文件）。"""
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0

    if not backup_dir.exists():
        return

    for f in backup_dir.glob("app_backup_*.sqlite"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                removed += 1
                logger.debug(f"删除过期备份: {f.name}")
        except OSError as e:
            logger.warning(f"清理备份文件失败 {f.name}: {e}")

    if removed:
        logger.info(f"清理了 {removed} 个过期备份（保留最近 {retention_days} 天）")


# ============================================================
# 数据保留策略
# ============================================================

def apply_retention_policies() -> dict:
    """按配置清理过期数据，防止数据库无限膨胀。

    清理规则：
    - task_logs: 超过 retention.task_logs_days 的日志（与任务状态无关）
    - generation_tasks: 超过 retention.tasks_days 且已结束的任务
      （状态为 succeeded / failed / cancelled；running 中的任务绝不删除）

    Returns:
        {"logs_deleted": int, "tasks_deleted": int}
    """
    from sqlalchemy import delete
    from sqlmodel import Session, select

    from app.core.config import get_settings
    from app.db import get_engine
    from app.models import GenerationTask, TaskLog

    settings = get_settings()
    result = {"logs_deleted": 0, "tasks_deleted": 0}
    engine = get_engine()

    # ---- 1. 清理过期 task_logs ----
    if settings.retention.task_logs_days > 0:
        log_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention.task_logs_days)
        try:
            with Session(engine, expire_on_commit=False) as session:
                # 先统计数量（给用户可观察的指标）
                count_stmt = (
                    select(GenerationTask.id)
                    .where(GenerationTask.created_at < log_cutoff)
                )
                # 直接用子查询删，避免加载到内存
                from sqlalchemy import func
                log_count = session.exec(
                    select(func.count()).select_from(TaskLog).where(TaskLog.created_at < log_cutoff)
                ).one()

                session.exec(
                    delete(TaskLog).where(TaskLog.created_at < log_cutoff)
                )
                session.commit()
                result["logs_deleted"] = log_count or 0
                if result["logs_deleted"]:
                    logger.info(f"[retention] 清理了 {result['logs_deleted']} 条过期任务日志（>{settings.retention.task_logs_days} 天）")
        except Exception as e:
            logger.error(f"[retention] 清理 task_logs 失败: {e}")

    # ---- 2. 清理过期已结束任务 ----
    if settings.retention.tasks_days > 0:
        task_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention.tasks_days)
        terminal_statuses = ["succeeded", "failed", "cancelled"]
        try:
            with Session(engine, expire_on_commit=False) as session:
                from sqlalchemy import func
                task_count = session.exec(
                    select(func.count())
                    .select_from(GenerationTask)
                    .where(
                        GenerationTask.created_at < task_cutoff,
                        GenerationTask.status.in_(terminal_statuses),
                    )
                ).one()

                if task_count and task_count > 0:
                    # 先解绑关联的素材（保留文件，只清 FK）
                    from sqlalchemy import update
                    from app.models import Asset

                    old_task_ids_stmt = (
                        select(GenerationTask.id)
                        .where(
                            GenerationTask.created_at < task_cutoff,
                            GenerationTask.status.in_(terminal_statuses),
                        )
                    )
                    # 用子查询批量解绑
                    session.exec(
                        update(Asset)
                        .where(Asset.task_id.in_(old_task_ids_stmt))
                        .values(task_id=None)
                    )
                    # 删除关联日志
                    session.exec(
                        delete(TaskLog).where(TaskLog.task_id.in_(old_task_ids_stmt))
                    )
                    # 删除任务本身
                    session.exec(
                        delete(GenerationTask)
                        .where(
                            GenerationTask.created_at < task_cutoff,
                            GenerationTask.status.in_(terminal_statuses),
                        )
                    )
                    session.commit()
                    result["tasks_deleted"] = task_count
                    logger.info(f"[retention] 清理了 {task_count} 个过期已结束任务（>{settings.retention.tasks_days} 天）")
        except Exception as e:
            logger.error(f"[retention] 清理 generation_tasks 失败: {e}")

    # ---- 3. 清理过期性能监控数据 ----
    # perf 数据保留 7 天，与 task_logs 同策略，防止 perf_events 无限膨胀
    _PERF_RETENTION_DAYS = 7
    try:
        perf_cutoff = datetime.now(timezone.utc) - timedelta(days=_PERF_RETENTION_DAYS)
        from app.models.perf import PerfEvent, PerfSession, PerfAlert

        with Session(engine, expire_on_commit=False) as session:
            # 先清理过期 session（关联的 events/alerts 通过 session_id 级联删除）
            old_session_ids = session.exec(
                select(PerfSession.session_id).where(PerfSession.created_at < perf_cutoff)
            ).all()
            if old_session_ids:
                session.exec(delete(PerfAlert).where(PerfAlert.session_id.in_(old_session_ids)))
                session.exec(delete(PerfEvent).where(PerfEvent.session_id.in_(old_session_ids)))
                session.exec(delete(PerfSession).where(PerfSession.created_at < perf_cutoff))
                session.commit()
                result["perf_sessions_deleted"] = len(old_session_ids)
                logger.info(f"[retention] 清理了 {len(old_session_ids)} 个过期性能监控会话（>{_PERF_RETENTION_DAYS} 天）")
    except Exception as e:
        logger.error(f"[retention] 清理 perf 数据失败: {e}")

    if not any(result.values()):
        logger.info("[retention] 没有需要清理的过期数据")

    return result


# ============================================================
# WAL Checkpoint
# ============================================================

def wal_checkpoint(mode: str = "TRUNCATE") -> bool:
    """执行 SQLite WAL checkpoint，防止 WAL 文件无限增长。

    WAL 模式下，写操作只追加到 -wal 文件，不直接修改主 DB。
    定期 checkpoint 将 WAL 内容合并回主 DB，并清空 WAL 文件。

    Modes:
        PASSIVE:  尽量 checkpoint，不锁库，允许读者继续
        FULL:     checkpoint 后重置 WAL，阻塞新写操作
        RESTART:  同 FULL，并重置 WAL 帧计数
        TRUNCATE: 同 RESTART，并将 WAL 文件截断为 0 字节（推荐，最彻底）

    Returns:
        True 成功，False 失败或不适用。
    """
    from app.core.config import get_settings
    from app.db import get_engine

    settings = get_settings()
    if not settings.database.url.startswith("sqlite"):
        return False

    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                __import__("sqlalchemy").text(f"PRAGMA wal_checkpoint({mode})")
            ).fetchone()
            # result: (busy, log, checkpointed) - busy=1 表示有写锁导致未完成
            if result and result[0] == 0:
                logger.info(f"WAL checkpoint({mode}) 完成: log={result[1]}, checkpointed={result[2]}")
                return True
            else:
                logger.warning(f"WAL checkpoint({mode}) 未能完全执行（数据库繁忙）: {result}")
                return False
    except Exception as e:
        logger.error(f"WAL checkpoint 失败: {e}")
        return False


# ============================================================
# 启动时一键执行
# ============================================================

def run_startup_maintenance() -> dict:
    """启动时一键维护：备份 + 保留策略 + WAL checkpoint。

    在 main.py lifespan 中调用，确保每次重启都执行基础维护。
    每个步骤独立容错，单个失败不影响其他步骤。

    Returns:
        维护结果摘要 dict
    """
    report = {
        "backup": None,
        "retention": {},
        "wal_checkpoint": False,
    }

    # 1. 备份
    try:
        backup_path = backup_database()
        report["backup"] = str(backup_path) if backup_path else "skipped"
    except Exception as e:
        logger.error(f"[maintenance] 备份步骤异常: {e}")
        report["backup"] = f"error: {e}"

    # 2. 保留策略
    try:
        report["retention"] = apply_retention_policies()
    except Exception as e:
        logger.error(f"[maintenance] 保留策略步骤异常: {e}")
        report["retention"] = {"error": str(e)}

    # 3. WAL checkpoint
    try:
        report["wal_checkpoint"] = wal_checkpoint()
    except Exception as e:
        logger.error(f"[maintenance] WAL checkpoint 步骤异常: {e}")
        report["wal_checkpoint"] = f"error: {e}"

    logger.info(f"[maintenance] 启动维护完成: {report}")
    return report
