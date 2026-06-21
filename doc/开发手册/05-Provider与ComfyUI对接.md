# 05 · Provider 与 ComfyUI 对接

> 新增 AI Provider 怎么做？ComfyUI 怎么接？

## 1. Provider 抽象（`providers/base.py`）

所有 AI Provider 都继承 `ProviderHandler`，采用 **translate/parse 模式**：

```python
class ProviderHandler(ABC):
    # 子类必须覆盖的类属性
    PROVIDER_KIND: str = ""              # provider_kind 标识符
    SUPPORTED_MODELS: dict = {}          # { model_name: { "param_specs": [...], "capabilities": ModelCapabilities | dict } }

    @classmethod
    def get_capabilities(cls, model: str | None = None) -> dict:
        """返回前端需要的能力声明（含动态参数定义）。"""

    def validate_params(self, model: str, params: dict) -> list[str]:
        """参数校验；返回错误列表（空 = 通过）。"""

    def translate(self, request: StandardGenerateRequest) -> tuple[str, dict, dict]:
        """将标准请求转为厂商 API 的 HTTP 请求三要素。
        Returns: (url, payload, headers)
        """

    def parse(self, response_body: dict, status_code: int) -> StandardGenerateResult:
        """将厂商 API 响应转为标准结果。"""

    async def generate_image(
        self, model: str, prompt: str, params: dict,
        api_key: str | None = None, base_url: str | None = None, timeout: int = 120,
    ) -> list[str]:
        """基类通用实现：translate → httpx → parse → result。
        子类一般不需要覆盖此方法，只需实现 translate/parse。
        只有特殊协议（如 WebSocket/流式）才需要覆盖。
        """
```

### 标准化模型（`schemas/provider_types.py`）

```python
class StandardGenerateRequest(BaseModel):
    model: str
    prompt: str
    negative_prompt: str | None = None
    size: str | None = None
    reference_images: list[str] = []     # Data URI Base64
    count: int = 1
    extra: dict = {}                     # 厂商特有参数扩展口

class StandardGenerateResult(BaseModel):
    success: bool
    image_urls: list[str] = []
    video_urls: list[str] = []
    raw_request: dict = {}               # 实际发给厂商的 payload（调试用）
    raw_response: dict = {}              # 厂商原始响应（调试用）
    provider_kind: str = ""
    model: str = ""
    usage: dict = {}
    error: str | None = None
    duration_ms: int | None = None

class ModelCapabilities(BaseModel):
    image_generation: bool = True
    image_to_image: bool = False
    video_generation: bool = False
    batch_support: bool = False
    max_count: int = 1
    max_reference_images: int = 0
    supports_negative_prompt: bool = False
    custom_size_range: tuple[int, int] = (256, 2048)
```

## 2. 注册 Provider

### 添加 Provider 实现

1. **新建文件**：`backend/app/providers/my_handler.py`

```python
from app.providers.base import ProviderHandler
from app.providers.registry import register
from app.schemas.provider_types import (
    ModelCapabilities,
    StandardGenerateRequest,
    StandardGenerateResult,
)

@register
class MyHandler(ProviderHandler):
    PROVIDER_KIND = "my_kind"

    SUPPORTED_MODELS = {
        "my-model-v1": {
            "param_specs": [
                {"key": "size", "label": "尺寸", "required": True,
                 "input_type": "select",
                 "options": ["1024x1024", "2048x2048"], "default": "1024x1024"},
                {"key": "seed", "label": "随机种子", "input_type": "number", "default": -1},
            ],
            "capabilities": ModelCapabilities(
                image_generation=True,
                image_to_image=True,
                max_reference_images=3,
            ),
        },
    }

    def __init__(self, api_key: str, base_url: str | None = None, timeout: int = 120):
        self._api_key = api_key
        self._base_url = (base_url or "https://api.example.com").rstrip("/")
        self._timeout = timeout

    def translate(self, request: StandardGenerateRequest) -> tuple[str, dict, dict]:
        """将标准请求转为厂商 API 的 url/payload/headers。"""
        url = f"{self._base_url}/v1/images/generations"
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "size": request.size,
            "n": request.count,
        }
        if request.reference_images:
            payload["ref_images"] = request.reference_images
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        return url, payload, headers

    def parse(self, response_body: dict, status_code: int) -> StandardGenerateResult:
        """将厂商 API 响应转为标准结果。"""
        if status_code != 200:
            error_msg = response_body.get("error", {}).get("message", "")
            return StandardGenerateResult(success=False, error=error_msg)
        urls = [item["url"] for item in response_body.get("data", [])]
        return StandardGenerateResult(success=True, image_urls=urls)
```

### 注册到注册表

2. **修改** `backend/app/providers/__init__.py`：

