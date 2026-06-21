"""Agnes Provider Handler — 适配 agnes-image-2.1-flash / agnes-video-v2.0 等模型。

通过 translate/parse 模式实现：
- translate(): 将 StandardGenerateRequest 转为 Agnes API 的 url/payload/headers
- parse(): 将 Agnes API 响应转为 StandardGenerateResult
- generate_image(): 由基类统一处理（translate → httpx → parse），无需覆盖
- generate_video(): 异步任务模式（提交 → 轮询 → 返回视频 URL）
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from app.providers.base import ProviderHandler
from app.providers.registry import register
from app.schemas.provider_types import (
    ModelCapabilities,
    StandardGenerateRequest,
    StandardGenerateResult,
)

logger = logging.getLogger(__name__)


@register
class AgnesHandler(ProviderHandler):
    """Agnes AI 图像/视频生成适配器。

    图片文档：https://agnes-ai.com/doc/agnes-image-21-flash
    视频文档：https://agnes-ai.com/doc/agnes-video-v2.0

    关键参数：
    - 图片：size 必填，格式 "1024x768"；extra_body.response_format 必须放在 extra_body 中
    - 视频：异步任务模式，image 参数只支持公网 URL（不支持 base64）
    """

    PROVIDER_KIND = "agnes"

    SUPPORTED_MODELS = {
        "agnes-image-2.1-flash": {
            "param_specs": [
                {
                    "key": "size",
                    "label": "分辨率",
                    "required": True,
                    "input_type": "select",
                    "options": [
                        "512x512",
                        "640x640",
                        "512x768",
                        "768x512",
                        "720x720",
                        "1024x768",
                        "768x1024",
                        "1024x1024",
                        "1280x720",
                        "720x1280",
                        "1280x1280",
                        "1440x1440",
                        "1920x1080",
                    ],
                    "allow_custom": True,
                    "default": "1920x1080",
                    "placeholder": "宽x高，如 1920x1080",
                    "help_text": "Agnes 支持自定义分辨率（256-2048），默认 1920x1080",
                }
            ],
            "capabilities": ModelCapabilities(
                image_generation=True,
                image_to_image=True,
                video_generation=False,
                batch_support=False,
                max_count=1,
                max_reference_images=5,
                supports_negative_prompt=False,
                custom_size_range=(256, 2048),
                reference_images_need_url=False,  # 图片 API 支持 base64
            ),
        },
        "agnes-video-v2.0": {
            "param_specs": [
                {
                    "key": "width",
                    "label": "宽度",
                    "required": False,
                    "input_type": "number",
                    "default": "1152",
                    "help_text": "视频宽度，默认 1152",
                },
                {
                    "key": "height",
                    "label": "高度",
                    "required": False,
                    "input_type": "number",
                    "default": "768",
                    "help_text": "视频高度，默认 768",
                },
                {
                    "key": "num_frames",
                    "label": "帧数",
                    "required": False,
                    "input_type": "select",
                    "options": ["81", "121", "161", "241", "441"],
                    "default": "121",
                    "help_text": "必须满足 8n+1，如 81(3s)/121(5s)/241(10s)/441(18s)",
                },
                {
                    "key": "frame_rate",
                    "label": "帧率",
                    "required": False,
                    "input_type": "select",
                    "options": ["24", "30"],
                    "default": "24",
                    "help_text": "视频 FPS，推荐 24 或 30",
                },
            ],
            "capabilities": ModelCapabilities(
                image_generation=False,
                image_to_image=True,  # 图生视频
                video_generation=True,
                batch_support=False,
                max_count=1,
                max_reference_images=2,  # 首帧+末帧
                supports_negative_prompt=True,
                custom_size_range=(480, 1920),
                reference_images_need_url=True,  # 视频 API 只支持公网 URL
            ),
        },
    }

    # 视频轮询配置
    VIDEO_POLL_INTERVAL = 5  # 秒
    VIDEO_POLL_TIMEOUT = 600  # 10 分钟

    def __init__(self, api_key: str, base_url: str | None = None, timeout: int = 120):
        self._api_key = api_key
        self._base_url = (base_url or "https://apihub.agnes-ai.com").rstrip("/")
        self._timeout = timeout

    # ============================================================
    # 辅助方法
    # ============================================================

    def _is_video_model(self, model: str) -> bool:
        """判断是否为视频模型。"""
        return model.startswith("agnes-video")

    # ============================================================
    # 参数校验
    # ============================================================

    def validate_params(self, model: str, params: dict) -> list[str]:
        """Agnes 参数校验。"""
        errors = super().validate_params(model, params)

        if self._is_video_model(model):
            # 视频参数校验
            num_frames = params.get("num_frames")
            if num_frames:
                try:
                    nf = int(num_frames)
                    if nf > 441:
                        errors.append("「帧数」不能超过 441")
                    if (nf - 1) % 8 != 0:
                        errors.append(f"「帧数」必须满足 8n+1，当前值 {nf} 不合法（推荐：81/121/161/241/441）")
                except ValueError:
                    errors.append(f"「帧数」格式错误：{num_frames}")

            frame_rate = params.get("frame_rate")
            if frame_rate:
                try:
                    fr = int(frame_rate)
                    if fr < 1 or fr > 60:
                        errors.append("「帧率」范围 1-60")
                except ValueError:
                    errors.append(f"「帧率」格式错误：{frame_rate}")
        else:
            # 图片参数校验
            size = params.get("size", "")
            if size:
                if not re.match(r"^\d+x\d+$", size):
                    errors.append(f"「分辨率」格式错误，应为「宽x高」（如 1024x1024），当前值：{size}")
                else:
                    try:
                        w, h = size.split("x")
                        if int(w) < 256 or int(h) < 256:
                            errors.append("「分辨率」宽高不能小于 256")
                        if int(w) > 2048 or int(h) > 2048:
                            errors.append("「分辨率」宽高不能大于 2048（Agnes 限制）")
                    except ValueError:
                        errors.append(f"「分辨率」格式错误：{size}")

        return errors

    # ============================================================
    # translate: 标准请求 → Agnes API 请求
    # ============================================================

    def translate(self, request: StandardGenerateRequest) -> tuple[str, dict, dict]:
        """将标准请求转为 Agnes API 的 url/payload/headers。

        根据 model 自动区分图片/视频端点。
        """
        if self._is_video_model(request.model):
            return self._translate_video(request)
        return self._translate_image(request)

    def _translate_image(self, request: StandardGenerateRequest) -> tuple[str, dict, dict]:
        """图片生成 translate。"""
        url = f"{self._base_url}/v1/images/generations"

        size = request.size or "1024x1024"
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "size": size,
            "extra_body": {
                "response_format": "url",
            },
        }

        # 图生图：参考图片（base64 Data URI）
        if request.reference_images:
            payload["extra_body"]["image"] = request.reference_images
            logger.info(f"[AgnesHandler] 图生图模式：{len(request.reference_images)} 张参考图")

        if request.negative_prompt:
            payload["extra_body"]["negative_prompt"] = request.negative_prompt

        # 厂商特有参数
        if request.extra:
            extra_copy = dict(request.extra)
            extra_body = extra_copy.pop("extra_body", {})
            if extra_body:
                payload["extra_body"].update(extra_body)
            payload.update(extra_copy)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        return url, payload, headers

    def _translate_video(self, request: StandardGenerateRequest) -> tuple[str, dict, dict]:
        """视频生成 translate。

        Agnes 视频 API 特点：
        - 端点：POST /v1/videos
        - image 参数只支持公网 URL（不支持 base64）
        - 多图在 extra_body.image 数组中
        - 支持首尾帧关键帧模式：extra_body.mode = "keyframes"
        """
        url = f"{self._base_url}/v1/videos"

        payload = {
            "model": request.model,
            "prompt": request.prompt,
        }

        # 分辨率
        if request.size:
            # request.size 格式为 "1152x768"
            parts = request.size.lower().split("x")
            if len(parts) == 2:
                payload["width"] = int(parts[0])
                payload["height"] = int(parts[1])
        elif request.extra.get("width") or request.extra.get("height"):
            if request.extra.get("width"):
                payload["width"] = int(request.extra["width"])
            if request.extra.get("height"):
                payload["height"] = int(request.extra["height"])

        # 帧数和帧率
        if request.extra.get("num_frames"):
            payload["num_frames"] = int(request.extra["num_frames"])
        if request.extra.get("frame_rate"):
            payload["frame_rate"] = int(request.extra["frame_rate"])

        # 反向提示词
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt

        # 参考图（公网 URL）
        if request.reference_images:
            if len(request.reference_images) == 1:
                # 单图：image 字段
                payload["image"] = request.reference_images[0]
                logger.info(f"[AgnesHandler] 图生视频模式：1 张参考图（首帧）")
            else:
                # 多图：extra_body.image 数组 + keyframes 模式
                payload["extra_body"] = {
                    "image": request.reference_images,
                    "mode": "keyframes",
                }
                logger.info(f"[AgnesHandler] 首尾帧关键帧模式：{len(request.reference_images)} 张参考图")

        # 其他 extra 参数
        if request.extra:
            extra_copy = dict(request.extra)
            # 移除已处理的参数
            for key in ("width", "height", "num_frames", "frame_rate"):
                extra_copy.pop(key, None)
            if extra_copy:
                if "extra_body" not in payload:
                    payload["extra_body"] = {}
                extra_body = extra_copy.pop("extra_body", {})
                if extra_body:
                    payload["extra_body"].update(extra_body)
                payload.update(extra_copy)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        return url, payload, headers

    # ============================================================
    # parse: Agnes API 响应 → 标准结果
    # ============================================================

    def parse(self, response_body: dict, status_code: int) -> StandardGenerateResult:
        """将 Agnes API 响应转为标准结果。

        图片和视频的提交响应格式不同：
        - 图片：{ "data": [{ "url": "https://..." }] }
        - 视频：{ "video_id": "video_xxx", "status": "queued" }
        """
        if status_code not in (200, 201):
            error_info = response_body.get("error", {})
            error_msg = error_info.get("message", "") if isinstance(error_info, dict) else str(error_info)
            detail = f"Agnes API 返回 {status_code}: {response_body}"
            logger.error(f"[AgnesHandler] {detail}")
            return StandardGenerateResult(
                success=False,
                error=error_msg or detail,
                raw_response=response_body,
            )

        # 图片响应
        image_urls = []
        for item in response_body.get("data", []):
            url = item.get("url")
            if url:
                image_urls.append(url)

        if image_urls:
            return StandardGenerateResult(
                success=True,
                image_urls=image_urls,
                raw_response=response_body,
            )

        # 视频提交响应（异步任务，需要轮询）
        video_id = response_body.get("video_id")
        if video_id:
            return StandardGenerateResult(
                success=True,
                raw_response=response_body,
                provider_kind=self.PROVIDER_KIND,
                model=response_body.get("model", ""),
            )

        # 未知响应格式
        return StandardGenerateResult(
            success=False,
            error=f"无法解析 Agnes 响应: {response_body}",
            raw_response=response_body,
        )

    # ============================================================
    # generate_video: 异步轮询模式
    # ============================================================

    async def generate_video(self, request: StandardGenerateRequest) -> StandardGenerateResult:
        """视频生成：提交任务 → 轮询结果 → 返回视频 URL。

        Agnes 视频 API 是异步的：
        1. POST /v1/videos → 返回 video_id
        2. GET /agnesapi?video_id=xxx → 轮询直到 status=completed
        3. 从 remixed_from_video_id 取视频 URL
        """
        # 1. 提交任务
        url, payload, headers = self.translate(request)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            submit_result = self.parse(resp.json(), resp.status_code)

            if not submit_result.success:
                return submit_result

            video_id = submit_result.raw_response.get("video_id")
            if not video_id:
                return StandardGenerateResult(
                    success=False,
                    error="视频任务提交成功但未返回 video_id",
                    raw_response=submit_result.raw_response,
                )

            logger.info(f"[AgnesHandler] 视频任务已提交: video_id={video_id}")

            # 2. 轮询结果
            poll_url = f"{self._base_url}/agnesapi?video_id={video_id}"
            poll_headers = {"Authorization": f"Bearer {self._api_key}"}

            max_attempts = self.VIDEO_POLL_TIMEOUT // self.VIDEO_POLL_INTERVAL
            for attempt in range(max_attempts):
                await asyncio.sleep(self.VIDEO_POLL_INTERVAL)

                poll_resp = await client.get(poll_url, headers=poll_headers)
                if poll_resp.status_code != 200:
                    logger.warning(f"[AgnesHandler] 轮询失败 (attempt {attempt+1}): {poll_resp.status_code}")
                    continue

                body = poll_resp.json()
                status = body.get("status", "")
                progress = body.get("progress", 0)

                logger.info(f"[AgnesHandler] 视频轮询 (attempt {attempt+1}): status={status}, progress={progress}%")

                if status == "completed":
                    video_url = body.get("remixed_from_video_id")
                    if not video_url:
                        return StandardGenerateResult(
                            success=False,
                            error="视频已完成但未返回视频 URL",
                            raw_response=body,
                        )
                    return StandardGenerateResult(
                        success=True,
                        video_urls=[video_url],
                        raw_response=body,
                        provider_kind=self.PROVIDER_KIND,
                        model=request.model,
                    )

                if status == "failed":
                    error_info = body.get("error", {})
                    error_msg = error_info.get("message", "") if isinstance(error_info, dict) else str(error_info)
                    return StandardGenerateResult(
                        success=False,
                        error=f"视频生成失败: {error_msg or '未知错误'}",
                        raw_response=body,
                    )

            # 超时
            return StandardGenerateResult(
                success=False,
                error=f"视频生成超时（{self.VIDEO_POLL_TIMEOUT}s）",
                raw_response={"video_id": video_id, "last_status": status},
            )
