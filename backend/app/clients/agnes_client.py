"""Agnes AI API 客户端。

支持三个模型：
- agnes-2.0-flash: 文本生成（同步，OpenAI 兼容）
- agnes-image-2.1-flash: 文生图（同步，OpenAI 兼容 images.generate）
- agnes-video-v2.0: 文生视频（异步，需轮询）

Base URL: https://apihub.agnes-ai.com/v1
认证: Bearer Token（与 OpenAI 兼容）
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"


class AgnesClient:
    """Agnes AI API 客户端。"""

    def __init__(self, api_key: str, timeout: int = 120):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = AGNES_BASE_URL
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._client.close()

    # ============================================================
    # 文生图（同步，OpenAI 兼容）
    # ============================================================

    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        model: str = "agnes-image-2.1-flash",
        n: int = 1,
    ) -> list[str]:
        """生成图片，返回图片 URL 列表。

        API 是同步的，通常 30-60 秒返回。
        返回格式: {"data": [{"url": "..."}, ...]}

        参数:
        - prompt: 提示词
        - size: 图片尺寸，如 "1024x1024"、"512x512" 等
        - model: 模型名称
        - n: 生成数量
        """
        # Prompt 过长时截断
        if len(prompt) > 2000:
            logger.warning(f"[Agnes] Prompt 过长({len(prompt)}字符)，截断到2000字符")
            prompt = prompt[:2000]

        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "extra_body": {
                "response_format": "url"
            }
        }
        logger.info(f"[Agnes] 生图请求体: model={model}, size={size}, n={n}, prompt长度={len(prompt)}")
        try:
            resp = self._client.post(
                "/images/generations",
                json=payload,
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                # 400/422 等错误，打印响应体帮助排查
                logger.error(f"[Agnes] 生图失败 HTTP {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            # 把 API 返回的错误信息也记录下来
            try:
                error_detail = e.response.json()
                logger.error(f"[Agnes] 生图 API 错误详情: {error_detail}")
            except Exception:
                logger.error(f"[Agnes] 生图 API 原始响应: {e.response.text}")
            raise
        data = resp.json()
        # OpenAI 兼容格式: {"data": [{"url": "..."}]}
        urls = [item["url"] for item in data.get("data", [])]
        logger.info(f"[Agnes] 生图成功，返回 {len(urls)} 个 URL")
        return urls

    # ============================================================
    # 文生视频（异步，需轮询）
    # ============================================================

    def submit_video_task(
        self,
        prompt: str,
        image: Optional[str] = None,
        model: str = "agnes-video-v2.0",
        num_frames: int = 121,
        frame_rate: int = 24,
        width: int = 1152,
        height: int = 768,
    ) -> str:
        """提交视频生成任务，返回 task_id。

        image: 可选的输入图片 URL（图生视频）
        num_frames: 必须是 8n+1（81/121/161/241）
        """
        body = {
            "model": model,
            "prompt": prompt,
            "num_frames": num_frames,
            "frame_rate": frame_rate,
            "width": width,
            "height": height,
        }
        if image:
            body["image"] = image

        resp = self._client.post("/videos", json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("id")
        if not task_id:
            raise ValueError(f"提交视频任务失败，响应中没有 id: {data}")
        return task_id

    def get_video_task(self, task_id: str) -> dict:
        """查询视频任务状态。

        返回格式:
        - 运行中: {"id": "...", "status": "processing"}
        - 完成: {"id": "...", "status": "completed", "remixed_from_video_id": "视频URL"}
        - 失败: {"id": "...", "status": "failed", "error": "..."}
        """
        resp = self._client.get(f"/videos/{task_id}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def wait_video_completion(
        self,
        task_id: str,
        poll_interval: int = 10,
        max_wait: int = 600,
    ) -> str:
        """轮询视频任务直到完成，返回视频 URL。

        Raises:
            TimeoutError: 超过 max_wait 秒仍未完成
            ValueError: 任务失败
        """
        start = time.time()
        while time.time() - start < max_wait:
            data = self.get_video_task(task_id)
            status = data.get("status", "unknown")
            logger.info(f"[Agnes] 视频任务 {task_id} 状态: {status}")

            if status == "completed":
                video_url = data.get("remixed_from_video_id") or data.get("video_url")
                if not video_url:
                    raise ValueError(f"任务完成但未返回视频 URL: {data}")
                return video_url
            elif status == "failed":
                error = data.get("error", "未知错误")
                raise ValueError(f"视频生成失败: {error}")

            time.sleep(poll_interval)

        raise TimeoutError(f"视频任务 {task_id} 超时（{max_wait}s）")

    # ============================================================
    # 文本生成（同步，OpenAI 兼容）
    # ============================================================

    def generate_text(
        self,
        messages: list[dict],
        model: str = "agnes-2.0-flash",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """文本生成，返回生成的文本。"""
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens

        resp = self._client.post("/chat/completions", json=body, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ============================================================
# 异步辅助函数（在非阻塞线程中运行同步客户端）
# ============================================================


async def async_generate_image(client: AgnesClient, **kwargs) -> list[str]:
    """异步包装：在非阻塞线程中运行同步生图调用。"""
    return await asyncio.to_thread(client.generate_image, **kwargs)


async def async_submit_video_task(client: AgnesClient, **kwargs) -> str:
    """异步包装：在非阻塞线程中运行同步提交视频任务。"""
    return await asyncio.to_thread(client.submit_video_task, **kwargs)


async def async_wait_video_completion(
    client: AgnesClient,
    task_id: str,
    poll_interval: int = 10,
    max_wait: int = 600,
) -> str:
    """异步轮询视频任务（使用 asyncio.sleep，不阻塞事件循环）。"""

    async def _poll() -> str:
        start = time.time()
        while time.time() - start < max_wait:
            data = await asyncio.to_thread(client.get_video_task, task_id)
            status = data.get("status", "unknown")
            logger.info(f"[Agnes] 视频任务 {task_id} 状态: {status}")

            if status == "completed":
                video_url = data.get("remixed_from_video_id") or data.get("video_url")
                if not video_url:
                    raise ValueError(f"任务完成但未返回视频 URL: {data}")
                return video_url
            elif status == "failed":
                error = data.get("error", "未知错误")
                raise ValueError(f"视频生成失败: {error}")

            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"视频任务 {task_id} 超时（{max_wait}s）")

    return await _poll()


async def async_download_file(url: str, output_path: Path, timeout: int = 120) -> None:
    """异步包装：在非阻塞线程中运行同步文件下载。"""
    return await asyncio.to_thread(download_file, url, output_path, timeout)


def download_file(url: str, output_path: Path, timeout: int = 120, max_retries: int = 3) -> None:
    """下载文件到本地（原子写入：先下载到临时文件，成功后 rename，支持重试）。"""
    import os
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
            os.replace(str(tmp_path), str(output_path))
            logger.info(f"[Agnes] 文件已下载: {output_path}")
            return
        except (OSError, httpx.HTTPError) as e:
            last_exc = e
            logger.warning(f"[Agnes] 下载失败（第 {attempt}/{max_retries} 次）: {e}")
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            if attempt < max_retries:
                import time
                time.sleep(2 * attempt)  # 递增等待
    raise last_exc  # type: ignore[misc]
