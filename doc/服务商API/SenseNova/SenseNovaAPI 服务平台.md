---
created: 2026-06-19T20:26:43 (UTC +08:00)
tags: []
source: https://platform.sensenova.cn/docs
author: 
---

# SenseNova · LLM API 服务平台

> ## Excerpt
> SenseNova AI API 文档Documentation SenseNova 提供大模型 API 服务，覆盖文本对话、多模态理解、图像生成、工具调用与流式响应等能力。 Base URL · 所有接口请求基于 https://token.sensenova.cn/v1（OpenAI SDK 设置 base_url 时使用此地址） 快速开始 使用 SenseNova API 只需 3 步： 注

---
# SenseNova AI API 文档

Documentation

SenseNova 提供大模型 API 服务，覆盖文本对话、多模态理解、图像生成、工具调用与流式响应等能力。

Base URL · 所有接口请求基于 `https://token.sensenova.cn/v1`（OpenAI SDK 设置 base\_url 时使用此地址）

## 快速开始

使用 SenseNova API 只需 3 步：

1.  [注册账号](https://platform.sensenova.cn/login)并完成手机号验证
2.  在 [控制台 → API Keys](https://platform.sensenova.cn/console/keys) 创建一枚 `sk-` 开头的密钥
3.  替换 OpenAI SDK 的 `base_url` 为 SenseNova 地址（`https://token.sensenova.cn/v1`），即可调用

## 鉴权

所有 API 请求必须在 HTTP Header 中携带 Bearer Token：

建议为不同应用/环境创建独立的 API Key，以便独立监控与轮换。密钥可在 [控制台](https://platform.sensenova.cn/console/keys) 随时注销。

## 模型总览

| 模型名称 | Model ID | 调用次数限制 | 描述 |
|--------------------------|--------------------------|-----------|---------------------------------------------|
| SenseNova 6.7 Flash-Lite | `sensenova-6.7-flash-lite` | 每5小时1500次 | 面向真实工作流的轻量多模态智能体模型，支持文本对话与图像输入理解 |
| SenseNova U1 Fast | `sensenova-u1-fast` | 每5小时1500次 | 基于 SenseNova U1 的加速版本，专供信息图（Infographics）生成 |
| DeepSeek V4 Flash | `deepseek-v4-flash` | 每5小时500次 | DeepSeek 高性能对话模型，支持思考/非思考模式、1M 上下文、工具调用 |

## SenseNova 6.7 Flash-Lite

面向真实工作流的轻量多模态智能体模型，支持**文本对话**与**图像输入理解**。

-   轻量高效，兼顾效果、成本与落地性
-   原生多模态架构，支持图像输入理解（OCR、图表解读等）
-   办公场景增强，稳定支撑复杂长链路任务
-   Token 效率更优，复杂任务成本更可控
-   上下文长度 256K tokens（最大输入 252K，最大输出 64K）

model ID: `sensenova-6.7-flash-lite`

### 请求地址

### 纯文本对话

### 图像输入（多模态理解）

SenseNova 6.7 Flash-Lite 支持通过 `image_url` 类型的 content 块传入图片进行内容理解与分析。

#### 请求示例

用户消息的 `content` 可以是字符串，也可以是内容块数组。图像输入使用 `image_url` 类型：

### 工具调用 (Function Calling)

通过 `tools` 字段声明可用函数，模型会在需要时以 `tool_calls` 的形式返回调用请求。工具执行后，以 `role="tool"` 的消息把结果回传，再次请求即可获得最终答复。

#### 请求示例

#### 模型返回 tool\_calls

#### 回传工具结果

### 流式响应 (SSE)

设置 `stream: true` 后，响应 Content-Type 为 `text/event-stream`，每行以 `data: {json}` 推送一个 chunk，最后以 `data: [DONE]` 结束。

`usage` 仅在 `stream_options.include_usage=true` 时在最后一个 chunk 中返回。

### 请求参数

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|-------------------|-----------------|-----|-------------------------|----------------------------------------------------------------------------|
| `model` | string | ✅ | — | 固定为 `sensenova-6.7-flash-lite` |
| `messages` | array | ✅ | — | 对话消息列表，role ∈ {system, user, assistant, tool}；content 可为字符串或内容块数组（图像输入时使用） |
| `stream` | boolean | — | `false` | 是否以 SSE 流式返回 |
| `stream_options` | object | — | `{"include_usage": True}` | 仅 `stream=true` 生效。含 `include_usage` (boolean) |
| `temperature` | float | — | `0.6` | 采样温度，建议 [0, 2] |
| `top_p` | float | — | `0.95` | 核采样，范围 [0, 1] |
| `max_tokens` | integer | — | `65535` | 最大生成 token 数，范围 [1, 65536] |
| `n` | integer | — | `1` | 生成回复数量，范围 1–7 |
| `stop` | string | array | — | — | 停止序列 |
| `frequency_penalty` | float | — | `0` | 频率惩罚，[0,2] |
| `presence_penalty` | float | — | `0` | 存在惩罚，[0,2] |
| `reasoning_effort` | string | — | `"medium"` | 推理力度，可选值`"low"`/`"medium"`/`"high"`/`"none"` |
| `tools` | array | — | — | 可用工具列表 |
| `tool_choice` | string | object | — | `"auto"` | 工具选择策略：`"auto"` / `"none"` / `"required"` 或指定工具 |
| `parallel_tool_calls` | boolean | — | `true` | 是否允许并行调用多个工具 |
| `seed` | integer | — | — | 随机种子（Beta）,范围[0,9999999) |

### 响应结构

#### finish\_reason 枚举

| value | 含义 |
|----------------|----------------------|
| `stop` | 正常结束 |
| `length` | 达到 max_tokens 或上下文上限 |
| `tool_calls` | 模型选择调用工具 |
| `content_filter` | 内容被合规审核拦截 |

## SenseNova U1 Fast

基于SenseNova U1的加速版本，专供信息图（Infographics）生成。

model ID: `sensenova-u1-fast`

⚠️ U1 Fast 使用独立的图像生成接口，**不是** Chat Completions 接口。不支持图像输入。
3K及以上图，速率有限制1分钟1次。

### 请求地址

### 请求参数

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|--------|---------|-----|-------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `model` | string | ✅ | — | 固定为 `sensenova-u1-fast` |
| `prompt` | string | ✅ | — | 图像描述文本，最大token数为4096 |
| `size` | string | — | `"2752x1536"` | 图像尺寸，2K 分辨率常量 - 11种 aspect ratio 对应的 [width, height]<br>`1664x2496` ｜ 2:3<br>`2496x1664` ｜ 3:2<br>`1760x2368` ｜ 3:4<br>`2368x1760` ｜ 4:3<br>`1824x2272` ｜ 4:5<br>`2272x1824` ｜ 5:4<br>`2048x2048` ｜ 1:1<br>`2752x1536` ｜ 16:9<br>`1536x2752` ｜ 9:16<br>`3072x1376` ｜ 21:9<br>`1344x3136` ｜ 9:21 |
| `n` | integer | — | `1` | 生成图片数量 |

### 响应结构

## DeepSeek V4 Flash

DeepSeek 高性能对话模型，支持**思考模式**与**非思考模式**，上下文长度 1M tokens、最大输出 384K tokens。内置 JSON Output、Tool Calls等功能。

model ID: `deepseek-v4-flash`

### 请求地址

### 纯文本对话

### 思考模式

DeepSeek V4 Flash 默认启用思考模式。通过 `reasoning_effort` 参数控制：

-   `reasoning_effort`: `"low"` / `"medium"` / `"high"` / `"none"`，默认 `"medium"`
-   设为 `"none"` 关闭思考模式，设为 `"high"` 适合需要深度推理的复杂任务

思考模式下，响应的 `message` 中会额外包含 `reasoning_content` 字段，为模型的推理过程。

### 工具调用 (Function Calling)

### JSON 输出

设置 `response_format` 启用 JSON 模式（需在 prompt 中指示模型输出 JSON）：

### 流式响应 (SSE)

设置 `stream: true` 后，响应以 `text/event-stream` 形式推送，最后以 `data: [DONE]` 结束。

### 请求参数

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|-------------------|-----------------|-----|----------|-----------------------------------------------|
| `model` | string | ✅ | — | 固定为 `deepseek-v4-flash` |
| `messages` | array | ✅ | — | 对话消息列表，role ∈ {system, user, assistant, tool} |
| `reasoning_effort` | string | — | `"medium"` | 推理力度，可选值 `"low"` / `"medium"` / `"high"` / `"none"` |
| `stream` | boolean | — | `false` | 是否以 SSE 流式返回 |
| `stream_options` | object | — | — | 仅 `stream=true` 生效。含 `include_usage` (boolean) |
| `temperature` | float | — | `1` | 采样温度，范围 [0, 2) |
| `top_p` | float | — | `1` | 核采样，范围 [0, 1] |
| `max_tokens` | integer | — | `65536` | 最大生成 token 数 |
| `stop` | string | array | — | — | 停止序列 |
| `frequency_penalty` | float | — | `0` | 频率惩罚，[-2, 2] |
| `presence_penalty` | float | — | `0` | 存在惩罚，[-2, 2] |
| `response_format` | object | — | — | `{"type": "json_object"}` 启用 JSON 输出模式 |
| `tools` | array | — | — | 可用工具列表 |
| `tool_choice` | string | object | — | `"auto"` | 工具选择策略：`"none"` / `"auto"` / `"required"` 或指定工具 |

### 响应结构

#### finish\_reason 枚举

| value | 含义 |
|----------------|----------------------|
| `stop` | 正常结束 |
| `length` | 达到 max_tokens 或上下文上限 |
| `tool_calls` | 模型选择调用工具 |
| `content_filter` | 内容被合规审核拦截 |

## 模型列表

列出当前可用的模型列表，返回每个模型的基本信息，包括能力、上下文长度、定价等。

### 请求

### 认证

### 请求示例

### 响应结构

返回一个包含 `data` 数组的 JSON 对象，每个元素为一个 Model 对象。

### Model 对象字段说明

| 字段 | 类型 | 说明 |
|-----------------------------|-----------------|-------------------------------|
| `id` | string | 模型唯一标识符，用于 API 调用时指定模型 |
| `name` | string | 模型名称（通常与 `id` 一致） |
| `created` | number | 模型创建/发布时间（Unix 时间戳，秒） |
| `description` | string | 模型功能的文字描述 |
| `input_modalities` | array of string | 支持的输入模态，可选值：`text`、`image` |
| `output_modalities` | array of string | 支持的输出模态，可选值：`text`、`image` |
| `context_length` | number | 最大上下文窗口长度（token 数） |
| `max_output_length` | number | 单次请求最大输出长度（token 数） |
| `quantization` | string | 模型量化精度（如 `fp8`） |
| `pricing` | object | 定价信息 |
| `supported_sampling_parameters` | array of string | 模型支持的采样参数列表 |
| `supported_features` | array of string | 模型支持的功能特性 |
| `hugging_face_id` | string | 对应的 HuggingFace 模型 ID（如有） |
| `openrouter` | object | OpenRouter 路由信息，含 `slug` 字段 |
| `datacenters` | array of object | 模型部署的数据中心列表，含 `country_code` 字段 |

## Anthropic 兼容接口

SenseNova 同时提供 **Anthropic Messages API** 兼容端点，适用于使用 Anthropic SDK 或 Claude 生态工具的场景。

### 请求地址

### 鉴权

与 OpenAI 兼容接口共用同一 API Key，通过 `Authorization: Bearer` Header 传递：

### 请求示例

💡 使用 `authToken` 会以 `Authorization: Bearer` 方式发送密钥。若 SDK 版本不支持，可用 `apiKey` 参数替代。

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|----------------|----------------|-----|-------------------|----------------------------------------------------------------------------------------|
| `model` | string | ✅ | — | 模型 ID，如 `sensenova-6.7-flash-lite`、`deepseek-v4-flash` |
| `messages` | array | ✅ | — | 消息列表，每条消息包含 `role`（`user`/`assistant`）和 `content` |
| `max_tokens` | integer | ✅ | — | 最大输出 Token 数，范围 [1, 65536] |
| `system` | string / array | — | — | 系统提示词，可为字符串或 `[{"type":"text","text":"..."}]` 数组 |
| `temperature` | number | — | `1` | 采样温度，`sensenova-6.7-flash-lite` 模型 temperature 取值范围 [0, 2]，`deepseek-v4-flash` 模型范围 [0, 2] |
| `top_p` | number | — | `1` | 核采样概率，范围 [0, 1.0]，高级用途 |
| `stop_sequences` | array | — | — | 自定义停止序列，字符串数组，如 `["\n", "END"]` |
| `stream` | boolean | — | `false` | 是否开启流式输出（SSE） |
| `metadata` | object | — | — | 请求元数据，如 `{"user_id": "xxx"}`，透传不影响推理 |
| `tools` | array | — | — | 工具定义列表，用于函数调用 |
| `tool_choice` | object | — | `{"type":"auto"}` | 工具选择策略：`auto` / `any` / `{"type":"tool","name":"..."}` |
| `output_config` | object | — | `{"effort":"high"}` | 输出配置。`effort` 子字段控制推理力度，可选值：`"low"` / `"medium"` / `"high"` / `"max"` |

**messages 格式说明：**

-   `role` 只能为 `user` 或 `assistant`，不支持在 messages 中传入 `system` role（系统提示请用顶层 `system` 参数）
-   首条消息必须为 `user` role
-   `content` 可为字符串或 content block 数组：
-   **图片输入**（仅 `sensenova-6.7-flash-lite` 支持）：base64 或 URL 均可，支持 `image/png`、`image/jpeg`、`image/gif`、`image/webp` 格式

### 响应结构

| 字段 | 说明 |
|---------------------|----------------------------------------------------------------------------------|
| `id` | 本次请求的唯一 ID，格式为 `msg_<uuid>` |
| `type` | 固定为 `"message"` |
| `role` | 固定为 `"assistant"` |
| `content` | 内容块数组，包含 `thinking`（推理过程）和 `text`（回复文本）类型 |
| `model` | 实际使用的模型 ID |
| `stop_reason` | 停止原因：`end_turn`（自然结束）/ `max_tokens`（达到最大 Token）/ `stop_sequence`（命中停止序列）/ `tool_use`（请求函数调用） |
| `usage.input_tokens` | 输入消耗的 Token 数 |
| `usage.output_tokens` | 输出消耗的 Token 数（含 thinking 部分） |

### 流式输出（SSE）

设置 `"stream": true` 后，接口以 [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) 格式返回，事件序列如下：

### 图片输入（sensenova-6.7-flash-lite）

`sensenova-6.7-flash-lite` 通过 Anthropic Messages 接口支持图片输入，支持 Base64 和 URL 两种方式：

**Base64 方式：**

**URL 方式：**

支持格式：`image/png`、`image/jpeg`、`image/gif`、`image/webp`。可在 content 数组中传入多张图片，也支持图文混合多轮对话。

## 错误码

所有错误响应遵循统一结构：

| HTTP 状态码 | 错误类型 (type) | 含义 |
|----------|-------------------------|-----------------------------|
| 400 | `invalid_request_error` | 请求参数不合法（缺失、超范围、格式错误等） |
| 400 | `failed_precondition_error` | 前置条件不满足（编码失败、引擎不可用、安全检查未通过） |
| 403 | `permission_denied_error` | 不支持当前语言的请求 |
| 404 | `not_found_error` | 模型 ID 不存在或已下线 |
| 408 | `canceled_error` | 客户端取消请求 |
| 429 | `quota_exceeded_error` | 速率/额度超限，建议指数退避重试 |
| 500 | `internal_server_error` | 服务器内部错误 |

