# Agnes AI 高分辨率调用避坑指南

> **版本**：v1.0 | 2026-06-24
> **适用模型**：`agnes-image-2.1-flash`（图片）、`agnes-video-v2.0`（视频）
> **目的**：让任何 AI 或开发者读完本文档后，第一次就能成功调用高分辨率接口，不踩任何坑。

---

## 一、图片 API 高分辨率调用（核心重点）

### 1.1 档位 + 比例：官方推荐写法（必须用这个）

Agnes 图片 API 支持 **档位（Tier）** 格式的 `size` 参数，搭配 `ratio` 参数控制比例。**这是生成高分辨率图片的唯一正确方式。**

| 档位 | size 值 | 含义 |
|------|---------|------|
| 1K | `"1K"` | 基础分辨率 |
| 2K | `"2K"` | 超高清 |
| 4K | `"4K"` | 极致高清 |

| 比例 | ratio 值 |
|------|----------|
| 横屏 | `"16:9"` |
| 竖屏 | `"9:16"` |
| 方形 | `"1:1"` |
| 传统横屏 | `"4:3"` |
| 传统竖屏 | `"3:4"` |
| 摄影横屏 | `"3:2"` |
| 摄影竖屏 | `"2:3"` |

### 1.2 实测分辨率对照表

以下为 2026-06-24 实际调用 Agnes API 返回的分辨率，**已验证**：

| 档位 | ratio | 实际分辨率 | 文件大小 |
|------|-------|-----------|---------|
| 2K | 16:9 | **2624 x 1472** | ~4.5 MB |
| 4K | 16:9 | **5248 x 2944** | ~11.3 MB |
| 2K | 1:1 | ~2048 x 2048 | ~5 MB |
| 4K | 1:1 | ~4096 x 4096 | ~15 MB |

### 1.3 正确的请求 Payload

```json
{
  "model": "agnes-image-2.1-flash",
  "prompt": "写实摄影，电影级画质，8K超高清...",
  "size": "2K",
  "ratio": "16:9",
  "extra_body": {
    "response_format": "url",
    "ratio": "16:9"
  }
}
```

### 1.4 关键规则（踩坑总结）

#### 规则 1：`ratio` 必须同时放在顶层和 `extra_body` 中

```json
// ✅ 正确：ratio 双重传递
{
  "size": "2K",
  "ratio": "16:9",
  "extra_body": {
    "response_format": "url",
    "ratio": "16:9"
  }
}

// ❌ 错误：ratio 只放顶层 → API 可能忽略，返回正方形图片
{
  "size": "2K",
  "ratio": "16:9",
  "extra_body": {
    "response_format": "url"
  }
}

// ❌ 错误：ratio 只放 extra_body → API 可能忽略
{
  "size": "2K",
  "extra_body": {
    "response_format": "url",
    "ratio": "16:9"
  }
}
```

**原因**：Agnes API 可能从不同位置读取 `ratio`，双保险确保生效。实测只放一处会导致返回 2048x2048（正方形）而非 2624x1472（16:9）。

#### 规则 2：`size` 用档位值，不要解析为 `宽x高`

```json
// ✅ 正确：直接传档位
{ "size": "2K" }

// ❌ 错误：自己算宽高传过去
{ "size": "2048x1152" }
```

**原因**：`"2048x1152"` 不是 Agnes 支持的标准尺寸，API 会降级输出。档位值 `"2K"` 由 API 内部自动计算最优分辨率。

#### 规则 3：`response_format` 必须放在 `extra_body` 中

```json
// ✅ 正确
{ "extra_body": { "response_format": "url" } }

// ❌ 错误：放在顶层会返回 400
{ "response_format": "url" }
```

#### 规则 4：图生图的 `image` 参数放在 `extra_body.image` 中

```json
// ✅ 正确：图生图
{
  "model": "agnes-image-2.1-flash",
  "prompt": "基于首帧画面...",
  "size": "2K",
  "ratio": "16:9",
  "extra_body": {
    "response_format": "url",
    "ratio": "16:9",
    "image": ["data:image/png;base64,iVBOR..."]
  }
}
```

