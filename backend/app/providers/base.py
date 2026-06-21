"""Provider 抽象基类 — 定义所有 Provider Handler 必须实现的接口。

设计原则：
- translate/parse 分离：Handler 只负责"翻译"，HTTP 调用由基类统一处理
- 标准模型 + extra 扩展口：通用参数走标准字段，厂商特有参数走 extra
- 向后兼容：generate_image 签名不变，translate/parse 是可选覆盖
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.schemas.provider_types import (
    ModelCapabilities,
    StandardGenerateRequest,
    StandardGenerateResult,
)

logger = logging.getLogger(__name__)


class ProviderHandler(ABC):
    """Provider 适配器基类。

    每个服务商（Agnes / SenseNova / OpenAI...）实现一个子类，
    集中管理该服务商的参数规范、API 调用、能力声明。

    新增 Handler 只需：
    1. 设置 PROVIDER_KIND 和 SUPPORTED_MODELS
    2. 实现 translate() — 将标准请求转为厂商 API 的 url/payload/headers
    3. 实现 parse() — 将厂商 API 响应转为标准结果

    generate_image() 基类提供了通用实现（translate → httpx → parse），
    只有特殊协议（如 WebSocket/流式）才需要覆盖。
    """

    # ============================================================
    # 子类必须覆盖的类属性
    # ============================================================

    # provider_kind 标识符（对应 ApiProvider.provider_kind 字段）
    PROVIDER_KIND: str = ""

    # 该服务商支持的所有模型及其参数规范
    # 结构：{ model_name: { "param_specs": [...], "capabilities": ModelCapabilities | dict } }
    SUPPORTED_MODELS: dict[str, dict[str, Any]] = {}

    # ============================================================
    # 能力声明（前端调用）
    # ============================================================

    @classmethod
    def get_capabilities(cls, model: str | None = None) -> dict:
        """返回前端需要的能力声明（含动态参数定义）。

        Args:
            model: 模型名（如 "agnes-image-2.1-flash"），
                   为 None 时返回第一个支持的模型的 capabilities。

        Returns:
            dict: {
                "provider_kind": "agnes",
                "model": "agnes-image-2.1-flash",
                "param_specs": [...],
                "batch_support": False,
                "max_count": 1,
                "reference_image": True,
                ...
            }
        """
        if not model:
            if cls.SUPPORTED_MODELS:
                model = next(iter(cls.SUPPORTED_MODELS))
            else:
                return cls._empty_capabilities()

        model_config = cls.SUPPORTED_MODELS.get(model)
        if not model_config:
            return cls._empty_capabilities()

        param_specs = model_config.get("param_specs", [])
        capabilities = model_config.get("capabilities", {})

        # 如果 capabilities 是 ModelCapabilities 实例，转为 dict
        if isinstance(capabilities, ModelCapabilities):
            caps_dict = capabilities.to_dict()
        elif isinstance(capabilities, dict):
            caps_dict = capabilities
        else:
            caps_dict = {}

        return {
            "provider_kind": cls.PROVIDER_KIND,
            "model": model,
            "param_specs": param_specs,
            **caps_dict,
        }

    @classmethod
    def _empty_capabilities(cls) -> dict:
        """返回空的 capabilities（模型未配置时）。"""
        return {
            "provider_kind": cls.PROVIDER_KIND,
            "model": None,
            "param_specs": [],
            "batch_support": False,
            "max_count": 1,
            "reference_image": False,
            "image_to_image": False,
            "video_generation": False,
            "max_reference_images": 0,
            "supports_negative_prompt": False,
        }

    @classmethod
    def list_supported_models(cls) -> list[str]:
        """返回该服务商支持的所有模型名。"""
        return list(cls.SUPPORTED_MODELS.keys())

    # ============================================================
    # 参数校验
    # ============================================================

    def validate_params(self, model: str, params: dict) -> list[str]:
        """校验参数，返回错误列表（空列表 = 全部合法）。"""
        errors = []
        model_config = self.SUPPORTED_MODELS.get(model)
        if not model_config:
            return errors

        param_specs = model_config.get("param_specs", [])
        for spec in param_specs:
            key = spec["key"]
            required = spec.get("required", False)
            value = params.get(key)

            if required and value is None:
                errors.append(f"「{spec['label']}」为必填项")

            if spec.get("input_type") == "select" and not spec.get("allow_custom", False):
                options = spec.get("options", [])
                if value and options and value not in options:
                    errors.append(f"「{spec['label']}」的值必须在 {options} 中")

        return errors

    # ============================================================
    # 核心：translate / parse（子类必须实现）
    # ============================================================

    def translate(self, request: StandardGenerateRequest) -> tuple[str, dict, dict]:
        """将标准请求转为厂商 API 的 HTTP 请求三要素。

        Args:
            request: 标准化的生成请求

        Returns:
            (url, payload, headers) — 完整的 HTTP 请求三要素

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 必须实现 translate() 方法"
        )

    def parse(self, response_body: dict, status_code: int) -> StandardGenerateResult:
        """将厂商 API 响应转为标准结果。

        Args:
            response_body: 厂商 API 返回的 JSON body
            status_code: HTTP 状态码

        Returns:
            StandardGenerateResult: 标准化的生成结果

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 必须实现 parse() 方法"
        )

    # ============================================================
    # 核心：生成图片（基类通用实现）
    # ============================================================

    async def generate_image(
        self,
        model: str,
        prompt: str,
        params: dict,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 120,
    ) -> list[str]:
        """调用服务商 API 生成图片，返回图片 URL 列表。

        基类通用流程：translate → httpx → parse → result
        子类一般不需要覆盖此方法，只需实现 translate/parse。
        只有特殊协议（如 WebSocket/流式）才需要覆盖。

        Args:
            model: 模型名（如 "agnes-image-2.1-flash"）
            prompt: 生成提示词
            params: 前端传来的参数字典（含 size, reference_images 等）
            api_key: API Key（可选，默认用初始化时的 key）
            base_url: 自定义 base URL（可选）
            timeout: 请求超时时间（秒）

        Returns:
            list[str]: 生成的图片 URL 列表

        Raises:
            Exception: API 调用失败时抛出异常
        """
        # 使用传入的参数或初始化时的参数
        api_key = api_key or getattr(self, "_api_key", "")
        base_url = (base_url or getattr(self, "_base_url", "")).rstrip("/")
        timeout = timeout or getattr(self, "_timeout", 120)

        # 构建标准请求
        request = StandardGenerateRequest(
            model=model,
            prompt=prompt,
            size=params.get("size"),
            reference_images=params.get("reference_images", []),
            count=params.get("count", 1),
            negative_prompt=params.get("negative_prompt"),
            extra=params.get("extra", {}),
        )

        # translate: 标准请求 → 厂商 API 请求
        url, payload, headers = self.translate(request)

        # 确保 headers 中有 Authorization
        if api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        logger.info(
            f"[{self.__class__.__name__}] 调用 API: model={model}, "
            f"size={request.size}, prompt={prompt[:100]}..."
        )

        # httpx 调用
        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
            duration_ms = int((time.monotonic() - start_time) * 1000)
        except httpx.TimeoutException:
            raise ValueError(f"API 请求超时（{timeout}秒）")
        except Exception as e:
            if "API 返回" in str(e) or "API 请求超时" in str(e):
                raise
            logger.error(f"[{self.__class__.__name__}] 请求失败: {e}")
            raise ValueError(f"API 请求失败: {e}")

        # parse: 厂商响应 → 标准结果
        try:
            response_body = resp.json()
        except Exception:
            response_body = {"raw_text": resp.text[:500]}

        result = self.parse(response_body, resp.status_code)
        result.duration_ms = duration_ms
        result.provider_kind = self.PROVIDER_KIND
        result.model = model
        result.raw_request = payload
        result.raw_response = response_body

        if not result.success:
            error_msg = result.error or f"API 返回 {resp.status_code}"
            logger.error(f"[{self.__class__.__name__}] {error_msg}")
            raise ValueError(error_msg)

        if not result.image_urls:
            raise ValueError("API 未返回图片 URL")

        logger.info(f"[{self.__class__.__name__}] 生成成功，返回 {len(result.image_urls)} 张图片 ({duration_ms}ms)")
        return result.image_urls

    # ============================================================
    # 核心：生成视频（异步轮询模式）
    # ============================================================

    async def generate_video(
        self,
        model: str,
        prompt: str,
        params: dict,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 120,
    ) -> list[str]:
        """调用服务商 API 生成视频，返回视频 URL 列表。

        默认实现：调用子类的 generate_video() 方法（如果实现了），
        否则走 translate → httpx → parse 流程（同步模式，不适合异步轮询）。

        对于异步轮询模式的 Provider（如 Agnes 视频），子类应覆盖此方法。

        Args:
            model: 模型名（如 "agnes-video-v2.0"）
            prompt: 生成提示词
            params: 前端传来的参数字典
            api_key: API Key
            base_url: 自定义 base URL
            timeout: 请求超时时间（秒）

        Returns:
            list[str]: 生成的视频 URL 列表
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 不支持视频生成，请实现 generate_video() 方法"
        )

    # ============================================================
    # 辅助方法（向后兼容）
    # ============================================================

    def _build_request_payload(self, model: str, prompt: str, params: dict) -> dict:
        """将通用 params 转成该服务商 API 的实际请求体（向后兼容）。

        新代码应使用 translate() 方法替代。
        """
        payload = {
            "model": model,
            "prompt": prompt,
            **params,
        }
        return payload