```python
# 自动导入所有 Handler（触发 @register 装饰器注册）
from app.providers.my_handler import MyHandler  # noqa: F401
```

> 注册机制：`registry.py` 维护 `_REGISTRY` 字典（`{provider_kind: HandlerClass}`）。
> `@register` 装饰器自动读取 Handler 的 `PROVIDER_KIND` 属性作为 key。
> 如需为已有 Handler 添加别名（如兼容旧数据），可用 `register_alias("old_kind", SomeHandler)`。

### 前端：Provider 类型枚举

3. **修改** `frontend/src/types/index.ts`：

```typescript
export type ProviderKind = "openai" | "fal" | "replicate" | "agnes" | "custom";
```

4. **修改** `frontend/src/pages/settings/SettingsApiPage.tsx`：新增 Provider Kind 选项。

## 3. 已实现的 Provider

| Kind | 文件 | 协议 | 状态 |
| --- | --- | --- | --- |
| `agnes` | `agnes_handler.py` | Agnes 原生（translate/parse 模式） | ✓ 已用 |
| `openai` | — | AgnesHandler 的别名（兼容旧数据） | ✓ 已用（别名） |
| `fal` | — | fal.ai | 枚举预留 |
| `replicate` | — | Replicate | 枚举预留 |
| `custom` | — | 自定义 | 枚举预留 |

> Agnes 实际是 SenseTime 的 AI 平台（API 兼容 OpenAI）。`doc/Agnes-API说明/` 有详细 API 文档。
> ComfyUI 不通过 Provider 实现，走 `WorkflowMapping` 路线（见下文）。

## 4. ComfyUI 对接

### 设计

ComfyUI 不是一个简单的 HTTP API，它的核心是"工作流图"。我们的设计：

- `ApiProvider` 表：管理 ComfyUI 服务端地址
- `WorkflowMapping` 表：管理工作流模板 + 输入输出映射
- `ProviderHandler` 当前**不直接支持 ComfyUI**——ComfyUI 走专门的执行路径

### 当前状态

- 模型：✓
- 数据：✓
- 前端：✓ (`SettingsComfyuiServersPage` + `SettingsComfyuiWorkflowsPage`)
- 任务执行器：⚠️ 占位

具体执行路径 TODO 写在 `tasks/execute_task.py` 的 `if asset_type_str == "video"` 分支附近。

## 5. Provider 能力查询

前端在用户点击"生成图片"时，需要根据 Provider 动态渲染参数表单。流程：

1. 前端：选择 Provider + 模型
2. 调用 `GET /api/config/providers/{provider_id}/capabilities`
3. 返回能力声明：`param_specs` 描述每个参数 + `ModelCapabilities` 描述模型能力
4. 前端用 `param_specs` 动态生成表单

详见 `frontend/src/components/GenerateDialog.tsx` 和 `api/generate.ts`。

## 6. 任务执行器（`tasks/execute_task.py`）

主流程：

```
1. status: pending → running (5%)
2. 分配 trace_id（contextvars 全链路追踪）
3. 读取任务上下文（project, target, payload）
4. 收集参考图（log_ref_collect 记录）
5. 调用 Handler.generate_image（translate → httpx → parse）
6. log_api_call 记录 API 调用（请求/响应/耗时/错误）
7. 下载图片到项目目录（log_download 记录）
8. 保存 prompt（可选）
9. 创建 Asset 记录 + 自动回填到实体
10. status: succeeded
```

每一步都：
- `write_task_log(...)` / `log_api_call(...)` / `log_ref_collect(...)` / `log_download(...)` 写结构化日志
- `update_task_status(...)` 推进度
- `push_task_progress(...)` 推 WS

**任何步骤失败都会**：
- `update_task_status(..., status="failed", error=...)`
- `write_task_log(..., "ERROR", ...)` 或 `log_api_call/log_download` 记录错误
- `push_task_failed(...)`

## 7. 加新 Provider 的清单

1. `backend/app/providers/<name>_handler.py`（继承 `ProviderHandler`，加 `@register` 装饰器）
2. 实现 `translate()` — 将 `StandardGenerateRequest` 转为厂商 API 的 url/payload/headers
3. 实现 `parse()` — 将厂商 API 响应转为 `StandardGenerateResult`
4. 声明 `SUPPORTED_MODELS`（含 `param_specs` + `ModelCapabilities`）
5. `backend/app/providers/__init__.py` 添加 import（触发 `@register` 自动注册）
6. `backend/app/models/provider.py` 的 `PROVIDER_KINDS` 加枚举
7. `frontend/src/types/index.ts` 的 `ProviderKind` 加类型
8. `frontend/src/pages/settings/SettingsApiPage.tsx` 加 UI 选项
9. 端到端测试：新建 Provider → 选模型 → 生成一张图
10. 同步 `doc/产品手册/10-API供应商与模型配置.md`
