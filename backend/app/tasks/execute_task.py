"""任务执行器 — 调用 AI API 生成图片/视频。

集成结构化日志 + trace_id，全链路可追踪：
  ref_collect → generate → download → save → backfill
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Literal, Optional

# 参考图注入策略预设（第一阶段）
ReferencePreset = Literal["full", "first_frame_only", "first_and_last_frame", "none"]


def _select_provider_model(provider, target_type: str) -> str:
    """从 Provider 的多模型中，按目标类型和标签选择最合适的模型。"""
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

    # 兜底：返回第一个模型
    return models[0].model_name

from app.clients.agnes_client import async_download_file
from app.core.config import get_settings
from app.core.trace import new_trace_id, get_trace_id, clear_trace_id
from app.db import session_scope
from app.models import ApiProvider, Character, Project, Prop, Scene
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
    """根据 target_type 自动回填素材 ID 与生成状态到对应实体。"""
    try:
        if target_type == "character":
            e = session.get(Character, target_id)
            if e:
                e.image_asset_id = asset_id
                e.gen_status = "ready"
                logger.info(f"自动回填 Character {e.name} image_asset_id={asset_id}")
        elif target_type == "scene":
            e = session.get(Scene, target_id)
            if e:
                e.image_asset_id = asset_id
                e.gen_status = "ready"
                logger.info(f"自动回填 Scene {e.name} image_asset_id={asset_id}")
        elif target_type == "prop":
            e = session.get(Prop, target_id)
            if e:
                e.image_asset_id = asset_id
                e.gen_status = "ready"
                logger.info(f"自动回填 Prop {e.name} image_asset_id={asset_id}")
        elif target_type == "shot_first_frame":
            from app.models import Shot
            e = session.get(Shot, target_id)
            if e:
                e.first_frame_asset_id = asset_id
                e.first_frame_status = "ready"
        elif target_type == "shot_last_frame":
            from app.models import Shot
            e = session.get(Shot, target_id)
            if e:
                e.last_frame_asset_id = asset_id
                e.last_frame_status = "ready"
        elif target_type == "shot_video":
            from app.models import Shot
            e = session.get(Shot, target_id)
            if e:
                e.video_asset_id = asset_id
                e.video_status = "ready"
    except Exception as ex:
        logger.warning(f"自动回填失败: {ex}")


def _get_prompt_from_entity(session, target_type: str, target_id: str) -> str:
    """从实体获取提示词（优先用 input_payload.prompt，否则用实体描述）。"""
    from app.models import Shot

    try:
        if target_type == "character":
            e = session.get(Character, target_id)
            return e.description or e.settings or e.name if e else "一个角色"
        elif target_type == "scene":
            e = session.get(Scene, target_id)
            return e.description or e.name if e else "一个场景"
        elif target_type == "prop":
            e = session.get(Prop, target_id)
            return e.description or e.name if e else "一个道具"
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
    preset: ReferencePreset = "full",
) -> dict:
    """按策略收集参考图片，返回结构化结果。

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

    empty = {"data_uris": [], "details": [], "refs": []}

    if preset == "none" or not target_type.startswith("shot_"):
        return empty

    shot = session.get(Shot, target_id)
    if not shot:
        return empty

    # 候选来源：(asset_id, type, label)
    candidates: list[tuple[str, str, str]] = []

    # 首帧
    if preset in ("full", "first_frame_only", "first_and_last_frame"):
        if shot.first_frame_asset_id:
            candidates.append((shot.first_frame_asset_id, "first_frame", "首帧"))

    # 尾帧
    if preset in ("full", "first_and_last_frame"):
        if shot.last_frame_asset_id:
            candidates.append((shot.last_frame_asset_id, "last_frame", "尾帧"))

    # 完整注入才带角色/场景/道具
    if preset == "full":
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

    data_uris: list[str] = []
    details: list[dict] = []
    refs: list[dict] = []

    seen_asset_ids: set[str] = set()
    for asset_id, ref_type, label in candidates:
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


