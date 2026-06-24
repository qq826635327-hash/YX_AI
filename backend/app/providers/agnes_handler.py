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
import time
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
                        "1K",
                        "2K",
                        "4K",
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
                    "default": "2K",
                    "placeholder": "档位(1K/2K/4K) 或 宽x高",
                    "help_text": "推荐使用 2K/4K 档位 + 比例参数，可稳定输出超高清分辨率",
                },
                {
                    "key": "ratio",
                    "label": "画面比例",
                    "required": False,
                    "input_type": "select",
                    "options": ["16:9", "9:16", "4:3", "3:4", "1:1", "3:2", "2:3", "21:9"],
                    "default": "16:9",
                    "help_text": "配合 2K/4K 档位使用，自动计算宽高",
                },
            ],
            "capabilities": ModelCapabilities(
                image_generation=True,
                image_to_image=True,
                video_generation=False,
                batch_support=False,
                max_count=1,
                max_reference_images=5,
                supports_negative_prompt=False,
                custom_size_range=(256, 8192),  # 4K 档位实际输出可达 5248x2944，留余量
                reference_images_need_url=False,  # 图片 API 支持 base64
            ),
        },
        "agnes-video-v2.0": {
            "param_specs": [
                {
                    "key": "size",
                    "label": "分辨率",
                    "required": False,
                    "input_type": "select",
                    "options": [
                        "720p",
                        "1080p",
                    ],
                    "allow_custom": True,
                    "default": "1080p",
                    "placeholder": "720p / 1080p 或 宽x高",
                    "help_text": "视频最大宽度 1920px，推荐 1080p(1920x1088) 或 720p(1280x720)",
                },
                {
                    "key": "ratio",
                    "label": "画面比例",
                    "required": False,
                    "input_type": "select",
                    "options": ["16:9", "9:16", "4:3", "3:4", "1:1"],
                    "default": "16:9",
                    "help_text": "配合 720p/1080p 档位使用",
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
                video_reference_types=["first_frame", "last_frame"],  # 关键帧模式：仅首尾帧
                video_reference_hint="当前模型为首尾关键帧模式，建议仅选择首帧和尾帧作为参考图",
            ),
        },
    }

    # 视频轮询配置
    VIDEO_POLL_INTERVAL = 10  # 秒
    VIDEO_POLL_TIMEOUT = 600  # 10 分钟

    def __init__(self, api_key: str, base_url: str | None = None, timeout: int = 120):
        self._api_key = api_key
        self._base_url = (base_url or "https://apihub.agnes-ai.com").rstrip("/")
        self._timeout = timeout

    # ============================================================
    # 辅助方法
    # ============================================================

    # 图片 size 档位 → 基础宽度映射（按 16:9 比例，其他比例自动换算）
    SIZE_TIERS = {
        "1K": 1024,
        "2K": 2048,
        "4K": 4096,
    }

    # 视频 size 档位 → (默认宽度, 最大宽度) 映射
    VIDEO_SIZE_TIERS = {
        "720p": (1280, 1280),
        "1080p": (1920, 1920),
    }

    # 常用比例 → 宽高比（宽/高）
    RATIO_MAP = {
        "1:1": 1.0,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "3:2": 3 / 2,
        "2:3": 2 / 3,
        "21:9": 21 / 9,
    }

    def _resolve_size(self, size: str | None, ratio: str | None) -> str | None:
        """将 size+ratio 解析为 "宽x高" 格式。

        支持三种输入：
        1. size="2K", ratio="16:9" → "2048x1152"（官方推荐档位写法）
        2. size="1920x1080" → 直接使用（兼容旧格式）
        3. size=None → 返回 None
        """
        if not size:
            return None

        # 已经是 宽x高 格式，直接返回
        if "x" in size.lower():
            return size

        # 档位写法：size="2K"/"4K" + ratio="16:9"
        tier = self.SIZE_TIERS.get(size.upper())
        if tier is None:
            logger.warning(f"[AgnesHandler] 未知 size 档位: {size}，回退为 1920x1080")
            return "1920x1080"

        # 解析比例
        aspect = self.RATIO_MAP.get(ratio) if ratio else (16 / 9)  # 默认 16:9
        if aspect is None:
            logger.warning(f"[AgnesHandler] 未知 ratio: {ratio}，回退为 16:9")
            aspect = 16 / 9

        # 按比例计算宽高（确保 8 的倍数对齐，避免 API 拒绝）
        if aspect >= 1:
            w = tier
            h = round(tier / aspect / 8) * 8
        else:
            h = tier
            w = round(tier * aspect / 8) * 8

        return f"{w}x{h}"

    def _resolve_video_size(
        self, size: str | None, ratio: str | None, extra: dict | None
    ) -> tuple[int | None, int | None]:
        """将视频的 size+ratio 解析为 (width, height)。

        支持三种输入：
        1. size="1080p", ratio="16:9" → (1920, 1088)（档位写法）
        2. size="1920x1088" → (1920, 1088)（宽x高写法）
        3. size=None, extra 中有 width/height → 使用 extra 值
        """
        # 1. 优先使用 size 参数
        if size:
            # 宽x高 格式
            if "x" in size.lower():
                parts = size.lower().split("x")
                if len(parts) == 2:
                    try:
                        return int(parts[0]), int(parts[1])
                    except ValueError:
                        pass

            # 视频档位写法：720p / 1080p
            tier_info = self.VIDEO_SIZE_TIERS.get(size.lower())
            if tier_info:
                base_width = tier_info[0]
                # 解析比例
                aspect = self.RATIO_MAP.get(ratio) if ratio else (16 / 9)
                if aspect is None:
                    aspect = 16 / 9
                # 按比例计算宽高（8 的倍数对齐）
                if aspect >= 1:
                    w = base_width  # 横屏：宽度 = 档位宽度
                    h = round(w / aspect / 8) * 8
                else:
                    h = base_width  # 竖屏：高度 = 档位宽度
                    w = round(h * aspect / 8) * 8
                return w, h

            # 图片档位写法（2K/4K）降级到视频最大 1920
            if size.upper() in self.SIZE_TIERS:
                resolved = self._resolve_size(size, ratio)
                if resolved:
                    parts = resolved.lower().split("x")
                    if len(parts) == 2:
                        w, h = int(parts[0]), int(parts[1])
                        # 视频 API 最大 1920px，等比缩放
                        if w > 1920:
                            scale = 1920 / w
                            w = 1920
                            h = round(h * scale / 8) * 8
                        return w, h

        # 2. 回退到 extra 中的 width/height
        if extra:
            w = extra.get("width")
            h = extra.get("height")
            if w or h:
                return int(w) if w else None, int(h) if h else None

        # 3. 无 size 也无 width/height，返回 None（使用 API 默认值）
        return None, None

    def _is_video_model(self, model: str) -> bool:
        """判断是否为视频模型。优先从 capabilities 读取，fallback 到模型名前缀。"""
        caps = self.SUPPORTED_MODELS.get(model, {}).get("capabilities", {})
        if isinstance(caps, ModelCapabilities):
            return caps.video_generation
        if isinstance(caps, dict) and "video_generation" in caps:
            return caps.get("video_generation", False)
        return model.startswith("agnes-video")

    # ============================================================
    # 参数校验
    # ============================================================

    def validate_params(self, model: str, params: dict, param_specs_override: list | None = None) -> list[str]:
        """Agnes 参数校验。"""
        errors = super().validate_params(model, params, param_specs_override=param_specs_override)

        if self._is_video_model(model):
            # 视频参数校验
            size = params.get("size", "")
            if size:
                # 视频档位写法：720p / 1080p
                if size.lower() in self.VIDEO_SIZE_TIERS:
                    ratio = params.get("ratio", "")
                    if ratio and ratio not in self.RATIO_MAP:
                        errors.append(f"「画面比例」不支持：{ratio}，可选：{', '.join(self.RATIO_MAP.keys())}")
                elif size.upper() in self.SIZE_TIERS:
                    # 图片档位（2K/4K）用于视频，会自动降级到 1920px
                    ratio = params.get("ratio", "")
                    if ratio and ratio not in self.RATIO_MAP:
                        errors.append(f"「画面比例」不支持：{ratio}，可选：{', '.join(self.RATIO_MAP.keys())}")
                elif re.match(r"^\d+x\d+$", size):
                    try:
                        w, h = size.split("x")
                        if int(w) > 1920 or int(h) > 1920:
                            errors.append("视频分辨率最大 1920px，当前值超出限制")
                    except ValueError:
                        errors.append(f"「分辨率」格式错误：{size}")
                else:
                    errors.append(f"「分辨率」格式错误，应为档位（720p/1080p）或「宽x高」，当前值：{size}")

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
                # 档位写法（1K/2K/4K）+ ratio，由 _resolve_size 在 translate 阶段解析
                if size.upper() in self.SIZE_TIERS:
                    # 档位格式合法，校验 ratio（如果提供）
                    ratio = params.get("ratio", "")
                    if ratio and ratio not in self.RATIO_MAP:
                        errors.append(f"「画面比例」不支持：{ratio}，可选：{', '.join(self.RATIO_MAP.keys())}")
                elif re.match(r"^\d+x\d+$", size):
                    try:
                        w, h = size.split("x")
                        # 从模型 capabilities 读取尺寸范围，不再硬编码
                        model_caps = self.SUPPORTED_MODELS.get(model, {}).get("capabilities")
                        if isinstance(model_caps, ModelCapabilities):
                            size_min, size_max = model_caps.custom_size_range
                        else:
                            # 非内置模型（如 SenseNova）：仅校验最小值，不限制上限（由 API 自身校验）
                            size_min, size_max = 256, 99999
                        if int(w) < size_min or int(h) < size_min:
                            errors.append(f"「分辨率」宽高不能小于 {size_min}")
                        if size_max < 99999 and (int(w) > size_max or int(h) > size_max):
                            errors.append(f"「分辨率」宽高不能大于 {size_max}（当前模型限制）")
                    except ValueError:
                        errors.append(f"「分辨率」格式错误：{size}")
                else:
                    errors.append(f"「分辨率」格式错误，应为档位（1K/2K/4K）或「宽x高」（如 1024x1024），当前值：{size}")

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
        # base_url 可能已包含 /v1（如 SenseNova），避免重复拼接
        if self._base_url.endswith("/v1"):
            url = f"{self._base_url}/images/generations"
        else:
            url = f"{self._base_url}/v1/images/generations"

        # 支持 size="2K"/"4K" + ratio="16:9" 的官方推荐写法
        # 档位格式直接传给 API（由 API 自动计算宽高），非档位格式才解析为 宽x高
        ratio = request.extra.get("ratio") if request.extra else None
        raw_size = request.size

        if raw_size and raw_size.upper() in self.SIZE_TIERS:
            # 官方推荐：直接传档位 + ratio
            size = raw_size.upper()
        else:
            # 兼容旧格式：解析为 宽x高
            size = self._resolve_size(raw_size, ratio) or "1024x1024"

        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "size": size,
            "extra_body": {
                "response_format": "url",
            },
        }

        # 档位模式下，ratio 同时作为顶层参数和 extra_body 参数传给 API
        # （Agnes API 可能从不同位置读取 ratio，双保险）
        if size in self.SIZE_TIERS and ratio:
            payload["ratio"] = ratio
            payload["extra_body"]["ratio"] = ratio

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
            # 档位模式下 ratio 已单独处理，避免重复
            if size in self.SIZE_TIERS:
                extra_copy.pop("ratio", None)
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
        if self._base_url.endswith("/v1"):
            url = f"{self._base_url}/videos"
        else:
            url = f"{self._base_url}/v1/videos"

        payload = {
            "model": request.model,
            "prompt": request.prompt,
        }

        # 分辨率：支持 size 档位（720p/1080p）+ ratio，或直接 宽x高
        ratio = request.extra.get("ratio") if request.extra else None
        width, height = self._resolve_video_size(request.size, ratio, request.extra)
        if width:
            payload["width"] = width
        if height:
            payload["height"] = height

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
            for key in ("width", "height", "num_frames", "frame_rate", "ratio"):
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

    async def generate_video(
        self,
        model: str,
        prompt: str,
        params: dict,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 120,
        resume_video_id: str | None = None,
        on_submitted: Any = None,
    ) -> list[str]:
        """视频生成：提交任务 → 轮询结果 → 返回视频 URL。

        Agnes 视频 API 是异步的：
        1. POST /v1/videos → 返回 video_id
        2. GET /agnesapi?video_id=xxx → 轮询直到 status=completed
        3. 从 remixed_from_video_id 取视频 URL

        断点续传：
        - resume_video_id: 如果上次已提交但轮询中断，传入已有的 video_id 跳过提交
        - on_submitted: 提交成功后的回调 async fn(video_id)，
                        用于立即持久化 video_id 到 DB，防止中断丢失
        """
        # 构建 StandardGenerateRequest 以复用 translate/parse
        start_time = time.time()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            video_id = resume_video_id

            # 1. 提交任务（如果有 resume_video_id 则跳过）
            if not video_id:
                # 与 base.py generate_image() 一致：将非标准字段收集到 extra 中
                _standard_keys = {"size", "reference_images", "count", "negative_prompt", "extra", "model", "prompt"}
                extra = dict(params.get("extra", {}))
                for k, v in params.items():
                    if k not in _standard_keys:
                        extra[k] = v
                request = StandardGenerateRequest(
                    model=model,
                    prompt=prompt,
                    size=params.get("size"),
                    reference_images=params.get("reference_images", []),
                    count=params.get("count", 1),
                    negative_prompt=params.get("negative_prompt"),
                    extra=extra,
                )
                url, payload, headers = self.translate(request)

                resp = await client.post(url, json=payload, headers=headers)
                submit_result = self.parse(resp.json(), resp.status_code)

                if not submit_result.success:
                    raise ValueError(submit_result.error or "视频任务提交失败")

                video_id = submit_result.raw_response.get("video_id")
                if not video_id:
                    raise ValueError("视频任务提交成功但未返回 video_id")

                logger.info(f"[AgnesHandler] 视频任务已提交: video_id={video_id}")

                # 提交成功后立即回调，让调用方持久化 video_id 到 DB
                if on_submitted:
                    try:
                        await on_submitted(video_id)
                    except Exception as cb_err:
                        logger.warning(f"[AgnesHandler] on_submitted 回调失败: {cb_err}")
            else:
                logger.info(f"[AgnesHandler] 断点续传：跳过提交，直接轮询 video_id={video_id}")

            # 2. 轮询结果
            if self._base_url.endswith("/v1"):
                poll_url = f"{self._base_url}/agnesapi?video_id={video_id}"
            else:
                poll_url = f"{self._base_url}/v1/agnesapi?video_id={video_id}"
            poll_headers = {"Authorization": f"Bearer {self._api_key}"}

            max_attempts = self.VIDEO_POLL_TIMEOUT // self.VIDEO_POLL_INTERVAL
            last_status = ""
            for attempt in range(max_attempts):
                await asyncio.sleep(self.VIDEO_POLL_INTERVAL)

                poll_resp = await client.get(poll_url, headers=poll_headers)
                if poll_resp.status_code != 200:
                    logger.warning(f"[AgnesHandler] 轮询失败 (attempt {attempt+1}): {poll_resp.status_code}")
                    continue

                body = poll_resp.json()
                status = body.get("status", "")
                progress = body.get("progress", 0)
                last_status = status

                logger.info(f"[AgnesHandler] 视频轮询 (attempt {attempt+1}): status={status}, progress={progress}%")

                if status == "completed":
                    video_url = body.get("remixed_from_video_id")
                    if not video_url:
                        raise ValueError("视频已完成但未返回视频 URL")
                    logger.info(f"[AgnesHandler] 视频生成成功: {video_url[:100]}")
                    # 保存元数据供调用方读取
                    from app.schemas.provider_types import StandardGenerateResult
                    self._last_result = StandardGenerateResult(
                        success=True,
                        video_urls=[video_url],
                        provider_kind=self.PROVIDER_KIND,
                        model=model,
                        duration_ms=int((time.time() - start_time) * 1000),
                        raw_response=body,
                    )
                    return [video_url]

                if status == "failed":
                    error_info = body.get("error", {})
                    error_msg = error_info.get("message", "") if isinstance(error_info, dict) else str(error_info)
                    raise ValueError(f"视频生成失败: {error_msg or '未知错误'}")

            # 超时
            raise ValueError(f"视频生成超时（{self.VIDEO_POLL_TIMEOUT}s），最后状态: {last_status}")


# custom provider_kind 复用 AgnesHandler（OpenAI 兼容格式）
# param_specs 和 capabilities 完全从 DB 读取，不依赖代码中的 SUPPORTED_MODELS
from app.providers.registry import register_alias
register_alias("custom", AgnesHandler)