图生图支持 base64 Data URI 和公网 URL 两种输入方式。

#### 规则 5：不要传 `tags: ["img2img"]`

图生图不需要 `tags` 参数，只需在 `extra_body.image` 中提供输入图片即可。

---

## 二、视频 API 调用（关键限制）

### 2.1 最大分辨率限制：1920px

**Agnes 视频 API 最大宽度为 1920px，不支持 2K/4K 档位。** 传入超过 1920 的宽度会被 API 自动降级。

| 请求 size | 实际输出 | 说明 |
|-----------|---------|------|
| 2K + 16:9 | **1920 x 1088** | 降级到 1080p |
| 1920x1080 | **1920 x 1088** | 接近 1080p |
| 1152x768 | **1280 x 768** | 720p 档位 |

### 2.2 正确的视频请求 Payload

视频 API 支持两种分辨率指定方式：

**方式一：档位 + 比例（推荐，与图片模型风格统一）**

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "写实摄影，电影级画质...",
  "size": "1080p",
  "ratio": "16:9",
  "num_frames": 121,
  "frame_rate": 24,
  "image": "https://example.com/first-frame.png"
}
```

| 档位 | 含义 |
|------|------|
| `"720p"` | 720p 分辨率（1280 宽度基准） |
| `"1080p"` | 1080p 分辨率（1920 宽度基准） |

比例与图片 API 相同：`"16:9"`、`"9:16"`、`"1:1"`、`"4:3"`、`"3:4"` 等。

**方式二：直接指定 width/height（兼容旧写法）**

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "写实摄影，电影级画质...",
  "width": 1920,
  "height": 1088,
  "num_frames": 121,
  "frame_rate": 24,
  "image": "https://example.com/first-frame.png"
}
```

### 2.3 关键规则（踩坑总结）

#### 规则 1：视频 API 支持 `size` 档位和 `width`/`height` 两种写法

推荐使用 `size="1080p" + ratio="16:9"` 档位写法，与图片模型风格统一。也兼容直接传 `width`/`height` 数值。

**注意**：视频 API 不支持图片的 `"2K"`/`"4K"` 档位，最大宽度为 1920px。如果传入 `"2K"`/`"4K"`，系统会自动等比缩放到 1920px 以内。

#### 规则 2：参考图只支持公网 URL，不支持 base64

```json
// ✅ 正确：公网 URL
{ "image": "https://example.com/frame.png" }

// ❌ 错误：base64 不支持
{ "image": "data:image/png;base64,iVBOR..." }
```

**这意味着**：如果本地图片需要作为视频参考图，必须先上传到图床获取公网 URL。

#### 规则 3：首尾帧关键帧模式

当提供 2 张参考图（首帧+尾帧）时，使用关键帧模式：

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "...",
  "width": 1920,
  "height": 1088,
  "extra_body": {
    "image": [
      "https://example.com/first-frame.png",
      "https://example.com/last-frame.png"
    ],
    "mode": "keyframes"
  }
}
```

当只提供 1 张参考图时，用顶层 `image` 字段：

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "...",
  "image": "https://example.com/first-frame.png"
}
```

#### 规则 4：视频是异步任务，需要轮询

1. POST `/v1/videos` 提交任务 → 返回 `video_id`
2. GET `/agnesapi?video_id=<VIDEO_ID>` 轮询结果
3. 轮询间隔建议 5-10 秒，视频生成通常需要 3-5 分钟
4. `status` 为 `completed` 时，`remixed_from_video_id` 字段包含视频 URL

#### 规则 5：`num_frames` 必须满足 `8n + 1`

| 目标时长 | num_frames | frame_rate |
|---------|-----------|-----------|
| ~3 秒 | 81 | 24 |
| ~5 秒 | **121** | 24 |
| ~10 秒 | 241 | 24 |
| ~18 秒 | 441 | 24 |

---

## 三、图床上传陷阱（视频参考图必读）

