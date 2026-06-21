# 10. API 供应商与模型配置

**路由**：`/settings/api` + `/settings/models`
**对应文件**：`pages/settings/SettingsApiPage.tsx` + `SettingsModelsPage.tsx`

---

## 1. 功能描述

管理所有可用的 API 供应商（AI 服务提供方）及其模型。如 Agnes、SenseNova、OpenAI 等。

## 2. API 供应商

### 2.1 供应商列表

| 列 | 内容 |
|----|------|
| 名称 | 唯一标识 |
| 类型 | openai / fal / replicate / agnes / 自定义 |
| API 地址 | base_url |
| 状态 | 启用/禁用 |
| 模型 | 默认模型 |

每行操作：编辑、删除、连接测试

### 2.2 新建/编辑供应商对话框

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 名称 | text | ✅ | 唯一 |
| 类型 | select | ✅ | openai / fal / replicate / agnes / 自定义 |
| API 地址 | text | ✅ | base_url |
| API Key | password | ✅ | 密文保存，前端展示时脱敏前 4 位 + 后 4 位 |
| 模型 | text | ❌ | 默认使用的模型名称 |
| 超时时间 | number | ❌ | timeout_seconds，默认值由系统决定 |
| 默认供应商 | bool | ❌ | is_default，设为默认供应商 |
| 描述 | textarea | ❌ | - |

### 2.3 安全性

**API Key 加密**：
- Fernet 对称加密存储在数据库
- 加密密钥来自 `config.yaml` 的 `encryption_key`
- 生产环境必须用 `ADS_ENCRYPTION_KEY` 环境变量覆盖
- 前端从不接收明文 API Key

**脱敏显示**：`abcd********wxyz`（前 4 + 后 4，中间 8 个星号）

### 2.4 连接测试

- 点击"测试连接"按钮
- 后端调用 provider 的 health_check 接口
- 显示延迟、版本、能力验证结果

**当前状态**：Phase 1 占位实现，不会真正调用 provider

### 2.5 供应商 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config/providers` | 供应商列表 |
| POST | `/api/config/providers` | 新建 |
| GET | `/api/config/providers/{id}` | 详情 |
| PATCH | `/api/config/providers/{id}` | 更新（API Key 留空表示不修改） |
| DELETE | `/api/config/providers/{id}` | 删除（带确认） |
| POST | `/api/config/providers/{id}/test` | 连接测试 |

### 2.6 供应商数据模型（ApiProvider）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | UUID |
| name | str | 唯一名称 |
| provider_kind | str | openai / fal / replicate / agnes / custom |
| base_url | str | API 地址 |
| api_key | str | 加密存储的 API Key |
| model | str | 默认模型名称 |
| timeout_seconds | int | 超时时间（秒） |
| is_default | bool | 是否默认供应商 |
| description | str | 描述 |
| enabled | bool | 启用/禁用 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3. 模型配置

> ⚠️ **[Phase 3 占位 · 当前无实际功能]** 模型数据结构待设计，UI 为占位页面。

### 3.1 模型列表

按 Provider 分组显示：模型名 / 类型（图/视频）/ 版本 / 能力标签 / 启用/禁用开关

### 3.2 模型分类

| 类型 | 说明 | 例子 |
|------|------|------|
| 文生图 | 主要 | flux / sdxl / midjourney |
| 图生图 | 风格迁移 | - |
| 文生视频 | 主要 | kling / sora / runway |
| 图生视频 | 首帧驱动 | - |

### 3.3 模型数据模型（计划）

```python
class Model:
    id: str
    provider_id: str
    name: str           # 内部唯一名
    display_name: str   # 显示名
    model_type: str     # image / video
    capabilities: dict  # ModelCapabilities
    default_params: dict
    enabled: bool
```

### 3.4 未来规划

- **模型自动发现**：从 Provider API 拉取可用模型列表，自动识别类型和能力
- **模型参数预设**：温度（LLM）/ 步数、guidance scale（图）/ 视频时长、帧率 / 质量档位
- **一键测试**：发送简单 prompt 测试，显示响应时间和效果

## 4. Phase 状态

- **供应商管理**：Phase 1 已有完整 CRUD UI，连接测试为占位
- **模型配置**：Phase 1 占位页面，Phase 3 接入真实 Provider 时动态加载

## 5. 已知限制

- 供应商连接测试为占位实现
- 模型配置 UI 为占位
- 模型数据结构和 UI 待 Phase 3 完善

---

## AI 开发检查清单

> AI 修改本模块功能时，必须逐项检查以下内容。

### 前置检查
- [ ] 已阅读 `doc/开发手册/08-常见Bug与注意事项.md`
- [ ] 已阅读 `doc/开发手册/CHANGELOG.md` 最近 3 条
- [ ] 已理解本模块的数据模型和 API 路由

### 修改后验证
- [ ] 后端：修改的文件 Python 语法检查通过
- [ ] 后端：`pytest tests/ -v --tb=short -x` 全部通过
- [ ] 后端：`/api/health` 返回 200
- [ ] 前端：`npx tsc --noEmit` 无类型错误
- [ ] 日志：`GET /api/logs?level=ERROR&limit=5` 无新错误

### 业务规则验证
- [ ] API Key 加密存储（数据库中非明文）
- [ ] 前端展示脱敏（前4+后4+中间星号）
- [ ] Provider 类型与 Handler 注册表匹配
- [ ] 默认 Provider 标记正确

### 文档同步
- [ ] `doc/开发手册/CHANGELOG.md` 已更新
- [ ] 本文件已更新（如产品行为有变化）
- [ ] `doc/产品手册/A-完整路由表.md` 已更新（如 API 有变化）

---

## 6. 相关模块

- [ComfyUI](./14-ComfyUI.md)
- [插件扩展](./11-插件扩展.md)
- [提示词模版](./13-提示词模版.md)
