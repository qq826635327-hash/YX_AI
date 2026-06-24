"""任务执行器 — 调用 AI API 生成图片/视频。

集成结构化日志 + trace_id，全链路可追踪：
  ref_collect → generate → download → save → backfill
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


def _select_provider_model(provider, target_type: str) -> str | None:
    """从 Provider 的多模型中，按目标类型和标签选择最合适的模型。

    Returns:
        匹配到的模型名，或 None（标签匹配不到时不盲目兜底，由调用方处理）。
    """
    models = sorted(provider.models or [], key=lambda m: m.sort_order)
    if not models:
        return provider.model or ""

    # 按目标类型推断优先标签
    preferred_tag = None
    if target_type == "shot_video":
        preferred_tag = "video_generation"
    elif target_type in ("character", "scene", "prop", "shot_first_frame", "shot_last_frame"):
        preferred_tag = "image_generation"

    if preferred_tag:
        for m in models:
            if preferred_tag in (m.tags or []):
                return m.model_name
        # 标签匹配不到时，不盲目返回第一个模型（可能不支持当前任务）
        logger.warning(f"_select_provider_model: Provider 无标签为 {preferred_tag} 的模型，返回 None")
        return None

    # 无标签偏好时，返回第一个模型作为兜底
    return models[0].model_name


from app.clients.agnes_client import async_download_file
from app.core.config import get_settings
from app.core.trace import new_trace_id, get_trace_id, set_trace_id, clear_trace_id
from app.db import session_scope
from app.models import ApiProvider, Character, Project, Prop, Scene
from app.models.task import GenerationTask
from app.providers import get_handler, get_handler_class
from app.services.asset_service import create_asset_record, get_project_root
from app.services.business_service import sanitize_name, get_entity_dirname, TARGET_TYPE_DIR_MAP
from app.services.config_service import decrypt_secret
from app.services.generation_service import get_task, update_task_status
from app.services.task_log_service import (
    write_task_log,
    log_api_call,
    log_ref_collect,
    log_download,
)
from app.ws.routes import push_task_completed, push_task_failed, push_task_progress

logger = logging.getLogger(__name__)

# ============================================================
# 任务取消事件管理（内存中标记，执行器定期检查）
# ============================================================

_task_cancel_events: Dict[str, asyncio.Event] = {}


def get_cancel_event(task_id: str) -> asyncio.Event:
    """获取（或创建）任务的取消事件。"""
    if task_id not in _task_cancel_events:
        _task_cancel_events[task_id] = asyncio.Event()
    return _task_cancel_events[task_id]


def request_task_cancel(task_id: str) -> None:
    """请求取消指定任务（由 cancel API 调用）。"""
    event = get_cancel_event(task_id)
    event.set()


def clear_cancel_event(task_id: str) -> None:
    """任务结束后清理取消事件，避免内存泄漏。"""
    _task_cancel_events.pop(task_id, None)


def _auto_fill_entity(session, target_type: str, target_id: str, asset_id: str) -> None:
    """根据 target_type 自动回填素材 ID 与生成状态到对应实体。

    注意：不在此函数内 commit，由调用方统一提交，避免破坏外层事务边界。
    """
    try:
        if target_type == "character":
            e = session.get(Character, target_id)
            if e:
                e.image_asset_id = asset_id
                e.gen_status = "ready"
                session.add(e)
                logger.info(f"自动回填 Character {e.name} image_asset_id={asset_id}")
        elif target_type == "scene":
            e = session.get(Scene, target_id)
            if e:
                e.image_asset_id = asset_id
                e.gen_status = "ready"
                session.add(e)
                logger.info(f"自动回填 Scene {e.name} image_asset_id={asset_id}")
        elif target_type == "prop":
            e = session.get(Prop, target_id)
            if e:
                e.image_asset_id = asset_id
                e.gen_status = "ready"
                session.add(e)
                logger.info(f"自动回填 Prop {e.name} image_asset_id={asset_id}")
        elif target_type == "shot_first_frame":
            from app.models import Shot
            e = session.get(Shot, target_id)
            if e:
                e.first_frame_asset_id = asset_id
                e.first_frame_status = "ready"
                session.add(e)
        elif target_type == "shot_last_frame":
            from app.models import Shot
            e = session.get(Shot, target_id)
            if e:
                e.last_frame_asset_id = asset_id
                e.last_frame_status = "ready"
                session.add(e)
        elif target_type == "shot_video":
            from app.models import Shot
            e = session.get(Shot, target_id)
            if e:
                e.video_asset_id = asset_id
                e.video_status = "ready"
                session.add(e)
        # 不在此处 commit，由调用方统一提交
    except Exception as ex:
        logger.warning(f"自动回填失败: {ex}")


def _get_prompt_from_entity(session, target_type: str, target_id: str) -> str:
    """从实体获取提示词（优先用 input_payload.prompt，否则用实体描述）。"""
    from app.models import Shot

    try:
        if target_type == "character":
            e = session.get(Character, target_id)
            return (e.description or e.settings or e.name) if e else "一个角色"
        elif target_type == "scene":
            e = session.get(Scene, target_id)
            return (e.description or e.name) if e else "一个场景"
        elif target_type == "prop":
            e = session.get(Prop, target_id)
            return (e.description or e.name) if e else "一个道具"
        elif target_type.startswith("shot_"):
            e = session.get(Shot, target_id)
            if e:
                if target_type == "shot_first_frame" and e.first_frame_prompt:
                    return e.first_frame_prompt
                if target_type == "shot_last_frame" and e.last_frame_prompt:
                    return e.last_frame_prompt
                if target_type == "shot_video" and e.video_prompt:
                    return e.video_prompt
                return e.summary or f"分镜 {e.shot_no}"
            return "一个分镜"
    except Exception:
        pass
    return "生成一个图片"


def _file_to_data_uri(file_path: Path) -> tuple[str, bytes] | None:
    """将图片文件转为 Data URI Base64，返回 (data_uri, file_bytes)。"""
    import base64

    if not file_path.exists():
        return None
    try:
        file_bytes = file_path.read_bytes()
        b64 = base64.b64encode(file_bytes).decode("ascii")
        ext = file_path.suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(ext, "image/png")
        return f"data:{mime};base64,{b64}", file_bytes
    except (OSError, PermissionError):
        return None


def _collect_reference_images(
    session, target_type: str, target_id: str, project_root: Path,
    reference_types: list[str] | None = None,
) -> dict:
    """按目标类型自动收集参考图片。

    逻辑：
    - 首帧生成：收集关联的角色/场景/道具参考图
    - 尾帧生成：收集首帧图 + 关联的角色/场景/道具参考图
    - 视频生成：根据 reference_types 过滤收集（仅 shot_video 受此参数影响）
    - 非分镜目标（角色/场景/道具）：不收集参考图
    - 没有关联实体也没有首尾帧：返回空，走文生图

    Args:
        reference_types: 视频生成时参考图类型过滤，如 ["first_frame", "last_frame"]。
                         仅对 shot_video 生效，None 表示使用默认逻辑（全收集）。

    优先级排序：首帧 > 角色 > 场景 > 道具，超出5张截断

    Returns:
        {
            "data_uris": ["data:image/png;base64,..."],
            "details": [{"type": "character", "label": "角色:张三", "file": "...", "size_kb": 123}],
            "refs": [{"asset_id": "...", "type": "character", "label": "角色:张三", "data_uri": "..."}],
        }
    """
    import base64
    from sqlmodel import select
    from app.models import Asset, Shot
    from app.models.shot_reference import ShotCharacter, ShotScene, ShotProp

    # 优先级：首帧(0) > 角色(1) > 场景(2) > 道具(3)
    PRIORITY_MAP = {"first_frame": 0, "last_frame": 0, "character": 1, "scene": 2, "prop": 3}
    MAX_REFERENCE_IMAGES = 5

    empty = {"data_uris": [], "details": [], "refs": []}

    if not target_type.startswith("shot_"):
        return empty

    shot = session.get(Shot, target_id)
    if not shot:
        return empty

    # 候选来源：(asset_id, type, label)
    candidates: list[tuple[str, str, str]] = []

    # 尾帧生成时，首帧图作为参考
    if target_type == "shot_last_frame" and shot.first_frame_asset_id:
        candidates.append((shot.first_frame_asset_id, "first_frame", "首帧"))

    # 视频生成时，首帧图 + 尾帧图作为参考
    if target_type == "shot_video":
        if shot.first_frame_asset_id:
            candidates.append((shot.first_frame_asset_id, "first_frame", "首帧"))
        if shot.last_frame_asset_id:
            candidates.append((shot.last_frame_asset_id, "last_frame", "尾帧"))

    # 所有分镜目标：收集关联的角色/场景/道具参考图
    for ref in session.exec(select(ShotCharacter).where(ShotCharacter.shot_id == target_id)).all():
        char = session.get(Character, ref.character_id)
        if char and char.image_asset_id:
            candidates.append((char.image_asset_id, "character", f"角色:{char.name}"))

    for ref in session.exec(select(ShotScene).where(ShotScene.shot_id == target_id)).all():
        scene = session.get(Scene, ref.scene_id)
        if scene and scene.image_asset_id:
            candidates.append((scene.image_asset_id, "scene", f"场景:{scene.name}"))

    for ref in session.exec(select(ShotProp).where(ShotProp.shot_id == target_id)).all():
        prop = session.get(Prop, ref.prop_id)
        if prop and prop.image_asset_id:
            candidates.append((prop.image_asset_id, "prop", f"道具:{prop.name}"))

    # 按优先级排序：首帧 > 角色 > 场景 > 道具
    candidates.sort(key=lambda c: PRIORITY_MAP.get(c[1], 99))

    # 视频生成时，按 reference_types 过滤候选（仅 shot_video 受影响）
    if target_type == "shot_video" and reference_types is not None:
        type_set = set(reference_types)
        before_count = len(candidates)
        candidates = [c for c in candidates if c[1] in type_set]
        if before_count != len(candidates):
            logger.info(f"视频参考图过滤：{before_count} → {len(candidates)}（reference_types={reference_types}）")

    data_uris: list[str] = []
    details: list[dict] = []
    refs: list[dict] = []

    seen_asset_ids: set[str] = set()
    for asset_id, ref_type, label in candidates:
        # 超出5张截断
        if len(data_uris) >= MAX_REFERENCE_IMAGES:
            logger.info(f"参考图已达上限 {MAX_REFERENCE_IMAGES} 张，跳过剩余: {label}")
            break

        if asset_id in seen_asset_ids:
            continue
        seen_asset_ids.add(asset_id)

        asset = session.get(Asset, asset_id)
        if not asset or not asset.file_path:
            continue
        file_path = project_root / asset.file_path.replace("/", os.sep)
        result = _file_to_data_uri(file_path)
        if not result:
            logger.warning(f"参考图文件不存在或读取失败: {file_path}")
            continue
        data_uri, file_bytes = result

        data_uris.append(data_uri)
        details.append({
            "type": ref_type,
            "label": label,
            "file": file_path.name,
            "size_kb": len(file_bytes) // 1024,
        })
        refs.append({
            "asset_id": asset_id,
            "type": ref_type,
            "label": label,
            "data_uri": data_uri,
        })
        logger.info(f"已收集参考图: {label} ({file_path.name}, {len(file_bytes)//1024}KB)")

    if len(candidates) > MAX_REFERENCE_IMAGES:
        logger.info(f"参考图候选 {len(candidates)} 张，截断至 {MAX_REFERENCE_IMAGES} 张")

    return {"data_uris": data_uris, "details": details, "refs": refs}


def _build_reference_prompt(original_prompt: str, refs: list[dict]) -> str:
    """根据配置自动拼接参考图描述行到 prompt。"""
    cfg = get_settings().reference_prompt
    if not cfg.enabled or not refs:
        return original_prompt

    items = cfg.separator.join(
        cfg.item_template.format(index=i + 1, label=ref["label"])
        for i, ref in enumerate(refs)
    )
    items = items + cfg.item_terminator

    rendered = cfg.template.format(items=items, original_prompt=original_prompt)
    return rendered.strip()


def _find_fallback_handler(
    session,
    exclude_provider_id: str,
    target_type: str,
    task_id: str,
):
    """智能降级：查找备选 Provider 并构建 Handler。

    策略：在所有 enabled 的 Provider 中，排除当前失败的，
    找到第一个拥有匹配 asset_type 标签模型的 Provider，构建 Handler。

    Returns:
        (handler, provider_kind, model_name, db_param_specs) 或 None
    """
    from sqlalchemy.orm import selectinload
    from sqlmodel import select as sqlmodel_select

    # 目标类型 → 需要的模型标签
    tag_map = {
        "shot_video": "video_generation",
        "character": "image_generation",
        "scene": "image_generation",
        "prop": "image_generation",
        "shot_first_frame": "image_generation",
        "shot_last_frame": "image_generation",
    }
    required_tag = tag_map.get(target_type)

    stmt = (
        sqlmodel_select(ApiProvider)
        .where(ApiProvider.enabled == True, ApiProvider.id != exclude_provider_id)
        .options(selectinload(ApiProvider.models))
    )
    providers = session.exec(stmt).all()

    for prov in providers:
        models = sorted(prov.models or [], key=lambda m: m.sort_order)
        # 按标签匹配
        fallback_model = None
        if required_tag:
            fallback_model = next(
                (m for m in models if required_tag in (m.tags or [])),
                None,
            )
        # 标签未匹配到，跳过此 Provider（避免降级到不支持对应功能的 Provider）
        if not fallback_model:
            continue

        handler_cls = get_handler_class(prov.provider_kind)
        if not handler_cls:
            continue

        api_key = decrypt_secret(prov.api_key_encrypted)
        handler = handler_cls(
            api_key=api_key,
            base_url=prov.base_url,
            timeout=prov.timeout_seconds,
        )
        write_task_log(task_id, "INFO",
            f"智能降级：切换到备选 Provider [{prov.name}] 模型 [{fallback_model.model_name}]",
            phase="generate", event_type="fallback",
            data_json={
                "fallback_provider": prov.name,
                "fallback_model": fallback_model.model_name,
                "original_provider_id": exclude_provider_id,
            },
        )
        return (
            handler,
            prov.provider_kind,
            fallback_model.model_name,
            fallback_model.param_specs,
        )

    return None


# ── 自动重试相关 ──────────────────────────────────────────
# 追踪每个任务的自动重试协程，用于手动重试时取消
_auto_retry_tasks: Dict[str, asyncio.Task] = {}


def _is_url_expired_error(err: Exception) -> bool:
    """检测是否为 URL 过期相关的错误（HTTP 403/410/404）。

    使用词边界匹配避免误判（如 "Error 4034" 不会匹配 403）。
    """
    import re
    err_str = str(err).lower()
    # 精确匹配 HTTP 状态码（词边界）和明确的过期/禁止关键词
    if re.search(r'\b40[34]\b', err_str) or re.search(r'\b410\b', err_str):
        return True
    if any(k in err_str for k in ["expired", "forbidden", "not found"]):
        return True
    return False


def _clear_result_urls_if_expired(task_id: str, dl_err: Exception, url_str: str, asset_label: str) -> None:
    """下载失败时检测 URL 是否过期，过期则清除 _result_urls（下次重试重新轮询/调 API）。

    保留 _video_task_id：如果 API 已提交，重试时可通过 video_id 重新轮询获取新 URL，
    而非重新提交一个全新的视频任务。
    """
    if not _is_url_expired_error(dl_err):
        return
    with session_scope() as sess:
        t = sess.get(GenerationTask, task_id)
        if t and t.input_payload and "_result_urls" in t.input_payload:
            t.input_payload.pop("_result_urls", None)
            # 保留 _video_task_id，重试时可恢复轮询而非重新提交
            sess.add(t)
            sess.commit()
    write_task_log(
        task_id, "WARNING", f"{asset_label} URL 已过期，下次重试将重新获取 URL",
        phase="download", event_type="url_expired",
        data_json={"url": url_str[:200], "error": str(dl_err)[:200]},
        push_ws=True,
    )


def cancel_auto_retry(task_id: str) -> None:
    """取消指定任务的自动重试协程（手动重试时调用）。"""
    pending = _auto_retry_tasks.pop(task_id, None)
    if pending and not pending.done():
        pending.cancel()
        logger.info(f"已取消任务 {task_id} 的自动重试协程")


async def _handle_task_failure(task_id: str, error: str, traceback_str: str = "", target_type: str = "") -> None:
    """任务失败后的处理：判断是否自动重试，否则标记为最终失败。

    自动重试条件：
    1. input_payload._result_urls 存在（API 已成功返回 URL）
    2. auto_retry_count < auto_retry_max_attempts
    3. 任务创建时间未超过 task_max_age_minutes
    """
    from app.core.config import get_settings
    settings = get_settings()

    with session_scope() as session:
        task = session.get(GenerationTask, task_id)
        if not task:
            await _safe_mark_task_failed(task_id, status="failed", error=error, traceback=traceback_str)
            return

        result_urls = (task.input_payload or {}).get("_result_urls")
        video_task_id = (task.input_payload or {}).get("_video_task_id")
        # task.created_at 从 SQLite 读取时是 naive datetime，统一替换为 UTC 再计算年龄
        if task.created_at:
            created_aware = task.created_at.replace(tzinfo=timezone.utc) if task.created_at.tzinfo is None else task.created_at
            age_minutes = (datetime.now(timezone.utc) - created_aware).total_seconds() / 60
        else:
            age_minutes = 0

        can_auto_retry = (
            settings.tasks.auto_retry_on_download_fail
            and (result_urls or video_task_id)  # API 已成功返回 URL 或已提交待轮询
            and task.auto_retry_count < settings.tasks.auto_retry_max_attempts
            and age_minutes < settings.tasks.task_max_age_minutes
        )

        if can_auto_retry:
            # 自动重试：重置为 pending，延迟后重新执行
            task.auto_retry_count += 1
            task.status = "pending"
            task.progress = 0
            task.error_message = f"自动重试中（第{task.auto_retry_count}次）: {error[:200]}"
            task.started_at = None
            task.finished_at = None
            session.add(task)
            session.commit()

            delay = 10 * task.auto_retry_count  # 10s, 20s, 30s
            write_task_log(
                task_id, "INFO",
                f"API 已成功但后续步骤失败，{delay}s 后自动重试（第{task.auto_retry_count}次）",
                phase="system", event_type="auto_retry",
                data_json={"retry_count": task.auto_retry_count, "delay": delay, "error": error[:200]},
                push_ws=True,
            )

            # 推送 WS 让前端看到状态变化
            await push_task_failed(task_id, f"自动重试中（第{task.auto_retry_count}次）", target_type=target_type)

            # 取消之前的自动重试协程（如果有）
            cancel_auto_retry(task_id)

            # 延迟后重新执行
            async def _delayed_retry():
                try:
                    await asyncio.sleep(delay)
                    from app.api.generate import _spawn_task
                    _spawn_task(execute_task_async(task_id))
                except asyncio.CancelledError:
                    logger.info(f"任务 {task_id} 的自动重试被取消")
                finally:
                    _auto_retry_tasks.pop(task_id, None)

            t = asyncio.create_task(_delayed_retry())
            _auto_retry_tasks[task_id] = t
            logger.info(f"任务 {task_id} 将在 {delay}s 后自动重试（第{task.auto_retry_count}次）")
        else:
            # 最终失败
            await _safe_mark_task_failed(task_id, status="failed", error=error, traceback=traceback_str)
            await push_task_failed(task_id, error[:200], target_type=target_type)


async def _safe_mark_task_failed(
    task_id: str,
    status: str = "failed",
    error: str = "",
    traceback: str = "",
) -> None:
    """安全地将任务标记为失败/取消，防止 database is locked 级联崩溃。

    busy_timeout=30000 已在引擎层设置，SQLite 会自动等待锁释放。
    这里只做 3 次轻量重试 + 裸 SQL 兜底，确保 except 块中不会再抛异常。
    使用 asyncio.sleep 避免阻塞事件循环。
    """
    for attempt in range(3):
        try:
            with session_scope() as session:
                update_task_status(session, task_id, status=status, error=error)
                write_task_log(
                    task_id, "ERROR" if status == "failed" else "INFO",
                    f"任务状态更新为 {status}" + (f": {error[:200]}" if error else ""),
                    data=traceback[:500] if traceback else None,
                    phase="system", event_type="system",
                    data_json={"error": error[:500], "traceback": traceback[:1000]} if traceback else {"error": error[:500]},
                )
            return  # 成功，退出
        except Exception as e:
            if attempt < 2:
                logger.warning(f"_safe_mark_task_failed 失败，重试 {attempt + 1}/3 (task={task_id}): {e}")
                # 异步等待，不阻塞事件循环
                await asyncio.sleep(0.1)
            else:
                # 最终兜底：直接用裸 SQL 尝试更新，不走 ORM
                logger.error(f"_safe_mark_task_failed 最终失败 (task={task_id}): {e}")
                try:
                    from sqlalchemy import text as sa_text
                    from app.db import get_engine
                    engine = get_engine()
                    with engine.connect() as conn:
                        conn.execute(
                            sa_text("UPDATE generation_tasks SET status=:s, error_message=:e, finished_at=:f WHERE id=:id"),
                            {"s": status, "e": error[:500], "f": datetime.now(timezone.utc).isoformat(), "id": task_id},
                        )
                        conn.commit()
                    logger.info(f"_safe_mark_task_failed 兜底 SQL 更新成功 (task={task_id})")
                except Exception as fallback_err:
                    # 彻底放弃，只记日志。下次启动 recover_orphan_tasks 会兜底
                    logger.error(f"_safe_mark_task_failed 兜底也失败 (task={task_id}): {fallback_err}")
                return


async def execute_task_async(task_id: str) -> None:
    """执行生成任务（后台）。

    流程：
    1. 等待 API handler 的 session 释放（避免 SQLite 锁冲突）
    2. 读取上下文 + 准备参数（一个 session）
    3. 调用 AI API 生成图片（结构化日志记录）
    4. 下载结果 + 保存记录（结构化日志记录）
    """
    cancel_event = get_cancel_event(task_id)
    trace_id = new_trace_id()  # 为整个任务分配 trace_id
    target_type = ""  # 提升到函数级别，供 except 块中的 WS 推送使用

    try:
        # 整体超时保护：任务执行超过 30 分钟自动标记为失败
        return await asyncio.wait_for(
            _execute_task_inner(task_id, cancel_event, trace_id),
            timeout=1800.0,  # 30 分钟
        )
    except asyncio.TimeoutError:
        await _handle_task_failure(task_id, "任务执行超时（30分钟）", target_type=target_type)
        logger.error(f"任务 {task_id} 执行超时（30分钟）")
    except asyncio.CancelledError:
        await _safe_mark_task_failed(task_id, status="cancelled", error="用户取消任务")
        await push_task_failed(task_id, "任务已取消", target_type=target_type)
        logger.info(f"任务 {task_id} 被取消")
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"任务 {task_id} 失败: {e}")
        logger.error(error_detail)
        await _handle_task_failure(task_id, str(e)[:500], traceback_str=error_detail[:1000], target_type=target_type)
    finally:
        clear_cancel_event(task_id)
        clear_trace_id()
        logger.info(f"任务 {task_id} 执行结束")


async def _execute_task_inner(task_id: str, cancel_event: asyncio.Event, trace_id: str) -> None:
    """任务执行核心逻辑（被 execute_task_async 包装，提供超时和异常处理）。"""
    set_trace_id(trace_id)
    # 等待 API handler 的 session 释放，避免 SQLite 锁冲突
    # API handler 在 spawn_task 后才返回响应、关闭 session，
    # 如果立即写同一行会导致 "database is locked"
    await asyncio.sleep(0.2)

    # ── 阶段 1：读取上下文 + 准备参数 ──────
    with session_scope() as session:
        # 注意：不再重复 update_task_status(running, 5)，
        # API handler 已经设置过了，重复写同一行会导致 SQLite 锁冲突
        write_task_log(task_id, "INFO", "任务开始执行",
            phase="system", event_type="system",
        )

        task = get_task(session, task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        project_id = task.project_id
        target_type = task.target_type  # 赋值给外层变量
        target_id = task.target_id
        input_payload = task.input_payload or {}
        asset_type = input_payload.get("asset_type", "image")
        provider_id = getattr(task, "provider_id", None)

        # 获取提示词
        prompt = input_payload.get("prompt")
        if not prompt:
            prompt = _get_prompt_from_entity(session, target_type, target_id)
            write_task_log(
                session, task_id, "INFO", f"使用默认提示词: {prompt[:100]}...",
                phase="validate", event_type="validate",
                data_json={"prompt_source": "entity", "prompt_preview": prompt[:200]},
            )
        else:
            write_task_log(
                session, task_id, "INFO", f"使用用户输入提示词: {prompt[:100]}...",
                phase="validate", event_type="validate",
                data_json={"prompt_source": "user_input", "prompt_preview": prompt[:200]},
            )

        # 首帧校验：尾帧和视频生成必须有首帧
        from app.models import Shot as _Shot
        if target_type in ("shot_last_frame", "shot_video"):
            shot = session.get(_Shot, target_id)
            if shot and not shot.first_frame_asset_id:
                error_msg = f"{'尾帧' if target_type == 'shot_last_frame' else '视频'}生成需要先有首帧，请先生成首帧"
                write_task_log(
                    session, task_id, "ERROR", error_msg,
                    phase="validate", event_type="validate",
                )
                raise ValueError(error_msg)

        # 获取项目根目录 + 实体名 + 模块目录
        project_root = get_project_root(project_id, session)
        if not project_root:
            raise ValueError(f"找不到项目 {project_id} 的根目录")

        # 确定文件类型 & 目录结构
        if asset_type == "video" or target_type == "shot_video":
            asset_type_str = "video"
            category = "shot_video" if target_type.startswith("shot_") else target_type
            ext = ".mp4"
        else:
            asset_type_str = "image"
            if target_type == "shot_first_frame":
                category = "first_frame"
            elif target_type == "shot_last_frame":
                category = "last_frame"
            else:
                category = target_type
            ext = ".png"

        # 计算输出子目录
        if target_type.startswith("shot_"):
            # 分镜资产：剧集/第X集/分镜NNN/首帧|尾帧|视频/
            from app.models import Episode as _Episode
            shot = session.get(_Shot, target_id)
            if not shot:
                raise ValueError(f"找不到分镜 {target_id}")
            ep = session.get(_Episode, shot.episode_id)
            if not ep:
                raise ValueError(f"找不到剧集 {shot.episode_id}")
            ep_dir = f"第{ep.episode_no}集"
            shot_dir = f"分镜{shot.shot_no:03d}"
            if target_type == "shot_first_frame":
                sub_dir_name = "首帧"
            elif target_type == "shot_last_frame":
                sub_dir_name = "尾帧"
            else:
                sub_dir_name = "视频"
            sub_dir = Path("剧集") / ep_dir / shot_dir / sub_dir_name
        else:
            # 角色/场景/道具：角色|场景|道具/实体名/images/
            entity_name = get_entity_dirname(session, target_type, target_id) or target_id[:8]
            module_dir = TARGET_TYPE_DIR_MAP.get(target_type, "其他")
            sub_dir = Path(module_dir) / entity_name / "images"

        target_dir = project_root / sub_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        base_name = f"gen_{int(time.time())}_{task_id[:8]}"
        file_name = base_name + ext
        output_path = target_dir / file_name

        # 路径穿越校验
        if not output_path.resolve().is_relative_to(project_root.resolve()):
            raise ValueError(f"输出路径非法（路径穿越）: {output_path}")

        # 防止重名
        counter = 1
        while output_path.exists():
            file_name = f"{base_name}_{counter}{ext}"
            output_path = target_dir / file_name
            counter += 1

        # 获取 Provider Handler
        provider_kind = None
        handler = None
        provider_model = None
        db_param_specs = None  # DB 中的 param_specs（数据驱动）
        db_capabilities = None  # DB 中的 capabilities（数据驱动）

        if provider_id:
            from sqlalchemy.orm import selectinload
            from sqlmodel import select as sqlmodel_select

            stmt = sqlmodel_select(ApiProvider).where(ApiProvider.id == provider_id).options(selectinload(ApiProvider.models))
            provider = session.exec(stmt).first()
            if provider:
                provider_kind = provider.provider_kind
                provider_model = _select_provider_model(provider, target_type)
                # 提取 DB 中的 param_specs 和 capabilities（数据驱动，优先于 Handler 代码）
                _model_record = next((m for m in (provider.models or []) if m.model_name == provider_model), None)
                if _model_record:
                    db_param_specs = _model_record.param_specs
                    db_capabilities = _model_record.capabilities
                handler_cls = get_handler_class(provider_kind)
                if handler_cls:
                    api_key = decrypt_secret(provider.api_key_encrypted)
                    handler = handler_cls(
                        api_key=api_key,
                        base_url=provider.base_url,
                        timeout=provider.timeout_seconds,
                    )
                    write_task_log(
                        session, task_id, "DEBUG",
                        f"使用 Handler: {handler_cls.__name__}, provider_model={provider_model}",
                        phase="validate", event_type="validate",
                        data_json={
                            "handler_class": handler_cls.__name__,
                            "provider_kind": provider_kind,
                            "provider_model": provider_model,
                        },
                    )
                else:
                    write_task_log(
                        session, task_id, "WARNING",
                        f"未找到 Handler: provider_kind={provider_kind}",
                        phase="validate", event_type="validate",
                    )
        else:
            # 无指定 Provider 时，根据默认模型配置自动选择
            from app.core.config import get_settings
            settings = get_settings()
            default_model_name = ""
            if target_type == "shot_video":
                default_model_name = settings.default_models.default_video_model
            elif target_type in ("character", "scene", "prop", "shot_first_frame", "shot_last_frame"):
                default_model_name = settings.default_models.default_image_model

            if default_model_name:
                # 在所有启用的 Provider 中查找拥有该模型的 Provider
                from sqlalchemy.orm import selectinload
                from sqlmodel import select as sqlmodel_select
                from app.models import ProviderModel

                stmt = (
                    sqlmodel_select(ApiProvider)
                    .where(ApiProvider.enabled == True)
                    .options(selectinload(ApiProvider.models))
                )
                all_providers = session.exec(stmt).all()

                for prov in all_providers:
                    matched_model = next(
                        (m for m in (prov.models or []) if m.model_name == default_model_name),
                        None,
                    )
                    if matched_model:
                        provider_id = prov.id
                        provider_kind = prov.provider_kind
                        provider_model = matched_model.model_name
                        db_param_specs = matched_model.param_specs
                        db_capabilities = matched_model.capabilities
                        handler_cls = get_handler_class(provider_kind)
                        if handler_cls:
                            api_key = decrypt_secret(prov.api_key_encrypted)
                            handler = handler_cls(
                                api_key=api_key,
                                base_url=prov.base_url,
                                timeout=prov.timeout_seconds,
                            )
                            write_task_log(
                                session, task_id, "INFO",
                                f"自动选择默认模型: Provider=[{prov.name}] 模型=[{provider_model}]",
                                phase="validate", event_type="auto_select",
                                data_json={
                                    "provider_id": str(prov.id),
                                    "provider_name": prov.name,
                                    "model": provider_model,
                                    "default_config": True,
                                },
                            )
                        break

        # 参数准备：合并 extra_params 和顶层的 size/count 等
        params = dict(input_payload.get("extra_params", input_payload.get("params", {})))
        # 将顶层的 size/count 等参数合并到 params（extra_params 中可能没有这些字段）
        for top_key in ("size", "count"):
            if top_key in input_payload and top_key not in params:
                params[top_key] = input_payload[top_key]
        if not params:
            size = input_payload.get("size", "1024x1024")
            params = {"size": size}

        model_name = input_payload.get("model") or provider_model or ""
        if not model_name:
            raise ValueError("未找到模型名：Provider 未配置 model，且 input_payload 未指定 model")

        # 尾帧 prompt 自动增强：基于首帧画面生成分镜结束时的画面
        if target_type == "shot_last_frame":
            last_frame_prefix = "基于首帧画面，生成分镜结束时的画面。"
            if not prompt.startswith(last_frame_prefix):
                original_prompt = prompt
                prompt = last_frame_prefix + prompt
                write_task_log(
                    session, task_id, "INFO",
                    "尾帧 prompt 已自动增强",
                    phase="validate", event_type="validate",
                    data_json={
                        "original_prompt": original_prompt[:200],
                        "enhanced_prompt": prompt[:200],
                    },
                )

        # ── 收集参考图片（图生图）──────────────────────────
        reference_images: list[str] = []
        ref_details: list[dict] = []
        structured_refs: list[dict] = []

        # 解析视频参考图类型过滤（仅 shot_video 生效）
        video_ref_types: list[str] | None = None
        if target_type == "shot_video":
            # 优先使用 extra_params.reference_types（用户手动选择）
            extra_params = input_payload.get("extra_params", {})
            ref_types_str = extra_params.get("reference_types", "")
            if ref_types_str:
                video_ref_types = [t.strip() for t in ref_types_str.split(",") if t.strip()]
            elif db_capabilities:
                # 回退到模型默认配置
                video_ref_types = db_capabilities.get("video_reference_types")
            # 如果都为空，video_ref_types 保持 None（全收集，兼容旧行为）

        # 自动收集：按目标类型决定收集哪些参考图
        if target_type.startswith("shot_") and project_root:
            auto_result = _collect_reference_images(
                session, target_type, target_id, project_root,
                reference_types=video_ref_types,
            )
            reference_images.extend(auto_result["data_uris"])
            ref_details.extend(auto_result["details"])
            structured_refs.extend(auto_result["refs"])
            if auto_result["data_uris"]:
                log_ref_collect(
                    task_id,
                    source="自动收集",
                    count=len(auto_result["data_uris"]),
                    details=auto_result["details"],
                )

        # 2. 从 input_payload.reference_asset_ids 手动收集
        ref_asset_ids = input_payload.get("reference_asset_ids", [])
        if ref_asset_ids and project_root:
            from app.models import Asset as AssetModel
            manual_details: list[dict] = []
            for ref_id in ref_asset_ids:
                asset = session.get(AssetModel, ref_id)
                if asset and asset.file_path:
                    fp = project_root / asset.file_path.replace("/", os.sep)
                    result = _file_to_data_uri(fp)
                    if result:
                        data_uri, fb = result
                        if data_uri not in reference_images:
                            reference_images.append(data_uri)
                            manual_details.append({
                                "type": "manual_ref",
                                "label": "参考图",
                                "file": fp.name,
                                "size_kb": len(fb) // 1024,
                            })
                            structured_refs.append({
                                "asset_id": ref_id,
                                "type": "manual_ref",
                                "label": "参考图",
                                "data_uri": data_uri,
                            })
            if manual_details:
                log_ref_collect(
                    task_id,
                    source="手动指定参考图",
                    count=len(manual_details),
                    details=manual_details,
                )

        # 3. 自动拼接参考图描述行到 prompt
        if structured_refs:
            original_prompt = prompt
            prompt = _build_reference_prompt(original_prompt, structured_refs)
            if prompt != original_prompt:
                write_task_log(
                    session, task_id, "INFO",
                    "已自动拼接参考图描述行到 prompt",
                    phase="generate", event_type="validate",
                    data_json={
                        "original_prompt": original_prompt[:200],
                        "final_prompt": prompt[:200],
                        "reference_count": len(structured_refs),
                    },
                )

        # 将参考图注入 params（供 Handler 使用）
        if reference_images:
            params["reference_images"] = reference_images
            write_task_log(
                session, task_id, "INFO",
                f"共 {len(reference_images)} 张参考图，将走图生图模式",
                phase="generate", event_type="validate",
                data_json={"reference_count": len(reference_images), "mode": "image_to_image"},
            )
        else:
            write_task_log(
                session, task_id, "INFO", "无参考图，走文生图模式",
                phase="generate", event_type="validate",
                data_json={"reference_count": 0, "mode": "text_to_image"},
            )

        # 将参考图详情和模型名回写到 input_payload，供前端展示
        task.input_payload = {
            **(task.input_payload or {}),
            "model": model_name,
            "ref_details": ref_details,
            "asset_type": asset_type_str,
        }
        session.add(task)

        update_task_status(session, task_id, status="running", progress=30)
        write_task_log(task_id, "INFO", "开始调用生成引擎...",
            phase="generate", event_type="system",
        )

    await push_task_progress(task_id, 5, message="准备参数...")
    await push_task_progress(task_id, 10, message="收集参考图...")
    await push_task_progress(task_id, 25, message="正在调用AI生成引擎...")

    # ── 阶段 2：调用 AI API ─────────────────────────────────
    image_urls = None
    video_urls = None
    api_start_time = time.monotonic()
    fallback_attempted = False
    # 从配置读取速率限制重试参数
    from app.core.config import get_settings
    _settings = get_settings()
    rate_limit_retry = 0
    max_rate_limit_retries = _settings.tasks.rate_limit_retry
    rate_limit_wait = _settings.tasks.rate_limit_wait
    smart_fallback = _settings.tasks.smart_fallback

    if asset_type_str == "video":
        # ── 视频生成 ──
        if not handler:
            raise ValueError(f"视频生成暂不支持 provider_kind={provider_kind}（需要对应的 Handler）")

        # 检查 Handler 是否支持视频生成
        # 优先用 DB 中的 capabilities，fallback 到 Handler 代码
        if db_capabilities:
            caps = db_capabilities
        else:
            caps = handler.get_capabilities(model_name)
        need_url = caps.get("reference_images_need_url", False)

        # 参考图分流：need_url=True → 上传图床获取公网 URL；否则用 base64
        if reference_images and need_url:
            await push_task_progress(task_id, 15, message="上传参考图到图床...")
            from app.services.image_hosting_service import get_or_upload_public_url
            from app.models import Asset as AssetModel

            public_urls: list[str] = []
            with session_scope() as session:
                # 从 structured_refs 中取出所有实际用到的参考图 asset_id
                upload_asset_ids = list(dict.fromkeys(
                    ref["asset_id"] for ref in structured_refs if ref.get("asset_id")
                ))

                for ref_aid in upload_asset_ids:
                    asset = session.get(AssetModel, ref_aid)
                    if asset and asset.file_path:
                        fp = project_root / asset.file_path.replace("/", os.sep)
                        if fp.exists():
                            try:
                                url = await get_or_upload_public_url(ref_aid, fp, session)
                                public_urls.append(url)
                                write_task_log(
                                    session, task_id, "INFO",
                                    f"参考图已上传图床: {fp.name} → {url[:80]}...",
                                    phase="generate", event_type="upload",
                                    data_json={"asset_id": ref_aid, "public_url": url[:200]},
                                )
                            except Exception as upload_err:
                                write_task_log(
                                    session, task_id, "ERROR",
                                    f"参考图上传图床失败: {fp.name}: {upload_err}",
                                    phase="generate", event_type="upload",
                                    data_json={"asset_id": ref_aid, "error": str(upload_err)[:200]},
                                )
                                raise ValueError(f"参考图上传图床失败: {upload_err}")

            # 用公网 URL 替换 base64 Data URI
            params["reference_images"] = public_urls
            await push_task_progress(task_id, 20, message="已打包发送API...")
            write_task_log(
                session, task_id, "INFO",
                f"视频模式：{len(public_urls)} 张参考图已转为公网 URL",
                phase="generate", event_type="validate",
                data_json={"reference_count": len(public_urls), "mode": "public_url"},
            )

        errors = handler.validate_params(model=model_name, params=params, param_specs_override=db_param_specs)
        if errors:
            raise ValueError(f"参数校验失败: {'; '.join(errors)}")

        await push_task_progress(task_id, 30, message="视频生成中（API轮询）...")

        if cancel_event.is_set():
            raise asyncio.CancelledError("用户取消任务")

        # 重试复用优先级：_result_urls（API 已返回最终 URL）> _video_task_id（API 已提交但轮询中断）
        _cached_urls = (input_payload or {}).get("_result_urls")
        _video_task_id = (input_payload or {}).get("_video_task_id")
        if _cached_urls and isinstance(_cached_urls, list) and len(_cached_urls) > 0:
            video_urls = _cached_urls
            write_task_log(
                task_id, "INFO",
                f"复用上次 API 已返回的 {len(video_urls)} 个视频 URL，跳过 API 调用",
                phase="generate", event_type="cache_hit",
                data_json={"url_count": len(video_urls), "first_url": str(video_urls[0])[:200]},
                push_ws=True,
            )
            await push_task_progress(task_id, 50, message="复用已有结果，准备下载...")
        else:
            # 定义回调：提交成功后立即保存 video_id 到 DB，防止中断丢失
            async def _on_video_submitted(vid: str) -> None:
                with session_scope() as sess:
                    t = sess.get(GenerationTask, task_id)
                    if t:
                        t.input_payload = {**(t.input_payload or {}), "_video_task_id": vid}
                        sess.add(t)
                        sess.commit()
                write_task_log(
                    task_id, "INFO",
                    f"视频任务已提交 API，video_id={vid}，已持久化到 DB",
                    phase="generate", event_type="video_submitted",
                    data_json={"video_id": vid},
                    push_ws=True,
                )

            # 支持智能降级的重试循环（最多 1 次降级）
            while True:
                try:
                    video_urls = await handler.generate_video(
                        model=model_name,
                        prompt=prompt,
                        params=params,
                        resume_video_id=_video_task_id,
                        on_submitted=_on_video_submitted,
                        timeout=getattr(handler, "_timeout", 120),
                    )
                    api_duration_ms = int((time.monotonic() - api_start_time) * 1000)

                    with session_scope() as session:
                        log_api_call(
                            task_id,
                            phase="generate",
                            provider_kind=provider_kind or "unknown",
                            model=model_name,
                            url=f"{handler._base_url}/v1/videos",
                            method="POST",
                            request_payload={"model": model_name, "prompt": prompt[:200]},
                            response_status=200,
                            response_body={"video_count": len(video_urls)},
                            duration_ms=api_duration_ms,
                        )
                    # API 成功：将返回的 URL 保存到 input_payload，供重试时复用
                    with session_scope() as sess:
                        t = sess.get(GenerationTask, task_id)
                        if t:
                            t.input_payload = {**(t.input_payload or {}), "_result_urls": [str(u) for u in video_urls]}
                            sess.add(t)
                            sess.commit()
                    break  # 成功，退出重试循环

                except Exception as api_err:
                    api_duration_ms = int((time.monotonic() - api_start_time) * 1000)
                    with session_scope() as session:
                        log_api_call(
                            task_id,
                            phase="generate",
                            provider_kind=provider_kind or "unknown",
                            model=model_name,
                            url=f"{handler._base_url}/v1/videos",
                            method="POST",
                            request_payload={"model": model_name, "prompt": prompt[:200]},
                            response_status=None,
                            duration_ms=api_duration_ms,
                            error=str(api_err)[:500],
                        )
                    # ── 智能降级：尝试备选 Provider（受开关控制）──
                    if smart_fallback and not fallback_attempted and provider_id:
                        fallback_attempted = True
                        await push_task_progress(task_id, 35, message="主引擎失败，正在寻找备选引擎...")
                        with session_scope() as fb_session:
                            fb = _find_fallback_handler(fb_session, provider_id, target_type, task_id)
                        if fb:
                            handler, provider_kind, model_name, db_param_specs = fb
                            api_start_time = time.monotonic()
                            logger.info(f"任务 {task_id} 智能降级：切换到备选引擎 {provider_kind}/{model_name}")
                            continue
                    raise

    else:
        if not handler:
            raise ValueError(f"provider_kind={provider_kind} 暂无对应 Handler，请在 providers/ 目录下添加")

        errors = handler.validate_params(model=model_name, params=params, param_specs_override=db_param_specs)
        if errors:
            raise ValueError(f"参数校验失败: {'; '.join(errors)}")

        await push_task_progress(task_id, 25, message="正在调用AI生成引擎...")

        # 调用前检查是否已取消
        if cancel_event.is_set():
            raise asyncio.CancelledError("用户取消任务")

        # 重试复用：如果上次 API 已成功返回 URL，直接复用，跳过 API 调用
        _cached_urls = (input_payload or {}).get("_result_urls")
        if _cached_urls and isinstance(_cached_urls, list) and len(_cached_urls) > 0:
            image_urls = _cached_urls
            write_task_log(
                task_id, "INFO",
                f"复用上次 API 已返回的 {len(image_urls)} 个图片 URL，跳过 API 调用",
                phase="generate", event_type="cache_hit",
                data_json={"url_count": len(image_urls), "first_url": str(image_urls[0])[:200]},
                push_ws=True,
            )
            await push_task_progress(task_id, 50, message="复用已有结果，准备下载...")
        else:
            # 调用 Handler（基类 generate_image 内部会调用 translate → httpx → parse）
            # 支持智能降级的重试循环（最多 1 次降级）
            while True:
                try:
                    image_urls = await handler.generate_image(
                        model=model_name,
                        prompt=prompt,
                        params=params,
                        timeout=getattr(handler, "_timeout", 120),
                    )
                    api_duration_ms = int((time.monotonic() - api_start_time) * 1000)

                    # 记录成功的 API 调用
                    with session_scope() as session:
                        log_api_call(
                            task_id,
                            phase="generate",
                            provider_kind=provider_kind or "unknown",
                            model=model_name,
                            url=f"{handler._base_url}/v1/images/generations",
                            method="POST",
                            request_payload={"model": model_name, "prompt": prompt[:200], "size": params.get("size")},
                            response_status=200,
                            response_body={"image_count": len(image_urls)},
                            duration_ms=api_duration_ms,
                        )
                    # API 成功：将返回的 URL 保存到 input_payload，供重试时复用
                    with session_scope() as sess:
                        t = sess.get(GenerationTask, task_id)
                        if t:
                            t.input_payload = {**(t.input_payload or {}), "_result_urls": [str(u) for u in image_urls]}
                            sess.add(t)
                            sess.commit()
                    break  # 成功，退出重试循环

                except Exception as api_err:
                    api_duration_ms = int((time.monotonic() - api_start_time) * 1000)
                    err_str = str(api_err)

                    # ── 速率限制自动重试（次数和等待时间由配置控制）──
                    if ("rate limit" in err_str.lower() or "429" in err_str) and rate_limit_retry < max_rate_limit_retries:
                        rate_limit_retry += 1
                        logger.warning(f"任务 {task_id} 遇到速率限制，等待 {rate_limit_wait}s 后重试 ({rate_limit_retry}/{max_rate_limit_retries}): {err_str[:200]}")
                        await push_task_progress(task_id, 32, message=f"遇到速率限制，等待 {rate_limit_wait}s 后自动重试...")
                        await asyncio.sleep(rate_limit_wait)
                        api_start_time = time.monotonic()
                        continue

                    # 记录失败的 API 调用
                    with session_scope() as session:
                        log_api_call(
                            task_id,
                            phase="generate",
                            provider_kind=provider_kind or "unknown",
                            model=model_name,
                            url=f"{handler._base_url}/v1/images/generations",
                            method="POST",
                            request_payload={"model": model_name, "prompt": prompt[:200], "size": params.get("size")},
                            response_status=None,
                            duration_ms=api_duration_ms,
                            error=str(api_err)[:500],
                        )
                    # ── 智能降级：尝试备选 Provider（受开关控制）──
                    if smart_fallback and not fallback_attempted and provider_id:
                        fallback_attempted = True
                        await push_task_progress(task_id, 35, message="主引擎失败，正在寻找备选引擎...")
                        with session_scope() as fb_session:
                            fb = _find_fallback_handler(fb_session, provider_id, target_type, task_id)
                        if fb:
                            handler, provider_kind, model_name, db_param_specs = fb
                            api_start_time = time.monotonic()
                            logger.info(f"任务 {task_id} 智能降级：切换到备选引擎 {provider_kind}/{model_name}")
                            continue
                    raise

    # ── 阶段 3：下载 + 保存记录 ────────────────────────────
    if asset_type_str == "video":
        if not video_urls:
            raise ValueError("API 未返回视频 URL")

        await push_task_progress(task_id, 70, message="下载生成结果...")

        with session_scope() as session:
            update_task_status(session, task_id, status="running", progress=70)

        if cancel_event.is_set():
            raise asyncio.CancelledError("用户取消任务")

        # 下载视频
        dl_start = time.monotonic()
        try:
            await async_download_file(str(video_urls[0]), output_path)
            dl_duration_ms = int((time.monotonic() - dl_start) * 1000)
            file_size = output_path.stat().st_size if output_path.exists() else None

            with session_scope() as session:
                log_download(
                    task_id,
                    url=str(video_urls[0]),
                    output_path=str(output_path),
                    file_size=file_size,
                    duration_ms=dl_duration_ms,
                )
        except Exception as dl_err:
            dl_duration_ms = int((time.monotonic() - dl_start) * 1000)
            with session_scope() as session:
                log_download(
                    task_id,
                    url=str(video_urls[0]),
                    output_path=str(output_path),
                    duration_ms=dl_duration_ms,
                    error=str(dl_err)[:500],
                )
            _clear_result_urls_if_expired(task_id, dl_err, str(video_urls[0]), "视频")
            raise

    elif asset_type_str == "image":
        if not image_urls:
            raise ValueError("API 未返回图片 URL")

        await push_task_progress(task_id, 70, message="下载生成结果...")

        with session_scope() as session:
            update_task_status(session, task_id, status="running", progress=70)

        # 下载前再次检查取消
        if cancel_event.is_set():
            raise asyncio.CancelledError("用户取消任务")

        # 下载第一张图片
        dl_start = time.monotonic()
        try:
            await async_download_file(str(image_urls[0]), output_path)
            dl_duration_ms = int((time.monotonic() - dl_start) * 1000)
            file_size = output_path.stat().st_size if output_path.exists() else None

            # 读取实际图片尺寸，用于对比请求尺寸（异步执行避免阻塞事件循环）
            actual_image_size = None
            try:
                def _read_img_size(path: Path) -> str | None:
                    try:
                        from PIL import Image as PILImage
                        with PILImage.open(path) as img:
                            return f"{img.width}x{img.height}"
                    except Exception:
                        return None
                actual_image_size = await asyncio.to_thread(_read_img_size, output_path)
            except Exception:
                pass  # 读取失败不影响主流程

            with session_scope() as session:
                log_download(
                    task_id,
                    url=str(image_urls[0]),
                    output_path=str(output_path),
                    file_size=file_size,
                    duration_ms=dl_duration_ms,
                )

            # 如果实际尺寸和请求尺寸不一致，记录警告
            requested_size = params.get("size") or input_payload.get("size")
            if actual_image_size and requested_size and actual_image_size != requested_size:
                with session_scope() as session:
                    write_task_log(
                        session, task_id, "WARNING",
                        f"图片实际尺寸 {actual_image_size} 与请求尺寸 {requested_size} 不一致（AI 服务端可能做了分辨率标准化）",
                        phase="generate", event_type="validate",
                        data_json={"requested_size": requested_size, "actual_size": actual_image_size},
                    )
        except Exception as dl_err:
            dl_duration_ms = int((time.monotonic() - dl_start) * 1000)
            with session_scope() as session:
                log_download(
                    task_id,
                    url=str(image_urls[0]),
                    output_path=str(output_path),
                    duration_ms=dl_duration_ms,
                    error=str(dl_err)[:500],
                )
            _clear_result_urls_if_expired(task_id, dl_err, str(image_urls[0]), "图片")
            raise

        # 如果有多个图片，也下载（用序号命名）
        for i, url in enumerate(image_urls[1:], 1):
            if cancel_event.is_set():
                raise asyncio.CancelledError("用户取消任务")
            extra_path = output_path.parent / f"{output_path.stem}_{i}{output_path.suffix}"
            await async_download_file(str(url), extra_path)

    await push_task_progress(task_id, 85, message="保存记录...")

    # 下载成功，清除 input_payload 中的 _result_urls 和 _video_task_id（不再需要复用）
    with session_scope() as sess:
        t = sess.get(GenerationTask, task_id)
        if t and t.input_payload:
            changed = False
            if "_result_urls" in t.input_payload:
                t.input_payload.pop("_result_urls", None)
                changed = True
            if "_video_task_id" in t.input_payload:
                t.input_payload.pop("_video_task_id", None)
                changed = True
            if changed:
                sess.add(t)
                sess.commit()

    # ── 保存提示词文本（可选）───
    if get_settings().tasks.save_prompts:
        with session_scope() as session:
            try:
                project_root = get_project_root(project_id, session)
                # sub_dir 在上面 if/else 分支中已统一赋值，分镜和非分镜场景都能用
                prompt_dir = project_root / sub_dir / "prompts"
                prompt_dir.mkdir(parents=True, exist_ok=True)
                prompt_path = prompt_dir / (Path(file_name).stem + ".txt")
                prompt_path.write_text(
                    f"Prompt: {prompt}\n"
                    f"Size: {input_payload.get('params', {}).get('size', input_payload.get('size', '1024x1024'))}\n"
                    f"Asset Type: {asset_type_str}\n"
                    f"Task ID: {task_id}\n"
                    f"Trace ID: {get_trace_id()}\n"
                    f"Generated at: {datetime.now(timezone.utc).isoformat()}\n",
                    encoding="utf-8",
                )
                write_task_log(
                    session, task_id, "DEBUG", f"提示词已保存到: {prompt_path}",
                    phase="system", event_type="system",
                )
            except Exception as ex:
                # 保存提示词失败不影响主流程
                logger.warning(f"保存提示词文件失败（已忽略）: {ex}")
                write_task_log(
                    session, task_id, "WARNING", f"保存提示词文件失败: {ex}",
                    phase="system", event_type="system",
                )

    # ── 创建 Asset 记录 + 回填 ─────────────────────────
    with session_scope() as session:
        project_root = get_project_root(project_id, session)
        file_path_rel = str(
            output_path.relative_to(project_root.resolve())
        ).replace("\\", "/")

        asset = create_asset_record(
            session=session,
            project_id=project_id,
            asset_type=asset_type_str,
            category=category,
            file_path=file_path_rel,
            task_id=task_id,
            status="ready",
            target_type=target_type,
            target_id=target_id,
        )
        asset_id = asset.id
        write_task_log(task_id, "INFO", f"Asset 记录已创建: {asset_id}",
            phase="system", event_type="system",
            data_json={"asset_id": asset_id, "file_path": file_path_rel},
        )

        await push_task_progress(task_id, 90, message="回填到实体...")

        # 自动回填到目标实体
        _auto_fill_entity(session, target_type, target_id, asset_id)
        write_task_log(task_id, "INFO", "已回填到目标实体",
            phase="system", event_type="system",
            data_json={"target_type": target_type, "target_id": target_id, "asset_id": asset_id},
        )

        # ── 成本追踪：从 handler._last_result 提取生成元数据 ──
        generation_metadata = None
        if handler and hasattr(handler, '_last_result') and handler._last_result:
            r = handler._last_result
            generation_metadata = {
                "usage": r.usage if hasattr(r, 'usage') else None,
                "duration_ms": r.duration_ms if hasattr(r, 'duration_ms') else None,
                "provider_kind": r.provider_kind if hasattr(r, 'provider_kind') else None,
                "model": r.model if hasattr(r, 'model') else model_name,
                "asset_type": asset_type_str,
                "output_count": len(r.image_urls) if hasattr(r, 'image_urls') and r.image_urls else 1,
            }

        # 读取实际输出尺寸（图片/视频），对比请求尺寸
        # 注意：必须用异步方式执行，避免同步 I/O 阻塞 FastAPI 事件循环
        actual_size = None
        try:
            if output_path.exists():
                if asset_type_str == "image":
                    def _read_image_size(path: Path) -> str | None:
                        try:
                            from PIL import Image as PILImage
                            with PILImage.open(path) as img:
                                return f"{img.width}x{img.height}"
                        except Exception:
                            return None
                    actual_size = await asyncio.to_thread(_read_image_size, output_path)
                elif asset_type_str == "video":
                    async def _read_video_size(path: Path) -> str | None:
                        try:
                            proc = await asyncio.create_subprocess_exec(
                                "ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0",
                                str(path),
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                            if proc.returncode == 0 and stdout.strip():
                                return stdout.strip().decode("utf-8", errors="ignore")
                        except Exception:
                            return None
                        return None
                    actual_size = await _read_video_size(output_path)
        except Exception:
            pass

        if actual_size:
            if generation_metadata is None:
                generation_metadata = {}
            generation_metadata["actual_size"] = actual_size
            requested_size = params.get("size") or input_payload.get("size")
            if requested_size and actual_size != requested_size:
                generation_metadata["requested_size"] = requested_size
                generation_metadata["size_mismatch"] = True

        # 更新任务状态
        update_task_status(
            session,
            task_id,
            status="succeeded",
            progress=100,
            output_asset_id=asset_id,
            output_payload=generation_metadata,
        )
        write_task_log(task_id, "INFO", "任务状态更新为 succeeded",
            phase="system", event_type="system",
        )

    await push_task_completed(task_id, target_type=target_type, asset_id=asset_id, message="任务完成")
    logger.info(f"任务 {task_id} 完成，asset_id={asset_id}, trace_id={get_trace_id()}")