async def execute_task_async(task_id: str) -> None:
    """执行生成任务（后台）。

    流程：
    1. 立即将状态从 pending → running，分配 trace_id
    2. 读取上下文 + 准备参数（一个 session）
    3. 调用 AI API 生成图片（结构化日志记录）
    4. 下载结果 + 保存记录（结构化日志记录）
    """
    cancel_event = get_cancel_event(task_id)
    trace_id = new_trace_id()  # 为整个任务分配 trace_id

    try:
        # ── 阶段 1：标记 running + 读取上下文 + 准备参数 ──────
        with session_scope() as session:
            update_task_status(session, task_id, status="running", progress=5)
            write_task_log(
                session, task_id, "INFO", "任务开始执行，状态更新为 running",
                phase="system", event_type="system",
            )

            task = get_task(session, task_id)
            if not task:
                raise ValueError(f"任务 {task_id} 不存在")
            project_id = task.project_id
            target_type = task.target_type
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

            # 获取项目根目录 + 实体名 + 模块目录
            project_root = get_project_root(project_id, session)
            if not project_root:
                raise ValueError(f"找不到项目 {project_id} 的根目录")

            entity_name = get_entity_dirname(session, target_type, target_id) or target_id[:8]
            module_dir = TARGET_TYPE_DIR_MAP.get(target_type, "其他")

            # 确定文件类型 & 目录结构
            if asset_type == "video" or target_type == "shot_video":
                asset_type_str = "video"
                category = "shot_video" if target_type.startswith("shot_") else target_type
                sub_dir = Path(module_dir) / entity_name / "videos"
                ext = ".mp4"
            else:
                asset_type_str = "image"
                if target_type == "shot_first_frame":
                    category = "first_frame"
                elif target_type == "shot_last_frame":
                    category = "last_frame"
                else:
                    category = target_type
                sub_dir = Path(module_dir) / entity_name / "images"
                ext = ".png"

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

            if provider_id:
                from sqlalchemy.orm import selectinload
                from sqlmodel import select as sqlmodel_select

                stmt = sqlmodel_select(ApiProvider).where(ApiProvider.id == provider_id).options(selectinload(ApiProvider.models))
                provider = session.exec(stmt).first()
                if provider:
                    provider_kind = provider.provider_kind
                    provider_model = _select_provider_model(provider, target_type)
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

            # 参数准备
            params = input_payload.get("extra_params", input_payload.get("params", {}))
            if not params:
                size = input_payload.get("size", "1024x1024")
                params = {"size": size}

            model_name = input_payload.get("model") or provider_model or ""
            if not model_name:
                raise ValueError("未找到模型名：Provider 未配置 model，且 input_payload 未指定 model")

            # ── 收集参考图片（图生图）──────────────────────────
            reference_images: list[str] = []
            ref_details: list[dict] = []
            structured_refs: list[dict] = []

            # 读取注入策略预设（默认完整注入）
            ref_preset: ReferencePreset = input_payload.get("reference_preset", "full")
            if ref_preset not in ("full", "first_frame_only", "first_and_last_frame", "none"):
                ref_preset = "full"

            # 1. 按策略自动收集
            if target_type.startswith("shot_") and project_root and ref_preset != "none":
                auto_result = _collect_reference_images(
                    session, target_type, target_id, project_root, preset=ref_preset
                )
                reference_images.extend(auto_result["data_uris"])
                ref_details.extend(auto_result["details"])
                structured_refs.extend(auto_result["refs"])
                if auto_result["data_uris"]:
                    log_ref_collect(
                        session, task_id,
                        source=f"自动注入({ref_preset})",
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
                        session, task_id,
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

            update_task_status(session, task_id, status="running", progress=20)
            write_task_log(
                session, task_id, "INFO", "开始调用生成引擎...",
                phase="generate", event_type="system",
            )

        await push_task_progress(task_id, 5, message="准备生成...")
        await push_task_progress(task_id, 20, message="正在生成（预计 30-60 秒）...")

        # ── 阶段 2：调用 AI API ─────────────────────────────────
        image_urls = None
        video_urls = None
        api_start_time = time.monotonic()

        if asset_type_str == "video":
            # ── 视频生成 ──
            if not handler:
                raise ValueError(f"视频生成暂不支持 provider_kind={provider_kind}（需要对应的 Handler）")

            # 检查 Handler 是否支持视频生成
            caps = handler.get_capabilities(model_name)
            need_url = caps.get("reference_images_need_url", False)

            # 参考图分流：need_url=True → 上传图床获取公网 URL；否则用 base64
            if reference_images and need_url:
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
                write_task_log(
                    session, task_id, "INFO",
                    f"视频模式：{len(public_urls)} 张参考图已转为公网 URL",
                    phase="generate", event_type="validate",
                    data_json={"reference_count": len(public_urls), "mode": "public_url"},
                )

            errors = handler.validate_params(model=model_name, params=params)
            if errors:
                raise ValueError(f"参数校验失败: {'; '.join(errors)}")

            with session_scope() as session:
                update_task_status(session, task_id, status="running", progress=30)

            await push_task_progress(task_id, 30, message="正在生成视频（可能需要数分钟）...")

            if cancel_event.is_set():
                raise asyncio.CancelledError("用户取消任务")

            try:
                video_urls = await handler.generate_video(
                    model=model_name,
                    prompt=prompt,
                    params=params,
                )
                api_duration_ms = int((time.monotonic() - api_start_time) * 1000)

                with session_scope() as session:
                    log_api_call(
                        session, task_id,
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

            except Exception as api_err:
                api_duration_ms = int((time.monotonic() - api_start_time) * 1000)
                with session_scope() as session:
                    log_api_call(
                        session, task_id,
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
                raise

        else:
            if not handler:
                raise ValueError(f"provider_kind={provider_kind} 暂无对应 Handler，请在 providers/ 目录下添加")

            errors = handler.validate_params(model=model_name, params=params)
            if errors:
                raise ValueError(f"参数校验失败: {'; '.join(errors)}")

            with session_scope() as session:
                update_task_status(session, task_id, status="running", progress=30)

            await push_task_progress(task_id, 30, message="正在生成图片（30-60秒）...")

            # 调用前检查是否已取消
            if cancel_event.is_set():
                raise asyncio.CancelledError("用户取消任务")

            # 调用 Handler（基类 generate_image 内部会调用 translate → httpx → parse）
            try:
                image_urls = await handler.generate_image(
                    model=model_name,
                    prompt=prompt,
                    params=params,
                )
                api_duration_ms = int((time.monotonic() - api_start_time) * 1000)

                # 记录成功的 API 调用
                with session_scope() as session:
                    log_api_call(
                        session, task_id,
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

            except Exception as api_err:
                api_duration_ms = int((time.monotonic() - api_start_time) * 1000)

                # 记录失败的 API 调用
                with session_scope() as session:
                    log_api_call(
                        session, task_id,
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
                raise

        # ── 阶段 3：下载 + 保存记录 ────────────────────────────
        if asset_type_str == "video":
            if not video_urls:
                raise ValueError("API 未返回视频 URL")

            await push_task_progress(task_id, 70, message="视频生成完成，下载中...")

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
                        session, task_id,
                        url=str(video_urls[0]),
                        output_path=str(output_path),
                        file_size=file_size,
                        duration_ms=dl_duration_ms,
                    )
            except Exception as dl_err:
                dl_duration_ms = int((time.monotonic() - dl_start) * 1000)
                with session_scope() as session:
                    log_download(
                        session, task_id,
                        url=str(video_urls[0]),
                        output_path=str(output_path),
                        duration_ms=dl_duration_ms,
                        error=str(dl_err)[:500],
                    )
                raise

        elif asset_type_str == "image":
            if not image_urls:
                raise ValueError("API 未返回图片 URL")

            await push_task_progress(task_id, 70, message="图片生成完成，下载中...")

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

                with session_scope() as session:
                    log_download(
                        session, task_id,
                        url=str(image_urls[0]),
                        output_path=str(output_path),
                        file_size=file_size,
                        duration_ms=dl_duration_ms,
                    )
            except Exception as dl_err:
                dl_duration_ms = int((time.monotonic() - dl_start) * 1000)
                with session_scope() as session:
                    log_download(
                        session, task_id,
                        url=str(image_urls[0]),
                        output_path=str(output_path),
                        duration_ms=dl_duration_ms,
                        error=str(dl_err)[:500],
                    )
                raise

            # 如果有多个图片，也下载（用序号命名）
            for i, url in enumerate(image_urls[1:], 1):
                if cancel_event.is_set():
                    raise asyncio.CancelledError("用户取消任务")
                extra_path = output_path.parent / f"{output_path.stem}_{i}{output_path.suffix}"
                await async_download_file(str(url), extra_path)

        await push_task_progress(task_id, 85, message="保存记录...")

        # ── 保存提示词文本（可选）───
        if get_settings().tasks.save_prompts:
            with session_scope() as session:
                project_root = get_project_root(project_id, session)
                prompt_dir = project_root / module_dir / entity_name / "prompts"
                prompt_dir.mkdir(parents=True, exist_ok=True)
                prompt_path = prompt_dir / (Path(file_name).stem + ".txt")
                try:
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
                except (OSError, PermissionError) as ex:
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
            write_task_log(
                session, task_id, "INFO", f"Asset 记录已创建: {asset_id}",
                phase="system", event_type="system",
                data_json={"asset_id": asset_id, "file_path": file_path_rel},
            )

            await push_task_progress(task_id, 90, message="回填到实体...")

            # 自动回填到目标实体
            _auto_fill_entity(session, target_type, target_id, asset_id)
            write_task_log(
                session, task_id, "INFO", "已回填到目标实体",
                phase="system", event_type="system",
                data_json={"target_type": target_type, "target_id": target_id, "asset_id": asset_id},
            )

            # 更新任务状态
            update_task_status(
                session,
                task_id,
                status="succeeded",
                progress=100,
                output_asset_id=asset_id,
            )
            write_task_log(
                session, task_id, "INFO", "任务状态更新为 succeeded",
                phase="system", event_type="system",
            )

        await push_task_completed(task_id, asset_id=asset_id, message="任务完成")
        logger.info(f"任务 {task_id} 完成，asset_id={asset_id}, trace_id={get_trace_id()}")

    except asyncio.CancelledError:
        with session_scope() as session:
            update_task_status(session, task_id, status="cancelled", error="用户取消任务")
            write_task_log(
                session, task_id, "INFO", "任务被取消",
                phase="system", event_type="system",
            )
        await push_task_failed(task_id, "任务已取消")
        logger.info(f"任务 {task_id} 被取消")
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"任务 {task_id} 失败: {e}")
        logger.error(error_detail)
        with session_scope() as session:
            update_task_status(session, task_id, status="failed", error=str(e)[:500])
            write_task_log(
                session, task_id, "ERROR", f"任务失败: {str(e)}",
                data=error_detail[:500],
                phase="system", event_type="system",
                data_json={"error": str(e)[:500], "traceback": error_detail[:1000]},
            )
        await push_task_failed(task_id, str(e)[:200])
    finally:
        clear_cancel_event(task_id)
        clear_trace_id()
        logger.info(f"任务 {task_id} 执行结束")
