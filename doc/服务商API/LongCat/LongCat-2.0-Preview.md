---
created: 2026-06-22T11:54:19 (UTC +08:00)
tags: []
source: https://longcat.chat/platform/docs/zh/APIDocs.html
author: 
---

# LongCat API开放平台接口文档 | API 文档

> ## Excerpt
> 概述LongCat API开放平台专为LongCat系列模型提供AI模型代理服务，同时兼容OpenAI和Anthropic API格式。本文档遵循标准API格式约定。基础URL生产环境端点: https://api.longcat.chat认证所有API请求都需要在Authorization头中使用API密钥进行认证：Authorization: Bearer YOUR_API_KEY接口聊天补全

---
## [概述](https://longcat.chat/platform/docs/zh/APIDocs.html#%E6%A6%82%E8%BF%B0)

LongCat API开放平台专为LongCat系列模型提供AI模型代理服务，同时兼容OpenAI和Anthropic API格式。本文档遵循标准API格式约定。

## [基础URL](https://longcat.chat/platform/docs/zh/APIDocs.html#%E5%9F%BA%E7%A1%80url)

```bash
生产环境端点: https://api.longcat.chat
```

## [认证](https://longcat.chat/platform/docs/zh/APIDocs.html#%E8%AE%A4%E8%AF%81)

所有API请求都需要在Authorization头中使用API密钥进行认证：

```makefile
Authorization: Bearer YOUR_API_KEY
```

## [接口](https://longcat.chat/platform/docs/zh/APIDocs.html#%E6%8E%A5%E5%8F%A3)

### [聊天补全](https://longcat.chat/platform/docs/zh/APIDocs.html#%E8%81%8A%E5%A4%A9%E8%A1%A5%E5%85%A8)

#### [POST /openai/v1/chat/completions](https://longcat.chat/platform/docs/zh/APIDocs.html#post-openai-v1-chat-completions)

使用OpenAI兼容格式创建聊天补全。

**请求头**

-   `Authorization: Bearer YOUR_API_KEY`（必填）
-   `Content-Type: application/json`

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|-------------|---------|-----|----------------------------------------------------|
| `model` | string | 是 | 模型标识符 |
| `messages` | array | 是 | 消息对象数组，仅允许文本输入 |
| `stream` | boolean | 否 | 是否以流式返回响应（默认：false） |
| `max_tokens` | integer | 否 | 生成的最大token数，LongCat-2.0-Preview 默认为32768，最大为131072 |
| `temperature` | number | 否 | 采样温度，范围0到1 |
| `top_p` | number | 否 | 核采样参数 |

**消息对象**

| 字段 | 类型 | 必填 | 说明 |
|---------|--------|-----|---------------------------------------------------------------------------------------------|
| `role` | string | 是 | 消息作者角色。必须为以下之一：<br>• `system` - 设置助手行为和上下文<br>• `user` - 人类用户消息<br>• `assistant` - AI助手消息（用于会话历史） |
| `content` | string | 是 | 消息内容。简单文本消息字符串 |

**请求示例对话**

```json
{
  "model": "LongCat-2.0-Preview",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Hello, how are you?"
    }
  ],
  "stream": false,
  "max_tokens": 150,
  "temperature": 0.7
}
```

**响应（非流式）**

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "LongCat-2.0-Preview",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking. How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 15,
    "total_tokens": 35
  }
}
```

**响应（流式）**

当`stream: true`时，响应以Server-Sent Events (SSE)返回：

```kotlin
Content-Type: text/event-stream

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"LongCat-2.0-Preview","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"LongCat-2.0-Preview","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"LongCat-2.0-Preview","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: [DONE]
```

### [Anthropic消息](https://longcat.chat/platform/docs/zh/APIDocs.html#anthropic%E6%B6%88%E6%81%AF)

#### [POST /anthropic/v1/messages](https://longcat.chat/platform/docs/zh/APIDocs.html#post-anthropic-v1-messages)

使用Anthropic的Claude API格式创建消息。

**请求头**

-   `Authorization: Bearer YOUR_API_KEY`（必填）
-   `Content-Type: application/json`

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|-------------|---------|-----|---------------------|
| `model` | string | 是 | Claude模型名称 |
| `messages` | array | 是 | 消息对象数组 |
| `max_tokens` | integer | 否 | 生成的最大token数 |
| `stream` | boolean | 否 | 是否以流式返回响应（默认：false） |
| `temperature` | number | 否 | 采样温度，范围0到1 |
| `top_p` | number | 否 | 核采样参数 |
| `system` | string | 否 | 用于设置上下文的系统消息 |

**消息对象**

| 字段 | 类型 | 必填 | 说明 |
|---------|--------|-----|-------------------------------------------------------------------------------------------------|
| `role` | string | 是 | 消息作者角色。必须为以下之一：<br>• `user` - 人类用户消息<br>• `assistant` - Claude助手消息（用于会话历史）<br>注意：系统消息通过`system`参数单独传递 |
| `content` | string | 是 | 消息内容。仅支持文本消息字符串 |

**请求示例**

```json
{
  "model": "LongCat-2.0-Preview",
  "max_tokens": 1000,
  "messages": [
    {
      "role": "user",
      "content": "Hello, LongCat"
    }
  ],
  "stream": false,
  "temperature": 0.7
}
```

**响应（非流式）**

```json
{
  "id": "msg_123",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Hello! How can I help you today?"
    }
  ],
  "model": "LongCat-2.0-Preview",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 10,
    "output_tokens": 8
  }
}
```

**响应（流式）**

当`stream: true`时，响应遵循Anthropic的SSE格式：

# [LongCat API开放平台接口文档](https://longcat.chat/platform/docs/zh/APIDocs.html/#longcat-api开放平台接口文档)

```csharp
Content-Type: text/event-stream

