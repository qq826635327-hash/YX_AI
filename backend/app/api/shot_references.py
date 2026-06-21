"""分镜关联引用 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Character, Prop, Scene, Shot
from app.schemas.common import ok
from app.schemas.generation import ShotReferenceAdd
from app.services import business_service
from app.services import shot_reference_service as ref_svc

router = APIRouter(tags=["shot_references"])


def _validate_entities_in_project(
    session: Session,
    project_id: str,
    character_ids: list[str] | None = None,
    scene_ids: list[str] | None = None,
    prop_ids: list[str] | None = None,
) -> None:
    """校验所有实体归属同一 project，防止跨项目关联。"""
    if character_ids:
        rows = session.exec(
            select(Character.id, Character.project_id).where(Character.id.in_(character_ids))
        ).all()
        found_ids = {r[0] for r in rows}
        missing = set(character_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"角色不存在: {missing}"},
            )
        wrong_owner = [r[0] for r in rows if r[1] != project_id]
        if wrong_owner:
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": f"角色不属于当前项目: {wrong_owner}"},
            )
    if scene_ids:
        rows = session.exec(
            select(Scene.id, Scene.project_id).where(Scene.id.in_(scene_ids))
        ).all()
        found_ids = {r[0] for r in rows}
        missing = set(scene_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"场景不存在: {missing}"},
            )
        wrong_owner = [r[0] for r in rows if r[1] != project_id]
        if wrong_owner:
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": f"场景不属于当前项目: {wrong_owner}"},
            )
    if prop_ids:
        rows = session.exec(
            select(Prop.id, Prop.project_id).where(Prop.id.in_(prop_ids))
        ).all()
        found_ids = {r[0] for r in rows}
        missing = set(prop_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"道具不存在: {missing}"},
            )
        wrong_owner = [r[0] for r in rows if r[1] != project_id]
        if wrong_owner:
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": f"道具不属于当前项目: {wrong_owner}"},
            )


@router.get("/shots/{shot_id}/references")
async def api_get_shot_references(shot_id: str, session: Session = Depends(get_session)):
    """获取分镜的所有关联实体及参考图。"""
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    return ok(ref_svc.get_shot_references(session, shot_id))


# ---- 角色关联 ----

@router.post("/shots/{shot_id}/characters")
async def api_add_shot_characters(
    shot_id: str,
    payload: ShotReferenceAdd,
    session: Session = Depends(get_session),
):
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    _validate_entities_in_project(session, shot.project_id, character_ids=payload.entity_ids)
    refs = ref_svc.add_characters(session, shot_id, payload.entity_ids)
    return ok({"added": len(refs)}, message="已添加关联角色")


@router.delete("/shots/{shot_id}/characters/{character_id}")
async def api_remove_shot_character(
    shot_id: str,
    character_id: str,
    session: Session = Depends(get_session),
):
    # 校验 shot 存在（间接确认关联归属）
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    # 校验 character 属于同一项目
    character = session.get(Character, character_id)
    if not character or character.project_id != shot.project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "角色不存在或不属于当前项目"})
    success = ref_svc.remove_character(session, shot_id, character_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "关联不存在"})
    return ok(None, message="已移除关联角色")


# ---- 场景关联 ----

@router.post("/shots/{shot_id}/scenes")
async def api_add_shot_scenes(
    shot_id: str,
    payload: ShotReferenceAdd,
    session: Session = Depends(get_session),
):
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    _validate_entities_in_project(session, shot.project_id, scene_ids=payload.entity_ids)
    refs = ref_svc.add_scenes(session, shot_id, payload.entity_ids)
    return ok({"added": len(refs)}, message="已添加关联场景")


@router.delete("/shots/{shot_id}/scenes/{scene_id}")
async def api_remove_shot_scene(
    shot_id: str,
    scene_id: str,
    session: Session = Depends(get_session),
):
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    scene = session.get(Scene, scene_id)
    if not scene or scene.project_id != shot.project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "场景不存在或不属于当前项目"})
    success = ref_svc.remove_scene(session, shot_id, scene_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "关联不存在"})
    return ok(None, message="已移除关联场景")


# ---- 道具关联 ----

@router.post("/shots/{shot_id}/props")
async def api_add_shot_props(
    shot_id: str,
    payload: ShotReferenceAdd,
    session: Session = Depends(get_session),
):
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    _validate_entities_in_project(session, shot.project_id, prop_ids=payload.entity_ids)
    refs = ref_svc.add_props(session, shot_id, payload.entity_ids)
    return ok({"added": len(refs)}, message="已添加关联道具")


@router.delete("/shots/{shot_id}/props/{prop_id}")
async def api_remove_shot_prop(
    shot_id: str,
    prop_id: str,
    session: Session = Depends(get_session),
):
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    prop = session.get(Prop, prop_id)
    if not prop or prop.project_id != shot.project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "道具不存在或不属于当前项目"})
    success = ref_svc.remove_prop(session, shot_id, prop_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "关联不存在"})
    return ok(None, message="已移除关联道具")
