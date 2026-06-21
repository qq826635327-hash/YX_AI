"""Provider 标准化请求/响应模型。

所有 Handler 统一使用这些模型进行输入/输出，
将厂商 API 差异封装在 Handler.translate() / Handler.parse() 内部。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StandardGenerateRequest(BaseModel):
    """所有 Provider 统一的输入模型。

    execute_task 将参数组装到此模型后传给 Handler，
    Handler 在 translate() 中将其转为厂商 API 的实际请求体。
    """

    model: str = Field(description="模型名，如 agnes-image-2.1-flash")
    prompt: str = Field(description="生成提示词")
    negative_prompt: str | None = Field(default=None, description="反向提示词")
    size: str | None = Field(default=None, description="分辨率，如 1920x1080")
    reference_images: list[str] = Field(default_factory=list, description="参考图 Data URI Base64 列表")
    count: int = Field(default=1, ge=1, description="生成数量")
    extra: dict[str, Any] = Field(default_factory=dict, description="厂商特有参数扩展口")


class StandardGenerateResult(BaseModel):
    """所有 Provider 统一的输出模型。

    Handler 在 parse() 中将厂商 API 响应转为此模型，
    execute_task 根据此模型决定后续流程（下载/报错等）。
    """

    success: bool = Field(description="是否成功")
    image_urls: list[str] = Field(default_factory=list, description="生成的图片 URL 列表")
    video_urls: list[str] = Field(default_factory=list, description="生成的视频 URL 列表")
    raw_request: dict[str, Any] = Field(default_factory=dict, description="实际发给厂商的 payload（调试用）")
    raw_response: dict[str, Any] = Field(default_factory=dict, description="厂商原始响应（调试用）")
    provider_kind: str = Field(default="", description="Provider 标识")
    model: str = Field(default="", description="使用的模型名")
    usage: dict[str, Any] = Field(default_factory=dict, description="token/次数消耗")
    error: str | None = Field(default=None, description="错误信息")
    duration_ms: int | None = Field(default=None, description="API 调用耗时（毫秒）")


class ModelCapabilities(BaseModel):
    """模型能力声明（扩展版）。

    替代之前 capabilities dict 中的零散字段，
    提供更丰富的能力描述供前端和后端使用。
    """

    image_generation: bool = Field(default=True, description="是否支持图片生成")
    image_to_image: bool = Field(default=False, description="是否支持图生图")
    video_generation: bool = Field(default=False, description="是否支持视频生成")
    batch_support: bool = Field(default=False, description="是否支持批量生成")
    max_count: int = Field(default=1, description="单次最大生成数量")
    max_reference_images: int = Field(default=0, description="最大参考图数量（0=不支持）")
    supports_negative_prompt: bool = Field(default=False, description="是否支持反向提示词")
    custom_size_range: tuple[int, int] = Field(default=(256, 2048), description="自定义尺寸范围 (min, max)")
    reference_images_need_url: bool = Field(default=False, description="参考图是否需要公网 URL（False=支持 base64）")

    def to_dict(self) -> dict[str, Any]:
        """转为前端兼容的 dict（兼容旧 capabilities 格式）。"""
        return {
            "image_generation": self.image_generation,
            "image_to_image": self.image_to_image,
            "video_generation": self.video_generation,
            "batch_support": self.batch_support,
            "max_count": self.max_count,
            "reference_image": self.image_to_image,
            "max_reference_images": self.max_reference_images,
            "supports_negative_prompt": self.supports_negative_prompt,
            "custom_size_range": list(self.custom_size_range),
            "reference_images_need_url": self.reference_images_need_url,
        }
