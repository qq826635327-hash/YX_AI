"""剧本解析管线 — LLM 调用工具层。

提供 LLM 调用（流式/非流式）、JSON 提取、模板加载渲染等底层工具。
被 _extraction_stages.py 和 _orchestrator.py 导入使用。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.db import session_scope
from sqlmodel import select
from app.ws.routes import push_script_stream

logger = logging.getLogger(__name__)


# ============================================================
# LLM 调用工具
# ============================================================

def _update_task_progress(task_id: str, progress: int) -> None:
    """更新任务中心的进度（同步，在 session_scope 中执行）。"""
    if not task_id:
        return
    try:
        from app.models import GenerationTask
        with session_scope() as session:
            task = session.get(GenerationTask, task_id)
            if task:
                task.progress = progress
                session.add(task)
                session.commit()
    except Exception as e:
        logger.warning(f"更新任务进度失败: {e}")


def _update_task_status(task_id: str, status: str, progress: int | None = None, error_message: str | None = None) -> None:
    """更新任务中心的状态（同步，在 session_scope 中执行）。"""
    if not task_id:
        return
    try:
        from app.models import GenerationTask
        from datetime import datetime, timezone
        with session_scope() as session:
            task = session.get(GenerationTask, task_id)
            if task:
                task.status = status
                if progress is not None:
                    task.progress = progress
                if error_message:
                    task.error_message = error_message
                if status in ("succeeded", "failed", "cancelled"):
                    task.finished_at = datetime.now(timezone.utc)
                session.add(task)
                session.commit()
    except Exception as e:
        logger.warning(f"更新任务状态失败: {e}")

def _find_text_llm_config() -> tuple[str, str, str, int] | None:
    """从数据库中查找支持文本推理的 Provider 配置。

    优先使用数据库中启用的 Provider，其次使用 config.yaml 中的 LLM 配置。

    Returns:
        (base_url, api_key, model, timeout) 或 None
    """
    from app.models.provider import ApiProvider, ProviderModel

    with session_scope() as session:
        # 查找有 text_reasoning 标签模型的 Provider
        from sqlalchemy.orm import selectinload
        providers = session.exec(
            select(ApiProvider)
            .where(ApiProvider.enabled == True)
            .options(selectinload(ApiProvider.models))
        ).all()
        for provider in providers:
            for model in provider.models:
                if "text_reasoning" in (model.tags or []):
                    from app.core.config import decrypt_secret
                    api_key = decrypt_secret(provider.api_key_encrypted)
                    return (
                        provider.base_url,
                        api_key,
                        model.model_name,
                        provider.timeout_seconds,
                    )

    return None


async def _call_llm(
    system_prompt: str,
    user_content: str,
    temperature: float = 0.3,
    json_mode: bool = True,
    timeout_override: int | None = None,
) -> str:
    """调用 LLM 并返回原始文本响应。遇到速率限制自动重试。"""
    from app.core.config import get_settings

    llm_config = _find_text_llm_config()
    if not llm_config:
        raise RuntimeError("未找到可用的文本推理模型，请在设置中配置 Provider 或 LLM")

    base_url, api_key, model, timeout = llm_config
    if timeout_override:
        timeout = timeout_override

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
    }
    # 注意：Agnes API 不支持 response_format: json_object（会返回错误对象），
    # 模板中已要求 LLM 输出 JSON，不需要强制 json_object 模式。
    # 仅对明确支持的标准 OpenAI API 启用 json_mode。
    if json_mode and "agnes" not in base_url:
        payload["response_format"] = {"type": "json_object"}

    # 速率限制自动重试
    settings = get_settings()
    max_retries = settings.tasks.rate_limit_retry
    wait_seconds = settings.tasks.rate_limit_wait
    rate_limit_retry = 0

    while True:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Agnes API 需要 /v1 前缀
            chat_url = f"{base_url.rstrip('/')}/chat/completions"
            if "agnes" in base_url and "/v1" not in base_url:
                chat_url = f"{base_url.rstrip('/')}/v1/chat/completions"
            try:
                resp = await client.post(
                    chat_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                err_str = str(e)
                if ("rate limit" in err_str.lower() or "429" in err_str) and rate_limit_retry < max_retries:
                    rate_limit_retry += 1
                    logger.warning(f"LLM 调用遇到速率限制，等待 {wait_seconds}s 后重试 ({rate_limit_retry}/{max_retries}): {err_str[:200]}")
                    await asyncio.sleep(wait_seconds)
                    continue
                raise


async def _call_llm_stream(
    system_prompt: str,
    user_content: str,
    project_id: str,
    stage: str,
    temperature: float = 0.3,
    json_mode: bool = True,
    timeout_override: int | None = None,
) -> str:
    """流式调用 LLM，逐 token 通过 WebSocket 批量推送，返回完整响应。

    每 100ms 批量推送一次 token，减少前端渲染压力。
    如果流式调用失败，自动降级为非流式调用。
    """
    llm_config = _find_text_llm_config()
    if not llm_config:
        raise RuntimeError("未找到可用的文本推理模型，请在设置中配置 Provider 或 LLM")

    base_url, api_key, model, timeout = llm_config
    if timeout_override:
        timeout = timeout_override

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "stream": True,
    }
    if json_mode and "agnes" not in base_url:
        payload["response_format"] = {"type": "json_object"}

    chat_url = f"{base_url.rstrip('/')}/chat/completions"
    if "agnes" in base_url and "/v1" not in base_url:
        chat_url = f"{base_url.rstrip('/')}/v1/chat/completions"

    accumulated = ""
    buffer = ""
    last_flush = time.monotonic()

    try:
        # 流式请求需要较长的读取超时（LLM 可能需要几分钟才能完成输出）
        stream_timeout = httpx.Timeout(timeout, read=timeout * 5, write=30.0)
        async with httpx.AsyncClient(timeout=stream_timeout) as client:
            async with client.stream(
                "POST",
                chat_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            accumulated += token
                            buffer += token
                            # 每 100ms 批量推送一次
                            now = time.monotonic()
                            if now - last_flush >= 0.1:
                                await push_script_stream(project_id, stage, buffer)
                                buffer = ""
                                last_flush = now
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue

                # 刷出剩余 buffer
                if buffer:
                    await push_script_stream(project_id, stage, buffer)

    except httpx.HTTPStatusError as e:
        # 流式请求遇到速率限制，降级为非流式重试
        err_str = str(e)
        if "rate limit" in err_str.lower() or "429" in err_str:
            from app.core.config import get_settings
            settings = get_settings()
            max_retries = settings.tasks.rate_limit_retry
            wait_seconds = settings.tasks.rate_limit_wait
            if max_retries > 0:
                logger.warning(f"流式调用遇到速率限制，等待 {wait_seconds}s 后降级为非流式重试: {err_str[:200]}")
                await asyncio.sleep(wait_seconds)
                return await _call_llm(
                    system_prompt, user_content, temperature, json_mode, timeout_override
                )
        raise
    except Exception as e:
        logger.warning(f"流式调用失败，降级为非流式: {e}")
        # 流式失败，降级为非流式
        return await _call_llm(
            system_prompt, user_content, temperature, json_mode, timeout_override
        )

    return accumulated


def _extract_json(text: str) -> Any:
    """从 LLM 响应中提取 JSON（兼容 markdown 代码块包裹和截断）。"""
    text = text.strip()
    # 去掉 markdown 代码块
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉首行 ```json 和末行 ```
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试修复截断的 JSON 数组：找到最后一个完整的 } 并补上 ]
    if text.startswith("["):
        last_brace = text.rfind("}")
        if last_brace > 0:
            try:
                return json.loads(text[:last_brace + 1] + "]")
            except json.JSONDecodeError:
                pass

    # 尝试修复截断的 JSON 对象
    if text.startswith("{"):
        last_brace = text.rfind("}")
        if last_brace > 0:
            try:
                return json.loads(text[:last_brace + 1] + "}")
            except json.JSONDecodeError:
                pass

    raise json.JSONDecodeError("无法解析 JSON", text, 0)


# ============================================================
# 模板加载与渲染
# ============================================================

def _load_template_content(template_type: str) -> str:
    """从数据库加载指定类型的默认模板内容。"""
    from app.services.prompt_template_service import get_default_template

    with session_scope() as session:
        tmpl = get_default_template(session, template_type)
        if tmpl:
            return tmpl.content

    # 如果数据库没有模板，使用内置默认
    from app.services.prompt_template_service import BUILTIN_TEMPLATES
    for t in BUILTIN_TEMPLATES:
        if t["template_type"] == template_type:
            return t["content"]

    return ""


def _render_template(template_content: str, **kwargs) -> str:
    """渲染模板，替换 {{占位符}}。"""
    result = template_content
    for key, value in kwargs.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result
