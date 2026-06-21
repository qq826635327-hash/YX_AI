"""配置中心服务：Provider 与工作流映射管理。"""

from __future__ import annotations

from typing import List, Optional

from sqlmodel import Session, select

from app.core.config import decrypt_secret, encrypt_secret, mask_secret
from app.models import ApiProvider, ProviderModel, WorkflowMapping
from app.schemas.generation import ProviderCreate, ProviderUpdate, WorkflowCreate, WorkflowUpdate


# ============================================================
# Provider
# ============================================================

def list_providers(session: Session, enabled: Optional[bool] = None) -> List[ApiProvider]:
    from sqlalchemy.orm import selectinload

    stmt = select(ApiProvider).options(selectinload(ApiProvider.models))
    if enabled is not None:
        stmt = stmt.where(ApiProvider.enabled == enabled)
    stmt = stmt.order_by(ApiProvider.created_at.desc())
    return list(session.exec(stmt).all())


def get_provider(session: Session, provider_id: str) -> Optional[ApiProvider]:
    from sqlalchemy.orm import selectinload

    stmt = select(ApiProvider).where(ApiProvider.id == provider_id).options(selectinload(ApiProvider.models))
    return session.exec(stmt).first()


def get_provider_decrypted_key(session: Session, provider_id: str) -> Optional[str]:
    """获取解密后的 API Key（仅内部使用）。"""
    provider = get_provider(session, provider_id)
    if not provider:
        return None
    return decrypt_secret(provider.api_key_encrypted)


def create_provider(session: Session, payload: ProviderCreate) -> ApiProvider:
    provider = ApiProvider(
        name=payload.name,
        provider_kind=payload.provider_kind,
        base_url=payload.base_url,
        api_key_encrypted=encrypt_secret(payload.api_key) if payload.api_key else "",
        model=payload.model,
        timeout_seconds=payload.timeout_seconds,
        enabled=payload.enabled,
        is_default=payload.is_default,
        description=payload.description,
    )

    # 如果设为默认，取消其他默认（不提前 commit，与创建操作在同一事务）
    if payload.is_default:
        _clear_other_defaults(session, auto_commit=False)

    session.add(provider)
    session.flush()  # 先拿到 provider.id

    # 写入多模型配置（优先使用 models，models 为空时回退到单 model）
    _sync_provider_models(session, provider, payload.models, fallback_model=payload.model)

    session.commit()
    session.refresh(provider)
    return provider


def update_provider(session: Session, provider_id: str, payload: ProviderUpdate) -> Optional[ApiProvider]:
    provider = get_provider(session, provider_id)
    if not provider:
        return None

    data = payload.model_dump(exclude_unset=True)
    # api_key 特殊处理：留空表示不修改
    if "api_key" in data:
        if data["api_key"]:
            provider.api_key_encrypted = encrypt_secret(data["api_key"])
        del data["api_key"]

    # models 单独处理，不能直接用 setattr
    models_payload = data.pop("models", None)

    if data.get("is_default"):
        _clear_other_defaults(session, exclude_id=provider_id)

    for key, value in data.items():
        setattr(provider, key, value)

    # 同步多模型配置
    if models_payload is not None:
        _sync_provider_models(session, provider, models_payload, fallback_model=data.get("model", provider.model))

    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


def delete_provider(session: Session, provider_id: str) -> bool:
    provider = session.get(ApiProvider, provider_id)
    if not provider:
        return False
    session.delete(provider)
    session.commit()
    return True


def _clear_other_defaults(session: Session, exclude_id: Optional[str] = None, auto_commit: bool = True) -> None:
    """清除其他 Provider 的 is_default 标记。

    Args:
        auto_commit: 是否自动提交。False 时由调用方统一 commit，保证事务原子性。
    """
    stmt = select(ApiProvider).where(ApiProvider.is_default == True)  # noqa: E712
    for p in session.exec(stmt).all():
        if p.id != exclude_id:
            p.is_default = False
            session.add(p)
    if auto_commit:
        session.commit()


