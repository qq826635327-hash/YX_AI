"""ComfyUI 工作流映射配置路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.schemas.common import ok
from app.schemas.generation import WorkflowCreate, WorkflowUpdate
from app.services.config_service import (
    create_workflow,
    delete_workflow,
    get_workflow,
    list_workflows,
    update_workflow,
)

router = APIRouter(prefix="/config/workflows", tags=["config"])


@router.get("")
async def api_list_workflows(
    asset_type: Optional[str] = Query(default=None),
    enabled: Optional[bool] = Query(default=None),
    session: Session = Depends(get_session),
):
    """工作流映射列表。"""
    items = list_workflows(session, asset_type=asset_type, enabled=enabled)
    return ok(serialize_models(items))


@router.post("")
async def api_create_workflow(
    payload: WorkflowCreate,
    session: Session = Depends(get_session),
):
    workflow = create_workflow(session, payload)
    return ok(serialize_model(workflow), message="工作流映射已创建")


@router.get("/{workflow_id}")
async def api_get_workflow(workflow_id: str, session: Session = Depends(get_session)):
    workflow = get_workflow(session, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "工作流不存在"})
    return ok(serialize_model(workflow))


@router.patch("/{workflow_id}")
async def api_update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    session: Session = Depends(get_session),
):
    workflow = update_workflow(session, workflow_id, payload)
    if not workflow:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "工作流不存在"})
    return ok(serialize_model(workflow), message="工作流已更新")


@router.delete("/{workflow_id}")
async def api_delete_workflow(workflow_id: str, session: Session = Depends(get_session)):
    success = delete_workflow(session, workflow_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "工作流不存在"})
    return ok(None, message="工作流已删除")
