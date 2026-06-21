"""素材资源 API 路由。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.models import Project
from app.schemas.common import err, ok
from app.services.asset_service import (
    create_asset_record,
    delete_asset,
    get_asset,
    get_asset_file_path,
    list_assets,
    save_uploaded_file,
)

# 上传文件大小限制：200MB
MAX_UPLOAD_SIZE = 200 * 1024 * 1024

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
async def api_list_assets(
    project_id: str = Query(..., description="项目 ID"),
    category: Optional[str] = None,
    asset_type: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """素材列表。可按 category / asset_type / target_type+target_id 过滤。"""
    items = list_assets(
        session, project_id,
        category=category, asset_type=asset_type,
        target_type=target_type, target_id=target_id,
    )
    return ok(serialize_models(items))


@router.post("/sync")
async def api_sync_assets(
    project_id: str = Query(..., description="项目 ID"),
    session: Session = Depends(get_session),
):
    """同步清理：删除磁盘文件已丢失的素材 DB 记录。"""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "项目不存在"})

    from app.services.asset_service import sync_assets as do_sync

    result = do_sync(session, project_id)
    msg = f"同步完成：检查 {result['checked']} 条，清理 {result['cleaned']} 条"
    if result["errors"]:
        msg += f"，{result['errors']} 条处理出错"
    return ok(result, message=msg)


@router.post("/projects/{project_id}/upload")
async def api_upload_new_asset(
    project_id: str,
    category: str = Query(...),
    file: UploadFile = File(...),
    target_type: Optional[str] = Query(default=None),
    target_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    """上传全新素材到项目。"""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "项目不存在"})

    # 读取文件内容，限制大小
    content = await file.read(MAX_UPLOAD_SIZE)
    if len(content) >= MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail={"error": "file_too_large", "message": f"文件超过 {MAX_UPLOAD_SIZE // (1024*1024)}MB 限制"})

    rel_path = save_uploaded_file(
        Path(project.root_path),
        category,
        file.filename or "upload.bin",
        content,
        target_type=target_type,
        target_id=target_id,
        session=session,
    )

    # 判断类型
    ext = (file.filename or "").lower().rsplit(".", 1)[-1] if file.filename else ""
    asset_type = "video" if ext in ("mp4", "webm", "mov", "mkv") else "image"

    asset = create_asset_record(
        session,
        project_id=project_id,
        asset_type=asset_type,
        category=category,
        file_path=rel_path,
        file_size=len(content),
        mime_type=file.content_type,
        status="ready",
        target_type=target_type,
        target_id=target_id,
    )

    return ok(serialize_model(asset), message="素材已上传")


@router.get("/{asset_id}")
async def api_get_asset(asset_id: str, session: Session = Depends(get_session)):
    """获取素材元数据。"""
    asset = get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "素材不存在"})
    return ok(serialize_model(asset))


@router.get("/{asset_id}/file")
async def api_get_asset_file(asset_id: str, session: Session = Depends(get_session)):
    """下载/预览素材文件。"""
    result = get_asset_file_path(session, asset_id)
    if not result:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "素材不存在"})
    full_path, asset = result
    if not full_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file_missing", "message": "素材文件丢失"})
    return FileResponse(
        path=str(full_path),
        media_type=asset.mime_type or "application/octet-stream",
        filename=asset.file_name,
    )


@router.post("/{asset_id}/upload")
async def api_upload_asset(
    asset_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """上传替换素材文件。

    注意：此接口用于替换已有素材记录的文件内容。
    全新上传建议通过 create 接口。
    """
    asset = get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "素材记录不存在"})

    project = session.get(Project, asset.project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "项目不存在"})

    content = await file.read(MAX_UPLOAD_SIZE)
    if len(content) >= MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail={"error": "file_too_large", "message": f"文件超过 {MAX_UPLOAD_SIZE // (1024*1024)}MB 限制"})

    rel_path = save_uploaded_file(
        Path(project.root_path),
        asset.category,
        file.filename or "upload.bin",
        content,
    )

    # 更新素材记录
    asset.file_path = rel_path
    asset.file_name = file.filename or "upload.bin"
    asset.file_size = len(content)
    asset.status = "ready"
    session.add(asset)
    session.commit()
    session.refresh(asset)

    return ok(serialize_model(asset), message="素材已上传")


@router.delete("/{asset_id}")
async def api_delete_asset(
    asset_id: str,
    delete_file: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    """删除素材记录。"""
    success = delete_asset(session, asset_id, delete_file=delete_file)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "素材不存在"})
    return ok(None, message="素材已删除")