视频 API 要求参考图使用公网 URL，需要先上传到图床。以下是踩过的坑：

### 3.1 图床文件大小限制

| 图床 | 最大文件大小 |
|------|------------|
| SM.MS | 5 MB |
| 聚合图床(superbed.cc) | 10 MB |
| 闪电图床(boltp.com) | 10 MB |

### 3.2 4K 图片超过图床限制

4K 分辨率图片（5248x2944）的 PNG 文件约 11.3 MB，**超过所有图床的 10MB 限制**。

**解决方案**：上传图床前自动压缩——转为 JPEG 并降低质量，确保文件在限制内。本项目已在 `image_hosting_service.py` 中实现了 `_compress_for_upload` 自动压缩功能。

### 3.3 压缩策略

1. 先尝试降低 JPEG 质量（85 → 75 → 65 → ... → 35）
2. 如果质量降到 35 仍超限，缩小到 1920px 宽后重试
3. 压缩后的图片作为参考图传给视频 API 是可接受的（视频 API 最大 1920px）

---

## 四、系统内部参数传递踩坑

以下是在 AI Drama Studio 系统内部调用时踩过的坑，其他系统可能有类似问题：

### 4.1 `ratio` 参数丢失问题

**现象**：前端传入 `size="2K"` + `ratio="16:9"`，但 Agnes API 只收到 `size="2K"`，没有 `ratio`，返回正方形图片。

**根因**：`base.py` 的 `generate_image()` 方法构建 `StandardGenerateRequest` 时，只从 `params` 中提取了标准字段（size、count 等），`ratio` 等非标准字段没有传递到 `request.extra`。

**修复**：将 `params` 中的非标准字段自动收集到 `extra` 中：

```python
_standard_keys = {"size", "reference_images", "count", "negative_prompt", "extra", "model", "prompt"}
extra = dict(params.get("extra", {}))
for k, v in params.items():
    if k not in _standard_keys:
        extra[k] = v
```

**注意**：`agnes_handler.py` 的 `generate_video()` 方法中直接用 `params.get("extra", {})` 构建 `StandardGenerateRequest`，没有上述非标准字段收集逻辑。如果视频生成时 ratio 丢失，需要检查 `generate_video()` 中的参数传递是否完整。

### 4.2 `params` 中缺少 `size` 字段

**现象**：`execute_task.py` 构建 `params` 时只取了 `extra_params`，没有把顶层的 `size`/`count` 合并进去。

**修复**：

```python
params = dict(input_payload.get("extra_params", input_payload.get("params", {})))
for top_key in ("size", "count"):
    if top_key in input_payload and top_key not in params:
        params[top_key] = input_payload[top_key]
```

### 4.3 datetime 时区不兼容

**现象**：`_handle_task_failure` 中 `datetime.now(timezone.utc)` 是 aware datetime，但 SQLite 的 `task.created_at` 是 naive datetime，两者相减抛出 `TypeError`。

**修复**：统一使用 naive datetime：

```python
# ❌ 错误
age = (datetime.now(timezone.utc) - task.created_at).total_seconds()

# ✅ 正确
age = (datetime.utcnow() - task.created_at.replace(tzinfo=None)).total_seconds()
```

---

## 五、一键复制：各场景完整 Payload

### 5.1 2K 图片（16:9 横屏）

```json
{
  "model": "agnes-image-2.1-flash",
  "prompt": "写实摄影，电影级画质，8K超高清，自然光影，极致细节纹理，[你的画面描述]",
  "size": "2K",
  "ratio": "16:9",
  "extra_body": {
    "response_format": "url",
    "ratio": "16:9"
  }
}
```

### 5.2 4K 图片（16:9 横屏）

```json
{
  "model": "agnes-image-2.1-flash",
  "prompt": "写实摄影，电影级画质，8K超高清，自然光影，极致细节纹理，[你的画面描述]",
  "size": "4K",
  "ratio": "16:9",
  "extra_body": {
    "response_format": "url",
    "ratio": "16:9"
  }
}
```