event: message_start
data: {"type": "message_start", "message": {"id": "msg_123", "type": "message", "role": "assistant", "content": [], "model": "LongCat-2.0-Preview", "stop_reason": null, "stop_sequence": null, "usage": {"input_tokens": 10, "output_tokens": 0}}}

event: content_block_start
data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}

event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}

event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "!"}}

event: content_block_stop
data: {"type": "content_block_stop", "index": 0}

event: message_delta
data: {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": null}, "usage": {"output_tokens": 8}}

event: message_stop
data: {"type": "message_stop"}
```

### [模型接口](https://longcat.chat/platform/docs/zh/APIDocs.html#%E6%A8%A1%E5%9E%8B%E6%8E%A5%E5%8F%A3)

#### [GET /v1/models](https://longcat.chat/platform/docs/zh/APIDocs.html#get-v1-models)

支持openai和anthropic两个端点下列出 LongCat 可用的模型列表，并提供相关模型的基本信息

| 接口 | 说明 |
|----------------------|--------------------|
| /openai/v1/models | openai端点下获取模型列表 |
| /anthropic/v1/models | anthropic端点下获取模型列表 |

**请求头**

-   `Authorization: Bearer YOUR_API_KEY`（必填）
-   `Content-Type: application/json`

示例：

```rust
curl --location 'https://api.longcat.chat/openai/v1/models' \
--header 'Authorization: Bearer YOUR_API_KEY' \
--header 'Content-Type: application/json'
```

```rust
curl --location 'https://api.longcat.chat/anthropic/v1/models' \
--header 'Authorization: Bearer YOUR_API_KEY' \
--header 'Content-Type: application/json'
```

返回示例:

```css
{
    "object": "list",
    "data": [
        {
            "id": "LongCat-2.0-Preview",
            "object": "model",
            "owned_by": "LongCat"
        }
    ]
}
```

#### [GET /v1/models/{model}](https://longcat.chat/platform/docs/zh/APIDocs.html#get-v1-models-model)

支持openai和anthropic两个端点下获取 LongCat 模型详情，包含模态，价格等信息

| 接口 | 说明 |
|------------------------------|--------------------|
| /openai/v1/models/{model} | openai端点下获取模型详情 |
| /anthropic/v1/models/{model} | anthropic端点下获取模型详情 |

**请求头**

-   `Authorization: Bearer YOUR_API_KEY`（必填）
-   `Content-Type: application/json`

示例：

```rust
curl --location 'https://api.longcat.chat/openai/v1/models/LongCat-2.0-Preview' \
--header 'Authorization: Bearer YOUR_API_KEY' \
--header 'Content-Type: application/json'
```

返回示例:

```json
{
  "id": "LongCat-2.0-Preview",
  "name": "LongCat-2.0-Preview",
  "created": 1773331200,
  "context_length": 1048576,
  "architecture": {
    "input_modalities": [
      "text"
    ],
    "output_modalities": [
      "text"
    ],
    "modality": "text->text",
    "tokenizer": "Other",
    "instruct_type": null
  },
  "supported_parameters": [
    "max_tokens",
    "temperature",
    "top_p",
    "stream",
    "tools",
    "tool_choice"
  ],
  "pricing": {
    "prompt": "0",
    "completion": "0"
  }
}
```

## [错误响应](https://longcat.chat/platform/docs/zh/APIDocs.html#%E9%94%99%E8%AF%AF%E5%93%8D%E5%BA%94)

API使用常规HTTP响应码指示成功或失败：

### [HTTP状态码](https://longcat.chat/platform/docs/zh/APIDocs.html#http%E7%8A%B6%E6%80%81%E7%A0%81)

| 状态码 | 状态名称 | 说明 |
|-----|-----------------------|-----------------|
| `200` | OK | 请求成功 |
| `400` | Bad Request | 请求参数无效或JSON格式错误 |
| `401` | Unauthorized | API密钥无效或缺失 |
| `403` | Forbidden | API密钥无权限访问请求资源 |
| `429` | Too Many Requests | 超出速率限制 |
| `500` | Internal Server Error | 服务器遇到意外情况 |
| `502` | Bad Gateway | 上游服务器响应无效 |
| `503` | Service Unavailable | 服务器暂时不可用 |

### [错误响应格式](https://longcat.chat/platform/docs/zh/APIDocs.html#%E9%94%99%E8%AF%AF%E5%93%8D%E5%BA%94%E6%A0%BC%E5%BC%8F)

所有错误返回如下结构的JSON对象：

```json
{
  "error": {
    "message": "人类可读的错误描述",
    "type": "error_type_identifier",
    "code": "specific_error_code"
  }
}
```

### [错误类型与代码](https://longcat.chat/platform/docs/zh/APIDocs.html#%E9%94%99%E8%AF%AF%E7%B1%BB%E5%9E%8B%E4%B8%8E%E4%BB%A3%E7%A0%81)

| 错误类型 | 错误代码 | HTTP状态 | 说明 |
|----------------------|--------------------|--------|------------|
| `authentication_error` | `invalid_api_key` | 401 | 提供的API密钥无效 |
| `permission_error` | `insufficient_quota` | 403 | API密钥配额不足 |
| `invalid_request_error` | `invalid_parameter` | 400 | 参数值无效 |
| `invalid_request_error` | `invalid_json` | 400 | JSON格式无效 |
| `rate_limit_error` | `rate_limit_exceeded` | 429 | 短时间内请求过多 |
| `server_error` | `internal_error` | 500 | 服务器内部错误 |

### [错误响应示例](https://longcat.chat/platform/docs/zh/APIDocs.html#%E9%94%99%E8%AF%AF%E5%93%8D%E5%BA%94%E7%A4%BA%E4%BE%8B)

**API密钥无效**

```json
{
  "error": {
    "message": "Invalid API key provided",
    "type": "authentication_error",
    "code": "invalid_api_key"
  }
}
```

**超出速率限制**

```json
{
  "error": {
    "message": "Rate limit exceeded. Please try again in 60 seconds",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}
```

## [速率限制](https://longcat.chat/platform/docs/zh/APIDocs.html#%E9%80%9F%E7%8E%87%E9%99%90%E5%88%B6)

速率限制按API密钥执行。超出限制时会收到429状态码。

## [SDK兼容性](https://longcat.chat/platform/docs/zh/APIDocs.html#sdk%E5%85%BC%E5%AE%B9%E6%80%A7)

本API设计兼容：

-   OpenAI Python SDK（用于`/openai/`端点）
-   Anthropic Python SDK（用于`/anthropic/`端点）
-   任何支持相应API格式的HTTP客户端

## [示例](https://longcat.chat/platform/docs/zh/APIDocs.html#%E7%A4%BA%E4%BE%8B)

### [使用OpenAI Python SDK](https://longcat.chat/platform/docs/zh/APIDocs.html#%E4%BD%BF%E7%94%A8openai-python-sdk)

```makefile
import openai

# 配置LongCat API
openai.api_base = "https://api.longcat.chat/openai"
openai.api_key = "your-api-key"

response = openai.ChatCompletion.create(
    model="LongCat-2.0-Preview",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)
```

### [使用Anthropic Python SDK](https://longcat.chat/platform/docs/zh/APIDocs.html#%E4%BD%BF%E7%94%A8anthropic-python-sdk)

```makefile
import anthropic

# 配置LongCat API
client = anthropic.Anthropic(
    api_key="Bearer your-api-key",
    base_url="https://api.longcat.chat"
)
default_headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer your-api-key",
    }


message = client.messages.create(
    model="LongCat-2.0-Preview",
    max_tokens=150,
    messages=[
        {"role": "user", "content": "Hello, LongCat!"}
    ]
)
```

### [使用cURL](https://longcat.chat/platform/docs/zh/APIDocs.html#%E4%BD%BF%E7%94%A8curl)

```cpp
# OpenAI风格请求
curl -X POST https://api.longcat.chat/openai/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "LongCat-2.0-Preview",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'

# Anthropic风格请求
curl -X POST https://api.longcat.chat/anthropic/v1/messages \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "LongCat-2.0-Preview",
    "max_tokens": 1000,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

___

> 📋 **需要帮助？** 请查阅我们的[常见问题](https://longcat.chat/platform/docs/zh/FAQ.html)获取常见问题和故障排查指南。