def _sync_provider_models(
    session: Session,
    provider: ApiProvider,
    models_payload: Optional[list[dict]],
    fallback_model: Optional[str] = None,
) -> None:
    """同步 Provider 的模型列表：删除旧模型，按 payload 创建新模型。"""
    if not models_payload and fallback_model:
        models_payload = [{"model_name": fallback_model, "tags": _infer_model_tags(fallback_model), "sort_order": 0}]

    if not models_payload:
        return

    # 删除旧模型
    for old in list(provider.models or []):
        session.delete(old)

    # 创建新模型
    for idx, item in enumerate(models_payload):
        if not item.get("model_name"):
            continue
        pm = ProviderModel(
            provider_id=provider.id,
            model_name=item["model_name"].strip(),
            tags=item.get("tags", []) or _infer_model_tags(item["model_name"]),
            sort_order=item.get("sort_order", idx),
        )
        session.add(pm)


def _infer_model_tags(model_name: str) -> list[str]:
    """根据模型名猜测默认能力标签（仅用于旧数据迁移或 fallback）。"""
    name = model_name.lower()
    tags = []
    if "video" in name:
        tags.append("video_generation")
    if "img" in name or "image" in name or "flux" in name or "sd" in name or "dall" in name:
        tags.append("image_generation")
    if "gpt" in name or "claude" in name or "llm" in name or "reason" in name:
        tags.append("text_reasoning")
    return tags


def provider_to_view(provider: ApiProvider) -> dict:
    """转成脱敏视图字典。"""
    from app.core.serialization import serialize_model

    data = serialize_model(provider)
    # 解密并脱敏展示
    plain = decrypt_secret(provider.api_key_encrypted) if provider.api_key_encrypted else ""
    data["api_key_masked"] = mask_secret(plain)
    # 移除原始敏感字段，避免意外泄露
    data.pop("api_key_encrypted", None)

    # 组装多模型视图
    data["models"] = [
        {
            "id": m.id,
            "model_name": m.model_name,
            "tags": m.tags or [],
            "sort_order": m.sort_order,
        }
        for m in sorted(provider.models or [], key=lambda x: x.sort_order)
    ]
    return data


# ============================================================
# 工作流映射
# ============================================================

def list_workflows(
    session: Session,
    asset_type: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> List[WorkflowMapping]:
    stmt = select(WorkflowMapping)
    if asset_type:
        stmt = stmt.where(WorkflowMapping.asset_type == asset_type)
    if enabled is not None:
        stmt = stmt.where(WorkflowMapping.enabled == enabled)
    stmt = stmt.order_by(WorkflowMapping.created_at.desc())
    return list(session.exec(stmt).all())


def get_workflow(session: Session, workflow_id: str) -> Optional[WorkflowMapping]:
    return session.get(WorkflowMapping, workflow_id)


def create_workflow(session: Session, payload: WorkflowCreate) -> WorkflowMapping:
    if payload.is_default:
        _clear_other_default_workflows(session, payload.asset_type, auto_commit=False)

    workflow = WorkflowMapping(
        name=payload.name,
        asset_type=payload.asset_type,
        description=payload.description,
        workflow_json=payload.workflow_json,
        input_mapping=payload.input_mapping,
        output_mapping=payload.output_mapping,
        provider_type=payload.provider_type,
        provider_id=payload.provider_id,
        is_default=payload.is_default,
        enabled=payload.enabled,
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


def update_workflow(session: Session, workflow_id: str, payload: WorkflowUpdate) -> Optional[WorkflowMapping]:
    workflow = session.get(WorkflowMapping, workflow_id)
    if not workflow:
        return None

    data = payload.model_dump(exclude_unset=True)
    if data.get("is_default"):
        _clear_other_default_workflows(session, workflow.asset_type, exclude_id=workflow_id)

    for key, value in data.items():
        setattr(workflow, key, value)

    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


def delete_workflow(session: Session, workflow_id: str) -> bool:
    workflow = session.get(WorkflowMapping, workflow_id)
    if not workflow:
        return False
    session.delete(workflow)
    session.commit()
    return True


def _clear_other_default_workflows(
    session: Session,
    asset_type: str,
    exclude_id: Optional[str] = None,
    auto_commit: bool = True,
) -> None:
    """清除同类型其他 Workflow 的 is_default 标记。

    Args:
        auto_commit: 是否自动提交。False 时由调用方统一 commit。
    """
    stmt = select(WorkflowMapping).where(
        WorkflowMapping.asset_type == asset_type,
        WorkflowMapping.is_default == True,  # noqa: E712
    )
    for w in session.exec(stmt).all():
        if w.id != exclude_id:
            w.is_default = False
            session.add(w)
    if auto_commit:
        session.commit()