### 5.3 图生图（2K，16:9）

```json
{
  "model": "agnes-image-2.1-flash",
  "prompt": "基于首帧画面，生成分镜结束时的画面。[你的修改描述]",
  "size": "2K",
  "ratio": "16:9",
  "extra_body": {
    "response_format": "url",
    "ratio": "16:9",
    "image": ["data:image/png;base64,BASE64_HERE"]
  }
}
```

### 5.4 视频（1080p 档位，首帧参考）

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "写实摄影，电影级画质，8K超高清，[你的运动描述]",
  "size": "1080p",
  "ratio": "16:9",
  "num_frames": 121,
  "frame_rate": 24,
  "image": "https://your-image-host.com/first-frame.jpg"
}
```

### 5.5 视频（1080p 档位，首尾帧关键帧）

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "写实摄影，电影级画质，8K超高清，[你的过渡描述]",
  "size": "1080p",
  "ratio": "16:9",
  "num_frames": 121,
  "frame_rate": 24,
  "extra_body": {
    "image": [
      "https://your-image-host.com/first-frame.jpg",
      "https://your-image-host.com/last-frame.jpg"
    ],
    "mode": "keyframes"
  }
}
```

### 5.6 视频（width/height 写法，首帧参考）

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "写实摄影，电影级画质，8K超高清，[你的运动描述]",
  "width": 1920,
  "height": 1088,
  "num_frames": 121,
  "frame_rate": 24,
  "image": "https://your-image-host.com/first-frame.jpg"
}
```

---

## 六、快速排查清单

| 症状 | 可能原因 | 检查项 |
|------|---------|--------|
| 2K/4K 图片返回正方形 | ratio 未传递 | `ratio` 是否同时放在顶层和 `extra_body` |
| 图片返回低分辨率 | size 格式错误 | 是否用了 `"2048x1152"` 而非 `"2K"` |
| API 返回 400 | response_format 放错位置 | 是否放在顶层而非 `extra_body` |
| 图生图无效果 | image 参数位置错误 | 是否放在 `extra_body.image` 中 |
| 视频返回低分辨率 | 超过 1920px 限制 | 视频最大宽度 1920px |
| 视频参考图上传失败 | 图片文件太大 | 4K PNG 约 11MB，超过图床 10MB 限制 |
| 视频参考图 API 报错 | 传了 base64 | 视频 API 只支持公网 URL |
| 系统内部 ratio 丢失 | extra 映射问题 | 非标准字段是否自动收集到 extra |
| 4K 竖图生成超时失败 | timeout 不够 | 4K 竖图需 200+ 秒，默认 120 秒不够，需设为 300 秒 |
| 降级后 404 Not Found | base_url 重复 `/v1` | SenseNova 等已含 `/v1` 的 base_url 拼接时是否重复 |
| 降级到错误 Provider | 标签匹配逻辑 | 降级时是否按 `required_tag`（如 `image_generation`）匹配 |

---

## 七、API 基础信息速查

| 项目 | 图片 API | 视频 API |
|------|---------|---------|
| 模型名 | `agnes-image-2.1-flash` | `agnes-video-v2.0` |
| 端点 | `POST /v1/images/generations` | `POST /v1/videos` |
| 查询端点 | 无（同步返回） | `GET /agnesapi?video_id=<ID>` |
| 认证 | `Authorization: Bearer <KEY>` | `Authorization: Bearer <KEY>` |
| Base URL | `https://apihub.agnes-ai.com` | `https://apihub.agnes-ai.com` |
| 超时建议 | 60-360s（4K 竖图需 300s） | 600s（含轮询） |
| 高分辨率 | 支持 1K/2K/4K 档位 | 支持 720p/1080p 档位，最大 1920px |
| 比例控制 | `ratio` 参数（顶层 + extra_body） | `ratio` 参数（档位模式下） |
| 参考图输入 | base64 或 URL | 仅公网 URL |
| 响应格式 | `data[0].url` | 轮询后 `remixed_from_video_id` |
