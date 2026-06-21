"""剧本 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.schemas.common import err, ok
from app.schemas.script import ScriptParseRequest, ScriptUpdate, ScriptView
from app.services.script_service import (
    get_script,
    mark_parsing,
    update_script,
)

router = APIRouter(prefix="/projects/{project_id}/script", tags=["script"])


def _to_view(doc) -> dict:
    """把 ScriptDocument 序列化为 ScriptView dict。"""
    return ScriptView(
        id=doc.id,
        project_id=doc.project_id,
        raw_text=doc.raw_text,
        version=doc.version,
        parse_status=doc.parse_status,
        parse_error=doc.parse_error,
        parsed_at=doc.parsed_at,
        parsed_result=doc.parsed_result,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
    ).model_dump()


@router.get("")
async def api_get_script(project_id: str, session: Session = Depends(get_session)):
    """获取剧本。"""
    doc = get_script(session, project_id)
    if not doc:
        return ok({"raw_text": "", "version": 0, "parse_status": "none", "parsed_result": None})
    return ok(_to_view(doc))


@router.put("")
async def api_update_script(
    project_id: str,
    payload: ScriptUpdate,
    session: Session = Depends(get_session),
):
    """更新剧本文本。"""
    doc = update_script(session, project_id, payload)
    return ok(_to_view(doc), message="剧本已保存")


@router.post("/parse")
async def api_parse_script(
    project_id: str,
    payload: ScriptParseRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """触发 AI 解析。

    MVP 阶段：标记为 parsing，启动后台解析任务。
    实际 LLM 调用与管线在 pipelines/ 模块实现（Phase 2）。
    """
    doc = get_script(session, project_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "请先保存剧本"})

    if doc.parse_status == "parsing" and not payload.force:
        return err("剧本正在解析中，请稍候", error="already_parsing")

    mark_parsing(session, doc.id)

    # 后台启动解析任务（Phase 2 实现 LLM 调用，Phase 1 用占位）
    from app.pipelines.script_parser import parse_script_async

    background_tasks.add_task(parse_script_async, doc.id, project_id)

    return ok({"script_id": doc.id, "status": "parsing"}, message="解析已启动")
