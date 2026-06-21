"""项目 API 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.schemas.common import err, ok, paginate
from app.schemas.project import ProjectCreate, ProjectDetail, ProjectSummary, ProjectUpdate
from app.services.project_service import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def api_list_projects(
    status: Optional[str] = Query(default=None, pattern="^(active|archived)$"),
    keyword: Optional[str] = Query(default=None, description="名称关键词"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """项目列表。"""
    items, total = list_projects(session, status=status, keyword=keyword, page=page, page_size=page_size)
    summaries = [ProjectSummary.model_validate(serialize_model(p)).model_dump() for p in items]
    return paginate(summaries, total, page, page_size)


@router.post("")
async def api_create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
):
    """新建项目。"""
    try:
        project = create_project(session, payload)
        detail = ProjectDetail.model_validate(serialize_model(project))
        return ok(detail.model_dump(), message="项目创建成功")
    except Exception as e:
        return err(f"创建项目失败: {e}", error="create_failed")


@router.get("/{project_id}")
async def api_get_project(
    project_id: str,
    session: Session = Depends(get_session),
):
    """项目详情。"""
    project = get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "项目不存在"})
    detail = ProjectDetail.model_validate(serialize_model(project))
    return ok(detail.model_dump())


@router.patch("/{project_id}")
async def api_update_project(
    project_id: str,
    payload: ProjectUpdate,
    session: Session = Depends(get_session),
):
    """更新项目。"""
    project = update_project(session, project_id, payload)
    if not project:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "项目不存在"})
    detail = ProjectDetail.model_validate(serialize_model(project))
    return ok(detail.model_dump(), message="项目已更新")


@router.delete("/{project_id}")
async def api_delete_project(
    project_id: str,
    delete_files: bool = Query(default=False, description="是否同时删除项目目录文件"),
    session: Session = Depends(get_session),
):
    """删除项目。"""
    success = delete_project(session, project_id, delete_files=delete_files)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "项目不存在"})
    return ok(None, message="项目已删除")
