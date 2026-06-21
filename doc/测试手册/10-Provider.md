# Provider 配置 API 测试用例

> 本文件包含 Provider 配置相关的所有 API 测试用例，对应原文 §3.11。

---

### 3.11 Provider 配置 API

| 编号 | 名称 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|------|------|----------|------|----------|--------|
| TC-API-PROV-001 | 创建 Provider | 无 | POST {"name": "测试Provider", ...} | 200 | P0 |
| TC-API-PROV-002 | 缺少名称 | 无 | POST 缺少 name | 422 | P0 |
| TC-API-PROV-003 | 无效 provider_kind | 无 | POST {"provider_kind": "invalid"} | 422 | P1 |
| TC-API-PROV-004 | 加密 API Key | 创建时提供 api_key | POST 含 api_key | 200, key 加密存储 | P0 |
| TC-API-PROV-010 | 获取 Provider 列表 | 有 Provider | GET /api/config/providers | 200 | P0 |
| TC-API-PROV-011 | 列表不泄露 API Key | 有 Provider | GET /api/config/providers | 响应中 api_key 被遮掩 | P0 |
| TC-API-PROV-020 | 获取 Provider 详情 | Provider 存在 | GET /api/config/providers/{id} | 200 | P0 |
| TC-API-PROV-021 | Provider 不存在 | 无 | GET /api/config/providers/99999 | 404 | P0 |
| TC-API-PROV-030 | 更新 Provider | Provider 存在 | PATCH {"name": "新名称"} | 200 | P0 |
| TC-API-PROV-031 | 更新-不存在 | 无 | PATCH /api/config/providers/99999 | 404 | P0 |
| TC-API-PROV-040 | 删除 Provider | Provider 存在 | DELETE /api/config/providers/{id} | 200/204 | P0 |
| TC-API-PROV-041 | 删除-不存在 | 无 | DELETE /api/config/providers/99999 | 404 | P0 |
| TC-API-PROV-042 | 删除被引用的 Provider | Provider 被工作流引用 | DELETE | 409 或级联处理 | P1 |
| TC-API-PROV-050 | 测试 Provider 连接 | Provider 已配置 | POST /api/config/providers/{id}/test | 200, 返回测试结果 | P0 |
| TC-API-PROV-051 | 测试-连接失败 | API Key 无效 | POST /test | 200/400, 返回失败信息 | P1 |
| TC-API-PROV-060 | 获取 Provider 能力 | Provider 存在 | GET /api/config/providers/{id}/capabilities | 200 | P0 |
| TC-API-PROV-061 | 获取 ComfyUI 能力 | ComfyUI 已配置 | GET /api/config/providers/comfyui/capabilities | 200 | P1 |

```python
class TestProviderAPI:
    """Provider 配置 API 测试集"""

    @pytest.mark.asyncio
    async def test_tc_api_prov_001_create(
        self, client: AsyncClient
    ):
        """TC-API-PROV-001: 创建 Provider"""
        response = await client.post("/api/config/providers", json={
            "name": "测试OpenAI",
            "provider_kind": "openai",
            "base_url": "https://api.openai.com/v1",
            "encrypted_api_key": "sk-test-xxx",
            "model": "dall-e-3"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "测试OpenAI"
        assert data["provider_kind"] == "openai"

    @pytest.mark.asyncio
    async def test_tc_api_prov_011_key_masked(
        self, client: AsyncClient, provider
    ):
        """TC-API-PROV-011: 列表不泄露API Key"""
        response = await client.get("/api/config/providers")
        assert response.status_code == 200
        for prov in response.json():
            if "encrypted_api_key" in prov:
                assert "sk-test-xxx" not in str(prov["encrypted_api_key"])
```
